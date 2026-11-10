# Mecanum base

Hệ thống gồm robot agent (Jetson `100.69.39.18`) và app gồm client + server (máy `100.119.83.63`).

Nguồn sự thật: `.claude/spec/spec.md` (yêu cầu), `.claude/plan/plan.md` (thiết kế, quy trình), `.claude/task/task.md` (công việc).
Ba file phải đối chứng chéo: mọi mã spec có task, mọi task trỏ tới mã spec và giai đoạn tồn tại. Đổi một file thì cập nhật hai file còn lại. Xong mỗi task, Sonnet đối chứng kết quả theo cả ba file, đạt mới được merge.

## Quy tắc không được vi phạm

- Lệnh chuyển động duy nhất là `cmd_vel (vx, vy, wz)`. Không gửi tốc độ bánh hay đích xuống robot. Link app server → robot ngoài `cmd_vel` chỉ có lệnh phiên `mode`, `hb` (không mang vận tốc, D-10).
- Hệ số hiệu chỉnh tốc độ là cấu hình `SPEED_SCALE` của app server (đo thực tế 1.89): `cmd_vel` chia **chỉ** trong `app/server/app_server/control.py`, telemetry nhân lại **chỉ** trong `telemetry.py`. Không đưa hệ số vào client, UI, hay payload tới web. Robot không biết hệ số. Không hằng số cố định trong mã. Ngoại lệ duy nhất (D-09, D-11): nguồn vision (chế độ Cử chỉ) chạy hoàn toàn trên Jetson, xuất **đơn vị wire** từ cấu hình `.env` của Jetson, không qua `control.py`; Jetson vẫn không biết hệ số.
- Robot luôn mặc định dừng: disarm khi khởi động, deadman ở mọi chặng. Không thêm đường đi nào vượt qua các lớp này. Không thêm giới hạn tốc độ nếu người dùng chưa yêu cầu. Chế độ Cử chỉ (D-09) chỉ bật được khi app server đang arm và driver ra lệnh; mất heartbeat > 0.5 s chặn vision, > 3 s tắt chế độ; lái tay khác 0 luôn thắng vision; cổng LiDAR chỉ **chặn** lệnh vision (D-11), không kẹp tốc độ. Dữ liệu khuôn mặt chỉ nằm trên Jetson (D-12).
- Không chạy động cơ thật khi người dùng chưa xác nhận có mặt cạnh robot.
- Firmware STM32 là của bên ngoài: không viết, không sửa, không đề xuất nạp code vào STM. STM chỉ nhận `cmd_vel` và trả telemetry; mọi cơ chế an toàn nằm ở phía Jetson và app server.

## Quy trình sub-agent

Điều phối: Opus 5.5 medium (phiên chính). Xác định việc và review: Sonnet 5.5 medium. Viết code: Haiku 5.5, chỉ làm đúng Work order, thiếu thông tin thì trả `BLOCKED`. Chi tiết ở plan.md §5.

## Git-flow

`main` chỉ nhận bản phát hành, `develop` tích hợp, mỗi task một nhánh `feature/Txx-*`, merge `--no-ff` vào `develop`. Không commit thẳng vào `main` hoặc `develop`, trừ khi khởi tạo repo.

## Lưu ý

- Client dùng Next.js 16 có thay đổi lớn: đọc `app/client/node_modules/next/dist/docs/` trước khi viết code client (xem `app/client/AGENTS.md`).
- Python phải tương thích 3.10 cho Jetson.
- Không tạo file chỉ để bọc một hàm; bố cục thư mục theo plan.md §3.
