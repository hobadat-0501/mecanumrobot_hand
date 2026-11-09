# PLAN — Web điều khiển robot Mecanum (giai đoạn 1)

Trạng thái: **ĐÃ DUYỆT 2026-11-09**. Đối chiếu: [spec.md](../spec/spec.md) · [task.md](../task/task.md)

## 1. Mục tiêu

Xây lại từ đầu phần truyền thông và website điều khiển: robot chạy một server, app server trên máy này
kết nối xuống robot, web điều khiển bằng bàn phím, động học thuận/ngược, hiển thị lực, tất cả realtime.

## 2. Quyết định thiết kế

| Mã | Quyết định | Lý do | Spec |
|---|---|---|---|
| D-01 | Robot là WS server, app server chủ động kết nối xuống | Theo yêu cầu; thay cho hướng robot gọi ra trước đây | PROTO-2, SAF-07 |
| D-02 | App server dùng FastAPI + uvicorn; robot dùng `websockets`; không ROS/MQTT | Chỉ có ba thành phần, không cần broker | PROTO-1, PROTO-2 |
| D-03 | Chia 1.89 ở đúng một hàm trên app server, robot không biết hệ số | Một điểm sửa, web không thể lộ | SAF-01 |
| D-04 | Động học, động lực học, bộ bám đích ở `mecanum.ts`/`motion.ts`; server chỉ làm odometry | Web chỉ gửi cmd_vel; không trùng công thức ở hai ngôn ngữ | FR-03, PHY-1..PHY-6, A-5 |
| D-05 | Arm và quyền lái dừng ở app server; link robot chỉ có cmd_vel | Giữ quy tắc "chỉ cmd_vel" và vẫn disarm mặc định | SAF-02, FR-03 |
| D-06 | Chế độ mô phỏng trên robot agent | Jetson đang offline, cần kiểm thử toàn tuyến | NFR-06 |
| D-07 | Có LiDAR, chưa có camera; giữ `AstraSSource` không khởi động | Yêu cầu chỉ loại camera | FR-10 |
| D-08 | Web nối trực tiếp FastAPI; Next.js chỉ phục vụ UI | Tránh thêm một chặng cho realtime | PROTO-1 |

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

Luồng lệnh: `Web cmd_vel → app server (arm, chia hệ số) → robot (deadman) → STM32`.
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
| 2 | Telemetry (A-1) | Nhân lại 1.89 trước khi lên web |
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
