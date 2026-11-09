import struct
import threading
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


T0 = 10_000_000_000
MS = 1_000_000


class FakeDriveSource:
    def __init__(self, t_ns: int) -> None:
        self.latest = SimpleNamespace(t_ns=t_ns, flag_stop=0)
        self.sent: list[tuple[float, float, float]] = []
        self.attempts = 0
        self.fail_first = 0
        self.fail_always = False
        self.during_send = None
        self.wrote = threading.Event()

    def send_velocity(self, vx: float, vy: float, wz: float) -> None:
        self.attempts += 1
        if self.during_send is not None:
            self.during_send()
        if self.fail_always or self.attempts <= self.fail_first:
            raise OSError("port gone")
        self.sent.append((vx, vy, wz))
        self.wrote.set()


class BlockingSource(FakeDriveSource):
    def __init__(self, t_ns: int) -> None:
        super().__init__(t_ns)
        self.entered = threading.Event()
        self.release = threading.Event()

    def send_velocity(self, vx: float, vy: float, wz: float) -> None:
        self.entered.set()
        if not self.release.wait(5.0):
            raise RuntimeError("test timeout: send_velocity was never released")
        super().send_velocity(vx, vy, wz)


def _writer(source, **kwargs) -> drive.CmdVelWriter:
    kwargs.setdefault("motion_enabled", True)
    return drive.CmdVelWriter(source, **kwargs)


def test_default_writer_writes_only_zero():
    source = FakeDriveSource(T0)
    writer = drive.CmdVelWriter(source)
    assert writer.motion_enabled is False
    assert writer.set_cmd_vel(0.1, 0.0, 0.0, now_ns=T0) is True
    assert writer.tick(now_ns=T0 + MS) == drive.ZERO
    assert source.sent == [drive.ZERO]


def test_motion_enabled_passes_command_unchanged():
    source = FakeDriveSource(T0)
    writer = _writer(source)
    writer.set_cmd_vel(0.1, -0.05, 0.2, now_ns=T0)
    assert writer.tick(now_ns=T0 + MS) == (0.1, -0.05, 0.2)
    assert source.sent == [(0.1, -0.05, 0.2)]


def test_no_speed_limit():
    source = FakeDriveSource(T0)
    writer = _writer(source)
    writer.set_cmd_vel(5.0, -3.0, 20.0, now_ns=T0)
    assert writer.tick(now_ns=T0 + MS) == (5.0, -3.0, 20.0)


def test_int16_boundary_is_accepted_unchanged():
    source = FakeDriveSource(T0)
    writer = _writer(source)
    assert writer.set_cmd_vel(32.767, -32.768, 0.0, now_ns=T0) is True
    assert writer.tick(now_ns=T0 + MS) == (32.767, -32.768, 0.0)
    assert writer.health().rejected_count == 0


@pytest.mark.parametrize(
    "values",
    [
        (float("nan"), 0.0, 0.0),
        (0.0, float("inf"), 0.0),
        (0.0, 0.0, float("-inf")),
        (32.768, 0.0, 0.0),
        (0.0, -32.769, 0.0),
        (0.0, 0.0, 32.768),
        (None, 0.0, 0.0),
    ],
)
def test_invalid_values_are_rejected_not_clamped(values):
    source = FakeDriveSource(T0)
    writer = _writer(source)
    assert writer.set_cmd_vel(0.1, 0.0, 0.0, now_ns=T0) is True
    assert writer.set_cmd_vel(*values, now_ns=T0) is False
    # The earlier valid command was cleared too, and zero is written instead.
    assert writer.tick(now_ns=T0 + MS) == drive.ZERO
    assert source.sent == [drive.ZERO]
    assert writer.health().rejected_count == 1


def test_deadman_discards_expired_command():
    source = FakeDriveSource(T0)
    writer = _writer(source)
    writer.set_cmd_vel(0.1, 0.0, 0.0, now_ns=T0)
    assert writer.tick(now_ns=T0 + 249 * MS) == (0.1, 0.0, 0.0)
    assert writer.tick(now_ns=T0 + 251 * MS) == drive.ZERO
    # Discarded, not merely zeroed: it never runs again, even with a "valid" clock.
    assert writer.tick(now_ns=T0 + 100 * MS) == drive.ZERO
    assert writer.tick(now_ns=T0 + 252 * MS) == drive.ZERO


def test_new_command_keeps_deadman_alive():
    source = FakeDriveSource(T0)
    writer = _writer(source)
    writer.set_cmd_vel(0.1, 0.0, 0.0, now_ns=T0)
    writer.set_cmd_vel(0.1, 0.0, 0.0, now_ns=T0 + 200 * MS)
    assert writer.tick(now_ns=T0 + 400 * MS) == (0.1, 0.0, 0.0)


def test_missing_telemetry_forces_zero_and_discards_command():
    source = FakeDriveSource(T0)
    source.latest = None
    writer = _writer(source)
    writer.set_cmd_vel(0.1, 0.0, 0.0, now_ns=T0)
    assert writer.tick(now_ns=T0 + MS) == drive.ZERO
    source.latest = SimpleNamespace(t_ns=T0 + MS, flag_stop=0)
    assert writer.tick(now_ns=T0 + 2 * MS) == drive.ZERO


def test_stale_telemetry_forces_zero_and_discards_command():
    source = FakeDriveSource(5_000_000_000)
    writer = _writer(source, deadman_s=5.0)
    writer.set_cmd_vel(0.05, 0.0, 0.0, now_ns=5_000_000_000)
    assert writer.tick(now_ns=5_100_000_000) == (0.05, 0.0, 0.0)
    # 0.6 s old telemetry is stale (limit 0.5 s).
    assert writer.tick(now_ns=5_600_000_000) == drive.ZERO
    # Fresh telemetry must not revive the discarded command.
    source.latest = SimpleNamespace(t_ns=5_600_000_000, flag_stop=0)
    assert writer.tick(now_ns=5_700_000_000) == drive.ZERO


def test_flag_stop_forces_zero_and_discards_command():
    source = FakeDriveSource(T0)
    writer = _writer(source)
    writer.set_cmd_vel(0.1, 0.0, 0.0, now_ns=T0)
    source.latest = SimpleNamespace(t_ns=T0, flag_stop=1)
    assert writer.tick(now_ns=T0 + MS) == drive.ZERO
    source.latest = SimpleNamespace(t_ns=T0, flag_stop=0)
    assert writer.tick(now_ns=T0 + 2 * MS) == drive.ZERO


def test_default_clock_is_monotonic():
    source = FakeDriveSource(time.monotonic_ns())
    writer = _writer(source, deadman_s=60.0, telemetry_timeout_s=60.0)
    writer.set_cmd_vel(0.05, 0.0, 0.0)
    assert writer.tick() == (0.05, 0.0, 0.0)
    # A system-clock (epoch) timestamp is not comparable to monotonic time.
    source.latest = SimpleNamespace(t_ns=time.time_ns(), flag_stop=0)
    writer.set_cmd_vel(0.05, 0.0, 0.0)
    assert writer.tick() == drive.ZERO


def test_clear_discards_command():
    source = FakeDriveSource(T0)
    writer = _writer(source)
    writer.set_cmd_vel(0.1, 0.0, 0.0, now_ns=T0)
    writer.clear()
    assert writer.tick(now_ns=T0 + MS) == drive.ZERO


def test_set_cmd_vel_does_not_block_on_slow_serial_write():
    source = BlockingSource(T0)
    writer = _writer(source)
    writer.set_cmd_vel(0.1, 0.0, 0.0, now_ns=T0)
    results: list = []

    def run_tick() -> None:
        results.append(writer.tick(now_ns=T0 + MS))

    ticker = threading.Thread(target=run_tick)
    finished = threading.Event()

    def probe() -> None:
        writer.set_cmd_vel(0.2, 0.0, 0.0, now_ns=T0 + 2 * MS)
        writer.health()
        finished.set()

    try:
        ticker.start()
        assert source.entered.wait(2.0)  # tick is now stuck inside send_velocity
        thread = threading.Thread(target=probe)
        thread.start()
        thread.join(1.0)
        assert finished.is_set(), "set_cmd_vel/health blocked while a write was in progress"
    finally:
        source.release.set()
        ticker.join(2.0)
    assert results == [(0.1, 0.0, 0.0)]
    assert writer.tick(now_ns=T0 + 3 * MS) == (0.2, 0.0, 0.0)


def test_write_error_is_recorded_and_old_command_is_not_replayed():
    source = FakeDriveSource(T0)
    writer = _writer(source)
    writer.set_cmd_vel(0.1, 0.0, 0.0, now_ns=T0)
    source.fail_always = True
    assert writer.tick(now_ns=T0 + 10 * MS) is None
    health = writer.health()
    assert health.healthy is False
    assert health.error_count == 1
    assert health.last_error == "OSError: port gone"
    source.fail_always = False
    # Recovered, still inside the deadman window, but the command was discarded.
    assert writer.tick(now_ns=T0 + 20 * MS) == drive.ZERO
    assert source.sent == [drive.ZERO]
    health = writer.health()
    assert health.healthy is True
    assert health.last_write_ns == T0 + 20 * MS
    assert health.error_count == 1
    writer.set_cmd_vel(0.2, 0.0, 0.0, now_ns=T0 + 30 * MS)
    assert writer.tick(now_ns=T0 + 40 * MS) == (0.2, 0.0, 0.0)


def test_command_set_during_failed_write_is_kept():
    source = FakeDriveSource(T0)
    writer = _writer(source)
    writer.set_cmd_vel(0.1, 0.0, 0.0, now_ns=T0)

    def inject() -> None:
        source.during_send = None
        writer.set_cmd_vel(0.3, 0.0, 0.0, now_ns=T0 + 15 * MS)

    source.during_send = inject
    source.fail_always = True
    assert writer.tick(now_ns=T0 + 10 * MS) is None
    source.fail_always = False
    assert writer.tick(now_ns=T0 + 20 * MS) == (0.3, 0.0, 0.0)


def test_loop_survives_write_errors_and_stop_writes_final_zero():
    source = FakeDriveSource(T0)
    source.fail_first = 2
    writer = drive.CmdVelWriter(source, period_s=0.001, retry_s=0.001)
    writer.start()
    try:
        assert source.wrote.wait(2.0)
        assert writer.health().running is True
    finally:
        assert writer.stop() is True
    assert source.sent[-1] == drive.ZERO
    assert all(item == drive.ZERO for item in source.sent)
    health = writer.health()
    assert health.running is False
    assert health.healthy is True
    assert health.error_count == 2
    assert health.last_error == "OSError: port gone"


def test_stop_tolerates_failing_final_zero():
    source = FakeDriveSource(T0)
    source.fail_always = True
    writer = _writer(source)
    assert writer.stop() is False
    health = writer.health()
    assert health.error_count == 1
    assert health.last_error == "OSError: port gone"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"deadman_s": 0},
        {"deadman_s": -1.0},
        {"deadman_s": float("nan")},
        {"telemetry_timeout_s": float("inf")},
        {"period_s": 0},
    ],
)
def test_constructor_rejects_bad_timing(kwargs):
    with pytest.raises(ValueError):
        drive.CmdVelWriter(FakeDriveSource(T0), **kwargs)


def test_initial_health():
    writer = drive.CmdVelWriter(FakeDriveSource(T0))
    health = writer.health()
    assert health == drive.WriterHealth(
        running=False,
        healthy=False,
        error_count=0,
        last_error=None,
        rejected_count=0,
        last_write_ns=None,
    )
