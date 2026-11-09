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
