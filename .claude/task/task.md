# TASK — Web điều khiển robot Mecanum (giai đoạn 1)

Trạng thái: **ĐÃ DUYỆT 2026-11-09**. Đối chiếu: [spec.md](../spec/spec.md) · [plan.md](../plan/plan.md)

Mỗi task theo quy trình ở plan.md §5. Mục **Work order** do Sonnet điền trước khi Haiku bắt đầu.
Trạng thái: `TODO → ORDERED → CODED → PASS → MERGED` hoặc `BLOCKED`. Chỉ merge sau khi Sonnet đối chứng đạt theo cả ba file.

## P0 — Tái cấu trúc

### T01 — Dựng cấu trúc thư mục
- Trạng thái: MERGED · Plan: P0 · Phụ thuộc: không
- Spec: NFR-01, NFR-05, NFR-07
- Việc: chuyển `src/hardware.py` sang `robot/robot_agent/`, `src/teleop.py` thành `drive.py`, `read.md` sang `docs/dynamics.md` (thêm ghi chú thông số cũ), `src/openni2_redist/` sang `robot/vendor/openni2/`. Viết lại `pyproject.toml` với extras và đường dẫn test thực tế. Viết lại `.env.example`, bỏ các dòng `configs/` trong `.gitignore`. Repo gốc do Opus khởi tạo theo git-flow; `app/client/.git` cũ được Opus chuyển ra `.git-backups/`.
- Đạt khi: `pytest --collect-only` chạy không lỗi; không còn tham chiếu tới `src/`, `configs/`.
- Work order:

  **QUY TẮC ĐẦU TIÊN: Chỉ chạm các file được liệt kê dưới đây. Nếu thiếu thông tin hoặc có mâu thuẫn, dừng lại và trả `BLOCKED` kèm câu hỏi. Không chạy `git commit` (không chạy git làm đổi repo ngoài `git mv` nếu muốn; có thể dùng `mv` thường). Không sửa nội dung code Python nào. Không tạo module của task sau.**

  Thư mục làm việc: `/home/vth/ws/mecanum_base` (nhánh `feature/T01-restructure`).

  **Bước 1. Tạo thư mục**
  `mkdir -p robot/robot_agent robot/vendor robot/tests app/server/app_server app/server/tests docs`

  **Bước 2. Di chuyển (giữ nguyên nội dung, `mv` hoặc `git mv`)**
  - `src/hardware.py` → `robot/robot_agent/hardware.py`
  - `src/teleop.py` → `robot/robot_agent/drive.py`
  - `src/openni2_redist` → `robot/vendor/openni2` (cả thư mục, gồm `x64/`, `arm64/`)
  - `read.md` → `docs/dynamics.md`

  **Bước 3. Xóa**
  - `rm -rf src/__pycache__`
  - `rmdir src` (phải trống; nếu còn file thì trả BLOCKED, liệt kê file còn lại)

  **Bước 4. Tạo file mới**
  - `robot/robot_agent/__init__.py`: file rỗng.
  - `app/server/app_server/__init__.py`: file rỗng.
  - `robot/tests/test_robot.py`, nội dung chính xác:
    ```python
    def test_package_imports():
        import robot_agent

        assert robot_agent is not None
    ```
  - `app/server/tests/test_server.py`, nội dung chính xác:
    ```python
    def test_package_imports():
        import app_server

        assert app_server is not None
    ```
  - Không tạo `__init__.py` trong thư mục `tests/`. Không tạo `deploy/`, `conftest.py` hay module nào khác.

  **Bước 5. Ghi chú đầu `docs/dynamics.md`**
  Chèn đúng khối sau vào ĐẦU file (trước dòng `# Chứng minh 4 động cơ ...`), rồi một dòng trống, giữ nguyên phần còn lại:
  ```
  > **Ghi chú (2026-11-09):** Các số hình học trong tài liệu này (L + d = 0,30 m) là giả định cũ, đã bị thay bởi spec PHY-1 (`L = 0,32 m`, `d = 0,35 m`, `lever = (L + d)/2 = 0,335 m`). Các kết quả tính trong tài liệu chưa được tính lại theo thông số mới.
  ```

  **Bước 6. Thay toàn bộ `pyproject.toml` bằng đúng nội dung này**
  ```toml
  [build-system]
  requires = ["setuptools>=75"]
  build-backend = "setuptools.build_meta"

  [project]
  name = "mecanum-base"
  version = "0.2.0.dev0"
  description = "Mecanum robot agent (Jetson) and app server for the web control system"
  requires-python = ">=3.10"
  dependencies = []

  [project.optional-dependencies]
  robot = [
      "pyserial>=3.5,<4",
      "websockets>=14,<17",
      "python-dotenv>=1,<2",
      "numpy>=2.0,<3",
  ]
  server = [
      "fastapi>=0.110,<1",
      "uvicorn[standard]>=0.30,<1",
      "websockets>=14,<17",
      "python-dotenv>=1,<2",
  ]
  camera = [
      "numpy>=2.0,<3",
      "primesense>=2.2.0.30.post5",
  ]
  test = [
      "pytest>=8,<10",
      "pytest-asyncio>=0.23,<2",
      "httpx>=0.27,<1",
  ]

  [tool.setuptools]
  packages = ["robot_agent", "app_server"]

  [tool.setuptools.package-dir]
  robot_agent = "robot/robot_agent"
  app_server = "app/server/app_server"

  [tool.pytest.ini_options]
  testpaths = ["robot/tests", "app/server/tests"]
  pythonpath = ["robot", "app/server"]
  asyncio_mode = "auto"
  addopts = "-q"

  [tool.ruff]
  line-length = 100
  target-version = "py310"
  ```

  **Bước 7. Thay toàn bộ `.env.example` bằng đúng nội dung này**
  ```
  # Copy to .env and adjust. One file serves both machines; each side reads only its own section.

  # ===== Jetson (robot agent) - 100.69.39.18 =====
  # Motion is OFF by default: with false the agent only writes zero velocity.
  ROBOT_MOTION_ENABLED=false
  # true runs a fake STM32 and LiDAR, no hardware needed.
  ROBOT_SIMULATE=false
  STM_PORT=/dev/rai_controller
  STM_BAUD=115200
  LIDAR_PORT=/dev/rai_lidar
  LIDAR_BAUD=460800
  # Leave blank to select the bundled OpenNI2 SDK by architecture, or use the system SDK.
  CAMERA_SDK_PATH=
  # WebSocket server of the robot; bind to the Tailscale IP only.
  ROBOT_BIND_HOST=100.69.39.18
  ROBOT_BIND_PORT=8765
  # Shared secret the app server presents to the robot. Set a long random value.
  ROBOT_LINK_TOKEN=

  # ===== App server - 100.119.83.63 =====
  # Where the app server connects to the robot.
  ROBOT_WS_URL=ws://100.69.39.18:8765/ws
  # ROBOT_LINK_TOKEN above is also read by the app server; use the same value on both machines.
  # Operator secret entered in the web UI to gain control; without it viewers are read-only.
  OPERATOR_TOKEN=
  APP_BIND_HOST=100.119.83.63
  APP_BIND_PORT=8000
  # Comma-separated allowed Origin values for the operator WebSocket.
  APP_ALLOWED_ORIGINS=http://100.119.83.63:3000
  ```
  (Không thêm biến nào khác; không có `ROBOT_SERVER_URL`, `ROBOT_CONTROL_CONFIG`, `ROBOT_DEVICE_CONFIG`; không có hệ số 1.89.)

  **Bước 8. `.gitignore`**
  Xóa đúng 3 dòng `/configs/local*.yaml`, `/configs/local*.yml`, `/configs/local*.json` (giữ dòng trống và mọi dòng khác). (Cần để không còn tham chiếu `configs/`; xem câu hỏi mở bên dưới.)

  **Bước 9. Tạo venv và cài đặt (từ gốc repo)**
  ```
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -e ".[robot,server,test]"
  ```
  Nếu `venv` hoặc `pip install` lỗi (thiếu python3-venv, không có mạng), trả BLOCKED kèm thông báo lỗi. `.venv/` đã nằm trong `.gitignore`; `*.egg-info/` cũng vậy.

  **Bước 10. Kiểm tra (chạy hết, báo kết quả từng lệnh)**
  1. `.venv/bin/pytest --collect-only` -> exit 0, báo `2 tests collected` (một ở `robot/tests/test_robot.py`, một ở `app/server/tests/test_server.py`), không có error.
  2. `.venv/bin/pytest` -> `2 passed`.
  3. `.venv/bin/python -c "import robot_agent.hardware, robot_agent.drive, app_server"` -> exit 0, không in lỗi. (Nếu lỗi import nội bộ do code cũ, KHÔNG sửa code, trả BLOCKED kèm traceback.)
  4. `grep -niE 'src/|configs/|robot_server_url' pyproject.toml .env.example CLAUDE.md .gitignore` -> không có dòng nào, exit 1.
  5. `grep -nE 'ROBOT_CONTROL_CONFIG|ROBOT_DEVICE_CONFIG|1\.89' .env.example` -> không có dòng nào, exit 1.
  6. `test ! -e src && echo OK` -> `OK`.
  7. `ls robot/robot_agent robot/vendor/openni2 docs` -> thấy `__init__.py drive.py hardware.py`, `arm64 x64`, `dynamics.md`; và `ls robot` thấy `robot_agent`, `tests`, `vendor`.
  8. `head -3 docs/dynamics.md` -> dòng đầu là ghi chú `> **Ghi chú (2026-11-09):**`.
  9. `ls read.md` -> không tồn tại.

  **Báo cáo cuối của Haiku:** liệt kê file đã chuyển/tạo/sửa/xóa và kết quả 9 lệnh kiểm tra. Không commit.

  **Mâu thuẫn/câu hỏi mở cho Opus (Sonnet nêu, Haiku không xử lý):**
  1. task.md T01 yêu cầu "không còn tham chiếu `configs/`" nhưng `.gitignore` có 3 dòng `/configs/local*`; Work order xóa chúng (Bước 8), file này không được nêu trong dòng "Việc" của T01.
  2. `.env.example` dùng một `ROBOT_LINK_TOKEN` cho cả hai máy (robot kiểm tra, app server gửi); spec SAF-07/PROTO-2 chỉ nêu tên biến này, không nêu biến riêng phía app server. Work order giữ nguyên một biến theo đúng danh sách biến trong spec.
  3. plan §3 có `deploy/robot-agent.service` nhưng T04 mới tạo, nên T01 không tạo `deploy/`. `pyproject.toml` dùng `package-dir` ánh xạ tường minh và `packages` chỉ liệt kê gói cấp cao: khi task sau thêm gói con (nếu có) phải thêm vào danh sách.
  4. `pytest.ini_options` thêm `pythonpath = ["robot", "app/server"]` để test chạy được kể cả khi chưa cài editable; `asyncio_mode = "auto"` thêm sẵn cho T04+ (spec/plan/task không cấm).

## P1 — Robot agent

### T02 — Sửa lớp thiết bị
- Trạng thái: MERGED · Plan: P1 · Phụ thuộc: T01
- Spec: FIX-1, FIX-2, FIX-7, FIX-8, FIX-9
- File: `robot/robot_agent/hardware.py`, `robot/robot_agent/drive.py` (chỉ phần tính độ tuổi của FIX-7), `robot/tests/test_robot.py`
- Đạt khi: test bao phủ đọc không chờ đủ 128 byte, frame phụ được lưu, mất gói quanh 0° vẫn tách scan, `0.1/1.89` mã hóa thành 53 mm/s, độ tuổi dùng monotonic.
- Work order:
  **Quy tắc đầu tiên:** chỉ sửa đúng 3 file sau: `robot/robot_agent/hardware.py`, `robot/robot_agent/drive.py`, `robot/tests/test_robot.py`. Nếu thiếu thông tin hoặc có điều gì mâu thuẫn (ví dụ đoạn "old" không khớp file thật), dừng lại và trả `BLOCKED` kèm câu hỏi. Không chạy lệnh git commit (và không chạy lệnh git nào làm thay đổi repo). Không đổi `pyproject.toml` (không có test async nên không cần `asyncio_default_fixture_loop_scope`). Không đụng `AstraFrame`/`AstraSSource` (camera ngoài phạm vi), `utc_ns()` giữ nguyên vì Astra còn dùng.

  **Quyết định thiết kế đã chốt (Haiku không đổi):**
  - `Stm32FrameDecoder.feed` trả tuple gồm cả `Stm32Telemetry` lẫn `Stm32AuxTelemetry` theo thứ tự đến; reader tách bằng `isinstance`.
  - Vòng đọc một lần của STM32 tách thành `Stm32SerialSource._read_once()` để test được bằng serial giả.
  - Phát hiện vòng LiDAR mới: hàm thuần `lidar_revolution_wrapped(previous_deg, current_deg)` (góc giảm hơn 180°) và phương thức `N10PSerialSource._accept_point(point, timestamp_ns)`.
  - Mọi `t_ns` của STM32/LiDAR lấy từ `monotonic_ns()`. `last_command[0]` cũng dùng `monotonic_ns()`.
  - Bố cục frame phụ chưa xác minh (A-4): `[1:3]` dòng sạc mA (big-endian, không dấu, chia 1000 ra A), `[3]` red, `[4]` charging, `[5]` set_state.

  **Bước 1 — `robot/robot_agent/hardware.py`, FIX-9.** Thay đúng một dòng.
  ```python
  # old
      quantized = tuple(int(float(value) * 1000.0) for value in values)
  # new
      quantized = tuple(int(round(float(value) * 1000.0)) for value in values)
  ```
  Dòng kiểm tra `if not all(-32768 <= value <= 32767 for value in quantized):` ngay dưới giữ nguyên (nó đã chạy sau khi làm tròn, nên vẫn đúng).

  **Bước 2 — `hardware.py`, FIX-2.** Ba thay đổi trong `Stm32FrameDecoder.feed`.
  ```python
  # old
      def feed(self, data: bytes, timestamp_ns: int) -> tuple[Stm32Telemetry, ...]:
  # new
      def feed(self, data: bytes, timestamp_ns: int) -> tuple[Stm32Telemetry | Stm32AuxTelemetry, ...]:
  ```
  ```python
  # old
          decoded: list[Stm32Telemetry] = []
  # new
          decoded: list[Stm32Telemetry | Stm32AuxTelemetry] = []
  ```
  ```python
  # old
                      del self._buffer[:STM32_AUX_SIZE]
                      continue
  # new
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
  ```

  **Bước 3 — `hardware.py`, FIX-7 cho `send_velocity`.**
  ```python
  # old
          self.last_command = (utc_ns(), float(vx_mps), float(vy_mps), float(wz_radps))
  # new
          self.last_command = (monotonic_ns(), float(vx_mps), float(vy_mps), float(wz_radps))
  ```

  **Bước 4 — `hardware.py`, FIX-1 + FIX-2 + FIX-7: thay toàn bộ `Stm32SerialSource._run`.**
  ```python
  # old (toàn bộ hàm)
      def _run(self) -> None:
          while not self._stop.is_set():
              try:
                  payload = self._serial.read(128)
                  if not payload:
                      continue
                  timestamp = utc_ns()
                  frames = self._decoder.feed(payload, timestamp)
                  if frames:
                      with self._lock:
                          self._latest = frames[-1]
              except Exception:
                  self.errors += 1
                  if self._stop.wait(0.05):
                      return
  # new
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
  ```

  **Bước 5 — `hardware.py`, FIX-8: thêm hàm thuần ngay trước dòng `class N10PSerialSource:`.**
  ```python
  def lidar_revolution_wrapped(previous_deg: float | None, current_deg: float) -> bool:
      """True when the angle fell by more than 180 degrees (new revolution, even after packet loss)."""
      return previous_deg is not None and previous_deg - current_deg > 180.0


  ```
  (giữ hai dòng trống trước `class N10PSerialSource:`.)

  **Bước 6 — `hardware.py`, FIX-8: trạng thái tách scan trong `N10PSerialSource`.**
  ```python
  # old (trong __init__)
          self._scan_times = deque(maxlen=24)
  # new
          self._scan_times = deque(maxlen=24)
          self._last_angle_deg: float | None = None
          self._points: list[LidarPoint] = []
  ```
  ```python
  # old (trong start)
          self._decoder = N10PDecoder(self.protocol_profile)
          self._latest = None
          self.error = None
  # new
          self._decoder = N10PDecoder(self.protocol_profile)
          self._latest = None
          self._last_angle_deg = None
          self._points = []
          self.error = None
  ```

  **Bước 7 — `hardware.py`, FIX-8 + FIX-7: thay toàn bộ `N10PSerialSource._run` bằng hai hàm.**
  ```python
  # old (toàn bộ hàm)
      def _run(self) -> None:
          last_angle: float | None = None
          points: list[LidarPoint] = []
          while not self._stop.is_set():
              waiting = int(getattr(self._serial, "in_waiting", 0) or 0)
              payload = self._serial.read(max(256, min(waiting, 4096)))
              if not payload:
                  continue
              timestamp = utc_ns()
              for decoded in self._decoder.feed_all(payload, timestamp):
                  for point in decoded:
                      angle = math.degrees(point.angle_rad)
                      wrapped = last_angle is not None and last_angle > 355.0 and angle < 5.0
                      if wrapped and points:
                          with self._lock:
                              self._latest = LidarScan(timestamp, tuple(points))
                              self._scan_times.append(time.monotonic())
                          points = []
                      points.append(point)
                      last_angle = angle
  # new
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
  ```

  **Bước 8 — `robot/robot_agent/drive.py`, FIX-7 (chỉ phần `tick`; T03 sẽ viết lại phần còn lại).** Đổi tham số `wall_ns` thành `now_ns` và dùng đồng hồ monotonic.
  ```python
  # old
      def tick(self, *, now: float | None = None, wall_ns: int | None = None) -> tuple[float, float, float]:
          now = time.monotonic() if now is None else now
          wall_ns = time.time_ns() if wall_ns is None else wall_ns
  # new
      def tick(self, *, now: float | None = None, now_ns: int | None = None) -> tuple[float, float, float]:
          now = time.monotonic() if now is None else now
          now_ns = time.monotonic_ns() if now_ns is None else now_ns
  ```
  ```python
  # old
              age_s = (wall_ns - sample.t_ns) / 1e9 if sample is not None else math.inf
  # new
              age_s = (now_ns - sample.t_ns) / 1e9 if sample is not None else math.inf
  ```
  Không sửa gì khác trong `drive.py` (kể cả giới hạn tốc độ 0.2 m/s, thuộc T03).

  **Bước 9 — `robot/tests/test_robot.py`: thay toàn bộ nội dung bằng đoạn sau (giữ test smoke có sẵn).**
  ```python
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
  ```

  **Bước 10 — kiểm tra (chạy từ `/home/vth/ws/mecanum_base`).**
  1. `.venv/bin/pytest -v` → mong đợi tất cả test pass, 0 failed, 0 error (gồm cả `test_package_imports`; test của `app/server/tests` nếu có cũng pass). `ruff` chưa cài, không yêu cầu chạy.
  2. `grep -n "utc_ns\|time_ns" robot/robot_agent/hardware.py robot/robot_agent/drive.py` → mong đợi chỉ còn: dòng `def utc_ns()` và `return time.time_ns()` trong `hardware.py`, và đúng một chỗ dùng `utc_ns()` là `capture_t_ns = max(utc_ns(), ...)` trong `AstraSSource.read`. Không còn `utc_ns()` ở `Stm32SerialSource`, `N10PSerialSource`, không còn `time_ns` trong `drive.py`.
  3. `grep -n "read(128)\|wall_ns" robot/robot_agent/*.py` → không có kết quả.
  4. Nếu một test fail do đoạn code trong Work order (không phải do môi trường), dừng và trả `BLOCKED` kèm tên test và thông báo lỗi, không tự sửa thiết kế.

  **Trả về:** danh sách file đã sửa, kết quả ba lệnh ở Bước 10 (dán nguyên output), và mọi điểm bạn phải dừng.

  **Mâu thuẫn/điểm mở cho Opus (Sonnet nêu, Haiku không xử lý):**
  1. spec FIX-7 nhắc `teleop.py:65-69`, nhưng file hiện là `drive.py` (T01 đã đổi tên; T03 viết lại); Work order chỉ sửa `tick` trong `drive.py`, khớp dòng "File" của T02. Các số dòng trong cột FIX của spec cũng đã lệch (chỉ để tham khảo).
  2. Đổi tên tham số `tick(wall_ns=...)` thành `tick(now_ns=...)` là thay đổi API; hiện không có nơi gọi nào khác trong repo (đã grep). T03 sẽ viết lại `drive.py`.
  3. `drive.py` còn kẹp tốc độ 0.2 m/s và 1 rad/s, trái SAF-04; không thuộc T02, để T03 xử lý. Test của T02 dùng tốc độ mặc định 0.05 m/s để không phụ thuộc điều này.
  4. A-4 chưa xác nhận: đơn vị mA được đổi sang A (chia 1000) vì trường tên `charging_current_a`; kiểm chứng ở T15.
  5. FIX-7 nói cả "dt", nhưng hiện không có phép tính dt nào dùng đồng hồ hệ thống ngoài tuổi telemetry; `scan_rate_hz` đã dùng `time.monotonic()`.

### T03 — Writer cmd_vel
- Trạng thái: MERGED · Plan: P1 · Phụ thuộc: T02
- Spec: FIX-3, FIX-4, FIX-5, FIX-6, SAF-02, SAF-03, SAF-04, SAF-05, SAF-06
- File: `robot/robot_agent/drive.py`, `robot/tests/test_robot.py`
- Đạt khi: test bao phủ `set_cmd_vel` không chặn khi serial chậm, deadman 250 ms, không kẹp tốc độ, giá trị ngoài int16 bị loại và ghi 0, telemetry cũ và cờ dừng ép 0, tự phục hồi sau lỗi ghi mà không chạy lại lệnh cũ, `MOTION_ENABLED=false` chỉ ghi 0.
- Work order:
  **QUY TẮC ĐẦU TIÊN: Chỉ chạm hai file `robot/robot_agent/drive.py` và `robot/tests/test_robot.py`. Nếu thiếu thông tin hoặc có mâu thuẫn (ví dụ đoạn "old" không khớp file thật), dừng lại và trả `BLOCKED` kèm câu hỏi. Không chạy `git commit` (và không chạy lệnh git nào làm thay đổi repo). Không sửa `hardware.py`, `pyproject.toml` hay file nào khác. Không tạo `server.py`, `config.py`, `__main__.py` (thuộc T04).**

  Thư mục làm việc: `/home/vth/ws/mecanum_base` (nhánh `feature/T03-cmd-vel-writer`). Dùng `.venv/bin/...`.

  **Quyết định thiết kế đã chốt (Haiku không đổi):**
  - Bàn phím nay nằm ở web client, nên `KeyboardDrive`, `DIRECTIONS`, `press`, giới hạn 0.2 m/s và 1 rad/s bị xóa hoàn toàn. `drive.py` chỉ còn `ZERO`, `WriterHealth`, `CmdVelWriter`.
  - `set_cmd_vel` chỉ ghi vào một ô lệnh dưới `threading.Lock` ngắn, không bao giờ chạm serial. `send_velocity` luôn gọi ngoài lock (FIX-4).
  - Kiểm tra giá trị (SAF-04) tái dùng `hardware.encode_stm32_velocity_command`: giá trị không hữu hạn hoặc `round(v*1000)` ngoài int16 làm encoder ném `ValueError` (cũng bắt `TypeError`, `OverflowError`). Không có kẹp giá trị. Giá trị bị loại: ô lệnh bị xóa, `rejected_count` tăng, tick ghi 0, `set_cmd_vel` trả `False`.
  - Lệnh hết hạn khi tuổi `now_ns - cmd_ns` nằm ngoài `[0, deadman_s]`; telemetry cũ khi tuổi nằm ngoài `[0, telemetry_timeout_s]` (đúng 250 ms hoặc 500 ms vẫn còn hạn; chỉ "cũ hơn" mới bị loại). Tuổi âm cũng bị loại (để bắt timestamp đồng hồ hệ thống). Lệnh bị loại thì bị xóa hẳn khỏi ô lệnh, không chạy lại.
  - `motion_enabled=False` (mặc định, kể cả constructor mặc định) thì chỉ ghi 0 và lệnh bị xóa.
  - Lỗi ghi: ghi nhận lỗi, xóa lệnh (trừ khi có lệnh mới đến trong lúc ghi, dựa vào bộ đếm `_seq`), `tick` trả `None`, vòng lặp chờ `retry_s` rồi thử lại; sau khi phục hồi ghi 0 cho đến khi có `set_cmd_vel` mới (SAF-06).
  - `start()` không ghi gì đồng bộ; tick đầu tiên của thread sẽ ghi 0. `stop()` trả `True` chỉ khi thread đã dừng và lần ghi 0 cuối thành công; lỗi chỉ được ghi nhận, không ném.
  - Chỉ dùng `time.monotonic_ns()`; không dùng `time.time`. Tương thích Python 3.10.

  **Bước 1. Thay TOÀN BỘ nội dung `robot/robot_agent/drive.py` bằng đúng đoạn sau.**

  ```python
  """cmd_vel writer: a one-slot mailbox plus a loop that feeds the STM32 safe velocities.

  Velocities are (vx, vy, wz) in STM32 wire units (m/s, m/s, rad/s). There is no speed limit
  here by design (SAF-04); only non-finite values and values that do not fit the STM32 int16
  frame are rejected. All ages use the monotonic clock (time.monotonic_ns).
  """
  from __future__ import annotations

  import math
  import threading
  import time
  from dataclasses import dataclass
  from typing import Any

  from .hardware import encode_stm32_velocity_command

  ZERO = (0.0, 0.0, 0.0)
  _NS = 1_000_000_000


  @dataclass(frozen=True)
  class WriterHealth:
      running: bool  # writer thread is alive
      healthy: bool  # the most recent write attempt succeeded
      error_count: int  # write/telemetry-read errors since construction
      last_error: str | None  # "ExceptionType: message" of the latest error
      rejected_count: int  # set_cmd_vel calls rejected (non-finite or outside int16)
      last_write_ns: int | None  # monotonic time of the latest successful write


  class CmdVelWriter:
      def __init__(
          self,
          source: Any,
          *,
          motion_enabled: bool = False,
          deadman_s: float = 0.25,
          telemetry_timeout_s: float = 0.5,
          period_s: float = 0.05,
          retry_s: float = 0.2,
          join_timeout_s: float = 2.0,
      ) -> None:
          for name, value in (
              ("deadman_s", deadman_s),
              ("telemetry_timeout_s", telemetry_timeout_s),
              ("period_s", period_s),
              ("retry_s", retry_s),
              ("join_timeout_s", join_timeout_s),
          ):
              if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                  raise ValueError(f"{name} must be positive and finite")
          self.source = source
          self.motion_enabled = bool(motion_enabled)
          self.period_s = float(period_s)
          self.retry_s = float(retry_s)
          self.join_timeout_s = float(join_timeout_s)
          self._deadman_ns = int(round(deadman_s * _NS))
          self._telemetry_ns = int(round(telemetry_timeout_s * _NS))
          # Mailbox and health state. _lock is held only for short in-memory updates and is
          # never held while writing to the source.
          self._lock = threading.Lock()
          self._cmd: tuple[float, float, float] | None = None
          self._cmd_ns = 0
          self._seq = 0
          self._healthy = False
          self._error_count = 0
          self._last_error: str | None = None
          self._rejected = 0
          self._last_write_ns: int | None = None
          self._stop = threading.Event()
          self._thread: threading.Thread | None = None

      # ---- mailbox (never touches the serial port) ----

      @staticmethod
      def _fits_frame(values: tuple[Any, Any, Any]) -> bool:
          # Reuse the encoder so the accepted range is exactly what the STM32 frame can carry
          # (finite, and round(v * 1000) within int16).
          try:
              encode_stm32_velocity_command(*values)
          except (ValueError, TypeError, OverflowError):
              return False
          return True

      def set_cmd_vel(self, vx: float, vy: float, wz: float, now_ns: int | None = None) -> bool:
          """Store the latest command. Returns False when rejected (the mailbox is then emptied)."""
          accepted = self._fits_frame((vx, vy, wz))
          with self._lock:
              stamp = time.monotonic_ns() if now_ns is None else now_ns
              self._seq += 1
              if accepted:
                  self._cmd = (float(vx), float(vy), float(wz))
                  self._cmd_ns = stamp
              else:
                  self._cmd = None
                  self._rejected += 1
          return accepted

      def clear(self) -> None:
          """Discard the stored command (link loss). The next write is zero."""
          with self._lock:
              self._seq += 1
              self._cmd = None

      def health(self) -> WriterHealth:
          thread = self._thread
          with self._lock:
              return WriterHealth(
                  running=thread is not None and thread.is_alive(),
                  healthy=self._healthy,
                  error_count=self._error_count,
                  last_error=self._last_error,
                  rejected_count=self._rejected,
                  last_write_ns=self._last_write_ns,
              )

      def _record_error(self, error: BaseException) -> None:
          with self._lock:
              self._healthy = False
              self._error_count += 1
              self._last_error = f"{type(error).__name__}: {error}"

      # ---- writing ----

      def _usable(self, cmd_ns: int, sample: Any, now_ns: int) -> bool:
          if not self.motion_enabled or sample is None or sample.flag_stop:
              return False
          if not 0 <= now_ns - sample.t_ns <= self._telemetry_ns:
              return False
          return 0 <= now_ns - cmd_ns <= self._deadman_ns

      def tick(self, now_ns: int | None = None) -> tuple[float, float, float] | None:
          """Write one velocity. Returns what was written, or None when the write failed."""
          try:
              sample = self.source.latest
          except Exception as error:
              self._record_error(error)
              sample = None
          with self._lock:
              now = time.monotonic_ns() if now_ns is None else now_ns
              seq = self._seq
              command = ZERO
              if self._cmd is not None:
                  if self._usable(self._cmd_ns, sample, now):
                      command = self._cmd
                  else:
                      # Expired, stale telemetry, stop flag or motion off: discard it for good.
                      self._cmd = None
          try:
              self.source.send_velocity(*command)  # outside the lock
          except Exception as error:
              with self._lock:
                  if self._seq == seq:  # keep a command that arrived during the failed write
                      self._cmd = None
              self._record_error(error)
              return None
          with self._lock:
              self._healthy = True
              self._last_write_ns = now
          return command

      def _run(self) -> None:
          while not self._stop.is_set():
              try:
                  ok = self.tick() is not None
              except Exception as error:
                  self._record_error(error)
                  ok = False
              self._stop.wait(self.period_s if ok else self.retry_s)

      def start(self) -> None:
          if self._thread is not None:
              raise RuntimeError("cmd_vel writer is already started")
          self.clear()
          self._stop.clear()
          thread = threading.Thread(target=self._run, name="cmd-vel-writer", daemon=True)
          self._thread = thread
          thread.start()

      def stop(self) -> bool:
          """Stop the loop and try a final zero. Returns True only if both succeeded."""
          self._stop.set()
          self.clear()
          thread = self._thread
          if thread is not None:
              thread.join(timeout=self.join_timeout_s)
              if thread.is_alive():
                  self._record_error(RuntimeError("cmd_vel writer thread did not stop in time"))
                  return False
              self._thread = None
          try:
              self.source.send_velocity(*ZERO)
          except Exception as error:
              self._record_error(error)
              return False
          return True
  ```

  **Bước 2. `robot/tests/test_robot.py`: hai chỉnh sửa.**

  (a) Phần import ở đầu file:
  ```python
  # old
  import struct
  import time
  # new
  import struct
  import threading
  import time
  ```

  (b) Xóa từ dòng `class FakeDriveSource:` đến hết file (gồm `FakeDriveSource`, `_armed_drive`, `test_tick_freshness_compares_monotonic_values`, `test_tick_default_clock_is_monotonic`), rồi thêm đúng đoạn sau vào cuối file (sau hai dòng trống). Mọi test T02 phía trên giữ nguyên. Hai test cũ được thay bằng `test_stale_telemetry_forces_zero_and_discards_command` (độ tuổi so monotonic, cũ 0.6 s thì ép 0 và xóa lệnh) và `test_default_clock_is_monotonic` (đồng hồ mặc định là monotonic, timestamp epoch bị loại).

  ```python
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
  ```

  **Bước 3. Kiểm tra (chạy từ `/home/vth/ws/mecanum_base`, báo output từng lệnh).**
  1. `.venv/bin/pytest -v` -> mong đợi `45 passed`, 0 failed, 0 error (15 test T02 + 29 test mới ở `robot/tests/test_robot.py` + 1 ở `app/server/tests/test_server.py`). Nếu tổng khác 45 nhưng không có fail, báo số thực tế và không sửa; nếu có fail, trả `BLOCKED` kèm tên test và lỗi, không tự sửa thiết kế.
  2. `.venv/bin/python -c "import robot_agent.drive as d; print(sorted(n for n in dir(d) if n[0].isupper()))"` -> in có `CmdVelWriter`, `WriterHealth`, `ZERO`, và không có `KeyboardDrive`.
  3. `grep -nE "KeyboardDrive|DIRECTIONS|time_ns|time\.time\(|min\(|max\(" robot/robot_agent/drive.py` -> không có dòng nào (exit 1).
  4. `grep -rn "KeyboardDrive" robot app` -> không có kết quả (exit 1).
  5. `grep -c "time.sleep" robot/tests/test_robot.py` -> `0`.
  6. `.venv/bin/pytest robot/tests/test_robot.py -k "writer or deadman or telemetry or loop or stop or blocking or block or error or invalid or clear or health or clock or boundary or limit or flag or constructor or command" -v` -> các test mới đều pass; toàn bộ chạy dưới 5 giây.

  **Trả về:** danh sách file đã sửa, output nguyên văn của 6 lệnh, mọi điểm bạn phải dừng. Không commit.

  **Mâu thuẫn/điểm mở cho Opus (Sonnet nêu, Haiku không xử lý):**
  1. task.md T03 "Đạt khi" ghi `MOTION_ENABLED=false`, spec SAF-02 ghi `ROBOT_MOTION_ENABLED`. Không mâu thuẫn thực chất: T03 chỉ có tham số constructor `motion_enabled` (mặc định `False`); việc đọc biến môi trường `ROBOT_MOTION_ENABLED` thuộc T04 (`config.py`).
  2. SAF-03(c) ("robot mất link thì tự ghi 0") liệt kê T03 nhưng việc nối "mất link" vào writer là của T04: T03 cung cấp `clear()` và deadman 250 ms; T04 phải gọi `clear()` khi WS đóng (test "mất link thì writer về 0" của T04).
  3. Spec không nói đúng 250 ms/500 ms thuộc phía nào; Work order chọn "đúng ngưỡng vẫn còn hạn, cũ hơn ngưỡng thì loại" (khác code cũ loại ở `>=`). Test tránh đúng biên (249 ms/251 ms).
  4. Hợp đồng ngoài spec, do Work order chốt cho T04/T06 dùng: `set_cmd_vel` trả `bool`; `tick` trả lệnh đã ghi hoặc `None`; `stop()` trả `bool`; `health()` trả `WriterHealth(running, healthy, error_count, last_error, rejected_count, last_write_ns)` với `healthy` là "lần ghi gần nhất thành công" (ban đầu `False`). Tham số thêm `retry_s=0.2` và `join_timeout_s=2.0` ngoài danh sách của yêu cầu.
  5. Constructor cũ giới hạn timeout (key ≤ 0.5 s, telemetry ≤ 1 s) cùng tốc độ; bản mới chỉ yêu cầu timing dương và hữu hạn (không phải giới hạn tốc độ nên không vi phạm SAF-04, nhưng là thay đổi hành vi).
  6. `AstraSSource` và `hardware.py` không đổi; `drive.py` import `encode_stm32_velocity_command` từ `.hardware` (import tương đối trong gói `robot_agent`).


### T04 — WS server, cấu hình, mô phỏng
- Trạng thái: TODO · Plan: P1 · Phụ thuộc: T03
- Spec: FR-03, SAF-03, SAF-07, PROTO-2, NFR-03, NFR-06
- File: `robot/robot_agent/{__main__,config,server,sim}.py`, `deploy/robot-agent.service`, `robot/tests/test_robot.py`
- Đạt khi: chạy `ROBOT_SIMULATE=true python -m robot_agent`; sai token bị từ chối; message không phải `cmd_vel` bị bỏ; mất link thì writer về 0; thiết bị lỗi được thử lại độc lập.
- Work order: _(Sonnet điền)_

## P2 — App server

### T05 — Lõi điều khiển
- Trạng thái: TODO · Plan: P2 · Phụ thuộc: T01
- Spec: FR-03, SAF-01, SAF-02, SAF-04, SAF-07, PROTO-1
- File: `app/server/app_server/{config,control}.py`, `app/server/tests/test_server.py`
- Đạt khi: test bao phủ disarm mặc định, chia hệ số cả ba thành phần ở một hàm, không kẹp tốc độ, loại giá trị không hữu hạn, chỉ một operator, sai token chỉ được xem, Origin không hợp lệ bị từ chối.
- Work order: _(Sonnet điền)_

### T06 — Link robot, telemetry, WS operator
- Trạng thái: TODO · Plan: P2 · Phụ thuộc: T04, T05
- Spec: FR-08, FR-12, SAF-01, SAF-03, PROTO-1, PROTO-2, PHY-7, NFR-03
- File: `app/server/app_server/{main,robot_link,telemetry}.py`, `app/server/tests/test_server.py`
- Đạt khi: nối được robot mô phỏng, tự kết nối lại; quá 250 ms không có lệnh hoặc operator rớt thì gửi 0; state tới web ≤ 20 Hz và theo đơn vị web; odometry khớp test vector; không payload nào lộ hệ số.
- Work order: _(Sonnet điền)_

## P3 — Nền client

### T07 — Thư viện vật lý
- Trạng thái: CODED · Plan: P3 · Phụ thuộc: T01
- Spec: PHY-1, PHY-2, PHY-3, PHY-4, PHY-5, PHY-6, NFR-04
- File: `app/client/src/robot/{mecanum,motion,mecanum.test}.ts`, `app/client/package.json` và `package-lock.json` (thêm vitest)
- Đạt khi: các test vector trong PHY-2, PHY-3, PHY-5 qua; thuận rồi ngược trả lại đầu vào; bộ bám đạt tiêu chí xong trên mô hình giả lập.
- Work order:

  **QUY TẮC ĐẦU TIÊN: Chỉ chạm các file được liệt kê dưới đây. Nếu thiếu thông tin hoặc có mâu thuẫn, dừng lại và trả `BLOCKED` kèm câu hỏi. Không chạy `git commit` (không chạy git làm đổi repo). Không tự thiết kế: chép đúng nội dung file bên dưới.**

  Thư mục làm việc: worktree `/tmp/claude-1000/-home-vth-ws-mecanum-base/76fe0d3b-44a2-4858-8e13-7f99f2566330/scratchpad/wt/T07` (nhánh `feature/T07-physics-lib`). Mọi lệnh npm chạy trong `app/client` của worktree này, không phải `/home/vth/ws/mecanum_base`. `app/client/node_modules` là symlink tới bản cài dùng chung; `npm install` sẽ ghi vào đó, đó là chủ ý.

  File được chạm (và chỉ các file này):
  - `app/client/package.json` và `app/client/package-lock.json` (do `npm install`, thêm vitest và script `test`)
  - tạo mới `app/client/src/robot/mecanum.ts`
  - tạo mới `app/client/src/robot/motion.ts`
  - tạo mới `app/client/src/robot/mecanum.test.ts`

  Không sửa `next.config.ts`, `tsconfig.json`, `eslint.config.mjs`. Không tạo `vitest.config.*`. Thư mục `app/client/src/robot/` chưa có, tạo bằng `mkdir -p`.

  **Ràng buộc SAF-01 (tuyệt đối).** Hệ số chia của `cmd_vel` và mọi tên gọi cho nó không được xuất hiện ở bất kỳ file client nào, kể cả chú thích và test. Các file dưới đây đã sạch; không thêm chú thích nhắc tới hệ số đó. Bước 6 có lệnh kiểm tra. Không thêm giới hạn tốc độ nào (SAF-04): `FR-04` cảnh báo tổng tốc độ chỉ là hàm trả `boolean`, không được dùng để kẹp hay chặn.

  **Bước 1. Cài vitest.** Chạy trong `app/client`:
  `npm install -D vitest@^4`
  Phải dùng `vitest@^4`. Bản mới nhất (5.x) đòi `@types/node` >= 22 và `npm install` báo lỗi ERESOLVE vì dự án dùng `@types/node@^20`. Nếu vẫn ERESOLVE với `vitest@^4`, trả `BLOCKED` kèm toàn bộ thông báo lỗi; không dùng `--force` hay `--legacy-peer-deps`. Mong đợi: kết thúc không lỗi, `package.json` có `"vitest": "^4.x.y"` trong `devDependencies`, `package-lock.json` đổi theo.

  **Bước 2. Thêm script test.** Trong `app/client/package.json`, mục `"scripts"`, thêm sau dòng `"lint": "eslint"` (nhớ thêm dấu phẩy sau `"eslint"`):
  ```json
      "lint": "eslint",
      "test": "vitest run"
  ```
  Không đổi gì khác trong `package.json` ngoài dòng vitest do npm thêm.

  **Bước 3. Tạo `app/client/src/robot/mecanum.ts`** với đúng nội dung sau:
  ```ts
    // Công thức vật lý PHY-1..PHY-5 (spec.md §6). Thuần TypeScript, không dùng React hay DOM.
    // Mọi vận tốc ở đây là đơn vị web (m/s, rad/s).

    // PHY-1: thông số, khai báo một chỗ duy nhất.
    export const L = 0.32; // m, tâm cầu trước đến tâm cầu sau
    export const D = 0.35; // m, tâm bánh trái đến tâm bánh phải
    export const R = 0.05; // m, bán kính bánh
    export const LEVER = (L + D) / 2; // 0.335 m (A-2)
    export const MASS = 9.7; // kg
    export const GRAVITY = 9.81; // m/s^2
    export const MU_R = 0.05; // hệ số cản lăn
    export const I_Z = MASS * ((L / 2) ** 2 + (D / 2) ** 2); // ~0.5454 kg.m^2
    export const TAU_RATED = 0.981; // N.m, mô-men định mức mỗi bánh
    export const F_C = (MU_R * MASS * GRAVITY) / 4; // lực cản lăn mỗi bánh
    export const FILTER_TAU = 0.1; // s, hằng số thời gian bộ lọc PHY-5
    export const SPEED_SUM_LIMIT = 1.6; // ngưỡng cảnh báo FR-04

    /** Bốn bánh theo thứ tự A, B, C, D. */
    export type Wheels = readonly [number, number, number, number];
    export type Flags4 = readonly [boolean, boolean, boolean, boolean];

    /** Dấu ε của bánh A, B, C, D. */
    export const EPS: Wheels = [1, -1, 1, -1];
    /** Dấu s của bánh A, B, C, D. */
    export const SGN: Wheels = [-1, -1, 1, 1];

    export interface BodyVel {
      vx: number;
      vy: number;
      wz: number;
    }

    export interface Pose {
      x: number;
      y: number;
      theta: number;
    }

    function wheelsOf(f: (i: number) => number): Wheels {
      return [f(0), f(1), f(2), f(3)];
    }

    function signOf(x: number): number {
      return x > 0 ? 1 : x < 0 ? -1 : 0;
    }

    /** PHY-2: động học ngược, vận tốc thân -> tốc độ 4 bánh (rad/s). */
    export function inverseKinematics(v: BodyVel): Wheels {
      return wheelsOf((i) => (v.vx + EPS[i] * v.vy + SGN[i] * LEVER * v.wz) / R);
    }

    /** PHY-3: động học thuận, tốc độ 4 bánh (rad/s) -> vận tốc thân. */
    export function forwardKinematics(w: Wheels): BodyVel {
      let sum = 0;
      let sumEps = 0;
      let sumSgn = 0;
      for (let i = 0; i < 4; i++) {
        sum += w[i];
        sumEps += EPS[i] * w[i];
        sumSgn += SGN[i] * w[i];
      }
      return {
        vx: (R / 4) * sum,
        vy: (R / 4) * sumEps,
        wz: (R / (4 * LEVER)) * sumSgn,
      };
    }

    /** PHY-3: thành phần dư e (m/s). Khác 0 nghĩa là bánh đánh nhau. */
    export function wheelResidual(w: Wheels): number {
      return (R / 4) * (w[0] - w[1] - w[2] + w[3]);
    }

    /** PHY-4: vận tốc thân sang đạo hàm tư thế trong khung thế giới. */
    export function bodyToWorld(
      v: BodyVel,
      theta: number,
    ): { xDot: number; yDot: number; thetaDot: number } {
      const c = Math.cos(theta);
      const s = Math.sin(theta);
      return {
        xDot: v.vx * c - v.vy * s,
        yDot: v.vx * s + v.vy * c,
        thetaDot: v.wz,
      };
    }

    /** FR-04: tổng |vx| + |vy| + lever*|wz| (m/s). */
    export function speedSum(v: BodyVel): number {
      return Math.abs(v.vx) + Math.abs(v.vy) + LEVER * Math.abs(v.wz);
    }

    /** FR-04: true khi vượt 1.6 m/s. Chỉ để cảnh báo, không được dùng để chặn lệnh. */
    export function exceedsSpeedSum(v: BodyVel): boolean {
      return speedSum(v) > SPEED_SUM_LIMIT;
    }

    export interface DynamicsResult {
      ax: number;
      ay: number;
      wzDot: number;
      Fx: number;
      Fy: number;
      Mz: number;
      /** Lực dọc từng bánh F_d,i (N). */
      Fd: Wheels;
      /** Mô-men từng bánh tau_i (N.m). */
      tau: Wheels;
      /** |tau_i| / TAU_RATED * 100. */
      tauPct: Wheels;
      /** true khi |tau_i| > TAU_RATED. */
      over: Flags4;
    }

    /**
     * PHY-5 phần lực: từ gia tốc thân (ax, ay đã trừ thành phần ly tâm) và wzDot
     * tính lực, mô-men. `wheels` chỉ dùng để lấy dấu sign(omega_i) của lực cản lăn.
     */
    export function computeDynamics(
      acc: { ax: number; ay: number; wzDot: number },
      wheels: Wheels,
    ): DynamicsResult {
      const Fx = MASS * acc.ax;
      const Fy = MASS * acc.ay;
      const Mz = I_Z * acc.wzDot;
      const Fd = wheelsOf((i) => (Fx + EPS[i] * Fy + (SGN[i] * Mz) / LEVER) / 4);
      const tau = wheelsOf((i) => R * (Fd[i] + F_C * signOf(wheels[i])));
      const tauPct = wheelsOf((i) => (100 * Math.abs(tau[i])) / TAU_RATED);
      const over: Flags4 = [
        Math.abs(tau[0]) > TAU_RATED,
        Math.abs(tau[1]) > TAU_RATED,
        Math.abs(tau[2]) > TAU_RATED,
        Math.abs(tau[3]) > TAU_RATED,
      ];
      return {
        ax: acc.ax,
        ay: acc.ay,
        wzDot: acc.wzDot,
        Fx,
        Fy,
        Mz,
        Fd,
        tau,
        tauPct,
        over,
      };
    }

    /**
     * PHY-5: ước lượng động lực học từ vận tốc đo. Đạo hàm vận tốc được lọc thông
     * thấp bậc 1 (hằng số thời gian `tau`, mặc định 0.1 s). Gọi `update` mỗi lần có
     * mẫu vận tốc mới, kèm dt (s) kể từ mẫu trước.
     */
    export class DynamicsEstimator {
      private readonly tauFilter: number;
      private prev: BodyVel | null = null;
      private vxDot = 0;
      private vyDot = 0;
      private wzDotF = 0;

      constructor(tauFilter: number = FILTER_TAU) {
        this.tauFilter = tauFilter;
      }

      reset(): void {
        this.prev = null;
        this.vxDot = 0;
        this.vyDot = 0;
        this.wzDotF = 0;
      }

      /** `v` là vận tốc đo (đơn vị web), `wheels` là tốc độ bánh (rad/s) tương ứng. */
      update(v: BodyVel, wheels: Wheels, dt: number): DynamicsResult {
        if (Number.isFinite(dt) && dt > 0) {
          if (this.prev !== null) {
            const alpha = dt / (this.tauFilter + dt);
            this.vxDot += alpha * ((v.vx - this.prev.vx) / dt - this.vxDot);
            this.vyDot += alpha * ((v.vy - this.prev.vy) / dt - this.vyDot);
            this.wzDotF += alpha * ((v.wz - this.prev.wz) / dt - this.wzDotF);
          }
          this.prev = { vx: v.vx, vy: v.vy, wz: v.wz };
        }
        return computeDynamics(
          {
            ax: this.vxDot - v.wz * v.vy,
            ay: this.vyDot + v.wz * v.vx,
            wzDot: this.wzDotF,
          },
          wheels,
        );
      }
    }
  ```

  **Bước 4. Tạo `app/client/src/robot/motion.ts`** với đúng nội dung sau:
  ```ts
    // PHY-6: bộ bám đích và chạy theo tốc độ bánh. Thuần TypeScript, không dùng React hay DOM.
    // Mọi hàm là bước tính thuần: nhận trạng thái + đầu vào, trả trạng thái mới + cmd_vel.
    // Đầu ra chuyển động duy nhất là cmd_vel (vx, vy, wz) theo đơn vị web.

    import { forwardKinematics } from "./mecanum";
    import type { BodyVel, Pose, Wheels } from "./mecanum";

    export const CONTROL_HZ = 20;
    export const KP_LIN = 1.0;
    export const KP_ANG = 1.5;
    export const TOL_POS = 0.02; // m
    export const TOL_ANG = 0.035; // rad
    export const DONE_CYCLES = 3;
    export const STALE_S = 0.5; // s

    export interface RunParams {
      /** Tốc độ tịnh tiến chạy (m/s). Không chặn trên. */
      vCruise: number;
      /** Tốc độ quay chạy (rad/s). Không chặn trên. */
      wzCruise: number;
      /** Gia tốc tịnh tiến tối đa (m/s^2). Không chặn trên. */
      accelLin: number;
      /** Gia tốc góc tối đa (rad/s^2). Không chặn trên. */
      accelAng: number;
    }

    export const DEFAULT_RUN_PARAMS: RunParams = {
      vCruise: 0.2,
      wzCruise: 1.0,
      accelLin: 0.5,
      accelAng: 1.5,
    };

    export type AbortReason = "stale" | "disarmed" | "key" | "timeout";

    export type RunStatus =
      | { kind: "running" }
      | { kind: "done" }
      | { kind: "aborted"; reason: AbortReason };

    /** Điều kiện hủy dùng chung cho bộ bám đích và chạy theo tốc độ bánh. */
    export interface RunContext {
      /** Tuổi của state mới nhất (s). */
      stateAgeS: number;
      armed: boolean;
      /** Có phím di chuyển đang được giữ. */
      keyPressed: boolean;
    }

    function zeroCmd(): BodyVel {
      return { vx: 0, vy: 0, wz: 0 };
    }

    /** Quấn góc về [-pi, pi]. */
    export function wrapAngle(a: number): number {
      return Math.atan2(Math.sin(a), Math.cos(a));
    }

    /** Trả thông báo lỗi nếu tham số chạy không hợp lệ, ngược lại null. Không đặt chặn trên. */
    export function validateRunParams(p: RunParams): string | null {
      const entries: [string, number][] = [
        ["vCruise", p.vCruise],
        ["wzCruise", p.wzCruise],
        ["accelLin", p.accelLin],
        ["accelAng", p.accelAng],
      ];
      for (const [name, value] of entries) {
        if (!Number.isFinite(value) || value <= 0) {
          return `${name} phải là số hữu hạn lớn hơn 0`;
        }
      }
      return null;
    }

    /** Lý do hủy theo RunContext, hoặc null. Thứ tự ưu tiên: disarmed, key, stale. */
    export function abortReason(ctx: RunContext): AbortReason | null {
      if (!ctx.armed) return "disarmed";
      if (ctx.keyPressed) return "key";
      if (!(ctx.stateAgeS <= STALE_S)) return "stale";
      return null;
    }

    /** PHY-6 kiểu A: quy đổi (quãng đường s, hướng alpha rad so với thân) sang tư thế đích. */
    export function goalFromDistanceHeading(
      start: Pose,
      s: number,
      alpha: number,
    ): Pose {
      return {
        x: start.x + s * Math.cos(start.theta + alpha),
        y: start.y + s * Math.sin(start.theta + alpha),
        theta: start.theta,
      };
    }

    /** T_dự_kiến (s) = max(quãng đường / vCruise, |góc quay| / wzCruise). */
    export function expectedDuration(
      start: Pose,
      goal: Pose,
      p: RunParams,
    ): number {
      const dist = Math.hypot(goal.x - start.x, goal.y - start.y);
      const ang = Math.abs(wrapAngle(goal.theta - start.theta));
      return Math.max(dist / p.vCruise, ang / p.wzCruise);
    }

    export interface TrackError {
      /** Sai số thế giới. */
      ex: number;
      ey: number;
      /** Sai số quay về khung thân. */
      ebx: number;
      eby: number;
      dist: number;
      /** Sai số góc đã quấn về [-pi, pi]. */
      etheta: number;
    }

    /** Sai số tới đích; world -> body bằng góc theta của xe. */
    export function trackError(pose: Pose, goal: Pose): TrackError {
      const ex = goal.x - pose.x;
      const ey = goal.y - pose.y;
      const c = Math.cos(pose.theta);
      const s = Math.sin(pose.theta);
      return {
        ex,
        ey,
        ebx: c * ex + s * ey,
        eby: -s * ex + c * ey,
        dist: Math.hypot(ex, ey),
        etheta: wrapAngle(goal.theta - pose.theta),
      };
    }

    export interface TrackState {
      goal: Pose;
      params: RunParams;
      /** Hạn chót = 3 * T_dự_kiến + 5 (s). */
      timeoutS: number;
      elapsed: number;
      /** Số chu kỳ liên tiếp đã nằm trong dung sai. */
      okCycles: number;
      /** cmd_vel của chu kỳ trước, dùng để giới hạn gia tốc. */
      prevCmd: BodyVel;
    }

    /** Tạo trạng thái bám đích. Ném RangeError nếu tham số hoặc tư thế không hợp lệ. */
    export function createTrack(
      start: Pose,
      goal: Pose,
      params: RunParams,
    ): TrackState {
      const msg = validateRunParams(params);
      if (msg !== null) throw new RangeError(msg);
      const nums = [start.x, start.y, start.theta, goal.x, goal.y, goal.theta];
      if (!nums.every((n) => Number.isFinite(n))) {
        throw new RangeError("tư thế đầu hoặc đích không hữu hạn");
      }
      return {
        goal: { ...goal },
        params: { ...params },
        timeoutS: 3 * expectedDuration(start, goal, params) + 5,
        elapsed: 0,
        okCycles: 0,
        prevCmd: zeroCmd(),
      };
    }

    export interface TrackInput extends RunContext {
      /** Tư thế hiện tại (khung odometry). */
      pose: Pose;
      /** Thời gian từ chu kỳ trước (s), thường 1/CONTROL_HZ. */
      dt: number;
    }

    export interface TrackStep {
      cmd: BodyVel;
      state: TrackState;
      status: RunStatus;
      error: TrackError;
    }

    /** Một chu kỳ điều khiển PHY-6. Khi done hoặc aborted, cmd là 0. */
    export function trackStep(s: TrackState, input: TrackInput): TrackStep {
      const dt = Number.isFinite(input.dt) && input.dt > 0 ? input.dt : 0;
      const elapsed = s.elapsed + dt;
      const error = trackError(input.pose, s.goal);

      let reason = abortReason(input);
      if (reason === null && elapsed > s.timeoutS) reason = "timeout";
      if (reason !== null) {
        return {
          cmd: zeroCmd(),
          state: { ...s, elapsed, okCycles: 0, prevCmd: zeroCmd() },
          status: { kind: "aborted", reason },
          error,
        };
      }

      const inTol = error.dist < TOL_POS && Math.abs(error.etheta) < TOL_ANG;
      const okCycles = inTol ? s.okCycles + 1 : 0;
      if (okCycles >= DONE_CYCLES) {
        return {
          cmd: zeroCmd(),
          state: { ...s, elapsed, okCycles, prevCmd: zeroCmd() },
          status: { kind: "done" },
          error,
        };
      }

      const p = s.params;
      // Tốc độ mong muốn; thu nhỏ vector tịnh tiến để giữ hướng.
      let vx = KP_LIN * error.ebx;
      let vy = KP_LIN * error.eby;
      const speed = Math.hypot(vx, vy);
      if (speed > p.vCruise) {
        const k = p.vCruise / speed;
        vx *= k;
        vy *= k;
      }
      let wz = KP_ANG * error.etheta;
      if (Math.abs(wz) > p.wzCruise) wz = Math.sign(wz) * p.wzCruise;

      // Giới hạn gia tốc: thu nhỏ vector thay đổi tịnh tiến để giữ hướng; wz giới hạn riêng.
      let dvx = vx - s.prevCmd.vx;
      let dvy = vy - s.prevCmd.vy;
      const dv = Math.hypot(dvx, dvy);
      const maxDv = p.accelLin * dt;
      if (dv > maxDv) {
        const k = maxDv / dv;
        dvx *= k;
        dvy *= k;
      }
      const maxDw = p.accelAng * dt;
      const dw = Math.max(-maxDw, Math.min(maxDw, wz - s.prevCmd.wz));

      const cmd: BodyVel = {
        vx: s.prevCmd.vx + dvx,
        vy: s.prevCmd.vy + dvy,
        wz: s.prevCmd.wz + dw,
      };
      return {
        cmd,
        state: { ...s, elapsed, okCycles, prevCmd: { ...cmd } },
        status: { kind: "running" },
        error,
      };
    }

    export interface WheelRun {
      /** cmd_vel cố định tính từ tốc độ bánh bằng động học thuận. */
      cmd: BodyVel;
      durationS: number;
      elapsed: number;
    }

    /** FR-04: tạo lần chạy theo tốc độ bánh (rad/s) trong durationS giây. Ném RangeError nếu không hợp lệ. */
    export function createWheelRun(wheels: Wheels, durationS: number): WheelRun {
      if (!wheels.every((w) => Number.isFinite(w))) {
        throw new RangeError("tốc độ bánh không hữu hạn");
      }
      if (!Number.isFinite(durationS) || durationS <= 0) {
        throw new RangeError("thời gian chạy phải là số hữu hạn lớn hơn 0");
      }
      return { cmd: forwardKinematics(wheels), durationS, elapsed: 0 };
    }

    export interface WheelRunStep {
      cmd: BodyVel;
      run: WheelRun;
      status: RunStatus;
    }

    /** Một chu kỳ chạy theo tốc độ bánh. Hết giờ thì done; hủy theo RunContext thì aborted. cmd là 0 khi kết thúc. */
    export function wheelRunStep(
      run: WheelRun,
      ctx: RunContext,
      dt: number,
    ): WheelRunStep {
      const elapsed = run.elapsed + (Number.isFinite(dt) && dt > 0 ? dt : 0);
      const next: WheelRun = { ...run, elapsed };
      const reason = abortReason(ctx);
      if (reason !== null) {
        return { cmd: zeroCmd(), run: next, status: { kind: "aborted", reason } };
      }
      if (elapsed >= run.durationS) {
        return { cmd: zeroCmd(), run: next, status: { kind: "done" } };
      }
      return { cmd: { ...run.cmd }, run: next, status: { kind: "running" } };
    }
  ```

  **Bước 5. Tạo `app/client/src/robot/mecanum.test.ts`** với đúng nội dung sau:
  ```ts
    import { describe, expect, it } from "vitest";
    import {
      DynamicsEstimator,
      I_Z,
      LEVER,
      bodyToWorld,
      computeDynamics,
      exceedsSpeedSum,
      forwardKinematics,
      inverseKinematics,
      wheelResidual,
    } from "./mecanum";
    import type { BodyVel, Pose, Wheels } from "./mecanum";
    import {
      DEFAULT_RUN_PARAMS,
      createTrack,
      createWheelRun,
      expectedDuration,
      goalFromDistanceHeading,
      trackStep,
      wheelRunStep,
      wrapAngle,
    } from "./motion";
    import type { RunParams, RunStatus, TrackInput } from "./motion";

    const V: BodyVel = { vx: 0.1, vy: 0.05, wz: 0.2 };

    describe("PHY-1", () => {
      it("thông số dẫn xuất", () => {
        expect(LEVER).toBeCloseTo(0.335, 12);
        expect(I_Z).toBeCloseTo(0.5454, 4);
      });
    });

    describe("PHY-2/PHY-3 động học", () => {
      it("ngược: (0.1, 0.05, 0.2) -> (1.66, -0.34, 4.34, 2.34)", () => {
        const w = inverseKinematics(V);
        [1.66, -0.34, 4.34, 2.34].forEach((e, i) => expect(w[i]).toBeCloseTo(e, 9));
      });

      it("thuận rồi ngược trả lại đầu vào", () => {
        const back = forwardKinematics(inverseKinematics(V));
        expect(back.vx).toBeCloseTo(V.vx, 12);
        expect(back.vy).toBeCloseTo(V.vy, 12);
        expect(back.wz).toBeCloseTo(V.wz, 12);
      });

      it("dư bằng 0 với bánh nhất quán", () => {
        expect(wheelResidual(inverseKinematics(V))).toBeCloseTo(0, 12);
      });

      it("dư khác 0 với (1, -1, -1, 1) và thuận cho vận tốc 0", () => {
        const w: Wheels = [1, -1, -1, 1];
        expect(wheelResidual(w)).toBeCloseTo(0.05, 12);
        const v = forwardKinematics(w);
        expect(v.vx).toBeCloseTo(0, 12);
        expect(v.vy).toBeCloseTo(0, 12);
        expect(v.wz).toBeCloseTo(0, 12);
      });
    });

    describe("PHY-4 thân sang thế giới", () => {
      it("theta = 0 giữ nguyên", () => {
        const r = bodyToWorld({ vx: 1, vy: 0.5, wz: 0.3 }, 0);
        expect(r.xDot).toBeCloseTo(1, 12);
        expect(r.yDot).toBeCloseTo(0.5, 12);
        expect(r.thetaDot).toBeCloseTo(0.3, 12);
      });

      it("theta = pi/2: tiến về +y, trái về -x", () => {
        const r = bodyToWorld({ vx: 1, vy: 0.5, wz: 0 }, Math.PI / 2);
        expect(r.xDot).toBeCloseTo(-0.5, 12);
        expect(r.yDot).toBeCloseTo(1, 12);
      });
    });

    describe("FR-04 cảnh báo tổng tốc độ", () => {
      it("1.567 không cảnh báo, 1.634 có cảnh báo", () => {
        expect(exceedsSpeedSum({ vx: 1, vy: 0.5, wz: 0.2 })).toBe(false);
        expect(exceedsSpeedSum({ vx: 1, vy: 0.5, wz: 0.4 })).toBe(true);
      });
    });

    describe("PHY-5 động lực học", () => {
      it("a = (1, 0), omega_i > 0 -> F_d = 2.425, tau ~ 0.1807", () => {
        const r = computeDynamics({ ax: 1, ay: 0, wzDot: 0 }, [1, 1, 1, 1]);
        expect(r.Fx).toBeCloseTo(9.7, 9);
        for (let i = 0; i < 4; i++) {
          expect(r.Fd[i]).toBeCloseTo(2.425, 9);
          expect(r.tau[i]).toBeCloseTo(0.1807, 3);
          expect(r.over[i]).toBe(false);
        }
        expect(r.tauPct[0]).toBeCloseTo((100 * 0.18072) / 0.981, 2);
      });

      it("omega_i = 0 thì lực cản lăn bằng 0", () => {
        const r = computeDynamics({ ax: 1, ay: 0, wzDot: 0 }, [0, 0, 0, 0]);
        expect(r.tau[0]).toBeCloseTo(0.05 * 2.425, 9);
      });

      it("cờ vượt định mức khi tải lớn", () => {
        const r = computeDynamics({ ax: 100, ay: 0, wzDot: 0 }, [1, 1, 1, 1]);
        expect(r.over.every((f) => f)).toBe(true);
      });

      it("bộ ước lượng hội tụ về a = (1, 0) với vx tăng đều", () => {
        const est = new DynamicsEstimator();
        const dt = 0.05;
        let r = computeDynamics({ ax: 0, ay: 0, wzDot: 0 }, [0, 0, 0, 0]);
        for (let k = 0; k <= 120; k++) {
          const v: BodyVel = { vx: k * dt, vy: 0, wz: 0 };
          r = est.update(v, inverseKinematics(v), dt);
        }
        expect(r.ax).toBeCloseTo(1, 6);
        expect(r.Fd[0]).toBeCloseTo(2.425, 4);
        expect(r.tau[0]).toBeCloseTo(0.1807, 3);
      });

      it("thành phần ly tâm: vx = 0.5, wz = 1 không đổi -> ay = 0.5", () => {
        const est = new DynamicsEstimator();
        const v: BodyVel = { vx: 0.5, vy: 0, wz: 1 };
        let r = est.update(v, inverseKinematics(v), 0.05);
        for (let k = 0; k < 100; k++) r = est.update(v, inverseKinematics(v), 0.05);
        expect(r.ax).toBeCloseTo(0, 9);
        expect(r.ay).toBeCloseTo(0.5, 9);
        expect(r.wzDot).toBeCloseTo(0, 9);
        expect(r.Fy).toBeCloseTo(4.85, 9);
      });
    });

    describe("PHY-6 góc và đích", () => {
      it("wrapAngle về [-pi, pi]", () => {
        expect(wrapAngle(0.1 + 2 * Math.PI)).toBeCloseTo(0.1, 9);
        expect(wrapAngle((3 * Math.PI) / 2)).toBeCloseTo(-Math.PI / 2, 9);
        expect(wrapAngle((-3 * Math.PI) / 2)).toBeCloseTo(Math.PI / 2, 9);
        expect(Math.abs(wrapAngle(Math.PI))).toBeCloseTo(Math.PI, 9);
        expect(wrapAngle(0.5)).toBeCloseTo(0.5, 12);
      });

      it("kiểu A: đích từ quãng đường và hướng", () => {
        const a = goalFromDistanceHeading({ x: 1, y: 2, theta: Math.PI / 2 }, 1, 0);
        expect(a.x).toBeCloseTo(1, 9);
        expect(a.y).toBeCloseTo(3, 9);
        expect(a.theta).toBeCloseTo(Math.PI / 2, 12);
        const b = goalFromDistanceHeading(
          { x: 1, y: 2, theta: Math.PI / 2 },
          1,
          Math.PI / 2,
        );
        expect(b.x).toBeCloseTo(0, 9);
        expect(b.y).toBeCloseTo(2, 9);
      });

      it("timeout = 3 * T_dự_kiến + 5", () => {
        const o: Pose = { x: 0, y: 0, theta: 0 };
        expect(expectedDuration(o, { x: 1, y: 0, theta: 0 }, DEFAULT_RUN_PARAMS)).toBeCloseTo(5, 9);
        expect(createTrack(o, { x: 1, y: 0, theta: 0 }, DEFAULT_RUN_PARAMS).timeoutS).toBeCloseTo(20, 9);
        expect(createTrack(o, { x: 0, y: 0, theta: 1 }, DEFAULT_RUN_PARAMS).timeoutS).toBeCloseTo(8, 9);
      });

      it("tham số không hợp lệ bị từ chối", () => {
        const o: Pose = { x: 0, y: 0, theta: 0 };
        expect(() => createTrack(o, o, { ...DEFAULT_RUN_PARAMS, vCruise: 0 })).toThrow(RangeError);
        expect(() => createTrack(o, o, { ...DEFAULT_RUN_PARAMS, accelAng: NaN })).toThrow(RangeError);
      });
    });

    function simulate(start: Pose, goal: Pose, params: RunParams) {
      const dt = 0.05;
      let s = createTrack(start, goal, params);
      let pose: Pose = { ...start };
      let status: RunStatus = { kind: "running" };
      let steps = 0;
      let maxSpeed = 0;
      let maxDv = 0;
      let prev = { vx: 0, vy: 0, wz: 0 };
      while (status.kind === "running" && steps < 4000) {
        const out = trackStep(s, { pose, dt, stateAgeS: 0.05, armed: true, keyPressed: false });
        s = out.state;
        status = out.status;
        steps++;
        if (status.kind !== "running") break;
        const w = bodyToWorld(out.cmd, pose.theta);
        pose = { x: pose.x + w.xDot * dt, y: pose.y + w.yDot * dt, theta: pose.theta + w.thetaDot * dt };
        maxSpeed = Math.max(maxSpeed, Math.hypot(out.cmd.vx, out.cmd.vy));
        maxDv = Math.max(maxDv, Math.hypot(out.cmd.vx - prev.vx, out.cmd.vy - prev.vy) / dt);
        prev = out.cmd;
      }
      return { status, pose, steps, maxSpeed, maxDv, state: s };
    }

    describe("PHY-6 bộ bám đích trên mô hình tích phân", () => {
      it("tới đích (có quấn góc) trong dung sai, tham số mặc định", () => {
        const goal: Pose = { x: -0.5, y: 0.8, theta: 3.0 };
        const r = simulate({ x: 0, y: 0, theta: -3.0 }, goal, DEFAULT_RUN_PARAMS);
        expect(r.status).toEqual({ kind: "done" });
        expect(Math.hypot(goal.x - r.pose.x, goal.y - r.pose.y)).toBeLessThan(0.02);
        expect(Math.abs(wrapAngle(goal.theta - r.pose.theta))).toBeLessThan(0.035);
        expect(r.maxSpeed).toBeLessThanOrEqual(DEFAULT_RUN_PARAMS.vCruise + 1e-9);
        expect(r.maxDv).toBeLessThanOrEqual(DEFAULT_RUN_PARAMS.accelLin + 1e-9);
        expect(r.state.elapsed).toBeLessThan(r.state.timeoutS);
      });

      it("tới đích với tham số chạy khác (nhanh hơn)", () => {
        const params: RunParams = { vCruise: 0.5, wzCruise: 2, accelLin: 2, accelAng: 3 };
        const goal: Pose = { x: 1.2, y: -0.7, theta: 0.4 };
        const r = simulate({ x: 0.3, y: 0.3, theta: 0.9 }, goal, params);
        expect(r.status).toEqual({ kind: "done" });
        expect(Math.hypot(goal.x - r.pose.x, goal.y - r.pose.y)).toBeLessThan(0.02);
        expect(Math.abs(wrapAngle(goal.theta - r.pose.theta))).toBeLessThan(0.035);
      });

      it("chu kỳ đầu giữ hướng vector và bị giới hạn gia tốc", () => {
        const s = createTrack({ x: 0, y: 0, theta: 0 }, { x: 1, y: 1, theta: 0 }, DEFAULT_RUN_PARAMS);
        const out = trackStep(s, { pose: { x: 0, y: 0, theta: 0 }, dt: 0.05, stateAgeS: 0, armed: true, keyPressed: false });
        expect(out.status).toEqual({ kind: "running" });
        expect(out.cmd.vx).toBeCloseTo(out.cmd.vy, 9);
        expect(Math.hypot(out.cmd.vx, out.cmd.vy)).toBeCloseTo(0.5 * 0.05, 9);
      });

      it("xong cần 3 chu kỳ liên tiếp trong dung sai", () => {
        const g: Pose = { x: 1, y: 1, theta: 0 };
        let s = createTrack(g, g, DEFAULT_RUN_PARAMS);
        const input: TrackInput = { pose: g, dt: 0.05, stateAgeS: 0, armed: true, keyPressed: false };
        const kinds: string[] = [];
        for (let k = 0; k < 3; k++) {
          const out = trackStep(s, input);
          s = out.state;
          kinds.push(out.status.kind);
        }
        expect(kinds).toEqual(["running", "running", "done"]);
      });
    });

    describe("PHY-6 các điều kiện hủy", () => {
      const goal: Pose = { x: 5, y: 0, theta: 0 };
      const base: TrackInput = {
        pose: { x: 0, y: 0, theta: 0 },
        dt: 0.05,
        stateAgeS: 0.1,
        armed: true,
        keyPressed: false,
      };
      const fresh = () => createTrack({ x: 0, y: 0, theta: 0 }, goal, DEFAULT_RUN_PARAMS);

      it("state cũ hơn 500 ms", () => {
        const out = trackStep(fresh(), { ...base, stateAgeS: 0.6 });
        expect(out.status).toEqual({ kind: "aborted", reason: "stale" });
        expect(out.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
      });

      it("disarm", () => {
        const out = trackStep(fresh(), { ...base, armed: false });
        expect(out.status).toEqual({ kind: "aborted", reason: "disarmed" });
        expect(out.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
      });

      it("có phím di chuyển", () => {
        const out = trackStep(fresh(), { ...base, keyPressed: true });
        expect(out.status).toEqual({ kind: "aborted", reason: "key" });
        expect(out.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
      });

      it("quá thời gian", () => {
        const s = fresh();
        const out = trackStep({ ...s, elapsed: s.timeoutS - 0.01 }, base);
        expect(out.status).toEqual({ kind: "aborted", reason: "timeout" });
        expect(out.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
      });

      it("không hủy khi mọi điều kiện ổn", () => {
        expect(trackStep(fresh(), base).status).toEqual({ kind: "running" });
      });
    });

    describe("FR-04 chạy theo tốc độ bánh", () => {
      const w: Wheels = [1.66, -0.34, 4.34, 2.34];
      const ok = { stateAgeS: 0.05, armed: true, keyPressed: false };

      it("cmd_vel bằng động học thuận, hết giờ thì done với cmd 0", () => {
        let run = createWheelRun(w, 3);
        const expected = forwardKinematics(w);
        let steps = 0;
        let status: RunStatus = { kind: "running" };
        while (status.kind === "running" && steps < 1000) {
          const out = wheelRunStep(run, ok, 0.05);
          run = out.run;
          status = out.status;
          steps++;
          if (status.kind === "running") {
            expect(out.cmd.vx).toBeCloseTo(expected.vx, 12);
            expect(out.cmd.vy).toBeCloseTo(expected.vy, 12);
            expect(out.cmd.wz).toBeCloseTo(expected.wz, 12);
          } else {
            expect(out.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
          }
        }
        expect(status).toEqual({ kind: "done" });
        expect(steps).toBeGreaterThanOrEqual(59);
        expect(steps).toBeLessThanOrEqual(61);
      });

      it("hủy khi có phím, disarm, state cũ", () => {
        const run = createWheelRun(w, 3);
        expect(wheelRunStep(run, { ...ok, keyPressed: true }, 0.05).status).toEqual({ kind: "aborted", reason: "key" });
        expect(wheelRunStep(run, { ...ok, armed: false }, 0.05).status).toEqual({ kind: "aborted", reason: "disarmed" });
        expect(wheelRunStep(run, { ...ok, stateAgeS: 0.6 }, 0.05).status).toEqual({ kind: "aborted", reason: "stale" });
      });

      it("đầu vào không hợp lệ bị từ chối", () => {
        expect(() => createWheelRun(w, 0)).toThrow(RangeError);
        expect(() => createWheelRun([1, 2, NaN, 4], 3)).toThrow(RangeError);
      });
    });
  ```

  **Bước 6. Kiểm tra.** Chạy lần lượt trong `app/client` và báo kết quả từng lệnh:
  1. `npm test`
     Mong đợi: `Test Files  1 passed (1)` và `Tests  29 passed (29)`, thoát mã 0. Nếu số test khác 29 hoặc có test fail, kiểm tra xem đã chép đúng nguyên văn chưa; nếu đã đúng thì trả `BLOCKED` kèm tên test và thông báo lỗi, không tự sửa công thức hay test.
  2. `npx tsc --noEmit -p . 2>&1 | grep 'src/robot'`
     Mong đợi: không có dòng nào in ra (mã thoát của `grep` là 1). Lỗi ở file khác (ngoài `src/robot`) nếu có là có sẵn từ trước, chỉ ghi lại, không sửa.
  3. `npx eslint src/robot`
     Mong đợi: không có lỗi hay cảnh báo nào.
  4. `grep -rn "1\.89" src; echo "exit=$?"`
     Mong đợi: không in dòng nào ngoài `exit=1` (SAF-01).
  5. `grep -rnE "from \"(react|next)|document\.|window\." src/robot; echo "exit=$?"`
     Mong đợi: không in dòng nào ngoài `exit=1` (thư viện thuần, không React hay DOM).
  6. `git -C /tmp/claude-1000/-home-vth-ws-mecanum-base/76fe0d3b-44a2-4858-8e13-7f99f2566330/scratchpad/wt/T07 status --short` (chỉ đọc)
     Mong đợi chỉ có: `M app/client/package.json`, `M app/client/package-lock.json`, và `?? app/client/src/robot/`. Có file khác thì báo lại.

  **Báo cáo cuối:** liệt kê file đã chạm, dán kết quả sáu lệnh ở Bước 6, và nêu mọi điểm đã trả `BLOCKED` hoặc chưa rõ.

  **Ghi chú thiết kế (cho người review, Haiku không đổi):**
  1. Spec không định nghĩa `T_dự_kiến` của PHY-6; Work order dùng `max(quãng đường / vCruise, |góc quay quấn| / wzCruise)`. Timeout = `3·T + 5` s.
  2. "Giữ hướng vector" được hiểu: thu nhỏ vector tịnh tiến `(vx, vy)` để `|v| <= vCruise`; giới hạn gia tốc cũng thu nhỏ vector thay đổi `(Δvx, Δvy)`; `wz` được kẹp và giới hạn gia tốc riêng. Các kẹp này là tham số lần chạy do người dùng nhập (không chặn trên), không phải giới hạn phần mềm cố định (SAF-04).
  3. Kiểu A nhận `alpha` theo rad; UI (T11) đổi độ sang rad. Lần chạy theo tốc độ bánh (FR-04) xuất `cmd_vel` cố định từ động học thuận, không giới hạn gia tốc, kết thúc khi hết giờ hoặc bị hủy; hết giờ/hủy đều xuất cmd 0 ở chu kỳ đó (T10 vẫn phải gửi 0 khi dừng).
  4. `DynamicsEstimator` lọc đạo hàm vận tốc đo (thông thấp bậc 1, `alpha = dt/(τ+dt)`); mẫu đầu tiên chỉ lưu mốc nên gia tốc bằng 0 cho tới mẫu thứ hai.
  5. `vitest` phải ghim `^4` do xung đột peer với `@types/node@^20` (ghi nhận để T08+ không nâng nhầm).

### T08 — Kết nối, bàn phím toàn cục, khung ứng dụng
- Trạng thái: TODO · Plan: P3 · Phụ thuộc: T06, T07
- Spec: FR-01, FR-02, FR-03, FR-08, FR-09, SAF-03, PROTO-1, NFR-03, NFR-05
- File: `app/client/src/app/layout.tsx`, `app/client/src/robot/{protocol,store}.ts`, `app/client/src/robot/keyboard.tsx`, `app/client/src/components/robot/app-shell.tsx`
- Đạt khi: lái được từ mọi trang trên mô phỏng, nhiều phím cộng vector, gõ trong ô nhập không làm xe chạy, `Esc` luôn dừng, rời tab thì gửi 0, chuyển trang không rớt WS.
- Work order: _(Sonnet điền; phải dẫn tài liệu Next.js 16 đã đọc)_

## P4 — Các trang

### T09 — Trang tổng quan và hệ thống
- Trạng thái: TODO · Plan: P4 · Phụ thuộc: T08
- Spec: FR-08, FR-09, FR-11, FR-12
- File: `app/client/src/app/page.tsx`, `app/client/src/app/system/page.tsx`, `app/client/src/components/robot/{panels,charts}.tsx`
- Đạt khi: hiển thị đủ số liệu FR-08, RTT, độ trễ vòng lệnh, quỹ đạo, reset odometry hoạt động.
- Work order: _(Sonnet điền)_

### T10 — Động học thuận
- Trạng thái: TODO · Plan: P4 · Phụ thuộc: T09
- Spec: FR-04, PHY-2, PHY-3, PHY-4
- File: `app/client/src/app/kinematics/forward/page.tsx`
- Đạt khi: đủ chuỗi tính realtime và thành phần dư; chạy có giới hạn thời gian; bấm phím di chuyển thì hủy chạy.
- Work order: _(Sonnet điền)_

### T11 — Động học ngược
- Trạng thái: TODO · Plan: P4 · Phụ thuộc: T09
- Spec: FR-05, FR-06, PHY-6
- File: `app/client/src/app/kinematics/inverse/page.tsx`
- Đạt khi: chọn được kiểu A/B; hiện 4 tốc độ bánh và tiến độ; tới đích trên mô phỏng trong sai số PHY-6; các điều kiện hủy hoạt động.
- Work order: _(Sonnet điền)_

### T12 — Động lực học
- Trạng thái: TODO · Plan: P4 · Phụ thuộc: T09
- Spec: FR-07, PHY-5
- File: `app/client/src/app/dynamics/page.tsx`, `app/client/src/components/robot/charts.tsx`
- Đạt khi: hiện realtime Fx, Fy, Mz, F_d và τ từng bánh, % định mức, có cảnh báo.
- Work order: _(Sonnet điền)_

### T13 — LiDAR
- Trạng thái: TODO · Plan: P4 · Phụ thuộc: T09
- Spec: FR-10, PROTO-2
- File: `app/client/src/app/lidar/page.tsx`, `app/client/src/components/robot/charts.tsx`, `robot/robot_agent/server.py`, `app/server/app_server/robot_link.py`
- Đạt khi: vẽ polar 5–10 Hz trên mô phỏng, khung nhị phân đúng PROTO-2, không dồn hàng đợi.
- Work order: _(Sonnet điền)_

## P5 — Kiểm chứng

### T14 — Kiểm thử toàn tuyến trên mô phỏng
- Trạng thái: TODO · Plan: P5 · Phụ thuộc: T10, T11, T12, T13
- Spec: SAF-01, SAF-02, SAF-03, SAF-04, SAF-05, SAF-07, NFR-02, NFR-04, NFR-06
- Việc: chạy toàn bộ test, lint, build; `app/client/src` không chứa hệ số; bắt payload WS chứng minh web không nhận đơn vị wire; ngắt từng chặng và đo thời gian tự dừng; kiểm tra trên trình duyệt thật.
- Đạt khi: tất cả qua, kết quả đo ghi vào mục này.
- Work order: _(Sonnet điền)_

### T15 — Thử trên Jetson (cần người dùng)
- Trạng thái: TODO · Plan: P5 · Phụ thuộc: T14, Jetson online
- Spec: SAF-08, NFR-02
- Việc: triển khai agent; nhấc bánh, thử watchdog firmware; xác minh A-4; đo độ trễ thật; chạy thử trên mặt đất ở tốc độ thấp.
- Đạt khi: người dùng xác nhận kết quả; giả định sai được đưa về spec.md để sửa.
- Work order: _(Sonnet điền)_

## Ma trận Plan → Task

| Giai đoạn | Task |
|---|---|
| P0 | T01 |
| P1 | T02, T03, T04 |
| P2 | T05, T06 |
| P3 | T07, T08 |
| P4 | T09, T10, T11, T12, T13 |
| P5 | T14, T15 |
