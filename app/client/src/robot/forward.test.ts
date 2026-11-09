import { describe, expect, it } from "vitest";
import {
  MotionMeter,
  computeChain,
  createWheelDriver,
  describeRunEnd,
  parseNumber,
  parsePositive,
  parseWheels,
  parseWheelsLive,
  plannedMotion,
  runBlockReason,
} from "./forward";
import type { RunReadiness } from "./forward";

const READY: RunReadiness = {
  open: true,
  hasState: true,
  stale: false,
  robotLink: true,
  armed: true,
  isDriver: true,
  wheelsValid: true,
  durationValid: true,
};
const OK_INPUT = { stateAgeS: 0.05, armed: true, keyPressed: false, pose: null };

describe("đọc số nhập", () => {
  it("giá trị khổng lồ làm tràn tổng thì null", () => {
    expect(parseWheels(["1e308", "1e308", "1e308", "1e308"])).toBeNull();
  });

  it("rỗng, chữ, vô cực không bao giờ ra NaN", () => {
    for (const t of ["", "  ", "abc", "1e999", "Infinity", "NaN", "1.2.3"]) {
      expect(parseNumber(t)).toBeNull();
    }
  });
  it("chấp nhận âm, dấu phẩy", () => {
    expect(parseNumber("-0.34")).toBe(-0.34);
    expect(parseNumber(" 1,5 ")).toBe(1.5);
  });
  it("thời gian phải dương", () => {
    expect(parsePositive("0")).toBeNull();
    expect(parsePositive("-1")).toBeNull();
    expect(parsePositive("0.5")).toBe(0.5);
    expect(parsePositive("1000")).toBe(1000);
  });
  it("bộ bánh thiếu một ô là null", () => {
    expect(parseWheels(["1", "2", "3", ""])).toBeNull();
    expect(parseWheels(["1", "2", "3"])).toBeNull();
    expect(parseWheels(["1", "2", "3", "4"])).toEqual([1, 2, 3, 4]);
  });
});

describe("chuỗi tính", () => {
  it("vector kiểm thử PHY-2/3", () => {
    const c = computeChain([1.66, -0.34, 4.34, 2.34], 0);
    expect(c.body.vx).toBeCloseTo(0.1, 12);
    expect(c.body.vy).toBeCloseTo(0.05, 12);
    expect(c.body.wz).toBeCloseTo(0.2, 12);
    expect(c.rim[2]).toBeCloseTo(0.217, 12);
    expect(c.residualNonZero).toBe(false);
    expect(c.exceeds).toBe(false);
  });
  it("PHY-4: θ = 90° đổi trục", () => {
    const c = computeChain([1.66, -0.34, 4.34, 2.34], Math.PI / 2);
    expect(c.world?.xDot).toBeCloseTo(-0.05, 12);
    expect(c.world?.yDot).toBeCloseTo(0.1, 12);
    expect(c.world?.thetaDot).toBeCloseTo(0.2, 12);
  });
  it("chưa có θ thì không có khung thế giới", () => {
    expect(computeChain([1, 1, 1, 1], null).world).toBeNull();
  });
  it("bánh đánh nhau thì dư khác 0", () => {
    const c = computeChain([10, 0, 0, 0], 0);
    expect(c.residual).toBeCloseTo(0.125, 12);
    expect(c.residualNonZero).toBe(true);
  });
  it("cảnh báo vượt 1.6 m/s", () => {
    // 4 bánh 40 rad/s -> vx = 2 m/s
    expect(computeChain([40, 40, 40, 40], 0).exceeds).toBe(true);
    // wz = 5 rad/s -> lever*|wz| = 1.675 m/s
    expect(computeChain([-33.5, -33.5, 33.5, 33.5], 0).exceeds).toBe(true);
    expect(computeChain([-30, -30, 30, 30], 0).exceeds).toBe(false);
  });
});

describe("lý do khóa nút Chạy", () => {
  it("sẵn sàng thì null", () => expect(runBlockReason(READY)).toBeNull());
  it.each([
    [{ open: false }],
    [{ stale: true }],
    [{ isDriver: false }],
    [{ robotLink: false }],
    [{ armed: false }],
    [{ wheelsValid: false }],
    [{ durationValid: false }],
  ])("%j có lý do", (patch) => {
    expect(runBlockReason({ ...READY, ...patch })).not.toBeNull();
  });
});

describe("RunDriver", () => {
  it("chạy rồi dừng bằng lệnh 0 khi hết giờ", () => {
    const d = createWheelDriver([1.66, -0.34, 4.34, 2.34], 0.2);
    const a = d.step({ ...OK_INPUT, dt: 0.1 });
    expect(a.status.kind).toBe("running");
    expect(a.cmd.vx).toBeCloseTo(0.1, 12);
    expect(d.remaining()).toBeCloseTo(0.1, 12);
    const b = d.step({ ...OK_INPUT, dt: 0.1 });
    expect(b.status.kind).toBe("done");
    expect(b.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
    expect(d.remaining()).toBe(0);
  });
  it("hủy khi state cũ", () => {
    const d = createWheelDriver([1, 1, 1, 1], 3);
    const r = d.step({ ...OK_INPUT, stateAgeS: 2, dt: 0.05 });
    expect(r.status).toEqual({ kind: "aborted", reason: "stale" });
    expect(r.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
  });
  it("đầu vào sai ném lỗi", () => {
    expect(() => createWheelDriver([NaN, 0, 0, 0], 1)).toThrow(RangeError);
    expect(() => createWheelDriver([0, 0, 0, 0], 0)).toThrow(RangeError);
  });
});

describe("mô tả kết thúc", () => {
  it("chỉ nhận nguồn forward", () => {
    expect(describeRunEnd(null)).toBeNull();
    expect(describeRunEnd({ source: "inverse", done: true, reason: null })).toBeNull();
    expect(describeRunEnd({ source: "forward", done: true, reason: null })?.tone).toBe("ok");
    expect(describeRunEnd({ source: "forward", done: false, reason: "key" })?.text).toContain("phím");
  });
});


describe("nhập đến đâu tính đến đó", () => {
  it("ô trống tính là 0: chỉ gõ ô A đã có kết quả", () => {
    expect(parseWheels(["5", "", "", ""])).toBeNull();
    expect(parseWheelsLive(["5", "", "", ""])).toEqual([5, 0, 0, 0]);
    expect(parseWheelsLive(["", "", "", ""])).toEqual([0, 0, 0, 0]);
  });
  it("ô sai hoặc làm tràn thì null, không bao giờ NaN", () => {
    expect(parseWheelsLive(["abc", "", "", ""])).toBeNull();
    expect(parseWheelsLive(["-", "", "", ""])).toBeNull();
    expect(parseWheelsLive(["1e308", "1e308", "1e308", "1e308"])).toBeNull();
  });
  it("quãng đường tính toán đổi theo từng ô nhập", () => {
    // bốn bánh cùng 10 rad/s: đi thẳng vx = r·10 = 0.5 m/s, 3 s -> 1.5 m
    const all = parseWheelsLive(["10", "10", "10", "10"]);
    expect(all).not.toBeNull();
    const m = plannedMotion(computeChain(all!, null).body, 3);
    expect(m.distance).toBeCloseTo(1.5, 9);
    expect(m.turn).toBeCloseTo(0, 9);
    // mới gõ bánh A = 10: vx = r/4·10 = 0.125, vy = r/4·10 = 0.125 -> |v| = 0.1768
    const onlyA = parseWheelsLive(["10", "", "", ""]);
    const mA = plannedMotion(computeChain(onlyA!, null).body, 2);
    expect(mA.distance).toBeCloseTo(Math.hypot(0.125, 0.125) * 2, 9);
  });
  it("vector kiểm tra PHY-2: (1.66, -0.34, 4.34, 2.34) rad/s, 2 s", () => {
    const w = parseWheelsLive(["1.66", "-0.34", "4.34", "2.34"]);
    const m = plannedMotion(computeChain(w!, null).body, 2);
    expect(m.distance).toBeCloseTo(Math.hypot(0.1, 0.05) * 2, 9);
    expect(m.turn).toBeCloseTo(0.2 * 2, 9);
  });
});

describe("đo quãng đường thực tế", () => {
  const P = (x: number, y: number, theta: number) => ({ x, y, theta });
  it("cộng dồn chiều dài đường đi, không phải khoảng cách thẳng", () => {
    const m = new MotionMeter();
    m.start(P(0, 0, 0));
    m.update(P(1, 0, 0));
    m.update(P(1, 1, 0));
    expect(m.get().distance).toBeCloseTo(2, 9);
  });
  it("không đo khi chưa start hoặc đã stop", () => {
    const m = new MotionMeter();
    m.update(P(1, 0, 0));
    expect(m.get().distance).toBe(0);
    m.start(P(0, 0, 0));
    m.update(P(0.3, 0, 0));
    m.stop();
    m.update(P(5, 0, 0));
    expect(m.get().distance).toBeCloseTo(0.3, 9);
    expect(m.active).toBe(false);
  });
  it("góc xoay cộng dồn quá 180° và qua ±π", () => {
    const m = new MotionMeter();
    m.start(P(0, 0, 3));
    m.update(P(0, 0, -3.1)); // +0.0832 qua ±π
    m.update(P(0, 0, -1.5));
    expect(m.get().turn).toBeCloseTo(wrap(-3.1 - 3) + wrap(-1.5 + 3.1), 9);
    expect(m.get().turn).toBeGreaterThan(0);
  });
  it("mẫu không hữu hạn bị bỏ, odometry reset (nhảy lớn) không cộng vào", () => {
    const m = new MotionMeter();
    m.start(P(0, 0, 0));
    m.update(P(NaN, 0, 0));
    m.update(P(0.2, 0, 0));
    m.update(P(0, 0, 0)); // odometry về 0: nhảy 0.2 vẫn là bước thật
    m.update(P(50, 0, 0)); // nhảy 50 m: coi là reset
    m.update(P(50.1, 0, 0));
    expect(m.get().distance).toBeCloseTo(0.2 + 0.2 + 0.1, 9);
  });
  it("start lại thì về 0", () => {
    const m = new MotionMeter();
    m.start(P(0, 0, 0));
    m.update(P(1, 0, 0));
    m.start(P(1, 0, 0));
    expect(m.get().distance).toBe(0);
  });
});

function wrap(a: number): number {
  return Math.atan2(Math.sin(a), Math.cos(a));
}
