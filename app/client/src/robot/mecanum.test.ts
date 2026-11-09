import { describe, expect, it } from "vitest";
import {
  DynamicsEstimator,
  I_Z,
  LEVER,
  bodyToWorld,
  computeDynamics,
  exceedsSpeedSum,
  forwardKinematics,
  inverseKinematics,
  wheelResidual,
} from "./mecanum";
import type { BodyVel, Pose, Wheels } from "./mecanum";
import {
  DEFAULT_RUN_PARAMS,
  createTrack,
  createWheelRun,
  expectedDuration,
  goalFromDistanceHeading,
  trackStep,
  wheelRunStep,
  wrapAngle,
} from "./motion";
import type { RunParams, RunStatus, TrackInput } from "./motion";

const V: BodyVel = { vx: 0.1, vy: 0.05, wz: 0.2 };

describe("PHY-1", () => {
  it("thông số dẫn xuất", () => {
    expect(LEVER).toBeCloseTo(0.335, 12);
    expect(I_Z).toBeCloseTo(0.5454, 4);
  });
});

describe("PHY-2/PHY-3 động học", () => {
  it("ngược: (0.1, 0.05, 0.2) -> (1.66, -0.34, 4.34, 2.34)", () => {
    const w = inverseKinematics(V);
    [1.66, -0.34, 4.34, 2.34].forEach((e, i) => expect(w[i]).toBeCloseTo(e, 9));
  });

  it("thuận rồi ngược trả lại đầu vào", () => {
    const back = forwardKinematics(inverseKinematics(V));
    expect(back.vx).toBeCloseTo(V.vx, 12);
    expect(back.vy).toBeCloseTo(V.vy, 12);
    expect(back.wz).toBeCloseTo(V.wz, 12);
  });

  it("dư bằng 0 với bánh nhất quán", () => {
    expect(wheelResidual(inverseKinematics(V))).toBeCloseTo(0, 12);
  });

  it("dư khác 0 với (1, -1, -1, 1) và thuận cho vận tốc 0", () => {
    const w: Wheels = [1, -1, -1, 1];
    expect(wheelResidual(w)).toBeCloseTo(0.05, 12);
    const v = forwardKinematics(w);
    expect(v.vx).toBeCloseTo(0, 12);
    expect(v.vy).toBeCloseTo(0, 12);
    expect(v.wz).toBeCloseTo(0, 12);
  });
});

describe("PHY-4 thân sang thế giới", () => {
  it("theta = 0 giữ nguyên", () => {
    const r = bodyToWorld({ vx: 1, vy: 0.5, wz: 0.3 }, 0);
    expect(r.xDot).toBeCloseTo(1, 12);
    expect(r.yDot).toBeCloseTo(0.5, 12);
    expect(r.thetaDot).toBeCloseTo(0.3, 12);
  });

  it("theta = pi/2: tiến về +y, trái về -x", () => {
    const r = bodyToWorld({ vx: 1, vy: 0.5, wz: 0 }, Math.PI / 2);
    expect(r.xDot).toBeCloseTo(-0.5, 12);
    expect(r.yDot).toBeCloseTo(1, 12);
  });
});

describe("FR-04 cảnh báo tổng tốc độ", () => {
  it("1.567 không cảnh báo, 1.634 có cảnh báo", () => {
    expect(exceedsSpeedSum({ vx: 1, vy: 0.5, wz: 0.2 })).toBe(false);
    expect(exceedsSpeedSum({ vx: 1, vy: 0.5, wz: 0.4 })).toBe(true);
  });
});

describe("PHY-5 động lực học", () => {
  it("a = (1, 0), omega_i > 0 -> F_d = 2.425, tau ~ 0.1807", () => {
    const r = computeDynamics({ ax: 1, ay: 0, wzDot: 0 }, [1, 1, 1, 1]);
    expect(r.Fx).toBeCloseTo(9.7, 9);
    for (let i = 0; i < 4; i++) {
      expect(r.Fd[i]).toBeCloseTo(2.425, 9);
      expect(r.tau[i]).toBeCloseTo(0.1807, 3);
      expect(r.over[i]).toBe(false);
    }
    expect(r.tauPct[0]).toBeCloseTo((100 * 0.18072) / 0.981, 2);
  });

  it("mô-men Mz: wzDot = 2 -> F_d = (-0.81403, -0.81403, +0.81403, +0.81403)", () => {
    const r = computeDynamics({ ax: 0, ay: 0, wzDot: 2 }, [1, 1, 1, 1]);
    expect(r.Mz).toBeCloseTo(1.0908, 3);
    [-0.81403, -0.81403, 0.81403, 0.81403].forEach((e, i) => expect(r.Fd[i]).toBeCloseTo(e, 4));
  });

  it("omega_i = 0 thì lực cản lăn bằng 0", () => {
    const r = computeDynamics({ ax: 1, ay: 0, wzDot: 0 }, [0, 0, 0, 0]);
    expect(r.tau[0]).toBeCloseTo(0.05 * 2.425, 9);
  });

  it("cờ vượt định mức khi tải lớn", () => {
    const r = computeDynamics({ ax: 100, ay: 0, wzDot: 0 }, [1, 1, 1, 1]);
    expect(r.over.every((f) => f)).toBe(true);
  });

  it("bộ ước lượng hội tụ về a = (1, 0) với vx tăng đều", () => {
    const est = new DynamicsEstimator();
    const dt = 0.05;
    let r = computeDynamics({ ax: 0, ay: 0, wzDot: 0 }, [0, 0, 0, 0]);
    for (let k = 0; k <= 120; k++) {
      const v: BodyVel = { vx: k * dt, vy: 0, wz: 0 };
      r = est.update(v, inverseKinematics(v), dt);
    }
    expect(r.ax).toBeCloseTo(1, 6);
    expect(r.Fd[0]).toBeCloseTo(2.425, 4);
    expect(r.tau[0]).toBeCloseTo(0.1807, 3);
  });

  it("thành phần ly tâm: vx = 0.5, wz = 1 không đổi -> ay = 0.5", () => {
    const est = new DynamicsEstimator();
    const v: BodyVel = { vx: 0.5, vy: 0, wz: 1 };
    let r = est.update(v, inverseKinematics(v), 0.05);
    for (let k = 0; k < 100; k++) r = est.update(v, inverseKinematics(v), 0.05);
    expect(r.ax).toBeCloseTo(0, 9);
    expect(r.ay).toBeCloseTo(0.5, 9);
    expect(r.wzDot).toBeCloseTo(0, 9);
    expect(r.Fy).toBeCloseTo(4.85, 9);
  });
});

describe("PHY-6 góc và đích", () => {
  it("wrapAngle về [-pi, pi]", () => {
    expect(wrapAngle(0.1 + 2 * Math.PI)).toBeCloseTo(0.1, 9);
    expect(wrapAngle((3 * Math.PI) / 2)).toBeCloseTo(-Math.PI / 2, 9);
    expect(wrapAngle((-3 * Math.PI) / 2)).toBeCloseTo(Math.PI / 2, 9);
    expect(Math.abs(wrapAngle(Math.PI))).toBeCloseTo(Math.PI, 9);
    expect(wrapAngle(0.5)).toBeCloseTo(0.5, 12);
  });

  it("kiểu A: đích từ quãng đường và hướng", () => {
    const a = goalFromDistanceHeading({ x: 1, y: 2, theta: Math.PI / 2 }, 1, 0);
    expect(a.x).toBeCloseTo(1, 9);
    expect(a.y).toBeCloseTo(3, 9);
    expect(a.theta).toBeCloseTo(Math.PI / 2, 12);
    const b = goalFromDistanceHeading(
      { x: 1, y: 2, theta: Math.PI / 2 },
      1,
      Math.PI / 2,
    );
    expect(b.x).toBeCloseTo(0, 9);
    expect(b.y).toBeCloseTo(2, 9);
  });

  it("timeout = 3 * T_dự_kiến + 5", () => {
    const o: Pose = { x: 0, y: 0, theta: 0 };
    expect(expectedDuration(o, { x: 1, y: 0, theta: 0 }, DEFAULT_RUN_PARAMS)).toBeCloseTo(5, 9);
    expect(createTrack(o, { x: 1, y: 0, theta: 0 }, DEFAULT_RUN_PARAMS).timeoutS).toBeCloseTo(20, 9);
    expect(createTrack(o, { x: 0, y: 0, theta: 1 }, DEFAULT_RUN_PARAMS).timeoutS).toBeCloseTo(8, 9);
  });

  it("tham số không hợp lệ bị từ chối", () => {
    const o: Pose = { x: 0, y: 0, theta: 0 };
    expect(() => createTrack(o, o, { ...DEFAULT_RUN_PARAMS, vCruise: 0 })).toThrow(RangeError);
    expect(() => createTrack(o, o, { ...DEFAULT_RUN_PARAMS, accelAng: NaN })).toThrow(RangeError);
  });
});

function simulate(start: Pose, goal: Pose, params: RunParams) {
  const dt = 0.05;
  let s = createTrack(start, goal, params);
  let pose: Pose = { ...start };
  let status: RunStatus = { kind: "running" };
  let steps = 0;
  let maxSpeed = 0;
  let maxDv = 0;
  let maxOvershoot = 0;
  let maxOvershootTheta = 0;
  let prev = { vx: 0, vy: 0, wz: 0 };
  while (status.kind === "running" && steps < 4000) {
    const out = trackStep(s, { pose, dt, stateAgeS: 0.05, armed: true, keyPressed: false });
    s = out.state;
    status = out.status;
    steps++;
    if (status.kind !== "running") break;
    const w = bodyToWorld(out.cmd, pose.theta);
    pose = { x: pose.x + w.xDot * dt, y: pose.y + w.yDot * dt, theta: pose.theta + w.thetaDot * dt };
    maxOvershoot = Math.max(maxOvershoot, Math.max(0, (pose.x - goal.x) * Math.sign(goal.x - start.x)));
    maxOvershootTheta = Math.max(maxOvershootTheta, Math.max(0, (pose.theta - goal.theta) * Math.sign(goal.theta - start.theta)));
    maxSpeed = Math.max(maxSpeed, Math.hypot(out.cmd.vx, out.cmd.vy));
    maxDv = Math.max(maxDv, Math.hypot(out.cmd.vx - prev.vx, out.cmd.vy - prev.vy) / dt);
    prev = out.cmd;
  }
  return { status, pose, steps, maxSpeed, maxDv, maxOvershoot, maxOvershootTheta, state: s };
}

describe("PHY-6 bộ bám đích trên mô hình tích phân", () => {
  it("tới đích (có quấn góc) trong dung sai, tham số mặc định", () => {
    const goal: Pose = { x: -0.5, y: 0.8, theta: 3.0 };
    const r = simulate({ x: 0, y: 0, theta: -3.0 }, goal, DEFAULT_RUN_PARAMS);
    expect(r.status).toEqual({ kind: "done" });
    expect(Math.hypot(goal.x - r.pose.x, goal.y - r.pose.y)).toBeLessThan(0.02);
    expect(Math.abs(wrapAngle(goal.theta - r.pose.theta))).toBeLessThan(0.035);
    expect(r.maxSpeed).toBeLessThanOrEqual(DEFAULT_RUN_PARAMS.vCruise + 1e-9);
    expect(r.maxDv).toBeLessThanOrEqual(DEFAULT_RUN_PARAMS.accelLin + 1e-9);
    expect(r.state.elapsed).toBeLessThan(r.state.timeoutS);
  });

  it("tới đích với tham số chạy khác (nhanh hơn)", () => {
    const params: RunParams = { vCruise: 0.5, wzCruise: 2, accelLin: 2, accelAng: 3 };
    const goal: Pose = { x: 1.2, y: -0.7, theta: 0.4 };
    const r = simulate({ x: 0.3, y: 0.3, theta: 0.9 }, goal, params);
    expect(r.status).toEqual({ kind: "done" });
    expect(Math.hypot(goal.x - r.pose.x, goal.y - r.pose.y)).toBeLessThan(0.02);
    expect(Math.abs(wrapAngle(goal.theta - r.pose.theta))).toBeLessThan(0.035);
  });

  it("chu kỳ đầu giữ hướng vector và bị giới hạn gia tốc", () => {
    const s = createTrack({ x: 0, y: 0, theta: 0 }, { x: 1, y: 1, theta: 0 }, DEFAULT_RUN_PARAMS);
    const out = trackStep(s, { pose: { x: 0, y: 0, theta: 0 }, dt: 0.05, stateAgeS: 0, armed: true, keyPressed: false });
    expect(out.status).toEqual({ kind: "running" });
    expect(out.cmd.vx).toBeCloseTo(out.cmd.vy, 9);
    expect(Math.hypot(out.cmd.vx, out.cmd.vy)).toBeCloseTo(0.5 * 0.05, 9);
  });

  it("sai số quay về khung thân: theta = pi/2, đích ở +x thế giới -> đi sang phải (vy < 0)", () => {
    const g: Pose = { x: 1, y: 0, theta: Math.PI / 2 };
    const s = createTrack({ x: 0, y: 0, theta: Math.PI / 2 }, g, DEFAULT_RUN_PARAMS);
    const out = trackStep(s, { pose: { x: 0, y: 0, theta: Math.PI / 2 }, dt: 0.05, stateAgeS: 0, armed: true, keyPressed: false });
    expect(out.cmd.vx).toBeCloseTo(0, 9);
    expect(out.cmd.vy).toBeCloseTo(-0.025, 9);
  });

  it("giới hạn phanh: vCruise = 2, accelLin = 0.5, 10 m, vọt đích dưới 0.05 m", () => {
    const params: RunParams = { vCruise: 2, wzCruise: 1, accelLin: 0.5, accelAng: 1.5 };
    const goal: Pose = { x: 10, y: 0, theta: 0 };
    const r = simulate({ x: 0, y: 0, theta: 0 }, goal, params);
    expect(r.status).toEqual({ kind: "done" });
    expect(Math.hypot(goal.x - r.pose.x, goal.y - r.pose.y)).toBeLessThan(0.02);
    expect(r.maxOvershoot).toBeLessThan(0.05);
    expect(r.state.elapsed).toBeLessThan(r.state.timeoutS);
  });

  it("giới hạn phanh góc: wzCruise = 6, accelAng = 1.5, quay 3 rad, vọt dưới 0.05 rad", () => {
    const params: RunParams = { vCruise: 0.2, wzCruise: 6, accelLin: 0.5, accelAng: 1.5 };
    const goal: Pose = { x: 0, y: 0, theta: 3 };
    const r = simulate({ x: 0, y: 0, theta: 0 }, goal, params);
    expect(r.status).toEqual({ kind: "done" });
    expect(Math.abs(goal.theta - r.pose.theta)).toBeLessThan(0.035);
    expect(r.maxOvershootTheta).toBeLessThan(0.05);
  });

  it("xong cần 3 chu kỳ liên tiếp trong dung sai", () => {
    const g: Pose = { x: 1, y: 1, theta: 0 };
    let s = createTrack(g, g, DEFAULT_RUN_PARAMS);
    const input: TrackInput = { pose: g, dt: 0.05, stateAgeS: 0, armed: true, keyPressed: false };
    const kinds: string[] = [];
    for (let k = 0; k < 3; k++) {
      const out = trackStep(s, input);
      s = out.state;
      kinds.push(out.status.kind);
    }
    expect(kinds).toEqual(["running", "running", "done"]);
  });
});

describe("PHY-6 các điều kiện hủy", () => {
  const goal: Pose = { x: 5, y: 0, theta: 0 };
  const base: TrackInput = {
    pose: { x: 0, y: 0, theta: 0 },
    dt: 0.05,
    stateAgeS: 0.1,
    armed: true,
    keyPressed: false,
  };
  const fresh = () => createTrack({ x: 0, y: 0, theta: 0 }, goal, DEFAULT_RUN_PARAMS);

  it("state cũ hơn 500 ms", () => {
    const out = trackStep(fresh(), { ...base, stateAgeS: 0.6 });
    expect(out.status).toEqual({ kind: "aborted", reason: "stale" });
    expect(out.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
  });

  it("disarm", () => {
    const out = trackStep(fresh(), { ...base, armed: false });
    expect(out.status).toEqual({ kind: "aborted", reason: "disarmed" });
    expect(out.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
  });

  it("có phím di chuyển", () => {
    const out = trackStep(fresh(), { ...base, keyPressed: true });
    expect(out.status).toEqual({ kind: "aborted", reason: "key" });
    expect(out.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
  });

  it("quá thời gian", () => {
    const s = fresh();
    const out = trackStep({ ...s, elapsed: s.timeoutS - 0.01 }, base);
    expect(out.status).toEqual({ kind: "aborted", reason: "timeout" });
    expect(out.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
  });

  it("tư thế không hữu hạn thì hủy, cmd 0 hữu hạn, không làm hỏng trạng thái", () => {
    const out = trackStep(fresh(), { ...base, pose: { x: NaN, y: 0, theta: 0 } });
    expect(out.status).toEqual({ kind: "aborted", reason: "stale" });
    expect(out.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
    expect(out.state.prevCmd).toEqual({ vx: 0, vy: 0, wz: 0 });
  });

  it("không hủy khi mọi điều kiện ổn", () => {
    expect(trackStep(fresh(), base).status).toEqual({ kind: "running" });
  });
});

describe("FR-04 chạy theo tốc độ bánh", () => {
  const w: Wheels = [1.66, -0.34, 4.34, 2.34];
  const ok = { stateAgeS: 0.05, armed: true, keyPressed: false };

  it("cmd_vel bằng động học thuận, hết giờ thì done với cmd 0", () => {
    let run = createWheelRun(w, 3);
    const expected = forwardKinematics(w);
    let steps = 0;
    let status: RunStatus = { kind: "running" };
    while (status.kind === "running" && steps < 1000) {
      const out = wheelRunStep(run, ok, 0.05);
      run = out.run;
      status = out.status;
      steps++;
      if (status.kind === "running") {
        expect(out.cmd.vx).toBeCloseTo(expected.vx, 12);
        expect(out.cmd.vy).toBeCloseTo(expected.vy, 12);
        expect(out.cmd.wz).toBeCloseTo(expected.wz, 12);
      } else {
        expect(out.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
      }
    }
    expect(status).toEqual({ kind: "done" });
    expect(steps).toBeGreaterThanOrEqual(59);
    expect(steps).toBeLessThanOrEqual(61);
  });

  it("hủy khi có phím, disarm, state cũ", () => {
    const run = createWheelRun(w, 3);
    expect(wheelRunStep(run, { ...ok, keyPressed: true }, 0.05).status).toEqual({ kind: "aborted", reason: "key" });
    expect(wheelRunStep(run, { ...ok, armed: false }, 0.05).status).toEqual({ kind: "aborted", reason: "disarmed" });
    expect(wheelRunStep(run, { ...ok, stateAgeS: 0.6 }, 0.05).status).toEqual({ kind: "aborted", reason: "stale" });
  });

  it("đầu vào không hợp lệ bị từ chối", () => {
    expect(() => createWheelRun(w, 0)).toThrow(RangeError);
    expect(() => createWheelRun([1, 2, NaN, 4], 3)).toThrow(RangeError);
  });
});
