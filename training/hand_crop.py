"""Tìm bàn tay trong ảnh đã thu rồi cắt crop 96x96 cho bộ phân loại tầng 2 (v7 7.3). Chạy ngoại tuyến
trên Jetson, ảnh không rời máy (D-12). Không phải một phần của chuỗi điều khiển.

    PYTHONPATH=libs python3 training/hand_crop.py --src data/raw/p001/s3/gesture \
        --out data/crops/p001/s3 --model models/hand_landmarker.task

Mỗi ảnh có thể có hai tay (tay làm cử chỉ và tay buông). Với mỗi tay, 21 điểm mốc cho biết các ngón
duỗi hay gập và ngón trỏ chỉ hướng nào; tay nào khớp luật của nhãn ảnh thì được giữ (nhiều tay khớp
thì lấy tay cao hơn). Nhãn OTHER giữ mọi tay. Luật chỉ là bộ lọc thô để dọn nhãn, không thay cho việc
duyệt mẫu bằng mắt; ghi report.json (số khung có tay, số khung khớp luật).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

CROP = 96
EXPAND = 1.8  # mở rộng hộp tay để gồm cổ tay và một phần cẳng tay
EXTENDED = 1.12  # đầu ngón xa cổ tay hơn đốt giữa bấy nhiêu lần -> ngón duỗi
CURLED = 1.0  # nhỏ hơn mức này -> ngón gập
FINGERS = {"index": (8, 6), "middle": (12, 10), "ring": (16, 14), "pinky": (20, 18)}


def square_box(xs: list[float], ys: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    cx, cy = (min(xs) + max(xs)) / 2 * width, (min(ys) + max(ys)) / 2 * height
    side = max((max(xs) - min(xs)) * width, (max(ys) - min(ys)) * height) * EXPAND
    side = max(side, 24.0)
    left, top = int(cx - side / 2), int(cy - side / 2)
    return left, top, int(side), int(side)


def finger_states(points: list, width: int, height: int) -> dict[str, str]:
    """Mỗi ngón: 'ext' (duỗi), 'curl' (gập) hoặc 'mid'. Khoảng cách tính theo điểm ảnh."""

    def dist(a: int, b: int) -> float:
        return math.hypot((points[a].x - points[b].x) * width, (points[a].y - points[b].y) * height)

    states = {}
    for name, (tip, pip) in FINGERS.items():
        ratio = dist(tip, 0) / max(dist(pip, 0), 1e-6)
        states[name] = "ext" if ratio > EXTENDED else "curl" if ratio < CURLED else "mid"
    return states


def matches(label: str, points: list, width: int, height: int) -> bool:
    """Tay này có khớp tư thế của nhãn không (luật thô theo điểm mốc)."""
    if label == "OTHER":
        return True
    states = finger_states(points, width, height)
    others_curled = all(states[n] == "curl" for n in ("middle", "ring", "pinky"))
    if label == "OPEN_PALM":
        return sum(s == "ext" for s in states.values()) >= 4
    if label == "STOP":
        return all(s == "curl" for s in states.values())
    if not (states["index"] == "ext" and others_curled):
        return False
    dx = (points[8].x - points[5].x) * width
    dy = (points[8].y - points[5].y) * height
    if label == "FORWARD":
        return dy < 0 and abs(dy) > abs(dx)
    if label == "BACK":
        return dy > 0 and abs(dy) > abs(dx)
    if label == "RIGHT":
        return dx > 0 and abs(dx) > abs(dy)
    if label == "LEFT":
        return dx < 0 and abs(dx) > abs(dy)
    raise ValueError(f"nhãn lạ: {label}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", type=Path, required=True)
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
            total = seen = kept = 0
            sizes: list[int] = []
            for image_path in sorted(label_dir.glob("*.jpg")):
                total += 1
                rgb = np.asarray(Image.open(image_path).convert("RGB"))
                height, width = rgb.shape[:2]
                result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
                if not result.hand_landmarks:
                    continue
                seen += 1
                fitting = [h for h in result.hand_landmarks if matches(label, h, width, height)]
                if not fitting:
                    continue
                kept += 1
                points = min(fitting, key=lambda hand: sum(p.y for p in hand))
                left, top, w, h = square_box([p.x for p in points], [p.y for p in points], width, height)
                sizes.append(w)
                crop = Image.fromarray(rgb).crop((left, top, left + w, top + h)).resize((CROP, CROP))
                crop.save(args.out / label / image_path.name, quality=92)
            report[label] = {
                "frames": total,
                "with_hand": seen,
                "matching_pose": kept,
                "median_box_px": int(np.median(sizes)) if sizes else None,
            }
            print(label, report[label], flush=True)
    (args.out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
