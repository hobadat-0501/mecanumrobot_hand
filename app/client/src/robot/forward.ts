// Logic thuần của trang động học thuận (FR-04, PHY-2..PHY-4): đọc số nhập an toàn, chuỗi tính
// ω_i -> v_i -> (vx, vy, wz) -> (ẋ, ẏ, θ̇), thành phần dư, lý do chưa chạy được, bọc RunDriver.
// Không dùng React hay DOM.

import { exceedsSpeedSum, forwardKinematics, bodyToWorld, wheelResidual, R } from "./mecanum";
import type { BodyVel, Wheels } from "./mecanum";
import { createWheelRun, wheelRunStep } from "./motion";
import type { WheelRun } from "./motion";
import type { EndReason, RunDriver, RunEnd } from "./control";

export const DEFAULT_DURATION_S = 3;
/** Dư |e| (m/s) từ ngưỡng này trở lên mới coi là khác 0, để nhiễu làm tròn số thực không báo giả. */
export const RESIDUAL_EPS = 1e-6;

/** Đọc một số từ ô nhập. Rỗng, chữ, NaN, Infinity: null. Chấp nhận dấu phẩy thập phân. */
export function parseNumber(text: string): number | null {
  const t = text.trim().replace(",", ".");
  if (t === "") return null;
  const value = Number(t);
  return Number.isFinite(value) ? value : null;
}

/** Số hữu hạn lớn hơn 0 (thời gian chạy). Không có chặn trên. */
export function parsePositive(text: string): number | null {
  const value = parseNumber(text);
  return value !== null && value > 0 ? value : null;
}

/** Đủ bốn số hữu hạn thì trả bộ bánh, thiếu hoặc sai một ô thì null (không bao giờ NaN). */
export function parseWheels(texts: readonly string[]): Wheels | null {
  if (texts.length !== 4) return null;
  const v = texts.map(parseNumber);
  if (v.some((x) => x === null)) return null;
  const w: Wheels = [v[0] as number, v[1] as number, v[2] as number, v[3] as number];
  // Giá trị hữu hạn nhưng quá lớn có thể làm tràn tổng: không bao giờ phát ra lệnh vô hạn.
  const b = forwardKinematics(w);
  if (![b.vx, b.vy, b.wz].every(Number.isFinite)) return null;
  if (!Number.isFinite(wheelResidual(w))) return null;
  return w;
}

export interface Chain {
  /** v_i = r·ω_i (m/s). */
  rim: Wheels;
  body: BodyVel;
  /** Null khi chưa biết θ. */
  world: { xDot: number; yDot: number; thetaDot: number } | null;
  /** PHY-3: thành phần dư e (m/s). */
  residual: number;
  residualNonZero: boolean;
  /** FR-04: |vx|+|vy|+lever·|wz| > 1.6 m/s. Chỉ cảnh báo. */
  exceeds: boolean;
}

/** Toàn bộ chuỗi tính từ tốc độ bánh và góc θ hiện tại (rad, hoặc null nếu chưa có state). */
export function computeChain(wheels: Wheels, theta: number | null): Chain {
  const body = forwardKinematics(wheels);
  const residual = wheelResidual(wheels);
  return {
    rim: [R * wheels[0], R * wheels[1], R * wheels[2], R * wheels[3]],
    body,
    world: theta !== null && Number.isFinite(theta) ? bodyToWorld(body, theta) : null,
    residual,
    residualNonZero: Math.abs(residual) > RESIDUAL_EPS,
    exceeds: exceedsSpeedSum(body),
  };
}

export interface RunReadiness {
  open: boolean;
  hasState: boolean;
  stale: boolean;
  robotLink: boolean;
  armed: boolean;
  isDriver: boolean;
  wheelsValid: boolean;
  durationValid: boolean;
}

/** Lý do nút Chạy bị khóa (tiếng Việt), hoặc null nếu chạy được. */
export function runBlockReason(r: RunReadiness): string | null {
  if (!r.open || !r.hasState) return "Chưa kết nối tới app server.";
  if (r.stale) return "Mất dữ liệu: không nhận được trạng thái mới.";
  if (!r.isDriver) return "Chỉ xem: cần nhập mã điều khiển để có quyền lái.";
  if (!r.robotLink) return "Mất link tới robot.";
  if (!r.armed) return "Chưa arm: bấm R hoặc nút Arm trên thanh trạng thái.";
  if (!r.wheelsValid) return "Cần nhập đủ bốn tốc độ bánh là số hợp lệ.";
  if (!r.durationValid) return "Thời gian chạy phải là số lớn hơn 0.";
  return null;
}

const END_TEXT: Record<EndReason, string> = {
  stale: "mất dữ liệu trạng thái",
  disarmed: "disarm",
  key: "bấm phím di chuyển",
  timeout: "quá thời gian",
  blur: "mất focus cửa sổ",
  hidden: "ẩn tab",
  closed: "mất kết nối",
  stop: "dừng khẩn",
  cancel: "bấm Dừng",
  error: "lỗi bộ chạy",
};

/** Kết thúc của lần chạy động học thuận gần nhất để hiển thị; null nếu lần gần nhất thuộc nguồn khác. */
export function describeRunEnd(end: RunEnd | null): { tone: "ok" | "warn"; text: string } | null {
  if (end === null || end.source !== "forward") return null;
  if (end.done) return { tone: "ok", text: "Xong: hết thời gian, đã gửi lệnh 0." };
  return { tone: "warn", text: `Đã hủy: ${END_TEXT[end.reason ?? "cancel"]}. Đã gửi lệnh 0.` };
}

export interface WheelDriver extends RunDriver {
  readonly durationS: number;
  /** Thời gian còn lại (s), không âm. */
  remaining(): number;
  readonly cmd: BodyVel;
}

/** Bọc createWheelRun/wheelRunStep của motion.ts thành RunDriver. Ném RangeError nếu đầu vào sai. */
export function createWheelDriver(wheels: Wheels, durationS: number): WheelDriver {
  let run: WheelRun = createWheelRun(wheels, durationS);
  return {
    durationS,
    cmd: { ...run.cmd },
    remaining: () => Math.max(0, run.durationS - run.elapsed),
    step(input) {
      const r = wheelRunStep(run, input, input.dt);
      run = r.run;
      return { cmd: r.cmd, status: r.status };
    },
  };
}
