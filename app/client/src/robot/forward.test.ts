import { describe, expect, it } from "vitest";
import {
  computeChain,
  createWheelDriver,
  describeRunEnd,
  parseNumber,
  parsePositive,
  parseWheels,
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
