import asyncio
import json
import math
import struct
import threading
import time
from types import SimpleNamespace

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from robot_agent import __main__ as agent
from robot_agent import config, drive, hardware, server, sim


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


class TimedSource(FakeDriveSource):
    def __init__(self, t_ns: int) -> None:
        super().__init__(t_ns)
        self.times: list[float] = []
        self.second_attempt = threading.Event()

    def send_velocity(self, vx: float, vy: float, wz: float) -> None:
        self.times.append(time.monotonic())
        if len(self.times) == 2:
            self.second_attempt.set()
        super().send_velocity(vx, vy, wz)


def test_retry_backoff_is_waited_after_write_error():
    source = TimedSource(T0)
    source.fail_first = 1
    writer = drive.CmdVelWriter(source, period_s=0.01, retry_s=0.2)
    writer.start()
    try:
        assert source.second_attempt.wait(3.0)
    finally:
        assert writer.stop() is True
    # The first write failed, so the next attempt must wait retry_s (not the 0.01 s period).
    assert source.times[1] - source.times[0] >= 0.18


# ---------------------------------------------------------------- T04: config


def _clear_robot_env(monkeypatch) -> None:
    for name in (
        "ROBOT_MOTION_ENABLED",
        "ROBOT_SIMULATE",
        "STM_PORT",
        "STM_BAUD",
        "LIDAR_PORT",
        "LIDAR_BAUD",
        "ROBOT_BIND_HOST",
        "ROBOT_BIND_PORT",
        "ROBOT_LINK_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


def test_config_defaults_are_safe():
    cfg = config.load_config({"ROBOT_LINK_TOKEN": "x"})
    assert cfg.motion_enabled is False
    assert cfg.simulate is False
    assert cfg.bind_host == "127.0.0.1"
    assert cfg.bind_port == 8765
    assert cfg.stm_baud == 115200
    assert cfg.lidar_baud == 460800
    assert cfg.link_token == "x"


def test_config_parses_values():
    cfg = config.load_config(
        {
            "ROBOT_LINK_TOKEN": "tok",
            "ROBOT_MOTION_ENABLED": "TRUE",
            "ROBOT_SIMULATE": "1",
            "ROBOT_BIND_HOST": "100.69.39.18",
            "ROBOT_BIND_PORT": "9000",
            "STM_PORT": "/dev/ttyUSB0",
        }
    )
    assert cfg.motion_enabled is True
    assert cfg.simulate is True
    assert cfg.bind_host == "100.69.39.18"
    assert cfg.bind_port == 9000
    assert cfg.stm_port == "/dev/ttyUSB0"


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"ROBOT_LINK_TOKEN": ""},
        {"ROBOT_LINK_TOKEN": "   "},
        {"ROBOT_LINK_TOKEN": "x", "ROBOT_BIND_HOST": "0.0.0.0"},
        {"ROBOT_LINK_TOKEN": "x", "ROBOT_MOTION_ENABLED": "maybe"},
        {"ROBOT_LINK_TOKEN": "x", "ROBOT_BIND_PORT": "abc"},
        {"ROBOT_LINK_TOKEN": "x", "ROBOT_BIND_PORT": "70000"},
    ],
)
def test_config_refuses_bad_values(env):
    with pytest.raises(config.ConfigError):
        config.load_config(env)


def test_config_reads_env_file_and_real_env_wins(tmp_path, monkeypatch):
    _clear_robot_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("ROBOT_LINK_TOKEN=from-file\nROBOT_BIND_PORT=9001\nROBOT_SIMULATE=true\n")
    cfg = config.load_config(env_file=env_file)
    assert (cfg.link_token, cfg.bind_port, cfg.simulate) == ("from-file", 9001, True)
    monkeypatch.setenv("ROBOT_BIND_PORT", "9002")
    assert config.load_config(env_file=env_file).bind_port == 9002


def test_config_missing_env_file_means_empty_token(tmp_path, monkeypatch):
    _clear_robot_env(monkeypatch)
    with pytest.raises(config.ConfigError):
        config.load_config(env_file=tmp_path / "missing.env")


# ------------------------------------------------------------------ T04: sim


def test_sim_stm32_first_order_response_in_wire_units():
    now = [1_000]
    stm = sim.SimulatedStm32(tau_s=0.1, clock_ns=lambda: now[0])
    assert stm.latest is None
    stm.start()
    first = stm.latest
    assert (first.vx_mps, first.vy_mps, first.wz_radps) == (0.0, 0.0, 0.0)
    stm.send_velocity(0.1, -0.1, 0.0)
    now[0] += 100_000_000  # one time constant: 1 - exp(-1) = 0.632 of the target
    one_tau = stm.latest
    assert one_tau.vx_mps == pytest.approx(0.063, abs=1e-9)
    assert one_tau.vy_mps == pytest.approx(-0.063, abs=1e-9)
    assert one_tau.t_ns > first.t_ns
    now[0] += 1_000_000_000
    settled = stm.latest
    assert settled.vx_mps == pytest.approx(0.1, abs=1e-9)
    assert settled.t_ns > one_tau.t_ns
    assert stm.last_command[1:] == (0.1, -0.1, 0.0)
    assert stm.latest_aux is not None and stm.latest_aux.t_ns == settled.t_ns


def test_sim_stm32_timestamps_never_go_backwards():
    now = [5_000]
    stm = sim.SimulatedStm32(clock_ns=lambda: now[0])
    stm.start()
    stamps = []
    for value in (6_000, 6_000, 5_500, 7_000):
        now[0] = value
        stamps.append(stm.latest.t_ns)
    assert stamps == sorted(stamps)


def test_sim_stm32_validates_and_requires_start():
    stm = sim.SimulatedStm32()
    with pytest.raises(RuntimeError):
        stm.send_velocity(0.0, 0.0, 0.0)
    stm.start()
    with pytest.raises(ValueError):
        stm.send_velocity(float("nan"), 0.0, 0.0)
    with pytest.raises(ValueError):
        stm.send_velocity(32.768, 0.0, 0.0)
    stm.stop()
    assert stm.latest is None
    with pytest.raises(RuntimeError):
        stm.send_velocity(0.0, 0.0, 0.0)


def test_sim_lidar_produces_scans_at_the_configured_rate():
    now = [0]
    lidar = sim.SimulatedLidar(period_s=0.1, clock_ns=lambda: now[0])
    assert lidar.latest is None
    assert lidar.scan_rate_hz == 0.0
    lidar.start()
    assert lidar.latest is None  # first scan only after one full period
    assert lidar.scan_rate_hz == pytest.approx(10.0)
    now[0] = 100_000_000
    first = lidar.latest
    assert len(first.points) == 360
    assert first.t_ns == 100_000_000
    assert lidar.latest is first  # same period, same scan
    now[0] = 250_000_000
    assert lidar.latest.t_ns == 200_000_000
    lidar.stop()
    assert lidar.latest is None


# ---------------------------------------------------------------- T04: server

TOKEN = "unit-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeWriter:
    def __init__(self) -> None:
        self.calls: list[tuple[float, float, float]] = []
        self.clears = 0

    def set_cmd_vel(self, vx, vy, wz, now_ns=None) -> bool:
        self.calls.append((vx, vy, wz))
        return True

    def clear(self) -> None:
        self.clears += 1

    def health(self) -> drive.WriterHealth:
        return drive.WriterHealth(True, True, 0, None, 0, None)


def _devices_ok() -> dict:
    ok = {"ok": True, "state": "ok", "error": None, "restarts": 0}
    return {"stm": dict(ok), "lidar": dict(ok)}


async def wait_for(predicate, timeout: float = 3.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            raise AssertionError("timed out waiting for condition")
        await asyncio.sleep(0.005)


class Rig:
    def __init__(self, srv, writer, stm, port: int) -> None:
        self.srv = srv
        self.writer = writer
        self.stm = stm
        self.url = f"ws://127.0.0.1:{port}/ws"

    def connect(self, headers=AUTH, url=None):
        return connect(url or self.url, additional_headers=headers)


async def _make_rig(writer, devices=_devices_ok) -> Rig:
    stm = sim.SimulatedStm32()
    stm.start()
    srv = server.RobotServer(token=TOKEN, writer=writer, stm=stm, devices=devices)
    port = await srv.start("127.0.0.1", 0)
    return Rig(srv, writer, stm, port)


@pytest.fixture
async def rig():
    made = await _make_rig(FakeWriter())
    yield made
    await made.srv.close()
    made.stm.stop()


def _cmd(seq=1, vx=0.1, vy=0.0, wz=0.0, **extra) -> str:
    return json.dumps({"t": "cmd_vel", "seq": seq, "vx": vx, "vy": vy, "wz": wz, **extra})


async def test_wrong_or_missing_token_is_refused_at_handshake(rig):
    for headers in (
        {"Authorization": "Bearer wrong"},
        {"Authorization": "Bearer "},
        {"Authorization": TOKEN},
        {"Authorization": f"bearer {TOKEN}"},
        {},
    ):
        with pytest.raises(InvalidStatus) as refused:
            async with rig.connect(headers):
                pass
        assert refused.value.response.status_code == 401
    assert rig.writer.calls == []


async def _raw_handshake_status(port: int, extra_headers: bytes) -> bytes:
    """Send a hand-written upgrade request (so headers can be malformed) and return the status line."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(
            b"GET /ws HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n"
            + extra_headers
            + b"\r\n"
        )
        await writer.drain()
        return await asyncio.wait_for(reader.readline(), 3)
    finally:
        writer.close()


@pytest.mark.parametrize(
    "extra",
    [
        b"Authorization: Bearer " + TOKEN.encode() + b"\r\nAuthorization: Bearer " + TOKEN.encode() + b"\r\n",
        b"Authorization: Bearer \xc3\xa9\r\n",  # non-ASCII (UTF-8 bytes)
        b"Authorization: Bearer \xff\xfe\r\n",  # non-ASCII (invalid UTF-8)
        b"Authorization:\r\n",
        b"",
    ],
    ids=["duplicated", "non-ascii-utf8", "non-ascii-latin1", "empty", "missing"],
)
async def test_malformed_authorization_header_gets_401_not_500(rig, extra):
    port = int(rig.url.rsplit(":", 1)[1].split("/")[0])
    status = await _raw_handshake_status(port, extra)
    assert status.startswith(b"HTTP/1.1 401"), status
    assert rig.writer.calls == []


async def test_valid_authorization_header_still_upgrades(rig):
    port = int(rig.url.rsplit(":", 1)[1].split("/")[0])
    status = await _raw_handshake_status(port, b"Authorization: Bearer " + TOKEN.encode() + b"\r\n")
    assert status.startswith(b"HTTP/1.1 101"), status
    assert rig.writer.clears == 0


async def test_other_path_is_refused(rig):
    with pytest.raises(InvalidStatus) as refused:
        async with rig.connect(url=rig.url.replace("/ws", "/other")):
            pass
    assert refused.value.response.status_code == 404


async def test_valid_cmd_vel_reaches_the_writer(rig):
    async with rig.connect() as ws:
        await ws.send(_cmd(seq=5, vx=0.1, vy=-0.2, wz=0.3))
        await wait_for(lambda: rig.writer.calls == [(0.1, -0.2, 0.3)])
        # Integers are valid numbers too, and there is no speed limit here.
        await ws.send(_cmd(seq=6, vx=3, vy=0, wz=-9))
        await wait_for(lambda: len(rig.writer.calls) == 2)
    assert rig.writer.calls[1] == (3, 0, -9)


async def test_anything_but_cmd_vel_never_reaches_the_writer(rig):
    bad = [
        "not json",
        "{",
        "",
        "null",
        "[]",
        "[1, 2, 3]",
        '"cmd_vel"',
        "42",
        json.dumps({"t": "arm", "on": True}),
        json.dumps({"t": "hello", "token": "x"}),
        json.dumps({"t": "odom_reset"}),
        json.dumps({"t": "state"}),
        json.dumps({"seq": 1, "vx": 0.1, "vy": 0, "wz": 0}),
        json.dumps({"t": "cmd_vel", "seq": 1, "vx": 0.1, "vy": 0}),
        json.dumps({"t": "cmd_vel", "seq": 1, "vx": "0.1", "vy": 0, "wz": 0}),
        json.dumps({"t": "cmd_vel", "seq": 1, "vx": True, "vy": 0, "wz": 0}),
        json.dumps({"t": "cmd_vel", "seq": 1, "vx": None, "vy": 0, "wz": 0}),
        json.dumps({"t": "cmd_vel", "seq": "1", "vx": 0.1, "vy": 0, "wz": 0}),
        json.dumps({"t": "cmd_vel", "seq": 1.5, "vx": 0.1, "vy": 0, "wz": 0}),
        json.dumps({"t": "cmd_vel", "seq": True, "vx": 0.1, "vy": 0, "wz": 0}),
        json.dumps({"t": "wheel_speeds", "seq": 1, "vx": 0.1, "vy": 0, "wz": 0}),
        _cmd(src="keyboard"),
        _cmd().encode(),  # a binary frame, even with valid JSON inside
        b"\x00\x01\x02",
    ]
    async with rig.connect() as ws:
        for message in bad:
            await ws.send(message)
        await ws.send(_cmd(seq=99, vx=0.5))  # sentinel, processed after all of the above
        await wait_for(lambda: len(rig.writer.calls) >= 1)
    assert rig.writer.calls == [(0.5, 0.0, 0.0)]
    assert rig.srv.ignored == len(bad)


async def test_new_connection_replaces_the_old_one(rig):
    async with rig.connect() as first:
        await first.send(_cmd(seq=1, vx=0.1))
        await wait_for(lambda: len(rig.writer.calls) == 1)
        async with rig.connect() as second:
            await asyncio.wait_for(first.wait_closed(), 3.0)
            assert first.close_code == 4000
            assert rig.writer.clears == 1  # the replaced link's command was cleared
            await second.send(_cmd(seq=2, vx=0.2))
            await wait_for(lambda: len(rig.writer.calls) == 2)
            assert rig.writer.calls[1] == (0.2, 0.0, 0.0)
        await wait_for(lambda: rig.writer.clears == 2)  # and the newest one clears on close


async def test_disconnect_clears_writer_and_zero_is_written():
    made = await _make_rig(FakeWriter())
    # Real writer on the simulated STM32. A long deadman proves clear() stops the robot,
    # not the 250 ms timeout.
    stm_writer = drive.CmdVelWriter(
        made.stm, motion_enabled=True, deadman_s=30.0, period_s=0.01, retry_s=0.01
    )
    made.srv.writer = stm_writer
    stm_writer.start()
    try:
        async with made.connect() as ws:
            await ws.send(_cmd(seq=1, vx=0.2, vy=0.0, wz=0.0))
            await wait_for(
                lambda: made.stm.last_command is not None and made.stm.last_command[1] == 0.2
            )
        await wait_for(lambda: made.stm.last_command[1:] == (0.0, 0.0, 0.0))
        await asyncio.sleep(0.1)  # the old command does not come back
        assert made.stm.last_command[1:] == (0.0, 0.0, 0.0)
    finally:
        await made.srv.close()
        assert await asyncio.to_thread(stm_writer.stop) is True
        made.stm.stop()


async def test_state_messages_have_required_fields_and_rate_limit(rig):
    messages = []
    async with rig.connect() as ws:
        loop = asyncio.get_running_loop()
        start = loop.time()
        while loop.time() - start < 0.6:
            messages.append(json.loads(await asyncio.wait_for(ws.recv(), 1.0)))
        await ws.send(_cmd(seq=7))
        while True:
            state = json.loads(await asyncio.wait_for(ws.recv(), 1.0))
            if state["last_cmd_seq"] == 7:
                break
    first = messages[0]
    assert first["t"] == "state"
    assert isinstance(first["t_mono_ns"], int)
    assert first["last_cmd_seq"] is None
    assert set(first["vel"]) == {"vx", "vy", "wz"}
    assert set(first["imu"]) == {"ax", "ay", "az", "gx", "gy", "gz"}
    assert first["voltage"] == 12.0
    assert first["flag_stop"] == 0
    assert set(first["charge"]) == {"current_a", "red", "charging", "set_state"}
    assert set(first["health"]) == {"stm", "lidar", "writer"}
    assert first["health"]["stm"]["ok"] is True
    assert set(first["health"]["writer"]) == {
        "running",
        "healthy",
        "error_count",
        "last_error",
        "rejected_count",
    }
    stamps = [m["t_mono_ns"] for m in messages]
    assert stamps == sorted(stamps)
    assert len(messages) >= 5
    assert len(messages) <= 0.6 * 50 + 3  # at most about 50 Hz


async def test_state_without_telemetry_has_null_sensor_fields():
    made = await _make_rig(FakeWriter())
    made.stm.stop()  # no telemetry at all
    try:
        async with made.connect() as ws:
            state = json.loads(await asyncio.wait_for(ws.recv(), 1.0))
        assert state["vel"] is None and state["imu"] is None and state["charge"] is None
        assert state["voltage"] is None and state["flag_stop"] is None
        assert isinstance(state["t_mono_ns"], int)
    finally:
        await made.srv.close()


async def test_failed_device_does_not_stop_the_server_and_is_retried():
    allow_lidar = threading.Event()
    attempts = []

    class FlakyLidar(sim.SimulatedLidar):
        def start(self) -> None:
            attempts.append(1)
            if not allow_lidar.is_set():
                raise OSError("no lidar")
            super().start()

    stm_dev = agent.SupervisedDevice(
        "stm", sim.SimulatedStm32, agent._latest_stamp, stale_s=1.0, poll_s=0.01
    )
    lidar_dev = agent.SupervisedDevice(
        "lidar",
        lambda: FlakyLidar(period_s=0.02),
        agent._latest_stamp,
        stale_s=1.0,
        backoff_s=0.01,
        max_backoff_s=0.02,
        poll_s=0.01,
    )
    writer = drive.CmdVelWriter(stm_dev, motion_enabled=True, period_s=0.01, retry_s=0.01)
    srv = server.RobotServer(
        token=TOKEN,
        writer=writer,
        stm=stm_dev,
        devices=lambda: {"stm": stm_dev.health(), "lidar": lidar_dev.health()},
    )
    port = await srv.start("127.0.0.1", 0)
    writer.start()
    tasks = [asyncio.ensure_future(stm_dev.run()), asyncio.ensure_future(lidar_dev.run())]
    try:
        await wait_for(lambda: stm_dev.health()["ok"] and len(attempts) >= 2)
        async with connect(f"ws://127.0.0.1:{port}/ws", additional_headers=AUTH) as ws:
            state = json.loads(await asyncio.wait_for(ws.recv(), 1.0))
            assert state["health"]["lidar"]["ok"] is False
            assert "no lidar" in state["health"]["lidar"]["error"]
            assert state["health"]["stm"]["ok"] is True
            assert state["vel"] is not None  # the STM32 side keeps working
            allow_lidar.set()
            await wait_for(lambda: lidar_dev.health()["ok"])
            assert lidar_dev.health()["restarts"] >= 2
            await ws.send(_cmd(seq=3, vx=0.1))
            await wait_for(lambda: stm_dev.latest.vx_mps > 0.0)  # writer still drives the sim
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await srv.close()
        await asyncio.to_thread(writer.stop)


async def test_stalled_device_is_restarted():
    created = []

    class Frozen:
        def __init__(self) -> None:
            self.latest = SimpleNamespace(t_ns=1)
            self.stopped = False

        def start(self) -> None:
            pass

        def stop(self) -> None:
            self.stopped = True

    def factory() -> Frozen:
        created.append(Frozen())
        return created[-1]

    device = agent.SupervisedDevice(
        "stm",
        factory,
        agent._latest_stamp,
        stale_s=0.1,
        backoff_s=0.01,
        max_backoff_s=0.02,
        poll_s=0.01,
    )
    task = asyncio.ensure_future(device.run())
    try:
        await wait_for(lambda: len(created) >= 2)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert created[0].stopped is True
    assert device.restarts >= 1
    assert device.latest is None  # no source is exposed once supervision ended
    assert created[-1].stopped is True


async def test_device_without_source_is_safe_for_the_writer():
    device = agent.SupervisedDevice("stm", sim.SimulatedStm32, agent._latest_stamp, stale_s=1.0)
    assert device.latest is None
    assert device.latest_aux is None
    with pytest.raises(RuntimeError):
        device.send_velocity(0.0, 0.0, 0.0)
    assert device.health()["ok"] is False


async def test_bind_retries_until_the_address_is_available():
    class FlakyServer:
        def __init__(self) -> None:
            self.attempts = 0

        async def start(self, host, port):
            self.attempts += 1
            if self.attempts < 3:
                raise OSError(99, "Cannot assign requested address")
            return 4321

    fake = FlakyServer()
    port = await asyncio.wait_for(
        agent.bind_with_retry(fake, "100.69.39.18", 8765, delay_s=0.001, max_delay_s=0.002), 3.0
    )
    assert port == 4321
    assert fake.attempts == 3


# ---- LiDAR scan frames (PROTO-2, T13) ----


def _scan(points, t_ns=5_000_000_000) -> hardware.LidarScan:
    return hardware.LidarScan(
        t_ns, tuple(hardware.LidarPoint(t_ns, math.radians(deg), m, 100, 0) for deg, m in points)
    )


def _decode_scan(frame: bytes):
    kind, ver, seq, t_ms = struct.unpack_from("<BBIQ", frame)
    return kind, ver, seq, t_ms, struct.unpack_from("<360H", frame, 14)


def test_scan_frame_header_size_and_bins():
    frame = server.build_scan_frame(_scan([(0, 1.5), (90, 2.0), (359, 0.25)]), seq=7)
    assert len(frame) == server.SCAN_FRAME_SIZE == 14 + 720
    assert server.SCAN_HEADER.format == "<BBIQ"
    kind, ver, seq, t_ms, ranges = _decode_scan(frame)
    assert (kind, ver, seq, t_ms) == (server.SCAN_FRAME_TYPE, server.SCAN_FRAME_VER, 7, 5000)
    assert ranges[0] == 1500 and ranges[90] == 2000 and ranges[359] == 250
    assert sum(1 for r in ranges if r) == 3  # every other bin means "no point"


def test_scan_frame_keeps_the_nearest_point_per_bin():
    frame = server.build_scan_frame(_scan([(10.2, 3.0), (9.8, 1.0), (10, 2.0)]), seq=1)
    assert _decode_scan(frame)[4][10] == 1000


def test_scan_frame_empty_and_invalid_points():
    empty = _decode_scan(server.build_scan_frame(_scan([]), seq=1))
    assert set(empty[4]) == {0}
    bad = _scan([(5, 0.0), (6, -1.0), (7, math.nan), (8, math.inf), (9, 100.0)])
    ranges = _decode_scan(server.build_scan_frame(bad, seq=1))[4]
    assert ranges[5:9] == (0, 0, 0, 0)
    assert ranges[9] == 0xFFFF  # clamped to u16


def test_scan_frame_wraps_angles_and_sequence():
    ranges = _decode_scan(server.build_scan_frame(_scan([(360, 1.0), (-1, 2.0)]), seq=2**32 + 3))
    assert ranges[4][0] == 1000 and ranges[4][359] == 2000 and ranges[2] == 3


def test_sim_lidar_scene_is_recognisable():
    now = [0]
    lidar = sim.SimulatedLidar(period_s=0.1, clock_ns=lambda: now[0])
    lidar.start()
    now[0] = 150_000_000
    scan = lidar.latest
    assert scan is not None and len(scan.points) == 360
    ranges = _decode_scan(server.build_scan_frame(scan, 1))[4]
    assert all(r > 0 for r in ranges)
    assert len(set(ranges)) > 100  # walls, a box and a pillar, not a constant ring


class _FakeLidar:
    def __init__(self) -> None:
        self.latest = None
        self.n = 0

    def publish(self) -> None:
        self.n += 1
        self.latest = _scan([(0, 1.0 + self.n / 1000.0)], t_ns=self.n * 1_000_000)


async def _scan_rig(lidar) -> Rig:
    stm = sim.SimulatedStm32()
    stm.start()
    srv = server.RobotServer(
        token=TOKEN, writer=FakeWriter(), stm=stm, devices=_devices_ok, lidar=lidar
    )
    return Rig(srv, srv.writer, stm, await srv.start("127.0.0.1", 0))


async def test_scan_frames_are_sent_only_for_new_scans_at_most_10_hz():
    lidar = _FakeLidar()
    made = await _scan_rig(lidar)
    try:
        async with made.connect() as ws:
            await asyncio.sleep(0.2)  # no scan yet: nothing but states
            lidar.publish()
            stop = False

            async def produce():
                while not stop:
                    lidar.publish()  # far faster than the allowed rate
                    await asyncio.sleep(0.004)

            producer = asyncio.ensure_future(produce())
            frames, started = [], time.monotonic()
            try:
                while time.monotonic() - started < 1.0:
                    message = await asyncio.wait_for(ws.recv(), 1.0)
                    if isinstance(message, bytes):
                        frames.append(_decode_scan(message))
            finally:
                stop = True
                await asyncio.gather(producer, return_exceptions=True)
            assert 5 <= len(frames) <= 11
            seqs = [f[2] for f in frames]
            assert seqs == list(range(1, len(frames) + 1))
            assert [f[3] for f in frames] == sorted({f[3] for f in frames})  # newest, no repeats
    finally:
        await made.srv.close()
        made.stm.stop()


async def test_no_scan_frames_without_a_new_scan():
    lidar = _FakeLidar()
    lidar.publish()
    made = await _scan_rig(lidar)
    try:
        async with made.connect() as ws:
            kinds = []
            started = time.monotonic()
            while time.monotonic() - started < 0.5:
                kinds.append(type(await asyncio.wait_for(ws.recv(), 1.0)))
            assert kinds.count(bytes) == 1  # the one existing scan, sent once
    finally:
        await made.srv.close()
        made.stm.stop()


async def test_slow_scan_peer_does_not_block_command_intake():
    lidar = _FakeLidar()
    made = await _scan_rig(lidar)
    try:
        async with made.connect() as slow, made.connect() as fast:
            # `slow` is replaced by `fast` (newest connection wins); commands still go through
            # while scans keep being produced and nobody reads.
            stop = False

            async def produce():
                while not stop:
                    lidar.publish()
                    await asyncio.sleep(0.01)

            producer = asyncio.ensure_future(produce())
            try:
                await asyncio.sleep(0.3)
                await fast.send(_cmd(seq=9))
                await wait_for(lambda: made.writer.calls)
            finally:
                stop = True
                await asyncio.gather(producer, return_exceptions=True)
    finally:
        await made.srv.close()
        made.stm.stop()
