"""Face enrolment session and the PROTO-3 staff command dispatcher (T22 skeleton).

There is no face model yet (T25): `capture` takes a sample from an injected `sampler` that returns
(embedding, quality, yaw) or None. Rules enforced now: enrolment only while gesture mode is off,
8-10 samples to commit, 120 s idle timeout, the preview lives in RAM only, and no result ever
carries an embedding. Revoking or deleting the active driver calls `on_revoke` (-> LOCKED).
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .store import Store, StoreError

MIN_SAMPLES = 8
MAX_SAMPLES = 10
IDLE_TIMEOUT_S = 120.0
Sample = tuple[list[float], float, float]


@dataclass
class EnrollSession:
    employee_id: int
    replace: bool
    last_at: float
    samples: list[Sample] = field(default_factory=list)


class StaffCommands:
    def __init__(
        self,
        store: Store,
        *,
        mode_on: Callable[[], bool],
        active_user: Callable[[], Any],
        on_revoke: Callable[[], None],
        on_enroll: Callable[[bool], bool] = lambda start: True,
        sampler: Callable[[], Sample | None] = lambda: None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.store = store
        self._mode_on = mode_on
        self._active_user = active_user
        self._on_revoke = on_revoke
        self._on_enroll = on_enroll
        self._sampler = sampler
        self._clock = clock
        self.session: EnrollSession | None = None

    def tick(self) -> None:
        """Cancel an enrolment idle for IDLE_TIMEOUT_S, or when gesture mode starts."""
        if self.session is not None and (
            self._mode_on() or self._clock() - self.session.last_at > IDLE_TIMEOUT_S
        ):
            self._cancel("timeout")

    def _cancel(self, why: str) -> None:
        if self.session is not None:
            self.store.log_event("enroll_cancel", self.session.employee_id, why)
            self.session = None  # the in-RAM samples are dropped here
            self._on_enroll(False)

    def enroll_state(self) -> dict[str, Any] | None:
        s = self.session
        return None if s is None else {"employee_id": s.employee_id, "samples": len(s.samples)}

    def _revoked(self, employee_id: Any) -> None:
        user = self._active_user()
        if user is not None and str(user) == str(employee_id):
            self._on_revoke()
        if self.session is not None and self.session.employee_id == employee_id:
            self._cancel("employee changed")

    def handle(self, data: dict[str, Any]) -> dict[str, Any]:
        """Run one command. Never raises: failures come back as {"ok": False, "error": ...}."""
        self.tick()
        try:
            return {"ok": True, **self._dispatch(data)}
        except StoreError as exc:
            return {"ok": False, "error": str(exc)}

    def _dispatch(self, data: dict[str, Any]) -> dict[str, Any]:
        kind, store = data.get("t"), self.store
        if kind == "staff_list":
            return {"staff": store.list_staff(), "enroll": self.enroll_state()}
        if kind == "staff_create":
            new_id = store.create(data.get("code"), data.get("name"), data.get("note", ""), data.get("allowed", True))
            return {"id": new_id}
        if kind == "staff_update":
            before = store.update(data.get("id"), **{k: data.get(k) for k in ("code", "name", "note", "allowed")})
            if data.get("allowed") is False and before["allowed"]:
                self._revoked(data["id"])
            return {}
        if kind == "staff_delete":
            store.delete(data.get("id"))
            self._revoked(data.get("id"))
            return {}
        if kind == "faces_clear":
            store.clear_samples(data.get("id"))
            self._revoked(data.get("id"))
            return {}
        if kind == "enroll_start":
            return self._start(data)
        if self.session is None:
            raise StoreError("no enrolment in progress")
        s = self.session
        s.last_at = self._clock()
        if kind == "enroll_capture":
            if len(s.samples) >= MAX_SAMPLES:
                raise StoreError("enough samples already")
            sample = self._sampler()
            if sample is None:
                raise StoreError("no usable face sample (quality or liveness check failed)")
            s.samples.append(sample)
            return {"enroll": self.enroll_state()}
        if kind == "enroll_commit":
            if len(s.samples) < MIN_SAMPLES:
                raise StoreError(f"need at least {MIN_SAMPLES} samples")
            store.add_samples(s.employee_id, s.samples, s.replace)
            self.session = None
            self._on_enroll(False)
            return {}
        if kind == "enroll_cancel":
            self._cancel("user")
            return {}
        raise StoreError("unknown command")

    def _start(self, data: dict[str, Any]) -> dict[str, Any]:
        if self._mode_on():
            raise StoreError("turn gesture mode off before enrolling")
        if self.session is not None:
            raise StoreError("an enrolment is already in progress")
        replace = data.get("replace", False)
        if not isinstance(replace, bool):
            raise StoreError("replace must be true or false")
        employee = self.store.get(data.get("id"))
        if not self._on_enroll(True):
            raise StoreError("the vision agent is busy")
        self.session = EnrollSession(employee["id"], replace, self._clock())
        self.store.log_event("enroll_start", employee["id"])
        return {"enroll": self.enroll_state()}
