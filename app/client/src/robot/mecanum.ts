// Công thức vật lý PHY-1..PHY-5 (spec.md §6). Thuần TypeScript, không dùng React hay DOM.
// Mọi vận tốc ở đây là đơn vị web (m/s, rad/s).

// PHY-1: thông số, khai báo một chỗ duy nhất.
export const L = 0.32; // m, tâm cầu trước đến tâm cầu sau
export const D = 0.35; // m, tâm bánh trái đến tâm bánh phải
export const R = 0.05; // m, bán kính bánh
export const LEVER = (L + D) / 2; // 0.335 m (A-2)
export const MASS = 9.7; // kg
export const GRAVITY = 9.81; // m/s^2
export const MU_R = 0.05; // hệ số cản lăn
export const I_Z = MASS * ((L / 2) ** 2 + (D / 2) ** 2); // ~0.5454 kg.m^2
export const TAU_RATED = 0.981; // N.m, mô-men định mức mỗi bánh
export const F_C = (MU_R * MASS * GRAVITY) / 4; // lực cản lăn mỗi bánh
export const FILTER_TAU = 0.1; // s, hằng số thời gian bộ lọc PHY-5
export const SPEED_SUM_LIMIT = 1.6; // ngưỡng cảnh báo FR-04

/** Bốn bánh theo thứ tự A, B, C, D. */
export type Wheels = readonly [number, number, number, number];
export type Flags4 = readonly [boolean, boolean, boolean, boolean];

/** Dấu ε của bánh A, B, C, D. */
export const EPS: Wheels = [1, -1, 1, -1];
/** Dấu s của bánh A, B, C, D. */
export const SGN: Wheels = [-1, -1, 1, 1];

export interface BodyVel {
  vx: number;
  vy: number;
  wz: number;
}

export interface Pose {
  x: number;
  y: number;
  theta: number;
}

function wheelsOf(f: (i: number) => number): Wheels {
  return [f(0), f(1), f(2), f(3)];
}

function signOf(x: number): number {
  return x > 0 ? 1 : x < 0 ? -1 : 0;
}

/** PHY-2: động học ngược, vận tốc thân -> tốc độ 4 bánh (rad/s). */
export function inverseKinematics(v: BodyVel): Wheels {
  return wheelsOf((i) => (v.vx + EPS[i] * v.vy + SGN[i] * LEVER * v.wz) / R);
}

/** PHY-3: động học thuận, tốc độ 4 bánh (rad/s) -> vận tốc thân. */
export function forwardKinematics(w: Wheels): BodyVel {
  let sum = 0;
  let sumEps = 0;
  let sumSgn = 0;
  for (let i = 0; i < 4; i++) {
    sum += w[i];
    sumEps += EPS[i] * w[i];
    sumSgn += SGN[i] * w[i];
  }
  return {
    vx: (R / 4) * sum,
    vy: (R / 4) * sumEps,
    wz: (R / (4 * LEVER)) * sumSgn,
  };
}

/** PHY-3: thành phần dư e (m/s). Khác 0 nghĩa là bánh đánh nhau. */
export function wheelResidual(w: Wheels): number {
  return (R / 4) * (w[0] - w[1] - w[2] + w[3]);
}

/** PHY-4: vận tốc thân sang đạo hàm tư thế trong khung thế giới. */
export function bodyToWorld(
  v: BodyVel,
  theta: number,
): { xDot: number; yDot: number; thetaDot: number } {
  const c = Math.cos(theta);
  const s = Math.sin(theta);
  return {
    xDot: v.vx * c - v.vy * s,
    yDot: v.vx * s + v.vy * c,
    thetaDot: v.wz,
  };
}

/** FR-04: tổng |vx| + |vy| + lever*|wz| (m/s). */
export function speedSum(v: BodyVel): number {
  return Math.abs(v.vx) + Math.abs(v.vy) + LEVER * Math.abs(v.wz);
}

/** FR-04: true khi vượt 1.6 m/s. Chỉ để cảnh báo, không được dùng để chặn lệnh. */
export function exceedsSpeedSum(v: BodyVel): boolean {
  return speedSum(v) > SPEED_SUM_LIMIT;
}

export interface DynamicsResult {
  ax: number;
  ay: number;
  wzDot: number;
  Fx: number;
  Fy: number;
  Mz: number;
  /** Lực dọc từng bánh F_d,i (N). */
  Fd: Wheels;
  /** Mô-men từng bánh tau_i (N.m). */
  tau: Wheels;
  /** |tau_i| / TAU_RATED * 100. */
  tauPct: Wheels;
  /** true khi |tau_i| > TAU_RATED. */
  over: Flags4;
}

/**
 * PHY-5 phần lực: từ gia tốc thân (ax, ay đã trừ thành phần ly tâm) và wzDot
 * tính lực, mô-men. `wheels` chỉ dùng để lấy dấu sign(omega_i) của lực cản lăn.
 */
export function computeDynamics(
  acc: { ax: number; ay: number; wzDot: number },
  wheels: Wheels,
): DynamicsResult {
  const Fx = MASS * acc.ax;
  const Fy = MASS * acc.ay;
  const Mz = I_Z * acc.wzDot;
  const Fd = wheelsOf((i) => (Fx + EPS[i] * Fy + (SGN[i] * Mz) / LEVER) / 4);
  const tau = wheelsOf((i) => R * (Fd[i] + F_C * signOf(wheels[i])));
  const tauPct = wheelsOf((i) => (100 * Math.abs(tau[i])) / TAU_RATED);
  const over: Flags4 = [
    Math.abs(tau[0]) > TAU_RATED,
    Math.abs(tau[1]) > TAU_RATED,
    Math.abs(tau[2]) > TAU_RATED,
    Math.abs(tau[3]) > TAU_RATED,
  ];
  return {
    ax: acc.ax,
    ay: acc.ay,
    wzDot: acc.wzDot,
    Fx,
    Fy,
    Mz,
    Fd,
    tau,
    tauPct,
    over,
  };
}

/**
 * PHY-5: ước lượng động lực học từ vận tốc đo. Đạo hàm vận tốc được lọc thông
 * thấp bậc 1 (hằng số thời gian `tau`, mặc định 0.1 s). Gọi `update` mỗi lần có
 * mẫu vận tốc mới, kèm dt (s) kể từ mẫu trước.
 */
export class DynamicsEstimator {
  private readonly tauFilter: number;
  private prev: BodyVel | null = null;
  private vxDot = 0;
  private vyDot = 0;
  private wzDotF = 0;

  constructor(tauFilter: number = FILTER_TAU) {
    this.tauFilter = tauFilter;
  }

  reset(): void {
    this.prev = null;
    this.vxDot = 0;
    this.vyDot = 0;
    this.wzDotF = 0;
  }

  /** `v` là vận tốc đo (đơn vị web), `wheels` là tốc độ bánh (rad/s) tương ứng. */
  update(v: BodyVel, wheels: Wheels, dt: number): DynamicsResult {
    if (Number.isFinite(dt) && dt > 0) {
      if (this.prev !== null) {
        const alpha = dt / (this.tauFilter + dt);
        this.vxDot += alpha * ((v.vx - this.prev.vx) / dt - this.vxDot);
        this.vyDot += alpha * ((v.vy - this.prev.vy) / dt - this.vyDot);
        this.wzDotF += alpha * ((v.wz - this.prev.wz) / dt - this.wzDotF);
      }
      this.prev = { vx: v.vx, vy: v.vy, wz: v.wz };
    }
    return computeDynamics(
      {
        ax: this.vxDot - v.wz * v.vy,
        ay: this.vyDot + v.wz * v.vx,
        wzDot: this.wzDotF,
      },
      wheels,
    );
  }
}
