"""Split recorded data into train/val/test BY PERSON (never by image), so the test set contains
only people absent from training (v7 §7.5, §16). Deterministic for a given seed."""
from __future__ import annotations

import random


def split_by_person(
    people: list[str], val: float = 0.15, test: float = 0.15, seed: int = 0
) -> dict[str, list[str]]:
    unique = sorted(set(people))
    if len(unique) < 3:
        raise ValueError("need at least 3 people to split train/val/test")
    rng = random.Random(seed)
    rng.shuffle(unique)
    n_test = max(1, round(len(unique) * test))
    n_val = max(1, round(len(unique) * val))
    return {
        "test": sorted(unique[:n_test]),
        "val": sorted(unique[n_test : n_test + n_val]),
        "train": sorted(unique[n_test + n_val :]),
    }
