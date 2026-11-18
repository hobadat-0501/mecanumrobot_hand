"""T23: recorder, split by person, class rules and the download script (no downloads happen)."""
import json
import sys
from pathlib import Path

import pytest

from vision_agent.record import Recorder

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "training"))
import classes  # noqa: E402
import download  # noqa: E402
import split  # noqa: E402


def test_recorder_writes_layout_and_meta(tmp_path):
    r = Recorder(tmp_path, "p001", "s1", "gesture", consent=True, clock=lambda: 5.0)
    p = r.add(b"\xff\xd8x", "FORWARD", "bright")
    r.add(b"\xff\xd8y", "FORWARD")
    meta = json.loads(r.close().read_text())
    assert p == tmp_path / "p001" / "s1" / "gesture" / "FORWARD" / "000000.jpg"
    assert [f["file"] for f in meta["frames"]] == ["FORWARD/000000.jpg", "FORWARD/000001.jpg"]


def test_recorder_refuses_bad_input(tmp_path):
    with pytest.raises(ValueError):
        Recorder(tmp_path, "p1", "s", "gesture", consent=False)
    with pytest.raises(ValueError):
        Recorder(tmp_path, "../x", "s", "gesture", consent=True)
    with pytest.raises(ValueError):
        Recorder(tmp_path, "p1", "s", "nope", consent=True)
    r = Recorder(tmp_path, "p1", "s", "gesture", consent=True)
    with pytest.raises(ValueError):
        r.add(b"", "../evil")


def test_split_is_by_person_deterministic_and_disjoint():
    people = [f"p{i}" for i in range(30)] * 3  # many images per person
    a = split.split_by_person(people, seed=1)
    assert a == split.split_by_person(people, seed=1)
    train, val, test = set(a["train"]), set(a["val"]), set(a["test"])
    assert len(train | val | test) == 30 == len(train) + len(val) + len(test)
    assert val and test
    with pytest.raises(ValueError):
        split.split_by_person(["a", "b"])


def test_flip_swaps_left_right_only():
    assert classes.flip_label("LEFT") == "RIGHT" and classes.flip_label("RIGHT") == "LEFT"
    assert classes.flip_label("STOP") == "STOP"
    with pytest.raises(ValueError):
        classes.flip_label("WAVE")


def test_download_script_needs_yes_and_fetches_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert download.main(["list"]) == 0 and "wider_face" in capsys.readouterr().out
    assert download.main(["get", "hagrid"]) == 2
    assert not Path("data").exists()
    assert download.main(["get", "hagrid", "--yes"]) == 0
    assert Path("data/external/hagrid").is_dir() and not any(Path("data/external/hagrid").iterdir())
