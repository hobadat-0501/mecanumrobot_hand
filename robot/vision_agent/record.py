"""Training-data recorder (v7 §9 step 2). Skeleton: frames come from the caller, so it runs without
a camera. Layout: <root>/<person_id>/<session>/<kind>/<label>/<n>.jpg + meta.json.
`person_id` is an opaque code (never a name), because splits are made by person (see training/).
Data lives under data/ (git-ignored, D-12) - use access-controlled storage for real recordings.
"""
from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from pathlib import Path

KINDS = ("face_pose", "gesture", "lower_body_front", "lower_body_back", "spoof")
_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class Recorder:
    def __init__(
        self,
        root: Path | str,
        person_id: str,
        session: str,
        kind: str,
        consent: bool,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        if not (_SAFE.match(person_id) and _SAFE.match(session)):
            raise ValueError("person_id and session must be 1-40 chars of A-Z a-z 0-9 _ -")
        if not consent:
            raise ValueError("recording needs the person's consent (NFR-09)")
        self.dir = Path(root) / person_id / session / kind
        self._clock = clock
        self._counts: dict[str, int] = {}
        self._meta: dict = {
            "person": person_id, "session": session, "kind": kind, "started": clock(), "frames": [],
        }

    def add(self, jpeg: bytes, label: str, note: str = "") -> Path:
        if not _SAFE.match(label):
            raise ValueError("label must be 1-40 chars of A-Z a-z 0-9 _ -")
        folder = self.dir / label
        folder.mkdir(parents=True, exist_ok=True)
        n = self._counts.get(label, 0)
        self._counts[label] = n + 1
        path = folder / f"{n:06d}.jpg"
        path.write_bytes(jpeg)
        self._meta["frames"].append(
            {"file": f"{label}/{path.name}", "label": label, "t": self._clock(), "note": note}
        )
        return path

    def close(self) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        meta = self.dir / "meta.json"
        meta.write_text(json.dumps(self._meta, indent=1), encoding="utf-8")
        return meta
