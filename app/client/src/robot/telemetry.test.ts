import { describe, expect, it } from "vitest";

import {
  SCAN_BINS,
  SCAN_FRAME_BYTES,
  SCAN_FRAME_TYPE,
  SCAN_FRAME_VER,
  SCAN_HEADER_BYTES,
  decodeScanFrame,
} from "./protocol";
import {
  HistoryBuffer,
  LatencyTracker,
  RateMeter,
  SCAN_STALE_MS,
  isStale,
  parseDeviceHealth,
  percentile,
  scanStats,
  scanStatus,
  STALE_MS,
} from "./telemetry";

describe("isStale", () => {
  it("chỉ true khi vượt ngưỡng", () => {
    expect(isStale(0)).toBe(false);
    expect(isStale(STALE_MS)).toBe(false);
    expect(isStale(STALE_MS + 1)).toBe(true);
    expect(isStale(Number.POSITIVE_INFINITY)).toBe(true);
    expect(isStale(300, 200)).toBe(true);
  });
});

describe("percentile", () => {
  it("hạng gần nhất", () => {
    expect(percentile([], 0.95)).toBeNull();
    expect(percentile([5], 0.95)).toBe(5);
    const v = Array.from({ length: 20 }, (_, i) => i + 1);
    expect(percentile(v, 0.95)).toBe(19);
    expect(percentile([30, 10, 20], 0.5)).toBe(20);
  });
});

describe("LatencyTracker", () => {
  it("đo từ lúc gửi tới lúc last_cmd_seq đạt seq", () => {
    const t = new LatencyTracker();
    t.sent(1, 1000);
    expect(t.ack(0, 1020)).toBeNull();
    expect(t.ack(1, 1060)).toBe(60);
    expect(t.stats()).toEqual({ last: 60, p95: 60, count: 1 });
    expect(t.ack(1, 1100)).toBeNull(); // đã giải quyết, không tính lại
  });

  it("seq bị thay thế chỉ tính seq mới nhất đạt được", () => {
    const t = new LatencyTracker();
    t.sent(1, 0);
    t.sent(2, 50);
    t.sent(3, 100);
    expect(t.ack(2, 130)).toBe(80); // seq 2; seq 1 bị bỏ
    expect(t.stats().count).toBe(1);
    expect(t.ack(3, 160)).toBe(60);
    expect(t.stats().count).toBe(2);
  });

  it("chỉ khớp đúng last_cmd_seq, không khớp seq lớn hơn hay nhỏ hơn", () => {
    const t = new LatencyTracker();
    t.sent(5, 100);
    expect(t.ack(7, 120)).toBeNull(); // seq 7 là của tab khác, không phải của tab này
    expect(t.ack(4, 130)).toBeNull();
    expect(t.stats().count).toBe(0);
    expect(t.ack(5, 160)).toBe(60); // seq 5 vẫn còn chờ, không bị xóa nhầm
  });

  it("giới hạn cửa sổ, hàng chờ, và bỏ seq quá hạn", () => {
    const t = new LatencyTracker(3, 2, 1000);
    for (let i = 1; i <= 5; i++) {
      t.sent(i, i * 10);
      t.ack(i, i * 10 + i);
    }
    expect(t.stats().count).toBe(3);
    expect(t.stats().last).toBe(5);
    const u = new LatencyTracker(10, 2, 1000);
    u.sent(1, 0);
    u.sent(2, 1);
    u.sent(3, 2); // đẩy seq 1 ra
    expect(u.ack(1, 10)).toBeNull();
    u.sent(9, 100);
    expect(u.ack(null, 5000)).toBeNull();
    expect(u.ack(9, 5001)).toBeNull(); // 9 đã quá hạn
  });

  it("p95 trên cửa sổ", () => {
    const t = new LatencyTracker();
    for (let i = 1; i <= 20; i++) {
      t.sent(i, 0);
      t.ack(i, i * 10);
    }
    expect(t.stats().p95).toBe(190);
    t.clear();
    expect(t.stats()).toEqual({ last: null, p95: null, count: 0 });
  });
});

describe("HistoryBuffer", () => {
  it("giữ tối đa capacity, cũ nhất ở chỉ số 0", () => {
    const b = new HistoryBuffer(3, 0.001, 10);
    for (let i = 0; i < 5; i++) b.push(i * 0.1, 0, 0);
    expect(b.length).toBe(3);
    expect(b.x(0)).toBeCloseTo(0.2);
    expect(b.x(2)).toBeCloseTo(0.4);
  });

  it("bỏ điểm đứng yên nhưng cập nhật hướng; bỏ giá trị không hữu hạn", () => {
    const b = new HistoryBuffer(10, 0.01, 10);
    expect(b.push(0, 0, 0)).toBe(true);
    expect(b.push(0.001, 0, 0.5)).toBe(false);
    expect(b.length).toBe(1);
    expect(b.theta(0)).toBe(0.5);
    expect(b.push(Number.NaN, 0, 0)).toBe(false);
    expect(b.length).toBe(1);
  });

  it("nhảy xa (reset odometry) xóa lịch sử cũ", () => {
    const b = new HistoryBuffer(10, 0.001, 0.5);
    b.push(3, 3, 0);
    b.push(3.1, 3, 0);
    b.push(0, 0, 0);
    expect(b.length).toBe(1);
    expect(b.x(0)).toBe(0);
  });

  it("version tăng khi nội dung đổi", () => {
    const b = new HistoryBuffer();
    const v = b.version;
    b.push(0, 0, 0);
    expect(b.version).toBeGreaterThan(v);
    const w = b.version;
    b.clear();
    expect(b.version).toBeGreaterThan(w);
    expect(b.length).toBe(0);
  });
});

describe("parseDeviceHealth", () => {
  it("thiết bị stm/lidar", () => {
    expect(
      parseDeviceHealth({ ok: false, state: "error", error: "OSError: x", restarts: 2 }),
    ).toEqual({ ok: false, state: "error", errors: 2, rejected: null, lastError: "OSError: x" });
  });
  it("writer", () => {
    expect(
      parseDeviceHealth({
        running: true,
        healthy: true,
        error_count: 3,
        last_error: null,
        rejected_count: 1,
      }),
    ).toEqual({ ok: true, state: "running", errors: 3, rejected: 1, lastError: null });
  });
  it("thiếu dữ liệu", () => {
    expect(parseDeviceHealth(undefined).ok).toBeNull();
    expect(parseDeviceHealth([1]).errors).toBeNull();
  });
});

describe("khung scan LiDAR (PROTO-2)", () => {
  function frame(over: { type?: number; ver?: number; seq?: number; ms?: number; len?: number } = {}) {
    const buf = new ArrayBuffer(over.len ?? SCAN_FRAME_BYTES);
    const view = new DataView(buf);
    view.setUint8(0, over.type ?? SCAN_FRAME_TYPE);
    view.setUint8(1, over.ver ?? SCAN_FRAME_VER);
    view.setUint32(2, over.seq ?? 7, true);
    view.setBigUint64(6, BigInt(over.ms ?? 123456789), true);
    return { buf, view };
  }

  it("giải mã header và 360 ô little-endian", () => {
    const { buf, view } = frame();
    view.setUint16(SCAN_HEADER_BYTES + 0, 1500, true);
    view.setUint16(SCAN_HEADER_BYTES + 2 * 90, 0x1234, true);
    view.setUint16(SCAN_HEADER_BYTES + 2 * 359, 65535, true);
    const out = decodeScanFrame(buf);
    expect(out).not.toBeNull();
    expect(out!.seq).toBe(7);
    expect(out!.tMonoMs).toBe(123456789);
    expect(out!.ranges.length).toBe(SCAN_BINS);
    expect([out!.ranges[0], out!.ranges[90], out!.ranges[359], out!.ranges[1]]).toEqual([
      1500, 0x1234, 65535, 0,
    ]);
  });

  it("bỏ qua khung sai loại, sai phiên bản, sai kích thước", () => {
    expect(decodeScanFrame(frame({ type: 1 }).buf)).toBeNull();
    expect(decodeScanFrame(frame({ ver: 2 }).buf)).toBeNull();
    expect(decodeScanFrame(frame({ len: SCAN_FRAME_BYTES - 1 }).buf)).toBeNull();
    expect(decodeScanFrame(frame({ len: SCAN_FRAME_BYTES + 2 }).buf)).toBeNull();
    expect(decodeScanFrame(new ArrayBuffer(0))).toBeNull();
    expect(decodeScanFrame("x" as unknown as ArrayBuffer)).toBeNull();
  });
});

describe("thống kê scan và tuổi dữ liệu", () => {
  it("scanStats: đếm ô có điểm, tìm ô gần nhất, bỏ ô 0", () => {
    const ranges = new Uint16Array(SCAN_BINS);
    expect(scanStats(ranges)).toEqual({ count: 0, nearestMm: null, nearestDeg: null });
    ranges[10] = 2000;
    ranges[200] = 800;
    ranges[300] = 800;
    expect(scanStats(ranges)).toEqual({ count: 3, nearestMm: 800, nearestDeg: 200 });
  });

  it("scanStatus: none, live, stale theo ngưỡng", () => {
    expect(scanStatus(null)).toBe("none");
    expect(scanStatus(0)).toBe("live");
    expect(scanStatus(SCAN_STALE_MS)).toBe("live");
    expect(scanStatus(SCAN_STALE_MS + 1)).toBe("stale");
  });

  it("RateMeter: đo Hz, về 0 khi ngừng", () => {
    const meter = new RateMeter(2000);
    expect(meter.rate(0)).toBe(0);
    for (let i = 0; i <= 10; i++) meter.tick(i * 100);
    expect(meter.rate(1000)).toBeCloseTo(10, 5);
    expect(meter.rate(1500)).toBeCloseTo(10, 5);
    expect(meter.rate(2500)).toBe(0); // mẫu cuối đã cũ hơn nửa cửa sổ
    meter.clear();
    expect(meter.rate(1000)).toBe(0);
  });
});

describe("T21: gesture protocol", () => {
  it("httpBaseFromWs giữ host, cổng và đổi scheme", async () => {
    const { httpBaseFromWs } = await import("./protocol");
    expect(httpBaseFromWs("ws://100.119.83.63:8000/ws/operator")).toBe("http://100.119.83.63:8000");
    expect(httpBaseFromWs("wss://x.example/ws/operator")).toBe("https://x.example");
  });

  it("tin mode không mang vận tốc", async () => {
    const { encodeMessage } = await import("./protocol");
    const text = encodeMessage({ t: "mode", gesture: true });
    expect(JSON.parse(text)).toEqual({ t: "mode", gesture: true });
  });

  it("parseServerMessage nhận state có mode và vision", async () => {
    const { parseServerMessage } = await import("./protocol");
    const state = {
      t: "state",
      link: { robot: true, rtt_ms: 5 },
      session: { armed: true, has_driver: true, role: "driver", mode: "gesture" },
      pose: { x: 0, y: 0, theta: 0 },
      cmd: { vx: 0, vy: 0, wz: 0 },
      vision: { link: true, enabled: true, state: { state: "GESTURE" }, result: null },
    };
    const msg = parseServerMessage(JSON.stringify(state));
    expect(msg?.session.mode).toBe("gesture");
    expect(msg?.vision?.state?.state).toBe("GESTURE");
  });
});
