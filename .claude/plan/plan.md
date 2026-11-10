# PLAN — Web điều khiển robot Mecanum (giai đoạn 1)

Trạng thái: **ĐÃ DUYỆT 2026-11-09; bổ sung v7 (D-09..D-12, V0–V7) 2026-11-10**. Đối chiếu: [spec.md](../spec/spec.md) · [task.md](../task/task.md)

## 1. Mục tiêu

Xây lại từ đầu phần truyền thông và website điều khiển: robot chạy một server, app server trên máy này
kết nối xuống robot, web điều khiển bằng bàn phím, động học thuận/ngược, hiển thị lực, tất cả realtime.

## 2. Quyết định thiết kế

| Mã | Quyết định | Lý do | Spec |
|---|---|---|---|
| D-01 | Robot là WS server, app server chủ động kết nối xuống | Theo yêu cầu; thay cho hướng robot gọi ra trước đây | PROTO-2, SAF-07 |
| D-02 | App server dùng FastAPI + uvicorn; robot dùng `websockets`; không ROS/MQTT | Chỉ có ba thành phần, không cần broker | PROTO-1, PROTO-2 |
| D-03 | Hệ số hiệu chỉnh `SPEED_SCALE` đặt trong cấu hình app server, chia ở `control.py`, nhân lại ở `telemetry.py`; robot và web không biết hệ số | Một giá trị chỉnh được, đo bằng thước | SAF-01 |
| D-04 | Động học, động lực học, bộ bám đích ở `mecanum.ts`/`motion.ts`; server chỉ làm odometry | Web chỉ gửi cmd_vel; không trùng công thức ở hai ngôn ngữ | FR-03, PHY-1..PHY-6, A-5 |
| D-05 | Arm và quyền lái dừng ở app server; link robot chỉ có cmd_vel | Giữ quy tắc "chỉ cmd_vel" và vẫn disarm mặc định | SAF-02, FR-03 |
| D-06 | Chế độ mô phỏng trên robot agent | Jetson đang offline, cần kiểm thử toàn tuyến | NFR-06 |
| D-07 | Có LiDAR, chưa có camera; giữ `AstraSSource` không khởi động | Yêu cầu chỉ loại camera | FR-10 |
| D-08 | Web nối trực tiếp FastAPI; Next.js chỉ phục vụ UI | Tránh thêm một chặng cho realtime | PROTO-1 |
| D-09 | (v7, 2026-11-10) Lệnh chuyển động của chế độ Cử chỉ đi thẳng camera → vision agent → robot agent → STM32, không qua app server. Chế độ chỉ bật khi app server đang arm và driver ra lệnh; app server giữ heartbeat; mất arm/driver/heartbeat thì robot agent chặn rồi tắt chế độ. Lệnh vision còn qua xác thực mặt, deadman, `ROBOT_MOTION_ENABLED`, `flag_stop`, cổng LiDAR. Lái tay khác 0 luôn thắng | Mất mạng thì robot dừng; độ trễ không phụ thuộc mạng | SAF-02, SAF-09, SAF-10 |
| D-10 | (v7) Thêm lệnh phiên `mode`, `hb` xuống robot (không mang vận tốc); PROTO-3 (app server ↔ vision), PROTO-4 (unix socket vision ↔ robot agent) | Giữ nguyên "chuyển động chỉ là cmd_vel" | FR-03, PROTO-2..4 |
| D-11 | (v7) Cổng LiDAR chỉ chặn (không kẹp) lệnh nguồn vision; bám người không có trần tốc độ; vision xuất đơn vị wire cấu hình trên Jetson, Jetson không biết `SPEED_SCALE` | Người dùng yêu cầu cổng LiDAR, không yêu cầu trần | SAF-01, SAF-04, SAF-11 |
| D-12 | (v7) Nhân viên và embedding khuôn mặt nằm trong SQLite trên Jetson; web quản lý qua app server, chỉ driver (`OPERATOR_TOKEN`) thao tác; không có tài khoản riêng | Dữ liệu sinh trắc không rời Jetson | FR-14, FR-15, NFR-09 |

## 3. Cấu trúc thư mục đích

```
mecanum_base/
├─ CLAUDE.md
├─ pyproject.toml              # gói Python cho robot và server (extras: robot, server, camera, test)
├─ .env.example                # mẫu biến cho cả Jetson và app server, chia mục rõ
├─ docs/dynamics.md            # chuyển từ read.md
├─ deploy/robot-agent.service  # systemd trên Jetson
├─ robot/                      # CHẠY TRÊN JETSON
│  ├─ robot_agent/
│  │  ├─ __main__.py           # khởi động, supervisor thiết bị
│  │  ├─ config.py             # đọc env
│  │  ├─ hardware.py           # STM32, N10P, Astra (từ src/)
│  │  ├─ drive.py              # writer cmd_vel, deadman (thay teleop.py)
│  │  ├─ sim.py                # STM32 + LiDAR giả
│  │  └─ server.py             # WS server
│  ├─ vendor/openni2/          # từ src/openni2_redist/
│  └─ tests/test_robot.py
└─ app/
   ├─ server/                  # CHẠY TRÊN 100.119.83.63
   │  ├─ app_server/
   │  │  ├─ main.py            # FastAPI, WS operator
   │  │  ├─ config.py          # đọc env
   │  │  ├─ control.py         # arm, quyền lái, kiểm tra lệnh, chia hệ số, watchdog
   │  │  ├─ robot_link.py      # WS client xuống robot, tự kết nối lại
   │  │  └─ telemetry.py       # nhân hệ số, odometry, dựng state cho web
   │  └─ tests/test_server.py
   └─ client/src/
      ├─ app/                  # layout.tsx + trang FR-01 (mỗi trang một page.tsx)
      ├─ robot/
      │  ├─ protocol.ts        # kiểu message
      │  ├─ control.ts         # logic thuần: phím thành vector, phân xử nguồn lệnh
      │  ├─ control.test.ts
      │  ├─ store.ts           # WS, state, vòng gửi 20 Hz
      │  ├─ telemetry.ts       # logic thuần: độ trễ, bộ đệm quỹ đạo, phát hiện mất dữ liệu
      │  ├─ telemetry.test.ts
      │  ├─ forward.ts         # động học thuận: phân tích số nhập, chuỗi tính, chạy theo thời gian
      │  ├─ forward.test.ts
      │  ├─ inverse.ts         # động học ngược: đích, tiến độ, bộ chạy tới đích
      │  ├─ inverse.test.ts
      │  ├─ dynamics.ts        # nguồn cấp động lực học và bộ đệm lịch sử
      │  ├─ dynamics.test.ts
      │  ├─ keyboard.tsx       # bàn phím toàn cục (gắn ở root layout)
      │  ├─ mecanum.ts         # công thức PHY-1..PHY-5
      │  ├─ motion.ts          # chạy động học thuận và bộ bám đích PHY-6
      │  └─ mecanum.test.ts
      └─ components/robot/
         ├─ app-shell.tsx      # điều hướng, thanh trạng thái, dừng khẩn
         ├─ panels.tsx         # bảng số liệu dùng lại giữa các trang
         └─ charts.tsx         # quỹ đạo, lực, polar LiDAR (canvas)
```

Bổ sung v7 (chi tiết ở [robot_plan_final_v7.md](../../robot_plan_final_v7.md) §11): `deploy/vision-agent.service`; `robot/vision_agent/` (`__main__`, `config`, `server`, `pipeline`, `gesture_fsm`, `face`, `person`, `body`, `hand`, `legs`, `enroll`, `store`, `record`); `robot/robot_agent/local_link.py`; `drive.py` thêm `ModeGuard`, `CmdArbiter`, cổng LiDAR; `app/server/app_server/vision_link.py`; `app/client/src/app/gesture/page.tsx`, `app/client/src/app/gesture/staff/page.tsx`; `training/` (chạy trên PC có GPU); `robot/tests/test_vision.py`. Thêm extras `vision` trong `pyproject.toml`.

Luồng lệnh: `Web cmd_vel → app server (arm, chia hệ số) → robot (deadman) → STM32`.
Luồng lệnh Cử chỉ (v7): `Web mode{true} + hb 5 Hz → app server → robot (ModeGuard)`; `camera → vision agent (vision_cmd, đơn vị wire) → unix socket → robot (CmdArbiter + cổng LiDAR) → writer → STM32`.
Luồng dữ liệu: `STM32/LiDAR → robot → app server (nhân hệ số, odometry) → web`.

## 4. Các giai đoạn

| Giai đoạn | Nội dung | Task | Cổng hoàn thành |
|---|---|---|---|
| P0 | Tái cấu trúc | T01 | Import và cấu hình pytest chạy được |
| P1 | Robot agent | T02, T03, T04 | Test robot qua, chạy được ở chế độ mô phỏng |
| P2 | App server | T05, T06 | Test server qua, nối được robot mô phỏng |
| P3 | Nền client | T07, T08 | Lái được bằng bàn phím trên mô phỏng từ mọi trang |
| P4 | Các trang | T09, T10, T11, T12, T13 | Mỗi trang đạt tiêu chí trong task.md |
| P5 | Kiểm chứng | T14, T15 | E2E qua; thử trên Jetson do người dùng cùng thực hiện |
| V0 | (v7) Tài liệu + kiểm tra phần cứng | T16, T17 | D-09..D-12 ghi vào repo; SAF-08, JetPack, khung 40 × 40 đã kiểm |
| V1 | (v7) Hạ tầng chế độ Cử chỉ | T18, T19, T20, T21 | Bật/tắt chế độ từ web trên mô phỏng; rút mạng → chặn ≤ 0.5 s; arbiter và cổng LiDAR đúng |
| V2 | (v7) Nhân viên + dữ liệu + cử chỉ/người | T22, T23 | CRUD chạy trên web; đạt chỉ số cử chỉ, phát hiện người |
| V3 | (v7) GESTURE thật | T24 | Lệnh đúng hướng; dừng đúng khi mất tay, rút mạng, `Space`, vật cản |
| V4 | (v7) Mặt | T25 | FAR/FRR, giả mạo đạt; đăng ký ≤ 1 phút |
| V5–V6 | (v7) FOLLOW, hiệu chỉnh | T26, T27 | Bám đúng người, bám kịp, HOLD khi mất dấu; báo cáo v7 §16 |
| V7 | (v7) Triển khai, phát hành | T28 | Chạy ổn định nhiều giờ; release theo git-flow |

## 5. Quy trình sub-agent cho mỗi task

| Vai | Model | Cách chạy | Trách nhiệm |
|---|---|---|---|
| Điều phối | Opus 5.5, medium | Phiên chính (đặt bằng `/effort medium`) | Giao việc theo thứ tự, giữ trạng thái task.md, quyết định khi có vướng mắc |
| Xác định việc + review | Sonnet 5.5, medium | `Agent(model: "sonnet", effort: "medium")` | Đọc spec và code, viết Work order; review kết quả |
| Viết code | Haiku 5.5 | `Agent(model: "haiku")` | Làm đúng Work order, không tự thiết kế |

Vòng lặp mỗi task:

1. **Sonnet** viết Work order ngay dưới task trong task.md: file được sửa, chữ ký hàm, logic từng bước, test vector, lệnh kiểm tra.
2. **Opus** đối chiếu Work order với spec.md và plan.md, rồi giao Haiku.
3. **Haiku** chỉ sửa file có trong Work order. Nếu thiếu thông tin hoặc có mâu thuẫn, Haiku trả `BLOCKED` kèm câu hỏi, không tự suy luận.
4. **Sonnet** đối chứng kết quả theo **cả ba file** spec.md, plan.md, task.md (và Work order), tự chạy test, trả `PASS` hoặc danh sách sửa cụ thể.
5. Tối đa hai vòng sửa; sau đó Opus xử lý hoặc hỏi người dùng. **Chỉ khi `PASS`, Opus mới merge** và cập nhật trạng thái.

Giữa mỗi giai đoạn, Opus kiểm tra đối chiếu chéo: mọi mã spec có task, mọi task trỏ tới mã tồn tại.

**Ngoại lệ cho P4 (T09–T13, theo yêu cầu người dùng 2026-11-09):** Sonnet 5.5 medium viết code trực tiếp, không qua Work order và Haiku. Một agent Sonnet khác đối chứng theo cả ba file; đạt mới merge.

### Git-flow (NFR-07)

- `main` chỉ nhận bản phát hành; `develop` là nhánh tích hợp.
- Mỗi task: `git switch -c feature/Txx-ten develop`, Opus commit, Sonnet đối chứng trên `git diff develop...HEAD`.
- Khi `PASS`: `git merge --no-ff feature/Txx-ten` vào `develop`, rồi xóa nhánh feature.
- Haiku và Sonnet không chạy lệnh git làm thay đổi repo. Sonnet chỉ sửa mục Work order của task.md.
- Phát hành `release/0.2.0` lên `main` và gắn tag chỉ sau khi T15 đạt trên robot thật.

## 6. Người dùng đã xác nhận (2026-11-09)

| # | Nội dung | Kết quả |
|---|---|---|
| 1 | Hình học (A-2) | `L`, `d` là kích thước toàn phần, `lever = 0.335` m |
| 2 | Telemetry (A-1) | Nhân lại `SPEED_SCALE` trước khi lên web |
| 3 | Đích (A-3) | Dùng `x, y, θ`, không dùng `z` |
| 4 | cmd_vel (A-5) | Web chỉ gửi cmd_vel, tính toán trên client |
| 5 | Giới hạn (SAF-04) | Không đặt giới hạn tốc độ |
| 6 | Đối chứng và git | Sonnet đối chứng theo cả ba file, đạt mới merge, theo git-flow |

## 7. Rủi ro

- Jetson đang offline: T15 phải chờ Jetson online và người dùng có mặt cạnh robot.
- Chưa biết firmware có watchdog không (SAF-08); phải thử trước khi chạy thật.
- Odometry chỉ dựa vận tốc thân nên trôi theo thời gian; động học ngược chính xác có giới hạn.
- Thông số trong `docs/dynamics.md` dùng `L+d = 0.30` cũ; T01 thêm ghi chú, chưa tính lại.
- Không có giới hạn tốc độ phần mềm: nhập sai vẫn được gửi xuống; các lớp deadman, disarm giữ nguyên.
- (v7) Bám người không trần: rủi ro chính là bám nhầm ở tốc độ cao; robot agent crash chỉ còn watchdog firmware (SAF-08) và nút tắt nguồn; nút tắt nguồn cũng tắt Jetson; JetPack 5 (Python 3.8) vênh với yêu cầu Python 3.10; dữ liệu công khai huấn luyện có thể cấm thương mại; dữ liệu sinh trắc chịu Luật 91/2025/QH15.
- (v7) Trình tự: V0 (T16, T17) và các phần không cần phần cứng của V1 làm trước; T24 trở đi cần Jetson, camera và người dùng có mặt cạnh robot.
