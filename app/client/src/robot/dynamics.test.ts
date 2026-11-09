import { describe, expect, it } from "vitest";
import { DynamicsFeed, SeriesBuffer, anyOver } from "./dynamics";
import { DynamicsEstimator, ESTIMATOR_MAX_GAP, TAU_RATED, computeDynamics, inverseKinematics } from "./mecanum";
import type { BodyVel } from "./mecanum";

const ZERO = [0, 0, 0, 0] as const;

function ramp(est: DynamicsEstimator, steps: number, dt = 0.05, from = 0) {
  let r = est.update({ vx: from, vy: 0, wz: 0 }, ZERO, dt);
  for (let k = 1; k <= steps; k++) {
    const v: BodyVel = { vx: from + k * dt, vy: 0, wz: 0 };
    r = est.update(v, inverseKinematics(v), dt);
  }
  return r;
}

describe("% định mức và cờ vượt", () => {
  it("tau = định mức: 100% và chưa vượt; lớn hơn: vượt", () => {
    // Fx đặt sao cho tau_i = r*(Fx/4) = TAU_RATED với sign(omega) = 0.
    const Fx = (TAU_RATED * 4) / 0.05;
    const at = computeDynamics({ ax: Fx / 9.7, ay: 0, wzDot: 0 }, ZERO);
    expect(at.tauPct[0]).toBeCloseTo(100, 6);
    const over = computeDynamics({ ax: (Fx * 1.01) / 9.7, ay: 0, wzDot: 0 }, ZERO);
    expect(over.over).toEqual([true, true, true, true]);
    expect(anyOver(over)).toBe(true);
  });

  it("dùng trị tuyệt đối: tau âm lớn cũng vượt, tau nhỏ thì không", () => {
    const neg = computeDynamics({ ax: -50, ay: 0, wzDot: 0 }, ZERO);
    expect(neg.over[0]).toBe(true);
    expect(anyOver(computeDynamics({ ax: 0.1, ay: 0, wzDot: 0 }, ZERO))).toBe(false);
  });
});

describe("PHY-5 ở trạng thái ổn định", () => {
  it("a = (1, 0), omega > 0 -> F_d = 2.425, tau ~ 0.1807", () => {
    const r = ramp(new DynamicsEstimator(), 120);
    expect(r.ax).toBeCloseTo(1, 6);
    expect(r.Fd[0]).toBeCloseTo(2.425, 4);
    expect(r.tau[0]).toBeCloseTo(0.1807, 3);
  });

  it("vận tốc không đổi: chỉ còn lực cản lăn r*F_c theo dấu omega", () => {
    const est = new DynamicsEstimator();
    const v: BodyVel = { vx: 0.3, vy: 0, wz: 0 };
    let r = est.update(v, inverseKinematics(v), 0.05);
    for (let k = 0; k < 50; k++) r = est.update(v, inverseKinematics(v), 0.05);
    expect(r.Fx).toBeCloseTo(0, 9);
    expect(r.tau[0]).toBeCloseTo(0.05 * ((0.05 * 9.7 * 9.81) / 4), 6);
  });
});

describe("bộ ước lượng chịu lỗi dữ liệu", () => {
  it("mẫu không hữu hạn bị bỏ, không làm hỏng các mẫu sau", () => {
    const est = new DynamicsEstimator();
    ramp(est, 30);
    const bad = est.update({ vx: Number.NaN, vy: 0, wz: 0 }, ZERO, 0.05);
    expect(Number.isFinite(bad.Fx)).toBe(true);
    est.update({ vx: Infinity, vy: 0, wz: 0 }, ZERO, 0.05);
    const v: BodyVel = { vx: 1.55, vy: 0, wz: 0 };
    const ok = est.update(v, inverseKinematics(v), 0.05);
    expect(Number.isFinite(ok.Fx)).toBe(true);
    expect(Number.isFinite(ok.tau[0])).toBe(true);
  });

  it("dt <= 0 hoặc không hữu hạn bị bỏ, trạng thái giữ nguyên", () => {
    const est = new DynamicsEstimator();
    const before = ramp(est, 40);
    for (const dt of [0, -0.05, Number.NaN, Infinity]) {
      const r = est.update({ vx: 99, vy: 0, wz: 0 }, ZERO, dt);
      expect(r).toBe(before);
    }
    const v: BodyVel = { vx: 2.05, vy: 0, wz: 0 };
    const next = est.update(v, inverseKinematics(v), 0.05);
    expect(next.ax).toBeCloseTo(1, 1);
  });

  it("dt vượt ngưỡng mất dữ liệu: reset, mẫu đầu sau khoảng trống cho gia tốc 0", () => {
    const est = new DynamicsEstimator();
    ramp(est, 60);
    const v: BodyVel = { vx: 10, vy: 0, wz: 0 };
    const r = est.update(v, inverseKinematics(v), ESTIMATOR_MAX_GAP + 0.1);
    expect(r.ax).toBe(0);
    const v2: BodyVel = { vx: 10, vy: 0, wz: 0 };
    expect(est.update(v2, inverseKinematics(v2), 0.05).ax).toBeCloseTo(0, 9);
  });
});

describe("DynamicsFeed", () => {
  it("bỏ mẫu null, không hữu hạn, đảo thứ tự; vẫn hồi phục", () => {
    const feed = new DynamicsFeed();
    let t = 1000;
    for (let k = 0; k < 40; k++) {
      t += 50;
      feed.sample({ vx: k * 0.05, vy: 0, wz: 0 }, t);
    }
    const n = feed.history.length;
    const keep = feed.result;
    expect(feed.sample(null, t + 50)).toBe(keep);
    expect(feed.sample({ vx: Number.NaN, vy: 0, wz: 0 }, t + 50)).toBe(keep);
    expect(feed.sample({ vx: 5, vy: 0, wz: 0 }, t - 10)).toBe(keep); // đảo thứ tự
    expect(feed.sample({ vx: 5, vy: 0, wz: 0 }, t)).toBe(keep); // trùng thời điểm
    expect(feed.history.length).toBe(n);
    const r = feed.sample({ vx: 40 * 0.05, vy: 0, wz: 0 }, t + 50);
    expect(r?.ax).toBeCloseTo(1, 1);
    expect(feed.wheels?.[0]).toBeGreaterThan(0);
  });

  it("khoảng trống dữ liệu không làm lệch giá trị sau đó", () => {
    const feed = new DynamicsFeed();
    let t = 0;
    for (let k = 0; k < 40; k++) feed.sample({ vx: 0.2, vy: 0, wz: 0 }, (t += 50));
    t += 3000; // mất dữ liệu 3 s, vận tốc nhảy
    const r = feed.sample({ vx: 1.0, vy: 0, wz: 0 }, t);
    expect(r?.ax).toBe(0);
  });

  it("ghi nhớ lần vượt định mức gần nhất, reset thì xóa", () => {
    const feed = new DynamicsFeed();
    feed.sample({ vx: 0, vy: 0, wz: 0 }, 50);
    expect(feed.lastOver).toBeNull();
    feed.sample({ vx: 3, vy: 0, wz: 0 }, 100); // gia tốc rất lớn
    expect(feed.lastOver?.at).toBe(100);
    expect(feed.lastOver?.wheels).toEqual([true, true, true, true]);
    expect(feed.lastOver?.pct).toBeGreaterThan(100);
    feed.sample({ vx: 3, vy: 0, wz: 0 }, 150);
    expect(feed.lastOver?.at).toBeLessThanOrEqual(150);
    feed.reset();
    expect(feed.lastOver).toBeNull();
  });

  it("reset xóa kết quả và lịch sử", () => {
    const feed = new DynamicsFeed();
    feed.sample({ vx: 0.1, vy: 0, wz: 0 }, 50);
    feed.reset();
    expect(feed.result).toBeNull();
    expect(feed.history.length).toBe(0);
  });
});

describe("SeriesBuffer", () => {
  it("vòng đệm giữ mẫu mới nhất theo thứ tự cũ -> mới", () => {
    const b = new SeriesBuffer(2, 3);
    for (let i = 1; i <= 5; i++) b.push([i, -i]);
    expect(b.length).toBe(3);
    expect([b.at(0, 0), b.at(0, 1), b.at(0, 2)]).toEqual([3, 4, 5]);
    expect(b.at(1, 2)).toBe(-5);
  });
});
