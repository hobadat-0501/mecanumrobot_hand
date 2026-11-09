"use client";

// FR-02: điều khiển bàn phím toàn cục, gắn ở root layout nên hoạt động ở mọi trang.
// Không render gì; chỉ đăng ký listener và chuyển sự kiện cho store.

import { useEffect } from "react";

import { decideKeyDown, isTypingTarget, motionActionOf } from "./control";
import type { FocusLike } from "./control";
import {
  emergencyStop,
  cancelRun,
  haltAll,
  pressMotion,
  releaseKeys,
  releaseMotion,
  setArmed,
  startStore,
} from "./store";

export function KeyboardController(): null {
  useEffect(() => {
    startStore();

    const onKeyDown = (event: KeyboardEvent) => {
      const action = decideKeyDown(event.code, {
        typing: isTypingTarget(event.target as FocusLike | null),
        modifier: event.ctrlKey || event.metaKey || event.altKey,
      });
      if (action === null) return;
      if (action.kind === "motion") {
        event.preventDefault(); // không cuộn trang bằng phím mũi tên
        pressMotion(action.code);
      } else if (action.kind === "cancel") {
        event.preventDefault(); // không kích hoạt nút đang focus
        if (!event.repeat) cancelRun();
      } else if (action.kind === "arm") {
        if (!event.repeat) setArmed(true);
      } else {
        emergencyStop();
      }
    };
    // Nhả phím luôn được xử lý, kể cả khi focus đã chuyển vào ô nhập, để không kẹt phím.
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.code === "Space") event.preventDefault();
      if (motionActionOf(event.code) !== null) releaseMotion(event.code);
    };
    const onFocusIn = (event: FocusEvent) => {
      if (isTypingTarget(event.target as FocusLike | null)) releaseKeys();
    };
    const onBlur = () => haltAll("blur");
    const onVisibility = () => {
      if (document.hidden) haltAll("hidden");
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("focusin", onFocusIn);
    window.addEventListener("blur", onBlur);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("focusin", onFocusIn);
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return null;
}
