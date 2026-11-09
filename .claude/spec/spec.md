# SPEC — Web điều khiển robot Mecanum (giai đoạn 1)

Trạng thái: **ĐÃ DUYỆT 2026-11-09**. Đối chiếu: [plan.md](../plan/plan.md) · [task.md](../task/task.md)

Quy ước mã: `FR` chức năng, `SAF` an toàn, `FIX` lỗi code cũ, `PROTO` giao thức, `PHY` vật lý,
`NFR` phi chức năng, `A` giả định. Cột **Task** phải khớp 1-1 với dòng `Spec:` trong task.md.

## 1. Phạm vi

- Trong phạm vi: website điều khiển, app server, robot agent, bàn phím, động học thuận/ngược, động lực học, LiDAR.
- Ngoài phạm vi: camera (giữ `AstraSSource` nhưng không khởi động), SLAM/điều hướng, điều khiển từng bánh.

Địa chỉ: app (client + server) `100.119.83.63`, web `:3000`, API/WS `:8000`. Robot `100.69.39.18`, WS `:8765`.

## 2. Yêu cầu chức năng

| Mã | Yêu cầu | Task |
|---|---|---|
| FR-01 | Các trang: `/` tổng quan, `/kinematics/forward`, `/kinematics/inverse`, `/dynamics`, `/lidar`, `/system`. Chuyển trang bằng điều hướng phía client, không làm rớt kết nối. Giao diện tiếng Việt. | T08 |
| FR-02 | Điều khiển bàn phím nằm ở root layout, hoạt động ở mọi trang. `W/S` hoặc `↑/↓`: vx; `A/D` hoặc `←/→`: vy; `Q/E`: wz. Chiều dương: x tiến, y sang trái, wz ngược chiều kim đồng hồ, nên `W`/`↑` vx+, `S`/`↓` vx−, `A`/`←` vy+, `D`/`→` vy−, `Q` wz+, `E` wz−. Nhiều phím cộng thành vector (đi chéo được). `R` arm, `Space` là phím dừng khẩn duy nhất (thay `X` và `Esc`): hủy mọi lần chạy, gửi 0 và disarm. Bỏ qua phím di chuyển khi focus ở ô nhập; `Space` luôn có hiệu lực. Gửi theo timer 20 Hz khi đang giữ phím, không dùng auto-repeat của OS. Có ô chỉnh tốc độ, không chặn trên (SAF-04). | T08 |
| FR-03 | Lệnh chuyển động duy nhất trên toàn hệ thống là `cmd_vel (vx, vy, wz)`. Web không gửi tốc độ bánh, không gửi đích xuống server hay robot. Link xuống robot chỉ có `cmd_vel`. | T04, T05, T08 |
| FR-04 | Động học thuận: nhập 4 tốc độ bánh rad/s và thời gian chạy (mặc định 3 s). Hiển thị realtime chuỗi `ω_i → v_i = r·ω_i → vx, vy, wz → ẋ, ẏ, θ̇ (= ω), ω̇`, và thành phần dư (trượt bánh) theo PHY-3. Hiện cảnh báo, không chặn, khi `\|vx\|+\|vy\|+lever·\|wz\|` vượt 1.6 m/s. Nút chạy gửi cmd_vel đã tính. | T10 |
| FR-05 | Động học ngược, kiểu A: nhập quãng đường (m) + hướng (độ, so với thân xe tại lúc bấm chạy). Hiển thị 4 tốc độ bánh cần có và tiến độ. | T11 |
| FR-06 | Động học ngược, kiểu B: nhập đích `x, y, θ` theo khung odometry (A-3). Người dùng chọn giữa kiểu A và B trên cùng trang. | T11 |
| FR-07 | Trang động lực học hiển thị realtime: Fx, Fy, Mz, lực dọc từng bánh `F_d,i`, mô-men `τ_i`, % so với mô-men định mức, cảnh báo khi vượt định mức. | T12 |
| FR-08 | Toàn bộ số liệu hiển thị là realtime qua WS, trạng thái tới web tối đa 20 Hz: vận tốc đo, tư thế, lệnh hiện hành, IMU, điện áp, cờ dừng, sức khỏe link. | T06, T08, T09 |
| FR-09 | Thanh trạng thái toàn cục ở mọi trang: kết nối, arm/disarm, nút dừng khẩn, nguồn lệnh hiện tại, nhập mã điều khiển. | T08, T09 |
| FR-10 | Trang LiDAR vẽ scan dạng polar bằng canvas, 5–10 Hz. | T13 |
| FR-11 | Trang hệ thống: RTT, độ trễ vòng lệnh, trạng thái STM32/LiDAR/writer, số lỗi, dữ liệu sạc (nếu có). | T09 |
| FR-12 | Odometry `x, y, θ` trên app server, có nút reset; hiển thị quỹ đạo gần đây ở trang tổng quan. | T06, T09 |

## 3. Yêu cầu an toàn

| Mã | Yêu cầu | Task |
|---|---|---|
| SAF-01 | Không có hệ số quy đổi: `cmd_vel` đi từ web xuống STM và telemetry đi ngược lại đều giữ nguyên giá trị (đã bỏ hệ số 1.89 cũ). Không hằng số nhân/chia nào trong `control.py`, `telemetry.py`, client hay payload. | T05, T06, T08, T14 |
| SAF-02 | Mặc định disarm. App server khởi động ở disarm. Robot có `ROBOT_MOTION_ENABLED` mặc định `false`; khi `false` chỉ ghi vận tốc 0. Arm là trạng thái của app server, kết thúc ở đó, không gửi xuống robot. Mất link robot thì tự disarm; không arm được khi link đang mất. | T03, T05, T06, T14 |
| SAF-03 | Chuỗi tự dừng: (a) web thả phím, mất focus cửa sổ, ẩn tab thì gửi 0 và hủy chạy tự động; (b) app server không nhận lệnh 250 ms, hoặc operator ngắt kết nối, hoặc disarm thì gửi `cmd_vel` 0; (c) robot không nhận lệnh 250 ms hoặc mất link thì tự ghi 0. Lệnh đã hết hạn không được chạy lại khi link phục hồi. | T03, T04, T06, T08, T14 |
| SAF-04 | Không đặt giới hạn tốc độ phần mềm ở bất kỳ tầng nào (quyết định của người dùng). App server và robot vẫn loại giá trị không hữu hạn; giá trị vượt phạm vi `int16` của khung STM32 bị loại, không kẹp, và gửi 0 thay thế. | T03, T05, T08, T14 |
| SAF-05 | Writer ép 0 khi telemetry cũ hơn 0.5 s hoặc firmware bật cờ dừng. | T03, T14 |
| SAF-06 | Writer gặp lỗi ghi thì báo lỗi, xóa lệnh, tự thử lại; sau khi phục hồi vẫn xuất 0 cho đến khi có lệnh mới. | T03 |
| SAF-07 | Xác thực: link robot dùng `ROBOT_LINK_TOKEN`, robot chỉ bind IP Tailscale, kết nối hợp lệ mới nhất thay kết nối cũ. Operator: `hello` kèm `OPERATOR_TOKEN`, kiểm tra Origin; không có mã thì chỉ xem. Một operator giữ quyền lái tại một thời điểm. | T04, T05, T14 |
| SAF-08 | Firmware STM32 không được sửa. Trước khi chạy thật chỉ quan sát hành vi của firmware (nhấc bánh khỏi mặt đất, gửi một lệnh tốc độ thấp rồi ngừng gửi) để biết nó có tự dừng khi mất lệnh không. Nếu không, ghi nhận rủi ro và chờ người dùng quyết định; lớp bảo vệ duy nhất phía Jetson là deadman của writer. | T15 |

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

## 5. Giao thức

| Mã | Nội dung | Task |
|---|---|---|
| PROTO-1 | Web ↔ app server: `ws://100.119.83.63:8000/ws/operator`. Web → server: `hello{token}`, `cmd_vel{seq,vx,vy,wz,src}`, `arm{on}`, `odom_reset`. Server → web (JSON ≤ 20 Hz): `state{link,session,vel,pose,cmd,imu,voltage,flag_stop,charge,health,last_cmd_seq}`; LiDAR qua frame nhị phân theo PROTO-2. Mọi số vận tốc theo đơn vị web. | T05, T06, T08 |
| PROTO-2 | App server (client) ↔ robot (server): `ws://100.69.39.18:8765/ws`, header `Authorization: Bearer`. Xuống robot chỉ có `cmd_vel{seq,vx,vy,wz}` (đơn vị wire). Lên: `state` JSON ≤ 50 Hz gồm `t_mono_ns` (thời điểm mẫu STM32), `last_cmd_seq`, `vel{vx,vy,wz}`, `imu{ax,ay,az,gx,gy,gz}`, `voltage`, `flag_stop`, `charge{current_a,red,charging,set_state}` hoặc null, `health{stm,lidar,writer}`; `scan` nhị phân: header `type u8, ver u8, seq u32, t_mono_ms u64`, thân 360 × `u16` mm little-endian, 0 là không có điểm (tổng 734 byte, `type = 2`, `ver = 1`; ô 0 là hướng +x của robot, tăng dần ngược chiều kim đồng hồ, mỗi ô 1°, điểm gần nhất thắng; app server chuyển tiếp tối đa 10 Hz, chỉ giữ khung mới nhất). Hàng đợi gửi chỉ giữ bản mới nhất. | T04, T06, T13 |

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
| PHY-7 | Odometry trên app server từ vận tốc đo của STM (không quy đổi), tích phân trung điểm theo `t_mono_ns` của robot; bỏ mẫu có `dt ≤ 0` hoặc `dt > 0.5` s. | T06 |

## 7. Phi chức năng

| Mã | Yêu cầu | Task |
|---|---|---|
| NFR-01 | Cấu trúc thư mục theo plan.md §3. Không tạo file chỉ để bọc một hàm, mỗi file một trách nhiệm rõ. | T01 |
| NFR-02 | Mục tiêu đo được: độ trễ vòng lệnh (`cmd_vel` → `last_cmd_seq` trong state) p95 ≤ 150 ms trên Tailscale; tự dừng ≤ 300 ms sau một sự kiện mất link (socket đóng, ngắt kết nối, disarm); khi bên gửi chỉ im lặng thì tính từ lệnh cuối: deadman 250 ms cộng ≤ 300 ms, tức ≤ 550 ms. | T14, T15 |
| NFR-03 | Không dồn hàng đợi ở mọi chặng: chỉ giữ bản mới nhất, trừ `arm` và lệnh dừng. Trên web, dữ liệu tần số cao nằm ngoài React state (store + `useSyncExternalStore`, canvas qua ref). | T04, T06, T08 |
| NFR-04 | Có test cho giải mã, writer, control, odometry, công thức PHY. Toàn bộ test và lint phải qua. | T07, T14 |
| NFR-05 | Python ≥ 3.10 (Jetson). Next.js 16 có thay đổi lớn: phải đọc `app/client/node_modules/next/dist/docs/` trước khi viết code client. | T01, T08 |
| NFR-06 | Có chế độ `ROBOT_SIMULATE=true` để chạy toàn hệ thống không cần Jetson; mô phỏng trả vận tốc theo đơn vị wire và scan giả. | T04, T14 |
| NFR-07 | Tuân thủ git-flow ở repo gốc: `main`, `develop`, mỗi task một nhánh `feature/Txx-*`, merge `--no-ff` vào `develop` chỉ sau khi Sonnet đối chứng đạt theo cả ba file. | T01 |

## 8. Giả định và xác nhận

- **A-1 (thay đổi):** Telemetry vận tốc từ STM32 lên web giữ nguyên, không nhân hệ số nào (hệ số 1.89 cũ đã bỏ).
- **A-2 (đã xác nhận):** `L` là khoảng cách cầu trước đến cầu sau, `d` là khoảng cách tâm bánh trái đến phải, nên `lever = (L+d)/2 = 0.335`.
- **A-3 (đã xác nhận):** Đích dùng `x, y, θ`, không có `z`. θ là rad trong giao thức, độ trên UI.
- **A-4 (chưa xác nhận):** Bố cục frame phụ không có trong repo. Tạm dùng `[1:3]` dòng sạc mA, `[3]` red, `[4]` charging, `[5]` set_state; kiểm chứng ở T15.
- **A-5 (đã xác nhận):** Mọi lệnh chuyển động từ web đều là cmd_vel, nên động học và bộ bám đích chạy trên client. `arm`, `odom_reset`, `hello` là lệnh phiên, dừng ở app server.
