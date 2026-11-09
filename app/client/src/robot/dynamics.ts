// Nguồn dữ liệu động lực học cho trang /dynamics (FR-07, PHY-5). Mỗi state nhận được đi qua
// DynamicsEstimator đúng một lần; kết quả và lịch sử Fx, Fy, Mz nằm ngoài React state (NFR-03).
// Trang chỉ đăng ký (startDynamicsFeed) khi đang mở; rời trang thì hủy đăng ký và reset.

import { DynamicsEstimator, inverseKinematics } from "./mecanum";
import type { BodyVel, DynamicsResult, Wheels } from "./mecanum";
import { getTelemetry, getTelemetryAt, subscribeTelemetry } from "./store";

/** Số mẫu lịch sử giữ lại (20 Hz nên 400 mẫu là khoảng 20 s). */
export const HISTORY_CAPACITY = 400;

/** true khi |tau_i| vượt định mức ở bất kỳ bánh nào. */
export function anyOver(result: Pick<DynamicsResult, "over">): boolean {
  return result.over.some(Boolean);
}

/** Giữ cảnh báo vượt định mức thêm khoảng này (ms) để đỉnh ngắn không bị bỏ lỡ bởi chu kỳ hiển thị. */
export const OVER_HOLD_MS = 3000;

export interface OverEvent {
  /** Thời điểm (ms, đồng hồ đơn điệu) mẫu vượt gần nhất. */
  at: number;
  /** Bánh đã vượt trong lần đó (A, B, C, D). */
  wheels: readonly [boolean, boolean, boolean, boolean];
  /** % định mức cao nhất của lần vượt gần nhất. */
  pct: number;
}

/** Vòng đệm cố định cho các chuỗi thời gian Fx, Fy, Mz. */
export class SeriesBuffer {
  private readonly data: Float64Array[];
  private start = 0;
  private size = 0;
  /** Tăng mỗi khi nội dung đổi; nơi vẽ dùng để biết cần vẽ lại. */
  version = 0;

  constructor(
    readonly channels = 3,
    readonly capacity = HISTORY_CAPACITY,
  ) {
    this.data = Array.from({ length: channels }, () => new Float64Array(capacity));
  }

  get length(): number {
    return this.size;
  }

  /** Chỉ số 0 là mẫu cũ nhất. */
  at(channel: number, i: number): number {
    return this.data[channel][(this.start + i) % this.capacity];
  }

  push(values: readonly number[]): void {
    const idx = (this.start + this.size) % this.capacity;
    for (let c = 0; c < this.channels; c++) this.data[c][idx] = values[c];
    if (this.size < this.capacity) this.size += 1;
    else this.start = (this.start + 1) % this.capacity;
    this.version += 1;
  }

  clear(): void {
    this.start = 0;
    this.size = 0;
    this.version += 1;
  }
}

/**
 * Ghép bộ ước lượng với lịch sử. `sample` nhận vận tốc đo và thời điểm nhận (ms, đồng hồ đơn điệu);
 * dt tính từ mẫu hợp lệ trước đó. Tốc độ bánh lấy từ động học ngược của chính vận tốc đo.
 */
export class DynamicsFeed {
  readonly history = new SeriesBuffer();
  private readonly estimator = new DynamicsEstimator();
  private lastAt: number | null = null;
  result: DynamicsResult | null = null;
  /** Lần vượt định mức gần nhất, giữ để hiển thị; null nếu chưa có. */
  lastOver: OverEvent | null = null;
  /** Tốc độ bánh ω_i (rad/s) của mẫu hợp lệ gần nhất. */
  wheels: Wheels | null = null;

  sample(vel: BodyVel | null, atMs: number): DynamicsResult | null {
    if (vel === null || !Number.isFinite(atMs)) return this.result;
    if (![vel.vx, vel.vy, vel.wz].every(Number.isFinite)) return this.result;
    const dt = this.lastAt === null ? 0.05 : (atMs - this.lastAt) / 1000;
    if (!(dt > 0)) return this.result; // đảo thứ tự hoặc trùng thời điểm: bỏ
    const wheels = inverseKinematics(vel);
    const r = this.estimator.update(vel, wheels, dt);
    this.wheels = wheels;
    this.lastAt = atMs;
    this.result = r;
    this.history.push([r.Fx, r.Fy, r.Mz]);
    if (anyOver(r)) this.lastOver = { at: atMs, wheels: r.over, pct: Math.max(...r.tauPct) };
    return r;
  }

  reset(): void {
    this.estimator.reset();
    this.history.clear();
    this.lastAt = null;
    this.result = null;
    this.wheels = null;
    this.lastOver = null;
  }
}

export const dynamicsFeed = new DynamicsFeed();

/** Bắt đầu nạp state vào feed; trả hàm hủy (reset feed). Gọi từ effect của trang. */
export function startDynamicsFeed(): () => void {
  let lastSeen = getTelemetryAt();
  const unsubscribe = subscribeTelemetry(() => {
    const msg = getTelemetry();
    if (msg === null) {
      dynamicsFeed.reset(); // kết nối đóng
      return;
    }
    const at = getTelemetryAt();
    if (at === lastSeen) return; // không phải state mới
    lastSeen = at;
    dynamicsFeed.sample(msg.vel, at);
  });
  return () => {
    unsubscribe();
    dynamicsFeed.reset();
  };
}
