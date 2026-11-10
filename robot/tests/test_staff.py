"""T22: staff store, enrolment session and the command dispatcher (no face model needed)."""
import sqlite3

import pytest
from cryptography.fernet import Fernet

from vision_agent.enroll import IDLE_TIMEOUT_S, MIN_SAMPLES, StaffCommands
from vision_agent.pipeline import Pipeline
from vision_agent.store import Store, StoreError, load_key
from vision_agent.gesture_fsm import NS


def make(mode_on=False, user=None, sampler=None):
    store = Store(":memory:", Fernet.generate_key())
    now = [0.0]
    calls = {"revoke": 0, "enroll": []}
    cmds = StaffCommands(
        store,
        mode_on=lambda: mode_on,
        active_user=lambda: user,
        on_revoke=lambda: calls.__setitem__("revoke", calls["revoke"] + 1),
        on_enroll=lambda start: calls["enroll"].append(start) or True,
        sampler=sampler or (lambda: ([0.1, 0.2], 0.9, 0.0)),
        clock=lambda: now[0],
    )
    return cmds, store, now, calls


def test_crud_and_unique_code():
    c, store, *_ = make()
    r = c.handle({"t": "staff_create", "code": "A1", "name": "An", "note": "x", "allowed": True})
    assert r["ok"] and r["id"] == 1
    assert c.handle({"t": "staff_create", "code": "A1", "name": "B"}) == {"ok": False, "error": "code already exists"}
    assert not c.handle({"t": "staff_create", "code": "", "name": "B"})["ok"]
    assert not c.handle({"t": "staff_create", "code": "B", "name": "B", "allowed": "yes"})["ok"]
    assert c.handle({"t": "staff_update", "id": 1, "name": "An2"})["ok"]
    s = c.handle({"t": "staff_list"})["staff"][0]
    assert s["name"] == "An2" and s["samples"] == 0 and s["allowed"] is True
    assert not c.handle({"t": "staff_update", "id": 99, "name": "x"})["ok"]
    assert not c.handle({"t": "staff_update", "id": True, "name": "x"})["ok"]
    assert c.handle({"t": "staff_delete", "id": 1})["ok"]
    assert c.handle({"t": "staff_list"})["staff"] == []
    assert [e["kind"] for e in store.events()][:2] == ["staff_delete", "staff_update"]


def test_revoking_or_deleting_the_active_user_locks():
    c, _, _, calls = make(user="1")
    c.handle({"t": "staff_create", "code": "A", "name": "A"})
    c.handle({"t": "staff_create", "code": "B", "name": "B"})
    c.handle({"t": "staff_update", "id": 2, "allowed": False})
    assert calls["revoke"] == 0  # not the active user
    c.handle({"t": "staff_update", "id": 1, "note": "x"})
    assert calls["revoke"] == 0  # not a permission change
    c.handle({"t": "staff_update", "id": 1, "allowed": False})
    assert calls["revoke"] == 1
    c.handle({"t": "staff_delete", "id": 1})
    assert calls["revoke"] == 2


def _enroll_all(c, n=MIN_SAMPLES):
    c.handle({"t": "staff_create", "code": "A", "name": "A"})
    assert c.handle({"t": "enroll_start", "id": 1})["ok"]
    for _ in range(n):
        assert c.handle({"t": "enroll_capture"})["ok"]


def test_enroll_needs_mode_off_and_enough_samples():
    c, *_ = make(mode_on=True)
    c.handle({"t": "staff_create", "code": "A", "name": "A"})
    assert not c.handle({"t": "enroll_start", "id": 1})["ok"]
    c, store, _, calls = make()
    _enroll_all(c, MIN_SAMPLES - 1)
    assert not c.handle({"t": "enroll_commit"})["ok"]
    c.handle({"t": "enroll_capture"})
    assert c.handle({"t": "enroll_commit"})["ok"]
    assert c.session is None and calls["enroll"] == [True, False]
    assert c.handle({"t": "staff_list"})["staff"][0]["samples"] == MIN_SAMPLES


def test_enroll_limits_and_failed_capture_and_second_session():
    c, *_ = make()
    _enroll_all(c, 10)
    assert not c.handle({"t": "enroll_capture"})["ok"]  # max reached
    assert not c.handle({"t": "enroll_start", "id": 1})["ok"]  # already running
    c2, *_ = make(sampler=lambda: None)
    c2.handle({"t": "staff_create", "code": "A", "name": "A"})
    c2.handle({"t": "enroll_start", "id": 1})
    assert not c2.handle({"t": "enroll_capture"})["ok"]
    assert not make()[0].handle({"t": "enroll_capture"})["ok"]  # nothing in progress


def test_enroll_idle_timeout_and_cancel_drop_the_samples():
    c, store, now, calls = make()
    _enroll_all(c, 3)
    now[0] = IDLE_TIMEOUT_S + 1
    c.tick()
    assert c.session is None and calls["enroll"][-1] is False
    assert store.get(1)["samples"] == 0
    c.handle({"t": "enroll_start", "id": 1})
    c.handle({"t": "enroll_cancel"})
    assert c.session is None


def test_replace_and_faces_clear_and_delete_cascade():
    c, store, *_ = make()
    _enroll_all(c)
    c.handle({"t": "enroll_commit"})
    c.handle({"t": "enroll_start", "id": 1, "replace": True})
    for _ in range(MIN_SAMPLES):
        c.handle({"t": "enroll_capture"})
    c.handle({"t": "enroll_commit"})
    assert store.get(1)["samples"] == MIN_SAMPLES  # replaced, not appended
    assert c.handle({"t": "faces_clear", "id": 1})["ok"] and store.get(1)["samples"] == 0
    _ = store.add_samples(1, [([1.0], 0.9, 0.0)])
    c.handle({"t": "staff_delete", "id": 1})
    assert store._db.execute("SELECT COUNT(*) FROM face_samples").fetchone()[0] == 0


def test_embeddings_are_encrypted_at_rest_and_never_in_results():
    c, store, *_ = make()
    _enroll_all(c)
    c.handle({"t": "enroll_commit"})
    raw = store._db.execute("SELECT embedding FROM face_samples").fetchone()[0]
    assert b"0.1" not in raw
    assert store.gallery()[1][0] == [0.1, 0.2]
    listing = c.handle({"t": "staff_list"})
    assert "embedding" not in str(listing)
    c.handle({"t": "staff_update", "id": 1, "allowed": False})
    assert store.gallery() == {}  # disabled staff are not matched


def test_key_file_is_created_once(tmp_path):
    path = tmp_path / "k" / "staff.key"
    k1 = load_key("", path)
    assert load_key("", path) == k1 and path.exists()
    assert load_key("given", path) == b"given"
    Fernet(k1)


def test_pipeline_revoke_locks_the_fsm_once():
    p = Pipeline(simulate=True)
    p.mode_changed(True, 0)
    for step in range(0, 30):
        p.frame(step * NS // 10, )
    assert p.fsm.state in ("BIND", "GESTURE")
    p.revoke()
    p.frame(4 * NS)
    assert p.fsm.state == "LOCKED" and p.fsm.user is None
