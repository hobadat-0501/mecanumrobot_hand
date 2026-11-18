"""Gesture classes and augmentation rules (v7 §7.2, §7.4). Runs on the training PC."""
GESTURES = ("STOP", "FORWARD", "BACK", "RIGHT", "LEFT", "OPEN_PALM", "OTHER")

# Mirroring the image swaps left and right; every other class keeps its label.
_FLIP = {"LEFT": "RIGHT", "RIGHT": "LEFT"}
MAX_ROTATE_DEG = 15  # allowed rotation augmentation


def flip_label(label: str) -> str:
    if label not in GESTURES:
        raise ValueError(f"unknown gesture {label!r}")
    return _FLIP.get(label, label)
