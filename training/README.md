# Dữ liệu và huấn luyện (T23, chạy trên PC có GPU)

Khung quy trình theo v7 §9. Chưa tải hay thu dữ liệu nào; phần có robot làm ở T24–T26.

| Việc | Công cụ |
|---|---|
| Thu RGB + depth theo vị trí camera | `robot/vision_agent/record.py` (cần đồng ý của người được thu, mã người là mã ẩn danh) |
| Quy ước lớp cử chỉ, lật ảnh đổi nhãn TRÁI/PHẢI, xoay ≤ 15° | `training/classes.py` |
| Chia train/val/test **theo người**, tập test không có người trong train | `training/split.py` |
| Dữ liệu công khai (tùy chọn, tải tay sau khi xem giấy phép) | `python training/download.py list` |

Cấu trúc thu: `data/raw/<người>/<phiên>/<loại>/<nhãn>/<n>.jpg` + `meta.json`. Loại: `face_pose`, `gesture`,
`lower_body_front`, `lower_body_back`, `spoof`. Thư mục `data/` không vào git (D-12). Sau khi có dữ liệu:
gắn nhãn (CVAT/Label Studio), DVC, huấn luyện, ONNX → TensorRT FP16, đo trên robot theo v7 §16.
