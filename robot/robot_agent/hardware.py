from __future__ import annotations

import math
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

N10P_PROTOCOL_PROFILE = "n10p-108b-v1"
N10P_PROTOCOL_PROFILES = frozenset({N10P_PROTOCOL_PROFILE})

STM32_FRAME_HEADER = 0x7B
STM32_FRAME_TAIL = 0x7D
STM32_COMMAND_SIZE = 11
STM32_TELEMETRY_SIZE = 24
STM32_AUX_HEADER = 0x7C
STM32_AUX_TAIL = 0x7F
STM32_AUX_SIZE = 8
STM32_ACCELERATOR_RATIO = 1671.84
STM32_GYROSCOPE_RATIO = 0.00026644


def monotonic_ns() -> int:
    return time.monotonic_ns()


def utc_ns() -> int:
    return time.time_ns()


def stm32_xor_checksum(data: bytes) -> int:
    value = 0
    for byte in data:
        value ^= byte
    return value


def encode_stm32_velocity_command(
    vx_mps: float,
    vy_mps: float,
    wz_radps: float,
    *,
    mode: int = 0,
    reserved: int = 0,
) -> bytes:
    values = (vx_mps, vy_mps, wz_radps)
    if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in values):
        raise ValueError("STM32 velocity command values must be finite")
    if not isinstance(mode, int) or not 0 <= mode <= 255:
        raise ValueError("STM32 command mode must be an unsigned byte")
    if not isinstance(reserved, int) or not 0 <= reserved <= 255:
        raise ValueError("STM32 reserved command byte must be an unsigned byte")
    quantized = tuple(int(round(float(value) * 1000.0)) for value in values)
    if not all(-32768 <= value <= 32767 for value in quantized):
        raise ValueError("STM32 velocity command exceeds signed 16-bit millimetre range")
    frame = bytearray((STM32_FRAME_HEADER, mode, reserved))
    frame.extend(struct.pack(">hhh", *quantized))
    frame.append(stm32_xor_checksum(bytes(frame)))
    frame.append(STM32_FRAME_TAIL)
    return bytes(frame)


@dataclass(frozen=True)
class Stm32Telemetry:
    t_ns: int
    flag_stop: int
    vx_mps: float
    vy_mps: float
    wz_radps: float
    accel_x_mps2: float
    accel_y_mps2: float
    accel_z_mps2: float
    gyro_x_radps: float
    gyro_y_radps: float
    gyro_z_radps: float
    voltage_v: float


@dataclass(frozen=True)
class Stm32AuxTelemetry:
    t_ns: int
    charging_current_a: float
    red: int
    charging: bool
    charge_set_state: int


class Stm32FrameDecoder:
    def __init__(self) -> None:
        self._buffer = bytearray()

    @staticmethod
    def _signed_i16(data: bytes, offset: int) -> int:
        return int(struct.unpack_from(">h", data, offset)[0])

    def feed(self, data: bytes, timestamp_ns: int) -> tuple[Stm32Telemetry | Stm32AuxTelemetry, ...]:
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("STM32 serial data must be bytes-like")
        if timestamp_ns < 0:
            raise ValueError("STM32 telemetry timestamp must be nonnegative")
        self._buffer.extend(data)
        decoded: list[Stm32Telemetry | Stm32AuxTelemetry] = []
        while True:
            candidates = [index for index in (self._buffer.find(bytes((STM32_FRAME_HEADER,))), self._buffer.find(bytes((STM32_AUX_HEADER,)))) if index >= 0]
            if not candidates:
                self._buffer[:] = self._buffer[-1:] if self._buffer[-1:] in (bytes((STM32_FRAME_HEADER,)), bytes((STM32_AUX_HEADER,))) else b""
                return tuple(decoded)
            index = min(candidates)
            if index:
                del self._buffer[:index]
            if self._buffer[0] == STM32_AUX_HEADER:
                if len(self._buffer) < STM32_AUX_SIZE:
                    return tuple(decoded)
                packet = bytes(self._buffer[:STM32_AUX_SIZE])
                if packet[-1] == STM32_AUX_TAIL and packet[-2] == stm32_xor_checksum(packet[:6]):
                    del self._buffer[:STM32_AUX_SIZE]
                    # UNVERIFIED layout (spec A-4): [1:3] charging mA, [3] red,
                    # [4] charging, [5] set_state. Verify on the real robot in T15.
                    decoded.append(
                        Stm32AuxTelemetry(
                            t_ns=timestamp_ns,
                            charging_current_a=int.from_bytes(packet[1:3], "big") / 1000.0,
                            red=packet[3],
                            charging=bool(packet[4]),
                            charge_set_state=packet[5],
                        )
                    )
                    continue
                del self._buffer[0]
                continue
            if len(self._buffer) < STM32_TELEMETRY_SIZE:
                return tuple(decoded)
            packet = bytes(self._buffer[:STM32_TELEMETRY_SIZE])
            if packet[-1] != STM32_FRAME_TAIL or packet[-2] != stm32_xor_checksum(packet[:22]):
                del self._buffer[0]
                continue
            del self._buffer[:STM32_TELEMETRY_SIZE]
            decoded.append(
                Stm32Telemetry(
                    t_ns=timestamp_ns,
                    flag_stop=packet[1],
                    vx_mps=self._signed_i16(packet, 2) / 1000.0,
                    vy_mps=self._signed_i16(packet, 4) / 1000.0,
                    wz_radps=self._signed_i16(packet, 6) / 1000.0,
                    accel_x_mps2=self._signed_i16(packet, 8) / STM32_ACCELERATOR_RATIO,
                    accel_y_mps2=self._signed_i16(packet, 10) / STM32_ACCELERATOR_RATIO,
                    accel_z_mps2=self._signed_i16(packet, 12) / STM32_ACCELERATOR_RATIO,
                    gyro_x_radps=self._signed_i16(packet, 14) * STM32_GYROSCOPE_RATIO,
                    gyro_y_radps=self._signed_i16(packet, 16) * STM32_GYROSCOPE_RATIO,
                    gyro_z_radps=self._signed_i16(packet, 18) * STM32_GYROSCOPE_RATIO,
                    voltage_v=int.from_bytes(packet[20:22], "big") / 1000.0,
                )
            )


class Stm32SerialSource:
    def __init__(
        self,
        port: str,
        *,
        baudrate: int = 115200,
        timeout_s: float = 0.1,
        mode: int = 0,
    ) -> None:
        if not isinstance(port, str) or not port.strip():
            raise ValueError("STM32 serial port must be nonempty")
        if not isinstance(baudrate, int) or baudrate <= 0:
            raise ValueError("STM32 baudrate must be a positive integer")
        if not math.isfinite(timeout_s) or timeout_s <= 0.0:
            raise ValueError("STM32 serial timeout must be positive and finite")
        if not isinstance(mode, int) or not 0 <= mode <= 255:
            raise ValueError("STM32 mode must be an unsigned byte")
        self.port = port
        self.baudrate = baudrate
        self.timeout_s = timeout_s
        self.mode = mode
        self._serial: Any = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._latest: Stm32Telemetry | None = None
        self._latest_aux: Stm32AuxTelemetry | None = None
        self._decoder = Stm32FrameDecoder()
        self.errors = 0
        self.last_command: tuple[int, float, float, float] | None = None

    @property
    def latest(self) -> Stm32Telemetry | None:
        with self._lock:
            return self._latest

    @property
    def latest_aux(self) -> Stm32AuxTelemetry | None:
        with self._lock:
            return self._latest_aux

    def start(self) -> None:
        try:
            import serial
        except ImportError as error:
            raise RuntimeError("pyserial is required for STM32 capture") from error
        self._stop.clear()
        self._decoder = Stm32FrameDecoder()
        self._latest = None
        self._latest_aux = None
        self.errors = 0
        try:
            self._serial = serial.Serial(
                self.port, self.baudrate, timeout=self.timeout_s, write_timeout=self.timeout_s,
            )
            self._serial.reset_input_buffer()
            self._thread = threading.Thread(target=self._run, name="stm32-reader", daemon=True)
            self._thread.start()
        except Exception:
            if self._serial is not None:
                self._serial.close()
            self._serial = None
            self._thread = None
            raise

    def send_velocity(self, vx_mps: float, vy_mps: float, wz_radps: float) -> None:
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError("STM32 serial source is not started")
        frame = encode_stm32_velocity_command(vx_mps, vy_mps, wz_radps, mode=self.mode)
        with self._write_lock:
            self._serial.write(frame)
        self.last_command = (monotonic_ns(), float(vx_mps), float(vy_mps), float(wz_radps))

    def stop(self) -> None:
        if self._serial is not None and self._serial.is_open:
            try:
                self.send_velocity(0.0, 0.0, 0.0)
            except (OSError, RuntimeError, ValueError):
                self.errors += 1
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._serial is not None:
            self._serial.close()
        self._serial = None
        self._thread = None

    def _read_once(self) -> None:
        # Read what is already buffered, but ask for at least 1 byte so an idle
        # port still blocks up to the serial timeout (no busy loop) and a busy
        # port never waits for a fixed 128-byte block.
        waiting = int(getattr(self._serial, "in_waiting", 0) or 0)
        payload = self._serial.read(max(1, min(waiting, 4096)))
        if not payload:
            return
        timestamp = monotonic_ns()
        for frame in self._decoder.feed(payload, timestamp):
            with self._lock:
                if isinstance(frame, Stm32AuxTelemetry):
                    self._latest_aux = frame
                else:
                    self._latest = frame

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._read_once()
            except Exception:
                self.errors += 1
                if self._stop.wait(0.05):
                    return


@dataclass(frozen=True)
class N10PProtocolSpec:
    packet_size: int
    point_count: int
    point_offset: int
    start_angle_offset: int
    end_angle_offset: int


N10P_PROTOCOL_SPECS = {
    N10P_PROTOCOL_PROFILE: N10PProtocolSpec(
        packet_size=108,
        point_count=16,
        point_offset=7,
        start_angle_offset=5,
        end_angle_offset=105,
    )
}


def validate_n10p_protocol_profile(profile: str) -> str:
    if not isinstance(profile, str) or profile not in N10P_PROTOCOL_SPECS:
        supported = ", ".join(sorted(N10P_PROTOCOL_PROFILES))
        raise ValueError(f"unsupported N10P protocol profile; expected one of: {supported}")
    return profile


@dataclass(frozen=True)
class LidarPoint:
    t_ns: int
    angle_rad: float
    range_m: float
    intensity: int
    return_id: int


@dataclass(frozen=True)
class LidarScan:
    t_ns: int
    points: tuple[LidarPoint, ...]

    @property
    def minimum_range_m(self) -> float:
        ranges = [point.range_m for point in self.points if point.range_m > 0.0]
        return min(ranges) if ranges else math.nan


class N10PDecoder:
    @staticmethod
    def crc(packet: bytes) -> int:
        return sum(packet) & 0xFF

    def __init__(self, profile: str) -> None:
        self.profile = validate_n10p_protocol_profile(profile)
        spec = N10P_PROTOCOL_SPECS[self.profile]
        self.packet_size = spec.packet_size
        self.point_count = spec.point_count
        self.point_offset = spec.point_offset
        self.start_angle_offset = spec.start_angle_offset
        self.end_angle_offset = spec.end_angle_offset
        self._buffer = bytearray()

    def _next_packet(self, timestamp_ns: int) -> tuple[LidarPoint, ...] | None:
        while True:
            index = self._buffer.find(b"\xA5\x5A")
            if index < 0:
                self._buffer[:] = self._buffer[-1:] if self._buffer[-1:] == b"\xA5" else b""
                return None
            if index:
                del self._buffer[:index]
            if len(self._buffer) < self.packet_size:
                return None
            packet = bytes(self._buffer[: self.packet_size])
            if packet[-1] != self.crc(packet[:-1]):
                del self._buffer[0]
                continue
            del self._buffer[: self.packet_size]
            return self.decode(packet, timestamp_ns)

    def feed_all(self, data: bytes, timestamp_ns: int) -> tuple[tuple[LidarPoint, ...], ...]:
        self._buffer.extend(data)
        packets: list[tuple[LidarPoint, ...]] = []
        while True:
            decoded = self._next_packet(timestamp_ns)
            if decoded is None:
                return tuple(packets)
            packets.append(decoded)

    def feed(self, data: bytes, timestamp_ns: int) -> tuple[LidarPoint, ...]:
        self._buffer.extend(data)
        return self._next_packet(timestamp_ns) or ()

    def decode(self, packet: bytes, timestamp_ns: int) -> tuple[LidarPoint, ...]:
        if len(packet) != self.packet_size or packet[:2] != b"\xA5\x5A":
            raise ValueError("N10P packet header or size is invalid")
        if packet[-1] != self.crc(packet[:-1]):
            raise ValueError("N10P packet CRC mismatch")
        start = int.from_bytes(packet[self.start_angle_offset : self.start_angle_offset + 2], "big") / 100.0
        end = int.from_bytes(packet[self.end_angle_offset : self.end_angle_offset + 2], "big") / 100.0
        interval = (end - start) % 360.0
        entries: list[tuple[int, int, int, int]] = []
        for index in range(self.point_count):
            offset = self.point_offset + index * 6
            for return_id, distance_offset in enumerate((0, 3)):
                distance = int.from_bytes(packet[offset + distance_offset : offset + distance_offset + 2], "big")
                if distance not in (0, 0xFFFF):
                    intensity = packet[offset + distance_offset + 2]
                    entries.append((index, return_id, distance, intensity))
        valid_slots = max(1, self.point_count - 1)
        points: list[LidarPoint] = []
        for index, return_id, distance, intensity in entries:
            angle = math.radians((start + interval * index / valid_slots) % 360.0)
            points.append(LidarPoint(timestamp_ns, angle, distance / 1000.0, intensity, return_id))
        return tuple(points)


def lidar_revolution_wrapped(previous_deg: float | None, current_deg: float) -> bool:
    """True when the angle fell by more than 180 degrees (new revolution, even after packet loss)."""
    return previous_deg is not None and previous_deg - current_deg > 180.0


class N10PSerialSource:
    def __init__(
        self,
        port: str,
        *,
        profile: str,
        baudrate: int = 460800,
        timeout_s: float = 0.1,
    ) -> None:
        self.port = port
        self.protocol_profile = validate_n10p_protocol_profile(profile)
        self.baudrate = baudrate
        self.timeout_s = timeout_s
        self._serial: Any = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._latest: LidarScan | None = None
        self._decoder = N10PDecoder(self.protocol_profile)
        self._scan_times = deque(maxlen=24)
        self._last_angle_deg: float | None = None
        self._points: list[LidarPoint] = []
        self.error: Exception | None = None

    @property
    def latest(self) -> LidarScan | None:
        with self._lock:
            return self._latest

    @property
    def scan_rate_hz(self) -> float:
        with self._lock:
            if len(self._scan_times) < 2:
                return 0.0
            elapsed = self._scan_times[-1] - self._scan_times[0]
            return (len(self._scan_times) - 1) / elapsed if elapsed > 0.0 else 0.0

    def start(self) -> None:
        try:
            import serial
        except ImportError as error:
            raise RuntimeError("pyserial is required for N10P capture") from error
        self._stop.clear()
        self._decoder = N10PDecoder(self.protocol_profile)
        self._latest = None
        self._last_angle_deg = None
        self._points = []
        self.error = None
        with self._lock:
            self._scan_times.clear()
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout_s, write_timeout=self.timeout_s)
            self._serial.write(self.start_command())
            self._thread = threading.Thread(target=self._run_guarded, name="n10p-reader", daemon=True)
            self._thread.start()
        except Exception:
            if self._serial is not None:
                self._serial.close()
            self._serial = None
            raise

    def stop(self) -> None:
        self._stop.set()
        if self._serial is not None:
            try:
                self._serial.write(self.stop_command())
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._serial is not None:
            self._serial.close()
        self._serial = None
        self._thread = None

    @staticmethod
    def start_command() -> bytes:
        command = bytearray(188)
        command[0:3] = b"\xA5\x5A\x55"
        command[184:188] = b"\x01\x01\xFA\xFB"
        return bytes(command)

    @staticmethod
    def stop_command() -> bytes:
        command = bytearray(188)
        command[0:3] = b"\xA5\x5A\x55"
        command[184:188] = b"\x01\x00\xFA\xFB"
        return bytes(command)

    def _run_guarded(self) -> None:
        try:
            self._run()
        except Exception as error:
            self.error = error
            self._stop.set()

    def _accept_point(self, point: LidarPoint, timestamp_ns: int) -> None:
        angle = math.degrees(point.angle_rad)
        if lidar_revolution_wrapped(self._last_angle_deg, angle) and self._points:
            with self._lock:
                self._latest = LidarScan(timestamp_ns, tuple(self._points))
                self._scan_times.append(time.monotonic())
            self._points = []
        self._points.append(point)
        self._last_angle_deg = angle

    def _run(self) -> None:
        while not self._stop.is_set():
            waiting = int(getattr(self._serial, "in_waiting", 0) or 0)
            payload = self._serial.read(max(256, min(waiting, 4096)))
            if not payload:
                continue
            timestamp = monotonic_ns()
            for decoded in self._decoder.feed_all(payload, timestamp):
                for point in decoded:
                    self._accept_point(point, timestamp)


@dataclass(frozen=True)
class AstraFrame:
    t_ns: int
    color_bgr: Any
    depth_raw: Any
    depth_scale_m: float
    device_timestamp_ns: int | None = None
    timestamp_source: str = "host_receive_time"

    def __post_init__(self) -> None:
        if self.t_ns < 0 or not math.isfinite(self.depth_scale_m) or self.depth_scale_m <= 0.0:
            raise ValueError("Astra frame timestamp and depth scale must be valid")
        if self.device_timestamp_ns is not None and self.device_timestamp_ns < 0:
            raise ValueError("Astra device timestamp must be nonnegative")
        if not isinstance(self.timestamp_source, str) or not self.timestamp_source.strip():
            raise ValueError("Astra timestamp source must be nonempty")


def openni_frame_timestamp_ns(frame: Any) -> int | None:
    accessors: list[Any] = []
    for name in ("get_timestamp", "timestamp"):
        try:
            accessors.append(getattr(frame, name))
        except Exception:
            continue
    for accessor in accessors:
        try:
            value = accessor() if callable(accessor) else accessor
        except Exception:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        try:
            numeric_value = float(value)
        except (OverflowError, TypeError, ValueError):
            continue
        if not math.isfinite(numeric_value) or numeric_value < 0.0:
            continue
        return int(round(numeric_value * 1000.0))
    return None


class AstraSSource:
    def __init__(
        self,
        *,
        uri: str | None = None,
        sdk_path: str | None = None,
        depth_scale_m: float = 0.001,
        max_pair_skew_us: float | None = None,
    ) -> None:
        if not math.isfinite(depth_scale_m) or depth_scale_m <= 0.0:
            raise ValueError("Astra depth scale must be positive and finite")
        if max_pair_skew_us is not None and (
            not math.isfinite(max_pair_skew_us) or max_pair_skew_us <= 0.0
        ):
            raise ValueError("Astra pair skew limit must be positive and finite")
        self.uri = uri
        self.sdk_path = sdk_path
        self.depth_scale_m = depth_scale_m
        self.max_pair_skew_us = max_pair_skew_us
        self._openni: Any = None
        self._device: Any = None
        self._color_stream: Any = None
        self._depth_stream: Any = None
        self._last_capture_t_ns = 0
        self._frames_read = 0
        self._device_timestamp_frames = 0
        self._paired_timestamp_frames = 0
        self._max_pair_skew_ns = 0

    def start(self) -> None:
        try:
            from openni import openni2
        except ImportError:
            try:
                import openni2
            except ImportError:
                try:
                    # Orbbec's legacy SDK commonly ships the same bindings
                    # under the ``primesense`` package name.
                    from primesense import openni2
                except ImportError as primesense_error:
                    raise RuntimeError(
                        "OpenNI2 Python bindings are required for Astra-S capture"
                    ) from primesense_error
        self._openni = openni2
        try:
            self._openni.initialize(self.sdk_path) if self.sdk_path else self._openni.initialize()
            if self.uri:
                self._device = self._openni.Device.open_file(self.uri)
            else:
                self._device = self._openni.Device.open_any()
            self._depth_stream = self._device.create_depth_stream()
            self._color_stream = self._device.create_color_stream()
            # Ask the Astra driver for depth-to-colour registration and
            # hardware timestamp synchronisation when those capabilities are
            # exposed.  Older firmware may not implement either method, so
            # keep the acquisition path compatible and let timing metadata
            # report the observed result.
            self._depth_stream.start()
            self._color_stream.start()
            try:
                registration = self._openni.IMAGE_REGISTRATION_DEPTH_TO_COLOR
                if self._device.is_image_registration_mode_supported(registration):
                    self._device.set_image_registration_mode(registration)
            except (AttributeError, RuntimeError, TypeError):
                pass
            try:
                self._device.set_depth_color_sync_enabled(True)
            except (AttributeError, RuntimeError, TypeError):
                pass
        except Exception:
            self.stop()
            raise

    def read(self) -> AstraFrame:
        if self._depth_stream is None or self._color_stream is None:
            raise RuntimeError("Astra-S source is not started")
        try:
            import numpy as np
        except ImportError as error:
            raise RuntimeError("numpy is required for Astra-S capture") from error
        color_frame = self._color_stream.read_frame()
        depth_frame = self._depth_stream.read_frame()
        color_device_timestamp_ns = openni_frame_timestamp_ns(color_frame)
        depth_device_timestamp_ns = openni_frame_timestamp_ns(depth_frame)
        if color_device_timestamp_ns is not None and depth_device_timestamp_ns is not None:
            pair_skew_ns = abs(color_device_timestamp_ns - depth_device_timestamp_ns)
            self._paired_timestamp_frames += 1
            self._max_pair_skew_ns = max(self._max_pair_skew_ns, pair_skew_ns)
            if self.max_pair_skew_us is not None and pair_skew_ns > self.max_pair_skew_us * 1000.0:
                raise RuntimeError("Astra color/depth device timestamps exceed the configured pair skew")
        if color_device_timestamp_ns is not None or depth_device_timestamp_ns is not None:
            self._device_timestamp_frames += 1
        color_width = int(color_frame.width)
        color_height = int(color_frame.height)
        color = np.frombuffer(color_frame.get_buffer_as_uint8(), dtype=np.uint8)
        if color.size != color_width * color_height * 3:
            raise RuntimeError("Astra color frame is not RGB888")
        color = color.reshape((color_height, color_width, 3))[:, :, ::-1].copy()
        depth_width = int(depth_frame.width)
        depth_height = int(depth_frame.height)
        depth = np.frombuffer(depth_frame.get_buffer_as_uint16(), dtype=np.uint16)
        if depth.size != depth_width * depth_height:
            raise RuntimeError("Astra depth frame is not uint16")
        capture_t_ns = max(utc_ns(), self._last_capture_t_ns + 1)
        self._last_capture_t_ns = capture_t_ns
        self._frames_read += 1
        return AstraFrame(
            capture_t_ns,
            color,
            depth.reshape((depth_height, depth_width)).copy(),
            self.depth_scale_m,
            color_device_timestamp_ns if color_device_timestamp_ns is not None else depth_device_timestamp_ns,
            "host_receive_time",
        )

    def timing_metadata(self) -> dict[str, Any]:
        return {
            "canonical_timestamp": "host_receive_time",
            "device_timestamp_unit": "microseconds_converted_to_nanoseconds",
            "device_timestamp_frames": self._device_timestamp_frames,
            "paired_timestamp_frames": self._paired_timestamp_frames,
            "frames_read": self._frames_read,
            "max_observed_pair_skew_us": self._max_pair_skew_ns / 1000.0,
            "pair_skew_limit_us": self.max_pair_skew_us,
        }

    def stop(self) -> None:
        for stream in (self._color_stream, self._depth_stream):
            if stream is not None:
                try:
                    stream.stop()
                except Exception:
                    pass
        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
        if self._openni is not None:
            try:
                self._openni.unload()
            except Exception:
                pass
        self._color_stream = None
        self._depth_stream = None
        self._device = None
        self._openni = None
