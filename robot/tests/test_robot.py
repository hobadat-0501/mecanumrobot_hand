import struct
import time
from types import SimpleNamespace

import pytest

from robot_agent import drive, hardware


def test_package_imports():
    import robot_agent

    assert robot_agent is not None


def _telemetry_frame() -> bytes:
    body = bytearray(hardware.STM32_TELEMETRY_SIZE)
    body[0] = hardware.STM32_FRAME_HEADER
    body[22] = hardware.stm32_xor_checksum(bytes(body[:22]))
    body[23] = hardware.STM32_FRAME_TAIL
    return bytes(body)


def _aux_frame(current_ma: int, red: int, charging: int, state: int) -> bytes:
    body = bytearray([hardware.STM32_AUX_HEADER])
    body += current_ma.to_bytes(2, "big") + bytes([red, charging, state])
    body.append(hardware.stm32_xor_checksum(bytes(body)))
    body.append(hardware.STM32_AUX_TAIL)
    return bytes(body)


class FakeSerial:
    is_open = True

    def __init__(self, data: bytes = b"") -> None:
        self.data = bytearray(data)
        self.requested: list[int] = []
        self.written: list[bytes] = []

    @property
    def in_waiting(self) -> int:
        return len(self.data)

    def read(self, size: int) -> bytes:
        self.requested.append(size)
        chunk = bytes(self.data[:size])
        del self.data[:size]
        return chunk

    def write(self, frame: bytes) -> None:
        self.written.append(frame)


def _no_utc(monkeypatch) -> None:
    def boom() -> int:
        raise AssertionError("utc_ns must not be used for STM32/LiDAR timestamps")

    monkeypatch.setattr(hardware, "utc_ns", boom)


def test_stm32_read_does_not_wait_for_128_bytes(monkeypatch):
    _no_utc(monkeypatch)
    monkeypatch.setattr(hardware, "monotonic_ns", lambda: 777)
    data = _telemetry_frame()
    source = hardware.Stm32SerialSource("fake")
    source._serial = FakeSerial(data)
    source._read_once()
    assert source._serial.requested == [len(data)]
    assert source.latest is not None
    assert source.latest.t_ns == 777


def test_stm32_idle_read_asks_for_one_byte(monkeypatch):
    _no_utc(monkeypatch)
    source = hardware.Stm32SerialSource("fake")
    source._serial = FakeSerial(b"")
    source._read_once()
    assert source._serial.requested == [1]
    assert source.latest is None
    assert source.latest_aux is None


def test_stm32_aux_frame_is_stored(monkeypatch):
    _no_utc(monkeypatch)
    monkeypatch.setattr(hardware, "monotonic_ns", lambda: 777)
    source = hardware.Stm32SerialSource("fake")
    source._serial = FakeSerial(_aux_frame(1000, 2, 1, 3) + _telemetry_frame())
    source._read_once()
    assert source.latest_aux == hardware.Stm32AuxTelemetry(
        t_ns=777, charging_current_a=1.0, red=2, charging=True, charge_set_state=3
    )
    assert source.latest is not None
    assert source.latest.t_ns == 777


def test_decoder_returns_aux_and_telemetry_in_order():
    decoder = hardware.Stm32FrameDecoder()
    frames = decoder.feed(_telemetry_frame() + _aux_frame(0, 0, 0, 0), 5)
    assert [type(frame) for frame in frames] == [
        hardware.Stm32Telemetry,
        hardware.Stm32AuxTelemetry,
    ]


def test_send_velocity_last_command_uses_monotonic(monkeypatch):
    _no_utc(monkeypatch)
    monkeypatch.setattr(hardware, "monotonic_ns", lambda: 999)
    source = hardware.Stm32SerialSource("fake")
    source._serial = FakeSerial()
    source.send_velocity(0.1, 0.0, 0.0)
    assert source.last_command is not None
    assert source.last_command[0] == 999


def test_encode_rounds_instead_of_truncating():
    frame = hardware.encode_stm32_velocity_command(0.1 / 1.89, -0.1 / 1.89, 0.0)
    vx, vy, wz = struct.unpack(">hhh", frame[3:9])
    assert (vx, vy, wz) == (53, -53, 0)
    assert frame[0] == hardware.STM32_FRAME_HEADER
    assert frame[-1] == hardware.STM32_FRAME_TAIL
    assert frame[-2] == hardware.stm32_xor_checksum(frame[:-2])


def test_encode_range_checked_after_rounding():
    hardware.encode_stm32_velocity_command(32.767, 0.0, 0.0)
    with pytest.raises(ValueError):
        hardware.encode_stm32_velocity_command(32.7676, 0.0, 0.0)
    with pytest.raises(ValueError):
        hardware.encode_stm32_velocity_command(0.0, -32.769, 0.0)


@pytest.mark.parametrize(
    ("previous", "current", "expected"),
    [
        (None, 10.0, False),
        (350.0, 10.0, True),
        (350.0, 120.0, True),
        (10.0, 20.0, False),
        (20.0, 10.0, False),
        (180.0, 0.0, False),
    ],
)
def test_lidar_revolution_wrapped(previous, current, expected):
    assert hardware.lidar_revolution_wrapped(previous, current) is expected


def test_lidar_scan_splits_when_packets_lost_around_zero(monkeypatch):
    import math

    _no_utc(monkeypatch)
    source = hardware.N10PSerialSource("fake", profile=hardware.N10P_PROTOCOL_PROFILE)
    for degrees in (300.0, 330.0, 60.0, 90.0, 340.0, 70.0):
        point = hardware.LidarPoint(1, math.radians(degrees), 1.0, 10, 0)
        source._accept_point(point, 42)
    scan = source.latest
    assert scan is not None
    assert scan.t_ns == 42
    assert [round(math.degrees(p.angle_rad)) for p in scan.points] == [60, 90, 340]


class FakeDriveSource:
    def __init__(self, t_ns: int) -> None:
        self.latest = SimpleNamespace(t_ns=t_ns, flag_stop=0)
        self.sent: list[tuple[float, float, float]] = []

    def send_velocity(self, vx: float, vy: float, wz: float) -> None:
        self.sent.append((vx, vy, wz))


def _armed_drive(source: FakeDriveSource, now: float) -> drive.KeyboardDrive:
    keyboard = drive.KeyboardDrive(source, enable_motion=True)
    keyboard.press("w", now=now)
    return keyboard


def test_tick_freshness_compares_monotonic_values():
    source = FakeDriveSource(t_ns=5_000_000_000)
    keyboard = _armed_drive(source, now=10.0)
    assert keyboard.tick(now=10.1, now_ns=5_100_000_000) == (0.05, 0.0, 0.0)
    # 0.6 s old telemetry is stale (limit 0.5 s) and discards the command.
    assert keyboard.tick(now=10.1, now_ns=5_600_000_000) == drive.ZERO
    assert keyboard.tick(now=10.1, now_ns=5_100_000_000) == drive.ZERO


def test_tick_default_clock_is_monotonic():
    source = FakeDriveSource(t_ns=time.monotonic_ns())
    keyboard = drive.KeyboardDrive(source, enable_motion=True)
    keyboard.press("w")
    assert keyboard.tick() == (0.05, 0.0, 0.0)
    # A system-clock (epoch) timestamp is not comparable to monotonic time.
    source.latest = SimpleNamespace(t_ns=time.time_ns(), flag_stop=0)
    keyboard.press("w")
    assert keyboard.tick() == drive.ZERO
