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
- Trạng thái: CODED · Plan: P2 · Phụ thuộc: T01
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
