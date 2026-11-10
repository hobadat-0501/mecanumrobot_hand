# SPEC — Web điều khiển robot Mecanum (giai đoạn 1)

Trạng thái: **ĐÃ DUYỆT 2026-11-09; bổ sung v7 (chế độ Cử chỉ) 2026-11-10**. Nguồn bổ sung: [robot_plan_final_v7.md](../../robot_plan_final_v7.md). Đối chiếu: [plan.md](../plan/plan.md) · [task.md](../task/task.md)

Quy ước mã: `FR` chức năng, `SAF` an toàn, `FIX` lỗi code cũ, `PROTO` giao thức, `PHY` vật lý,
`NFR` phi chức năng, `A` giả định. Cột **Task** phải khớp 1-1 với dòng `Spec:` trong task.md.

## 1. Phạm vi

- Trong phạm vi: website điều khiển, app server, robot agent, bàn phím, động học thuận/ngược, động lực học, LiDAR.
- Trong phạm vi (v7): chế độ Cử chỉ (điều khiển bằng tay, bám theo người), xác thực khuôn mặt một lần, quản lý nhân viên, vision agent trên Jetson, cổng LiDAR cho nguồn vision.
- Ngoài phạm vi: SLAM/điều hướng, điều khiển từng bánh, tài khoản người dùng web riêng (chỉ một driver giữ `OPERATOR_TOKEN`), cảm biến cho vật thấp hơn 36 cm, nút dừng khẩn cắt riêng nguồn động cơ.

Địa chỉ: app (client + server) `100.119.83.63`, web `:3000`, API/WS `:8000`. Robot `100.69.39.18`, WS `:8765`; vision agent cùng máy robot, WS `:8766`.

## 2. Yêu cầu chức năng

| Mã | Yêu cầu | Task |
|---|---|---|
| FR-01 | Các trang: `/` tổng quan, `/kinematics/forward`, `/kinematics/inverse`, `/dynamics`, `/lidar`, `/system`. Chuyển trang bằng điều hướng phía client, không làm rớt kết nối. Giao diện tiếng Việt. Từ v7 thêm `/gesture` và `/gesture/staff`. | T08, T21, T22 |
| FR-02 | Điều khiển bàn phím nằm ở root layout, hoạt động ở mọi trang. `W/S` hoặc `↑/↓`: vx; `A/D` hoặc `←/→`: vy; `Q/E`: wz. Chiều dương: x tiến, y sang trái, wz ngược chiều kim đồng hồ, nên `W`/`↑` vx+, `S`/`↓` vx−, `A`/`←` vy+, `D`/`→` vy−, `Q` wz+, `E` wz−. Nhiều phím cộng thành vector (đi chéo được). `R` arm, `Space` là phím dừng khẩn duy nhất (thay `X` và `Esc`): hủy mọi lần chạy, gửi 0 và disarm. Bỏ qua phím di chuyển khi focus ở ô nhập; `Space` luôn có hiệu lực. Gửi theo timer 20 Hz khi đang giữ phím, không dùng auto-repeat của OS. Có ô chỉnh tốc độ, không chặn trên (SAF-04). | T08 |
| FR-03 | Lệnh chuyển động duy nhất trên toàn hệ thống là `cmd_vel (vx, vy, wz)`. Web không gửi tốc độ bánh, không gửi đích xuống server hay robot. Link xuống robot ngoài `cmd_vel` chỉ có lệnh phiên `mode`, `hb` (PROTO-2), không mang vận tốc. Nguồn vision (D-09) sinh `cmd_vel` ngay trên Jetson, không đi qua mạng. | T04, T05, T08, T18, T20 |
| FR-04 | Động học thuận: nhập 4 tốc độ bánh rad/s và thời gian chạy (mặc định 3 s). Hiển thị realtime chuỗi `ω_i → v_i = r·ω_i → vx, vy, wz → ẋ, ẏ, θ̇ (= ω), ω̇`, và thành phần dư (trượt bánh) theo PHY-3. Hiện cảnh báo, không chặn, khi `\|vx\|+\|vy\|+lever·\|wz\|` vượt 1.6 m/s. Nút chạy gửi cmd_vel đã tính. | T10 |
| FR-05 | Động học ngược, kiểu A: nhập quãng đường (m) + hướng (độ, so với thân xe tại lúc bấm chạy). Hiển thị 4 tốc độ bánh cần có và tiến độ. | T11 |
| FR-06 | Động học ngược, kiểu B: nhập đích `x, y, θ` theo khung odometry (A-3). Người dùng chọn giữa kiểu A và B trên cùng trang. | T11 |
| FR-07 | Trang động lực học hiển thị realtime: Fx, Fy, Mz, lực dọc từng bánh `F_d,i`, mô-men `τ_i`, % so với mô-men định mức, cảnh báo khi vượt định mức. | T12 |
| FR-08 | Toàn bộ số liệu hiển thị là realtime qua WS, trạng thái tới web tối đa 20 Hz: vận tốc đo, tư thế, lệnh hiện hành, IMU, điện áp, cờ dừng, sức khỏe link. | T06, T08, T09 |
| FR-09 | Thanh trạng thái toàn cục ở mọi trang: kết nối, arm/disarm, nút dừng khẩn, nguồn lệnh hiện tại, nhập mã điều khiển. | T08, T09 |
| FR-10 | Trang LiDAR vẽ scan dạng polar bằng canvas, 5–10 Hz. | T13 |
| FR-11 | Trang hệ thống: RTT, độ trễ vòng lệnh, trạng thái STM32/LiDAR/writer, số lỗi, dữ liệu sạc (nếu có). | T09 |
| FR-12 | Odometry `x, y, θ` trên app server, có nút reset; hiển thị quỹ đạo gần đây ở trang tổng quan. | T06, T09 |
| FR-13 | Trang `/gesture`: nút Bật/Tắt chế độ Cử chỉ (chỉ hiện khi là driver và đang arm); video có overlay (`/video`), trạng thái FSM, nhân viên đang điều khiển, cử chỉ, `cmd_vel` và nguồn lệnh, FPS, nhiệt độ, trạng thái heartbeat, vùng LiDAR bị chặn, gợi ý tư thế chữ to, nhật ký sự kiện. Trang chỉ hiển thị và bật/tắt chế độ, không gửi vận tốc. | T20, T21 |
| FR-14 | Trang `/gesture/staff`: danh sách, thêm, sửa, xóa nhân viên (`code` duy nhất, `name`, `note`, `allowed`), bật/tắt quyền không xóa dữ liệu; chỉ driver thao tác được; xóa phải xác nhận. Tắt quyền hoặc xóa người đang điều khiển đưa vision về LOCKED ngay. | T22 |
| FR-15 | Đăng ký khuôn mặt trên web (chỉ khi chế độ Cử chỉ tắt): video trực tiếp với chỉ báo chất lượng, tự chụp 8–10 mẫu nhiều góc, xem trước chỉ trong RAM, lưu chỉ khi không trùng nhân viên khác và đạt chống giả mạo; hết 120 s không thao tác tự hủy. Web không bao giờ nhận embedding hay ảnh đã lưu. | T22, T25 |

## 3. Yêu cầu an toàn

| Mã | Yêu cầu | Task |
|---|---|---|
| SAF-01 | Hệ số hiệu chỉnh tốc độ `SPEED_SCALE` (cấu hình app server, mặc định 1.0, đo thực tế 1.89): `cmd_vel` chia hệ số cả ba thành phần **chỉ trong `control.py`**, telemetry `vx, vy, wz` nhân lại **chỉ trong `telemetry.py`**, cùng một giá trị cấu hình. Hệ số không có trong client, payload tới web hay UI; web luôn thấy đơn vị thực. Ngoại lệ (D-09): lệnh nguồn vision xuất thẳng đơn vị wire từ cấu hình Jetson, không qua `control.py`; Jetson không biết hệ số. | T05, T06, T08, T14, T18 |
| SAF-02 | Mặc định disarm. App server khởi động ở disarm. Robot có `ROBOT_MOTION_ENABLED` mặc định `false`; khi `false` chỉ ghi vận tốc 0. Arm là trạng thái của app server, kết thúc ở đó, không gửi xuống robot. Mất link robot thì tự disarm; không arm được khi link đang mất. Chế độ Cử chỉ chỉ bật được khi đang arm (SAF-09). | T03, T05, T06, T14, T18, T20 |
| SAF-03 | Chuỗi tự dừng: (a) web thả phím, mất focus cửa sổ, ẩn tab thì gửi 0 và hủy chạy tự động; (b) app server không nhận lệnh 250 ms, hoặc operator ngắt kết nối, hoặc disarm thì gửi `cmd_vel` 0; (c) robot không nhận lệnh 250 ms hoặc mất link thì tự ghi 0. Lệnh đã hết hạn không được chạy lại khi link phục hồi. Ở chế độ Cử chỉ, `cmd_vel` bằng 0 từ app server bị robot bỏ qua; `Space` gửi kèm `mode{false}`. | T03, T04, T06, T08, T14, T18, T20, T21 |
| SAF-04 | Không đặt giới hạn tốc độ phần mềm ở bất kỳ tầng nào (quyết định của người dùng). App server và robot vẫn loại giá trị không hữu hạn; giá trị vượt phạm vi `int16` của khung STM32 bị loại, không kẹp, và gửi 0 thay thế. Cổng LiDAR (SAF-11) chỉ chặn lệnh vision, không kẹp tốc độ; không có trần tốc độ ở chế độ bám. | T03, T05, T08, T14, T18 |
| SAF-05 | Writer ép 0 khi telemetry cũ hơn 0.5 s hoặc firmware bật cờ dừng. | T03, T14 |
| SAF-06 | Writer gặp lỗi ghi thì báo lỗi, xóa lệnh, tự thử lại; sau khi phục hồi vẫn xuất 0 cho đến khi có lệnh mới. | T03 |
| SAF-07 | Xác thực: link robot dùng `ROBOT_LINK_TOKEN`, robot chỉ bind IP Tailscale, kết nối hợp lệ mới nhất thay kết nối cũ. Operator: `hello` kèm `OPERATOR_TOKEN`, kiểm tra Origin; không có mã thì chỉ xem. Một operator giữ quyền lái tại một thời điểm. | T04, T05, T14 |
| SAF-08 | Firmware STM32 không được sửa. Trước khi chạy thật chỉ quan sát hành vi của firmware (nhấc bánh khỏi mặt đất, gửi một lệnh tốc độ thấp rồi ngừng gửi) để biết nó có tự dừng khi mất lệnh không. Nếu không, ghi nhận rủi ro và chờ người dùng quyết định; lớp bảo vệ duy nhất phía Jetson là deadman của writer. Dừng khẩn vật lý: nút tắt nguồn robot. | T15, T17 |
| SAF-09 | `ModeGuard` (robot agent): chế độ Cử chỉ chỉ bật bằng `mode{gesture:true}` từ app server khi đang arm và đúng driver; app server gửi `hb` 5 Hz suốt chế độ. Heartbeat > 0.5 s chặn vision (ghi 0); > 3 s tắt chế độ, vision về OFF, xóa gallery. Disarm, driver ngắt, `Space`, mất link, `cmd_vel` khác 0 từ app server đều tắt chế độ. Mạng trở lại không tự bật lại. | T18, T20 |
| SAF-10 | `CmdArbiter` (robot agent, trước `CmdVelWriter`): `cmd_vel` khác 0 từ app server luôn thắng và tắt chế độ; chế độ tắt thì chỉ nhận app server; chế độ bật thì nhận `vision_cmd` khi heartbeat ≤ 0.5 s, `vision_cmd` ≤ 100 ms, `seq` tăng, `state ∈ {GESTURE, FOLLOW, HOLD}`, `VISION_MOTION_ENABLED`; ngoài ra bỏ, writer về 0 sau deadman. Mọi lớp writer cũ giữ nguyên. | T18 |
| SAF-11 | Cổng LiDAR cho nguồn vision: thân 0.40 × 0.40 m, LiDAR lệch tâm +0.10 m (khung tâm robot), vùng quét giữa thân hiện tại và thân dự đoán sau `t_check` (gợi ý 0.5 s) cộng lề 0.15 m; có điểm trong vùng, scan cũ > 300 ms hoặc LiDAR lỗi → 0 và báo `lidar_gate`; lệnh 0 luôn qua. Kiểm tra tự che khi khởi động. | T17, T18, T24 |
| SAF-12 | Nhân viên chỉ điều khiển được khi `allowed`; thu hồi quyền hoặc xóa → LOCKED ngay; phiên 20–30 phút rồi xác thực lại; BIND hết hạn → LOCKED; vision agent crash hoặc treo → writer về 0 ≤ 300 ms; mất `robot_status` > 0.5 s, `flag_stop`, lỗi camera → ESTOP. | T22, T25, T26 |

## 4. Lỗi code cũ phải sửa

| Mã | Vấn đề (vị trí trước refactor) | Yêu cầu | Task |
|---|---|---|---|
| FIX-1 | `hardware.py:238` `read(128)` gây trễ tới 100 ms | Đọc theo `in_waiting`, tối thiểu 1 byte | T02 |
| FIX-2 | `hardware.py:117-119` bỏ frame phụ, `latest_aux` luôn `None` | Giải mã và lưu theo A-4 | T02 |
| FIX-3 | `teleop.py:47` chỉ nhận một phím rời rạc | Thay bằng `set_cmd_vel(vx, vy, wz)` liên tục | T03 |
| FIX-4 | `teleop.py:74` ghi serial khi giữ lock | Ô lệnh không chặn; ghi serial ngoài lock của lệnh | T03 |
| FIX-5 | `teleop.py:90-92` một lỗi làm writer chết hẳn | Vòng lặp tự phục hồi theo SAF-06 | T03 |
| FIX-6 | `teleop.py:39` tự arm khi khởi động | Theo SAF-02 | T03 |
| FIX-7 | Độ mới tính bằng đồng hồ hệ thống (`hardware.py:241`, `teleop.py:65-69`) | Dùng monotonic cho mọi phép tính độ tuổi và dt | T02 |
| FIX-8 | `hardware.py:472` bỏ sót vòng mới khi mất gói | Phát hiện vòng mới khi góc giảm hơn 180° | T02 |
| FIX-9 | `hardware.py:55` `int()` cắt bớt: `0.1/1.89` (52.91 mm/s) thành 52 thay vì 53 | Dùng `round()`; thêm test vector này | T02 |

## 4b. Vision (v7)

| Mã | Yêu cầu | Task |
|---|---|---|
| VIS-01 | State machine OFF, ENROLL, LOCKED, BIND, BIND-BACK, GESTURE, FOLLOW, HOLD, ESTOP và chuyển trạng thái theo v7 §4. Mặc định `vision_cmd` = 0 (không thấy tay, `KHÁC`, mất người, ngoài vùng, lỗi). | T19, T24, T26 |
| VIS-02 | Xác thực mặt một lần: tư thế xác thực, khớp ≥ 5/8 khung, 1:N có margin, FAR ≤ 0.1%, FRR ≤ 3–5%; nhận diện mặt tự huấn luyện; gắn danh tính vào đúng một track (BIND). | T25 |
| VIS-03 | Chống giả mạo hai lớp (depth phẳng + CNN RGB-D); tấn công vượt qua gần 0%. | T25 |
| VIS-04 | Cử chỉ tay hai tầng (phát hiện tay → phân loại, bỏ phiếu 5 khung): DỪNG, tiến, lùi, đi ngang trái/phải, xòe tay giữ ≥ 1 s vào BÁM THEO. Tiến chặn theo depth (< 0.6 m hoặc vùng trước toàn 0). Chỉ nhận tay của track đã bind. Tốc độ cử chỉ cấu hình theo đơn vị wire. | T23, T24 |
| VIS-05 | Bám người theo tốc độ của người, không trần: `wz` P giữ người giữa khung (bù xoay bằng gyro), `vx` PD theo khoảng cách (depth ≤ 1.8 m, cụm chân LiDAR xa hơn), giảm tốc khi điểm danh tính thấp, đóng băng khi chồng lấn, HOLD khi mất dấu, thoát bằng cử chỉ sau lưng. | T23, T26, T27 |

## 5. Giao thức

| Mã | Nội dung | Task |
|---|---|---|
| PROTO-1 | Web ↔ app server: `ws://100.119.83.63:8000/ws/operator`. Web → server: `hello{token}`, `cmd_vel{seq,vx,vy,wz,src}`, `arm{on}`, `odom_reset`, `mode{gesture}` (chỉ driver, phải arm), lệnh nhân viên/đăng ký (PROTO-3, chỉ driver). Server → web (JSON ≤ 20 Hz): `state{link,session{armed,has_driver,mode,role},vel,pose,cmd,imu,voltage,flag_stop,charge,health,last_cmd_seq,gesture,vision}` (`gesture` = `mode/src/vision/lidar_gate` do robot báo, `vision` = trạng thái từ vision agent; không có vận tốc nào ngoài `vel`/`cmd`); LiDAR qua frame nhị phân theo PROTO-2. Mọi số vận tốc theo đơn vị web. | T05, T06, T08 |
| PROTO-2 | App server (client) ↔ robot (server): `ws://100.69.39.18:8765/ws`, header `Authorization: Bearer`. Xuống robot chỉ có `cmd_vel{seq,vx,vy,wz}` (đơn vị wire). Lên: `state` JSON ≤ 50 Hz gồm `t_mono_ns` (thời điểm mẫu STM32), `last_cmd_seq`, `vel{vx,vy,wz}`, `imu{ax,ay,az,gx,gy,gz}`, `voltage`, `flag_stop`, `charge{current_a,red,charging,set_state}` hoặc null, `health{stm,lidar,writer}`; `scan` nhị phân: header `type u8, ver u8, seq u32, t_mono_ms u64`, thân 360 × `u16` mm little-endian, 0 là không có điểm (tổng 734 byte, `type = 2`, `ver = 1`; ô 0 là hướng +x của robot, tăng dần ngược chiều kim đồng hồ, mỗi ô 1°, điểm gần nhất thắng; app server chuyển tiếp tối đa 10 Hz, chỉ giữ khung mới nhất). Hàng đợi gửi chỉ giữ bản mới nhất. **v7 (D-10):** xuống robot thêm lệnh phiên `mode{gesture, seq}` và `hb{seq}` (5 Hz khi chế độ bật), không mang vận tốc; `state` thêm `mode`, `src` (`app`, `vision`, `none`), `vision{link,blocked,last_cmd_age_ms}`, `lidar_gate{blocked,min_m}`. | T04, T06, T13, T18, T20 |
| PROTO-3 | App server (client) ↔ vision agent (server): `ws://100.69.39.18:8766/ws`, `Authorization: Bearer <VISION_LINK_TOKEN>`, chỉ bind IP Tailscale. Không có message nào mang vận tốc. Lên: `vision_state{mode,state,user,gesture,cmd,guide,fps,temps,events}` ≤ 10 Hz; frame JPEG nhị phân (`type u8 = 3, ver u8, seq u32, t_mono_ms u64` + JPEG), chỉ giữ khung mới nhất; kết quả lệnh quản lý. Xuống (chỉ chuyển tiếp khi người gửi là driver): `staff_list`, `staff_create`, `staff_update`, `staff_delete`, `enroll_start`, `enroll_capture`, `enroll_commit`, `enroll_cancel`, `faces_clear`. App server thêm route `/video` (MJPEG, cookie phiên cấp sau `hello` hợp lệ) và `vision` vào `state` gửi web. | T19, T20, T22 |
| PROTO-4 | Vision agent ↔ robot agent trên Jetson, unix socket datagram `/run/mecanum/vision.sock` (quyền `0660`). Lên robot: `vision_cmd{seq,t_mono_ns,vx,vy,wz,state,user}` 20 Hz (đơn vị wire, gửi cả khi 0). Xuống vision: `robot_status{t_mono_ns,mode,blocked,flag_stop,gz,lidar_ok}` 20 Hz; scan rút gọn 360 × u16 10 Hz khi FOLLOW cần. | T18, T19 |

## 6. Vật lý

Hệ trục thân: x tiến, y trái, z lên, wz dương ngược chiều kim đồng hồ.
Bánh A, B, C, D với `ε = (+,−,+,−)`, `s = (−,−,+,+)` (theo `docs/dynamics.md`).

| Mã | Công thức / thông số | Task |
|---|---|---|
| PHY-1 | `L = 0.32` m (tâm cầu trước đến tâm cầu sau), `d = 0.35` m (tâm bánh trái đến tâm bánh phải), `r = 0.05` m. `lever = (L + d)/2 = 0.335` m (A-2). `m = 9.7` kg, `g = 9.81`, `μ_r = 0.05`, `I_z = m((L/2)²+(d/2)²) ≈ 0.5454` kg·m², `τ_rated = 0.981` N·m. Khai báo một chỗ trong `mecanum.ts`. | T07 |
| PHY-2 | Động học ngược: `ω_i = (vx + ε_i·vy + s_i·lever·wz) / r`. Test: `(0.1, 0.05, 0.2)` → `ω = (1.66, −0.34, 4.34, 2.34)`. | T07, T10 |
| PHY-3 | Động học thuận: `vx = r/4·Σω_i`, `vy = r/4·Σε_i·ω_i`, `wz = r/(4·lever)·Σs_i·ω_i`. Dư: `e = r/4·(ω_A − ω_B − ω_C + ω_D)`, khác 0 nghĩa là bánh đánh nhau. | T07, T10 |
| PHY-4 | Thân sang thế giới: `ẋ = vx·cosθ − vy·sinθ`, `ẏ = vx·sinθ + vy·cosθ`, `θ̇ = wz`; `ω̇` là đạo hàm có lọc của wz. | T07, T10 |
| PHY-5 | Động lực học: gia tốc từ vận tốc đo, lọc thông thấp bậc 1 `τ = 0.1 s`; `a_x = v̇x − wz·vy`, `a_y = v̇y + wz·vx`; `Fx = m·a_x`, `Fy = m·a_y`, `Mz = I_z·ẇz`; `F_d,i = (Fx + ε_i·Fy + s_i·Mz/lever)/4`; `F_c = μ_r·m·g/4`; `τ_i = r·(F_d,i + F_c·sign(ω_i))`. Test: `a = (1, 0)`, `ω_i > 0` → `F_d = 2.425`, `τ ≈ 0.1807`. | T07, T12 |
| PHY-6 | Bộ bám đích trên client, 20 Hz, chỉ xuất `cmd_vel`: sai số thế giới quay về thân, `v = 1.0·e`, `wz = 1.5·e_θ` (e_θ quấn về `[−π, π]`), chỉ giới hạn theo tốc độ chạy, giữ hướng vector; tăng/giảm tốc do firmware STM đảm nhiệm nên client không nhập, không giới hạn và không làm trơn gia tốc. Người dùng chỉ nhập đích và thời gian mong muốn T; tốc độ chạy suy ra: `vCruise = |quãng đường|/T`, `wzCruise = |góc|/T` (mặc định 0.2 m/s, 1.0 rad/s khi quãng đường hoặc góc bằng 0), tốc độ thân và bốn bánh hiển thị tức thời từ quãng đường/T qua PHY-2; không chặn trên. Xong khi `\|e\| < 0.02` m, `\|e_θ\| < 0.035` rad trong 3 chu kỳ. Hủy khi state cũ hơn 500 ms, disarm, có phím di chuyển hoặc quá `3·T_dự_kiến + 5` s. Kiểu A quy đổi: `x_g = x0 + s·cos(θ0+α)`, `y_g = y0 + s·sin(θ0+α)`, `θ_g = θ0`. | T07, T11 |
| PHY-7 | Odometry trên app server từ vận tốc đo của STM sau khi nhân `SPEED_SCALE`, tích phân trung điểm theo `t_mono_ns` của robot; bỏ mẫu có `dt ≤ 0` hoặc `dt > 0.5` s. | T06 |
| PHY-8 | Hình học cảm biến (v7 §2): camera Astra S cao 0.35 m, nghiêng lên 20°, trước tâm +0.20 m; LiDAR N10P cao 0.36 m, trước tâm +0.10 m, không tự che; thân 0.40 × 0.40 m; không có vật thấp hơn 0.36 m. Khai báo một chỗ trong cấu hình robot agent (`CAMERA_POSE`, `LIDAR_POSE`, `ROBOT_FOOTPRINT`). | T17, T18 |

## 7. Phi chức năng

| Mã | Yêu cầu | Task |
|---|---|---|
| NFR-01 | Cấu trúc thư mục theo plan.md §3. Không tạo file chỉ để bọc một hàm, mỗi file một trách nhiệm rõ. | T01 |
| NFR-02 | (v7 thêm: rút mạng → writer ghi 0 ≤ 0.5 s; `Space` → robot dừng và chế độ tắt ≤ 550 ms; vision agent tắt/treo → 0 ≤ 300 ms.) Mục tiêu đo được: độ trễ vòng lệnh (`cmd_vel` → `last_cmd_seq` trong state) p95 ≤ 150 ms trên Tailscale; tự dừng ≤ 300 ms sau một sự kiện mất link (socket đóng, ngắt kết nối, disarm); khi bên gửi chỉ im lặng thì tính từ lệnh cuối: deadman 250 ms cộng ≤ 300 ms, tức ≤ 550 ms. | T14, T15, T24, T27 |
| NFR-03 | Không dồn hàng đợi ở mọi chặng: chỉ giữ bản mới nhất, trừ `arm` và lệnh dừng. Trên web, dữ liệu tần số cao nằm ngoài React state (store + `useSyncExternalStore`, canvas qua ref). | T04, T06, T08 |
| NFR-04 | Có test cho giải mã, writer, control, odometry, công thức PHY (v7: thêm FSM, PROTO-4, arbiter, ModeGuard, cổng LiDAR, store; không cần GPU). Toàn bộ test và lint phải qua. | T07, T14, T18, T19 |
| NFR-05 | Python ≥ 3.10 (Jetson). Next.js 16 có thay đổi lớn: phải đọc `app/client/node_modules/next/dist/docs/` trước khi viết code client. | T01, T08 |
| NFR-06 | Có chế độ `ROBOT_SIMULATE=true` để chạy toàn hệ thống không cần Jetson; mô phỏng trả vận tốc theo đơn vị wire và scan giả. | T04, T14 |
| NFR-07 | Tuân thủ git-flow ở repo gốc: `main`, `develop`, mỗi task một nhánh `feature/Txx-*`, merge `--no-ff` vào `develop` chỉ sau khi Sonnet đối chứng đạt theo cả ba file. | T01, T16, T28 |
| NFR-08 | `VISION_SIMULATE=true` phát video và chuỗi trạng thái giả để kiểm thử arbiter, ModeGuard, web mà không cần camera. | T19, T21 |
| NFR-09 | Dữ liệu sinh trắc: embedding mã hóa, chỉ nằm trên Jetson (SQLite), không gửi lên app server hay web, không lưu ảnh gốc khi đăng ký; ảnh huấn luyện lưu nơi kiểm soát truy cập; có thông báo, đồng ý, thời hạn lưu, quyền xóa (Luật 91/2025/QH15, NĐ 356/2025/NĐ-CP). | T22, T25 |
| NFR-10 | Hiệu năng vision: ≥ 20 fps, ổn định 30–60 phút; độ trễ cử chỉ → bánh ~0.2–0.25 s, không phụ thuộc mạng. | T24, T27, T28 |

## 8. Giả định và xác nhận

- **A-1 (đã đo):** STM báo vận tốc thấp hơn thực tế khoảng 1.89 lần (lệnh 0.6 m theo odometry STM, thực đi 1.25 m bằng thước, tỉ lệ 1.88; khớp 51/27 = 1.889 của tỉ số truyền trong firmware). Telemetry vận tốc được nhân `SPEED_SCALE`; IMU không nhân.
- **A-2 (đã xác nhận):** `L` là khoảng cách cầu trước đến cầu sau, `d` là khoảng cách tâm bánh trái đến phải, nên `lever = (L+d)/2 = 0.335`.
- **A-3 (đã xác nhận):** Đích dùng `x, y, θ`, không có `z`. θ là rad trong giao thức, độ trên UI.
- **A-4 (chưa xác nhận):** Bố cục frame phụ không có trong repo. Tạm dùng `[1:3]` dòng sạc mA, `[3]` red, `[4]` charging, `[5]` set_state; kiểm chứng ở T15.
- **A-6 (chưa xác nhận, v7):** JetPack/Python 3.10/TensorRT trên Jetson chưa kiểm tra (`cat /etc/nv_tegra_release`); bánh có nhô ra ngoài khung 40 × 40 hay không; LiDAR không tự che. Kiểm chứng ở T17.
- **A-5 (đã xác nhận):** Mọi lệnh chuyển động từ web đều là cmd_vel, nên động học và bộ bám đích chạy trên client. `arm`, `odom_reset`, `hello` là lệnh phiên, dừng ở app server.
