// Logic thuần của điều khiển (FR-02, FR-09, SAF-03a): ánh xạ phím, chặn khi gõ chữ,
// và bộ phân xử nguồn lệnh. Không dùng React, DOM, timer hay WebSocket nên test được trực tiếp.
// store.ts gắn bộ phân xử vào timer 20 Hz và socket.

import type { BodyVel, Pose } from "./mecanum";
import { CONTROL_HZ } from "./motion";
import type { AbortReason, RunContext, RunStatus } from "./motion";
import type { CmdSrc } from "./protocol";

export const TICK_MS = 1000 / CONTROL_HZ; // 50 ms

/** Tốc độ bàn phím: lin (m/s) cho vx, vy; ang (rad/s) cho wz. Không chặn trên (SAF-04). */
export interface Speed {
  lin: number;
  ang: number;
}

export const DEFAULT_SPEED: Speed = { lin: 0.2, ang: 1.0 };

/** Số hữu hạn lớn hơn 0 thì trả về số đó, ngược lại null. Không có chặn trên. */
export function parseSpeed(text: string): number | null {
  if (text.trim() === "") return null;
  const value = Number(text);
  return Number.isFinite(value) && value > 0 ? value : null;
}

export type MotionAction = "fwd" | "back" | "left" | "right" | "ccw" | "cw";

// event.code, không phải event.key: đúng khi bật bộ gõ tiếng Việt hay đổi bố cục bàn phím.
// Hệ trục thân: x tiến, y trái, wz dương ngược chiều kim đồng hồ.
const MOTION_CODES: Readonly<Record<string, MotionAction>> = {
  KeyW: "fwd",
  ArrowUp: "fwd",
  KeyS: "back",
  ArrowDown: "back",
  KeyA: "left",
  ArrowLeft: "left",
  KeyD: "right",
  ArrowRight: "right",
  KeyQ: "ccw",
  KeyE: "cw",
};

export function motionActionOf(code: string): MotionAction | null {
  return Object.prototype.hasOwnProperty.call(MOTION_CODES, code)
    ? MOTION_CODES[code]
    : null;
}

/** Tập phím đang giữ (theo event.code) thành vector. Hai phím cùng hướng không cộng đôi. */
export function keysToVector(held: ReadonlySet<string>, speed: Speed): BodyVel {
  const on = new Set<MotionAction>();
  for (const code of held) {
    const action = motionActionOf(code);
    if (action !== null) on.add(action);
  }
  const axis = (plus: MotionAction, minus: MotionAction): number =>
    (on.has(plus) ? 1 : 0) - (on.has(minus) ? 1 : 0);
  return {
    vx: axis("fwd", "back") * speed.lin,
    vy: axis("left", "right") * speed.lin,
    wz: axis("ccw", "cw") * speed.ang,
  };
}

/** Phần tử có focus mà gõ chữ vào được. Cấu trúc tối giản để test không cần DOM. */
export interface FocusLike {
  tagName?: string;
  isContentEditable?: boolean;
}

export function isTypingTarget(target: FocusLike | null | undefined): boolean {
  if (target === null || target === undefined) return false;
  if (target.isContentEditable === true) return true;
  const tag = typeof target.tagName === "string" ? target.tagName.toUpperCase() : "";
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

export type KeyAction =
  | { kind: "motion"; code: string }
  | { kind: "arm" }
  | { kind: "stop" };

export interface KeyContext {
  /** Focus đang ở ô nhập. */
  typing: boolean;
  /** Ctrl, Meta hoặc Alt đang giữ (Ctrl+R tải lại trang không được arm). */
  modifier: boolean;
}

/** FR-02: phím nhấn xuống thành hành động, hoặc null nếu bị bỏ qua. Esc luôn có hiệu lực. */
export function decideKeyDown(code: string, ctx: KeyContext): KeyAction | null {
  if (code === "Escape") return { kind: "stop" };
  if (ctx.typing || ctx.modifier) return null;
  if (code === "KeyX") return { kind: "stop" };
  if (code === "KeyR") return { kind: "arm" };
  if (motionActionOf(code) !== null) return { kind: "motion", code };
  return null;
}

export type RunSource = "forward" | "inverse";
/** FR-09: nguồn lệnh hiện tại, tính ở client. */
export type Source = "idle" | "keyboard" | RunSource;

export type EndReason =
  | AbortReason
  | "blur"
  | "hidden"
  | "closed"
  | "stop"
  | "cancel"
  | "error";

export interface RunEnd {
  source: RunSource;
  done: boolean;
  /** null khi done. */
  reason: EndReason | null;
}

/** Đầu vào mỗi chu kỳ cho bộ chạy tự động; tương thích RunContext của motion.ts. */
export interface RunInput extends RunContext {
  /** Thời gian từ chu kỳ trước (s). */
  dt: number;
  /** Tư thế mới nhất từ server, null nếu chưa có state. */
  pose: Pose | null;
}

export interface RunStep {
  cmd: BodyVel;
  status: RunStatus;
}

/** T10, T11 bọc bộ bước của motion.ts (wheelRunStep, trackStep) thành RunDriver. */
export interface RunDriver {
  step(input: RunInput): RunStep;
}

export interface TickContext {
  dt: number;
  pose: Pose | null;
  stateAgeS: number;
  armed: boolean;
}

export interface Output {
  cmd: BodyVel;
  src: CmdSrc;
}

const ZERO: BodyVel = { vx: 0, vy: 0, wz: 0 };

function isZero(cmd: BodyVel): boolean {
  return cmd.vx === 0 && cmd.vy === 0 && cmd.wz === 0;
}

/**
 * Phân xử nguồn lệnh: phím thắng chạy tự động. Chỉ có bộ phân xử này tạo ra cmd_vel.
 * Khi rảnh (không phím, không chạy, không nợ lệnh 0) thì tick trả null: không gửi gì.
 */
export class Arbiter {
  speed: Speed;
  private held = new Set<string>();
  private run: { driver: RunDriver; source: RunSource } | null = null;
  private owesZero = false;
  private lastSrc: CmdSrc = "keyboard";
  private end: RunEnd | null = null;

  constructor(speed: Speed = DEFAULT_SPEED) {
    this.speed = speed;
  }

  get source(): Source {
    if (this.held.size > 0) return "keyboard";
    if (this.run !== null) return this.run.source;
    return "idle";
  }

  /** Còn việc phải làm ở chu kỳ tới, nên timer 20 Hz cần chạy. */
  get active(): boolean {
    return this.held.size > 0 || this.run !== null || this.owesZero;
  }

  /** Kết thúc của lần chạy gần nhất, null nếu chưa có. */
  get lastRunEnd(): RunEnd | null {
    return this.end;
  }

  get holdingKeys(): boolean {
    return this.held.size > 0;
  }

  setSpeed(speed: Speed): void {
    this.speed = speed;
  }

  /** Giữ một phím di chuyển. Mọi phím di chuyển hủy lần chạy đang có. */
  keyDown(code: string): void {
    if (motionActionOf(code) === null) return;
    this.held.add(code);
    this.cancelRun("key");
  }

  keyUp(code: string): void {
    this.held.delete(code);
  }

  /** Bắt đầu một lần chạy. Trả false (không chạy) khi đang giữ phím: phím thắng. */
  startRun(driver: RunDriver, source: RunSource): boolean {
    if (this.held.size > 0) return false;
    this.cancelRun("cancel");
    this.run = { driver, source };
    this.end = null;
    return true;
  }

  cancelRun(reason: EndReason): void {
    if (this.run === null) return;
    this.end = { source: this.run.source, done: false, reason };
    this.run = null;
  }

  /** Nhả mọi phím và hủy lần chạy (mất focus, ẩn tab, disarm, đóng socket, dừng khẩn). */
  releaseAll(reason: EndReason): void {
    this.held.clear();
    this.cancelRun(reason);
    this.owesZero = false;
  }

  /** Nhả mọi phím nhưng giữ lần chạy (focus vào ô nhập). */
  releaseKeys(): void {
    this.held.clear();
  }

  /** Lệnh 0 còn nợ sau khi nhả phím hoặc hủy chạy. Trả null nếu không nợ hoặc vẫn còn nguồn. */
  flushZero(): Output | null {
    if (!this.owesZero || this.held.size > 0 || this.run !== null) return null;
    this.owesZero = false;
    return { cmd: { ...ZERO }, src: this.lastSrc };
  }

  /** Một chu kỳ 20 Hz. null nghĩa là không gửi gì. */
  tick(ctx: TickContext): Output | null {
    if (this.held.size > 0) {
      return this.emit({ cmd: keysToVector(this.held, this.speed), src: "keyboard" });
    }
    if (this.run !== null) {
      const { driver, source } = this.run;
      let step: RunStep;
      try {
        step = driver.step({ ...ctx, keyPressed: false });
      } catch {
        this.end = { source, done: false, reason: "error" };
        this.run = null;
        return this.emit({ cmd: { ...ZERO }, src: source });
      }
      if (step.status.kind === "running") {
        return this.emit({ cmd: step.cmd, src: source });
      }
      this.end =
        step.status.kind === "done"
          ? { source, done: true, reason: null }
          : { source, done: false, reason: step.status.reason };
      this.run = null;
      return this.emit({ cmd: { ...ZERO }, src: source });
    }
    return this.flushZero();
  }

  private emit(out: Output): Output {
    this.owesZero = !isZero(out.cmd);
    this.lastSrc = out.src;
    return out;
  }
}
