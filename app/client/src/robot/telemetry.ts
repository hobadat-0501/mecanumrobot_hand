// Logic thuần cho trang tổng quan và hệ thống (FR-08, FR-11, FR-12): độ trễ vòng lệnh,
// bộ đệm lịch sử quỹ đạo có giới hạn, phát hiện state quá cũ, đọc sức khỏe thiết bị.
// Không dùng React hay DOM; store.ts giữ các thể hiện, trang chỉ đọc.

import type { LooseRecord } from "./protocol";

/** Quá ngưỡng này không có state mới (socket vẫn mở) thì coi là mất dữ liệu. */
export const STALE_MS = 1000;

/** Số giây trở lên không có state: true. `ageMs` là tuổi state gần nhất; vô cực nếu chưa có. */
export function isStale(ageMs: number, thresholdMs: number = STALE_MS): boolean {
  return ageMs > thresholdMs;
}

// ---- độ trễ vòng lệnh: cmd_vel gửi đi -> last_cmd_seq trong state đạt seq đó ----

export interface LatencyStats {
  /** Mẫu gần nhất (ms); null nếu chưa có. */
  last: number | null;
  /** Phân vị 95 theo hạng gần nhất trên cửa sổ; null nếu chưa có mẫu. */
  p95: number | null;
  /** Số mẫu trong cửa sổ. */
  count: number;
}

/** Phân vị p (0..1) theo hạng gần nhất. Mảng rỗng: null. */
export function percentile(values: readonly number[], p: number): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const rank = Math.ceil(p * sorted.length);
  return sorted[Math.min(sorted.length - 1, Math.max(0, rank - 1))];
}

export class LatencyTracker {
  private readonly pending = new Map<number, number>();
  private samples: number[] = [];
  private lastMs: number | null = null;

  constructor(
    private readonly windowSize = 100,
    private readonly maxPending = 256,
    private readonly expireMs = 5000,
  ) {}

  /** Ghi thời điểm gửi (ms, đồng hồ đơn điệu) của một seq. */
  sent(seq: number, nowMs: number): void {
    this.pending.set(seq, nowMs);
    while (this.pending.size > this.maxPending) {
      const oldest = this.pending.keys().next().value;
      if (oldest === undefined) break;
      this.pending.delete(oldest);
    }
  }

  /**
   * State báo `last_cmd_seq` tại `nowMs`. Chỉ khi nó khớp đúng một seq đang chờ mới có mẫu;
   * seq khác (do tab lái khác, hoặc sau khi tải lại trang seq bắt đầu lại) bị bỏ qua. Khi khớp,
   * các seq cũ hơn đã bị thay thế (hàng đợi chỉ giữ bản mới nhất) nên bị xóa, không tính vì
   * sẽ đo quá lớn. Trả mẫu vừa ghi (ms) hoặc null.
   */
  ack(lastCmdSeq: number | null, nowMs: number): number | null {
    for (const [seq, at] of this.pending) {
      if (nowMs - at > this.expireMs) this.pending.delete(seq);
    }
    if (lastCmdSeq === null) return null;
    const sentAt = this.pending.get(lastCmdSeq);
    if (sentAt === undefined) return null;
    for (const seq of [...this.pending.keys()]) {
      if (seq <= lastCmdSeq) this.pending.delete(seq);
    }
    const ms = Math.max(0, nowMs - sentAt);
    this.lastMs = ms;
    this.samples.push(ms);
    if (this.samples.length > this.windowSize) this.samples.shift();
    return ms;
  }

  clear(): void {
    this.pending.clear();
    this.samples = [];
    this.lastMs = null;
  }

  stats(): LatencyStats {
    return {
      last: this.lastMs,
      p95: percentile(this.samples, 0.95),
      count: this.samples.length,
    };
  }
}

// ---- lịch sử quỹ đạo: vòng đệm cố định, nằm ngoài React state (NFR-03) ----

export class HistoryBuffer {
  private readonly xs: Float64Array;
  private readonly ys: Float64Array;
  private readonly ths: Float64Array;
  private start = 0;
  private size = 0;
  /** Tăng mỗi khi nội dung đổi; nơi vẽ dùng để biết cần vẽ lại. */
  version = 0;

  constructor(
    readonly capacity = 1200,
    /** Bước tối thiểu (m) giữa hai điểm liên tiếp; nhỏ hơn thì bỏ để xe đứng yên không đầy bộ đệm. */
    private readonly minStep = 0.002,
    /** Nhảy xa hơn (m) trong một mẫu là gián đoạn (reset odometry): xóa lịch sử cũ. */
    private readonly maxJump = 0.5,
  ) {
    this.xs = new Float64Array(capacity);
    this.ys = new Float64Array(capacity);
    this.ths = new Float64Array(capacity);
  }

  get length(): number {
    return this.size;
  }

  /** Chỉ số 0 là điểm cũ nhất. */
  x(i: number): number {
    return this.xs[(this.start + i) % this.capacity];
  }
  y(i: number): number {
    return this.ys[(this.start + i) % this.capacity];
  }
  theta(i: number): number {
    return this.ths[(this.start + i) % this.capacity];
  }

  /** Thêm điểm. Giá trị không hữu hạn bị bỏ. Trả true nếu điểm được lưu. */
  push(x: number, y: number, theta: number): boolean {
    if (!(Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(theta))) return false;
    if (this.size > 0) {
      const last = this.size - 1;
      const dist = Math.hypot(x - this.x(last), y - this.y(last));
      if (dist > this.maxJump) this.clear();
      else if (dist < this.minStep) {
        // Đứng yên: chỉ cập nhật hướng của điểm cuối, không thêm điểm.
        const idx = (this.start + last) % this.capacity;
        if (this.ths[idx] !== theta) {
          this.ths[idx] = theta;
          this.version += 1;
        }
        return false;
      }
    }
    const idx = (this.start + this.size) % this.capacity;
    this.xs[idx] = x;
    this.ys[idx] = y;
    this.ths[idx] = theta;
    if (this.size < this.capacity) this.size += 1;
    else this.start = (this.start + 1) % this.capacity;
    this.version += 1;
    return true;
  }

  clear(): void {
    this.start = 0;
    this.size = 0;
    this.version += 1;
  }
}

// ---- LiDAR (FR-10): thống kê scan, tốc độ nhận, tuổi dữ liệu ----

/** Quá ngưỡng này không có scan mới thì coi là mất dữ liệu LiDAR (scan tới 5 đến 10 Hz). */
export const SCAN_STALE_MS = 1000;

export type ScanStatus = "live" | "stale" | "none";

/** `ageMs` là tuổi scan gần nhất; null nếu chưa nhận scan nào. */
export function scanStatus(ageMs: number | null, thresholdMs: number = SCAN_STALE_MS): ScanStatus {
  if (ageMs === null) return "none";
  return isStale(ageMs, thresholdMs) ? "stale" : "live";
}

export interface ScanStats {
  /** Số ô có điểm (khác 0). */
  count: number;
  /** Khoảng cách gần nhất (mm) và góc ô đó (độ, 0 là phía trước, ngược chiều kim đồng hồ); null nếu không có điểm. */
  nearestMm: number | null;
  nearestDeg: number | null;
}

export function scanStats(ranges: ArrayLike<number>): ScanStats {
  let count = 0;
  let nearestMm: number | null = null;
  let nearestDeg: number | null = null;
  for (let i = 0; i < ranges.length; i++) {
    const mm = ranges[i];
    if (mm === 0) continue;
    count += 1;
    if (nearestMm === null || mm < nearestMm) {
      nearestMm = mm;
      nearestDeg = i;
    }
  }
  return { count, nearestMm, nearestDeg };
}

/** Tốc độ nhận (Hz) trên cửa sổ trượt; 0 khi chưa đủ hai mẫu hoặc mẫu cuối đã cũ. */
export class RateMeter {
  private times: number[] = [];

  constructor(private readonly windowMs = 2000) {}

  tick(nowMs: number): void {
    this.times.push(nowMs);
    const cutoff = nowMs - this.windowMs;
    while (this.times.length > 0 && this.times[0] < cutoff) this.times.shift();
  }

  rate(nowMs: number): number {
    const n = this.times.length;
    if (n < 2 || nowMs - this.times[n - 1] > this.windowMs / 2) return 0;
    const span = this.times[n - 1] - this.times[0];
    return span > 0 ? ((n - 1) * 1000) / span : 0;
  }

  clear(): void {
    this.times = [];
  }
}

// ---- sức khỏe thiết bị (health do robot gửi, trường tự do) ----

export interface DeviceHealth {
  /** Thiết bị đang tốt; null nếu không có dữ liệu. */
  ok: boolean | null;
  /** Mô tả trạng thái (stm, lidar: `state`; writer: chạy hay không). */
  state: string | null;
  /** Số lỗi (writer: error_count; stm, lidar: số lần khởi động lại); null nếu không có. */
  errors: number | null;
  /** Số lệnh bị từ chối (chỉ writer). */
  rejected: number | null;
  lastError: string | null;
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function str(value: unknown): string | null {
  return typeof value === "string" && value !== "" ? value : null;
}

/** Đọc health của một thiết bị: stm, lidar (ok/state/error/restarts) hoặc writer (healthy/error_count/...). */
export function parseDeviceHealth(raw: unknown): DeviceHealth {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    return { ok: null, state: null, errors: null, rejected: null, lastError: null };
  }
  const rec = raw as LooseRecord;
  let ok: boolean | null = null;
  if (typeof rec.ok === "boolean") ok = rec.ok;
  else if (typeof rec.healthy === "boolean") ok = rec.healthy;
  let state = str(rec.state);
  if (state === null && typeof rec.running === "boolean") {
    state = rec.running ? "running" : "stopped";
  }
  return {
    ok,
    state,
    errors: num(rec.error_count) ?? num(rec.restarts),
    rejected: num(rec.rejected_count),
    lastError: str(rec.last_error) ?? str(rec.error),
  };
}
