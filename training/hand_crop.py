"""Tìm bàn tay trong ảnh đã thu rồi cắt crop 96x96 cho bộ phân loại tầng 2 (v7 7.3). Chạy ngoại tuyến
trên Jetson, ảnh không rời máy (D-12). Không phải một phần của chuỗi điều khiển.

    PYTHONPATH=libs python3 training/hand_crop.py --src data/raw/p001/s3/gesture \
        --out data/crops/p001/s3 --model models/hand_landmarker.task

Mỗi ảnh: không có tay -> bỏ; có tay -> ghi crop vuông quanh tay (mở rộng để gồm cổ tay) và ghi
báo cáo report.json (số khung có tay theo nhãn, kích thước tay theo điểm ảnh).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CROP = 96
EXPAND = 1.8  # mở rộng hộp tay để gồm cổ tay và một phần cẳng tay


def square_box(xs: list[float], ys: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    cx, cy = (min(xs) + max(xs)) / 2 * width, (min(ys) + max(ys)) / 2 * height
    side = max((max(xs) - min(xs)) * width, (max(ys) - min(ys)) * height) * EXPAND
    side = max(side, 24.0)
    left, top = int(cx - side / 2), int(cy - side / 2)
    return left, top, int(side), int(side)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--max-y", type=float, default=1.0, help="bỏ tay có tâm thấp hơn mức này (0 trên, 1 dưới)")
    ap.add_argument("--confidence", type=float, default=0.3)
    args = ap.parse_args(argv)

    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks.python import BaseOptions, vision
    from PIL import Image

    options = vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(args.model)),
        num_hands=2,
        min_hand_detection_confidence=args.confidence,
    )
    report: dict[str, dict] = {}
    with vision.HandLandmarker.create_from_options(options) as detector:
        for label_dir in sorted(p for p in args.src.iterdir() if p.is_dir()):
            label = label_dir.name
            (args.out / label).mkdir(parents=True, exist_ok=True)
            total = found = two_hands = 0
            sizes: list[int] = []
            ys: list[float] = []
            for image_path in sorted(label_dir.glob("*.jpg")):
                total += 1
                rgb = np.asarray(Image.open(image_path).convert("RGB"))
                result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
                if not result.hand_landmarks:
                    continue
                # Tay làm cử chỉ thường nằm cao hơn tay buông ở hông: lấy tay có y trung bình nhỏ nhất.
                points = min(result.hand_landmarks, key=lambda hand: sum(p.y for p in hand))
                two_hands += len(result.hand_landmarks) > 1
                center_y = (min(p.y for p in points) + max(p.y for p in points)) / 2
                ys.append(round(center_y, 2))
                if center_y > args.max_y:
                    continue
                found += 1
                height, width = rgb.shape[:2]
                left, top, w, h = square_box([p.x for p in points], [p.y for p in points], width, height)
                sizes.append(w)
                crop = Image.fromarray(rgb).crop((left, top, left + w, top + h)).resize((CROP, CROP))
                crop.save(args.out / label / image_path.name, quality=92)
            report[label] = {
                "frames": total,
                "with_hand": found,
                "two_hands": two_hands,
                "hand_y_p10_p50_p90": [float(v) for v in np.percentile(ys, [10, 50, 90]).round(2)] if ys else None,
                "median_box_px": int(np.median(sizes)) if sizes else None,
            }
            print(label, report[label], flush=True)
    (args.out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
