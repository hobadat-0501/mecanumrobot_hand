import { describe, expect, it } from "vitest";

import { Arbiter } from "./control";
import {
  DEFAULT_FIELDS,
  InverseRun,
  planInverse,
  computeProgress,
  degToRad,
  parseInverseFields,
  parseNumber,
  radToDeg,
  resolveGoal,
} from "./inverse";
import type { InverseFields, ParsedInput } from "./inverse";
import { bodyToWorld, inverseKinematics } from "./mecanum";
import type { Pose } from "./mecanum";
import { CONTROL_HZ, DEFAULT_RUN_PARAMS, TOL_ANG, TOL_POS, trackError, wrapAngle } from "./motion";

const DT = 1 / CONTROL_HZ;

function parsed(kind: "distance" | "pose", over: Partial<InverseFields> = {}): ParsedInput {
  const r = parseInverseFields(kind, { ...DEFAULT_FIELDS, ...over });
  if (!r.ok) throw new Error(r.message);
  return r.value;
}

describe("đổi đơn vị và phân tích ô nhập", () => {
  it("độ sang rad và ngược lại", () => {
    expect(degToRad(180)).toBeCloseTo(Math.PI, 12);
    expect(radToDeg(degToRad(37.5))).toBeCloseTo(37.5, 12);
  });

  it("parseNumber nhận số âm và 0, từ chối rỗng, chữ, vô hạn", () => {
    expect(parseNumber("-0.5")).toBe(-0.5);
    expect(parseNumber("0")).toBe(0);
    for (const t of ["", "  ", "abc", "NaN", "Infinity", "1e999"]) {
      expect(parseNumber(t)).toBeNull();
    }
  });

  it("mặc định hợp lệ, thời gian 5 s", () => {
    const v = parsed("distance");
    expect(v.durationS).toBe(5);
    expect(v.target).toEqual({ kind: "distance", s: 0.5, alpha: 0 });
  });

  it("kiểu B đổi θ từ độ sang rad", () => {
    const v = parsed("pose", { theta: "30" });
    expect(v.target.kind).toBe("pose");
    if (v.target.kind === "pose") {
      expect(v.target.goal.theta).toBeCloseTo(Math.PI / 6, 12);
    }
  });

  it("không có chặn dưới cho thời gian (SAF-04): 1e-3 s vẫn nhận", () => {
    const v = parsed("distance", { duration: "0.001" });
    expect(v.durationS).toBe(0.001);
  });

  it("ô rỗng, chữ, 0 hoặc âm: lỗi, không có NaN", () => {
    for (const bad of ["", "abc", "0", "-1", "NaN"]) {
      const r = parseInverseFields("distance", { ...DEFAULT_FIELDS, duration: bad });
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.errors.duration).toBeDefined();
    }
    const r = parseInverseFields("pose", { ...DEFAULT_FIELDS, x: "", theta: "x" });
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(Object.keys(r.errors).sort()).toEqual(["theta", "x"]);
      expect(r.message).toContain("x đích");
    }
  });

  it("chỉ kiểm các ô của kiểu đang chọn", () => {
    const r = parseInverseFields("pose", { ...DEFAULT_FIELDS, distance: "" });
    expect(r.ok).toBe(true);
  });

  it("kiểu A: quy đổi PHY-6 theo tư thế lúc bấm chạy, hướng độ -> rad", () => {
    const start: Pose = { x: 1, y: 2, theta: Math.PI / 2 };
    const g = resolveGoal(parsed("distance", { distance: "0.5", heading: "90" }).target, start);
    expect(g.x).toBeCloseTo(0.5, 12); // hướng thân 90 + 90 = 180 độ
    expect(g.y).toBeCloseTo(2, 12);
    expect(g.theta).toBe(start.theta);
  });
});

describe("tiến độ", () => {
  const start: Pose = { x: 0, y: 0, theta: 0 };
  const goal: Pose = { x: 1, y: 0, theta: 1 };
  const e0 = trackError(start, goal);

  it("0% lúc đầu, 50% khi còn nửa chặng", () => {
    expect(computeProgress(e0, e0).percent).toBe(0);
    const mid = trackError({ x: 0.5, y: 0, theta: 1 }, goal);
    const p = computeProgress(e0, mid);
    expect(p.percent).toBe(50);
    expect(p.remainingDist).toBeCloseTo(0.5, 12);
    expect(p.remainingAngle).toBeCloseTo(0, 12);
  });

  it("lấy phần còn lại lớn nhất giữa tịnh tiến và quay", () => {
    const e = trackError({ x: 0.9, y: 0, theta: 0.2 }, goal); // dist 0.1, góc còn 0.8
    expect(computeProgress(e0, e).percent).toBe(20);
  });

  it("đích trùng điểm đầu: không chia cho 0", () => {
    const same = trackError(start, start);
    expect(computeProgress(same, same).percent).toBe(100);
  });

  it("done thì 100%", () => {
    expect(computeProgress(e0, e0, true).percent).toBe(100);
  });
});

/** Vật thể đơn giản: nhận cmd_vel, tích phân tư thế (Euler, có trễ bậc 1 để thử độ vọt). */
function simulate(
  start: Pose,
  input: ParsedInput,
  lag = 0.1,
): { pose: Pose; ended: boolean; done: boolean; maxOvershoot: number; run: InverseRun; steps: number } {
  const goal = resolveGoal(input.target, start);
  const run = new InverseRun(start, goal, planInverse(input.target, input.durationS, start)!.params);
  const arb = new Arbiter();
  expect(arb.startRun(run, "inverse")).toBe(true);
  let pose = { ...start };
  let vel = { vx: 0, vy: 0, wz: 0 };
  let steps = 0;
  let maxOvershoot = 0;
  const e0 = trackError(start, goal);
  while (arb.active && steps < 20000) {
    steps++;
    const out = arb.tick({ dt: DT, pose, stateAgeS: 0.05, armed: true });
    const cmd = out === null ? { vx: 0, vy: 0, wz: 0 } : out.cmd;
    const k = DT / (lag + DT);
    vel = {
      vx: vel.vx + k * (cmd.vx - vel.vx),
      vy: vel.vy + k * (cmd.vy - vel.vy),
      wz: vel.wz + k * (cmd.wz - vel.wz),
    };
    const w = bodyToWorld(vel, pose.theta);
    pose = {
      x: pose.x + w.xDot * DT,
      y: pose.y + w.yDot * DT,
      theta: wrapAngle(pose.theta + vel.wz * DT),
    };
    // vọt: khoảng cách vượt qua đích theo hướng ban đầu
    if (e0.dist > 0) {
      const along = ((pose.x - goal.x) * e0.ex + (pose.y - goal.y) * e0.ey) / e0.dist;
      maxOvershoot = Math.max(maxOvershoot, along);
    }
  }
  const end = arb.lastRunEnd;
  return { pose, ended: !arb.active, done: end?.done === true, maxOvershoot, run, steps };
}

describe("vòng kín: bộ điều khiển với ô nhập đã phân tích", () => {
  it("kiểu A: 0,5 m, 0 độ, tới đích trong dung sai", () => {
    const start: Pose = { x: 0.3, y: -0.1, theta: 0.4 };
    const input = parsed("distance", { distance: "0.5", heading: "0" });
    const r = simulate(start, input);
    expect(r.done).toBe(true);
    const e = trackError(r.pose, r.run.goal);
    expect(e.dist).toBeLessThan(TOL_POS);
    expect(Math.abs(e.etheta)).toBeLessThan(TOL_ANG);
    expect(r.maxOvershoot).toBeLessThan(0.02);
  });

  it("kiểu A: hướng 90 độ so với thân", () => {
    const start: Pose = { x: 0, y: 0, theta: Math.PI / 3 };
    const input = parsed("distance", { distance: "0.4", heading: "90" });
    const r = simulate(start, input);
    expect(r.done).toBe(true);
    expect(r.run.goal.x).toBeCloseTo(0.4 * Math.cos(Math.PI / 3 + Math.PI / 2), 12);
    const e = trackError(r.pose, r.run.goal);
    expect(e.dist).toBeLessThan(TOL_POS);
  });

  it("kiểu B: x=0,4 y=0,2 θ=30 độ", () => {
    const input = parsed("pose", { x: "0.4", y: "0.2", theta: "30" });
    const r = simulate({ x: 0, y: 0, theta: 0 }, input);
    expect(r.done).toBe(true);
    const e = trackError(r.pose, r.run.goal);
    expect(e.dist).toBeLessThan(TOL_POS);
    expect(Math.abs(e.etheta)).toBeLessThan(TOL_ANG);
    expect(r.maxOvershoot).toBeLessThan(0.02);
    expect(r.run.progress().percent).toBe(100);
  });

  it("thời gian rất ngắn (tốc độ lớn) vẫn tới đích", () => {
    const input = parsed("pose", { x: "1", y: "-1", theta: "-90", duration: "0.5" });
    const r = simulate({ x: 0, y: 0, theta: 0 }, input, 0.02);
    expect(r.done).toBe(true);
  });
});

describe("InverseRun", () => {
  it("bốn tốc độ bánh khớp động học ngược của lệnh đang gửi", () => {
    const run = new InverseRun({ x: 0, y: 0, theta: 0 }, { x: 1, y: 0, theta: 0 }, DEFAULT_RUN_PARAMS);
    run.step({ dt: DT, pose: { x: 0, y: 0, theta: 0 }, stateAgeS: 0, armed: true, keyPressed: false });
    expect(run.wheels()).toEqual(inverseKinematics(run.lastCmd));
    expect(run.lastCmd.vx).toBeGreaterThan(0);
  });

  it("T_expected = max(quãng đường / v, góc / wz)", () => {
    const run = new InverseRun({ x: 0, y: 0, theta: 0 }, { x: 0.5, y: 0, theta: 0 }, DEFAULT_RUN_PARAMS);
    expect(run.tExpected).toBeCloseTo(2.5, 12);
  });

  it("không có tư thế hoặc state cũ thì hủy, lệnh 0", () => {
    const run = new InverseRun({ x: 0, y: 0, theta: 0 }, { x: 1, y: 0, theta: 0 }, DEFAULT_RUN_PARAMS);
    const s1 = run.step({ dt: DT, pose: null, stateAgeS: 0, armed: true, keyPressed: false });
    expect(s1.status).toEqual({ kind: "aborted", reason: "stale" });
    const run2 = new InverseRun({ x: 0, y: 0, theta: 0 }, { x: 1, y: 0, theta: 0 }, DEFAULT_RUN_PARAMS);
    const s2 = run2.step({ dt: DT, pose: { x: 0, y: 0, theta: 0 }, stateAgeS: 0.6, armed: true, keyPressed: false });
    expect(s2.status).toEqual({ kind: "aborted", reason: "stale" });
    expect(s2.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
  });

  it("ném RangeError với tham số không hợp lệ", () => {
    expect(
      () => new InverseRun({ x: 0, y: 0, theta: 0 }, { x: 1, y: 0, theta: 0 }, { vCruise: NaN, wzCruise: 1 }),
    ).toThrow(RangeError);
  });
});

describe("planInverse: tốc độ suy ra từ quãng đường và thời gian", () => {
  it("kiểu A tiến thẳng 0.5 m trong 5 s: vx = 0.1, bốn bánh cùng tốc độ", () => {
    const p = planInverse(parsed("distance").target, 5, null)!;
    expect(p.body.vx).toBeCloseTo(0.1, 12);
    expect(p.body.vy).toBeCloseTo(0, 12);
    expect(p.body.wz).toBe(0);
    expect(p.params.vCruise).toBeCloseTo(0.1, 12);
    for (const w of p.wheels) expect(w).toBeCloseTo(0.1 / 0.05, 9);
    expect(p.distance).toBeCloseTo(0.5, 12);
  });

  it("kiểu A hướng 90 độ: đi ngang sang trái vy = s/T", () => {
    const p = planInverse(parsed("distance", { heading: "90" }).target, 2, null)!;
    expect(p.body.vx).toBeCloseTo(0, 9);
    expect(p.body.vy).toBeCloseTo(0.25, 9);
  });

  it("kiểu B cần tư thế hiện tại; có thì tính theo khung thân", () => {
    const t = parsed("pose", { x: "1", y: "0", theta: "90" }).target;
    expect(planInverse(t, 2, null)).toBeNull();
    const p = planInverse(t, 2, { x: 0, y: 0, theta: 0 })!;
    expect(p.body.vx).toBeCloseTo(0.5, 9);
    expect(p.body.wz).toBeCloseTo(Math.PI / 4, 9);
    expect(p.params.wzCruise).toBeCloseTo(Math.PI / 4, 9);
  });

  it("thời gian không hợp lệ thì null", () => {
    expect(planInverse(parsed("distance").target, 0, null)).toBeNull();
    expect(planInverse(parsed("distance").target, NaN, null)).toBeNull();
  });
});
