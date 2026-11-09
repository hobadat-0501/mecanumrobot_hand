// PHY-6: bộ bám đích và chạy theo tốc độ bánh. Thuần TypeScript, không dùng React hay DOM.
// Mọi hàm là bước tính thuần: nhận trạng thái + đầu vào, trả trạng thái mới + cmd_vel.
// Đầu ra chuyển động duy nhất là cmd_vel (vx, vy, wz) theo đơn vị web.

import { forwardKinematics } from "./mecanum";
import type { BodyVel, Pose, Wheels } from "./mecanum";

export const CONTROL_HZ = 20;
export const KP_LIN = 1.0;
export const KP_ANG = 1.5;
export const TOL_POS = 0.02; // m
export const TOL_ANG = 0.035; // rad
export const DONE_CYCLES = 3;
export const STALE_S = 0.5; // s

export interface RunParams {
  /** Tốc độ tịnh tiến chạy (m/s). Không chặn trên. */
  vCruise: number;
  /** Tốc độ quay chạy (rad/s). Không chặn trên. */
  wzCruise: number;
}

export const DEFAULT_RUN_PARAMS: RunParams = {
  vCruise: 0.2,
  wzCruise: 1.0,
};

export type AbortReason = "stale" | "disarmed" | "key" | "timeout";

export type RunStatus =
  | { kind: "running" }
  | { kind: "done" }
  | { kind: "aborted"; reason: AbortReason };

/** Điều kiện hủy dùng chung cho bộ bám đích và chạy theo tốc độ bánh. */
export interface RunContext {
  /** Tuổi của state mới nhất (s). */
  stateAgeS: number;
  armed: boolean;
  /** Có phím di chuyển đang được giữ. */
  keyPressed: boolean;
}

function zeroCmd(): BodyVel {
  return { vx: 0, vy: 0, wz: 0 };
}

/** Quấn góc về [-pi, pi]. */
export function wrapAngle(a: number): number {
  return Math.atan2(Math.sin(a), Math.cos(a));
}

/** Trả thông báo lỗi nếu tham số chạy không hợp lệ, ngược lại null. Không đặt chặn trên. */
export function validateRunParams(p: RunParams): string | null {
  const entries: [string, number][] = [
    ["vCruise", p.vCruise],
    ["wzCruise", p.wzCruise],
  ];
  for (const [name, value] of entries) {
    if (!Number.isFinite(value) || value <= 0) {
      return `${name} phải là số hữu hạn lớn hơn 0`;
    }
  }
  return null;
}

/** Lý do hủy theo RunContext, hoặc null. Thứ tự ưu tiên: disarmed, key, stale. */
export function abortReason(ctx: RunContext): AbortReason | null {
  if (!ctx.armed) return "disarmed";
  if (ctx.keyPressed) return "key";
  if (!(ctx.stateAgeS <= STALE_S)) return "stale";
  return null;
}

/** PHY-6 kiểu A: quy đổi (quãng đường s, hướng alpha rad so với thân) sang tư thế đích. */
export function goalFromDistanceHeading(
  start: Pose,
  s: number,
  alpha: number,
): Pose {
  return {
    x: start.x + s * Math.cos(start.theta + alpha),
    y: start.y + s * Math.sin(start.theta + alpha),
    theta: start.theta,
  };
}

/** T_dự_kiến (s) = max(quãng đường / vCruise, |góc quay| / wzCruise). */
export function expectedDuration(
  start: Pose,
  goal: Pose,
  p: RunParams,
): number {
  const dist = Math.hypot(goal.x - start.x, goal.y - start.y);
  const ang = Math.abs(wrapAngle(goal.theta - start.theta));
  return Math.max(dist / p.vCruise, ang / p.wzCruise);
}

export interface TrackError {
  /** Sai số thế giới. */
  ex: number;
  ey: number;
  /** Sai số quay về khung thân. */
  ebx: number;
  eby: number;
  dist: number;
  /** Sai số góc đã quấn về [-pi, pi]. */
  etheta: number;
}

/** Sai số tới đích; world -> body bằng góc theta của xe. */
export function trackError(pose: Pose, goal: Pose): TrackError {
  const ex = goal.x - pose.x;
  const ey = goal.y - pose.y;
  const c = Math.cos(pose.theta);
  const s = Math.sin(pose.theta);
  return {
    ex,
    ey,
    ebx: c * ex + s * ey,
    eby: -s * ex + c * ey,
    dist: Math.hypot(ex, ey),
    etheta: wrapAngle(goal.theta - pose.theta),
  };
}

export interface TrackState {
  goal: Pose;
  params: RunParams;
  /** Hạn chót = 3 * T_dự_kiến + 5 (s). */
  timeoutS: number;
  elapsed: number;
  /** Số chu kỳ liên tiếp đã nằm trong dung sai. */
  okCycles: number;
  /** cmd_vel của chu kỳ trước, dùng để giới hạn gia tốc. */
  prevCmd: BodyVel;
}

/** Tạo trạng thái bám đích. Ném RangeError nếu tham số hoặc tư thế không hợp lệ. */
export function createTrack(
  start: Pose,
  goal: Pose,
  params: RunParams,
): TrackState {
  const msg = validateRunParams(params);
  if (msg !== null) throw new RangeError(msg);
  const nums = [start.x, start.y, start.theta, goal.x, goal.y, goal.theta];
  if (!nums.every((n) => Number.isFinite(n))) {
    throw new RangeError("tư thế đầu hoặc đích không hữu hạn");
  }
  return {
    goal: { ...goal },
    params: { ...params },
    timeoutS: 3 * expectedDuration(start, goal, params) + 5,
    elapsed: 0,
    okCycles: 0,
    prevCmd: zeroCmd(),
  };
}

export interface TrackInput extends RunContext {
  /** Tư thế hiện tại (khung odometry). */
  pose: Pose;
  /** Thời gian từ chu kỳ trước (s), thường 1/CONTROL_HZ. */
  dt: number;
}

export interface TrackStep {
  cmd: BodyVel;
  state: TrackState;
  status: RunStatus;
  error: TrackError;
}

/** Một chu kỳ điều khiển PHY-6. Khi done hoặc aborted, cmd là 0. */
export function trackStep(s: TrackState, input: TrackInput): TrackStep {
  const dt = Number.isFinite(input.dt) && input.dt > 0 ? input.dt : 0;
  const elapsed = s.elapsed + dt;
  const error = trackError(input.pose, s.goal);

  const poseOk = [input.pose.x, input.pose.y, input.pose.theta].every(Number.isFinite);
  let reason: AbortReason | null = poseOk ? abortReason(input) : "stale";
  if (reason === null && elapsed > s.timeoutS) reason = "timeout";
  if (reason !== null) {
    return {
      cmd: zeroCmd(),
      state: { ...s, elapsed, okCycles: 0, prevCmd: zeroCmd() },
      status: { kind: "aborted", reason },
      error,
    };
  }

  const inTol = error.dist < TOL_POS && Math.abs(error.etheta) < TOL_ANG;
  const okCycles = inTol ? s.okCycles + 1 : 0;
  if (okCycles >= DONE_CYCLES) {
    return {
      cmd: zeroCmd(),
      state: { ...s, elapsed, okCycles, prevCmd: zeroCmd() },
      status: { kind: "done" },
      error,
    };
  }

  const p = s.params;
  // Tốc độ mong muốn; thu nhỏ vector tịnh tiến để giữ hướng.
  let vx = KP_LIN * error.ebx;
  let vy = KP_LIN * error.eby;
  // Chỉ giới hạn theo tốc độ chạy; tăng/giảm tốc do STM đảm nhiệm (PHY-6).
  const speedMax = p.vCruise;
  const speed = Math.hypot(vx, vy);
  if (speed > speedMax) {
    const k = speedMax / speed;
    vx *= k;
    vy *= k;
  }
  let wz = KP_ANG * error.etheta;
  if (Math.abs(wz) > p.wzCruise) wz = Math.sign(wz) * p.wzCruise;

  const cmd: BodyVel = { vx, vy, wz };
  return {
    cmd,
    state: { ...s, elapsed, okCycles, prevCmd: { ...cmd } },
    status: { kind: "running" },
    error,
  };
}

export interface WheelRun {
  /** cmd_vel cố định tính từ tốc độ bánh bằng động học thuận. */
  cmd: BodyVel;
  durationS: number;
  elapsed: number;
}

/** FR-04: tạo lần chạy theo tốc độ bánh (rad/s) trong durationS giây. Ném RangeError nếu không hợp lệ. */
export function createWheelRun(wheels: Wheels, durationS: number): WheelRun {
  if (!wheels.every((w) => Number.isFinite(w))) {
    throw new RangeError("tốc độ bánh không hữu hạn");
  }
  if (!Number.isFinite(durationS) || durationS <= 0) {
    throw new RangeError("thời gian chạy phải là số hữu hạn lớn hơn 0");
  }
  return { cmd: forwardKinematics(wheels), durationS, elapsed: 0 };
}

export interface WheelRunStep {
  cmd: BodyVel;
  run: WheelRun;
  status: RunStatus;
}

/** Một chu kỳ chạy theo tốc độ bánh. Hết giờ thì done; hủy theo RunContext thì aborted. cmd là 0 khi kết thúc. */
export function wheelRunStep(
  run: WheelRun,
  ctx: RunContext,
  dt: number,
): WheelRunStep {
  const elapsed = run.elapsed + (Number.isFinite(dt) && dt > 0 ? dt : 0);
  const next: WheelRun = { ...run, elapsed };
  const reason = abortReason(ctx);
  if (reason !== null) {
    return { cmd: zeroCmd(), run: next, status: { kind: "aborted", reason } };
  }
  if (elapsed >= run.durationS) {
    return { cmd: zeroCmd(), run: next, status: { kind: "done" } };
  }
  return { cmd: { ...run.cmd }, run: next, status: { kind: "running" } };
}
