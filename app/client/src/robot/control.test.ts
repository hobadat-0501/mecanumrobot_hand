import { describe, expect, it } from "vitest";

import {
  Arbiter,
  DEFAULT_SPEED,
  decideKeyDown,
  isTypingTarget,
  keysToVector,
  motionActionOf,
  parseSpeed,
} from "./control";
import type { RunDriver, TickContext } from "./control";
import { createWheelRun, wheelRunStep } from "./motion";
import type { Wheels } from "./mecanum";
import { parseServerMessage, resolveWsUrl } from "./protocol";
import { BACKOFF_INITIAL_MS, BACKOFF_MAX_MS, nextBackoff } from "./store";

const SPEED = { lin: 0.2, ang: 1.0 };
const CTX: TickContext = { dt: 0.05, pose: null, stateAgeS: 0.01, armed: true };
const NO_MODIFIER = { typing: false, modifier: false };

function keys(...codes: string[]): Set<string> {
  return new Set(codes);
}

function wheelDriver(wheels: Wheels, durationS: number): RunDriver {
  let run = createWheelRun(wheels, durationS);
  return {
    step(input) {
      const result = wheelRunStep(run, input, input.dt);
      run = result.run;
      return { cmd: result.cmd, status: result.status };
    },
  };
}

describe("keysToVector (FR-02)", () => {
  it("không phím thì vector 0", () => {
    expect(keysToVector(keys(), SPEED)).toEqual({ vx: 0, vy: 0, wz: 0 });
  });

  it("W và mũi tên lên là vx dương, S và mũi tên xuống là vx âm", () => {
    expect(keysToVector(keys("KeyW"), SPEED)).toEqual({ vx: 0.2, vy: 0, wz: 0 });
    expect(keysToVector(keys("ArrowUp"), SPEED)).toEqual({ vx: 0.2, vy: 0, wz: 0 });
    expect(keysToVector(keys("KeyS"), SPEED)).toEqual({ vx: -0.2, vy: 0, wz: 0 });
    expect(keysToVector(keys("ArrowDown"), SPEED)).toEqual({ vx: -0.2, vy: 0, wz: 0 });
  });

  it("A và mũi tên trái là vy dương (sang trái), D và mũi tên phải là vy âm", () => {
    expect(keysToVector(keys("KeyA"), SPEED)).toEqual({ vx: 0, vy: 0.2, wz: 0 });
    expect(keysToVector(keys("ArrowLeft"), SPEED)).toEqual({ vx: 0, vy: 0.2, wz: 0 });
    expect(keysToVector(keys("KeyD"), SPEED)).toEqual({ vx: 0, vy: -0.2, wz: 0 });
    expect(keysToVector(keys("ArrowRight"), SPEED)).toEqual({ vx: 0, vy: -0.2, wz: 0 });
  });

  it("Q quay ngược chiều kim đồng hồ (wz dương), E quay thuận chiều kim đồng hồ", () => {
    expect(keysToVector(keys("KeyQ"), SPEED)).toEqual({ vx: 0, vy: 0, wz: 1 });
    expect(keysToVector(keys("KeyE"), SPEED)).toEqual({ vx: 0, vy: 0, wz: -1 });
  });

  it("nhiều phím cộng thành vector (đi chéo vừa quay)", () => {
    expect(keysToVector(keys("KeyW", "KeyA", "KeyE"), SPEED)).toEqual({
      vx: 0.2,
      vy: 0.2,
      wz: -1,
    });
  });

  it("hai phím ngược nhau triệt tiêu", () => {
    expect(keysToVector(keys("KeyW", "KeyS"), SPEED)).toEqual({ vx: 0, vy: 0, wz: 0 });
  });

  it("hai phím cùng hướng không cộng đôi", () => {
    expect(keysToVector(keys("KeyW", "ArrowUp"), SPEED)).toEqual({ vx: 0.2, vy: 0, wz: 0 });
  });

  it("tốc độ không có chặn trên (SAF-04)", () => {
    expect(keysToVector(keys("KeyW", "KeyQ"), { lin: 1000, ang: 50 })).toEqual({
      vx: 1000,
      vy: 0,
      wz: 50,
    });
  });

  it("bỏ qua mã không phải phím di chuyển", () => {
    expect(keysToVector(keys("KeyX", "Space"), SPEED)).toEqual({ vx: 0, vy: 0, wz: 0 });
    expect(motionActionOf("KeyX")).toBeNull();
    expect(motionActionOf("constructor")).toBeNull();
    expect(motionActionOf("KeyW")).toBe("fwd");
  });
});

describe("parseSpeed", () => {
  it("nhận số hữu hạn lớn hơn 0, không chặn trên", () => {
    expect(parseSpeed("0.3")).toBe(0.3);
    expect(parseSpeed(" 2 ")).toBe(2);
    expect(parseSpeed("1000")).toBe(1000);
  });

  it("từ chối rỗng, 0, âm, không phải số, vô hạn", () => {
    for (const text of ["", "  ", "0", "-1", "abc", "Infinity", "NaN", "1e999"]) {
      expect(parseSpeed(text)).toBeNull();
    }
  });
});

describe("isTypingTarget", () => {
  it("true với input, textarea, select, contenteditable", () => {
    expect(isTypingTarget({ tagName: "INPUT" })).toBe(true);
    expect(isTypingTarget({ tagName: "textarea" })).toBe(true);
    expect(isTypingTarget({ tagName: "SELECT" })).toBe(true);
    expect(isTypingTarget({ tagName: "DIV", isContentEditable: true })).toBe(true);
  });

  it("false với phần tử khác hoặc không có target", () => {
    expect(isTypingTarget({ tagName: "BUTTON" })).toBe(false);
    expect(isTypingTarget({ tagName: "BODY" })).toBe(false);
    expect(isTypingTarget({})).toBe(false);
    expect(isTypingTarget(null)).toBe(false);
    expect(isTypingTarget(undefined)).toBe(false);
  });
});

describe("decideKeyDown (FR-02)", () => {
  it("phím di chuyển, R, X, Esc khi không gõ chữ", () => {
    expect(decideKeyDown("KeyW", NO_MODIFIER)).toEqual({ kind: "motion", code: "KeyW" });
    expect(decideKeyDown("ArrowLeft", NO_MODIFIER)).toEqual({
      kind: "motion",
      code: "ArrowLeft",
    });
    expect(decideKeyDown("KeyR", NO_MODIFIER)).toEqual({ kind: "arm" });
    expect(decideKeyDown("KeyX", NO_MODIFIER)).toEqual({ kind: "stop" });
    expect(decideKeyDown("Escape", NO_MODIFIER)).toEqual({ kind: "stop" });
  });

  it("đang gõ chữ thì bỏ qua phím di chuyển, R và X nhưng Esc vẫn dừng", () => {
    const typing = { typing: true, modifier: false };
    expect(decideKeyDown("KeyW", typing)).toBeNull();
    expect(decideKeyDown("ArrowUp", typing)).toBeNull();
    expect(decideKeyDown("KeyR", typing)).toBeNull();
    expect(decideKeyDown("KeyX", typing)).toBeNull();
    expect(decideKeyDown("Escape", typing)).toEqual({ kind: "stop" });
  });

  it("giữ Ctrl, Meta hoặc Alt thì bỏ qua (Ctrl+R không được arm), Esc vẫn dừng", () => {
    const modifier = { typing: false, modifier: true };
    expect(decideKeyDown("KeyR", modifier)).toBeNull();
    expect(decideKeyDown("KeyW", modifier)).toBeNull();
    expect(decideKeyDown("Escape", modifier)).toEqual({ kind: "stop" });
  });

  it("phím khác bị bỏ qua", () => {
    expect(decideKeyDown("KeyZ", NO_MODIFIER)).toBeNull();
    expect(decideKeyDown("Space", NO_MODIFIER)).toEqual({ kind: "cancel" });
    expect(decideKeyDown("Space", { typing: true, modifier: false })).toBeNull();
  });
});

describe("Arbiter: bàn phím", () => {
  it("rảnh thì tick không gửi gì và timer không cần chạy", () => {
    const arb = new Arbiter(SPEED);
    expect(arb.source).toBe("idle");
    expect(arb.active).toBe(false);
    expect(arb.tick(CTX)).toBeNull();
    expect(arb.flushZero()).toBeNull();
  });

  it("giữ phím thì mỗi tick gửi vector, nhả phím thì nợ đúng một lệnh 0", () => {
    const arb = new Arbiter(SPEED);
    arb.keyDown("KeyW");
    expect(arb.source).toBe("keyboard");
    expect(arb.active).toBe(true);
    expect(arb.tick(CTX)).toEqual({ cmd: { vx: 0.2, vy: 0, wz: 0 }, src: "keyboard" });
    expect(arb.tick(CTX)).toEqual({ cmd: { vx: 0.2, vy: 0, wz: 0 }, src: "keyboard" });
    arb.keyUp("KeyW");
    expect(arb.source).toBe("idle");
    expect(arb.active).toBe(true);
    expect(arb.flushZero()).toEqual({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "keyboard" });
    expect(arb.flushZero()).toBeNull();
    expect(arb.tick(CTX)).toBeNull();
    expect(arb.active).toBe(false);
  });

  it("nhả phím trước khi tick nào gửi vector thì không nợ lệnh 0", () => {
    const arb = new Arbiter(SPEED);
    arb.keyDown("KeyD");
    arb.keyUp("KeyD");
    expect(arb.flushZero()).toBeNull();
    expect(arb.active).toBe(false);
  });

  it("nhả một trong hai phím thì vector còn lại", () => {
    const arb = new Arbiter(SPEED);
    arb.keyDown("KeyW");
    arb.keyDown("KeyQ");
    expect(arb.tick(CTX)?.cmd).toEqual({ vx: 0.2, vy: 0, wz: 1 });
    arb.keyUp("KeyQ");
    expect(arb.tick(CTX)?.cmd).toEqual({ vx: 0.2, vy: 0, wz: 0 });
  });

  it("đổi tốc độ có hiệu lực ngay ở tick sau", () => {
    const arb = new Arbiter(SPEED);
    arb.keyDown("KeyW");
    arb.setSpeed({ lin: 3, ang: 2 });
    expect(arb.tick(CTX)?.cmd).toEqual({ vx: 3, vy: 0, wz: 0 });
  });

  it("phím không phải di chuyển bị bỏ qua", () => {
    const arb = new Arbiter(SPEED);
    arb.keyDown("KeyX");
    expect(arb.source).toBe("idle");
    expect(arb.active).toBe(false);
  });

  it("releaseAll nhả mọi phím và không nợ lệnh 0 (store tự gửi 0 một lần)", () => {
    const arb = new Arbiter(SPEED);
    arb.keyDown("KeyW");
    arb.tick(CTX);
    arb.releaseAll("blur");
    expect(arb.source).toBe("idle");
    expect(arb.active).toBe(false);
    expect(arb.tick(CTX)).toBeNull();
  });

  it("releaseKeys nhả phím nhưng vẫn nợ lệnh 0 đã gửi vector", () => {
    const arb = new Arbiter(SPEED);
    arb.keyDown("KeyW");
    arb.tick(CTX);
    arb.releaseKeys();
    expect(arb.flushZero()).toEqual({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "keyboard" });
  });

  it("DEFAULT_SPEED là 0.2 m/s và 1.0 rad/s", () => {
    expect(DEFAULT_SPEED).toEqual({ lin: 0.2, ang: 1.0 });
  });
});

describe("Arbiter: chạy tự động và phân xử (FR-09)", () => {
  const FORWARD: Wheels = [10, 10, 10, 10]; // vx = 0.5 m/s

  it("chạy theo bộ bước của motion.ts rồi tự kết thúc bằng một lệnh 0", () => {
    const arb = new Arbiter(SPEED);
    expect(arb.startRun(wheelDriver(FORWARD, 0.1), "forward")).toBe(true);
    expect(arb.source).toBe("forward");
    expect(arb.active).toBe(true);

    const first = arb.tick(CTX);
    expect(first?.src).toBe("forward");
    expect(first?.cmd.vx).toBeCloseTo(0.5, 12);
    expect(first?.cmd.vy).toBeCloseTo(0, 12);
    expect(first?.cmd.wz).toBeCloseTo(0, 12);

    const last = arb.tick(CTX);
    expect(last).toEqual({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "forward" });
    expect(arb.lastRunEnd).toEqual({ source: "forward", done: true, reason: null });
    expect(arb.source).toBe("idle");
    expect(arb.active).toBe(false);
    expect(arb.tick(CTX)).toBeNull();
  });

  it("phím di chuyển hủy lần chạy và phím thắng", () => {
    const arb = new Arbiter(SPEED);
    arb.startRun(wheelDriver(FORWARD, 5), "inverse");
    expect(arb.source).toBe("inverse");
    arb.keyDown("KeyD");
    expect(arb.source).toBe("keyboard");
    expect(arb.lastRunEnd).toEqual({ source: "inverse", done: false, reason: "key" });
    expect(arb.tick(CTX)).toEqual({ cmd: { vx: 0, vy: -0.2, wz: 0 }, src: "keyboard" });
  });

  it("đang giữ phím thì không bắt đầu được lần chạy", () => {
    const arb = new Arbiter(SPEED);
    arb.keyDown("KeyW");
    expect(arb.startRun(wheelDriver(FORWARD, 5), "forward")).toBe(false);
    expect(arb.source).toBe("keyboard");
  });

  it("bắt đầu lần chạy mới thay lần cũ", () => {
    const arb = new Arbiter(SPEED);
    arb.startRun(wheelDriver(FORWARD, 5), "forward");
    arb.startRun(wheelDriver(FORWARD, 5), "inverse");
    expect(arb.source).toBe("inverse");
    expect(arb.lastRunEnd).toBeNull();
  });

  it("hủy lần chạy đang gửi lệnh khác 0 thì nợ đúng một lệnh 0", () => {
    const arb = new Arbiter(SPEED);
    arb.startRun(wheelDriver(FORWARD, 5), "forward");
    arb.tick(CTX);
    arb.cancelRun("cancel");
    expect(arb.lastRunEnd).toEqual({ source: "forward", done: false, reason: "cancel" });
    expect(arb.flushZero()).toEqual({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "forward" });
    expect(arb.flushZero()).toBeNull();
    expect(arb.active).toBe(false);
  });

  it("disarm giữa chừng: motion.ts hủy với lý do disarmed và gửi 0", () => {
    const arb = new Arbiter(SPEED);
    arb.startRun(wheelDriver(FORWARD, 5), "forward");
    arb.tick(CTX);
    const out = arb.tick({ ...CTX, armed: false });
    expect(out).toEqual({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "forward" });
    expect(arb.lastRunEnd).toEqual({ source: "forward", done: false, reason: "disarmed" });
    expect(arb.active).toBe(false);
  });

  it("state cũ hơn 0.5 s: motion.ts hủy với lý do stale", () => {
    const arb = new Arbiter(SPEED);
    arb.startRun(wheelDriver(FORWARD, 5), "forward");
    const out = arb.tick({ ...CTX, stateAgeS: 0.6 });
    expect(out?.cmd).toEqual({ vx: 0, vy: 0, wz: 0 });
    expect(arb.lastRunEnd).toEqual({ source: "forward", done: false, reason: "stale" });
  });

  it("mất focus, ẩn tab, đóng socket: releaseAll hủy lần chạy, tick không gửi gì", () => {
    const arb = new Arbiter(SPEED);
    arb.startRun(wheelDriver(FORWARD, 5), "forward");
    arb.tick(CTX);
    arb.releaseAll("hidden");
    expect(arb.lastRunEnd).toEqual({ source: "forward", done: false, reason: "hidden" });
    expect(arb.source).toBe("idle");
    expect(arb.tick(CTX)).toBeNull();
  });

  it("bộ chạy ném lỗi thì kết thúc với lý do error và gửi 0", () => {
    const arb = new Arbiter(SPEED);
    const broken: RunDriver = {
      step() {
        throw new RangeError("hỏng");
      },
    };
    arb.startRun(broken, "inverse");
    expect(arb.tick(CTX)).toEqual({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "inverse" });
    expect(arb.lastRunEnd).toEqual({ source: "inverse", done: false, reason: "error" });
    expect(arb.tick(CTX)).toBeNull();
  });
});

describe("protocol", () => {
  const STATE = {
    t: "state",
    link: { robot: true, rtt_ms: 3.2 },
    session: { armed: false, has_driver: true, role: "driver" },
    vel: null,
    pose: { x: 0, y: 0, theta: 0 },
    cmd: { vx: 0, vy: 0, wz: 0 },
    imu: null,
    voltage: null,
    flag_stop: null,
    charge: null,
    health: null,
    last_cmd_seq: null,
  };

  it("nhận state hợp lệ", () => {
    const msg = parseServerMessage(JSON.stringify(STATE));
    expect(msg?.t).toBe("state");
    expect(msg?.session.role).toBe("driver");
  });

  it("từ chối JSON hỏng, tin khác loại và state thiếu trường", () => {
    expect(parseServerMessage("{")).toBeNull();
    expect(parseServerMessage("[]")).toBeNull();
    expect(parseServerMessage("null")).toBeNull();
    expect(parseServerMessage(JSON.stringify({ t: "pong" }))).toBeNull();
    expect(parseServerMessage(JSON.stringify({ ...STATE, link: null }))).toBeNull();
    expect(
      parseServerMessage(JSON.stringify({ ...STATE, session: { armed: "yes" } })),
    ).toBeNull();
    expect(parseServerMessage(JSON.stringify({ ...STATE, pose: 1 }))).toBeNull();
  });

  it("địa chỉ WebSocket suy từ hostname, cổng 8000, đường dẫn /ws/operator", () => {
    expect(resolveWsUrl(undefined, { protocol: "http:", hostname: "100.119.83.63" })).toBe(
      "ws://100.119.83.63:8000/ws/operator",
    );
    expect(resolveWsUrl("", { protocol: "http:", hostname: "localhost" })).toBe(
      "ws://localhost:8000/ws/operator",
    );
    expect(resolveWsUrl(undefined, { protocol: "https:", hostname: "robot.example" })).toBe(
      "wss://robot.example:8000/ws/operator",
    );
  });

  it("biến môi trường ghi đè địa chỉ", () => {
    expect(
      resolveWsUrl(" ws://10.0.0.5:9000/ws/operator ", {
        protocol: "http:",
        hostname: "localhost",
      }),
    ).toBe("ws://10.0.0.5:9000/ws/operator");
  });
});

describe("back-off kết nối lại", () => {
  it("gấp đôi tới mức tối đa", () => {
    const seen: number[] = [];
    let delay = BACKOFF_INITIAL_MS;
    for (let i = 0; i < 6; i++) {
      seen.push(delay);
      delay = nextBackoff(delay);
    }
    expect(seen).toEqual([500, 1000, 2000, 4000, 5000, 5000]);
    expect(BACKOFF_MAX_MS).toBe(5000);
  });
});
