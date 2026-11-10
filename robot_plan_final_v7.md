# Phương án v7: Điều khiển robot Mecanum bằng cử chỉ tay, xác thực khuôn mặt một lần, bám theo người

**Phần cứng:** Jetson Orin Nano 8GB · Astra S (RGB + depth) **cao 35 cm, nghiêng lên 20°, trước tâm robot 20 cm, cố định** · Đế **Mecanum** (STM32, firmware bên ngoài) · **LiDAR N10P** 360°, **cao 36 cm, trước tâm robot 10 cm** · Khung robot **40 × 40 cm**
**Hệ thống sẵn có (repo `mecanum_base`):** robot agent trên Jetson (`100.69.39.18`, WS `:8765`), app server FastAPI + web Next.js 16 trên máy `100.119.83.63`, nối qua Tailscale
**Thêm mới:** chế độ **Cử chỉ** (điều khiển bằng tay + bám theo người); **quản lý nhân viên và đăng ký khuôn mặt trên web**; chỉ nhân viên được cấp quyền mới điều khiển được
**Model:** YOLO cho phát hiện/bám người; nhận diện mặt, chống giả mạo, cử chỉ tay **tự xây dựng và huấn luyện** (được dùng dữ liệu công khai)

Bản này thay v6. Quyết định của người dùng (2026-11-10):

1. **Lệnh chuyển động đi thẳng từ camera vào Jetson rồi xuống robot**, không qua app server.
2. **Web bật/tắt chế độ Cử chỉ**: muốn điều khiển bằng cử chỉ thì web gửi một lệnh đưa robot vào chế độ Cử chỉ, sau đó mới tới các bước xác thực và điều khiển. Ngoài lệnh này, web chỉ theo dõi.
3. **Mất mạng thì robot dừng.**
4. **Web có trang quản lý nhân viên** (thêm, sửa, xóa, bật/tắt quyền) và **đăng ký khuôn mặt**. Không có tài khoản riêng: chỉ một người dùng web (giữ `OPERATOR_TOKEN` như hiện nay).
5. **Có cổng LiDAR** cho lệnh từ vision.
6. **Bám theo tốc độ của người, không đặt trần.**
7. Tốc độ cử chỉ cấu hình **theo đơn vị wire**.
8. Dừng khẩn vật lý: **nút tắt nguồn robot**.

Các chế độ (LOCKED, BIND, BIND-BACK, GESTURE, FOLLOW, HOLD, ESTOP) giữ nguyên. Khác biệt ở mục 18.

---

## 0. Quan hệ với quy tắc của repo

Các quyết định trên đi ngược một số quy tắc đang ghi trong `CLAUDE.md` và `spec.md`. Phải **ghi quyết định mới vào repo trước khi code**; nếu không, bước review theo ba file sẽ trả về không đạt.

| Quy tắc hiện tại | Thay đổi | Cách xử lý trong v7 |
|---|---|---|
| Arm là trạng thái của app server; không thêm đường đi vượt qua các lớp an toàn (SAF-02, `CLAUDE.md`) | Lệnh vision không qua app server | **D-09**: chế độ Cử chỉ chỉ bật được khi app server **đang arm** và driver gửi lệnh bật; app server giữ **heartbeat** xuống robot suốt chế độ. Mất arm, mất driver, mất heartbeat → robot agent tắt chế độ và chặn vision. Lệnh vision còn phải qua xác thực mặt, deadman writer, `ROBOT_MOTION_ENABLED`, `flag_stop`, cổng LiDAR |
| Link xuống robot chỉ có `cmd_vel` (FR-03, PROTO-2) | Thêm message phiên `mode` | **D-10**: PROTO-2 thêm `mode{gesture, seq}` (lệnh phiên, không mang vận tốc). Lệnh chuyển động trên link vẫn chỉ là `cmd_vel` |
| `SPEED_SCALE` chỉ chia trong `control.py`; robot không biết hệ số (SAF-01) | Lệnh vision không qua `control.py` | Vision xuất **đơn vị wire**; tốc độ cử chỉ cấu hình bằng đơn vị wire; bộ bám là vòng kín theo depth. Jetson vẫn không biết hệ số |
| Không thêm giới hạn tốc độ nếu người dùng chưa yêu cầu (SAF-04) | Người dùng yêu cầu cổng LiDAR, không yêu cầu trần tốc độ | **D-11**: cổng LiDAR (chặn, không kẹp tốc độ) chỉ cho nguồn vision. Không có trần tốc độ ở chế độ bám |
| Không có quản lý người dùng | Thêm quản lý nhân viên | **D-12**: dữ liệu nhân viên và embedding nằm trên Jetson; web quản lý qua app server, chỉ driver (`OPERATOR_TOKEN`) được thao tác |
| Firmware STM32 không sửa; SAF-08 chưa thử | Không đổi | Thử SAF-08 trước khi chạy thật |
| Không chạy động cơ thật khi người dùng chưa có mặt cạnh robot | Không đổi | Áp dụng cho mọi bước thử |

Cần sửa: `CLAUDE.md` (mục quy tắc), `spec.md` (FR-01 thêm trang, FR-03, SAF-01..04 thêm ngoại lệ cho nguồn vision, PROTO-2 thêm `mode`/heartbeat, thêm PROTO-3, PROTO-4), `plan.md` (D-09..D-12, cấu trúc thư mục).

---

## 1. Mục tiêu và yêu cầu

| # | Yêu cầu | Cách đáp ứng |
|---|---|---|
| 1 | Điều khiển bằng cử chỉ: tiến, lùi, trái, phải, bám theo người | Model cử chỉ tự huấn luyện; trái/phải dùng **đi ngang (vy)**; bám bằng YOLO + tracker + đặc trưng thân, theo tốc độ người |
| 2 | Chỉ nhân viên được cấp quyền | Danh sách nhân viên quản lý trên web; xác thực mặt một lần (chống giả mạo), gắn danh tính vào track |
| 3 | Bật chế độ từ web, sau đó điều khiển bằng cử chỉ | Lệnh `mode` từ web; lệnh chuyển động xử lý hoàn toàn trên Jetson |
| 4 | Mất mạng thì dừng | Heartbeat từ app server; mất > 0.5 s chặn vision, > 3 s tắt chế độ |
| 5 | Không phá hệ thống sẵn có | Lái tay từ web vẫn chạy như cũ và luôn thắng vision |

---

## 2. Hình học camera

### 2.1 Giới hạn Astra S

| Giới hạn | Thông số tham khảo | Ảnh hưởng |
|---|---|---|
| Tầm depth | ~0.4 – 2 m | < 0.4 m trả 0 |
| FOV | ~60° × 49.5° | Mỗi mét ngang ở khoảng cách s chiếm ~554/s px |
| Độ phân giải | 640×480 @ 30 fps | Mặt, tay nhỏ khi xa |
| Driver | OpenNI2 đã vendored cho arm64 trong repo (`robot/vendor/openni2/arm64`); `AstraSSource` đã có, đã yêu cầu registration depth→color | Rủi ro driver thấp hơn; vẫn phải chạy thử trên Jetson |

### 2.2 Camera thấy gì (cao 0.35 m, nghiêng lên 20°)

| Khoảng cách | Vùng độ cao thấy được | Ghi chú |
|---|---|---|
| 0.6 m | 0.30 – 0.94 m | Chân, hông |
| 0.8 m | 0.28 – 1.14 m | Chân, hông, bụng |
| 1.0 m | 0.27 – 1.34 m | Tay ngang bụng/ngực thấy rõ |
| 1.2 m | 0.25 – 1.54 m | Đến vai; chưa thấy mặt người đứng |
| 1.5 m | 0.23 – 1.84 m | Mặt người đứng ~43 px, nhìn từ dưới lên ~40°: không dùng để xác thực |

Hệ quả:
- Người đứng thẳng không xác thực mặt được → tư thế xác thực riêng (mục 6.1).
- Cử chỉ: đứng 0.9–1.3 m, tay ngang bụng–ngực, bàn tay ~36–50 px.
- Bám: camera thấy chân, hông, phần dưới thân; không thấy đầu, không đo được chiều cao.
- Camera nghiêng lên thấy đèn trần → ngược sáng; kiểm tra auto-exposure, cân nhắc LED trợ sáng.
- Mọi dữ liệu huấn luyện phải thu từ đúng camera ở đúng vị trí này.

---

## 3. Kiến trúc

### 3.1 Sơ đồ

```
           Máy app 100.119.83.63
┌─────────────────────────────────────────────────────────────┐
│ Web: /gesture (bật/tắt chế độ, theo dõi)                     │
│      /gesture/staff (nhân viên, đăng ký khuôn mặt)           │
│        │ /ws/operator (đã có) + message mới                  │
│ App server: arm, quyền lái (đã có)                           │
│   + mode Cử chỉ, heartbeat 5 Hz xuống robot                  │
│   + chuyển tiếp lệnh quản lý nhân viên, /video               │
└──────┬─────────────────────────────────┬────────────────────┘
       │ PROTO-2: cmd_vel, mode, hb       │ PROTO-3: quản lý nhân viên,
       ▼                                  ▼ enroll; lên: state, JPEG
┌──────────────────────── Jetson ─────────────────────────────┐
│ robot_agent (đã có, sửa)              vision_agent (MỚI)     │
│   ModeGuard: gesture on/off,            Astra S, TensorRT    │
│     heartbeat, arm                      state machine        │
│   CmdArbiter: app thắng vision   ◄──── vision_cmd 20 Hz      │
│   Cổng LiDAR (vision)            ────► robot_status 20 Hz    │
│   CmdVelWriter (deadman 250 ms)   PROTO-4 unix socket        │
│   N10P, STM32                           SQLite nhân viên     │
└─────────────────────────────────────────────────────────────┘
```

Lệnh chuyển động từ cử chỉ chỉ đi trên Jetson (vision → robot agent → STM32). Mạng chỉ mang lệnh bật/tắt, heartbeat, quản lý nhân viên và dữ liệu theo dõi.

### 3.2 Vision agent (mới)

- Gói `robot/vision_agent/`, process riêng, unit systemd riêng. Treo hay crash thì lệnh vision ngừng, deadman đưa về 0, robot agent không bị ảnh hưởng.
- Dùng lại `AstraSSource` từ `robot_agent.hardware`; robot agent vẫn không mở camera (D-07). Dùng `time.monotonic_ns()` cho mọi phép tính tuổi và dt.
- Khi chế độ Cử chỉ tắt: chỉ giữ camera (để xem video và đăng ký khuôn mặt), không chạy model điều khiển, `vision_cmd` luôn 0.

### 3.3 Bật/tắt chế độ Cử chỉ và heartbeat (PROTO-2 mở rộng)

**Luồng bật:**

1. Người dùng web (driver, đã nhập `OPERATOR_TOKEN`) bấm **Arm**, rồi **Bật chế độ Cử chỉ**.
2. App server kiểm tra: đúng driver, đang arm, link robot sống → gửi `mode{gesture: true, seq}` xuống robot agent, sau đó gửi `hb{seq}` **5 Hz** suốt thời gian bật.
3. Robot agent (`ModeGuard`) bật chế độ, báo vision qua PROTO-4 → vision vào **LOCKED** và bắt đầu chờ xác thực mặt.
4. Từ đây mọi bước (xác thực, BIND, cử chỉ, bám) diễn ra trên Jetson.

**Tắt chế độ** (robot agent chặn vision ngay, báo vision về trạng thái tắt, xóa gallery):

| Sự kiện | Ở đâu phát hiện |
|---|---|
| Bấm **Tắt chế độ Cử chỉ** trên web | App server gửi `mode{gesture: false}` |
| `Space` (dừng khẩn) | Client gửi `mode{false}` + `arm{false}`; app server gửi `mode{false}` và `cmd_vel` 0 |
| Disarm, driver ngắt kết nối | App server gửi `mode{false}` |
| Bất kỳ phím di chuyển/lệnh `cmd_vel` khác 0 từ web | Robot agent: lái tay thắng, tắt chế độ |
| **Mất heartbeat** | Robot agent: > **0.5 s** chặn vision (ghi 0); > **3 s** tắt chế độ, vision về trạng thái tắt |
| Mất link app server ↔ robot | Như mất heartbeat |

Như vậy **mất mạng thì robot dừng** trong khoảng 0.5 s cộng thời gian giảm tốc của firmware, không phải chờ cơ chế ping của WebSocket (2 s + 2 s). Mạng trở lại không tự bật lại: người dùng phải bấm bật lại và người điều khiển phải xác thực lại.

**Lệnh 0 từ app server:** app server gửi `cmd_vel` 0 khi watchdog bắn, khi disarm và khi nối lại link (`on_link_up`). Ở chế độ Cử chỉ, robot agent **bỏ qua `cmd_vel` bằng 0** từ app server (chúng không mang ý định lái tay); chỉ lệnh khác 0 mới được xem là lái tay. Dừng khẩn và disarm đã có `mode{false}` đi kèm nên vẫn dừng được.

### 3.4 Bộ phân xử ở robot agent (PROTO-4, unix socket cục bộ)

Kênh `/run/mecanum/vision.sock` (datagram, quyền `0660`).

| Chiều | Message | Nội dung |
|---|---|---|
| vision → robot | `vision_cmd{seq, t_mono_ns, vx, vy, wz, state, user}` | 20 Hz, gửi cả khi 0; **đơn vị wire** |
| robot → vision | `robot_status{t_mono_ns, mode, blocked, flag_stop, gz, lidar_ok}` | 20 Hz; `gz` từ IMU (đơn vị thực) để bù xoay cho tracker |
| robot → vision | Scan rút gọn 360 × u16 | 10 Hz, khi FOLLOW cần bám chân bằng LiDAR (mục 8.6) |

**`CmdArbiter`** (trong `drive.py`, trước `CmdVelWriter.set_cmd_vel`):

| Điều kiện | Kết quả |
|---|---|
| `cmd_vel` khác 0 từ app server | Lái tay: chuyển tiếp như cũ, **tắt chế độ Cử chỉ** |
| Chế độ Cử chỉ tắt | Chỉ nhận `cmd_vel` từ app server (hành vi cũ) |
| Chế độ bật, heartbeat ≤ 0.5 s, `vision_cmd` mới (≤ 100 ms, `seq` tăng), `state ∈ {GESTURE, FOLLOW, HOLD}` | Qua **cổng LiDAR** rồi `set_cmd_vel` |
| `vision_cmd` cũ, sai định dạng, `seq` lùi, sai trạng thái | Bỏ; writer về 0 sau deadman 250 ms |
| Cổng LiDAR chặn | Thay bằng 0 |

Mọi lớp sau đó của writer giữ nguyên: `ROBOT_MOTION_ENABLED`, deadman 250 ms, telemetry cũ > 0.5 s, `flag_stop`, giá trị ngoài `int16`.

### 3.5 App server ↔ vision agent (PROTO-3)

- Vision agent mở WS server `ws://100.69.39.18:8766/ws`, `Authorization: Bearer <VISION_LINK_TOKEN>`, chỉ bind IP Tailscale, theo mẫu D-01. **Không có message nào mang vận tốc.**
- Lên app server: `vision_state{mode, state, user, gesture, cmd, guide, fps, temps, events}` ≤ 10 Hz; frame JPEG nhị phân (`type u8 = 3, ver u8, seq u32, t_mono_ms u64` + JPEG), chỉ giữ khung mới nhất; kết quả các lệnh quản lý.
- Xuống vision (app server chỉ chuyển tiếp khi người gửi là driver): các lệnh quản lý nhân viên ở mục 3.7.
- App server: `vision_link.py` (dựng theo `robot_link.py`), route `/video` (MJPEG; quyền xem bằng cookie phiên cấp sau `hello` hợp lệ, vì `<img>` không gửi header), thêm `vision` vào `state` gửi web.
- Robot agent thêm vào `state` của PROTO-2: `mode`, `src` (`app | vision | none`), `vision{link, blocked, last_cmd_age_ms}`, `lidar_gate{blocked, min_m}`.

### 3.6 Trang `/gesture`

- Nút **Bật / Tắt chế độ Cử chỉ** (chỉ hiện khi là driver và đang arm).
- Video có overlay (bbox người đã bind, tay, nhãn cử chỉ, khung mặt khi xác thực, vùng LiDAR bị chặn).
- Trạng thái state machine, nhân viên đang điều khiển, cử chỉ và `cmd_vel` hiện tại, nguồn lệnh, FPS, nhiệt độ Jetson, trạng thái heartbeat.
- Gợi ý tư thế chữ to khi LOCKED/BIND/BIND-BACK.
- Nhật ký sự kiện gần đây.
- `Space` và phím di chuyển hoạt động như hệ thống cũ.

### 3.7 Quản lý nhân viên và đăng ký khuôn mặt (trang `/gesture/staff`)

Chỉ driver (đã nhập `OPERATOR_TOKEN`) mới thao tác được. Dữ liệu nằm trong SQLite trên Jetson; web không bao giờ nhận embedding hay ảnh khuôn mặt đã lưu.

**Dữ liệu nhân viên:**

| Trường | Ghi chú |
|---|---|
| `id` | Tự tăng |
| `code` | Mã nhân viên, duy nhất |
| `name` | Họ tên |
| `allowed` | Được phép điều khiển (bật/tắt mà không xóa) |
| `note` | Ghi chú (bộ phận...) |
| `created_at`, `updated_at` | |
| Số mẫu mặt, lần đăng ký gần nhất | Tính từ bảng `face_samples` |

`face_samples`: `id`, `employee_id`, embedding (mã hóa), điểm chất lượng, góc mặt ước lượng, thời điểm. Không lưu ảnh gốc.

**Thao tác (message PROTO-3, đi từ web qua app server):**

| Thao tác | Message | Ràng buộc |
|---|---|---|
| Danh sách | `staff_list` | |
| Thêm | `staff_create{code, name, note, allowed}` | `code` không trùng |
| Sửa | `staff_update{id, code?, name?, note?, allowed?}` | Tắt `allowed` của người đang điều khiển → vision về LOCKED ngay |
| Xóa | `staff_delete{id}` | Xóa luôn mọi mẫu mặt; người đang điều khiển → LOCKED ngay; web hỏi xác nhận |
| Bắt đầu đăng ký mặt | `enroll_start{id, replace}` | Chỉ khi chế độ Cử chỉ **tắt** (robot không chạy theo vision); `replace = true` xóa mẫu cũ khi lưu |
| Chụp mẫu | `enroll_capture` (hoặc tự chụp) | Mỗi mẫu phải qua kiểm tra chất lượng và chống giả mạo |
| Lưu / Hủy | `enroll_commit`, `enroll_cancel` | Cần đủ 8–10 mẫu đạt; hết 120 s không thao tác → tự hủy |
| Xóa mẫu mặt | `faces_clear{id}` | Giữ nhân viên, xóa mẫu |

**Luồng đăng ký khuôn mặt:**

1. Chọn nhân viên → **Đăng ký khuôn mặt**. Vision vào trạng thái ENROLL (chỉ khi chế độ Cử chỉ tắt).
2. Web hiện video trực tiếp, khung mặt và chỉ báo: khoảng cách, độ cao mặt, góc mặt, độ nét, độ sáng, chống giả mạo (đạt/không đạt).
3. Người đăng ký đứng ở **tư thế xác thực** (mục 6.1). Vision tự chụp khi mọi chỉ báo đạt và góc mặt khác các mẫu đã có (chính diện, hơi trái, hơi phải, hơi ngẩng, có/không kính nếu có); có nút chụp tay.
4. Web hiện các mẫu đã chụp (ảnh xem trước chỉ nằm trong RAM của phiên đăng ký) với điểm chất lượng; cho xóa từng mẫu.
5. Đủ 8–10 mẫu → **Lưu**: vision tính embedding, kiểm tra người này **không trùng** với nhân viên khác (điểm tương đồng với người khác phải dưới ngưỡng; nếu trùng thì cảnh báo và không lưu), ghi DB, xóa ảnh xem trước.
6. Ghi sự kiện vào nhật ký.

Gợi ý: đăng ký lại sau vài tháng, hoặc khi người đó thay đổi nhiều (để râu, đổi kính) hay khi tỉ lệ từ chối nhầm của họ tăng.

---

## 4. State machine (trong vision agent)

| Trạng thái | Ý nghĩa | `vision_cmd` |
|---|---|---|
| **OFF** | Chế độ Cử chỉ tắt; chỉ camera, video | 0 |
| **ENROLL** | Đang đăng ký khuôn mặt (chỉ từ OFF) | 0 |
| **LOCKED** | Chế độ bật, chờ xác thực mặt | 0 |
| **BIND** | Mặt khớp; người đứng dậy lùi về vùng cử chỉ, thu gallery `front` | 0 |
| **BIND-BACK** | Người quay lưng, thu gallery `back` | 0 |
| **GESTURE** | Điều khiển bằng tay | Theo lệnh tay |
| **FOLLOW** | Bám người đã bind | Bộ điều khiển bám |
| **HOLD** | Mất dấu, chờ nhận lại | 0 (trừ bước quay tìm) |
| **ESTOP** | Lỗi | 0 |

Chuyển trạng thái:

- OFF → LOCKED: robot agent báo chế độ bật. Bất kỳ → OFF: robot agent báo chế độ tắt (mục 3.3); xóa gallery.
- OFF ↔ ENROLL: `enroll_start` / `enroll_commit`, `enroll_cancel`, hết thời gian.
- LOCKED → BIND: mặt khớp ≥ 5/8 khung liên tiếp, nhân viên `allowed = true`, chống giả mạo đạt, gán được vào đúng một track người.
- BIND → GESTURE: người đứng 0.9–1.3 m cùng `track_id`, đủ mẫu `front`. BIND → LOCKED: quá 8 s, ID đổi, hoặc người khác vào vùng < 1.5 m.
- GESTURE → BIND-BACK: xòe tay giữ ≥ 1 s. BIND-BACK → FOLLOW: đủ 10–20 khung lưng cùng ID. BIND-BACK → GESTURE: quá 10 s hoặc ID đổi.
- GESTURE → HOLD: không thấy người đã bind > 3 s.
- FOLLOW → GESTURE: cử chỉ thoát (mục 8.5).
- FOLLOW → HOLD: mất track > 1.5 s, điểm danh tính thấp liên tục, ID switch.
- HOLD → trạng thái trước: nhận lại ổn định 10–15 khung. HOLD → LOCKED: hết 10–15 s.
- Bất kỳ (khi bật) → LOCKED: hết phiên 20–30 phút; nhân viên đang điều khiển bị tắt quyền hoặc bị xóa.
- Bất kỳ → ESTOP: mất `robot_status` > 0.5 s, `flag_stop`, lỗi camera. ESTOP → LOCKED (hoặc OFF): khi lỗi hết và robot đứng yên ≥ 2 s.

---

## 5. Phân công model

| Phần | Cách làm | Công cụ |
|---|---|---|
| Phát hiện người + keypoint, bám | YOLOv8n(-pose) fine-tune trên ảnh từ dưới lên, thân dưới bị cắt, cả mặt trước và lưng | Ultralytics + ByteTrack |
| Phát hiện mặt + 5 landmark | Tự huấn luyện YOLOv8n-pose, 1 lớp `face` | Ultralytics |
| Nhận diện mặt | Tự thiết kế, huấn luyện nền trên dữ liệu công khai, tinh chỉnh bằng dữ liệu Astra S | PyTorch |
| Chống giả mạo | Lớp 1 depth (không học) + lớp 2 CNN RGB-D tự huấn luyện | PyTorch |
| Cử chỉ tay | Hai tầng: phát hiện tay → phân loại | YOLOv8n + CNN nhỏ |
| Đặc trưng thân | Giai đoạn 1 không cần học; giai đoạn 2 ReID nếu cần | Mục 8 |

Huấn luyện trên PC có GPU. Jetson chỉ suy luận: ONNX → TensorRT FP16, build engine trên Orin Nano.

**Lưu ý phiên bản:** repo yêu cầu Python 3.10. JetPack 6 đi kèm Ubuntu 22.04 / Python 3.10 nên khớp; JetPack 5 đi kèm Python 3.8, sẽ vênh với repo và với binding TensorRT. Kiểm tra bằng `cat /etc/nv_tegra_release` hoặc `dpkg -l nvidia-jetpack` ở giai đoạn V0.

### Lịch chạy theo trạng thái

| Trạng thái | Model chạy | Tần suất |
|---|---|---|
| LOCKED | Phát hiện mặt, nhận diện, chống giả mạo; YOLO người | Mỗi khung; nhận diện trên khung đạt chất lượng |
| BIND / BIND-BACK | YOLO người, ByteTrack, đặc trưng thân | Mỗi khung |
| GESTURE | YOLO người, ByteTrack, tay + phân loại | Mỗi khung |
| FOLLOW | YOLO người, ByteTrack, danh tính, tay vùng hông | Danh tính 3–5 Hz; tay 10 Hz |
| HOLD | YOLO người, ByteTrack, danh tính | Mỗi khung |

---

## 6. Xác thực khuôn mặt

### 6.1 Tư thế xác thực

| Khoảng cách | Độ cao tâm mặt | Vị trí trong khung | Cỡ mặt |
|---|---|---|---|
| 0.7 m | 0.7 – 0.8 m | Gần giữa | ~100–106 px |
| 0.8 m | 0.7 – 0.9 m | Gần giữa | ~86–95 px |
| 0.8 m | 1.0 – 1.1 m | Sát mép trên | ~76–81 px |
| 0.6 m | ≥ 0.9 m | Ra khỏi khung | — |

**Khuyến nghị:** đứng cách 0.7–0.9 m, ngồi xổm hoặc khom sâu để mặt ở 0.7–0.95 m, ngẩng nhìn ống kính. Mặt ~85–105 px; depth ở ~0.8–1.0 m rất tốt cho chống giả mạo.

Robot không có màn hình, nên gợi ý tư thế ("Lại gần hơn", "Hạ thấp mặt", "Nhìn vào camera", "Đứng dậy, lùi lại 1 m", "Quay lưng lại") hiển thị chữ to trên trang `/gesture` của web. Người giám sát đọc cho người xác thực, hoặc chính người đó nhìn điện thoại; trang này chỉ hiển thị, không gửi lệnh chuyển động. Phiên kéo dài 20–30 phút và HOLD nhận lại không cần xác thực lại, nên việc ngồi xuống không lặp lại thường xuyên. Có phương án cho người không ngồi được: khom, đứng 0.9–1.0 m, chấp nhận mặt ~70 px, đo FRR riêng.

### 6.2 Nhận diện mặt tự xây dựng

1. **Huấn luyện nền** trên dữ liệu công khai nhiều danh tính (CASIA-WebFace, WebFace, Glint...). Đây là bài tập lớn nên dùng cho nghiên cứu/học tập; vẫn đọc điều khoản từng bộ, nhiều bộ cấm thương mại hoặc phân phối lại.
2. **Tinh chỉnh** bằng ảnh Astra S ở tư thế xác thực (nhìn từ dưới lên, ngược sáng đèn trần).

| Thành phần | Lựa chọn |
|---|---|
| Đầu vào | 112×112 căn theo 5 landmark |
| Backbone | MobileFaceNet hoặc ResNet-18 rút gọn (1–5 triệu tham số) |
| Đầu ra | Embedding 128/256, L2, cosine |
| Mất mát | ArcFace / CosFace |
| Tăng cường | Lật, mờ, giảm phân giải, JPEG, sáng/tương phản, ngược sáng, che một phần, biến dạng phối cảnh từ dưới lên |
| Kiểm chứng | TAR tại FAR cố định (benchmark chuẩn như LFW để so sánh, cộng tập Astra S) |

**Baseline đối chứng:** chạy một model huấn luyện sẵn trên cùng tập kiểm thử (chỉ để đo, không triển khai), để biết model tự xây dựng kém do dữ liệu nền hay do miền camera.

### 6.3 Phát hiện mặt

YOLOv8n-pose, lớp `face`, 5 keypoint; WIDER FACE cộng ảnh tự thu ở tư thế xác thực.

### 6.4 Chống giả mạo

| Lớp | Phương pháp | Dữ liệu |
|---|---|---|
| 1 | Khớp mặt phẳng vùng depth của mặt (mặt thật lồi, ảnh/màn hình phẳng) | Chọn ngưỡng |
| 2 | CNN nhỏ 4 kênh RGB + depth | Mặt thật + tấn công |

Tấn công cần thu: ảnh in (uốn cong, khoét mắt), điện thoại, máy tính bảng, video; đặc biệt **cầm điện thoại sát xuống trước camera thấp**. Đo APCER/BPCER trên thiết bị chưa dùng khi huấn luyện. Mặt nạ 3D ngoài phạm vi.

### 6.5 Quyết định

- Mặt ≥ 75–80 px, gần chính diện, không mờ, không cháy sáng.
- 1:N: điểm cao nhất vượt ngưỡng và cách điểm thứ hai một margin.
- Mở khóa khi khớp ≥ 5/8 khung và chống giả mạo đạt.
- Enroll 8–10 ảnh **trên robot, ở tư thế xác thực**, qua trang `/gesture/staff` (mục 3.7); giữ nhiều vector/người.
- FAR ≤ ~0.1%, FRR ≤ ~3–5%; ghi rõ số cặp mạo danh đã dùng để đo FAR.

### 6.6 Dữ liệu huấn luyện từ nhân viên

Nhiều phiên, tư thế xác thực, 0.7–1.0 m, nhiều điều kiện sáng, có/không kính; chia tập theo người và phiên; có tập người lạ.

### 6.7 BIND: chuyển từ tư thế cúi sang đứng

1. Mặt khớp → chọn bbox người chứa tâm mặt; hai bbox cùng chứa → từ chối.
2. Web: "Đứng dậy và lùi lại khoảng 1 m". Tracker giữ `track_id`, hỗ trợ bằng liên tục depth (người gần nhất phía trước, depth đổi mượt).
3. Người khác vào vùng < 1.5 m hoặc ID đổi → hủy, LOCKED.
4. Người đứng yên ở 0.9–1.3 m → 5–10 khung làm gallery `front`: màu quần, phần áo thấy được, bề rộng hông/thân theo mét, màu giày.
5. Quá 8 s → LOCKED.

Gallery chỉ trong RAM, xóa khi hết phiên.

---

## 7. Điều khiển bằng cử chỉ

### 7.1 Vùng đứng

0.9–1.3 m, tay trước người ở ngang bụng–ngực (≈ 0.9–1.2 m).

### 7.2 Bộ lệnh (tận dụng Mecanum)

Hệ trục của repo: x tiến, y sang trái, wz dương ngược chiều kim đồng hồ.

| Cử chỉ | Lệnh | `cmd_vel` (đơn vị wire) |
|---|---|---|
| Nắm tay, không thấy tay | DỪNG | (0, 0, 0) |
| Chỉ ngón trỏ lên | Tiến (về phía người) | (+v_x, 0, 0) |
| Chỉ ngón trỏ xuống | Lùi (ra xa người) | (−v_lùi, 0, 0) |
| Chỉ sang bên phải của ảnh | **Đi ngang** sang phải robot | (0, −v_y, 0) |
| Chỉ sang bên trái của ảnh | **Đi ngang** sang trái robot | (0, +v_y, 0) |
| Xòe bàn tay giữ ≥ 1 s | Vào BÁM THEO | (0, 0, 0) rồi BIND-BACK |
| Lớp `KHÁC` | DỪNG | (0, 0, 0) |

**Vì sao trái/phải là đi ngang chứ không xoay:** camera gắn phía trước; nếu robot xoay, camera quay khỏi người điều khiển, mất người và robot dừng. Mecanum đi ngang được mà vẫn giữ camera hướng về người.

Quy ước "chỉ về hướng muốn robot đi": khi đối diện robot, người chỉ sang trái của chính họ = sang phải của robot = bên phải ảnh (camera không lật gương). Có thể đổi trong cấu hình.

**Đơn vị:** `v_x`, `v_y`, `v_lùi` là **tốc độ lệnh** cấu hình trong `.env` của Jetson **bằng đơn vị wire**, để Jetson không cần biết `SPEED_SCALE`. Với hệ số đo được 1.89: muốn thực tế ~0.15 m/s thì đặt ~0.08 (wire); muốn ~0.10 m/s thì đặt ~0.053. Ghi chú quy đổi này ngay cạnh biến trong `.env.example`. Đây là độ lớn lệnh, không phải giới hạn; tăng/giảm tốc do firmware STM như PHY-6.

### 7.3 Model hai tầng

| Tầng | Việc | Model |
|---|---|---|
| 1 | Tìm bàn tay | YOLOv8n `hand`, hoặc crop quanh cổ tay (keypoint YOLO-pose) của người đã bind |
| 2 | Phân loại | CNN nhỏ, crop phóng lên 96×96 (rộng hơn bàn tay, gồm cổ tay và cẳng tay), có thể thêm depth |
| 3 | Làm mượt | Bỏ phiếu 5 khung, ổn định ≥ 3 khung mới đổi lệnh |

### 7.4 Dữ liệu

| Hạng mục | Gợi ý |
|---|---|
| Số người | ≥ 30 |
| Lượng | Theo người × phiên × điều kiện (ví dụ 30 × 3 × 4), không chỉ đếm ảnh |
| Điều kiện | Tay trái/phải, tay áo, 0.9–1.3 m, nhiều độ cao tay, đèn trần phía sau |

Lớp `KHÁC`: vẫy, cầm điện thoại, chỉ vào vật, tay khi nói, bán nắm, đút túi, vung khi đi. Lật ngang phải đổi nhãn TRÁI ↔ PHẢI; xoay ±15°.

### 7.5 Đánh giá

Ma trận nhầm lẫn, kích hoạt nhầm mỗi giờ, độ trễ cử chỉ → lệnh → bánh quay (đo trên Jetson, không qua mạng), kiểm thử trên người không có trong tập huấn luyện.

### 7.6 Chỉ nhận lệnh từ đúng người

Chỉ tay thuộc track đã bind; tay cách thân ≤ ~0.4 m theo trục sâu.

### 7.7 Tiến, lùi, đi ngang và LiDAR

- Tiến: chặn khi người/vật phía trước < 0.6 m theo depth **hoặc** vùng trước toàn depth 0 (vật có thể gần hơn 0.4 m). Kiểm tra này nằm trong vision agent.
- Lùi và đi ngang: camera không thấy, nhưng LiDAR N10P 360° thấy. **Cổng LiDAR** trong robot agent (mục 13.2, đã duyệt) chặn mọi lệnh vision có vật cản theo hướng chuyển động; robot agent đọc scan trực tiếp, không trễ mạng.
- LiDAR quét ở mặt phẳng cao 36 cm nên không thấy vật thấp hơn. Người dùng xác nhận môi trường **không có vật thấp hơn 36 cm**, nên không cần thêm cảm biến thấp. Nếu sau này đổi môi trường thì phải xem lại điểm này.

---

## 8. Bám theo người

### 8.1 Camera thấy gì

Ở 0.8–1.2 m phía sau: chân, hông, phần dưới lưng (~0.25–1.5 m). Robot thực chất bám theo thân dưới.

### 8.2 Các tầng

| Khâu | Giai đoạn 1 | Giai đoạn 2 |
|---|---|---|
| Phát hiện | YOLOv8n(-pose) fine-tune ảnh thân dưới từ dưới lên | Giữ nguyên |
| Bám | ByteTrack + ràng buộc depth + **bù xoay bằng gyro** | BoT-SORT nếu vẫn nhảy ID |
| Nhận diện lại | Màu quần/áo thấy được, bề rộng thân, màu giày | ReID nhỏ tự huấn luyện |
| Vị trí ngoài khung hình | — | Bám chân bằng LiDAR N10P (mục 8.6) |

**Bù chuyển động:** dùng `gz` của IMU trong `robot_status` (đơn vị thực, repo không nhân hệ số cho IMU) để dịch dự đoán Kalman theo góc xoay mỗi khung: Δu ≈ (gz·Δt / 60°) × 640 px. Dịch ngang khi đi ngang ít ảnh hưởng hơn và có thể bỏ qua ở giai đoạn 1.

Trọng số khởi điểm: màu 0.55, bề rộng thân 0.25, quỹ đạo/depth 0.2; khi có ReID: ReID 0.6, màu 0.25, bề rộng 0.15.

### 8.3 Kiểm tra danh tính (3–5 Hz)

| Tình huống | Hành động |
|---|---|
| Điểm ≥ cao | Tiếp tục, cập nhật gallery (EMA, ≤ 20 vector) |
| Thấp ≤ điểm < cao | Tiếp tục, giảm tốc, không cập nhật |
| < thấp N lần | HOLD |
| Chồng lấn > 30% hoặc depth gần nhau | Đóng băng: giảm tốc/dừng, không cập nhật |
| ID đổi đột ngột | HOLD, verify |

### 8.4 Điều khiển chuyển động (Mecanum)

Bám **theo tốc độ của người, không có trần** (quyết định người dùng).

- `wz`: giữ người ở giữa khung (P), vì camera chỉ nhìn phía trước. Camera nằm trước tâm robot 20 cm nên khi xoay, ảnh dịch cả do quay lẫn do camera di chuyển ngang; bù xoay bằng gyro vẫn đúng ở bậc một, hiệu chỉnh độ lợi bằng thử thực tế.
- `vx`: bộ điều khiển **PD theo khoảng cách** để bám kịp tốc độ người: `vx = Kp·(d − d_ref) + Kd·ḋ`, trong đó `ḋ` là tốc độ thay đổi khoảng cách (lọc thông thấp). Thành phần `Kd·ḋ` cho robot tăng tốc ngay khi người tăng tốc thay vì đợi khoảng cách giãn ra. `d_ref` ≈ 1.0 m.
- Nguồn khoảng cách `d`: median depth vùng hông khi ≤ 1.8 m; **khi người ra xa hơn tầm depth (> ~1.8–2 m), dùng khoảng cách từ cụm chân trên LiDAR** (mục 8.6). Không có trần tốc độ nên người đi nhanh sẽ kéo khoảng cách vượt 2 m; nếu chỉ dùng depth, robot mất khoảng cách và phải dừng, nên phần ghép LiDAR được đưa lên **giai đoạn 1**.
- Lệnh vượt phạm vi `int16` của khung STM32 vẫn bị writer loại (SAF-04 có sẵn); đây không phải trần mà là giới hạn định dạng.
- `vy`: mặc định 0; có thể dùng để né vật cản ở giai đoạn 2.
- Đây là vòng kín theo depth và vị trí ảnh, nên độ lợi tự hấp thụ chênh lệch `SPEED_SCALE`; hiệu chỉnh độ lợi bằng thử thực tế.
- Người dừng → robot dừng. Mất depth vùng hông > 0.5 s → 0.
- Trước khi vào HOLD: quay tại chỗ về hướng thấy người lần cuối, tối đa 1–2 s.
- Cổng LiDAR vẫn áp dụng: có vật cản theo hướng chạy thì dừng, kể cả khi đang bám nhanh.
- Không có trần nên **rủi ro chính** là bám nhầm người ở tốc độ cao; các quy tắc giảm tốc khi điểm danh tính thấp và đóng băng khi chồng lấn (mục 8.3) càng quan trọng.

### 8.5 Thoát khi đang bám

| Cách | Ghi chú |
|---|---|
| Đưa một tay ra sau lưng ngang hông, xòe bàn tay hướng về robot, giữ ≥ 1 s | Tay ở ~0.9–1.0 m luôn trong khung khi bám |
| `Space` trên web | Dừng khẩn, tắt chế độ Cử chỉ (mục 3.3) |
| "Tắt chế độ Cử chỉ" trên web | Robot dừng, vision về OFF |

Sau khi thoát: FOLLOW → GESTURE, robot dừng.

### 8.6 LiDAR N10P giúp bám (giai đoạn 1 cho khoảng cách, giai đoạn 2 cho bám ngoài khung hình)

N10P quét ở **độ cao 36 cm**, cắt ngang **cẳng chân** người (dưới đầu gối), nên thấy được hai chân dưới dạng hai cụm điểm nhỏ cách nhau 10–40 cm.

- **Giai đoạn 1:** dùng cụm chân để đo khoảng cách khi người ra ngoài tầm depth (mục 8.4).
- **Giai đoạn 2:** bám vị trí khi người ra khỏi FOV camera.

Khi chiếu track camera sang khung LiDAR: camera ở `x = +0.20 m`, LiDAR ở `x = +0.10 m` so với tâm robot (cùng trục dọc), nên điểm từ camera chỉ cần tịnh tiến 0.10 m về phía sau trước khi so với scan. Hai cảm biến gần như cùng độ cao nên không cần bù độ cao. Bám ngoài khung hình: khi người bước ra ngoài FOV 60° của camera, LiDAR vẫn thấy hai chân. Ghép: chiếu track camera (góc + depth) sang khung LiDAR, gắn cụm điểm chân gần nhất; khi camera mất người mà cụm chân vẫn liền mạch, tiếp tục quay về phía cụm chân thay vì vào HOLD. Danh tính chỉ xác nhận lại bằng camera. Robot agent gửi thêm scan rút gọn (360 × u16) cho vision qua PROTO-4 ở 10 Hz khi cần.

### 8.7 HOLD

1. Dừng khi mất target > 1.5 s (sau bước quay tìm).
2. 10–15 s quét; nhận lại khi điểm ≥ cao liên tục 10–15 khung.
3. Nhận lại → trạng thái trước; không được → LOCKED.

---

## 9. Dữ liệu và huấn luyện

| Bước | Việc | Sản phẩm |
|---|---|---|
| 1 | Quy trình thu và gắn nhãn theo đúng vị trí camera | Quy ước |
| 2 | Thu RGB + depth (vision agent có chế độ ghi): tư thế xác thực, cử chỉ, thân dưới trước/lưng, tấn công giả mạo | Dữ liệu thô |
| 3 | Gắn nhãn (CVAT/Label Studio), DVC | Train/val/test theo người |
| 4 | Huấn luyện, theo dõi (MLflow/W&B) | Ứng viên |
| 5 | ONNX → TensorRT FP16, so độ chính xác | Engine |
| 6 | Đo trên robot, thu ca lỗi, lặp lại | Cải thiện |

Thứ tự: cử chỉ và phát hiện người trước; mặt và chống giả mạo sau.

---

## 10. Truyền hình ảnh lên web

- Orin Nano không có NVENC → JPEG trên CPU (OpenCV/PyTurboJPEG), 640×480 hoặc 480×360, quality ~60, 10–15 fps, vẽ overlay trước khi nén.
- Vision agent → app server qua PROTO-3 → web `/video`. Chỉ nén khi app server đang nối.
- Video không nằm trên đường lệnh chuyển động. Nhưng **heartbeat** đi cùng mạng đó, nên mất mạng thì robot dừng (mục 3.3).

Hiệu năng kỳ vọng (cần đo): 20–30 fps pipeline. `nvpmodel` cao, `jetson_clocks`, quạt, theo dõi nhiệt.

---

## 11. Cấu trúc thư mục bổ sung

```
mecanum_base/
├─ deploy/vision-agent.service            # MỚI
├─ robot/
│  ├─ robot_agent/
│  │  ├─ drive.py                         # + ModeGuard, CmdArbiter, cổng LiDAR
│  │  ├─ server.py                        # + nhận mode/hb (PROTO-2), + mode/src/vision/lidar_gate trong state
│  │  ├─ local_link.py                    # MỚI: unix socket PROTO-4
│  │  └─ config.py                        # + VISION_MOTION_ENABLED, VISION_SOCKET, ROBOT_FOOTPRINT (0.40 × 0.40), LIDAR_POSE (x = +0.10), CAMERA_POSE (x = +0.20, z = 0.35, nghiêng 20°), ngưỡng cổng LiDAR
│  ├─ vision_agent/                       # MỚI
│  │  ├─ __main__.py
│  │  ├─ config.py                        # tốc độ lệnh (đơn vị wire), ngưỡng, engine, token
│  │  ├─ server.py                        # WS PROTO-3: state, JPEG, lệnh quản lý nhân viên
│  │  ├─ pipeline.py                      # capture + inference theo trạng thái
│  │  ├─ gesture_fsm.py                   # state machine + bộ điều khiển cmd_vel
│  │  ├─ face.py  person.py  body.py  hand.py  legs.py   # legs: cụm chân từ LiDAR
│  │  ├─ enroll.py                        # phiên đăng ký khuôn mặt
│  │  ├─ store.py                         # SQLite: employees, face_samples (mã hóa), events
│  │  └─ record.py                        # ghi dữ liệu huấn luyện
│  └─ tests/test_vision.py                # FSM, PROTO-4, arbiter, ModeGuard, cổng LiDAR, store (không cần GPU)
├─ app/server/app_server/
│  ├─ control.py                          # + mode Cử chỉ (chỉ driver, phải arm), heartbeat
│  ├─ robot_link.py                       # + gửi mode/hb
│  ├─ vision_link.py                      # MỚI
│  └─ main.py                             # + /video, + chuyển tiếp lệnh nhân viên (chỉ driver), + state.vision
├─ app/client/src/
│  ├─ app/gesture/page.tsx                # MỚI: bật/tắt chế độ, theo dõi
│  ├─ app/gesture/staff/page.tsx          # MỚI: danh sách, thêm/sửa/xóa, đăng ký khuôn mặt
│  └─ robot/{protocol,store,control}.ts   # + mode, vision, staff; Space gửi kèm mode{false}
└─ training/                              # MỚI, chạy trên PC có GPU
```

Thêm extras `vision` trong `pyproject.toml`. `VISION_SIMULATE=true` phát video và chuỗi trạng thái giả để kiểm thử arbiter, ModeGuard và web không cần camera (theo tinh thần NFR-06).

---

## 12. Chuỗi lệnh và độ trễ

```
Web: Arm → Bật chế độ Cử chỉ → app server: mode{true}, hb 5 Hz → robot_agent ModeGuard → vision: LOCKED

Cử chỉ → vision_agent (vision_cmd, đơn vị wire, 20 Hz)
       → unix socket → robot_agent CmdArbiter (chế độ bật? hb ≤ 0.5 s? vision_cmd ≤ 100 ms? cổng LiDAR)
       → CmdVelWriter (chu kỳ 50 ms, deadman 250 ms, telemetry ≤ 0.5 s, flag_stop)
       → STM32 (firmware bên ngoài, ramp gia tốc)
```

Ước tính: camera + suy luận + làm mượt 3 khung ~150–200 ms; socket cục bộ < 1 ms; writer ≤ 50 ms. Tổng từ lúc đổi cử chỉ đến khi bánh đổi lệnh ~0.2–0.25 s, không phụ thuộc mạng. Mất mạng → chặn trong ≤ 0.5 s.

---

## 13. An toàn

### 13.1 Các lớp

| Lớp | Nội dung |
|---|---|
| Vision agent | Mặc định 0: không thấy tay, `KHÁC`, mất người, ngoài vùng, lỗi; chặn tiến theo depth; chỉ nhận tay của track đã bind; chỉ nhân viên `allowed` |
| ModeGuard (robot agent) | Chế độ chỉ bật bằng lệnh web khi app server đang arm; heartbeat > 0.5 s chặn, > 3 s tắt; lái tay khác 0 tắt chế độ |
| CmdArbiter + cổng LiDAR | `VISION_MOTION_ENABLED`; lệnh vision mới và đúng trạng thái; vật cản theo hướng chạy → 0 |
| Writer (đã có) | `ROBOT_MOTION_ENABLED`, deadman 250 ms, telemetry cũ > 0.5 s, `flag_stop`, giá trị ngoài `int16` |
| STM32 | Chưa biết có watchdog: **thử SAF-08 trước** |
| Web | `Space` → `mode{false}` + disarm + lệnh 0 |
| Vật lý | **Nút tắt nguồn robot** |

- Vision agent crash hoặc treo → không còn `vision_cmd` → writer về 0 sau 250 ms.
- Robot agent crash → không còn ai ghi xuống STM32; an toàn lúc này phụ thuộc watchdog của firmware (SAF-08) và nút tắt nguồn.
- **Nút tắt nguồn** dừng mọi thứ nhưng cũng tắt Jetson: sau đó phải chờ khởi động lại, và nên kiểm tra hệ thống file nếu tắt khi đang ghi. Nếu sau này có thể, một nút dừng khẩn cắt riêng nguồn động cơ sẽ tốt hơn.
- Khi thử nghiệm: luôn có người đứng cạnh robot và một người giữ web sẵn `Space`, đúng quy tắc repo.

### 13.2 Cổng LiDAR (đã duyệt)

Chỉ áp dụng cho nguồn vision, trong `CmdArbiter`, mỗi lệnh:

1. Dựng **hình vuông thân xe 0.40 × 0.40 m** quanh tâm robot (`ROBOT_FOOTPRINT`), tức mép trước, sau, trái, phải cách tâm 0.20 m. Chuyển mỗi điểm LiDAR sang khung tâm robot: `x_r = x_lidar + 0.10`, `y_r = y_lidar` (LiDAR trước tâm 10 cm). Nếu bánh hay phần nào nhô ra ngoài khung 40 × 40 thì cộng thêm vào kích thước này.
2. Dự đoán vị trí thân xe sau thời gian `t_check` (gợi ý 0.5 s, cộng thời gian giảm tốc) theo `(vx, vy, wz)` hiện tại; xét các điểm LiDAR rơi vào **vùng quét** giữa thân hiện tại và thân dự đoán, nới thêm lề an toàn (gợi ý 0.15 m).
3. Có điểm trong vùng đó, hoặc scan cũ > 300 ms, hoặc LiDAR lỗi → thay bằng 0 và báo `lidar_gate{blocked, min_m}` lên web.
4. Lệnh 0 luôn qua (để robot dừng được).

Vì không kẹp tốc độ mà chỉ chặn, vùng quét tự rộng ra khi lệnh lớn (đúng với chế độ bám không trần).

**Che khuất do chính robot:** người dùng xác nhận LiDAR không quét vào phần nào của xe, nên không cần mặt nạ góc. Vẫn nên có một kiểm tra tự động khi khởi động: nếu có tia nào luôn báo khoảng cách nằm trong khung 40 × 40 thì báo lỗi lên web, vì điều đó nghĩa là có vật gắn thêm vào xe hoặc LiDAR bị lệch.

Ví dụ khoảng cách: điểm ngay trước mép trước nằm ở `x_r = 0.20 m`, tức chỉ cách LiDAR 0.10 m theo trục x; điểm ngay sau mép sau cách LiDAR 0.30 m. Vì vậy vùng an toàn quanh LiDAR không đối xứng, và mọi phép kiểm tra phải tính theo khung tâm robot chứ không theo khoảng cách thô của LiDAR.

### 13.3 Rủi ro khi chỉ xác thực một lần

| Rủi ro | Cách giảm |
|---|---|
| Mất danh tính khi đứng dậy sau xác thực | BIND có thời hạn, liên tục depth, hủy khi có người khác lại gần |
| Chân hai người lẫn nhau khi bám | Depth, đóng băng khi chồng lấn, HOLD khi không chắc; cụm chân LiDAR |
| Bám nhầm ở tốc độ cao (không có trần) | Giảm tốc khi điểm danh tính thấp, đóng băng khi chồng lấn, cổng LiDAR |
| Phiên dài | 20–30 phút; xác thực lại khi HOLD thất bại |
| Gallery học nhầm | Không cập nhật khi chồng lấn/điểm thấp |
| Nhân viên bị thu hồi quyền khi đang điều khiển | Tắt `allowed` hoặc xóa → LOCKED ngay |

---

## 14. Pháp lý và dữ liệu

- Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 và Nghị định 356/2025/NĐ-CP có hiệu lực từ 01/01/2026; dữ liệu nhận dạng khuôn mặt là dữ liệu sinh trắc học, thuộc nhóm nhạy cảm.
- Cần: thông báo mục đích, sự đồng ý của người được thu dữ liệu, thời hạn lưu, quyền xóa, bảo mật thiết bị lưu trữ và truyền tải.
- Embedding chỉ lưu trên Jetson, mã hóa; không gửi lên app server hay web; nhật ký sự kiện lưu trên Jetson. Ảnh gốc huấn luyện lưu nơi kiểm soát truy cập, xóa khi không cần.
- Dữ liệu công khai: đọc điều khoản từng bộ (nhiều bộ chỉ cho nghiên cứu).

---

## 15. Thông số khởi điểm (hiệu chỉnh bằng dữ liệu thật)

| Tham số | Giá trị gợi ý |
|---|---|
| Vùng xác thực | 0.7–0.9 m, mặt ở 0.7–0.95 m |
| Mặt tối thiểu | ≥ 75–80 px |
| Số khung khớp | ≥ 5/8 |
| Số mẫu đăng ký | 8–10, nhiều góc; tự hủy phiên sau 120 s không thao tác |
| Thời hạn BIND / BIND-BACK | 8 s / 10 s |
| Vùng cử chỉ | 0.9–1.3 m, tay ngang bụng–ngực |
| Tốc độ lệnh cử chỉ (đơn vị wire) | Tiến/ngang ~0.08, lùi ~0.053 (≈ 0.15 / 0.10 m/s thực với hệ số 1.89) |
| Khoảng cách bám `d_ref` | ~1.0 m (0.8–1.2 m) |
| Bộ bám | PD theo khoảng cách, không trần; depth ≤ 1.8 m, LiDAR xa hơn |
| Chặn tiến (depth) | < 0.6 m hoặc vùng trước toàn 0 |
| Cổng LiDAR | Thân 0.40 × 0.40 m, LiDAR tại x = +0.10 m; vùng quét theo `t_check` ≈ 0.5 s + lề 0.15 m; scan > 300 ms → 0 |
| Heartbeat | 5 Hz; > 0.5 s chặn vision; > 3 s tắt chế độ |
| `vision_cmd` / `robot_status` | 20 Hz / 20 Hz; tuổi tối đa `vision_cmd` 100 ms |
| Kiểm tra danh tính | 3–5 Hz |
| Chồng lấn bbox | 30% |
| Quay tìm trước HOLD | ≤ 1–2 s |
| Mất track → dừng | 1.5 s |
| Cửa sổ HOLD | 10–15 s |
| Hiệu lực phiên | 20–30 phút |
| Deadman writer | 250 ms (đã có) |

---

## 16. Chỉ số đánh giá

| Chỉ số | Mục tiêu |
|---|---|
| FAR / FRR mặt (tư thế xác thực) | FAR ≤ 0.1% (ghi số cặp), FRR ≤ 3–5% |
| Tấn công giả mạo vượt qua | Gần 0% |
| Đăng ký khuôn mặt một người | ≤ ~1 phút; không lưu được mẫu trùng người khác |
| BIND gắn đúng người | ≥ 95%, không bao giờ gắn nhầm |
| Thời gian ngồi xuống → GESTURE | ≤ ~10 s |
| Nhầm cử chỉ sau bỏ phiếu | < ~2% |
| Kích hoạt nhầm mỗi giờ | Về gần 0 |
| Cử chỉ DỪNG → writer ghi 0 | p95 ≤ 250 ms |
| Rút mạng (Tailscale) → writer ghi 0 | ≤ 0.5 s |
| `Space` → robot dừng, chế độ tắt | ≤ 550 ms (theo NFR-02) |
| Tắt/treo vision agent → writer ghi 0 | ≤ 300 ms |
| Cổng LiDAR: đặt vật cản theo hướng chạy | 100% dừng trước vật |
| Bám người đi nhanh dần | Giữ khoảng cách ổn định, không vào HOLD vì mất depth |
| Bám nhầm khi chen ngang | Phải vào HOLD |
| FPS, nhiệt | ≥ 20 fps, ổn định 30–60 phút |

---

## 17. Lộ trình (giai đoạn 2 của repo)

Trước khi code: ghi D-09..D-12 vào `plan.md`; sửa FR-01, FR-03, SAF-01..04, PROTO-2 và `CLAUDE.md`; thêm PROTO-3, PROTO-4 và các mã FR/SAF/NFR mới vào `spec.md`; thêm task vào `task.md`; đối chứng chéo ba file.

| Giai đoạn | Việc | Cổng hoàn thành |
|---|---|---|
| V0 | Kiểm tra JetPack/Python 3.10/TensorRT; chạy `AstraSSource` trên Jetson (RGB + depth 30 fps, registration, ngược sáng); quay thử tư thế xác thực, vùng cử chỉ, cảnh bám; **thử SAF-08**; kiểm tra bánh có nhô ra ngoài khung 40 × 40 không; chạy thử kiểm tra tự che khi khởi động | Gỡ rủi ro phần cứng |
| V1 | PROTO-2 `mode`/`hb`, ModeGuard, `local_link.py`, CmdArbiter, cổng LiDAR + test; vision agent khung gửi 0; PROTO-3 + `/video` + trang `/gesture`; `VISION_SIMULATE` | Bật/tắt chế độ từ web; rút mạng → chặn ≤ 0.5 s; arbiter đúng mọi ca; cổng LiDAR chặn đúng trên mô phỏng |
| V2 | Store nhân viên + trang `/gesture/staff` (thêm/sửa/xóa, bật/tắt quyền); ghi dữ liệu; thu cử chỉ + người; huấn luyện YOLO người, model cử chỉ | CRUD chạy trên web; đạt chỉ số cử chỉ, phát hiện người |
| V3 | GESTURE chạy thật (nhấc bánh → chạy chậm, người dùng có mặt), đi ngang, chặn tiến, cổng LiDAR trên robot thật | Lệnh đúng hướng; dừng đúng khi mất tay, rút mạng, `Space`, có vật cản |
| V4 | Thu dữ liệu mặt + tấn công; huấn luyện phát hiện, nhận diện (kèm baseline), chống giả mạo; **luồng đăng ký khuôn mặt trên web**; LOCKED → BIND | FAR/FRR, giả mạo đạt; đăng ký ≤ 1 phút |
| V5 | BIND chuyển tư thế, BIND-BACK, tracker bù xoay, FOLLOW với PD + khoảng cách LiDAR, HOLD, thoát sau lưng | Bám đúng người, bám kịp khi người đi nhanh, dừng khi mất dấu |
| V6 | Bám ngoài khung bằng LiDAR (nếu cần); ReID (nếu cần); hiệu chỉnh; kiểm thử an toàn tổng thể | Báo cáo mục 16 |
| V7 | `vision-agent.service`, tài liệu vận hành, phát hành theo git-flow | Chạy ổn định nhiều giờ |

---

## 18. Khác biệt so với v6

| Nội dung | v6 | v7 |
|---|---|---|
| Vào chế độ Cử chỉ | Vision tự chạy từ khi khởi động | **Web bật chế độ** (driver, đang arm), sau đó mới xác thực |
| Mất mạng | Robot vẫn chạy theo cử chỉ | **Heartbeat 5 Hz**: > 0.5 s chặn, > 3 s tắt chế độ |
| Lệnh 0 từ app server | Đưa vision về LOCKED | Bị bỏ qua ở chế độ Cử chỉ; chỉ lệnh khác 0 mới là lái tay; `Space` gửi kèm `mode{false}` |
| PROTO-2 | Không đổi | Thêm `mode`, `hb` (lệnh phiên, không mang vận tốc) |
| Cổng LiDAR | Đề xuất | **Đã duyệt**; vùng quét theo thân xe 40 × 40, LiDAR lệch tâm 10 cm |
| Bám theo | Có thể có trần | **Không trần**, PD theo khoảng cách; khoảng cách từ LiDAR khi > tầm depth (đưa lên giai đoạn 1) |
| Nhân viên | Lệnh trên Jetson | **Trang web**: thêm, sửa, xóa, bật/tắt quyền, đăng ký khuôn mặt, kiểm tra trùng người |
| Trạng thái | Không có OFF/ENROLL | Thêm **OFF**, **ENROLL** |
| Vị trí cảm biến | Chưa biết | Camera trước tâm 20 cm, cao 35 cm; LiDAR trước tâm 10 cm, cao 36 cm, không tự che; khung 40 × 40 cm |
| Vật thấp | Cân nhắc cảm biến thấp | Không cần (môi trường không có vật < 36 cm) |
| Dừng khẩn vật lý | Chưa biết | Nút tắt nguồn robot |

---

## 19. Câu hỏi còn lại

Chỉ còn hai việc kiểm tra ở V0, trước khi chạy thật:

1. Thử **SAF-08**: nhấc bánh, gửi một lệnh tốc độ thấp rồi ngừng gửi, xem firmware STM32 có tự dừng không.
2. Xác định **phiên bản JetPack** (`cat /etc/nv_tegra_release`) để chọn đúng TensorRT và kiểm tra Python 3.10.
