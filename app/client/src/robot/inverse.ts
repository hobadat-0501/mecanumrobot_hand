// T11 (FR-05, FR-06, PHY-6): logic thuần cho trang động học ngược. Không dùng React hay DOM.
// Đổi độ sang rad, phân tích ô nhập (không bao giờ để NaN lọt vào bộ điều khiển),
// dựng RunDriver bọc trackStep, và tính tiến độ.

import type { RunDriver, RunInput, RunStep } from "./control";
import { inverseKinematics } from "./mecanum";
import type { BodyVel, Pose, Wheels } from "./mecanum";
import {
  DEFAULT_RUN_PARAMS,
  TOL_ANG,
  TOL_POS,
  createTrack,
  expectedDuration,
  goalFromDistanceHeading,
  trackError,
  trackStep,
  wrapAngle,
} from "./motion";
import type { RunParams, TrackError, TrackState } from "./motion";

export const DEG_TO_RAD = Math.PI / 180;
export const RAD_TO_DEG = 180 / Math.PI;

export const degToRad = (deg: number): number => deg * DEG_TO_RAD;
export const radToDeg = (rad: number): number => rad * RAD_TO_DEG;

/** Số hữu hạn (âm, 0, dương đều nhận). Rỗng hoặc không phải số thì null. */
export function parseNumber(text: string): number | null {
  if (text.trim() === "") return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : null;
}

export type InputKind = "distance" | "pose";

/** Nội dung các ô nhập, giữ nguyên dạng chữ. */
export interface InverseFields {
  distance: string; // m
  heading: string; // độ
  x: string; // m
  y: string; // m
  theta: string; // độ
  /** Thời gian mong muốn để tới đích (s). */
  duration: string;
}

export const DEFAULT_FIELDS: InverseFields = {
  distance: "0.5",
  heading: "0",
  x: "0.4",
  y: "0.2",
  theta: "30",
  duration: "5",
};

export type FieldKey = keyof InverseFields;

export const FIELD_LABEL: Record<FieldKey, string> = {
  distance: "Quãng đường",
  heading: "Hướng",
  x: "x đích",
  y: "y đích",
  theta: "θ đích",
  duration: "Thời gian",
};

/** Mục tiêu đã phân tích, đơn vị chuẩn (m, rad). Kiểu A chưa quy đổi vì cần tư thế lúc bấm chạy. */
export type ParsedTarget =
  | { kind: "distance"; s: number; alpha: number }
  | { kind: "pose"; goal: Pose };

export interface ParsedInput {
  target: ParsedTarget;
  /** Thời gian mong muốn (s); tốc độ chạy suy ra từ quãng đường chia thời gian. */
  durationS: number;
}

export type ParseResult =
  | { ok: true; value: ParsedInput }
  | { ok: false; errors: Partial<Record<FieldKey, string>>; message: string };

const NEED_NUMBER = "cần là số";
const NEED_POSITIVE = "cần là số lớn hơn 0";

/** Phân tích toàn bộ ô nhập cho kiểu đã chọn. Mọi lỗi được gom lại để báo lý do vô hiệu hóa nút chạy. */
export function parseInverseFields(
  kind: InputKind,
  f: InverseFields,
): ParseResult {
  const errors: Partial<Record<FieldKey, string>> = {};
  const num = (key: FieldKey): number => {
    const v = parseNumber(f[key]);
    if (v === null) {
      errors[key] = NEED_NUMBER;
      return 0;
    }
    return v;
  };
  const pos = (key: FieldKey): number => {
    const v = parseNumber(f[key]);
    if (v === null || v <= 0) {
      errors[key] = NEED_POSITIVE;
      return 1;
    }
    return v;
  };

  let target: ParsedTarget;
  if (kind === "distance") {
    target = {
      kind: "distance",
      s: num("distance"),
      alpha: degToRad(num("heading")),
    };
  } else {
    target = {
      kind: "pose",
      goal: { x: num("x"), y: num("y"), theta: degToRad(num("theta")) },
    };
  }
  const durationS = pos("duration");
  const keys = Object.keys(errors) as FieldKey[];
  if (keys.length > 0) {
    const message = keys.map((k) => `${FIELD_LABEL[k]} ${errors[k]}`).join("; ");
    return { ok: false, errors, message };
  }
  return { ok: true, value: { target, durationS } };
}

/** Tư thế đích: kiểu A quy đổi theo PHY-6 từ tư thế lúc bấm chạy, kiểu B dùng thẳng. */
export function resolveGoal(target: ParsedTarget, start: Pose): Pose {
  return target.kind === "distance"
    ? goalFromDistanceHeading(start, target.s, target.alpha)
    : { ...target.goal };
}

/** Kế hoạch chạy suy ra từ đích và thời gian: tốc độ thân, tốc độ bốn bánh, tham số bộ bám đích. */
export interface InversePlan {
  params: RunParams;
  body: BodyVel;
  wheels: Wheels;
  /** Quãng đường (m) và góc quay có dấu (rad) tới đích. */
  distance: number;
  turn: number;
}

const EPS = 1e-9;

/**
 * Tốc độ chạy = quãng đường / thời gian, tốc độ quay = góc / thời gian, hướng theo khung thân.
 * Kiểu A không cần tư thế hiện tại (start null). Kiểu B cần start, thiếu thì trả null.
 */
export function planInverse(target: ParsedTarget, durationS: number, start: Pose | null): InversePlan | null {
  if (!Number.isFinite(durationS) || durationS <= 0) return null;
  const origin = start ?? (target.kind === "distance" ? { x: 0, y: 0, theta: 0 } : null);
  if (origin === null) return null;
  const e = trackError(origin, resolveGoal(target, origin));
  const body: BodyVel = {
    vx: e.dist > EPS ? e.ebx / durationS : 0,
    vy: e.dist > EPS ? e.eby / durationS : 0,
    wz: Math.abs(e.etheta) > EPS ? e.etheta / durationS : 0,
  };
  if (![body.vx, body.vy, body.wz, e.dist].every(Number.isFinite)) return null;
  return {
    params: {
      vCruise: e.dist > EPS ? e.dist / durationS : DEFAULT_RUN_PARAMS.vCruise,
      wzCruise: Math.abs(e.etheta) > EPS ? Math.abs(e.etheta) / durationS : DEFAULT_RUN_PARAMS.wzCruise,
    },
    body,
    wheels: inverseKinematics(body),
    distance: e.dist,
    turn: e.etheta,
  };
}

export interface Progress {
  /** Quãng đường còn lại (m). */
  remainingDist: number;
  /** Góc còn lại, có dấu, quấn về [-pi, pi] (rad). */
  remainingAngle: number;
  /** 0..100. */
  percent: number;
}

/** Tiến độ: phần còn lại lớn nhất giữa tịnh tiến và quay, so với lúc bắt đầu. Dưới dung sai thì tính là đã tới. */
export function computeProgress(
  initial: TrackError,
  current: TrackError,
  done = false,
): Progress {
  const frac = (now: number, start: number, tol: number): number =>
    start <= tol ? 0 : Math.min(1, Math.max(0, now / start));
  const remaining = Math.max(
    frac(current.dist, initial.dist, TOL_POS),
    frac(Math.abs(current.etheta), Math.abs(initial.etheta), TOL_ANG),
  );
  return {
    remainingDist: current.dist,
    remainingAngle: current.etheta,
    percent: done ? 100 : Math.round((1 - remaining) * 100),
  };
}

/** Một lần chạy động học ngược: RunDriver bọc trackStep và nhớ lần bước gần nhất để trang hiển thị. */
export class InverseRun implements RunDriver {
  readonly start: Pose;
  readonly goal: Pose;
  readonly params: RunParams;
  readonly tExpected: number;
  readonly initialError: TrackError;
  /** cmd_vel của chu kỳ gần nhất (đang gửi). */
  lastCmd: BodyVel = { vx: 0, vy: 0, wz: 0 };
  lastError: TrackError;
  finished = false;
  done = false;
  private track: TrackState;

  /** Ném RangeError nếu tham số hoặc tư thế không hợp lệ (createTrack). */
  constructor(start: Pose, goal: Pose, params: RunParams) {
    this.track = createTrack(start, goal, params);
    this.start = { ...start };
    this.goal = { ...goal };
    this.params = { ...params };
    this.tExpected = expectedDuration(start, goal, params);
    this.initialError = trackError(start, goal);
    this.lastError = this.initialError;
  }

  step(input: RunInput): RunStep {
    if (input.pose === null) {
      this.finished = true;
      this.lastCmd = { vx: 0, vy: 0, wz: 0 };
      return {
        cmd: this.lastCmd,
        status: { kind: "aborted", reason: "stale" },
      };
    }
    const out = trackStep(this.track, { ...input, pose: input.pose });
    this.track = out.state;
    this.lastCmd = out.cmd;
    this.lastError = out.error;
    this.finished = out.status.kind !== "running";
    this.done = out.status.kind === "done";
    return { cmd: out.cmd, status: out.status };
  }

  progress(): Progress {
    return computeProgress(this.initialError, this.lastError, this.done);
  }

  /** 4 tốc độ bánh (rad/s) cho lệnh đang gửi. */
  wheels(): Wheels {
    return inverseKinematics(this.lastCmd);
  }
}

/** Đích quấn góc để hiển thị trong [-180, 180] độ. */
export function wrapDeg(rad: number): number {
  return radToDeg(wrapAngle(rad));
}

/** Nhãn tiếng Việt cho lý do kết thúc lần chạy. */
export const END_REASON_LABEL: Record<string, string> = {
  stale: "dữ liệu trạng thái quá cũ (hơn 0,5 s)",
  disarmed: "robot đã disarm",
  key: "có phím di chuyển được nhấn",
  timeout: "quá thời gian cho phép",
  blur: "cửa sổ mất focus",
  hidden: "tab bị ẩn",
  closed: "mất kết nối tới app server",
  stop: "dừng khẩn",
  cancel: "người dùng hủy",
  error: "lỗi trong bộ điều khiển",
};
