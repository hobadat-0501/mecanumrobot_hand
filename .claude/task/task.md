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
- Trạng thái: TODO · Plan: P1 · Phụ thuộc: T02
- Spec: FIX-3, FIX-4, FIX-5, FIX-6, SAF-02, SAF-03, SAF-04, SAF-05, SAF-06
- File: `robot/robot_agent/drive.py`, `robot/tests/test_robot.py`
- Đạt khi: test bao phủ `set_cmd_vel` không chặn khi serial chậm, deadman 250 ms, không kẹp tốc độ, giá trị ngoài int16 bị loại và ghi 0, telemetry cũ và cờ dừng ép 0, tự phục hồi sau lỗi ghi mà không chạy lại lệnh cũ, `MOTION_ENABLED=false` chỉ ghi 0.
- Work order: _(Sonnet điền)_

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
- Trạng thái: TODO · Plan: P3 · Phụ thuộc: T01
- Spec: PHY-1, PHY-2, PHY-3, PHY-4, PHY-5, PHY-6, NFR-04
- File: `app/client/src/robot/{mecanum,motion,mecanum.test}.ts`, `app/client/package.json` (thêm vitest)
- Đạt khi: các test vector trong PHY-2, PHY-3, PHY-5 qua; thuận rồi ngược trả lại đầu vào; bộ bám đạt tiêu chí xong trên mô hình giả lập.
- Work order: _(Sonnet điền)_

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
