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
- Trạng thái: MERGED · Plan: P1 · Phụ thuộc: T03
- Spec: FR-03, SAF-03, SAF-07, PROTO-2, NFR-03, NFR-06
- File: `robot/robot_agent/{__main__,config,server,sim}.py`, `deploy/robot-agent.service`, `robot/tests/test_robot.py`, `pyproject.toml` (chỉ cấu hình pytest-asyncio)
- Đạt khi: chạy `ROBOT_SIMULATE=true python -m robot_agent`; sai token bị từ chối; message không phải `cmd_vel` bị bỏ; mất link thì writer về 0; thiết bị lỗi được thử lại độc lập.
- Work order:

  **QUY TẮC ĐẦU TIÊN: Chỉ chạm các file được liệt kê dưới đây. Nếu thiếu thông tin hoặc có mâu thuẫn, dừng lại và trả `BLOCKED` kèm câu hỏi. Không chạy `git commit` (và không chạy lệnh git nào làm thay đổi repo). Các file được phép chạm: `robot/robot_agent/config.py`, `sim.py`, `server.py`, `__main__.py` (tạo mới), `deploy/robot-agent.service` (tạo mới), `robot/tests/test_robot.py` (sửa), `pyproject.toml` (chỉ thêm đúng một dòng). Không sửa `drive.py`, `hardware.py`, `.env.example` hay bất kỳ file nào khác. Không khởi động camera. Không thêm hệ số 1.89 hay giới hạn tốc độ vào đâu cả.**

  Thư mục làm việc: `/home/vth/ws/mecanum_base` (nhánh `feature/T04-robot-server`). Dùng `.venv/bin/...`. Tất cả code dưới đây đã được Sonnet chạy thử trong bản sao với `websockets 16.1.1`: 73 test pass, ổn định qua 30 lần chạy kể cả khi CPU bị tải. Sao chép **nguyên văn** (bỏ 2 dấu cách thụt đầu dòng của khối markdown); không "cải tiến".

  **Quyết định thiết kế đã chốt (Haiku không đổi):**
  - Cấu hình: biến môi trường thật thắng `.env` ở gốc repo (`python-dotenv`, `dotenv_values`, không ghi vào `os.environ`). `ROBOT_LINK_TOKEN` rỗng thì `ConfigError`, `__main__` in lỗi ra stderr và thoát mã 2 (không bao giờ khởi động). `ROBOT_MOTION_ENABLED` mặc định `false`. `ROBOT_BIND_HOST` mặc định `127.0.0.1`; địa chỉ đại diện (`0.0.0.0`, `::`, `*`) bị từ chối vì chỉ được bind IP cụ thể.
  - `sim.py`: tính lười theo đồng hồ (không thread). `SimulatedStm32` đáp ứng bậc nhất (`tau_s=0.1`), báo vận tốc làm tròn 1 mm/s (đơn vị wire), `t_ns` đơn điệu không giảm. `SimulatedLidar` cho scan 360 điểm ở 10 Hz. Không import thư viện phần cứng (chỉ import kiểu dữ liệu từ `hardware.py`, vốn không import `serial` ở mức module).
  - `server.py`: `websockets.asyncio.server.serve`, đường dẫn `/ws`, kiểm `Authorization: Bearer <token>` bằng `hmac.compare_digest` ngay trong handshake (`process_request`): sai/thiếu token trả HTTP 401, sai đường dẫn trả 404. Chỉ nhận đúng tập khóa `{t, seq, vx, vy, wz}` với `t == "cmd_vel"`, `seq` là số nguyên, ba vận tốc là số (không phải bool); thứ khác (JSON hỏng, khung nhị phân, khóa thừa như `src`, kiểu sai) chỉ tăng bộ đếm `ignored`, không tới writer. Giá trị NaN/vô cực/quá int16 vẫn do `CmdVelWriter` loại (SAF-04). Tin nhắn dài quá 1024 byte làm websockets đóng kết nối (mã 1009).
  - Kết nối hợp lệ mới nhất thay kết nối cũ (SAF-07): gọi `writer.clear()` ngay khi thay, đóng cũ với mã 4000, bỏ qua mọi tin nhắn đến muộn từ kết nối cũ. Kết nối hiện tại đóng thì `writer.clear()` (SAF-03c). `last_cmd_seq` là `seq` của `cmd_vel` gần nhất mà writer chấp nhận, về `null` khi đổi/mất kết nối.
  - State gửi tối đa 50 Hz, theo vòng: dựng state mới nhất, `await send`, rồi ngủ đến chu kỳ kế (nếu trễ thì bỏ qua, không bù): peer chậm chỉ nhận state mới nhất, không có hàng đợi (NFR-03). Chỗ thêm khung nhị phân `scan` của T13 là phương thức rỗng `RobotServer._send_extras` (gọi một lần mỗi vòng); T04 không cài đặt.
  - Tên trường state (PROTO-2 chỉ chốt `t_mono_ns`, `last_cmd_seq`; các tên còn lại lấy theo PROTO-1): `t`, `t_mono_ns` (thời điểm mẫu STM32, đồng hồ monotonic của robot; nếu chưa có mẫu thì dùng giờ hiện tại), `last_cmd_seq`, `vel{vx,vy,wz}`, `imu{ax,ay,az,gx,gy,gz}`, `voltage`, `flag_stop`, `charge{current_a,red,charging,set_state}`, `health{stm,lidar,writer}`. Khi chưa có telemetry thì `vel`, `imu`, `voltage`, `flag_stop` là `null`; chưa có frame phụ thì `charge` là `null`. Health thiết bị: `{ok,state,error,restarts}`; health writer: `{running,healthy,error_count,last_error,rejected_count}`.
  - `__main__.py`: mỗi thiết bị do một `SupervisedDevice` riêng giám sát (khởi động lỗi, hoặc không có mẫu mới quá `stale_s` thì dừng, ghi lỗi vào health, chờ back-off 0.5 s nhân đôi tới 5 s rồi tạo nguồn mới). `SupervisedDevice` cũng đóng vai nguồn (`latest`, `latest_aux`, `send_velocity`) cho writer và server: khi chưa có nguồn chạy thì `latest` là `None` và `send_velocity` ném `RuntimeError`, writer ghi lỗi và tự thử lại. Bind lặp lại với back-off nếu `OSError` (Tailscale IP chưa lên). Tắt máy (SIGTERM/SIGINT): đóng bind, đóng server (mỗi kết nối `clear()`), `writer.stop()` ghi 0 cuối khi STM32 còn chạy, rồi mới dừng thiết bị.

  **Bước 1. `pyproject.toml`: thêm đúng một dòng** ngay dưới dòng `asyncio_mode = "auto"`:
  ```
  # old
  asyncio_mode = "auto"
  addopts = "-q"
  # new
  asyncio_mode = "auto"
  asyncio_default_fixture_loop_scope = "function"
  addopts = "-q"
  ```

  **Bước 2. Tạo `robot/robot_agent/config.py`** với đúng nội dung:

  ```python
  """Robot agent configuration, read from the environment and the repo-root .env file.

  Real environment variables win over .env. The link token is mandatory: an empty
  ROBOT_LINK_TOKEN refuses to start (SAF-07). Motion is off unless explicitly enabled (SAF-02).
  """
  from __future__ import annotations

  import os
  from collections.abc import Mapping
  from dataclasses import dataclass
  from pathlib import Path

  from dotenv import dotenv_values

  # robot/robot_agent/config.py -> repo root (also /opt/mecanum_base on the Jetson).
  ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

  _TRUE = frozenset({"1", "true", "yes", "on"})
  _FALSE = frozenset({"0", "false", "no", "off"})
  _WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", "*"})


  class ConfigError(ValueError):
      """The configuration is unusable; the agent must not start."""


  @dataclass(frozen=True)
  class Config:
      motion_enabled: bool
      simulate: bool
      stm_port: str
      stm_baud: int
      lidar_port: str
      lidar_baud: int
      bind_host: str
      bind_port: int
      link_token: str


  def _text(env: Mapping[str, str], name: str, default: str) -> str:
      value = env.get(name, "").strip()
      return value if value else default


  def _flag(env: Mapping[str, str], name: str) -> bool:
      value = env.get(name, "").strip().lower()
      if not value:
          return False
      if value in _TRUE:
          return True
      if value in _FALSE:
          return False
      raise ConfigError(f"{name} must be true or false")


  def _integer(env: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
      raw = env.get(name, "").strip()
      if not raw:
          return default
      try:
          value = int(raw)
      except ValueError:
          raise ConfigError(f"{name} must be an integer") from None
      if not low <= value <= high:
          raise ConfigError(f"{name} must be between {low} and {high}")
      return value


  def load_config(
      environ: Mapping[str, str] | None = None, *, env_file: Path | str = ENV_FILE
  ) -> Config:
      if environ is None:
          file_values = {k: v for k, v in dotenv_values(env_file).items() if v is not None}
          environ = {**file_values, **os.environ}
      token = environ.get("ROBOT_LINK_TOKEN", "").strip()
      if not token:
          raise ConfigError("ROBOT_LINK_TOKEN is empty: refusing to start without a link token")
      host = _text(environ, "ROBOT_BIND_HOST", "127.0.0.1")
      if host in _WILDCARD_HOSTS:
          raise ConfigError("ROBOT_BIND_HOST must be a specific address, not a wildcard")
      return Config(
          motion_enabled=_flag(environ, "ROBOT_MOTION_ENABLED"),
          simulate=_flag(environ, "ROBOT_SIMULATE"),
          stm_port=_text(environ, "STM_PORT", "/dev/rai_controller"),
          stm_baud=_integer(environ, "STM_BAUD", 115200, 1, 4_000_000),
          lidar_port=_text(environ, "LIDAR_PORT", "/dev/rai_lidar"),
          lidar_baud=_integer(environ, "LIDAR_BAUD", 460800, 1, 4_000_000),
          bind_host=host,
          bind_port=_integer(environ, "ROBOT_BIND_PORT", 8765, 1, 65535),
          link_token=token,
      )
  ```

  **Bước 3. Tạo `robot/robot_agent/sim.py`** với đúng nội dung:

  ```python
  """Simulated STM32 and LiDAR for ROBOT_SIMULATE=true (NFR-06).

  Drop-in replacements for the real sources: same attributes and methods that the writer, the
  server and the supervisor use. Both are computed lazily from a clock, so there are no threads.
  No hardware libraries are imported.
  """
  from __future__ import annotations

  import math
  import threading
  import time
  from collections.abc import Callable

  from .hardware import (
      LidarPoint,
      LidarScan,
      Stm32AuxTelemetry,
      Stm32Telemetry,
      encode_stm32_velocity_command,
  )


  class SimulatedStm32:
      """First-order velocity response toward the last command, reported in wire units."""

      def __init__(
          self,
          *,
          tau_s: float = 0.1,
          voltage_v: float = 12.0,
          clock_ns: Callable[[], int] = time.monotonic_ns,
      ) -> None:
          if not math.isfinite(tau_s) or tau_s <= 0.0:
              raise ValueError("tau_s must be positive and finite")
          self.tau_s = tau_s
          self.voltage_v = voltage_v
          self.errors = 0
          self.last_command: tuple[int, float, float, float] | None = None
          self._clock = clock_ns
          self._lock = threading.Lock()
          self._started = False
          self._t_ns = 0
          self._velocity = (0.0, 0.0, 0.0)
          self._target = (0.0, 0.0, 0.0)

      def _advance(self) -> None:
          # Caller holds the lock. The sample time never goes backwards.
          now = max(self._clock(), self._t_ns)
          dt = (now - self._t_ns) / 1e9
          if dt > 0.0:
              keep = math.exp(-dt / self.tau_s)
              self._velocity = tuple(
                  goal + (value - goal) * keep for value, goal in zip(self._velocity, self._target)
              )
          self._t_ns = now

      def start(self) -> None:
          with self._lock:
              self._started = True
              self._t_ns = self._clock()
              self._velocity = (0.0, 0.0, 0.0)
              self._target = (0.0, 0.0, 0.0)
              self.errors = 0

      def stop(self) -> None:
          with self._lock:
              self._started = False
              self._velocity = (0.0, 0.0, 0.0)
              self._target = (0.0, 0.0, 0.0)

      def send_velocity(self, vx_mps: float, vy_mps: float, wz_radps: float) -> None:
          # Same validation as the real frame encoder (finite and within int16 millimetres).
          encode_stm32_velocity_command(vx_mps, vy_mps, wz_radps)
          with self._lock:
              if not self._started:
                  raise RuntimeError("simulated STM32 is not started")
              self._advance()
              wire = (vx_mps, vy_mps, wz_radps)
              self._target = tuple(round(float(v) * 1000.0) / 1000.0 for v in wire)
              self.last_command = (self._t_ns, float(vx_mps), float(vy_mps), float(wz_radps))

      @property
      def latest(self) -> Stm32Telemetry | None:
          with self._lock:
              if not self._started:
                  return None
              self._advance()
              vx, vy, wz = (round(v * 1000.0) / 1000.0 for v in self._velocity)
              return Stm32Telemetry(
                  t_ns=self._t_ns,
                  flag_stop=0,
                  vx_mps=vx,
                  vy_mps=vy,
                  wz_radps=wz,
                  accel_x_mps2=0.0,
                  accel_y_mps2=0.0,
                  accel_z_mps2=9.81,
                  gyro_x_radps=0.0,
                  gyro_y_radps=0.0,
                  gyro_z_radps=wz,
                  voltage_v=self.voltage_v,
              )

      @property
      def latest_aux(self) -> Stm32AuxTelemetry | None:
          with self._lock:
              if not self._started:
                  return None
              self._advance()
              return Stm32AuxTelemetry(
                  t_ns=self._t_ns, charging_current_a=0.0, red=0, charging=False, charge_set_state=0
              )


  class SimulatedLidar:
      """A fake 360 point scan, one new scan every period_s (default 10 Hz)."""

      def __init__(
          self,
          *,
          period_s: float = 0.1,
          clock_ns: Callable[[], int] = time.monotonic_ns,
      ) -> None:
          if not math.isfinite(period_s) or period_s <= 0.0:
              raise ValueError("period_s must be positive and finite")
          self.error: Exception | None = None
          self._period_ns = max(1, int(round(period_s * 1e9)))
          self._clock = clock_ns
          self._lock = threading.Lock()
          self._started = False
          self._t0_ns = 0
          self._scan: LidarScan | None = None

      def start(self) -> None:
          with self._lock:
              self._started = True
              self._t0_ns = self._clock()
              self._scan = None
              self.error = None

      def stop(self) -> None:
          with self._lock:
              self._started = False
              self._scan = None

      @property
      def scan_rate_hz(self) -> float:
          return 1e9 / self._period_ns if self._started else 0.0

      @property
      def latest(self) -> LidarScan | None:
          with self._lock:
              if not self._started:
                  return None
              index = (self._clock() - self._t0_ns) // self._period_ns
              if index < 1:
                  return None
              t_ns = self._t0_ns + index * self._period_ns
              if self._scan is None or self._scan.t_ns != t_ns:
                  wobble = 0.05 * math.sin(index / 5.0)
                  points = tuple(
                      LidarPoint(
                          t_ns,
                          math.radians(degree),
                          2.0 + 0.5 * math.sin(math.radians(2 * degree)) + wobble,
                          100,
                          0,
                      )
                      for degree in range(360)
                  )
                  self._scan = LidarScan(t_ns, points)
              return self._scan
  ```

  **Bước 4. Tạo `robot/robot_agent/server.py`** với đúng nội dung:

  ```python
  """Robot WebSocket server (PROTO-2): ws://<ROBOT_BIND_HOST>:<ROBOT_BIND_PORT>/ws.

  Down: only {"t":"cmd_vel","seq","vx","vy","wz"} (wire units) reaches the writer (FR-03).
  Up: JSON "state" at most 50 Hz. Binary "scan" frames are added in T13 (see _send_extras).
  The robot knows nothing about the app-side scale factor.
  """
  from __future__ import annotations

  import asyncio
  import hmac
  import json
  import time
  from collections.abc import Callable
  from http import HTTPStatus
  from typing import Any
  from urllib.parse import urlsplit

  from websockets.asyncio.server import serve
  from websockets.exceptions import ConnectionClosed

  WS_PATH = "/ws"
  MAX_STATE_HZ = 50.0
  MAX_MESSAGE_BYTES = 1024
  CLOSE_REPLACED = 4000
  _CMD_KEYS = frozenset(("t", "seq", "vx", "vy", "wz"))


  def _number(value: Any) -> bool:
      return isinstance(value, (int, float)) and not isinstance(value, bool)


  def parse_cmd_vel(data: Any) -> tuple[int, float, float, float] | None:
      """Return (seq, vx, vy, wz) for a well-formed cmd_vel message, else None."""
      if not isinstance(data, dict) or set(data) != _CMD_KEYS or data["t"] != "cmd_vel":
          return None
      seq = data["seq"]
      if isinstance(seq, bool) or not isinstance(seq, int):
          return None
      if not (_number(data["vx"]) and _number(data["vy"]) and _number(data["wz"])):
          return None
      return seq, data["vx"], data["vy"], data["wz"]


  class RobotServer:
      def __init__(
          self,
          *,
          token: str,
          writer: Any,
          stm: Any,
          devices: Callable[[], dict[str, dict[str, Any]]],
          state_hz: float = MAX_STATE_HZ,
      ) -> None:
          """writer: CmdVelWriter. stm: object with latest/latest_aux (may return None).
          devices: returns {"stm": {...}, "lidar": {...}} health dicts from the supervisors."""
          if not token:
              raise ValueError("link token must not be empty")
          if not 0.0 < state_hz <= MAX_STATE_HZ:
              raise ValueError(f"state_hz must be in (0, {MAX_STATE_HZ}]")
          self._expected = ("Bearer " + token).encode("utf-8")
          self.writer = writer
          self._stm = stm
          self._devices = devices
          self._period_s = 1.0 / state_hz
          self._server: Any = None
          self._current: Any = None
          self._closers: set[asyncio.Future] = set()
          self._last_cmd_seq: int | None = None
          self.ignored = 0  # messages dropped without reaching the writer

      # ---- lifecycle ----

      async def start(self, host: str, port: int) -> int:
          """Bind and serve. Raises OSError if the address is not available. Returns the port."""
          self._server = await serve(
              self._handler,
              host,
              port,
              process_request=self._process_request,
              max_size=MAX_MESSAGE_BYTES,
              compression=None,
              ping_interval=2,
              ping_timeout=2,
          )
          return int(self._server.sockets[0].getsockname()[1])

      async def close(self) -> None:
          if self._server is not None:
              self._server.close()  # closes live connections; each handler then clears the writer
              await self._server.wait_closed()
              self._server = None

      # ---- handshake ----

      def _authorized(self, header: str | None) -> bool:
          return hmac.compare_digest((header or "").encode("utf-8"), self._expected)

      def _process_request(self, connection: Any, request: Any) -> Any:
          if urlsplit(request.path).path != WS_PATH:
              return connection.respond(HTTPStatus.NOT_FOUND, "not found\n")
          if not self._authorized(request.headers.get("Authorization")):
              return connection.respond(HTTPStatus.UNAUTHORIZED, "unauthorized\n")
          return None

      # ---- one connection ----

      def _claim(self, conn: Any) -> None:
          """The newest valid connection replaces the old one (SAF-07)."""
          old, self._current = self._current, conn
          self._last_cmd_seq = None
          if old is not None:
              self.writer.clear()  # SAF-03c: the replaced link's command must not survive
              closer = asyncio.ensure_future(old.close(CLOSE_REPLACED, "replaced"))
              self._closers.add(closer)
              closer.add_done_callback(self._closers.discard)

      def _release(self, conn: Any) -> None:
          if self._current is conn:
              self._current = None
              self._last_cmd_seq = None
              self.writer.clear()  # SAF-03c: link lost -> writer returns to zero

      async def _handler(self, conn: Any) -> None:
          self._claim(conn)
          sender = asyncio.ensure_future(self._send_states(conn))
          try:
              async for message in conn:
                  if self._current is not conn:
                      break
                  self._on_message(message)
          except ConnectionClosed:
              pass
          finally:
              self._release(conn)
              sender.cancel()
              await asyncio.gather(sender, return_exceptions=True)

      def _on_message(self, message: str | bytes) -> None:
          command = None
          if isinstance(message, str):
              try:
                  command = parse_cmd_vel(json.loads(message))
              except (ValueError, RecursionError):
                  command = None
          if command is None:  # binary frame, bad JSON, or anything but a valid cmd_vel
              self.ignored += 1
              return
          seq, vx, vy, wz = command
          if self.writer.set_cmd_vel(vx, vy, wz):
              self._last_cmd_seq = seq

      # ---- state out ----

      def build_state(self) -> dict[str, Any]:
          sample = self._stm.latest
          aux = self._stm.latest_aux
          devices = self._devices()
          health = self.writer.health()
          state: dict[str, Any] = {
              "t": "state",
              "t_mono_ns": sample.t_ns if sample is not None else time.monotonic_ns(),
              "last_cmd_seq": self._last_cmd_seq,
              "vel": None,
              "imu": None,
              "voltage": None,
              "flag_stop": None,
              "charge": None,
              "health": {
                  "stm": devices["stm"],
                  "lidar": devices["lidar"],
                  "writer": {
                      "running": health.running,
                      "healthy": health.healthy,
                      "error_count": health.error_count,
                      "last_error": health.last_error,
                      "rejected_count": health.rejected_count,
                  },
              },
          }
          if sample is not None:
              state["vel"] = {"vx": sample.vx_mps, "vy": sample.vy_mps, "wz": sample.wz_radps}
              state["imu"] = {
                  "ax": sample.accel_x_mps2,
                  "ay": sample.accel_y_mps2,
                  "az": sample.accel_z_mps2,
                  "gx": sample.gyro_x_radps,
                  "gy": sample.gyro_y_radps,
                  "gz": sample.gyro_z_radps,
              }
              state["voltage"] = sample.voltage_v
              state["flag_stop"] = sample.flag_stop
          if aux is not None:
              state["charge"] = {
                  "current_a": aux.charging_current_a,
                  "red": aux.red,
                  "charging": aux.charging,
                  "set_state": aux.charge_set_state,
              }
          return state

      async def _send_states(self, conn: Any) -> None:
          # One send at a time: a slow peer only ever receives the newest state, because the next
          # state is built after the previous send finished. No queue, no backlog (NFR-03).
          loop = asyncio.get_running_loop()
          due = loop.time()
          try:
              while self._current is conn:
                  await conn.send(json.dumps(self.build_state(), separators=(",", ":")))
                  await self._send_extras(conn)
                  due += self._period_s
                  now = loop.time()
                  if due < now:
                      due = now  # fell behind: skip ahead, never burst above the rate limit
                  await asyncio.sleep(due - now)
          except ConnectionClosed:
              return

      async def _send_extras(self, conn: Any) -> None:
          """T13 adds binary `scan` frames here (PROTO-2). Intentionally empty in T04."""
  ```

  **Bước 5. Tạo `robot/robot_agent/__main__.py`** với đúng nội dung:

  ```python
  """Robot agent entry point: python -m robot_agent.

  Starts the STM32 and LiDAR sources (real, or simulated with ROBOT_SIMULATE=true), the cmd_vel
  writer and the WebSocket server. Each device is supervised on its own: a device that fails to
  start, or later stops producing data, is reported in health and retried with back-off, without
  affecting the writer, the other device or the server. The camera is never started (D-07).
  """
  from __future__ import annotations

  import asyncio
  import logging
  import signal
  import sys
  import time
  from collections.abc import Callable
  from typing import Any

  from . import hardware
  from .config import Config, ConfigError, load_config
  from .drive import CmdVelWriter
  from .server import RobotServer
  from .sim import SimulatedLidar, SimulatedStm32

  log = logging.getLogger("robot_agent")


  class SupervisedDevice:
      """Starts a source from a factory, watches it for fresh data, restarts it with back-off.

      Also acts as the source itself (latest, latest_aux, send_velocity) so the writer and the
      server keep working across restarts: while there is no running source, latest is None and
      send_velocity raises, which the writer records and retries.
      """

      def __init__(
          self,
          name: str,
          factory: Callable[[], Any],
          probe: Callable[[Any], int | None],
          *,
          stale_s: float,
          backoff_s: float = 0.5,
          max_backoff_s: float = 5.0,
          poll_s: float = 0.1,
      ) -> None:
          self.name = name
          self._factory = factory
          self._probe = probe  # returns a stamp that changes whenever the source produced data
          self._stale_s = stale_s
          self._backoff_s = backoff_s
          self._max_backoff_s = max_backoff_s
          self._poll_s = poll_s
          self._source: Any = None
          self._state = "starting"
          self._error: str | None = None
          self.restarts = 0

      # ---- source proxy ----

      @property
      def latest(self) -> Any:
          source = self._source
          return source.latest if source is not None else None

      @property
      def latest_aux(self) -> Any:
          source = self._source
          return getattr(source, "latest_aux", None) if source is not None else None

      def send_velocity(self, vx: float, vy: float, wz: float) -> None:
          source = self._source
          if source is None:
              raise RuntimeError(f"{self.name} is not running")
          source.send_velocity(vx, vy, wz)

      def health(self) -> dict[str, Any]:
          return {
              "ok": self._state == "ok",
              "state": self._state,
              "error": self._error,
              "restarts": self.restarts,
          }

      # ---- supervision ----

      @staticmethod
      def _stop_now(source: Any) -> None:
          try:
              source.stop()
          except Exception:
              log.exception("stopping a device source failed")

      async def _watch(self, source: Any) -> tuple[bool, str]:
          """Wait until the source fails or goes quiet. Returns (produced_data, reason)."""
          stamp = None
          produced = False
          last_progress = time.monotonic()
          while True:
              await asyncio.sleep(self._poll_s)
              error = getattr(source, "error", None)
              if error is not None:
                  return produced, f"{type(error).__name__}: {error}"
              try:
                  current = self._probe(source)
              except Exception as exc:
                  return produced, f"{type(exc).__name__}: {exc}"
              now = time.monotonic()
              if current is not None and current != stamp:
                  stamp = current
                  produced = True
                  last_progress = now
                  self._state = "ok"
                  self._error = None
              elif now - last_progress > self._stale_s:
                  return produced, f"no data for more than {self._stale_s:g} s"

      async def run(self) -> None:
          delay = self._backoff_s
          source = None
          try:
              while True:
                  produced = False
                  try:
                      self._state = "starting"
                      source = self._factory()
                      await asyncio.to_thread(source.start)
                      self._source = source
                      produced, reason = await self._watch(source)
                  except Exception as exc:
                      reason = f"{type(exc).__name__}: {exc}"
                  self._source = None
                  if source is not None:
                      await asyncio.to_thread(self._stop_now, source)
                      source = None
                  self._state = "failed"
                  self._error = reason
                  self.restarts += 1
                  log.warning("%s: %s; retrying in %.1f s", self.name, reason, delay)
                  delay = self._backoff_s if produced else min(delay * 2, self._max_backoff_s)
                  await asyncio.sleep(delay)
          finally:
              self._source = None
              if source is not None:  # cancelled while a source was up
                  self._stop_now(source)


  async def bind_with_retry(
      server: RobotServer,
      host: str,
      port: int,
      *,
      delay_s: float = 1.0,
      max_delay_s: float = 5.0,
  ) -> int:
      """Bind the server, retrying while the address is not available (Tailscale not up yet)."""
      while True:
          try:
              actual = await server.start(host, port)
          except OSError as error:
              log.warning("cannot bind %s:%s (%s); retrying in %.1f s", host, port, error, delay_s)
              await asyncio.sleep(delay_s)
              delay_s = min(delay_s * 2, max_delay_s)
              continue
          log.info("listening on %s:%s", host, actual)
          return actual


  def _latest_stamp(source: Any) -> int | None:
      sample = source.latest
      return sample.t_ns if sample is not None else None


  def build_devices(config: Config) -> tuple[SupervisedDevice, SupervisedDevice]:
      if config.simulate:

          def make_stm() -> Any:
              return SimulatedStm32()

          def make_lidar() -> Any:
              return SimulatedLidar()

      else:

          def make_stm() -> Any:
              return hardware.Stm32SerialSource(config.stm_port, baudrate=config.stm_baud)

          def make_lidar() -> Any:
              return hardware.N10PSerialSource(
                  config.lidar_port,
                  profile=hardware.N10P_PROTOCOL_PROFILE,
                  baudrate=config.lidar_baud,
              )

      stm = SupervisedDevice("stm", make_stm, _latest_stamp, stale_s=2.0)
      lidar = SupervisedDevice("lidar", make_lidar, _latest_stamp, stale_s=3.0)
      return stm, lidar


  async def run(config: Config) -> None:
      stop = asyncio.Event()
      loop = asyncio.get_running_loop()
      for signum in (signal.SIGTERM, signal.SIGINT):
          loop.add_signal_handler(signum, stop.set)

      stm, lidar = build_devices(config)
      writer = CmdVelWriter(stm, motion_enabled=config.motion_enabled)
      server = RobotServer(
          token=config.link_token,
          writer=writer,
          stm=stm,
          devices=lambda: {"stm": stm.health(), "lidar": lidar.health()},
      )
      if not config.motion_enabled:
          log.warning("ROBOT_MOTION_ENABLED is false: only zero velocity will be written")
      if config.simulate:
          log.warning("ROBOT_SIMULATE is true: using simulated STM32 and LiDAR")

      writer.start()
      device_tasks = [asyncio.ensure_future(stm.run()), asyncio.ensure_future(lidar.run())]
      bind_task = asyncio.ensure_future(
          bind_with_retry(server, config.bind_host, config.bind_port)
      )
      try:
          await stop.wait()
      finally:
          log.info("shutting down")
          bind_task.cancel()
          await asyncio.gather(bind_task, return_exceptions=True)
          await server.close()  # each open connection clears the writer
          # The final zero goes out while the STM32 source is still running.
          if not await asyncio.to_thread(writer.stop):
              log.error("final zero velocity could not be written")
          for task in device_tasks:
              task.cancel()
          await asyncio.gather(*device_tasks, return_exceptions=True)  # stops the sources


  def main() -> int:
      logging.basicConfig(
          level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
      )
      try:
          config = load_config()
      except ConfigError as error:
          print(f"robot_agent: {error}", file=sys.stderr)
          return 2
      asyncio.run(run(config))
      return 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

  **Bước 6. Tạo thư mục `deploy/` (`mkdir -p deploy`) và `deploy/robot-agent.service`** với đúng nội dung:

  ```ini
  # systemd unit for the robot agent on the Jetson.
  # NOTE: the real install path on the Jetson is not known yet (confirm in T15). /opt/mecanum_base
  # is a placeholder: adjust WorkingDirectory, EnvironmentFile and ExecStart together, and set
  # User= to the account that owns the install and may open the serial devices.
  # Install: copy the repo there, create .venv, run `pip install -e ".[robot]"`, create .env from
  # .env.example (ROBOT_LINK_TOKEN must be set), then:
  #   sudo cp deploy/robot-agent.service /etc/systemd/system/ && sudo systemctl daemon-reload
  #   sudo systemctl enable --now robot-agent
  [Unit]
  Description=Mecanum robot agent (WebSocket server, STM32, LiDAR)
  After=network-online.target tailscaled.service
  Wants=network-online.target

  [Service]
  Type=simple
  #User=CHANGE_ME
  SupplementaryGroups=dialout
  WorkingDirectory=/opt/mecanum_base
  EnvironmentFile=/opt/mecanum_base/.env
  Environment=PYTHONUNBUFFERED=1
  ExecStart=/opt/mecanum_base/.venv/bin/python -m robot_agent
  Restart=on-failure
  RestartSec=3
  # Exit status 2 means a configuration error (for example an empty ROBOT_LINK_TOKEN): do not loop.
  RestartPreventExitStatus=2
  KillSignal=SIGTERM
  TimeoutStopSec=15

  [Install]
  WantedBy=multi-user.target
  ```

  **Bước 7. `robot/tests/test_robot.py`: hai chỉnh sửa.**

  (a) Thay phần import ở đầu file:
  ```python
  # old
  import struct
  import threading
  import time
  from types import SimpleNamespace

  import pytest

  from robot_agent import drive, hardware
  # new
  import asyncio
  import json
  import struct
  import threading
  import time
  from types import SimpleNamespace

  import pytest
  from websockets.asyncio.client import connect
  from websockets.exceptions import InvalidStatus

  from robot_agent import __main__ as agent
  from robot_agent import config, drive, hardware, server, sim
  ```

  (b) Thêm đoạn sau vào cuối file (sau hai dòng trống; mọi test cũ giữ nguyên, kể cả `FakeDriveSource`, `T0`, `MS` đã có). Đoạn đầu (`TimedSource` và `test_retry_backoff_is_waited_after_write_error`) là test còn thiếu từ review T03: sau lỗi ghi, lần thử kế phải chờ đúng `retry_s`.

  ```python
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
  ```

  **Bước 8. Kiểm tra (chạy từ `/home/vth/ws/mecanum_base`, báo output nguyên văn từng lệnh).**
  1. `.venv/bin/pytest -v` -> mong đợi `73 passed`, 0 failed, 0 error, không có warning (44 test robot cũ + 28 test mới ở `robot/tests/test_robot.py` + 1 ở `app/server/tests/test_server.py`), tổng dưới 5 giây. Nếu tổng khác 73 nhưng không có fail, báo số thực tế và không sửa. Nếu có fail do code trong Work order, trả `BLOCKED` kèm tên test và lỗi, không tự sửa thiết kế.
  2. Chạy lại 5 lần: `for i in 1 2 3 4 5; do .venv/bin/pytest robot/tests -p no:cacheprovider 2>&1 | tail -1; done` -> cả 5 dòng là `72 passed in ...s`.
  3. `grep -nE "time\.sleep" robot/tests/test_robot.py` -> không có dòng nào (exit 1).
  4. `grep -rnE "1\.89|TaskGroup|tomllib|except\*|asyncio\.timeout|AstraSSource|Astra" robot/robot_agent/config.py robot/robot_agent/sim.py robot/robot_agent/server.py robot/robot_agent/__main__.py` -> không có dòng nào (exit 1).
  5. `.venv/bin/python -c "import robot_agent.sim, robot_agent.config; import sys; print('serial' in sys.modules)"` -> in `False` (sim/config không kéo thư viện phần cứng).
  6. Token rỗng bị từ chối: `ROBOT_LINK_TOKEN= ROBOT_SIMULATE=true timeout 10 .venv/bin/python -m robot_agent; echo "rc=$?"` -> in `robot_agent: ROBOT_LINK_TOKEN is empty: refusing to start without a link token` rồi `rc=2`. (Chỉ đúng khi repo chưa có file `.env` chứa token; nếu có `.env` với token mà biến môi trường rỗng vẫn thắng nên kết quả không đổi.)
  7. Chạy thật ở chế độ mô phỏng, chứng minh client nhận `state` và thoát sạch khi SIGTERM (lệnh dưới được giới hạn bằng `timeout -s KILL 30`). Chạy nguyên khối này bằng `bash`:
  ```bash
  set -u
  PY=.venv/bin/python
  PORT=$($PY -c "import socket;s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1])")
  LOG=$(mktemp)
  ROBOT_SIMULATE=true ROBOT_LINK_TOKEN=test ROBOT_BIND_HOST=127.0.0.1 ROBOT_BIND_PORT=$PORT \
    timeout -s KILL 30 $PY -m robot_agent >"$LOG" 2>&1 &
  PID=$!
  $PY - "$PORT" <<'PYEOF'
  import asyncio, json, sys, time
  from websockets.asyncio.client import connect

  async def main(port):
      deadline = time.monotonic() + 10
      while True:
          try:
              ws = await connect(f"ws://127.0.0.1:{port}/ws", additional_headers={"Authorization": "Bearer test"})
              break
          except OSError:
              if time.monotonic() > deadline:
                  raise SystemExit("FAIL: server never came up")
              await asyncio.sleep(0.1)
      async with ws:
          state = json.loads(await asyncio.wait_for(ws.recv(), 3))
          assert state["t"] == "state", state
          for _ in range(100):
              state = json.loads(await asyncio.wait_for(ws.recv(), 3))
              if state["health"]["stm"]["ok"] and state["health"]["lidar"]["ok"]:
                  break
          else:
              raise SystemExit("FAIL: devices never became ok")
          print("OK state", sorted(state), state["health"])

  asyncio.run(main(int(sys.argv[1])))
  PYEOF
  CLIENT=$?
  kill -TERM $PID
  wait $PID
  RC=$?
  echo "client_exit=$CLIENT agent_exit=$RC"
  cat "$LOG"
  rm -f "$LOG"
  ```
  Mong đợi: một dòng `OK state ['charge', 'flag_stop', 'health', 'imu', 'last_cmd_seq', 't', 't_mono_ns', 'vel', 'voltage'] {...}` với `stm` và `lidar` đều `'ok': True`; `client_exit=0 agent_exit=0`; log có `listening on 127.0.0.1:<port>`, `shutting down`, `server closed`, và không có `Traceback` hay `final zero velocity could not be written`. (Dòng `writer ... 'healthy': False, 'error_count': 1` thoáng qua ngay sau khởi động là bình thường.) Nếu `agent_exit` khác 0 hoặc có `Traceback`, trả `BLOCKED` kèm log.
  8. `grep -c "" deploy/robot-agent.service && grep -nE "^(Restart|ExecStart|EnvironmentFile|WorkingDirectory)=" deploy/robot-agent.service` -> thấy `Restart=on-failure`, `ExecStart=/opt/mecanum_base/.venv/bin/python -m robot_agent`, `EnvironmentFile=/opt/mecanum_base/.env`, `WorkingDirectory=/opt/mecanum_base`.
  9. `git status --short` (chỉ đọc) -> chỉ có: ` M pyproject.toml`, ` M robot/tests/test_robot.py`, `?? deploy/`, `?? robot/robot_agent/__main__.py`, `?? robot/robot_agent/config.py`, `?? robot/robot_agent/server.py`, `?? robot/robot_agent/sim.py` (cộng ` M .claude/task/task.md` nếu Opus chưa commit nó). File nào khác xuất hiện thì báo.

  **Trả về:** danh sách file đã tạo/sửa, output nguyên văn của 9 lệnh, mọi điểm bạn phải dừng. Không commit.

  **Mâu thuẫn/điểm mở cho Opus (Sonnet nêu, Haiku không xử lý):**
  1. Ba tài liệu không mâu thuẫn nhau về T04. Điểm cần chú ý: PROTO-2 chỉ nêu `t_mono_ns` và `last_cmd_seq` cho state lên; Work order chốt các tên trường còn lại theo PROTO-1 (xem "Quyết định thiết kế"). T06 phải đọc đúng các tên này; nếu muốn tên khác thì sửa spec PROTO-2 trước.
  2. `t_mono_ns` là thời điểm mẫu STM32 (để odometry PHY-7 tích phân đúng), không phải lúc gửi; khi telemetry đứng thì `t_mono_ns` đứng theo. Nếu T06/T14 cần đo độ trễ vòng lệnh bằng thời điểm gửi thì phải thêm trường riêng.
  3. `cmd_vel` xuống robot được kiểm tra chặt: đúng 5 khóa. Message có thêm `src` (PROTO-1 dành cho web) sẽ bị bỏ; T06 phải bỏ `src` khi chuyển tiếp xuống robot.
  4. `last_cmd_seq` chỉ cập nhật khi writer chấp nhận lệnh (không phải khi lệnh bị loại do SAF-04); NFR-02 đo độ trễ vòng lệnh dựa vào đó.
  5. Đường dẫn cài trên Jetson chưa biết: `deploy/robot-agent.service` dùng `/opt/mecanum_base` (đã ghi chú trong file, xác nhận ở T15; `User=` đang để chú thích `CHANGE_ME`). `RestartPreventExitStatus=2` ngăn vòng lặp khởi động lại khi cấu hình sai token.
  6. Ngoài danh sách yêu cầu: `ROBOT_BIND_HOST` không đặt thì mặc định `127.0.0.1` và địa chỉ đại diện bị từ chối; tin nhắn > 1024 byte làm đóng kết nối (mã 1009); ping 2 s/timeout 2 s để phát hiện peer chết.
  7. Writer có thể báo `healthy: False`/1 lỗi trong khoảng 0.2 s đầu vì STM32 chưa chạy khi writer ghi lần đầu; tự hết sau lần thử lại. Đó là hành vi mong muốn (writer độc lập với thiết bị).
  8. `AstraSSource` vẫn nằm trong `hardware.py` nhưng không được import hay khởi động ở đâu trong T04 (D-07).
  9. Test dùng `from robot_agent import __main__ as agent`: import module `__main__` của gói không chạy `main()` (có bảo vệ `__name__`).

## P2 — App server

### T05 — Lõi điều khiển
- Trạng thái: MERGED · Plan: P2 · Phụ thuộc: T01
- Spec: FR-03, SAF-01, SAF-02, SAF-04, SAF-07, PROTO-1
- File: `app/server/app_server/{config,control}.py`, `app/server/tests/test_server.py`
- Đạt khi: test bao phủ disarm mặc định, chia hệ số cả ba thành phần ở một hàm, không kẹp tốc độ, loại giá trị không hữu hạn, chỉ một operator, sai token chỉ được xem, Origin không hợp lệ bị từ chối.
- Work order:

  **Quy tắc cao nhất, theo thứ tự:** chỉ sửa đúng 3 file liệt kê dưới đây. Thiếu thông tin hoặc có mâu thuẫn thì dừng và trả `BLOCKED` kèm câu hỏi. Không chạy `git commit` (và không chạy lệnh git nào làm thay đổi repo). Không thiết kế thêm: chép nguyên văn nội dung file.

  File được sửa (thư mục làm việc là gốc worktree):
  1. `app/server/app_server/config.py` (tạo mới)
  2. `app/server/app_server/control.py` (tạo mới)
  3. `app/server/tests/test_server.py` (thay toàn bộ nội dung)

  Không sửa `pyproject.toml`, `.env.example`, `__init__.py`. `python-dotenv` đã có trong venv.

  Thiết kế (đã chốt, không đổi): `CMD_VEL_DIVISOR = 1.89` và hàm `to_wire_units` là nơi duy nhất chia hệ số; không có giới hạn hay kẹp tốc độ; hệ số không đọc từ env; token rỗng thì `load_settings` ném `ConfigError`; phiên bắt đầu ở disarm; một driver tại một thời điểm (hello thứ hai bị từ chối), viewer chỉ xem; so token bằng `hmac.compare_digest`; `handle_cmd_vel` ném `ValueError` khi dữ liệu sai, trả `None` khi không chuyển tiếp, và trả dict chỉ có `seq, vx, vy, wz` theo đơn vị wire; `watchdog_tripped()` trả `True` đúng một lần sau 250 ms (đồng hồ monotonic, tiêm được); `snapshot()` chỉ chứa đơn vị web. Quy ước cho T06: `arm(..., False)` được chấp nhận, `disconnect()` trả `True`, `watchdog_tripped()` trả `True` đều nghĩa là T06 phải gửi `cmd_vel` 0 xuống robot.

  Các khối code dưới đây thụt vào 2 dấu cách vì nằm trong danh sách Markdown: **bỏ đúng 2 dấu cách đầu mỗi dòng** khi ghi ra file (file Python bắt đầu ở cột 0).

  **File 1: `app/server/app_server/config.py`** (chép nguyên văn)

  ```python
  """App server settings, read once from the environment (and `.env` at the repo root)."""

  from __future__ import annotations

  import os
  from dataclasses import dataclass
  from pathlib import Path
  from typing import Mapping, Optional, Tuple

  from dotenv import load_dotenv

  REPO_ROOT = Path(__file__).resolve().parents[3]


  class ConfigError(ValueError):
      """Raised when the settings are unusable; the server must not start."""


  @dataclass(frozen=True)
  class Settings:
      robot_ws_url: str
      robot_link_token: str
      operator_token: str
      bind_host: str
      bind_port: int
      allowed_origins: Tuple[str, ...]


  def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
      """Build Settings. With env=None, load `.env` (without overriding) and use os.environ."""
      if env is None:
          load_dotenv(REPO_ROOT / ".env", override=False)
          env = os.environ

      robot_link_token = env.get("ROBOT_LINK_TOKEN", "").strip()
      operator_token = env.get("OPERATOR_TOKEN", "").strip()
      if not robot_link_token:
          raise ConfigError("ROBOT_LINK_TOKEN must not be empty")
      if not operator_token:
          raise ConfigError("OPERATOR_TOKEN must not be empty")

      try:
          bind_port = int(env.get("APP_BIND_PORT", "8000"))
      except ValueError as exc:
          raise ConfigError("APP_BIND_PORT must be an integer") from exc
      if not 1 <= bind_port <= 65535:
          raise ConfigError("APP_BIND_PORT must be in 1..65535")

      origins = tuple(
          o.strip()
          for o in env.get("APP_ALLOWED_ORIGINS", "http://100.119.83.63:3000").split(",")
          if o.strip()
      )
      return Settings(
          robot_ws_url=env.get("ROBOT_WS_URL", "ws://100.69.39.18:8765/ws").strip(),
          robot_link_token=robot_link_token,
          operator_token=operator_token,
          bind_host=env.get("APP_BIND_HOST", "100.119.83.63").strip(),
          bind_port=bind_port,
          allowed_origins=origins,
      )
  ```

  **File 2: `app/server/app_server/control.py`** (chép nguyên văn)

  ```python
  """Control core: arm state, driving rights, cmd_vel validation, 1.89 division, watchdog.

  The ONLY place the 1.89 factor is applied to commands is `to_wire_units` (SAF-01).
  No speed limit or clamp exists here (SAF-04).
  """

  from __future__ import annotations

  import hmac
  import math
  import time
  from typing import Any, Callable, Dict, Iterable, Optional, Tuple

  # Telemetry (T06) imports this same constant to multiply velocities back.
  CMD_VEL_DIVISOR = 1.89
  WATCHDOG_S = 0.25

  Vec3 = Tuple[float, float, float]


  def to_wire_units(vx: float, vy: float, wz: float) -> Vec3:
      """Web units -> wire units. The single place that divides by CMD_VEL_DIVISOR."""
      return (vx / CMD_VEL_DIVISOR, vy / CMD_VEL_DIVISOR, wz / CMD_VEL_DIVISOR)


  def token_matches(supplied: Any, expected: str) -> bool:
      """Constant-time token compare. Empty expected or non-str supplied never matches."""
      if not isinstance(supplied, str) or not expected:
          return False
      return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


  def origin_allowed(origin: Any, allowed: Iterable[str]) -> bool:
      """Exact match of the Origin header against the allow-list."""
      return isinstance(origin, str) and origin in tuple(allowed)


  def _finite_number(value: Any) -> bool:
      return (
          isinstance(value, (int, float))
          and not isinstance(value, bool)
          and math.isfinite(value)
      )


  def validate_cmd_vel(msg: Any) -> Tuple[int, float, float, float]:
      """Return (seq, vx, vy, wz) from a cmd_vel message or raise ValueError."""
      if not isinstance(msg, dict):
          raise ValueError("cmd_vel must be an object")
      seq = msg.get("seq")
      if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
          raise ValueError("seq must be a non-negative integer")
      for key in ("vx", "vy", "wz"):
          if not _finite_number(msg.get(key)):
              raise ValueError(f"{key} must be a finite number")
      return seq, float(msg["vx"]), float(msg["vy"]), float(msg["wz"])


  class ControlSession:
      """Arm state, single driving operator, last accepted command and watchdog.

      Return conventions for T06:
      - methods returning bool: True means accepted.
      - `arm(..., False)` accepted, `disconnect(...)` returning True, and `watchdog_tripped()`
        returning True all mean T06 must send a zero cmd_vel to the robot.
      """

      def __init__(
          self,
          operator_token: str,
          allowed_origins: Iterable[str],
          clock: Callable[[], float] = time.monotonic,
      ) -> None:
          self._token = operator_token
          self._origins = tuple(allowed_origins)
          self._clock = clock
          self._armed = False  # SAF-02
          self._clients: set = set()
          self._driver: Optional[str] = None
          self._last_cmd_at: Optional[float] = None
          self._cmd_web: Vec3 = (0.0, 0.0, 0.0)
          self._last_seq: Optional[int] = None

      @property
      def armed(self) -> bool:
          return self._armed

      @property
      def driver(self) -> Optional[str]:
          return self._driver

      def connect(self, client_id: str, origin: Any) -> bool:
          """Register a client as a viewer; False (not registered) if the Origin is rejected."""
          if not origin_allowed(origin, self._origins):
              return False
          self._clients.add(client_id)
          return True

      def role(self, client_id: str) -> Optional[str]:
          if client_id not in self._clients:
              return None
          return "driver" if client_id == self._driver else "viewer"

      def hello(self, client_id: str, token: Any) -> bool:
          """Claim driving rights. False on bad token, unknown client, or another driver holding."""
          if client_id not in self._clients or not token_matches(token, self._token):
              return False
          if self._driver is not None and self._driver != client_id:
              return False
          self._driver = client_id
          return True

      def disconnect(self, client_id: str) -> bool:
          """Remove a client. If it was the driver: disarm, clear command, return True (emit zero)."""
          self._clients.discard(client_id)
          if client_id != self._driver:
              return False
          self._driver = None
          self._disarm()
          return True

      def arm(self, client_id: str, on: Any) -> bool:
          """Only the driver may arm/disarm. `on` must be a bool."""
          if client_id != self._driver or not isinstance(on, bool):
              return False
          if on:
              self._armed = True
              self._last_cmd_at = None
          else:
              self._disarm()
          return True

      def _disarm(self) -> None:
          self._armed = False
          self._last_cmd_at = None
          self._cmd_web = (0.0, 0.0, 0.0)

      def handle_cmd_vel(self, client_id: str, msg: Any) -> Optional[Dict[str, Any]]:
          """Validate and convert a cmd_vel.

          Raises ValueError if invalid. Returns None when not forwarded (disarmed or not the
          driver). Otherwise returns {"seq","vx","vy","wz"} in wire units (FR-03).
          """
          seq, vx, vy, wz = validate_cmd_vel(msg)
          if not self._armed or client_id != self._driver:
              return None
          self._last_cmd_at = self._clock()
          self._cmd_web = (vx, vy, wz)
          self._last_seq = seq
          wvx, wvy, wwz = to_wire_units(vx, vy, wz)
          return {"seq": seq, "vx": wvx, "vy": wvy, "wz": wwz}

      def watchdog_tripped(self) -> bool:
          """True once when 250 ms passed since the last accepted command (T06 emits zero)."""
          if self._last_cmd_at is None:
              return False
          if self._clock() - self._last_cmd_at < WATCHDOG_S:
              return False
          self._last_cmd_at = None
          self._cmd_web = (0.0, 0.0, 0.0)
          return True

      def snapshot(self) -> Dict[str, Any]:
          """Session part of the state message; web units only, never wire values or the factor."""
          vx, vy, wz = self._cmd_web
          return {
              "armed": self._armed,
              "has_driver": self._driver is not None,
              "cmd": {"vx": vx, "vy": vy, "wz": wz},
              "last_cmd_seq": self._last_seq,
          }
  ```

  **File 3: `app/server/tests/test_server.py`** (chép nguyên văn, thay file cũ)

  ```python
  import math

  import pytest

  from app_server import control
  from app_server.config import ConfigError, load_settings
  from app_server.control import (
      CMD_VEL_DIVISOR,
      ControlSession,
      origin_allowed,
      to_wire_units,
      token_matches,
      validate_cmd_vel,
  )

  ORIGIN = "http://100.119.83.63:3000"


  class FakeClock:
      def __init__(self):
          self.t = 100.0

      def __call__(self):
          return self.t


  def make_session(clock=None):
      return ControlSession("secret", [ORIGIN], clock or FakeClock())


  def driver_session(clock=None):
      s = make_session(clock)
      assert s.connect("a", ORIGIN)
      assert s.hello("a", "secret")
      return s


  def cmd(seq=1, vx=0.0, vy=0.0, wz=0.0):
      return {"type": "cmd_vel", "seq": seq, "vx": vx, "vy": vy, "wz": wz, "src": "kbd"}


  def test_package_imports():
      import app_server

      assert app_server is not None


  # ---- config ----

  BASE_ENV = {"ROBOT_LINK_TOKEN": "link", "OPERATOR_TOKEN": "op"}


  def test_config_defaults_and_frozen():
      s = load_settings(dict(BASE_ENV))
      assert s.robot_ws_url == "ws://100.69.39.18:8765/ws"
      assert s.bind_host == "100.119.83.63"
      assert s.bind_port == 8000
      assert s.allowed_origins == (ORIGIN,)
      with pytest.raises(Exception):
          s.bind_port = 1


  def test_config_parses_origins_and_port():
      env = dict(BASE_ENV, APP_ALLOWED_ORIGINS=" http://a:1 , http://b:2 ,", APP_BIND_PORT="9000")
      s = load_settings(env)
      assert s.allowed_origins == ("http://a:1", "http://b:2")
      assert s.bind_port == 9000


  @pytest.mark.parametrize("missing", ["ROBOT_LINK_TOKEN", "OPERATOR_TOKEN"])
  @pytest.mark.parametrize("value", [None, "", "   "])
  def test_config_empty_token_refuses_to_start(missing, value):
      env = dict(BASE_ENV)
      if value is None:
          del env[missing]
      else:
          env[missing] = value
      with pytest.raises(ConfigError):
          load_settings(env)


  def test_config_bad_port():
      with pytest.raises(ConfigError):
          load_settings(dict(BASE_ENV, APP_BIND_PORT="abc"))


  def test_config_has_no_divisor_setting():
      s = load_settings(dict(BASE_ENV, CMD_VEL_DIVISOR="5"))
      assert not any("divisor" in f.lower() for f in s.__dataclass_fields__)
      assert CMD_VEL_DIVISOR == 1.89


  # ---- disarm by default, arm rights ----

  def test_starts_disarmed():
      s = make_session()
      assert s.armed is False
      assert s.snapshot()["armed"] is False


  def test_disarmed_driver_command_not_forwarded():
      s = driver_session()
      assert s.handle_cmd_vel("a", cmd(vx=1.0)) is None


  def test_arm_then_forward():
      s = driver_session()
      assert s.arm("a", True) is True
      assert s.armed is True
      assert s.handle_cmd_vel("a", cmd(vx=1.0)) is not None


  def test_disarm_stops_forwarding():
      s = driver_session()
      s.arm("a", True)
      assert s.arm("a", False) is True
      assert s.armed is False
      assert s.handle_cmd_vel("a", cmd(vx=1.0)) is None
      assert s.snapshot()["cmd"] == {"vx": 0.0, "vy": 0.0, "wz": 0.0}


  def test_arm_requires_bool_and_driver():
      s = driver_session()
      assert s.arm("a", "yes") is False
      assert s.armed is False
      assert s.connect("v", ORIGIN)
      assert s.arm("v", True) is False
      assert s.armed is False


  # ---- 1.89 division, single function ----

  def test_divisor_constant():
      assert CMD_VEL_DIVISOR == 1.89


  def test_to_wire_units_divides_all_three():
      vx, vy, wz = to_wire_units(1.89, -3.78, 0.189)
      assert vx == pytest.approx(1.0)
      assert vy == pytest.approx(-2.0)
      assert wz == pytest.approx(0.1)


  def test_to_wire_units_known_vector():
      vx, vy, wz = to_wire_units(0.1, 0.1, 0.1)
      for v in (vx, vy, wz):
          assert v == pytest.approx(0.1 / 1.89)
      assert round(vx * 1000) == 53  # 52.91 mm/s


  def test_handle_cmd_vel_output_is_wire_only():
      s = driver_session()
      s.arm("a", True)
      out = s.handle_cmd_vel("a", cmd(seq=7, vx=1.89, vy=3.78, wz=-0.945))
      assert set(out) == {"seq", "vx", "vy", "wz"}
      assert out["seq"] == 7
      assert out["vx"] == pytest.approx(1.0)
      assert out["vy"] == pytest.approx(2.0)
      assert out["wz"] == pytest.approx(-0.5)


  def test_snapshot_web_units_without_factor_or_wire_values():
      s = driver_session()
      s.arm("a", True)
      s.handle_cmd_vel("a", cmd(seq=3, vx=1.89, vy=0.0, wz=0.0))
      snap = s.snapshot()
      assert snap["cmd"] == {"vx": 1.89, "vy": 0.0, "wz": 0.0}
      assert snap["last_cmd_seq"] == 3
      text = repr(snap)
      assert "1.89" in text  # the web-unit value itself
      assert "divisor" not in text.lower()
      assert repr(1.0) not in repr(snap["cmd"])  # wire value is absent


  def test_divisor_only_used_in_to_wire_units():
      import inspect

      src = inspect.getsource(control)
      body = inspect.getsource(control.to_wire_units)
      assert src.count("/ CMD_VEL_DIVISOR") == 3
      assert body.count("/ CMD_VEL_DIVISOR") == 3


  # ---- no clamping (SAF-04) ----

  @pytest.mark.parametrize("big", [5.0, 100.0, -250.0, 1e6])
  def test_no_speed_limit(big):
      s = driver_session()
      s.arm("a", True)
      out = s.handle_cmd_vel("a", cmd(vx=big, vy=-big, wz=big))
      assert out["vx"] == pytest.approx(big / 1.89)
      assert out["vy"] == pytest.approx(-big / 1.89)
      assert out["wz"] == pytest.approx(big / 1.89)
      assert s.snapshot()["cmd"]["vx"] == big


  # ---- validation ----

  @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
  @pytest.mark.parametrize("field", ["vx", "vy", "wz"])
  def test_non_finite_rejected(bad, field):
      s = driver_session()
      s.arm("a", True)
      m = cmd()
      m[field] = bad
      with pytest.raises(ValueError):
          s.handle_cmd_vel("a", m)
      assert s.snapshot()["last_cmd_seq"] is None


  @pytest.mark.parametrize("bad", ["1", None, True, [1], {"a": 1}])
  def test_wrong_types_rejected(bad):
      for field in ("vx", "vy", "wz"):
          m = cmd()
          m[field] = bad
          with pytest.raises(ValueError):
              validate_cmd_vel(m)


  @pytest.mark.parametrize("seq", [None, "1", 1.5, True, -1])
  def test_bad_seq_rejected(seq):
      with pytest.raises(ValueError):
          validate_cmd_vel(cmd(seq=seq))


  def test_missing_field_and_non_dict_rejected():
      with pytest.raises(ValueError):
          validate_cmd_vel({"seq": 1, "vx": 0.0, "vy": 0.0})
      with pytest.raises(ValueError):
          validate_cmd_vel([1, 2, 3])


  def test_int_values_accepted():
      assert validate_cmd_vel(cmd(seq=1, vx=1, vy=0, wz=0)) == (1, 1.0, 0.0, 0.0)


  # ---- single operator, viewers read-only ----

  def test_wrong_token_is_viewer_only():
      s = make_session()
      s.connect("a", ORIGIN)
      assert s.hello("a", "wrong") is False
      assert s.hello("a", None) is False
      assert s.role("a") == "viewer"
      assert s.arm("a", True) is False
      assert s.armed is False


  def test_only_one_driver():
      s = driver_session()
      s.connect("b", ORIGIN)
      assert s.hello("b", "secret") is False
      assert s.role("a") == "driver"
      assert s.role("b") == "viewer"
      s.arm("a", True)
      assert s.handle_cmd_vel("b", cmd(vx=1.0)) is None
      assert s.handle_cmd_vel("a", cmd(vx=1.0)) is not None


  def test_driver_hello_again_ok():
      s = driver_session()
      assert s.hello("a", "secret") is True


  def test_driver_disconnect_disarms_and_signals_zero():
      s = driver_session()
      s.arm("a", True)
      s.handle_cmd_vel("a", cmd(vx=1.0))
      assert s.disconnect("a") is True
      assert s.armed is False
      assert s.driver is None
      assert s.snapshot()["cmd"] == {"vx": 0.0, "vy": 0.0, "wz": 0.0}
      s.connect("b", ORIGIN)
      assert s.hello("b", "secret") is True
      assert s.armed is False  # new driver still starts disarmed


  def test_viewer_disconnect_keeps_state():
      s = driver_session()
      s.arm("a", True)
      s.connect("v", ORIGIN)
      assert s.disconnect("v") is False
      assert s.armed is True
      assert s.role("v") is None


  def test_unknown_client_cannot_hello():
      s = make_session()
      assert s.hello("ghost", "secret") is False


  # ---- token and origin ----

  def test_token_matches():
      assert token_matches("secret", "secret") is True
      assert token_matches("secreT", "secret") is False
      assert token_matches("", "") is False
      assert token_matches(None, "secret") is False
      assert token_matches(123, "secret") is False
      assert token_matches("sécret", "secret") is False


  def test_token_compare_is_constant_time():
      import inspect

      assert "compare_digest" in inspect.getsource(control.token_matches)


  def test_origin_allowed():
      assert origin_allowed(ORIGIN, [ORIGIN]) is True
      assert origin_allowed("http://evil.example", [ORIGIN]) is False
      assert origin_allowed(None, [ORIGIN]) is False
      assert origin_allowed("", [ORIGIN]) is False
      assert origin_allowed(ORIGIN, []) is False


  def test_bad_origin_rejected_on_connect():
      s = make_session()
      assert s.connect("x", "http://evil.example") is False
      assert s.connect("y", None) is False
      assert s.role("x") is None
      assert s.hello("x", "secret") is False


  # ---- watchdog (SAF-03b) ----

  def test_watchdog_trips_at_250ms_once():
      clock = FakeClock()
      s = driver_session(clock)
      s.arm("a", True)
      assert s.watchdog_tripped() is False  # nothing received yet
      s.handle_cmd_vel("a", cmd(vx=1.0))
      clock.t += 0.249
      assert s.watchdog_tripped() is False
      clock.t += 0.001
      assert s.watchdog_tripped() is True
      assert s.watchdog_tripped() is False
      assert s.snapshot()["cmd"] == {"vx": 0.0, "vy": 0.0, "wz": 0.0}
      assert s.armed is True


  def test_watchdog_reset_by_new_command():
      clock = FakeClock()
      s = driver_session(clock)
      s.arm("a", True)
      s.handle_cmd_vel("a", cmd(seq=1, vx=1.0))
      clock.t += 0.2
      s.handle_cmd_vel("a", cmd(seq=2, vx=1.0))
      clock.t += 0.2
      assert s.watchdog_tripped() is False
      clock.t += 0.06
      assert s.watchdog_tripped() is True


  def test_rejected_commands_do_not_feed_watchdog():
      clock = FakeClock()
      s = driver_session(clock)
      s.arm("a", True)
      s.handle_cmd_vel("a", cmd(vx=1.0))
      s.connect("b", ORIGIN)
      clock.t += 0.2
      assert s.handle_cmd_vel("b", cmd(seq=2, vx=1.0)) is None
      with pytest.raises(ValueError):
          s.handle_cmd_vel("a", cmd(seq=3, vx=math.nan))
      clock.t += 0.06
      assert s.watchdog_tripped() is True


  def test_default_clock_is_monotonic():
      import inspect
      import time

      default = inspect.signature(ControlSession.__init__).parameters["clock"].default
      assert default is time.monotonic
  ```

  **Lệnh kiểm tra** (chạy từ gốc worktree):
  1. `/home/vth/ws/mecanum_base/.venv/bin/pytest app/server` — mong đợi `61 passed`, không fail, không error.
  2. `/home/vth/ws/mecanum_base/.venv/bin/pytest` — toàn bộ suite phải qua (không test cũ nào hỏng).
  3. `grep -rn "1.89" app/server/app_server` — chỉ hiện trong `control.py`, không có trong `config.py`.

  Nếu test fail do chép sai thì sửa cho khớp văn bản trên; nếu fail mà văn bản đã chép đúng, trả `BLOCKED` kèm đầu ra lỗi, đừng tự sửa logic.

  **Điểm cho Opus/Sonnet khi đối chứng** (không phải việc của Haiku):
  - SAF-04 nói giá trị vượt phạm vi `int16` bị loại và gửi 0: work order này **không** làm ở app server (chỉ loại không hữu hạn, không kẹp, theo `Đạt khi` của T05). Kiểm tra `int16` thuộc robot (T03). Đây là cách đọc, cần Opus xác nhận.
  - PROTO-1 có trường `src` trong `cmd_vel`: T05 bỏ qua, T06 tự quyết nếu cần.
  - SAF-03b (watchdog, disconnect) không có trong `Đạt khi` của T05 nhưng nằm trong lõi nên được test ở đây; T06 gọi `watchdog_tripped()` định kỳ và phát `cmd_vel` 0.
  - Định tuyến `hello`/`arm`, FastAPI, robot link thuộc T06. `connect()` kiểm Origin và đăng ký viewer; T06 gọi sau khi đọc header Origin.

  **Vòng sửa 1 (từ review của Sonnet, kết quả FAIL)**

  Chỉ sửa `app/server/app_server/control.py` và `app/server/tests/test_server.py`.

  1. Trong `token_matches`, thay dòng cuối `return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))` bằng:
     ```python
     try:
         return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))
     except UnicodeEncodeError:
         return False
     ```
  2. Thay toàn bộ hàm `_finite_number` bằng:
     ```python
     def _finite_number(value: Any) -> bool:
         if not isinstance(value, (int, float)) or isinstance(value, bool):
             return False
         try:
             return math.isfinite(value)
         except OverflowError:
             return False
     ```
  3. Trong `test_token_matches` của `test_server.py`, thêm dòng cuối hàm: `assert token_matches("\ud800", "secret") is False`.
  4. Thêm vào cuối `test_server.py`:
     ```python
     @pytest.mark.parametrize("field", ["vx", "vy", "wz"])
     @pytest.mark.parametrize("huge", [10**330, 10**400])
     def test_validate_cmd_vel_rejects_overflowing_int(field, huge):
         msg = {"seq": 1, "vx": 0.0, "vy": 0.0, "wz": 0.0}
         msg[field] = huge
         with pytest.raises(ValueError):
             validate_cmd_vel(msg)
     ```
  5. Kiểm tra: `/home/vth/ws/mecanum_base/.venv/bin/pytest app/server` phải báo `67 passed`; `/home/vth/ws/mecanum_base/.venv/bin/pytest` phải báo `111 passed`.

### T06 — Link robot, telemetry, WS operator
- Trạng thái: MERGED · Plan: P2 · Phụ thuộc: T04, T05
- Spec: FR-08, FR-12, SAF-01, SAF-02, SAF-03, PROTO-1, PROTO-2, PHY-7, NFR-03
- File: `app/server/app_server/{main,robot_link,telemetry}.py`, `app/server/tests/test_server.py`
- Đạt khi: nối được robot mô phỏng, tự kết nối lại; quá 250 ms không có lệnh hoặc operator rớt thì gửi 0; state tới web ≤ 20 Hz và theo đơn vị web; odometry khớp test vector; không payload nào lộ hệ số.
- Work order:

  **Quy tắc cao nhất, theo thứ tự:** chỉ sửa đúng 4 file liệt kê dưới đây. Thiếu thông tin hoặc có mâu thuẫn thì dừng và trả `BLOCKED` kèm câu hỏi. Không chạy `git commit` (và không chạy lệnh git nào làm thay đổi repo). Không thiết kế thêm: chép nguyên văn nội dung file.

  File được sửa (thư mục làm việc là gốc worktree):
  1. `app/server/app_server/robot_link.py` (tạo mới)
  2. `app/server/app_server/telemetry.py` (tạo mới)
  3. `app/server/app_server/main.py` (tạo mới)
  4. `app/server/tests/test_server.py` (giữ nguyên toàn bộ test cũ, sửa khối import ở đầu file và thêm khối test mới ở cuối file)

  Không sửa `control.py`, `config.py`, `pyproject.toml`, `.env.example`, `__init__.py`. Mọi thư viện cần dùng (`fastapi`, `uvicorn`, `websockets`, `httpx`, `pytest-asyncio`) đã có trong `.venv`.

  Các khối code dưới đây thụt vào 2 dấu cách vì nằm trong danh sách Markdown: **bỏ đúng 2 dấu cách đầu mỗi dòng** khi ghi ra file (file Python bắt đầu ở cột 0). Code đã được Sonnet chạy thử trên bản sao ngoài repo bằng `.venv` của repo: `pytest app/server` báo 116 passed, ổn định qua nhiều lần chạy, kể cả khi CPU bận; đã thử đột biến (bỏ disarm khi mất link, bỏ watchdog) thì test tương ứng FAIL.

  Thiết kế (đã chốt, không đổi):
  - Robot link: một ô lệnh duy nhất (bản mới thay bản cũ), lệnh chỉ gửi khi link đang nối, bị bỏ khi link rớt và không bao giờ phát lại sau khi nối lại (SAF-03). Tin gửi xuống đúng 5 khóa `t, seq, vx, vy, wz` (`src` bị bỏ). Nối lại với back-off 0.2 s, nhân đôi tới tối đa 2 s. Mỗi lần nối được, app gửi ngay một `cmd_vel` 0.
  - Telemetry: chỉ `vel` nhân với `CMD_VEL_DIVISOR` import từ `control.py` (đúng một chỗ nhân trong `telemetry.py`); IMU và các trường khác đi qua nguyên vẹn. Odometry theo PHY-7: tích phân trung điểm bằng `t_mono_ns` của robot, bỏ mẫu đầu, `dt <= 0`, `dt > 0.5 s`, vận tốc không hữu hạn; vẫn ghi nhớ thời gian mẫu bị bỏ để mẫu sau tích phân từ đó. `theta` quấn về `[-pi, pi)`. Không có `1.89`, không có hệ số và không có vận tốc wire trong bất kỳ payload nào tới web; `main.py` và `robot_link.py` không nhắc `CMD_VEL_DIVISOR`.
  - Tin web gắn thẻ ở khóa `t` (như PROTO-2); `type` được chấp nhận làm bí danh. `state` gửi tới mỗi client tối đa 20 Hz qua hộp thư latest-only riêng từng client (client chậm chỉ trễ chính nó, không chặn client khác hay việc nhận lệnh). `state.session.role` là `driver` hoặc `viewer`, riêng từng client.
  - Quyết định mất link robot (SAF-03): app server disarm, `state.link.robot` là `false`, telemetry robot bị xóa (pose giữ nguyên). Khi nối lại vẫn disarm, chỉ gửi 0 cho tới khi operator `arm` lại; `arm(true)` bị bỏ qua khi link robot đang rớt.
  - Bắt buộc từ review T05: `session.disconnect` gọi trong `finally`; `ValueError` từ `handle_cmd_vel` chỉ bỏ tin đó; gửi `cmd_vel` 0 khi `disconnect`, `watchdog_tripped`, hoặc `arm(false)` trả `True`; watchdog chạy mỗi 50 ms. JSON hỏng, tin không phải object, tin quá 4096 ký tự, tin nhị phân đều bị bỏ qua, không làm sập handler. Viewer xem được nhưng `arm`, `cmd_vel`, `odom_reset` của viewer bị bỏ qua. Origin kiểm trước khi `accept` (sai hoặc thiếu: HTTP 403).
  - `last_cmd_seq` trong `state` là của robot (đo độ trễ NFR-02); `cmd` trong `state` lấy từ `session.snapshot()` theo đơn vị web.

  **File 1: `app/server/app_server/robot_link.py`** (chép nguyên văn)

  ```python
  """WebSocket client from the app server down to the robot (PROTO-2).

  Connects to ROBOT_WS_URL with `Authorization: Bearer <token>` and reconnects forever with
  back-off. The only thing sent down is `cmd_vel` with exactly the keys t, seq, vx, vy, wz in
  wire units. Outbound commands are latest-only: one slot, newer replaces older, so no backlog
  can build up (NFR-03). A command is never stored while the link is down or carried across a
  reconnect (SAF-03). Incoming `state` messages are handed to `on_state`; binary frames are
  ignored until T13.
  """

  from __future__ import annotations

  import asyncio
  import json
  import logging
  from typing import Any, Callable, Dict, Optional

  from websockets.asyncio.client import connect

  log = logging.getLogger("app_server.robot_link")

  MAX_MESSAGE_BYTES = 1 << 20


  class RobotLink:
      def __init__(
          self,
          url: str,
          token: str,
          *,
          on_state: Callable[[Dict[str, Any]], None],
          on_connect: Optional[Callable[[], None]] = None,
          on_disconnect: Optional[Callable[[], None]] = None,
          backoff_initial_s: float = 0.2,
          backoff_max_s: float = 2.0,
          ping_interval_s: float = 2.0,
          ping_timeout_s: float = 2.0,
          open_timeout_s: float = 3.0,
      ) -> None:
          self._url = url
          self._headers = {"Authorization": "Bearer " + token}
          self._on_state = on_state
          self._on_connect = on_connect
          self._on_disconnect = on_disconnect
          self._backoff_initial_s = backoff_initial_s
          self._backoff_max_s = backoff_max_s
          self._ping_interval_s = ping_interval_s
          self._ping_timeout_s = ping_timeout_s
          self._open_timeout_s = open_timeout_s
          self._connected = False
          self._ws: Any = None
          self._pending: Optional[str] = None
          self._wake = asyncio.Event()
          self._last_seq = 0

      @property
      def connected(self) -> bool:
          return self._connected

      @property
      def latency_s(self) -> Optional[float]:
          """Round-trip time of the last WebSocket ping, or None when unknown."""
          ws = self._ws
          if ws is None:
              return None
          value = getattr(ws, "latency", 0.0)
          return float(value) if value and value > 0 else None

      def send_cmd_vel(self, seq: int, vx: float, vy: float, wz: float) -> bool:
          """Queue the newest cmd_vel (wire units), replacing any unsent one.

          Returns False and drops the command when the link is down.
          """
          if not self._connected:
              return False
          self._last_seq = seq
          self._pending = json.dumps(
              {"t": "cmd_vel", "seq": seq, "vx": vx, "vy": vy, "wz": wz},
              separators=(",", ":"),
          )
          self._wake.set()
          return True

      def send_zero(self) -> bool:
          """Queue a zero cmd_vel that replaces any unsent command."""
          return self.send_cmd_vel(self._last_seq, 0.0, 0.0, 0.0)

      def _notify(self, callback: Optional[Callable[[], None]]) -> None:
          if callback is None:
              return
          try:
              callback()
          except Exception:
              log.exception("robot link callback failed")

      async def run(self) -> None:
          """Connect, serve until the link drops, back off, repeat. Cancel to stop."""
          delay = self._backoff_initial_s
          while True:
              try:
                  async with connect(
                      self._url,
                      additional_headers=self._headers,
                      compression=None,
                      max_size=MAX_MESSAGE_BYTES,
                      ping_interval=self._ping_interval_s,
                      ping_timeout=self._ping_timeout_s,
                      open_timeout=self._open_timeout_s,
                  ) as ws:
                      delay = self._backoff_initial_s
                      await self._session(ws)
              except asyncio.CancelledError:
                  raise
              except Exception as exc:
                  log.info("robot link: %s: %s", type(exc).__name__, exc)
              await asyncio.sleep(delay)
              delay = min(delay * 2, self._backoff_max_s)

      async def _session(self, ws: Any) -> None:
          self._ws = ws
          self._pending = None
          self._wake.clear()
          self._connected = True
          sender = asyncio.ensure_future(self._send_loop(ws))
          receiver = asyncio.ensure_future(self._receive_loop(ws))
          try:
              self._notify(self._on_connect)
              await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
          finally:
              self._connected = False
              self._ws = None
              self._pending = None
              self._notify(self._on_disconnect)
              sender.cancel()
              receiver.cancel()
              await asyncio.gather(sender, receiver, return_exceptions=True)

      async def _send_loop(self, ws: Any) -> None:
          while True:
              await self._wake.wait()
              self._wake.clear()
              text, self._pending = self._pending, None
              if text is not None:
                  await ws.send(text)

      async def _receive_loop(self, ws: Any) -> None:
          async for message in ws:
              if not isinstance(message, str):
                  continue  # binary scan frames arrive in T13
              try:
                  data = json.loads(message)
              except (ValueError, RecursionError):
                  continue
              if isinstance(data, dict) and data.get("t") == "state":
                  try:
                      self._on_state(data)
                  except Exception:
                      log.exception("robot state handler failed")
  ```

  **File 2: `app/server/app_server/telemetry.py`** (chép nguyên văn)

  ```python
  """Telemetry: scale robot velocity to web units, odometry (PHY-7), build the web `state`.

  SAF-01: only `vel` is multiplied by CMD_VEL_DIVISOR (the same constant control.py divides by).
  IMU and every other field pass through unscaled. Nothing built here carries the factor or a
  wire-unit velocity, so the web only ever sees web units.
  """

  from __future__ import annotations

  import math
  from typing import Any, Dict, Optional

  from .control import CMD_VEL_DIVISOR

  MAX_DT_S = 0.5  # PHY-7: samples further apart than this are not integrated
  _NS_PER_S = 1e9
  _IMU_KEYS = ("ax", "ay", "az", "gx", "gy", "gz")


  def _finite(value: Any) -> bool:
      if isinstance(value, bool) or not isinstance(value, (int, float)):
          return False
      try:
          return math.isfinite(value)
      except OverflowError:
          return False


  def _finite_dict(data: Any, keys: Any) -> Optional[Dict[str, float]]:
      """{key: float} when `data` is a dict with every key a finite number, else None."""
      if not isinstance(data, dict):
          return None
      out: Dict[str, float] = {}
      for key in keys:
          if not _finite(data.get(key)):
              return None
          out[key] = float(data[key])
      return out


  def _wrap_angle(theta: float) -> float:
      return (theta + math.pi) % (2.0 * math.pi) - math.pi


  class Odometry:
      """Pose (x, y, theta) in the odometry frame, integrated with the midpoint heading."""

      def __init__(self) -> None:
          self.x = 0.0
          self.y = 0.0
          self.theta = 0.0
          self._last_t_ns: Optional[int] = None

      def reset(self) -> None:
          self.x = 0.0
          self.y = 0.0
          self.theta = 0.0
          self._last_t_ns = None

      def forget_time(self) -> None:
          """Keep the pose but treat the next sample as the first one."""
          self._last_t_ns = None

      def update(self, t_ns: int, vx: float, vy: float, wz: float) -> bool:
          """Integrate one sample (web units, robot t_mono_ns). True when the pose moved.

          The first sample, dt <= 0, dt > MAX_DT_S and non-finite velocities are skipped; the
          sample time is still remembered so the following sample integrates from it.
          """
          last = self._last_t_ns
          self._last_t_ns = t_ns
          if last is None:
              return False
          dt = (t_ns - last) / _NS_PER_S
          if dt <= 0.0 or dt > MAX_DT_S:
              return False
          if not (_finite(vx) and _finite(vy) and _finite(wz)):
              return False
          mid = self.theta + 0.5 * wz * dt
          cos_mid = math.cos(mid)
          sin_mid = math.sin(mid)
          self.x += (vx * cos_mid - vy * sin_mid) * dt
          self.y += (vx * sin_mid + vy * cos_mid) * dt
          self.theta = _wrap_angle(self.theta + wz * dt)
          return True

      def pose(self) -> Dict[str, float]:
          return {"x": self.x, "y": self.y, "theta": self.theta}


  class Telemetry:
      """Latest robot telemetry in web units plus odometry; builds the PROTO-1 `state`."""

      def __init__(self) -> None:
          self.odometry = Odometry()
          self._clear_robot_fields()

      def _clear_robot_fields(self) -> None:
          self._vel: Optional[Dict[str, float]] = None
          self._imu: Optional[Dict[str, float]] = None
          self._voltage: Optional[float] = None
          self._flag_stop: Any = None
          self._charge: Any = None
          self._health: Any = None
          self._last_cmd_seq: Optional[int] = None

      def clear_robot(self) -> None:
          """The robot link dropped: forget its telemetry (the pose is kept)."""
          self._clear_robot_fields()
          self.odometry.forget_time()

      def reset_odometry(self) -> None:
          self.odometry.reset()

      def on_robot_state(self, msg: Dict[str, Any]) -> None:
          """Take one robot `state` message (PROTO-2)."""
          raw_vel = _finite_dict(msg.get("vel"), ("vx", "vy", "wz"))
          if raw_vel is None:
              self._vel = None
          else:
              self._vel = {key: value * CMD_VEL_DIVISOR for key, value in raw_vel.items()}
          t_ns = msg.get("t_mono_ns")
          if self._vel is not None and isinstance(t_ns, int) and not isinstance(t_ns, bool):
              self.odometry.update(t_ns, self._vel["vx"], self._vel["vy"], self._vel["wz"])
          self._imu = _finite_dict(msg.get("imu"), _IMU_KEYS)
          voltage = msg.get("voltage")
          self._voltage = float(voltage) if _finite(voltage) else None
          self._flag_stop = msg.get("flag_stop")
          charge = msg.get("charge")
          self._charge = charge if isinstance(charge, dict) else None
          health = msg.get("health")
          self._health = health if isinstance(health, dict) else None
          seq = msg.get("last_cmd_seq")
          valid_seq = isinstance(seq, int) and not isinstance(seq, bool)
          self._last_cmd_seq = seq if valid_seq else None

      def build_state(
          self,
          session: Dict[str, Any],
          robot_connected: bool,
          rtt_s: Optional[float] = None,
      ) -> Dict[str, Any]:
          """The web `state` (PROTO-1). `session` is ControlSession.snapshot() (web units)."""
          rtt_ms = round(rtt_s * 1000.0, 1) if rtt_s is not None else None
          return {
              "t": "state",
              "link": {"robot": robot_connected, "rtt_ms": rtt_ms},
              "session": {"armed": session["armed"], "has_driver": session["has_driver"]},
              "vel": dict(self._vel) if self._vel is not None else None,
              "pose": self.odometry.pose(),
              "cmd": dict(session["cmd"]),
              "imu": dict(self._imu) if self._imu is not None else None,
              "voltage": self._voltage,
              "flag_stop": self._flag_stop,
              "charge": self._charge,
              "health": self._health,
              "last_cmd_seq": self._last_cmd_seq,
          }
  ```

  **File 3: `app/server/app_server/main.py`** (chép nguyên văn)

  ```python
  """App server: FastAPI app with the operator WebSocket (PROTO-1) and a health endpoint.

  Wires ControlSession (arm, driving rights, unit conversion), RobotLink (WS client down to the
  robot) and Telemetry (scaling, odometry, state). State goes to each web client at most
  STATE_HZ times per second through a latest-only per-client mailbox, so a slow client only
  ever lags itself (NFR-03). Run with `python -m app_server.main`.
  """

  from __future__ import annotations

  import asyncio
  import json
  import logging
  import time
  import uuid
  from contextlib import asynccontextmanager
  from types import SimpleNamespace
  from typing import Any, Callable, Dict, Mapping, Optional

  import uvicorn
  from fastapi import FastAPI, WebSocket

  from .config import Settings, load_settings
  from .control import ControlSession
  from .robot_link import RobotLink
  from .telemetry import Telemetry

  log = logging.getLogger("app_server")

  STATE_HZ = 20.0
  WATCHDOG_TICK_S = 0.05
  MAX_MESSAGE_CHARS = 4096
  WS_MAX_SIZE_BYTES = 65536


  class Client:
      """One connected web client with a latest-only outbox and its own sender task."""

      def __init__(self, client_id: str, ws: Any) -> None:
          self.client_id = client_id
          self._ws = ws
          self._latest: Optional[str] = None
          self._event = asyncio.Event()
          self._task = asyncio.ensure_future(self._run())

      def offer(self, text: str) -> None:
          """Replace the unsent state with `text`. Never blocks."""
          self._latest = text
          self._event.set()

      def close(self) -> None:
          self._task.cancel()

      async def _run(self) -> None:
          try:
              while True:
                  await self._event.wait()
                  self._event.clear()
                  text, self._latest = self._latest, None
                  if text is not None:
                      await self._ws.send_text(text)
          except asyncio.CancelledError:
              raise
          except Exception:
              return  # the peer is gone; the receive loop ends the connection


  class Hub:
      """The set of web clients; publishing never waits for any of them."""

      def __init__(self) -> None:
          self._clients: Dict[str, Client] = {}

      def __len__(self) -> int:
          return len(self._clients)

      def add(self, client_id: str, ws: Any) -> Client:
          client = Client(client_id, ws)
          self._clients[client_id] = client
          return client

      def remove(self, client_id: str) -> None:
          client = self._clients.pop(client_id, None)
          if client is not None:
              client.close()

      def publish(self, state: Dict[str, Any], role_of: Callable[[str], Optional[str]]) -> None:
          """Offer `state` to every client, adding that client's own role under `session`."""
          for client in list(self._clients.values()):
              payload = dict(state)
              payload["session"] = dict(state["session"], role=role_of(client.client_id))
              client.offer(json.dumps(payload, separators=(",", ":")))


  def create_app(
      settings: Settings,
      *,
      clock: Callable[[], float] = time.monotonic,
      state_hz: float = STATE_HZ,
      watchdog_tick_s: float = WATCHDOG_TICK_S,
      backoff_initial_s: float = 0.2,
      backoff_max_s: float = 2.0,
  ) -> FastAPI:
      session = ControlSession(settings.operator_token, settings.allowed_origins, clock)
      telemetry = Telemetry()
      hub = Hub()

      def on_link_up() -> None:
          link.send_zero()  # a fresh link always starts at zero, whatever happened before

      def on_link_down() -> None:
          telemetry.clear_robot()
          if session.armed and session.driver is not None:
              session.arm(session.driver, False)  # SAF-03: stay disarmed until re-armed

      link = RobotLink(
          settings.robot_ws_url,
          settings.robot_link_token,
          on_state=telemetry.on_robot_state,
          on_connect=on_link_up,
          on_disconnect=on_link_down,
          backoff_initial_s=backoff_initial_s,
          backoff_max_s=backoff_max_s,
      )

      def build_state() -> Dict[str, Any]:
          return telemetry.build_state(session.snapshot(), link.connected, link.latency_s)

      async def broadcast_loop() -> None:
          loop = asyncio.get_running_loop()
          period = 1.0 / state_hz
          due = loop.time()
          while True:
              hub.publish(build_state(), session.role)
              due += period
              now = loop.time()
              if due < now:
                  due = now  # fell behind: skip ahead, never burst above the rate limit
              await asyncio.sleep(due - now)

      async def watchdog_loop() -> None:
          while True:
              if session.watchdog_tripped():
                  link.send_zero()
              await asyncio.sleep(watchdog_tick_s)

      def handle_text(client_id: str, text: str) -> None:
          if len(text) > MAX_MESSAGE_CHARS:
              return
          try:
              msg = json.loads(text)
          except (ValueError, RecursionError):
              return
          if not isinstance(msg, dict):
              return
          kind = msg.get("t", msg.get("type"))
          if kind == "hello":
              session.hello(client_id, msg.get("token"))
          elif kind == "cmd_vel":
              try:
                  wire = session.handle_cmd_vel(client_id, msg)
              except ValueError:
                  return  # drop only this message
              if wire is not None:
                  link.send_cmd_vel(wire["seq"], wire["vx"], wire["vy"], wire["wz"])
          elif kind == "arm":
              on = msg.get("on")
              if on is True and not link.connected:
                  return  # no arming without a robot link
              if session.arm(client_id, on) and on is False:
                  link.send_zero()
          elif kind == "odom_reset":
              if session.role(client_id) == "driver":
                  telemetry.reset_odometry()

      @asynccontextmanager
      async def lifespan(_app: FastAPI):
          tasks = [
              asyncio.ensure_future(link.run()),
              asyncio.ensure_future(broadcast_loop()),
              asyncio.ensure_future(watchdog_loop()),
          ]
          try:
              yield
          finally:
              for task in tasks:
                  task.cancel()
              await asyncio.gather(*tasks, return_exceptions=True)

      app = FastAPI(lifespan=lifespan)
      app.state.runtime = SimpleNamespace(session=session, link=link, telemetry=telemetry, hub=hub)

      @app.get("/health")
      async def health() -> Dict[str, Any]:
          return {"ok": True, "robot_link": link.connected, "clients": len(hub)}

      @app.websocket("/ws/operator")
      async def operator(ws: WebSocket) -> None:
          client_id = uuid.uuid4().hex
          if not session.connect(client_id, ws.headers.get("origin")):
              await ws.close(code=1008)  # refused before accept
              return
          try:
              await ws.accept()
              hub.add(client_id, ws)
              while True:
                  message = await ws.receive()
                  if message["type"] == "websocket.disconnect":
                      break
                  text = message.get("text")
                  if text is not None:
                      handle_text(client_id, text)
          finally:
              hub.remove(client_id)
              if session.disconnect(client_id):
                  link.send_zero()

      return app


  def main(env: Optional[Mapping[str, str]] = None) -> None:
      settings = load_settings(env)
      logging.basicConfig(level=logging.INFO)
      uvicorn.run(
          create_app(settings),
          host=settings.bind_host,
          port=settings.bind_port,
          ws_max_size=WS_MAX_SIZE_BYTES,
          log_level="info",
      )


  if __name__ == "__main__":
      main()
  ```

  **File 4: `app/server/tests/test_server.py`** (hai thao tác, không đụng phần giữa)

  Thao tác 4a: thay khối import ở đầu file. Văn bản cũ phải khớp chính xác (15 dòng đầu của file, không thêm không bớt); nếu không khớp thì trả `BLOCKED`.

  Văn bản cũ:

  ```python
  import math

  import pytest

  from app_server import control
  from app_server.config import ConfigError, load_settings
  from app_server.control import (
      CMD_VEL_DIVISOR,
      ControlSession,
      origin_allowed,
      to_wire_units,
      token_matches,
      validate_cmd_vel,
  )
  ```

  Văn bản mới (thay đúng khối trên; sau đó vẫn là một dòng trống rồi `ORIGIN = "http://100.119.83.63:3000"` như cũ):

  ```python
  import asyncio
  import json
  import math
  import time
  from contextlib import asynccontextmanager
  from http import HTTPStatus
  from types import SimpleNamespace

  import httpx
  import pytest
  import uvicorn
  from websockets.asyncio.client import connect
  from websockets.asyncio.server import serve
  from websockets.exceptions import ConnectionClosed, InvalidStatus
  from websockets.protocol import State

  from app_server import control
  from app_server import main as app_main
  from app_server import telemetry as telemetry_module
  from app_server.config import ConfigError, load_settings
  from app_server.control import (
      CMD_VEL_DIVISOR,
      ControlSession,
      origin_allowed,
      to_wire_units,
      token_matches,
      validate_cmd_vel,
  )
  from app_server.main import Hub, create_app
  from app_server.robot_link import RobotLink
  from app_server.telemetry import Odometry, Telemetry
  ```

  Thao tác 4b: thêm vào **cuối file**, sau test cuối cùng hiện có (`test_validate_cmd_vel_rejects_overflowing_int`), đúng khối sau (bắt đầu bằng hai dòng trống rồi dòng chú thích `# ====`). Không dùng `import` mới ở giữa file; mọi import đã nằm ở khối 4a.

  ```python
  # ======================================================================================
  # T06: odometry, telemetry, robot link, operator WebSocket
  # ======================================================================================

  LINK_TOKEN = "link"
  OPERATOR_TOKEN = "secret"
  NS = 1_000_000_000
  STEP_NS = 100_000_000  # 0.1 s
  WIRE_VEL = (0.1234, 0.0567, 0.0891)  # distinctive wire-unit values sent by the fake robot


  def robot_state(t_ns=0, vel=WIRE_VEL, seq=None):
      """A robot `state` message as PROTO-2 describes it (velocities in wire units)."""
      return {
          "t": "state",
          "t_mono_ns": t_ns,
          "last_cmd_seq": seq,
          "vel": None if vel is None else {"vx": vel[0], "vy": vel[1], "wz": vel[2]},
          "imu": {"ax": 0.01, "ay": 0.02, "az": 9.81, "gx": 0.003, "gy": 0.004, "gz": 0.005},
          "voltage": 12.3,
          "flag_stop": 0,
          "charge": None,
          "health": {
              "stm": {"ok": True, "state": "ok", "error": None, "restarts": 0},
              "lidar": {"ok": True, "state": "ok", "error": None, "restarts": 0},
              "writer": {
                  "running": True,
                  "healthy": True,
                  "error_count": 0,
                  "last_error": None,
                  "rejected_count": 0,
              },
          },
      }


  def is_zero(command):
      return command["vx"] == 0 and command["vy"] == 0 and command["wz"] == 0


  async def wait_until(condition, timeout=3.0, step=0.01):
      deadline = time.monotonic() + timeout
      while time.monotonic() < deadline:
          if condition():
              return
          await asyncio.sleep(step)
      raise AssertionError("condition not met in time")


  # ---- odometry (PHY-7) ----


  def test_odometry_first_sample_does_not_move():
      o = Odometry()
      assert o.update(5 * NS, 1.0, 1.0, 1.0) is False
      assert o.pose() == {"x": 0.0, "y": 0.0, "theta": 0.0}


  def test_odometry_straight_ahead():
      o = Odometry()
      o.update(0, 0.0, 0.0, 0.0)
      assert o.update(STEP_NS, 0.5, 0.0, 0.0) is True
      assert o.x == pytest.approx(0.05)
      assert o.y == pytest.approx(0.0)
      assert o.theta == pytest.approx(0.0)


  def test_odometry_sideways_is_body_y():
      o = Odometry()
      o.update(0, 0.0, 0.0, 0.0)
      o.update(STEP_NS, 0.0, 1.0, 0.0)
      assert o.x == pytest.approx(0.0, abs=1e-12)
      assert o.y == pytest.approx(0.1)


  def test_odometry_midpoint_heading():
      o = Odometry()
      o.update(0, 0.0, 0.0, 0.0)
      o.update(STEP_NS, 1.0, 0.0, 2.0)  # rotates 0.2 rad, heading used for motion is 0.1
      assert o.theta == pytest.approx(0.2)
      assert o.x == pytest.approx(0.1 * math.cos(0.1))
      assert o.y == pytest.approx(0.1 * math.sin(0.1))


  def test_odometry_body_to_world_when_rotated():
      o = Odometry()
      o.theta = math.pi / 2
      o.update(0, 0.0, 0.0, 0.0)
      o.update(STEP_NS, 1.0, 0.0, 0.0)  # body x points along world y
      assert o.x == pytest.approx(0.0, abs=1e-12)
      assert o.y == pytest.approx(0.1)
      o.update(2 * STEP_NS, 0.0, 1.0, 0.0)  # body y points along world -x
      assert o.x == pytest.approx(-0.1)
      assert o.y == pytest.approx(0.1)


  def test_odometry_accumulates_steps():
      o = Odometry()
      for i in range(11):
          o.update(i * STEP_NS, 0.5, 0.0, 0.0)
      assert o.x == pytest.approx(0.5)


  @pytest.mark.parametrize("dt_ns", [0, -1_000_000, 500_000_001, 600_000_000, 5 * NS])
  def test_odometry_skips_bad_dt(dt_ns):
      o = Odometry()
      o.update(10 * NS, 0.0, 0.0, 0.0)
      assert o.update(10 * NS + dt_ns, 1.0, 1.0, 1.0) is False
      assert o.pose() == {"x": 0.0, "y": 0.0, "theta": 0.0}


  def test_odometry_dt_of_exactly_half_second_is_integrated():
      o = Odometry()
      o.update(0, 0.0, 0.0, 0.0)
      assert o.update(500_000_000, 1.0, 0.0, 0.0) is True
      assert o.x == pytest.approx(0.5)


  def test_odometry_resumes_after_a_gap_from_the_skipped_sample():
      o = Odometry()
      o.update(0, 1.0, 0.0, 0.0)
      assert o.update(1 * NS, 1.0, 0.0, 0.0) is False  # 1 s gap
      assert o.update(1 * NS + STEP_NS, 1.0, 0.0, 0.0) is True  # dt 0.1 s, not 1.1 s
      assert o.x == pytest.approx(0.1)


  def test_odometry_resyncs_when_the_robot_clock_goes_backwards():
      o = Odometry()
      o.update(10 * NS, 1.0, 0.0, 0.0)
      assert o.update(5 * NS, 1.0, 0.0, 0.0) is False
      assert o.update(5 * NS + STEP_NS, 1.0, 0.0, 0.0) is True
      assert o.x == pytest.approx(0.1)


  @pytest.mark.parametrize("bad", [math.nan, math.inf])
  def test_odometry_skips_non_finite_velocity(bad):
      o = Odometry()
      o.update(0, 0.0, 0.0, 0.0)
      assert o.update(STEP_NS, bad, 0.0, 0.0) is False
      assert o.pose() == {"x": 0.0, "y": 0.0, "theta": 0.0}


  def test_odometry_theta_wraps():
      o = Odometry()
      o.update(0, 0.0, 0.0, 0.0)
      o.update(STEP_NS, 0.0, 0.0, 40.0)  # +4 rad in one step
      assert -math.pi <= o.theta < math.pi
      assert o.theta == pytest.approx(math.atan2(math.sin(4.0), math.cos(4.0)))


  def test_odometry_reset():
      o = Odometry()
      o.update(0, 1.0, 0.0, 1.0)
      o.update(STEP_NS, 1.0, 0.0, 1.0)
      assert o.x != 0.0
      o.reset()
      assert o.pose() == {"x": 0.0, "y": 0.0, "theta": 0.0}
      assert o.update(2 * STEP_NS, 1.0, 0.0, 0.0) is False  # first sample after a reset


  # ---- telemetry: web units, state shape (SAF-01, PROTO-1) ----

  SNAPSHOT = {
      "armed": False,
      "has_driver": False,
      "cmd": {"vx": 0.0, "vy": 0.0, "wz": 0.0},
      "last_cmd_seq": None,
  }


  def test_telemetry_vel_is_multiplied_imu_is_not():
      t = Telemetry()
      t.on_robot_state(robot_state(vel=(0.1, 0.0, 0.0), seq=4))
      state = t.build_state(SNAPSHOT, True)
      assert state["vel"]["vx"] == pytest.approx(0.189)
      assert state["vel"]["vy"] == 0.0
      assert state["imu"] == {"ax": 0.01, "ay": 0.02, "az": 9.81, "gx": 0.003, "gy": 0.004,
                              "gz": 0.005}
      assert state["voltage"] == 12.3
      assert state["flag_stop"] == 0
      assert state["last_cmd_seq"] == 4
      assert state["health"]["writer"]["running"] is True


  def test_telemetry_state_has_exactly_the_proto1_fields():
      state = Telemetry().build_state(SNAPSHOT, False)
      assert set(state) == {"t", "link", "session", "vel", "pose", "cmd", "imu", "voltage",
                            "flag_stop", "charge", "health", "last_cmd_seq"}
      assert state["t"] == "state"
      assert state["link"] == {"robot": False, "rtt_ms": None}
      assert state["session"] == {"armed": False, "has_driver": False}
      assert state["vel"] is None and state["imu"] is None
      assert state["pose"] == {"x": 0.0, "y": 0.0, "theta": 0.0}


  def test_telemetry_rtt_in_milliseconds():
      assert Telemetry().build_state(SNAPSHOT, True, 0.0123)["link"]["rtt_ms"] == 12.3


  def test_telemetry_ignores_malformed_fields():
      t = Telemetry()
      msg = robot_state()
      msg["vel"] = {"vx": "fast", "vy": 0.0, "wz": 0.0}
      msg["imu"] = {"ax": math.nan, "ay": 0, "az": 0, "gx": 0, "gy": 0, "gz": 0}
      msg["voltage"] = math.inf
      msg["last_cmd_seq"] = True
      t.on_robot_state(msg)
      state = t.build_state(SNAPSHOT, True)
      assert state["vel"] is None and state["imu"] is None
      assert state["voltage"] is None and state["last_cmd_seq"] is None
      json.dumps(state, allow_nan=False)


  def test_telemetry_odometry_uses_scaled_vel_and_robot_time():
      t = Telemetry()
      t.on_robot_state(robot_state(t_ns=0, vel=(0.5, 0.0, 0.0)))
      t.on_robot_state(robot_state(t_ns=STEP_NS, vel=(0.5, 0.0, 0.0)))
      t.on_robot_state(robot_state(t_ns=2 * STEP_NS, vel=(0.5, 0.0, 0.0)))
      assert t.build_state(SNAPSHOT, True)["pose"]["x"] == pytest.approx(0.189)


  def test_telemetry_clear_robot_keeps_pose_and_reset_clears_it():
      t = Telemetry()
      t.on_robot_state(robot_state(t_ns=0, vel=(0.5, 0.0, 0.0)))
      t.on_robot_state(robot_state(t_ns=STEP_NS, vel=(0.5, 0.0, 0.0)))
      t.clear_robot()
      state = t.build_state(SNAPSHOT, False)
      assert state["vel"] is None and state["imu"] is None and state["health"] is None
      assert state["pose"]["x"] == pytest.approx(0.0945)
      t.reset_odometry()
      assert t.build_state(SNAPSHOT, False)["pose"] == {"x": 0.0, "y": 0.0, "theta": 0.0}


  def test_telemetry_uses_the_control_constant_only():
      import inspect

      from app_server import robot_link

      assert telemetry_module.CMD_VEL_DIVISOR is control.CMD_VEL_DIVISOR
      assert inspect.getsource(telemetry_module).count("* CMD_VEL_DIVISOR") == 1
      for module in (telemetry_module, app_main, robot_link):
          source = inspect.getsource(module)
          assert "1.89" not in source
      for module in (app_main, robot_link):
          assert "CMD_VEL_DIVISOR" not in inspect.getsource(module)


  # ---- test doubles: a fake robot WebSocket server and the app under uvicorn ----


  class FakeRobot:
      """A robot WS server that records what the app sends and can push states."""

      def __init__(self, token=LINK_TOKEN):
          self.token = token
          self.received = []
          self.first_messages = []
          self.auth_headers = []
          self.connections = []
          self.attempts = 0
          self.refuse = False  # True: answer every handshake with 503
          self.port = None
          self._server = None

      @property
      def url(self):
          return "ws://127.0.0.1:%d/ws" % self.port

      def _process_request(self, connection, request):
          self.attempts += 1
          header = request.headers.get("Authorization")
          self.auth_headers.append(header)
          if self.refuse:
              return connection.respond(HTTPStatus.SERVICE_UNAVAILABLE, "down\n")
          if header != "Bearer " + self.token:
              return connection.respond(HTTPStatus.UNAUTHORIZED, "unauthorized\n")
          return None

      async def _handler(self, conn):
          self.connections.append(conn)
          first = True
          try:
              async for message in conn:
                  data = json.loads(message)
                  if first:
                      self.first_messages.append(data)
                      first = False
                  self.received.append(data)
          except ConnectionClosed:
              pass

      async def start(self, port=0):
          self._server = await serve(
              self._handler, "127.0.0.1", port, process_request=self._process_request
          )
          self.port = self._server.sockets[0].getsockname()[1]

      async def stop(self):
          if self._server is not None:
              self._server.close()
              await self._server.wait_closed()
              self._server = None

      def live(self):
          return [c for c in self.connections if c.state is State.OPEN]

      async def drop(self):
          for conn in self.live():
              await conn.close()

      async def send_state(self, message):
          live = self.live()
          if live:
              await live[-1].send(json.dumps(message))

      def cmds(self):
          return [m for m in self.received if m.get("t") == "cmd_vel"]


  @pytest.fixture
  async def robot():
      fake = FakeRobot()
      await fake.start()
      yield fake
      await fake.stop()


  @asynccontextmanager
  async def running_app(robot_url, clock=None):
      settings = load_settings(
          {
              "ROBOT_LINK_TOKEN": LINK_TOKEN,
              "OPERATOR_TOKEN": OPERATOR_TOKEN,
              "ROBOT_WS_URL": robot_url,
              "APP_ALLOWED_ORIGINS": ORIGIN,
          }
      )
      app = create_app(
          settings, clock=clock or time.monotonic, backoff_initial_s=0.02, backoff_max_s=0.1
      )
      server = uvicorn.Server(
          uvicorn.Config(
              app,
              host="127.0.0.1",
              port=0,
              log_level="warning",
              lifespan="on",
              timeout_graceful_shutdown=2,
          )
      )
      task = asyncio.ensure_future(server.serve())
      try:
          deadline = time.monotonic() + 5.0
          while not server.started:
              if task.done():
                  task.result()
              if time.monotonic() > deadline:
                  raise AssertionError("app server did not start")
              await asyncio.sleep(0.01)
          port = server.servers[0].sockets[0].getsockname()[1]
          yield SimpleNamespace(
              ws_url="ws://127.0.0.1:%d/ws/operator" % port,
              http_url="http://127.0.0.1:%d" % port,
              runtime=app.state.runtime,
          )
      finally:
          server.should_exit = True
          await asyncio.wait_for(task, 10)


  @asynccontextmanager
  async def operator(app, drive=True, origin=ORIGIN):
      async with connect(app.ws_url, origin=origin) as ws:
          if drive:
              await send(ws, t="hello", token=OPERATOR_TOKEN)
          yield ws


  async def send(ws, **message):
      await ws.send(json.dumps(message))


  async def state_where(ws, predicate, timeout=3.0):
      deadline = time.monotonic() + timeout
      while True:
          remaining = deadline - time.monotonic()
          if remaining <= 0:
              raise AssertionError("no matching state received")
          message = json.loads(await asyncio.wait_for(ws.recv(), remaining))
          if message.get("t") == "state" and predicate(message):
              return message


  async def arm_as_driver(ws, app):
      await wait_until(lambda: app.runtime.link.connected)
      await state_where(ws, lambda s: s["session"]["role"] == "driver" and s["link"]["robot"])
      await send(ws, t="arm", on=True)
      await state_where(ws, lambda s: s["session"]["armed"])


  async def drain_states(ws, seconds):
      """Every state received during the next `seconds`."""
      states = []
      deadline = time.monotonic() + seconds
      while True:
          remaining = deadline - time.monotonic()
          if remaining <= 0:
              return states
          try:
              message = json.loads(await asyncio.wait_for(ws.recv(), remaining))
          except asyncio.TimeoutError:
              return states
          if message.get("t") == "state":
              states.append(message)


  def nonzero(robot):
      return [c for c in robot.cmds() if not is_zero(c)]


  def zeros(robot):
      return [c for c in robot.cmds() if is_zero(c)]


  def numbers_and_keys(value, key=""):
      """Yield (key, number) for every numeric leaf and (key, None) for every dict key."""
      if isinstance(value, dict):
          for k, v in value.items():
              yield k, None
              yield from numbers_and_keys(v, k)
      elif isinstance(value, list):
          for v in value:
              yield from numbers_and_keys(v, key)
      elif isinstance(value, (int, float)) and not isinstance(value, bool):
          yield key, value


  def assert_web_units_only(texts, wire_values):
      """No payload may hold a wire-unit value, the factor, its inverse, or a telling key."""
      forbidden = tuple(wire_values) + (1.89, 1 / 1.89)
      for text in texts:
          assert "1.89" not in text
          for key, number in numbers_and_keys(json.loads(text)):
              assert not any(w in key.lower() for w in ("wire", "divisor", "factor", "scale"))
              if number is not None:
                  assert not any(math.isclose(number, f, rel_tol=1e-6) for f in forbidden)


  # ---- Hub: a slow client must not block the others ----


  class FakeWs:
      def __init__(self, blocked=False):
          self.sent = []
          self.gate = asyncio.Event()
          if not blocked:
              self.gate.set()

      async def send_text(self, text):
          await self.gate.wait()
          self.sent.append(text)


  async def test_slow_client_gets_only_the_latest_and_blocks_nobody():
      hub = Hub()
      fast, slow = FakeWs(), FakeWs(blocked=True)
      hub.add("fast", fast)
      hub.add("slow", slow)
      base = Telemetry().build_state(SNAPSHOT, True)
      for n in range(1, 6):
          hub.publish(dict(base, last_cmd_seq=n), lambda _cid: "viewer")
          await asyncio.sleep(0.01)
      assert [json.loads(t)["last_cmd_seq"] for t in fast.sent] == [1, 2, 3, 4, 5]
      assert slow.sent == []
      slow.gate.set()
      await wait_until(lambda: len(slow.sent) == 2)
      assert [json.loads(t)["last_cmd_seq"] for t in slow.sent] == [1, 5]  # in flight + latest
      hub.remove("fast")
      hub.remove("slow")


  async def test_hub_adds_each_clients_own_role():
      hub = Hub()
      a, b = FakeWs(), FakeWs()
      hub.add("a", a)
      hub.add("b", b)
      hub.publish(Telemetry().build_state(SNAPSHOT, True), {"a": "driver", "b": "viewer"}.get)
      await wait_until(lambda: a.sent and b.sent)
      assert json.loads(a.sent[0])["session"]["role"] == "driver"
      assert json.loads(b.sent[0])["session"]["role"] == "viewer"
      hub.remove("a")
      hub.remove("b")


  # ---- RobotLink ----


  async def test_link_connects_with_bearer_and_sends_exact_keys(robot):
      states = []
      link = RobotLink(robot.url, LINK_TOKEN, on_state=states.append, backoff_initial_s=0.02)
      task = asyncio.ensure_future(link.run())
      try:
          await wait_until(lambda: link.connected)
          assert robot.auth_headers[-1] == "Bearer " + LINK_TOKEN
          assert link.send_cmd_vel(3, 0.1, -0.2, 0.05) is True
          await wait_until(lambda: robot.cmds())
          assert robot.cmds()[0] == {"t": "cmd_vel", "seq": 3, "vx": 0.1, "vy": -0.2, "wz": 0.05}
          await robot.send_state(robot_state(t_ns=7))
          await wait_until(lambda: states)
          assert states[0]["t_mono_ns"] == 7
      finally:
          task.cancel()
          await asyncio.gather(task, return_exceptions=True)


  async def test_link_keeps_only_the_latest_command(robot):
      link = RobotLink(robot.url, LINK_TOKEN, on_state=lambda m: None, backoff_initial_s=0.02)
      task = asyncio.ensure_future(link.run())
      try:
          await wait_until(lambda: link.connected)
          for seq in range(1000):  # no await: the sender cannot run in between
              link.send_cmd_vel(seq, 0.1, 0.0, 0.0)
          await wait_until(lambda: robot.cmds())
          await asyncio.sleep(0.05)
          assert [c["seq"] for c in robot.cmds()] == [999]
          link.send_cmd_vel(1000, 0.1, 0.0, 0.0)
          link.send_zero()  # a zero replaces an unsent command
          await wait_until(lambda: len(robot.cmds()) == 2)
          await asyncio.sleep(0.05)
          assert is_zero(robot.cmds()[1]) and len(robot.cmds()) == 2
      finally:
          task.cancel()
          await asyncio.gather(task, return_exceptions=True)


  async def test_link_reconnects_and_never_replays_an_old_command(robot):
      events = []
      link = RobotLink(
          robot.url,
          LINK_TOKEN,
          on_state=lambda m: None,
          on_connect=lambda: events.append("up"),
          on_disconnect=lambda: events.append("down"),
          backoff_initial_s=0.02,
          backoff_max_s=0.1,
      )
      task = asyncio.ensure_future(link.run())
      try:
          await wait_until(lambda: link.connected)
          await robot.drop()
          await wait_until(lambda: "down" in events)
          assert link.connected is False
          assert link.send_cmd_vel(5, 0.1, 0.0, 0.0) is False  # dropped, not queued
          await wait_until(lambda: link.connected)  # reconnected by itself
          assert events == ["up", "down", "up"]
          await asyncio.sleep(0.1)
          assert robot.cmds() == []  # nothing from before the drop was replayed
      finally:
          task.cancel()
          await asyncio.gather(task, return_exceptions=True)


  async def test_link_retries_while_the_robot_is_unreachable():
      fake = FakeRobot()
      await fake.start()
      port = fake.port
      await fake.stop()
      link = RobotLink(
          "ws://127.0.0.1:%d/ws" % port,
          LINK_TOKEN,
          on_state=lambda m: None,
          backoff_initial_s=0.02,
          backoff_max_s=0.1,
      )
      task = asyncio.ensure_future(link.run())
      try:
          await asyncio.sleep(0.2)
          assert link.connected is False
          await fake.start(port=port)
          await wait_until(lambda: link.connected, timeout=5.0)
      finally:
          task.cancel()
          await asyncio.gather(task, return_exceptions=True)
          await fake.stop()


  async def test_link_with_wrong_token_never_connects():
      fake = FakeRobot(token="other")
      await fake.start()
      link = RobotLink(fake.url, LINK_TOKEN, on_state=lambda m: None, backoff_initial_s=0.02)
      task = asyncio.ensure_future(link.run())
      try:
          await wait_until(lambda: fake.attempts >= 3)  # it keeps retrying
          assert link.connected is False
          assert fake.live() == []
      finally:
          task.cancel()
          await asyncio.gather(task, return_exceptions=True)
          await fake.stop()


  # ---- app server over a real socket ----


  async def test_health_endpoint(robot):
      async with running_app(robot.url) as app:
          await wait_until(lambda: app.runtime.link.connected)
          async with httpx.AsyncClient() as client:
              response = await client.get(app.http_url + "/health")
          assert response.status_code == 200
          body = response.json()
          assert body["ok"] is True and body["robot_link"] is True
          assert_web_units_only([response.text], WIRE_VEL)


  async def test_bad_or_missing_origin_is_refused_before_accept(robot):
      async with running_app(robot.url) as app:
          for origin in ("http://evil.example", None):
              with pytest.raises(InvalidStatus) as info:
                  async with connect(app.ws_url, origin=origin):
                      pass
              assert info.value.response.status_code == 403
          assert len(app.runtime.hub) == 0
          assert app.runtime.session.driver is None


  async def test_web_command_reaches_robot_in_wire_units(robot):
      async with running_app(robot.url) as app:
          async with operator(app) as ws:
              await arm_as_driver(ws, app)
              await send(ws, t="cmd_vel", seq=7, vx=0.189, vy=-0.378, wz=0.0945, src="kbd")
              await wait_until(lambda: nonzero(robot))
              command = nonzero(robot)[0]
              assert set(command) == {"t", "seq", "vx", "vy", "wz"}  # src stripped
              assert command["seq"] == 7
              assert command["vx"] == pytest.approx(0.1)
              assert command["vy"] == pytest.approx(-0.2)
              assert command["wz"] == pytest.approx(0.05)
              state = await state_where(ws, lambda s: s["cmd"]["vx"] != 0.0)
              assert state["cmd"] == {"vx": 0.189, "vy": -0.378, "wz": 0.0945}  # web units


  async def test_state_is_in_web_units_and_passes_last_cmd_seq(robot):
      async with running_app(robot.url) as app:
          async with operator(app, drive=False) as ws:
              await wait_until(lambda: app.runtime.link.connected)
              await robot.send_state(robot_state(t_ns=1, vel=(0.1, 0.05, 0.2), seq=42))
              state = await state_where(ws, lambda s: s["vel"] is not None)
              assert state["vel"]["vx"] == pytest.approx(0.189)
              assert state["vel"]["vy"] == pytest.approx(0.0945)
              assert state["vel"]["wz"] == pytest.approx(0.378)
              assert state["imu"]["az"] == 9.81  # IMU is not scaled
              assert state["last_cmd_seq"] == 42
              assert state["link"]["robot"] is True
              assert state["session"]["role"] == "viewer"
              assert state["pose"] == {"x": 0.0, "y": 0.0, "theta": 0.0}


  async def test_state_rate_is_at_most_20_hz(robot):
      async with running_app(robot.url) as app:
          async with operator(app, drive=False) as ws:
              await wait_until(lambda: app.runtime.link.connected)
              stop = False

              async def flood():
                  t_ns = 0
                  while not stop:
                      await robot.send_state(robot_state(t_ns=t_ns))
                      t_ns += 5_000_000
                      await asyncio.sleep(0.005)

              flooder = asyncio.ensure_future(flood())
              count = 0
              started = time.monotonic()
              try:
                  while time.monotonic() - started < 0.8:
                      await asyncio.wait_for(ws.recv(), 2.0)
                      count += 1
              finally:
                  stop = True
                  await asyncio.gather(flooder, return_exceptions=True)
              elapsed = time.monotonic() - started
              assert 5 <= count <= 20 * elapsed + 2


  async def test_no_wire_values_or_factor_in_any_web_payload(robot):
      async with running_app(robot.url) as app:
          async with operator(app) as ws:
              await arm_as_driver(ws, app)
              await send(ws, t="cmd_vel", seq=1, vx=0.3402, vy=0.0, wz=0.0)  # wire 0.18
              await wait_until(lambda: nonzero(robot))
              for n in range(4):
                  await robot.send_state(robot_state(t_ns=n * STEP_NS, seq=1))
              texts = []
              deadline = time.monotonic() + 0.6
              while time.monotonic() < deadline:
                  try:
                      texts.append(await asyncio.wait_for(ws.recv(), 0.2))
                  except asyncio.TimeoutError:
                      break
              assert len(texts) >= 5
              assert any(json.loads(t)["vel"] is not None for t in texts)
              assert_web_units_only(texts, WIRE_VEL + (0.18,))


  async def test_watchdog_sends_zero_after_250ms_without_commands(robot):
      clock = FakeClock()
      async with running_app(robot.url, clock) as app:
          async with operator(app) as ws:
              await arm_as_driver(ws, app)
              await send(ws, t="cmd_vel", seq=1, vx=0.189, vy=0.0, wz=0.0)
              await wait_until(lambda: nonzero(robot))
              before = len(zeros(robot))
              clock.t += 0.24
              await asyncio.sleep(0.15)  # several watchdog ticks
              assert len(zeros(robot)) == before  # not yet
              clock.t += 0.02
              await wait_until(lambda: len(zeros(robot)) == before + 1)
              await asyncio.sleep(0.15)
              assert len(zeros(robot)) == before + 1  # once, not repeatedly
              state = await state_where(ws, lambda s: s["cmd"]["vx"] == 0.0)
              assert state["session"]["armed"] is True  # the watchdog stops, it does not disarm


  async def test_operator_disconnect_sends_zero_and_disarms(robot):
      async with running_app(robot.url) as app:
          async with operator(app) as ws:
              await arm_as_driver(ws, app)
              await send(ws, t="cmd_vel", seq=1, vx=0.189, vy=0.0, wz=0.0)
              await wait_until(lambda: nonzero(robot))
              before = len(zeros(robot))
          await wait_until(lambda: len(zeros(robot)) > before)
          assert app.runtime.session.armed is False
          assert app.runtime.session.driver is None
          async with operator(app, drive=False) as viewer:
              state = await state_where(viewer, lambda s: True)
              assert state["session"]["armed"] is False
              assert state["session"]["has_driver"] is False


  async def test_disarm_sends_zero(robot):
      async with running_app(robot.url) as app:
          async with operator(app) as ws:
              await arm_as_driver(ws, app)
              before = len(zeros(robot))
              await send(ws, t="arm", on=False)
              await wait_until(lambda: len(zeros(robot)) > before)
              await state_where(ws, lambda s: not s["session"]["armed"])


  async def test_arm_is_refused_while_the_robot_link_is_down():
      fake = FakeRobot()
      await fake.start()
      url = fake.url
      await fake.stop()
      async with running_app(url) as app:
          async with operator(app) as ws:
              await state_where(ws, lambda s: s["session"]["role"] == "driver")
              await send(ws, t="arm", on=True)
              states = await drain_states(ws, 0.2)
              assert len(states) >= 2
              assert all(s["session"]["armed"] is False for s in states)
              assert all(s["link"]["robot"] is False for s in states)


  async def test_link_loss_disarms_and_old_commands_do_not_resume(robot):
      async with running_app(robot.url) as app:
          async with operator(app) as ws:
              await arm_as_driver(ws, app)
              await send(ws, t="cmd_vel", seq=1, vx=0.189, vy=0.0, wz=0.0)
              await wait_until(lambda: nonzero(robot))
              robot.refuse = True  # keep the link down long enough to observe it
              await robot.drop()
              lost = await state_where(ws, lambda s: not s["link"]["robot"])
              assert lost["session"]["armed"] is False
              assert lost["vel"] is None and lost["imu"] is None
              robot.refuse = False
              back = await state_where(ws, lambda s: s["link"]["robot"])
              assert back["session"]["armed"] is False  # reconnected, still disarmed
              await wait_until(lambda: len(robot.first_messages) == 2)
              assert is_zero(robot.first_messages[1])  # the new link starts with zero
              await send(ws, t="cmd_vel", seq=2, vx=0.189, vy=0.0, wz=0.0)
              await asyncio.sleep(0.15)
              assert [c["seq"] for c in nonzero(robot)] == [1]  # seq 2 was not forwarded
              await send(ws, t="arm", on=True)  # explicit re-arm restores control
              await state_where(ws, lambda s: s["session"]["armed"])
              await send(ws, t="cmd_vel", seq=3, vx=0.189, vy=0.0, wz=0.0)
              await wait_until(lambda: [c["seq"] for c in nonzero(robot)] == [1, 3])


  async def test_viewer_may_watch_but_not_command(robot):
      async with running_app(robot.url) as app:
          async with operator(app) as driver, operator(app, drive=False) as viewer:
              await arm_as_driver(driver, app)
              await robot.send_state(robot_state(t_ns=0, vel=(0.5, 0.0, 0.0)))
              await robot.send_state(robot_state(t_ns=STEP_NS, vel=(0.5, 0.0, 0.0)))
              await robot.send_state(robot_state(t_ns=2 * STEP_NS, vel=(0.5, 0.0, 0.0)))
              moved = await state_where(viewer, lambda s: s["pose"]["x"] > 0.18)
              assert moved["pose"]["x"] == pytest.approx(0.189)
              assert moved["session"]["role"] == "viewer"
              await send(viewer, t="hello", token="wrong")
              await send(viewer, t="arm", on=False)
              await send(viewer, t="cmd_vel", seq=9, vx=0.189, vy=0.0, wz=0.0, src="kbd")
              await send(viewer, t="odom_reset")
              states = await drain_states(viewer, 0.2)
              assert len(states) >= 2
              assert all(s["session"]["armed"] for s in states)  # the viewer's arm(false) ignored
              assert all(s["pose"]["x"] == pytest.approx(0.189) for s in states)  # so was reset
              assert nonzero(robot) == []
              await send(driver, t="odom_reset")  # the driver may reset
              await state_where(viewer, lambda s: s["pose"]["x"] == 0.0)


  async def test_second_operator_with_the_right_token_cannot_take_over(robot):
      async with running_app(robot.url) as app:
          async with operator(app) as first, operator(app) as second:
              await state_where(first, lambda s: s["session"]["role"] == "driver")
              await send(second, t="hello", token=OPERATOR_TOKEN)
              states = await drain_states(second, 0.2)
              assert len(states) >= 2
              assert all(s["session"]["role"] == "viewer" for s in states)
              assert app.runtime.session.driver is not None


  async def test_malformed_messages_do_not_break_the_handler(robot):
      async with running_app(robot.url) as app:
          async with operator(app) as ws:
              await arm_as_driver(ws, app)
              junk = [
                  "not json",
                  "[1, 2, 3]",
                  "123",
                  "null",
                  '"hello"',
                  "{}",
                  '{"t": 5}',
                  '{"t": ["cmd_vel"]}',
                  '{"t": "cmd_vel"}',
                  '{"t": "cmd_vel", "seq": 1, "vx": "fast", "vy": 0, "wz": 0}',
                  '{"t": "cmd_vel", "seq": -1, "vx": 0, "vy": 0, "wz": 0}',
                  '{"t": "cmd_vel", "seq": 1, "vx": NaN, "vy": 0, "wz": 0}',
                  '{"t": "arm", "on": "yes"}',
                  '{"t": "hello", "token": 5}',
                  "x" * 5000,
                  "[" * 100000,
              ]
              for text in junk:
                  await ws.send(text)
              await ws.send(b"\x00\x01binary")
              await send(ws, t="cmd_vel", seq=11, vx=0.189, vy=0.0, wz=0.0)  # still works
              await wait_until(lambda: [c["seq"] for c in nonzero(robot)] == [11])
              state = await state_where(ws, lambda s: True)
              assert state["session"]["role"] == "driver" and state["session"]["armed"] is True


  async def test_end_to_end_with_the_real_robot_server_and_simulator(robot):
      from robot_agent.drive import CmdVelWriter
      from robot_agent.server import RobotServer
      from robot_agent.sim import SimulatedStm32

      stm = SimulatedStm32()
      stm.start()
      writer = CmdVelWriter(stm, motion_enabled=True)
      healthy = {"ok": True, "state": "ok", "error": None, "restarts": 0}
      real = RobotServer(
          token=LINK_TOKEN, writer=writer, stm=stm, devices=lambda: {"stm": healthy, "lidar": healthy}
      )
      port = await real.start("127.0.0.1", 0)
      try:
          # A frozen clock keeps the app watchdog quiet, so the command stays in the mailbox.
          async with running_app("ws://127.0.0.1:%d/ws" % port, FakeClock()) as app:
              async with operator(app) as ws:
                  await arm_as_driver(ws, app)
                  await send(ws, t="cmd_vel", seq=5, vx=0.189, vy=0.0, wz=0.0, src="kbd")
                  await wait_until(lambda: real.build_state()["last_cmd_seq"] == 5)
                  assert writer.tick() == (pytest.approx(0.1), 0.0, 0.0)  # wire units at the robot
                  assert stm.last_command[1] == pytest.approx(0.1)
                  state = await state_where(ws, lambda s: s["vel"] and s["vel"]["vx"] > 0.185)
                  assert state["vel"]["vx"] == pytest.approx(0.189, abs=0.005)  # web units again
                  assert state["last_cmd_seq"] == 5
      finally:
          await real.close()
          stm.stop()


  # ---- entry point ----


  def test_main_binds_to_the_configured_host_and_port(monkeypatch):
      captured = {}
      monkeypatch.setattr(app_main.uvicorn, "run", lambda app, **kwargs: captured.update(kwargs))
      env = {
          "ROBOT_LINK_TOKEN": "l",
          "OPERATOR_TOKEN": "o",
          "APP_BIND_HOST": "127.0.0.9",
          "APP_BIND_PORT": "8123",
      }
      app_main.main(env)
      assert captured["host"] == "127.0.0.9"
      assert captured["port"] == 8123


  def test_main_refuses_to_start_without_tokens():
      with pytest.raises(ConfigError):
          app_main.main({"ROBOT_LINK_TOKEN": "", "OPERATOR_TOKEN": "o"})
  ```

  **Kiểm tra (chạy từ gốc worktree, theo thứ tự):**

  1. `/home/vth/ws/mecanum_base/.venv/bin/pytest app/server` phải báo `116 passed`. Chạy thêm 2 lần nữa, cả 2 lần phải `116 passed` (test dùng socket thật nên cần đảm bảo không chập chờn).
  2. `/home/vth/ws/mecanum_base/.venv/bin/pytest` phải báo `188 passed`.
  3. `grep -rn "1\.89" app/server/app_server` chỉ được khớp trong `control.py`.
  4. `grep -rn "CMD_VEL_DIVISOR" app/server/app_server` chỉ được khớp trong `control.py` và `telemetry.py`.
  5. `grep -rn "Co-Authored\|print(" app/server/app_server` không khớp dòng nào.
  6. Nếu có test FAIL hoặc số `passed` khác: không sửa test cho khớp; trả `BLOCKED` kèm tên test và lỗi.

  **Ghi chú cho người đối chứng (không phải việc của Haiku):**

  - spec/plan/task không nêu tên khóa thẻ của tin web (`t` hay `type`). Work order chọn `t` (đồng nhất PROTO-2), nhận `type` làm bí danh; T08 phải gửi `t`. Cần Opus xác nhận.
  - FR-09 ("nguồn lệnh hiện tại") cần `src`, nhưng `ControlSession` không lưu `src` và T06 không được sửa `control.py`; state chưa có trường nguồn lệnh. Việc này để T08/T09 tự quyết hoặc mở lại `control.py`.
  - `state.session` có thêm `role` (riêng từng client) và `state.link` có thêm `rtt_ms` (RTT ping của link robot, cho FR-11); PROTO-1 chỉ liệt kê tên trường cấp trên cùng nên không mâu thuẫn.
  - Cổng `/health` trả `ok`, `robot_link`, `clients`; không có hệ số hay vận tốc.
  - Giao thức tin nhị phân `scan` (T13) chưa xử lý: `robot_link.py` bỏ qua khung nhị phân.
  - Nhánh có `.claude/spec/spec.md` đang sửa chưa commit (git status ` M`) khi viết work order này; không liên quan T06.

## P3 — Nền client

### T07 — Thư viện vật lý
- Trạng thái: MERGED · Plan: P3 · Phụ thuộc: T01
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

  **Vòng sửa 1 (từ review của Sonnet, kết quả FAIL)**

  **QUY TẮC ĐẦU TIÊN: Chỉ sửa đúng 2 file `app/client/src/robot/motion.ts` và `app/client/src/robot/mecanum.test.ts`. Mỗi sửa là thay đúng đoạn `CŨ` bằng đoạn `MỚI`; đoạn `CŨ` phải khớp nguyên văn và duy nhất, nếu không khớp thì trả `BLOCKED`. Không chạy git làm đổi repo. Không thêm hằng số tốc độ cố định nào (SAF-04); giới hạn phanh dưới đây dùng gia tốc của lần chạy. Không nhắc tới hệ số cmd_vel của SAF-01 ở bất kỳ đâu.**

  Lý do: (a) tư thế NaN cho `cmd_vel` NaN và làm hỏng `prevCmd` vĩnh viễn; (b) hai số hạng công thức không có test (`SGN·Mz/LEVER` của `F_d`, dấu `eby` của `trackError`); (c) spec PHY-6 mới thêm giới hạn phanh `|v| ≤ √(2·a·|e|)`, `|wz| ≤ √(2·α·|e_θ|)` để không vọt đích khi tốc độ chạy cao (trước đó vCruise 2 m/s, a 0.5 vọt 2 m).

  **Sửa 1. `motion.ts`, hàm `trackStep`: tư thế không hữu hạn thì hủy.**
  CŨ:
  ```ts
    let reason = abortReason(input);
  ```
  MỚI:
  ```ts
    const poseOk = [input.pose.x, input.pose.y, input.pose.theta].every(Number.isFinite);
    let reason: AbortReason | null = poseOk ? abortReason(input) : "stale";
  ```

  **Sửa 2. `motion.ts`, hàm `trackStep`: giới hạn phanh PHY-6.** Giới hạn tốc độ tịnh tiến thành `min(vCruise, √(2·accelLin·dist))`, giữ hướng vector; giới hạn `|wz|` thành `min(wzCruise, √(2·accelAng·|etheta|))`. Gần đích `√(2·a·dist)` lớn hơn nhiều so với `KP·e` nên luật P vẫn quyết định, không kẹt trước dung sai; giới hạn gia tốc và logic 3 chu kỳ giữ nguyên.
  CŨ:
  ```ts
    const speed = Math.hypot(vx, vy);
    if (speed > p.vCruise) {
      const k = p.vCruise / speed;
      vx *= k;
      vy *= k;
    }
    let wz = KP_ANG * error.etheta;
    if (Math.abs(wz) > p.wzCruise) wz = Math.sign(wz) * p.wzCruise;
  ```
  MỚI:
  ```ts
    // Giới hạn phanh PHY-6: |v| <= sqrt(2*a*|e|), |wz| <= sqrt(2*alpha*|e_theta|).
    const speedMax = Math.min(p.vCruise, Math.sqrt(2 * p.accelLin * error.dist));
    const speed = Math.hypot(vx, vy);
    if (speed > speedMax) {
      const k = speedMax / speed;
      vx *= k;
      vy *= k;
    }
    let wz = KP_ANG * error.etheta;
    const wzMax = Math.min(
      p.wzCruise,
      Math.sqrt(2 * p.accelAng * Math.abs(error.etheta)),
    );
    if (Math.abs(wz) > wzMax) wz = Math.sign(wz) * wzMax;
  ```

  **Sửa 3. `mecanum.test.ts`, hàm `simulate`: đo độ vọt.** Làm 3 thay thế nhỏ.
  3a. CŨ: `  let maxDv = 0;` (một dòng, trong `simulate`). MỚI:
  ```ts
    let maxDv = 0;
    let maxOvershoot = 0;
    let maxOvershootTheta = 0;
  ```
  3b. CŨ: `    maxSpeed = Math.max(maxSpeed, Math.hypot(out.cmd.vx, out.cmd.vy));` MỚI:
  ```ts
      maxOvershoot = Math.max(maxOvershoot, Math.max(0, (pose.x - goal.x) * Math.sign(goal.x - start.x)));
      maxOvershootTheta = Math.max(maxOvershootTheta, Math.max(0, (pose.theta - goal.theta) * Math.sign(goal.theta - start.theta)));
      maxSpeed = Math.max(maxSpeed, Math.hypot(out.cmd.vx, out.cmd.vy));
  ```
  3c. CŨ: `  return { status, pose, steps, maxSpeed, maxDv, state: s };` MỚI:
  ```ts
    return { status, pose, steps, maxSpeed, maxDv, maxOvershoot, maxOvershootTheta, state: s };
  ```

  **Sửa 4. `mecanum.test.ts`: thêm 5 test mới (29 -> 34).** Mỗi test chèn ngay TRƯỚC test có tên ở cột "Chèn trước".

  | Test mới | Chèn trước test |
  |---|---|
  | `mô-men Mz...` | `omega_i = 0 thì lực cản lăn bằng 0` (trong `describe("PHY-5 động lực học")`) |
  | `sai số quay về khung thân...`, `giới hạn phanh: ...`, `giới hạn phanh góc: ...` (đúng thứ tự này) | `xong cần 3 chu kỳ liên tiếp trong dung sai` (trong `describe("PHY-6 bộ bám đích trên mô hình tích phân")`) |
  | `tư thế không hữu hạn...` | `không hủy khi mọi điều kiện ổn` (trong `describe("PHY-6 các điều kiện hủy")`) |

  Test chèn trước `omega_i = 0 thì lực cản lăn bằng 0`:
  ```ts
    it("mô-men Mz: wzDot = 2 -> F_d = (-0.81403, -0.81403, +0.81403, +0.81403)", () => {
      const r = computeDynamics({ ax: 0, ay: 0, wzDot: 2 }, [1, 1, 1, 1]);
      expect(r.Mz).toBeCloseTo(1.0908, 3);
      [-0.81403, -0.81403, 0.81403, 0.81403].forEach((e, i) => expect(r.Fd[i]).toBeCloseTo(e, 4));
    });

  ```
  Ba test chèn trước `xong cần 3 chu kỳ liên tiếp trong dung sai`:
  ```ts
    it("sai số quay về khung thân: theta = pi/2, đích ở +x thế giới -> đi sang phải (vy < 0)", () => {
      const g: Pose = { x: 1, y: 0, theta: Math.PI / 2 };
      const s = createTrack({ x: 0, y: 0, theta: Math.PI / 2 }, g, DEFAULT_RUN_PARAMS);
      const out = trackStep(s, { pose: { x: 0, y: 0, theta: Math.PI / 2 }, dt: 0.05, stateAgeS: 0, armed: true, keyPressed: false });
      expect(out.cmd.vx).toBeCloseTo(0, 9);
      expect(out.cmd.vy).toBeCloseTo(-0.025, 9);
    });

    it("giới hạn phanh: vCruise = 2, accelLin = 0.5, 10 m, vọt đích dưới 0.05 m", () => {
      const params: RunParams = { vCruise: 2, wzCruise: 1, accelLin: 0.5, accelAng: 1.5 };
      const goal: Pose = { x: 10, y: 0, theta: 0 };
      const r = simulate({ x: 0, y: 0, theta: 0 }, goal, params);
      expect(r.status).toEqual({ kind: "done" });
      expect(Math.hypot(goal.x - r.pose.x, goal.y - r.pose.y)).toBeLessThan(0.02);
      expect(r.maxOvershoot).toBeLessThan(0.05);
      expect(r.state.elapsed).toBeLessThan(r.state.timeoutS);
    });

    it("giới hạn phanh góc: wzCruise = 6, accelAng = 1.5, quay 3 rad, vọt dưới 0.05 rad", () => {
      const params: RunParams = { vCruise: 0.2, wzCruise: 6, accelLin: 0.5, accelAng: 1.5 };
      const goal: Pose = { x: 0, y: 0, theta: 3 };
      const r = simulate({ x: 0, y: 0, theta: 0 }, goal, params);
      expect(r.status).toEqual({ kind: "done" });
      expect(Math.abs(goal.theta - r.pose.theta)).toBeLessThan(0.035);
      expect(r.maxOvershootTheta).toBeLessThan(0.05);
    });

  ```
  Test chèn trước `không hủy khi mọi điều kiện ổn`:
  ```ts
    it("tư thế không hữu hạn thì hủy, cmd 0 hữu hạn, không làm hỏng trạng thái", () => {
      const out = trackStep(fresh(), { ...base, pose: { x: NaN, y: 0, theta: 0 } });
      expect(out.status).toEqual({ kind: "aborted", reason: "stale" });
      expect(out.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
      expect(out.state.prevCmd).toEqual({ vx: 0, vy: 0, wz: 0 });
    });

  ```

  **Kiểm tra sau sửa** (trong `app/client`, báo kết quả từng lệnh):
  1. `npm test` — mong đợi `Test Files  1 passed (1)` và `Tests  34 passed (34)`.
  2. `npx eslint src/robot` — không lỗi, không cảnh báo.
  3. `npx tsc --noEmit -p . 2>&1 | grep 'src/robot'` — không in dòng nào.
  4. `grep -rn "1\.89" src; echo "exit=$?"` — chỉ `exit=1`.
  5. `grep -rnE "from \"(react|next)|document\.|window\." src/robot; echo "exit=$?"` — chỉ `exit=1`.
  6. `git -C <worktree> status --short` (chỉ đọc) — chỉ `M` cho `package.json`, `package-lock.json`, `spec.md`, `task.md` và `?? app/client/src/robot/` hoặc các file robot đã commit.

  Dry-run của Sonnet trên bản sao ngoài worktree: 34/34 qua; vọt đích mô phỏng (dt = 0.05) là 0.0099 m (vCruise 2, a 0.5, 10 m) và 0.0139 rad (wzCruise 6, 3 rad); bỏ giới hạn phanh làm 2 test mới fail. Test `Mz` và `khung thân` fail khi đổi `* LEVER` hoặc dấu `eby`.

  **Ghi chú cho T11/T12 (không thuộc vòng sửa này):** (1) với dt điều khiển lớn (0.1 s) độ vọt mô phỏng lên ~0.1 m do giới hạn gia tốc rời rạc; T11 giữ 20 Hz. (2) T12 phải bỏ mẫu vận tốc không hữu hạn hoặc gọi `DynamicsEstimator.reset()`: một mẫu NaN làm bộ lọc hỏng cho tới khi reset.

### T08 — Kết nối, bàn phím toàn cục, khung ứng dụng
- Trạng thái: MERGED · Plan: P3 · Phụ thuộc: T06, T07
- Spec: FR-01, FR-02, FR-03, FR-08, FR-09, SAF-01, SAF-03, SAF-04, PROTO-1, NFR-03, NFR-05
- File: `app/client/src/app/layout.tsx`, `app/client/src/robot/{protocol,control,control.test,store}.ts`, `app/client/src/robot/keyboard.tsx`, `app/client/eslint.config.mjs` (miễn trừ cho mã shadcn sẵn có), `app/client/src/components/robot/app-shell.tsx`, trang tạm cho các route trong FR-01 (T09–T13 thay thế)
- Đạt khi: lái được từ mọi trang trên mô phỏng, nhiều phím cộng vector, gõ trong ô nhập không làm xe chạy, `Esc` luôn dừng, rời tab thì gửi 0, chuyển trang không rớt WS.
- Work order:

  **QUY TẮC ĐẦU TIÊN: Chỉ chạm các file được liệt kê dưới đây. Nếu thiếu thông tin hoặc có mâu thuẫn, dừng lại và trả `BLOCKED` kèm câu hỏi. Không chạy `git commit` (không chạy lệnh git nào làm đổi repo). Không tự thiết kế: chép đúng nội dung file bên dưới.**

  Thư mục làm việc: worktree `/tmp/claude-1000/-home-vth-ws-mecanum-base/76fe0d3b-44a2-4858-8e13-7f99f2566330/scratchpad/wt/T08` (nhánh `feature/T08-client-shell`). Mọi lệnh npm chạy trong `app/client` của worktree này, không phải `/home/vth/ws/mecanum_base`. `app/client/node_modules` đã cài sẵn; không chạy `npm install`, không thêm thư viện (không cài jsdom).

  **Tài liệu Next.js 16 đã đọc (NFR-05)**, trong `app/client/node_modules/next/dist/docs/` và `app/client/AGENTS.md`:
  - `app/client/node_modules/next/dist/docs/01-app/01-getting-started/03-layouts-and-pages.md`: root layout bắt buộc có `<html>`, `<body>`; layout giữ state và không render lại khi chuyển trang; `LayoutProps`, `PageProps` là kiểu toàn cục chỉ có sau `next dev`, `next build` hoặc `next typegen`.
  - `app/client/node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/layout.md`: root layout nhận `children`; kiểu tường minh `{ children: React.ReactNode }` là cách hợp lệ; ghi chú "Types are generated during next dev, next build or next typegen".
  - `app/client/node_modules/next/dist/docs/01-app/03-api-reference/06-cli/next.md` (mục `next typegen`): tsc không thấy `LayoutProps` nếu chưa chạy typegen. Work order này dùng kiểu tường minh nên `tsc` không phụ thuộc file sinh sẵn (xem Quyết định 6).
  - `app/client/node_modules/next/dist/docs/01-app/01-getting-started/04-linking-and-navigating.md` và `app/client/node_modules/next/dist/docs/01-app/03-api-reference/02-components/link.md`: `next/link` chuyển trang phía client, giữ layout dùng chung, tự prefetch; mục "Checking active links" dùng `usePathname()` trong Client Component.
  - `app/client/node_modules/next/dist/docs/01-app/03-api-reference/04-functions/use-pathname.md`: `usePathname` chỉ dùng trong Client Component.
  - `app/client/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md` và `app/client/node_modules/next/dist/docs/01-app/03-api-reference/01-directives/use-client.md`: `"use client"` đặt đầu file, trước import; browser API và hook chỉ ở Client Component; trang và layout mặc định là Server Component.
  - `app/client/node_modules/next/dist/docs/01-app/03-api-reference/05-config/01-next-config-js/cacheComponents.md` và `app/client/node_modules/next/dist/docs/01-app/02-guides/preserving-ui-state.md`: dự án bật `cacheComponents: true`; trang cũ được giữ ẩn bằng `<Activity>` (effect của trang bị dọn khi ẩn). Vì vậy socket, bộ phân xử và listener bàn phím nằm ở layout gốc và store ngoài React, không nằm trong trang.
  - `app/client/node_modules/next/dist/docs/01-app/02-guides/environment-variables.md`: biến `NEXT_PUBLIC_*` được nhúng lúc build và chỉ nhúng khi viết nguyên văn `process.env.NEXT_PUBLIC_TÊN` (không qua biến trung gian). `store.ts` làm đúng như vậy.

  File được chạm (và chỉ các file này), đường dẫn tính từ gốc worktree:
  1. sửa `app/client/eslint.config.mjs` (thay toàn bộ nội dung)
  2. tạo mới `app/client/src/robot/protocol.ts`
  3. tạo mới `app/client/src/robot/control.ts`
  4. tạo mới `app/client/src/robot/store.ts`
  5. tạo mới `app/client/src/robot/keyboard.tsx`
  6. tạo mới `app/client/src/robot/control.test.ts`
  7. tạo mới `app/client/src/components/robot/app-shell.tsx`
  8. thay toàn bộ `app/client/src/app/layout.tsx`
  9. thay toàn bộ `app/client/src/app/page.tsx`
  10. tạo mới `app/client/src/app/kinematics/forward/page.tsx`
  11. tạo mới `app/client/src/app/kinematics/inverse/page.tsx`
  12. tạo mới `app/client/src/app/dynamics/page.tsx`
  13. tạo mới `app/client/src/app/lidar/page.tsx`
  14. tạo mới `app/client/src/app/system/page.tsx`

  Không sửa `package.json`, `package-lock.json`, `next.config.ts`, `tsconfig.json`, `globals.css`, `mecanum.ts`, `motion.ts`, `mecanum.test.ts`, bất kỳ file trong `src/components/ui/` hay `src/hooks/`. Không tạo `vitest.config.*`. Không tạo thêm file nào khác (ví dụ file bao một hàm).

  **Ràng buộc SAF-01 (tuyệt đối).** Hệ số chia của `cmd_vel` và mọi tên gọi cho nó không được xuất hiện ở bất kỳ file client nào, kể cả chú thích và test. Các file dưới đây đã sạch; không thêm chú thích nhắc tới hệ số đó. Bước 3, mục 5 có lệnh `grep` kiểm tra. **SAF-04:** không thêm giới hạn tốc độ nào; ô tốc độ chỉ từ chối giá trị không hữu hạn hoặc không dương.

  **Quyết định đã chốt (không đổi, để Haiku và các task sau biết lý do):**
  1. Giao thức khớp T06 (đối chiếu `main.py`, `telemetry.py` trong work order T06): thẻ tin ở khóa `t`; web gửi `hello{t,token}`, `cmd_vel{t,seq,vx,vy,wz,src}`, `arm{t,on}`, `odom_reset{t}`; server gửi `state` với `link.robot`, `link.rtt_ms`, `session.armed`, `session.has_driver`, `session.role`, `vel`, `pose`, `cmd`, `imu`, `voltage`, `flag_stop`, `charge`, `health`, `last_cmd_seq`. Server không trả lời `hello`: quyền lái biết qua `state.session.role`.
  2. Nguồn lệnh hiện tại (FR-09) tính ở client trong `Arbiter.source`: `keyboard` nếu có phím di chuyển đang giữ, ngược lại nguồn của lần chạy (`forward` hoặc `inverse`), ngược lại `idle`. Server không có trường này.
  3. Phím thắng chạy tự động (`keyDown` hủy lần chạy, `startRun` bị từ chối khi đang giữ phím). Một timer 20 Hz duy nhất trong `store.ts`, chỉ chạy khi có phím giữ, có lần chạy, hoặc còn nợ một lệnh 0; rảnh thì dừng timer và không gửi gì.
  4. SAF-03a: `haltAll` (mất focus cửa sổ, ẩn tab, disarm, đóng socket) nhả mọi phím, hủy lần chạy và gửi `cmd_vel` 0 đúng một lần nếu socket còn mở. `emergencyStop` (`X`, `Esc`, nút) gửi 0 rồi `arm{on:false}`. Nhả phím cuối thì gửi đúng một lệnh 0 ngay. Phím di chuyển bị bỏ qua khi chưa `armed` và chưa là `driver`, nên giữ sẵn phím rồi mới arm không làm xe chạy.
  5. Dấu phím (spec không ghi dấu, theo hệ trục thân x tiến, y trái, wz ngược chiều kim đồng hồ): `W`/`↑` vx+, `S`/`↓` vx-, `A`/`←` vy+ (sang trái), `D`/`→` vy-, `Q` wz+, `E` wz-. Dùng `event.code`, không dùng `event.key`, để đúng khi bật bộ gõ tiếng Việt. `R`, `X` cũng bị bỏ qua khi đang gõ chữ hoặc giữ Ctrl/Meta/Alt (Ctrl+R không được arm). `Esc` luôn dừng.
  6. Lỗi `tsc` "Cannot find name 'LayoutProps'" đến từ kiểu route sinh sẵn. Sửa theo tài liệu: root layout dùng kiểu tường minh `{ children: React.ReactNode }` (layout.md), nên `npx tsc --noEmit -p .` qua kể cả khi chưa có `.next/types`. Cách thay thế trong tài liệu (`npx next typegen && npx tsc --noEmit -p .`) cũng chạy được nhưng không cần.
  7. `npx eslint src` hiện đã lỗi từ trước ở hai file shadcn sinh sẵn (`src/components/ui/carousel.tsx`, `src/hooks/use-mobile.ts`, luật `react-hooks/set-state-in-effect`), không phải do T08. Cách sửa: `eslint.config.mjs` tắt đúng luật đó cho `src/components/ui/**` và `src/hooks/**`; không sửa hai file kia. Đây là chỗ T08 chạm một file ngoài danh sách `File:` của task, cần Opus xác nhận.
  8. Bộ phân xử và logic phím là mã thuần nằm ở `src/robot/control.ts` (không React, DOM, timer, WebSocket) để test không cần jsdom; `store.ts` gắn nó vào socket và timer. `control.ts` và `control.test.ts` không có trong cây thư mục plan.md §3 và dòng `File:` của T08, cần Opus cập nhật.
  9. Địa chỉ WS: `ws://<window.location.hostname>:8000/ws/operator` (`wss` nếu trang là https), ghi đè bằng `NEXT_PUBLIC_APP_WS_URL`. Mã điều khiển giữ trong `sessionStorage` (khóa `mecanum.operatorCode`), mọi truy cập bọc `try/catch`. Kết nối lại: 0.5 s, gấp đôi, tối đa 5 s, về 0.5 s khi nối được.
  10. Dữ liệu tần số cao ngoài React state: `useTelemetry()` hoặc `subscribeTelemetry()` + `getTelemetry()` cho state ~20 Hz; `useShell()` chỉ đổi khi kết nối, arm, quyền lái, mã, nguồn lệnh, tốc độ hay kết thúc lần chạy đổi, nên thanh trạng thái không render lại ở 20 Hz.

  **Hợp đồng store cho T09 tới T13 (hàm xuất của `store.ts` và `control.ts`):**
  - Đọc: `useShell(): ShellSnapshot`, `useTelemetry(): StateMsg | null`, `subscribeTelemetry(listener)`, `getTelemetry()`, `getTelemetryAt()` (`performance.now()` lúc nhận state gần nhất, `-Infinity` nếu chưa có).
  - Gửi: `setArmed(on)`, `resetOdometry()` (gửi `odom_reset`), `emergencyStop()`, `setOperatorCode(code)`, `setSpeed(lin, ang)`.
  - Chạy tự động (T10, T11): `startRun(driver: RunDriver, source: "forward" | "inverse"): boolean` (false nếu chưa là driver đã arm hoặc đang giữ phím) và `cancelRun()`. `RunDriver` có một hàm `step(input: RunInput): { cmd: BodyVel; status: RunStatus }` được gọi mỗi 50 ms; `RunInput` gồm `dt`, `pose`, `stateAgeS`, `armed`, `keyPressed` (tương thích `RunContext` của `motion.ts`). Ví dụ T10: giữ `let run = createWheelRun(wheels, seconds)` và `step(input) { const r = wheelRunStep(run, input, input.dt); run = r.run; return { cmd: r.cmd, status: r.status }; }`. `ShellSnapshot.lastRunEnd` cho biết lần chạy xong hay bị hủy và lý do.

  **Bước 1. Tạo thư mục.** Chạy trong `app/client`:
  `mkdir -p src/components/robot src/app/kinematics/forward src/app/kinematics/inverse src/app/dynamics src/app/lidar src/app/system`
  (`src/robot/` đã có `mecanum.ts`, `motion.ts`, `mecanum.test.ts`; không đụng ba file đó.)

  **Bước 2. Ghi 14 file.** Các khối code dưới đây thụt vào 2 dấu cách vì nằm trong danh sách Markdown: **bỏ đúng 2 dấu cách đầu mỗi dòng** khi ghi ra file (file bắt đầu ở cột 0; dòng trống để trống). Chép nguyên văn từng ký tự, kể cả dấu tiếng Việt. Code đã được Sonnet chạy thử trên bản sao ngoài repo: `tsc`, `eslint`, 74 test, `npm run build` đều qua, và `store.ts` đã thử thật với app server T06 cộng robot mô phỏng (hello, arm, giữ `W`, nhả phím, mất focus, chạy theo `motion.ts`, phím hủy chạy, dừng khẩn, kết nối lại).

  **File 1: `app/client/eslint.config.mjs`**

  ```js
  import { defineConfig, globalIgnores } from "eslint/config";
  import nextVitals from "eslint-config-next/core-web-vitals";
  import nextTs from "eslint-config-next/typescript";

  const eslintConfig = defineConfig([
    ...nextVitals,
    ...nextTs,
    // Override default ignores of eslint-config-next.
    globalIgnores([
      // Default ignores of eslint-config-next:
      ".next/**",
      "out/**",
      "build/**",
      "next-env.d.ts",
    ]),
    // File shadcn sinh sẵn gọi setState trong effect; luật mới của React 19 chặn việc đó.
    {
      files: ["src/components/ui/**", "src/hooks/**"],
      rules: { "react-hooks/set-state-in-effect": "off" },
    },
  ]);

  export default eslintConfig;
  ```

  **File 2: `app/client/src/robot/protocol.ts`**

  ```ts
  // PROTO-1: kiểu tin nhắn web <-> app server. Mọi vận tốc theo đơn vị web (m/s, rad/s).
  // Thẻ loại tin nằm ở khóa `t`.

  import type { BodyVel, Pose } from "./mecanum";

  /** Nguồn của một cmd_vel; app server bỏ qua trường này. */
  export type CmdSrc = "keyboard" | "forward" | "inverse" | "stop";

  export type Role = "driver" | "viewer";

  export type ClientMessage =
    | { t: "hello"; token: string }
    | {
        t: "cmd_vel";
        seq: number;
        vx: number;
        vy: number;
        wz: number;
        src: CmdSrc;
      }
    | { t: "arm"; on: boolean }
    | { t: "odom_reset" };

  export interface Imu {
    ax: number;
    ay: number;
    az: number;
    gx: number;
    gy: number;
    gz: number;
  }

  /** Trường tự do do robot gửi; trang hệ thống (T09) sẽ đọc chi tiết. */
  export type LooseRecord = { [key: string]: unknown };

  export interface StateMsg {
    t: "state";
    link: { robot: boolean; rtt_ms: number | null };
    session: { armed: boolean; has_driver: boolean; role: Role | null };
    vel: BodyVel | null;
    pose: Pose;
    cmd: BodyVel;
    imu: Imu | null;
    voltage: number | null;
    flag_stop: boolean | number | null;
    charge: LooseRecord | null;
    health: LooseRecord | null;
    last_cmd_seq: number | null;
  }

  export function encodeMessage(msg: ClientMessage): string {
    return JSON.stringify(msg);
  }

  function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
  }

  /** Phân tích một tin văn bản từ server. Trả null nếu không phải `state` hợp lệ. */
  export function parseServerMessage(text: string): StateMsg | null {
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      return null;
    }
    if (!isRecord(data) || data.t !== "state") return null;
    const { link, session, pose, cmd } = data;
    if (!isRecord(link) || typeof link.robot !== "boolean") return null;
    if (!isRecord(session) || typeof session.armed !== "boolean") return null;
    if (!isRecord(pose) || !isRecord(cmd)) return null;
    return data as unknown as StateMsg;
  }

  export interface LocationLike {
    protocol: string;
    hostname: string;
  }

  export const WS_PORT = 8000;
  export const WS_PATH = "/ws/operator";

  /** Địa chỉ WebSocket: biến môi trường nếu có, ngược lại suy từ hostname của trang, cổng 8000. */
  export function resolveWsUrl(
    envUrl: string | undefined,
    loc: LocationLike,
  ): string {
    if (envUrl !== undefined && envUrl.trim() !== "") return envUrl.trim();
    const scheme = loc.protocol === "https:" ? "wss" : "ws";
    return `${scheme}://${loc.hostname}:${WS_PORT}${WS_PATH}`;
  }
  ```

  **File 3: `app/client/src/robot/control.ts`**

  ```ts
  // Logic thuần của điều khiển (FR-02, FR-09, SAF-03a): ánh xạ phím, chặn khi gõ chữ,
  // và bộ phân xử nguồn lệnh. Không dùng React, DOM, timer hay WebSocket nên test được trực tiếp.
  // store.ts gắn bộ phân xử vào timer 20 Hz và socket.

  import type { BodyVel, Pose } from "./mecanum";
  import { CONTROL_HZ } from "./motion";
  import type { AbortReason, RunContext, RunStatus } from "./motion";
  import type { CmdSrc } from "./protocol";

  export const TICK_MS = 1000 / CONTROL_HZ; // 50 ms

  /** Tốc độ bàn phím: lin (m/s) cho vx, vy; ang (rad/s) cho wz. Không chặn trên (SAF-04). */
  export interface Speed {
    lin: number;
    ang: number;
  }

  export const DEFAULT_SPEED: Speed = { lin: 0.2, ang: 1.0 };

  /** Số hữu hạn lớn hơn 0 thì trả về số đó, ngược lại null. Không có chặn trên. */
  export function parseSpeed(text: string): number | null {
    if (text.trim() === "") return null;
    const value = Number(text);
    return Number.isFinite(value) && value > 0 ? value : null;
  }

  export type MotionAction = "fwd" | "back" | "left" | "right" | "ccw" | "cw";

  // event.code, không phải event.key: đúng khi bật bộ gõ tiếng Việt hay đổi bố cục bàn phím.
  // Hệ trục thân: x tiến, y trái, wz dương ngược chiều kim đồng hồ.
  const MOTION_CODES: Readonly<Record<string, MotionAction>> = {
    KeyW: "fwd",
    ArrowUp: "fwd",
    KeyS: "back",
    ArrowDown: "back",
    KeyA: "left",
    ArrowLeft: "left",
    KeyD: "right",
    ArrowRight: "right",
    KeyQ: "ccw",
    KeyE: "cw",
  };

  export function motionActionOf(code: string): MotionAction | null {
    return Object.prototype.hasOwnProperty.call(MOTION_CODES, code)
      ? MOTION_CODES[code]
      : null;
  }

  /** Tập phím đang giữ (theo event.code) thành vector. Hai phím cùng hướng không cộng đôi. */
  export function keysToVector(held: ReadonlySet<string>, speed: Speed): BodyVel {
    const on = new Set<MotionAction>();
    for (const code of held) {
      const action = motionActionOf(code);
      if (action !== null) on.add(action);
    }
    const axis = (plus: MotionAction, minus: MotionAction): number =>
      (on.has(plus) ? 1 : 0) - (on.has(minus) ? 1 : 0);
    return {
      vx: axis("fwd", "back") * speed.lin,
      vy: axis("left", "right") * speed.lin,
      wz: axis("ccw", "cw") * speed.ang,
    };
  }

  /** Phần tử có focus mà gõ chữ vào được. Cấu trúc tối giản để test không cần DOM. */
  export interface FocusLike {
    tagName?: string;
    isContentEditable?: boolean;
  }

  export function isTypingTarget(target: FocusLike | null | undefined): boolean {
    if (target === null || target === undefined) return false;
    if (target.isContentEditable === true) return true;
    const tag = typeof target.tagName === "string" ? target.tagName.toUpperCase() : "";
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
  }

  export type KeyAction =
    | { kind: "motion"; code: string }
    | { kind: "arm" }
    | { kind: "stop" };

  export interface KeyContext {
    /** Focus đang ở ô nhập. */
    typing: boolean;
    /** Ctrl, Meta hoặc Alt đang giữ (Ctrl+R tải lại trang không được arm). */
    modifier: boolean;
  }

  /** FR-02: phím nhấn xuống thành hành động, hoặc null nếu bị bỏ qua. Esc luôn có hiệu lực. */
  export function decideKeyDown(code: string, ctx: KeyContext): KeyAction | null {
    if (code === "Escape") return { kind: "stop" };
    if (ctx.typing || ctx.modifier) return null;
    if (code === "KeyX") return { kind: "stop" };
    if (code === "KeyR") return { kind: "arm" };
    if (motionActionOf(code) !== null) return { kind: "motion", code };
    return null;
  }

  export type RunSource = "forward" | "inverse";
  /** FR-09: nguồn lệnh hiện tại, tính ở client. */
  export type Source = "idle" | "keyboard" | RunSource;

  export type EndReason =
    | AbortReason
    | "blur"
    | "hidden"
    | "closed"
    | "stop"
    | "cancel"
    | "error";

  export interface RunEnd {
    source: RunSource;
    done: boolean;
    /** null khi done. */
    reason: EndReason | null;
  }

  /** Đầu vào mỗi chu kỳ cho bộ chạy tự động; tương thích RunContext của motion.ts. */
  export interface RunInput extends RunContext {
    /** Thời gian từ chu kỳ trước (s). */
    dt: number;
    /** Tư thế mới nhất từ server, null nếu chưa có state. */
    pose: Pose | null;
  }

  export interface RunStep {
    cmd: BodyVel;
    status: RunStatus;
  }

  /** T10, T11 bọc bộ bước của motion.ts (wheelRunStep, trackStep) thành RunDriver. */
  export interface RunDriver {
    step(input: RunInput): RunStep;
  }

  export interface TickContext {
    dt: number;
    pose: Pose | null;
    stateAgeS: number;
    armed: boolean;
  }

  export interface Output {
    cmd: BodyVel;
    src: CmdSrc;
  }

  const ZERO: BodyVel = { vx: 0, vy: 0, wz: 0 };

  function isZero(cmd: BodyVel): boolean {
    return cmd.vx === 0 && cmd.vy === 0 && cmd.wz === 0;
  }

  /**
   * Phân xử nguồn lệnh: phím thắng chạy tự động. Chỉ có bộ phân xử này tạo ra cmd_vel.
   * Khi rảnh (không phím, không chạy, không nợ lệnh 0) thì tick trả null: không gửi gì.
   */
  export class Arbiter {
    speed: Speed;
    private held = new Set<string>();
    private run: { driver: RunDriver; source: RunSource } | null = null;
    private owesZero = false;
    private lastSrc: CmdSrc = "keyboard";
    private end: RunEnd | null = null;

    constructor(speed: Speed = DEFAULT_SPEED) {
      this.speed = speed;
    }

    get source(): Source {
      if (this.held.size > 0) return "keyboard";
      if (this.run !== null) return this.run.source;
      return "idle";
    }

    /** Còn việc phải làm ở chu kỳ tới, nên timer 20 Hz cần chạy. */
    get active(): boolean {
      return this.held.size > 0 || this.run !== null || this.owesZero;
    }

    /** Kết thúc của lần chạy gần nhất, null nếu chưa có. */
    get lastRunEnd(): RunEnd | null {
      return this.end;
    }

    get holdingKeys(): boolean {
      return this.held.size > 0;
    }

    setSpeed(speed: Speed): void {
      this.speed = speed;
    }

    /** Giữ một phím di chuyển. Mọi phím di chuyển hủy lần chạy đang có. */
    keyDown(code: string): void {
      if (motionActionOf(code) === null) return;
      this.held.add(code);
      this.cancelRun("key");
    }

    keyUp(code: string): void {
      this.held.delete(code);
    }

    /** Bắt đầu một lần chạy. Trả false (không chạy) khi đang giữ phím: phím thắng. */
    startRun(driver: RunDriver, source: RunSource): boolean {
      if (this.held.size > 0) return false;
      this.cancelRun("cancel");
      this.run = { driver, source };
      this.end = null;
      return true;
    }

    cancelRun(reason: EndReason): void {
      if (this.run === null) return;
      this.end = { source: this.run.source, done: false, reason };
      this.run = null;
    }

    /** Nhả mọi phím và hủy lần chạy (mất focus, ẩn tab, disarm, đóng socket, dừng khẩn). */
    releaseAll(reason: EndReason): void {
      this.held.clear();
      this.cancelRun(reason);
      this.owesZero = false;
    }

    /** Nhả mọi phím nhưng giữ lần chạy (focus vào ô nhập). */
    releaseKeys(): void {
      this.held.clear();
    }

    /** Lệnh 0 còn nợ sau khi nhả phím hoặc hủy chạy. Trả null nếu không nợ hoặc vẫn còn nguồn. */
    flushZero(): Output | null {
      if (!this.owesZero || this.held.size > 0 || this.run !== null) return null;
      this.owesZero = false;
      return { cmd: { ...ZERO }, src: this.lastSrc };
    }

    /** Một chu kỳ 20 Hz. null nghĩa là không gửi gì. */
    tick(ctx: TickContext): Output | null {
      if (this.held.size > 0) {
        return this.emit({ cmd: keysToVector(this.held, this.speed), src: "keyboard" });
      }
      if (this.run !== null) {
        const { driver, source } = this.run;
        let step: RunStep;
        try {
          step = driver.step({ ...ctx, keyPressed: false });
        } catch {
          this.end = { source, done: false, reason: "error" };
          this.run = null;
          return this.emit({ cmd: { ...ZERO }, src: source });
        }
        if (step.status.kind === "running") {
          return this.emit({ cmd: step.cmd, src: source });
        }
        this.end =
          step.status.kind === "done"
            ? { source, done: true, reason: null }
            : { source, done: false, reason: step.status.reason };
        this.run = null;
        return this.emit({ cmd: { ...ZERO }, src: source });
      }
      return this.flushZero();
    }

    private emit(out: Output): Output {
      this.owesZero = !isZero(out.cmd);
      this.lastSrc = out.src;
      return out;
    }
  }
  ```

  **File 4: `app/client/src/robot/store.ts`**

  ```ts
  // Kho trạng thái robot cho cả ứng dụng: một WebSocket ngoài React, tự kết nối lại có back-off,
  // một bộ phân xử nguồn lệnh với một timer 20 Hz (FR-02, FR-03, FR-08, FR-09, SAF-03a, NFR-03).
  // Dữ liệu tần số cao (state ~20 Hz) không nằm trong React state: trang đọc bằng
  // useTelemetry() hoặc subscribeTelemetry() + getTelemetry() (canvas qua ref).
  // Trạng thái tần số thấp cho thanh trạng thái nằm trong useShell().

  import { useSyncExternalStore } from "react";

  import { Arbiter, DEFAULT_SPEED, TICK_MS } from "./control";
  import type {
    EndReason,
    Output,
    RunDriver,
    RunEnd,
    RunSource,
    Source,
    Speed,
  } from "./control";
  import { encodeMessage, parseServerMessage, resolveWsUrl } from "./protocol";
  import type { ClientMessage, Role, StateMsg } from "./protocol";

  export const BACKOFF_INITIAL_MS = 500;
  export const BACKOFF_MAX_MS = 5000;
  const MAX_BUFFERED_BYTES = 8192;
  const CODE_KEY = "mecanum.operatorCode";

  /** Thời gian chờ kết nối lại lần tới: gấp đôi, tối đa BACKOFF_MAX_MS. */
  export function nextBackoff(previousMs: number): number {
    return Math.min(previousMs * 2, BACKOFF_MAX_MS);
  }

  export type Connection = "connecting" | "open" | "closed";

  /** Trạng thái tần số thấp: chỉ đổi khi một trường đổi, nên thanh trạng thái không render lại ở 20 Hz. */
  export interface ShellSnapshot {
    conn: Connection;
    /** Đã nhận ít nhất một state trên kết nối hiện tại. */
    hasState: boolean;
    robotLink: boolean;
    armed: boolean;
    role: Role | null;
    hasCode: boolean;
    source: Source;
    speed: Speed;
    lastRunEnd: RunEnd | null;
  }

  const INITIAL_SHELL: ShellSnapshot = {
    conn: "closed",
    hasState: false,
    robotLink: false,
    armed: false,
    role: null,
    hasCode: false,
    source: "idle",
    speed: DEFAULT_SPEED,
    lastRunEnd: null,
  };

  const arbiter = new Arbiter(DEFAULT_SPEED);

  let started = false;
  let ws: WebSocket | null = null;
  let conn: Connection = "closed";
  let backoffMs = BACKOFF_INITIAL_MS;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let tickTimer: ReturnType<typeof setInterval> | null = null;
  let lastTickAt = 0;
  let seq = 0;
  let operatorCode = "";
  let telemetry: StateMsg | null = null;
  let telemetryAt = Number.NEGATIVE_INFINITY;
  let shell: ShellSnapshot = INITIAL_SHELL;
  const telemetryListeners = new Set<() => void>();
  const shellListeners = new Set<() => void>();

  // ---- tồn tại ngoài React: đăng ký và đọc ----

  export function subscribeTelemetry(listener: () => void): () => void {
    telemetryListeners.add(listener);
    return () => {
      telemetryListeners.delete(listener);
    };
  }

  export function getTelemetry(): StateMsg | null {
    return telemetry;
  }

  /** performance.now() lúc nhận state gần nhất; -Infinity nếu chưa có. */
  export function getTelemetryAt(): number {
    return telemetryAt;
  }

  function subscribeShell(listener: () => void): () => void {
    shellListeners.add(listener);
    return () => {
      shellListeners.delete(listener);
    };
  }

  function getShell(): ShellSnapshot {
    return shell;
  }

  function getServerShell(): ShellSnapshot {
    return INITIAL_SHELL;
  }

  function getServerTelemetry(): StateMsg | null {
    return null;
  }

  /** State mới nhất ở tần số tới 20 Hz; chỉ trang cần số liệu mới nên dùng. */
  export function useTelemetry(): StateMsg | null {
    return useSyncExternalStore(subscribeTelemetry, getTelemetry, getServerTelemetry);
  }

  /** Trạng thái tần số thấp cho thanh trạng thái và trang cần biết arm, quyền lái, nguồn lệnh. */
  export function useShell(): ShellSnapshot {
    return useSyncExternalStore(subscribeShell, getShell, getServerShell);
  }

  function notifyTelemetry(): void {
    for (const listener of telemetryListeners) listener();
  }

  function publishShell(): void {
    const next: ShellSnapshot = {
      conn,
      hasState: telemetry !== null,
      robotLink: telemetry?.link.robot ?? false,
      armed: telemetry?.session.armed ?? false,
      role: telemetry?.session.role ?? null,
      hasCode: operatorCode !== "",
      source: arbiter.source,
      speed: arbiter.speed,
      lastRunEnd: arbiter.lastRunEnd,
    };
    const same =
      next.conn === shell.conn &&
      next.hasState === shell.hasState &&
      next.robotLink === shell.robotLink &&
      next.armed === shell.armed &&
      next.role === shell.role &&
      next.hasCode === shell.hasCode &&
      next.source === shell.source &&
      next.speed === shell.speed &&
      next.lastRunEnd === shell.lastRunEnd;
    if (same) return;
    shell = next;
    for (const listener of shellListeners) listener();
  }

  // ---- gửi ----

  function isOpen(): boolean {
    return ws !== null && ws.readyState === WebSocket.OPEN;
  }

  function send(msg: ClientMessage): void {
    if (ws !== null && ws.readyState === WebSocket.OPEN) ws.send(encodeMessage(msg));
  }

  function sendCmd(out: Output): void {
    if (ws === null || ws.readyState !== WebSocket.OPEN) return;
    const zero = out.cmd.vx === 0 && out.cmd.vy === 0 && out.cmd.wz === 0;
    // NFR-03: socket đang nghẽn thì bỏ lệnh chuyển động này, không dồn hàng đợi; lệnh 0 vẫn đi.
    if (!zero && ws.bufferedAmount > MAX_BUFFERED_BYTES) return;
    seq += 1;
    send({
      t: "cmd_vel",
      seq,
      vx: out.cmd.vx,
      vy: out.cmd.vy,
      wz: out.cmd.wz,
      src: out.src,
    });
  }

  function sendZeroNow(): void {
    sendCmd({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "stop" });
  }

  function sendHello(): void {
    if (operatorCode !== "") send({ t: "hello", token: operatorCode });
  }

  // ---- điều khiển ----

  /** Quyền lái thật: socket mở, đã arm, và client này đang giữ quyền lái. */
  function canDrive(): boolean {
    return (
      isOpen() &&
      telemetry !== null &&
      telemetry.session.armed &&
      telemetry.session.role === "driver"
    );
  }

  function syncTimer(): void {
    if (arbiter.active) {
      if (tickTimer === null) {
        lastTickAt = performance.now() - TICK_MS;
        tickTimer = setInterval(onTick, TICK_MS);
      }
    } else if (tickTimer !== null) {
      clearInterval(tickTimer);
      tickTimer = null;
    }
  }

  function onTick(): void {
    if (!canDrive()) {
      haltAll("disarmed");
      return;
    }
    const now = performance.now();
    const dt = Math.max(0, (now - lastTickAt) / 1000);
    lastTickAt = now;
    const out = arbiter.tick({
      dt,
      pose: telemetry?.pose ?? null,
      stateAgeS: (now - telemetryAt) / 1000,
      armed: true,
    });
    if (out !== null) sendCmd(out);
    syncTimer();
    publishShell();
  }

  function flushZero(): void {
    const out = arbiter.flushZero();
    if (out !== null) sendCmd(out);
  }

  /**
   * SAF-03a: hủy phím và lần chạy, gửi cmd_vel 0 đúng một lần (nếu socket còn mở).
   * Dùng khi mất focus, ẩn tab, disarm, đóng socket.
   */
  export function haltAll(reason: EndReason): void {
    arbiter.releaseAll(reason);
    sendZeroNow();
    syncTimer();
    publishShell();
  }

  /** Dừng khẩn (X, Esc, nút): 0 rồi disarm. */
  export function emergencyStop(): void {
    arbiter.releaseAll("stop");
    sendZeroNow();
    send({ t: "arm", on: false });
    syncTimer();
    publishShell();
  }

  export function setArmed(on: boolean): void {
    send({ t: "arm", on });
  }

  export function resetOdometry(): void {
    send({ t: "odom_reset" });
  }

  /** Phím di chuyển nhấn xuống. Bỏ qua khi chưa được phép lái. */
  export function pressMotion(code: string): void {
    if (!canDrive()) return;
    arbiter.keyDown(code);
    syncTimer();
    publishShell();
  }

  export function releaseMotion(code: string): void {
    arbiter.keyUp(code);
    flushZero();
    syncTimer();
    publishShell();
  }

  /** Focus vào ô nhập: nhả mọi phím đang giữ, giữ nguyên lần chạy. */
  export function releaseKeys(): void {
    arbiter.releaseKeys();
    flushZero();
    syncTimer();
    publishShell();
  }

  /** T10, T11: bắt đầu một lần chạy theo bộ bước của motion.ts. Trả false nếu không được phép. */
  export function startRun(driver: RunDriver, source: RunSource): boolean {
    if (!canDrive()) return false;
    if (!arbiter.startRun(driver, source)) return false;
    syncTimer();
    publishShell();
    return true;
  }

  /** T10, T11: hủy lần chạy, gửi 0 một lần nếu còn nợ. */
  export function cancelRun(): void {
    arbiter.cancelRun("cancel");
    flushZero();
    syncTimer();
    publishShell();
  }

  /** Đặt tốc độ bàn phím. Giá trị không hữu hạn hoặc không dương bị bỏ qua; không có chặn trên. */
  export function setSpeed(lin: number, ang: number): void {
    if (!(Number.isFinite(lin) && lin > 0 && Number.isFinite(ang) && ang > 0)) return;
    arbiter.setSpeed({ lin, ang });
    publishShell();
  }

  // ---- mã điều khiển ----

  function readStoredCode(): string {
    try {
      return window.sessionStorage.getItem(CODE_KEY) ?? "";
    } catch {
      return "";
    }
  }

  function writeStoredCode(code: string): void {
    try {
      if (code === "") window.sessionStorage.removeItem(CODE_KEY);
      else window.sessionStorage.setItem(CODE_KEY, code);
    } catch {
      // sessionStorage bị chặn: mã chỉ sống trong bộ nhớ.
    }
  }

  /** Đặt mã điều khiển. Rỗng thì xóa mã và kết nối lại ở chế độ chỉ xem. */
  export function setOperatorCode(code: string): void {
    operatorCode = code.trim();
    writeStoredCode(operatorCode);
    if (operatorCode !== "") sendHello();
    else if (ws !== null) ws.close();
    publishShell();
  }

  // ---- kết nối ----

  function scheduleReconnect(): void {
    if (reconnectTimer !== null) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, backoffMs);
    backoffMs = nextBackoff(backoffMs);
  }

  function connect(): void {
    conn = "connecting";
    publishShell();
    let socket: WebSocket;
    try {
      socket = new WebSocket(
        resolveWsUrl(process.env.NEXT_PUBLIC_APP_WS_URL, window.location),
      );
    } catch {
      conn = "closed";
      publishShell();
      scheduleReconnect();
      return;
    }
    socket.binaryType = "arraybuffer";
    ws = socket;
    socket.onopen = () => {
      if (ws !== socket) return;
      conn = "open";
      backoffMs = BACKOFF_INITIAL_MS;
      sendHello();
      publishShell();
    };
    socket.onmessage = (event: MessageEvent) => {
      if (ws !== socket || typeof event.data !== "string") return; // khung nhị phân: LiDAR, T13
      const msg = parseServerMessage(event.data);
      if (msg === null) return;
      const couldDrive = canDrive();
      telemetry = msg;
      telemetryAt = performance.now();
      notifyTelemetry();
      if (couldDrive && !canDrive()) haltAll("disarmed");
      else publishShell();
    };
    socket.onclose = () => {
      if (ws !== socket) return;
      ws = null;
      conn = "closed";
      telemetry = null;
      notifyTelemetry();
      haltAll("closed");
      scheduleReconnect();
    };
    socket.onerror = () => {
      // onclose theo sau; không làm gì thêm.
    };
  }

  /** Khởi động kết nối một lần (gọi từ effect; gọi lại không làm gì). Không bao giờ đóng khi đổi trang. */
  export function startStore(): void {
    if (started || typeof window === "undefined") return;
    started = true;
    operatorCode = readStoredCode();
    connect();
  }
  ```

  **File 5: `app/client/src/robot/keyboard.tsx`**

  ```tsx
  "use client";

  // FR-02: điều khiển bàn phím toàn cục, gắn ở root layout nên hoạt động ở mọi trang.
  // Không render gì; chỉ đăng ký listener và chuyển sự kiện cho store.

  import { useEffect } from "react";

  import { decideKeyDown, isTypingTarget, motionActionOf } from "./control";
  import type { FocusLike } from "./control";
  import {
    emergencyStop,
    haltAll,
    pressMotion,
    releaseKeys,
    releaseMotion,
    setArmed,
    startStore,
  } from "./store";

  export function KeyboardController(): null {
    useEffect(() => {
      startStore();

      const onKeyDown = (event: KeyboardEvent) => {
        const action = decideKeyDown(event.code, {
          typing: isTypingTarget(event.target as FocusLike | null),
          modifier: event.ctrlKey || event.metaKey || event.altKey,
        });
        if (action === null) return;
        if (action.kind === "motion") {
          event.preventDefault(); // không cuộn trang bằng phím mũi tên
          pressMotion(action.code);
        } else if (action.kind === "arm") {
          if (!event.repeat) setArmed(true);
        } else {
          emergencyStop();
        }
      };
      // Nhả phím luôn được xử lý, kể cả khi focus đã chuyển vào ô nhập, để không kẹt phím.
      const onKeyUp = (event: KeyboardEvent) => {
        if (motionActionOf(event.code) !== null) releaseMotion(event.code);
      };
      const onFocusIn = (event: FocusEvent) => {
        if (isTypingTarget(event.target as FocusLike | null)) releaseKeys();
      };
      const onBlur = () => haltAll("blur");
      const onVisibility = () => {
        if (document.hidden) haltAll("hidden");
      };

      window.addEventListener("keydown", onKeyDown);
      window.addEventListener("keyup", onKeyUp);
      window.addEventListener("focusin", onFocusIn);
      window.addEventListener("blur", onBlur);
      document.addEventListener("visibilitychange", onVisibility);
      return () => {
        window.removeEventListener("keydown", onKeyDown);
        window.removeEventListener("keyup", onKeyUp);
        window.removeEventListener("focusin", onFocusIn);
        window.removeEventListener("blur", onBlur);
        document.removeEventListener("visibilitychange", onVisibility);
      };
    }, []);

    return null;
  }
  ```

  **File 6: `app/client/src/robot/control.test.ts`**

  ```ts
  import { describe, expect, it } from "vitest";

  import {
    Arbiter,
    DEFAULT_SPEED,
    decideKeyDown,
    isTypingTarget,
    keysToVector,
    motionActionOf,
    parseSpeed,
  } from "./control";
  import type { RunDriver, TickContext } from "./control";
  import { createWheelRun, wheelRunStep } from "./motion";
  import type { Wheels } from "./mecanum";
  import { parseServerMessage, resolveWsUrl } from "./protocol";
  import { BACKOFF_INITIAL_MS, BACKOFF_MAX_MS, nextBackoff } from "./store";

  const SPEED = { lin: 0.2, ang: 1.0 };
  const CTX: TickContext = { dt: 0.05, pose: null, stateAgeS: 0.01, armed: true };
  const NO_MODIFIER = { typing: false, modifier: false };

  function keys(...codes: string[]): Set<string> {
    return new Set(codes);
  }

  function wheelDriver(wheels: Wheels, durationS: number): RunDriver {
    let run = createWheelRun(wheels, durationS);
    return {
      step(input) {
        const result = wheelRunStep(run, input, input.dt);
        run = result.run;
        return { cmd: result.cmd, status: result.status };
      },
    };
  }

  describe("keysToVector (FR-02)", () => {
    it("không phím thì vector 0", () => {
      expect(keysToVector(keys(), SPEED)).toEqual({ vx: 0, vy: 0, wz: 0 });
    });

    it("W và mũi tên lên là vx dương, S và mũi tên xuống là vx âm", () => {
      expect(keysToVector(keys("KeyW"), SPEED)).toEqual({ vx: 0.2, vy: 0, wz: 0 });
      expect(keysToVector(keys("ArrowUp"), SPEED)).toEqual({ vx: 0.2, vy: 0, wz: 0 });
      expect(keysToVector(keys("KeyS"), SPEED)).toEqual({ vx: -0.2, vy: 0, wz: 0 });
      expect(keysToVector(keys("ArrowDown"), SPEED)).toEqual({ vx: -0.2, vy: 0, wz: 0 });
    });

    it("A và mũi tên trái là vy dương (sang trái), D và mũi tên phải là vy âm", () => {
      expect(keysToVector(keys("KeyA"), SPEED)).toEqual({ vx: 0, vy: 0.2, wz: 0 });
      expect(keysToVector(keys("ArrowLeft"), SPEED)).toEqual({ vx: 0, vy: 0.2, wz: 0 });
      expect(keysToVector(keys("KeyD"), SPEED)).toEqual({ vx: 0, vy: -0.2, wz: 0 });
      expect(keysToVector(keys("ArrowRight"), SPEED)).toEqual({ vx: 0, vy: -0.2, wz: 0 });
    });

    it("Q quay ngược chiều kim đồng hồ (wz dương), E quay thuận chiều kim đồng hồ", () => {
      expect(keysToVector(keys("KeyQ"), SPEED)).toEqual({ vx: 0, vy: 0, wz: 1 });
      expect(keysToVector(keys("KeyE"), SPEED)).toEqual({ vx: 0, vy: 0, wz: -1 });
    });

    it("nhiều phím cộng thành vector (đi chéo vừa quay)", () => {
      expect(keysToVector(keys("KeyW", "KeyA", "KeyE"), SPEED)).toEqual({
        vx: 0.2,
        vy: 0.2,
        wz: -1,
      });
    });

    it("hai phím ngược nhau triệt tiêu", () => {
      expect(keysToVector(keys("KeyW", "KeyS"), SPEED)).toEqual({ vx: 0, vy: 0, wz: 0 });
    });

    it("hai phím cùng hướng không cộng đôi", () => {
      expect(keysToVector(keys("KeyW", "ArrowUp"), SPEED)).toEqual({ vx: 0.2, vy: 0, wz: 0 });
    });

    it("tốc độ không có chặn trên (SAF-04)", () => {
      expect(keysToVector(keys("KeyW", "KeyQ"), { lin: 1000, ang: 50 })).toEqual({
        vx: 1000,
        vy: 0,
        wz: 50,
      });
    });

    it("bỏ qua mã không phải phím di chuyển", () => {
      expect(keysToVector(keys("KeyX", "Space"), SPEED)).toEqual({ vx: 0, vy: 0, wz: 0 });
      expect(motionActionOf("KeyX")).toBeNull();
      expect(motionActionOf("constructor")).toBeNull();
      expect(motionActionOf("KeyW")).toBe("fwd");
    });
  });

  describe("parseSpeed", () => {
    it("nhận số hữu hạn lớn hơn 0, không chặn trên", () => {
      expect(parseSpeed("0.3")).toBe(0.3);
      expect(parseSpeed(" 2 ")).toBe(2);
      expect(parseSpeed("1000")).toBe(1000);
    });

    it("từ chối rỗng, 0, âm, không phải số, vô hạn", () => {
      for (const text of ["", "  ", "0", "-1", "abc", "Infinity", "NaN", "1e999"]) {
        expect(parseSpeed(text)).toBeNull();
      }
    });
  });

  describe("isTypingTarget", () => {
    it("true với input, textarea, select, contenteditable", () => {
      expect(isTypingTarget({ tagName: "INPUT" })).toBe(true);
      expect(isTypingTarget({ tagName: "textarea" })).toBe(true);
      expect(isTypingTarget({ tagName: "SELECT" })).toBe(true);
      expect(isTypingTarget({ tagName: "DIV", isContentEditable: true })).toBe(true);
    });

    it("false với phần tử khác hoặc không có target", () => {
      expect(isTypingTarget({ tagName: "BUTTON" })).toBe(false);
      expect(isTypingTarget({ tagName: "BODY" })).toBe(false);
      expect(isTypingTarget({})).toBe(false);
      expect(isTypingTarget(null)).toBe(false);
      expect(isTypingTarget(undefined)).toBe(false);
    });
  });

  describe("decideKeyDown (FR-02)", () => {
    it("phím di chuyển, R, X, Esc khi không gõ chữ", () => {
      expect(decideKeyDown("KeyW", NO_MODIFIER)).toEqual({ kind: "motion", code: "KeyW" });
      expect(decideKeyDown("ArrowLeft", NO_MODIFIER)).toEqual({
        kind: "motion",
        code: "ArrowLeft",
      });
      expect(decideKeyDown("KeyR", NO_MODIFIER)).toEqual({ kind: "arm" });
      expect(decideKeyDown("KeyX", NO_MODIFIER)).toEqual({ kind: "stop" });
      expect(decideKeyDown("Escape", NO_MODIFIER)).toEqual({ kind: "stop" });
    });

    it("đang gõ chữ thì bỏ qua phím di chuyển, R và X nhưng Esc vẫn dừng", () => {
      const typing = { typing: true, modifier: false };
      expect(decideKeyDown("KeyW", typing)).toBeNull();
      expect(decideKeyDown("ArrowUp", typing)).toBeNull();
      expect(decideKeyDown("KeyR", typing)).toBeNull();
      expect(decideKeyDown("KeyX", typing)).toBeNull();
      expect(decideKeyDown("Escape", typing)).toEqual({ kind: "stop" });
    });

    it("giữ Ctrl, Meta hoặc Alt thì bỏ qua (Ctrl+R không được arm), Esc vẫn dừng", () => {
      const modifier = { typing: false, modifier: true };
      expect(decideKeyDown("KeyR", modifier)).toBeNull();
      expect(decideKeyDown("KeyW", modifier)).toBeNull();
      expect(decideKeyDown("Escape", modifier)).toEqual({ kind: "stop" });
    });

    it("phím khác bị bỏ qua", () => {
      expect(decideKeyDown("KeyZ", NO_MODIFIER)).toBeNull();
      expect(decideKeyDown("Space", NO_MODIFIER)).toBeNull();
    });
  });

  describe("Arbiter: bàn phím", () => {
    it("rảnh thì tick không gửi gì và timer không cần chạy", () => {
      const arb = new Arbiter(SPEED);
      expect(arb.source).toBe("idle");
      expect(arb.active).toBe(false);
      expect(arb.tick(CTX)).toBeNull();
      expect(arb.flushZero()).toBeNull();
    });

    it("giữ phím thì mỗi tick gửi vector, nhả phím thì nợ đúng một lệnh 0", () => {
      const arb = new Arbiter(SPEED);
      arb.keyDown("KeyW");
      expect(arb.source).toBe("keyboard");
      expect(arb.active).toBe(true);
      expect(arb.tick(CTX)).toEqual({ cmd: { vx: 0.2, vy: 0, wz: 0 }, src: "keyboard" });
      expect(arb.tick(CTX)).toEqual({ cmd: { vx: 0.2, vy: 0, wz: 0 }, src: "keyboard" });
      arb.keyUp("KeyW");
      expect(arb.source).toBe("idle");
      expect(arb.active).toBe(true);
      expect(arb.flushZero()).toEqual({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "keyboard" });
      expect(arb.flushZero()).toBeNull();
      expect(arb.tick(CTX)).toBeNull();
      expect(arb.active).toBe(false);
    });

    it("nhả phím trước khi tick nào gửi vector thì không nợ lệnh 0", () => {
      const arb = new Arbiter(SPEED);
      arb.keyDown("KeyD");
      arb.keyUp("KeyD");
      expect(arb.flushZero()).toBeNull();
      expect(arb.active).toBe(false);
    });

    it("nhả một trong hai phím thì vector còn lại", () => {
      const arb = new Arbiter(SPEED);
      arb.keyDown("KeyW");
      arb.keyDown("KeyQ");
      expect(arb.tick(CTX)?.cmd).toEqual({ vx: 0.2, vy: 0, wz: 1 });
      arb.keyUp("KeyQ");
      expect(arb.tick(CTX)?.cmd).toEqual({ vx: 0.2, vy: 0, wz: 0 });
    });

    it("đổi tốc độ có hiệu lực ngay ở tick sau", () => {
      const arb = new Arbiter(SPEED);
      arb.keyDown("KeyW");
      arb.setSpeed({ lin: 3, ang: 2 });
      expect(arb.tick(CTX)?.cmd).toEqual({ vx: 3, vy: 0, wz: 0 });
    });

    it("phím không phải di chuyển bị bỏ qua", () => {
      const arb = new Arbiter(SPEED);
      arb.keyDown("KeyX");
      expect(arb.source).toBe("idle");
      expect(arb.active).toBe(false);
    });

    it("releaseAll nhả mọi phím và không nợ lệnh 0 (store tự gửi 0 một lần)", () => {
      const arb = new Arbiter(SPEED);
      arb.keyDown("KeyW");
      arb.tick(CTX);
      arb.releaseAll("blur");
      expect(arb.source).toBe("idle");
      expect(arb.active).toBe(false);
      expect(arb.tick(CTX)).toBeNull();
    });

    it("releaseKeys nhả phím nhưng vẫn nợ lệnh 0 đã gửi vector", () => {
      const arb = new Arbiter(SPEED);
      arb.keyDown("KeyW");
      arb.tick(CTX);
      arb.releaseKeys();
      expect(arb.flushZero()).toEqual({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "keyboard" });
    });

    it("DEFAULT_SPEED là 0.2 m/s và 1.0 rad/s", () => {
      expect(DEFAULT_SPEED).toEqual({ lin: 0.2, ang: 1.0 });
    });
  });

  describe("Arbiter: chạy tự động và phân xử (FR-09)", () => {
    const FORWARD: Wheels = [10, 10, 10, 10]; // vx = 0.5 m/s

    it("chạy theo bộ bước của motion.ts rồi tự kết thúc bằng một lệnh 0", () => {
      const arb = new Arbiter(SPEED);
      expect(arb.startRun(wheelDriver(FORWARD, 0.1), "forward")).toBe(true);
      expect(arb.source).toBe("forward");
      expect(arb.active).toBe(true);

      const first = arb.tick(CTX);
      expect(first?.src).toBe("forward");
      expect(first?.cmd.vx).toBeCloseTo(0.5, 12);
      expect(first?.cmd.vy).toBeCloseTo(0, 12);
      expect(first?.cmd.wz).toBeCloseTo(0, 12);

      const last = arb.tick(CTX);
      expect(last).toEqual({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "forward" });
      expect(arb.lastRunEnd).toEqual({ source: "forward", done: true, reason: null });
      expect(arb.source).toBe("idle");
      expect(arb.active).toBe(false);
      expect(arb.tick(CTX)).toBeNull();
    });

    it("phím di chuyển hủy lần chạy và phím thắng", () => {
      const arb = new Arbiter(SPEED);
      arb.startRun(wheelDriver(FORWARD, 5), "inverse");
      expect(arb.source).toBe("inverse");
      arb.keyDown("KeyD");
      expect(arb.source).toBe("keyboard");
      expect(arb.lastRunEnd).toEqual({ source: "inverse", done: false, reason: "key" });
      expect(arb.tick(CTX)).toEqual({ cmd: { vx: 0, vy: -0.2, wz: 0 }, src: "keyboard" });
    });

    it("đang giữ phím thì không bắt đầu được lần chạy", () => {
      const arb = new Arbiter(SPEED);
      arb.keyDown("KeyW");
      expect(arb.startRun(wheelDriver(FORWARD, 5), "forward")).toBe(false);
      expect(arb.source).toBe("keyboard");
    });

    it("bắt đầu lần chạy mới thay lần cũ", () => {
      const arb = new Arbiter(SPEED);
      arb.startRun(wheelDriver(FORWARD, 5), "forward");
      arb.startRun(wheelDriver(FORWARD, 5), "inverse");
      expect(arb.source).toBe("inverse");
      expect(arb.lastRunEnd).toBeNull();
    });

    it("hủy lần chạy đang gửi lệnh khác 0 thì nợ đúng một lệnh 0", () => {
      const arb = new Arbiter(SPEED);
      arb.startRun(wheelDriver(FORWARD, 5), "forward");
      arb.tick(CTX);
      arb.cancelRun("cancel");
      expect(arb.lastRunEnd).toEqual({ source: "forward", done: false, reason: "cancel" });
      expect(arb.flushZero()).toEqual({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "forward" });
      expect(arb.flushZero()).toBeNull();
      expect(arb.active).toBe(false);
    });

    it("disarm giữa chừng: motion.ts hủy với lý do disarmed và gửi 0", () => {
      const arb = new Arbiter(SPEED);
      arb.startRun(wheelDriver(FORWARD, 5), "forward");
      arb.tick(CTX);
      const out = arb.tick({ ...CTX, armed: false });
      expect(out).toEqual({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "forward" });
      expect(arb.lastRunEnd).toEqual({ source: "forward", done: false, reason: "disarmed" });
      expect(arb.active).toBe(false);
    });

    it("state cũ hơn 0.5 s: motion.ts hủy với lý do stale", () => {
      const arb = new Arbiter(SPEED);
      arb.startRun(wheelDriver(FORWARD, 5), "forward");
      const out = arb.tick({ ...CTX, stateAgeS: 0.6 });
      expect(out?.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
      expect(arb.lastRunEnd).toEqual({ source: "forward", done: false, reason: "stale" });
    });

    it("mất focus, ẩn tab, đóng socket: releaseAll hủy lần chạy, tick không gửi gì", () => {
      const arb = new Arbiter(SPEED);
      arb.startRun(wheelDriver(FORWARD, 5), "forward");
      arb.tick(CTX);
      arb.releaseAll("hidden");
      expect(arb.lastRunEnd).toEqual({ source: "forward", done: false, reason: "hidden" });
      expect(arb.source).toBe("idle");
      expect(arb.tick(CTX)).toBeNull();
    });

    it("bộ chạy ném lỗi thì kết thúc với lý do error và gửi 0", () => {
      const arb = new Arbiter(SPEED);
      const broken: RunDriver = {
        step() {
          throw new RangeError("hỏng");
        },
      };
      arb.startRun(broken, "inverse");
      expect(arb.tick(CTX)).toEqual({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "inverse" });
      expect(arb.lastRunEnd).toEqual({ source: "inverse", done: false, reason: "error" });
      expect(arb.tick(CTX)).toBeNull();
    });
  });

  describe("protocol", () => {
    const STATE = {
      t: "state",
      link: { robot: true, rtt_ms: 3.2 },
      session: { armed: false, has_driver: true, role: "driver" },
      vel: null,
      pose: { x: 0, y: 0, theta: 0 },
      cmd: { vx: 0, vy: 0, wz: 0 },
      imu: null,
      voltage: null,
      flag_stop: null,
      charge: null,
      health: null,
      last_cmd_seq: null,
    };

    it("nhận state hợp lệ", () => {
      const msg = parseServerMessage(JSON.stringify(STATE));
      expect(msg?.t).toBe("state");
      expect(msg?.session.role).toBe("driver");
    });

    it("từ chối JSON hỏng, tin khác loại và state thiếu trường", () => {
      expect(parseServerMessage("{")).toBeNull();
      expect(parseServerMessage("[]")).toBeNull();
      expect(parseServerMessage("null")).toBeNull();
      expect(parseServerMessage(JSON.stringify({ t: "pong" }))).toBeNull();
      expect(parseServerMessage(JSON.stringify({ ...STATE, link: null }))).toBeNull();
      expect(
        parseServerMessage(JSON.stringify({ ...STATE, session: { armed: "yes" } })),
      ).toBeNull();
      expect(parseServerMessage(JSON.stringify({ ...STATE, pose: 1 }))).toBeNull();
    });

    it("địa chỉ WebSocket suy từ hostname, cổng 8000, đường dẫn /ws/operator", () => {
      expect(resolveWsUrl(undefined, { protocol: "http:", hostname: "100.119.83.63" })).toBe(
        "ws://100.119.83.63:8000/ws/operator",
      );
      expect(resolveWsUrl("", { protocol: "http:", hostname: "localhost" })).toBe(
        "ws://localhost:8000/ws/operator",
      );
      expect(resolveWsUrl(undefined, { protocol: "https:", hostname: "robot.example" })).toBe(
        "wss://robot.example:8000/ws/operator",
      );
    });

    it("biến môi trường ghi đè địa chỉ", () => {
      expect(
        resolveWsUrl(" ws://10.0.0.5:9000/ws/operator ", {
          protocol: "http:",
          hostname: "localhost",
        }),
      ).toBe("ws://10.0.0.5:9000/ws/operator");
    });
  });

  describe("back-off kết nối lại", () => {
    it("gấp đôi tới mức tối đa", () => {
      const seen: number[] = [];
      let delay = BACKOFF_INITIAL_MS;
      for (let i = 0; i < 6; i++) {
        seen.push(delay);
        delay = nextBackoff(delay);
      }
      expect(seen).toEqual([500, 1000, 2000, 4000, 5000, 5000]);
      expect(BACKOFF_MAX_MS).toBe(5000);
    });
  });
  ```

  **File 7: `app/client/src/components/robot/app-shell.tsx`**

  ```tsx
  "use client";

  // FR-01, FR-09: khung ứng dụng nằm ở root layout nên tồn tại xuyên suốt khi chuyển trang.
  // Gồm điều hướng (next/link, chuyển trang phía client không làm rớt WebSocket),
  // thanh trạng thái toàn cục (kết nối, arm, dừng khẩn, nguồn lệnh) và ô nhập mã điều khiển.

  import {
    Activity,
    Cpu,
    KeyRound,
    LayoutDashboard,
    Move,
    OctagonX,
    Power,
    Radar,
    Waypoints,
    Wifi,
    WifiOff,
  } from "lucide-react";
  import Link from "next/link";
  import { usePathname } from "next/navigation";
  import { useEffect, useId, useState } from "react";
  import type { ComponentType, FormEvent, ReactNode } from "react";

  import { Button } from "@/components/ui/button";
  import { Input } from "@/components/ui/input";
  import { Kbd, KbdGroup } from "@/components/ui/kbd";
  import { Label } from "@/components/ui/label";
  import { cn } from "@/lib/utils";
  import { parseSpeed } from "@/robot/control";
  import type { Source } from "@/robot/control";
  import {
    emergencyStop,
    setArmed,
    setOperatorCode,
    setSpeed,
    startStore,
    useShell,
  } from "@/robot/store";
  import type { ShellSnapshot } from "@/robot/store";

  interface NavItem {
    href: string;
    label: string;
    short: string;
    Icon: ComponentType<{ className?: string }>;
  }

  const NAV: readonly NavItem[] = [
    { href: "/", label: "Tổng quan", short: "Tổng quan", Icon: LayoutDashboard },
    { href: "/kinematics/forward", label: "Động học thuận", short: "Thuận", Icon: Move },
    { href: "/kinematics/inverse", label: "Động học ngược", short: "Ngược", Icon: Waypoints },
    { href: "/dynamics", label: "Động lực học", short: "Lực", Icon: Activity },
    { href: "/lidar", label: "LiDAR", short: "LiDAR", Icon: Radar },
    { href: "/system", label: "Hệ thống", short: "Hệ thống", Icon: Cpu },
  ];

  const SOURCE_LABEL: Record<Source, string> = {
    idle: "Không có",
    keyboard: "Bàn phím",
    forward: "Chạy động học thuận",
    inverse: "Chạy động học ngược",
  };

  type Tone = "ok" | "warn" | "bad" | "idle";

  const TONE_CLASS: Record<Tone, string> = {
    ok: "text-emerald-700 dark:text-emerald-400",
    warn: "text-amber-700 dark:text-amber-400",
    bad: "text-destructive",
    idle: "text-muted-foreground",
  };

  function Chip({ tone, children }: { tone: Tone; children: ReactNode }) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border bg-card px-2 py-1 text-xs font-medium tracking-wide whitespace-nowrap",
          TONE_CLASS[tone],
        )}
      >
        {children}
      </span>
    );
  }

  function connectionChip(s: ShellSnapshot): { tone: Tone; text: string } {
    if (s.conn === "open") {
      return s.hasState
        ? { tone: "ok", text: "Đã kết nối" }
        : { tone: "warn", text: "Chờ dữ liệu" };
    }
    if (s.conn === "connecting") return { tone: "warn", text: "Đang kết nối" };
    return { tone: "bad", text: "Mất kết nối" };
  }

  function StatusBar({ shell }: { shell: ShellSnapshot }) {
    const connection = connectionChip(shell);
    const driver = shell.role === "driver";
    const canToggleArm =
      shell.conn === "open" && driver && (shell.armed || shell.robotLink);
    return (
      <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2 md:px-6">
          <div className="flex w-full gap-2 sm:order-last sm:ml-auto sm:w-auto">
            <Button
              type="button"
              variant={shell.armed ? "secondary" : "outline"}
              size="lg"
              className="flex-1 sm:flex-none"
              disabled={!canToggleArm}
              onClick={() => setArmed(!shell.armed)}
            >
              <Power data-icon="inline-start" />
              {shell.armed ? "Disarm" : "Arm (R)"}
            </Button>
            <Button
              type="button"
              size="lg"
              className="flex-1 bg-destructive text-white hover:bg-destructive/90 sm:flex-none"
              onClick={() => emergencyStop()}
            >
              <OctagonX data-icon="inline-start" />
              DỪNG KHẨN (X / Esc)
            </Button>
          </div>
          <div
            className="flex flex-wrap items-center gap-2"
            role="status"
            aria-label="Trạng thái hệ thống"
          >
            <Chip tone={connection.tone}>
              {shell.conn === "open" ? (
                <Wifi className="size-3.5" />
              ) : (
                <WifiOff className="size-3.5" />
              )}
              {connection.text}
            </Chip>
            <Chip tone={!shell.hasState ? "idle" : shell.robotLink ? "ok" : "bad"}>
              Robot: {!shell.hasState ? "—" : shell.robotLink ? "đã nối" : "mất link"}
            </Chip>
            <Chip tone={driver ? "ok" : "idle"}>
              <KeyRound className="size-3.5" />
              {driver ? "Quyền lái" : "Chỉ xem"}
            </Chip>
            <Chip tone={shell.armed ? "warn" : "idle"}>
              {shell.armed ? "ĐÃ ARM" : "DISARM"}
            </Chip>
            <Chip tone={shell.source === "idle" ? "idle" : "ok"}>
              Nguồn lệnh: {SOURCE_LABEL[shell.source]}
            </Chip>
          </div>
        </div>
      </header>
    );
  }

  function ControlSettings({ shell }: { shell: ShellSnapshot }) {
    const linId = useId();
    const angId = useId();
    const codeId = useId();
    const [linText, setLinText] = useState(String(shell.speed.lin));
    const [angText, setAngText] = useState(String(shell.speed.ang));
    const [codeText, setCodeText] = useState("");
    const linValid = parseSpeed(linText) !== null;
    const angValid = parseSpeed(angText) !== null;

    function onLin(text: string) {
      setLinText(text);
      const lin = parseSpeed(text);
      if (lin !== null) setSpeed(lin, shell.speed.ang);
    }

    function onAng(text: string) {
      setAngText(text);
      const ang = parseSpeed(text);
      if (ang !== null) setSpeed(shell.speed.lin, ang);
    }

    function onSubmitCode(event: FormEvent<HTMLFormElement>) {
      event.preventDefault();
      if (codeText.trim() === "") return;
      setOperatorCode(codeText);
      setCodeText("");
    }

    const rejected = shell.hasCode && shell.hasState && shell.role !== "driver";

    return (
      <section
        aria-label="Cài đặt điều khiển"
        className="flex flex-wrap items-end gap-x-6 gap-y-3 border-b bg-muted/40 px-3 py-3 md:px-6"
      >
        <div className="flex gap-3">
          <div className="grid w-32 gap-1.5">
            <Label htmlFor={linId}>Tịnh tiến (m/s)</Label>
            <Input
              id={linId}
              inputMode="decimal"
              autoComplete="off"
              value={linText}
              aria-invalid={!linValid}
              className="tabular-nums"
              onChange={(e) => onLin(e.target.value)}
            />
          </div>
          <div className="grid w-32 gap-1.5">
            <Label htmlFor={angId}>Quay (rad/s)</Label>
            <Input
              id={angId}
              inputMode="decimal"
              autoComplete="off"
              value={angText}
              aria-invalid={!angValid}
              className="tabular-nums"
              onChange={(e) => onAng(e.target.value)}
            />
          </div>
        </div>

        {shell.hasCode ? (
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">Mã điều khiển</span>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                Đã lưu cho phiên này
              </span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setOperatorCode("")}
              >
                Xóa mã
              </Button>
            </div>
            {rejected ? (
              <span className="text-xs text-destructive">
                Mã chưa được chấp nhận hoặc đã có người khác đang lái.
              </span>
            ) : null}
          </div>
        ) : (
          <form onSubmit={onSubmitCode} className="grid gap-1.5">
            <Label htmlFor={codeId}>Mã điều khiển</Label>
            <div className="flex gap-2">
              <Input
                id={codeId}
                type="password"
                autoComplete="off"
                placeholder="Nhập mã để lái"
                value={codeText}
                className="w-44"
                onChange={(e) => setCodeText(e.target.value)}
              />
              <Button type="submit" variant="secondary">
                Xác nhận
              </Button>
            </div>
          </form>
        )}

        <div className="hidden flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground md:flex">
          <span className="flex items-center gap-1.5">
            <KbdGroup>
              <Kbd>W</Kbd>
              <Kbd>A</Kbd>
              <Kbd>S</Kbd>
              <Kbd>D</Kbd>
            </KbdGroup>
            tiến, trái, lùi, phải
          </span>
          <span className="flex items-center gap-1.5">
            <KbdGroup>
              <Kbd>Q</Kbd>
              <Kbd>E</Kbd>
            </KbdGroup>
            quay trái, phải
          </span>
          <span className="flex items-center gap-1.5">
            <Kbd>R</Kbd>
            arm
          </span>
          <span className="flex items-center gap-1.5">
            <KbdGroup>
              <Kbd>X</Kbd>
              <Kbd>Esc</Kbd>
            </KbdGroup>
            dừng và disarm
          </span>
        </div>
      </section>
    );
  }

  function Navigation() {
    const pathname = usePathname();
    return (
      <aside className="contents md:sticky md:top-0 md:flex md:h-svh md:w-56 md:shrink-0 md:flex-col md:border-r md:bg-sidebar md:text-sidebar-foreground">
        <div className="hidden border-b px-4 py-4 md:block">
          <div className="flex items-center gap-2">
            <span className="grid size-6 place-items-center rounded-sm bg-sidebar-primary text-xs font-bold text-sidebar-primary-foreground">
              M
            </span>
            <span className="text-sm font-semibold tracking-[0.18em]">MECANUM</span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Bảng điều khiển robot</p>
        </div>
        <nav
          aria-label="Điều hướng"
          className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-6 border-t bg-sidebar text-sidebar-foreground md:static md:z-auto md:flex md:flex-col md:gap-1 md:border-t-0 md:p-3"
        >
          {NAV.map(({ href, label, short, Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex flex-col items-center justify-center gap-0.5 px-1 py-2 text-[11px] leading-tight outline-none focus-visible:ring-3 focus-visible:ring-ring/50 md:flex-row md:justify-start md:gap-3 md:rounded-lg md:px-3 md:text-sm",
                  active
                    ? "font-medium text-sidebar-primary md:bg-sidebar-accent md:text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:text-foreground md:hover:bg-sidebar-accent/60",
                )}
              >
                <Icon className="size-5 md:size-4" />
                <span className="md:hidden">{short}</span>
                <span className="hidden md:inline">{label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
    );
  }

  export function AppShell({ children }: { children: ReactNode }) {
    const shell = useShell();

    useEffect(() => {
      startStore();
    }, []);

    return (
      <div className="flex min-h-svh flex-col md:flex-row">
        <Navigation />
        <div className="flex min-w-0 flex-1 flex-col pb-16 md:pb-0">
          <StatusBar shell={shell} />
          <ControlSettings shell={shell} />
          <main className="flex-1 px-3 py-4 md:px-6 md:py-6">{children}</main>
        </div>
      </div>
    );
  }
  ```

  **File 8: `app/client/src/app/layout.tsx`**

  ```tsx
  import "@/styles/globals.css";

  import type { Metadata } from "next";
  import { Roboto } from "next/font/google";

  import { AppShell } from "@/components/robot/app-shell";
  import { TooltipProvider } from "@/components/ui/tooltip";
  import { cn } from "@/lib/utils";
  import { KeyboardController } from "@/robot/keyboard";

  const roboto = Roboto({ subsets: ["latin", "vietnamese"], variable: "--font-sans" });

  export const metadata: Metadata = {
    title: "Mecanum - Bảng điều khiển",
    description: "Điều khiển và giám sát robot Mecanum theo thời gian thực",
  };

  export default function RootLayout({
    children,
  }: {
    children: React.ReactNode;
  }) {
    return (
      <html
        lang="vi"
        className={cn("h-full", "antialiased", "font-sans", roboto.variable)}
      >
        <body className="min-h-full">
          <TooltipProvider>
            <KeyboardController />
            <AppShell>{children}</AppShell>
          </TooltipProvider>
        </body>
      </html>
    );
  }
  ```

  **File 9: `app/client/src/app/page.tsx`**

  ```tsx
  export default function Home() {
    return (
      <section className="max-w-2xl">
        <h1 className="text-xl font-semibold tracking-tight">Tổng quan</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Vận tốc đo, tư thế, quỹ đạo và sức khỏe link (FR-08, FR-12).
        </p>
        <p className="mt-4 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
          Trang tạm, sẽ được thay ở T09. Bàn phím và thanh trạng thái vẫn hoạt động ở trang này.
        </p>
      </section>
    );
  }
  ```

  **File 10: `app/client/src/app/kinematics/forward/page.tsx`**

  ```tsx
  export default function Page() {
    return (
      <section className="max-w-2xl">
        <h1 className="text-xl font-semibold tracking-tight">Động học thuận</h1>
        <p className="mt-1 text-sm text-muted-foreground">Nhập tốc độ 4 bánh và xem chuỗi tính tới vận tốc thân, tư thế (FR-04).</p>
        <p className="mt-4 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
          Trang tạm, sẽ được thay ở T10. Bàn phím và thanh trạng thái vẫn hoạt động ở trang này.
        </p>
      </section>
    );
  }
  ```

  **File 11: `app/client/src/app/kinematics/inverse/page.tsx`**

  ```tsx
  export default function Page() {
    return (
      <section className="max-w-2xl">
        <h1 className="text-xl font-semibold tracking-tight">Động học ngược</h1>
        <p className="mt-1 text-sm text-muted-foreground">Nhập quãng đường và hướng, hoặc đích x, y, θ (FR-05, FR-06).</p>
        <p className="mt-4 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
          Trang tạm, sẽ được thay ở T11. Bàn phím và thanh trạng thái vẫn hoạt động ở trang này.
        </p>
      </section>
    );
  }
  ```

  **File 12: `app/client/src/app/dynamics/page.tsx`**

  ```tsx
  export default function Page() {
    return (
      <section className="max-w-2xl">
        <h1 className="text-xl font-semibold tracking-tight">Động lực học</h1>
        <p className="mt-1 text-sm text-muted-foreground">Lực và mô-men từng bánh theo thời gian thực (FR-07).</p>
        <p className="mt-4 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
          Trang tạm, sẽ được thay ở T12. Bàn phím và thanh trạng thái vẫn hoạt động ở trang này.
        </p>
      </section>
    );
  }
  ```

  **File 13: `app/client/src/app/lidar/page.tsx`**

  ```tsx
  export default function Page() {
    return (
      <section className="max-w-2xl">
        <h1 className="text-xl font-semibold tracking-tight">LiDAR</h1>
        <p className="mt-1 text-sm text-muted-foreground">Quét 360 độ dạng polar (FR-10).</p>
        <p className="mt-4 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
          Trang tạm, sẽ được thay ở T13. Bàn phím và thanh trạng thái vẫn hoạt động ở trang này.
        </p>
      </section>
    );
  }
  ```

  **File 14: `app/client/src/app/system/page.tsx`**

  ```tsx
  export default function Page() {
    return (
      <section className="max-w-2xl">
        <h1 className="text-xl font-semibold tracking-tight">Hệ thống</h1>
        <p className="mt-1 text-sm text-muted-foreground">RTT, độ trễ vòng lệnh, trạng thái thiết bị (FR-11).</p>
        <p className="mt-4 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
          Trang tạm, sẽ được thay ở T09. Bàn phím và thanh trạng thái vẫn hoạt động ở trang này.
        </p>
      </section>
    );
  }
  ```

  **Bước 3. Kiểm tra (chạy lần lượt trong `app/client`, báo kết quả nguyên văn của từng lệnh).**
  1. `npx tsc --noEmit -p .`: không in gì, exit code 0. Nếu còn báo `LayoutProps`, kiểm tra File 8 đã chép đúng (kiểu tường minh); nếu vẫn lỗi, trả `BLOCKED`.
  2. `npx eslint src`: không in gì, exit code 0. Nếu còn lỗi ở `carousel.tsx` hay `use-mobile.ts`, kiểm tra File 1; không sửa hai file đó.
  3. `npm test`: `Test Files  2 passed (2)` và `Tests  74 passed (74)` (34 test của `mecanum.test.ts` cộng 40 test mới của `control.test.ts`).
  4. `npm run build`: kết thúc không lỗi, phần `Route (app)` liệt kê đủ bảy route, tất cả `○ (Static)`: `/`, `/_not-found`, `/dynamics`, `/kinematics/forward`, `/kinematics/inverse`, `/lidar`, `/system`. Cảnh báo "Detected additional lockfiles" có thể xuất hiện, không sao. `next/font/google` (Roboto) cần tải font lúc build: nếu build lỗi vì không tải được font (mạng), trả `BLOCKED` kèm nguyên văn thông báo lỗi, không sửa code để né.
  5. `grep -rn "1\.89" src`: không in gì (exit code 1 của grep là đúng).
  6. `git status --short` (chỉ đọc) tại gốc worktree: chỉ được thấy `M app/client/eslint.config.mjs`, `M app/client/src/app/layout.tsx`, `M app/client/src/app/page.tsx`, bảy mục `??` mới (`src/robot/{protocol,control,store}.ts`, `keyboard.tsx`, `control.test.ts`, `src/components/robot/`, và các thư mục trang mới `src/app/{kinematics,dynamics,lidar,system}/`), cộng `M .claude/task/task.md` và `M .claude/plan/plan.md` đã có sẵn từ trước. `.next/`, `next-env.d.ts`, `tsconfig.tsbuildinfo` bị `.gitignore` bỏ qua. Nếu thấy file khác bị đổi, hoàn tác phần của mình và báo.

  **Bước 4. Báo cáo.** Trả: danh sách file đã tạo hoặc sửa, output nguyên văn năm lệnh ở Bước 3, và mọi chỗ phải dừng. Không tự commit.

  **Việc Sonnet làm khi review (không phải Haiku):** mở trình duyệt thật với app server T06 chạy `ROBOT_SIMULATE=true` (đặt `APP_ALLOWED_ORIGINS` đúng origin của trang), kiểm tra các mục `Đạt khi`: lái từ mọi trang, nhiều phím cộng vector, gõ trong ô nhập không chạy xe, `Esc` luôn dừng, rời tab gửi 0, chuyển trang không rớt WS (đếm kết nối ở `/health`), và nhìn giao diện ở độ rộng điện thoại.

  **Điểm cần Opus xác nhận hoặc mở:**
  - Task T08 `File:` và plan.md §3 thiếu `src/robot/control.ts`, `src/robot/control.test.ts`, `eslint.config.mjs` (Quyết định 7 và 8). Spec, plan và task không mâu thuẫn nhau ở T08 ngoài điểm này.
  - Dấu phím (Quyết định 5) là cách đọc FR-02, spec chỉ nêu trục.
  - `APP_ALLOWED_ORIGINS` mặc định chỉ có `http://100.119.83.63:3000`: mở web bằng `localhost` hay IP khác thì server trả 403 và thanh trạng thái hiện "Mất kết nối". Khi phát triển phải đặt biến này; T14 ghi vào hướng dẫn chạy.
  - Chưa phát hiện socket "treo im lặng" (không còn state nhưng chưa `onclose`): lúc đó thanh trạng thái vẫn hiện kết nối; an toàn vẫn đủ nhờ deadman app server và robot (SAF-03b, c). Có thể thêm ở T09.
  - `npm run build` cần tải Google Fonts (Roboto) lúc build; đã qua ở môi trường hiện tại, chưa kiểm chứng khi offline.

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
- Gia cố từ các review trước: bọc thân vòng lặp `broadcast_loop` và `watchdog_loop` trong try/except có log để lỗi một vòng không làm chết vòng lặp; chỉ chuyển tiếp `health`, `charge` sau khi kiểm tra kiểu và giá trị hữu hạn; test `telemetry.clear_robot()` khi mất link; `_authorized` của robot trả 401 thay vì lỗi 500 với header hỏng.
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
