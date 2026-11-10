// PROTO-1: kiểu tin nhắn web <-> app server. Mọi vận tốc theo đơn vị web (m/s, rad/s).
// Thẻ loại tin nằm ở khóa `t`.

import type { BodyVel, Pose } from "./mecanum";

/** Nguồn của một cmd_vel; app server bỏ qua trường này. */
export type CmdSrc = "keyboard" | "forward" | "inverse" | "stop";

export type Role = "driver" | "viewer";

export type ClientMessage =
  | { t: "hello"; token: string }
  | {
      t: "cmd_vel";
      seq: number;
      vx: number;
      vy: number;
      wz: number;
      src: CmdSrc;
    }
  | { t: "arm"; on: boolean }
  | { t: "mode"; gesture: boolean }
  | StaffCommand
  | { t: "odom_reset" };

/** Lệnh quản lý nhân viên (PROTO-1/3): chỉ driver gửi được, app server chuyển tiếp tới vision agent. */
export type StaffCommand =
  | { t: "staff_list" }
  | { t: "staff_create"; code: string; name: string; note: string; allowed: boolean }
  | { t: "staff_update"; id: number; code?: string; name?: string; note?: string; allowed?: boolean }
  | { t: "staff_delete"; id: number }
  | { t: "faces_clear"; id: number };

/** Một nhân viên như web nhận được: không có embedding, chỉ số mẫu. */
export interface StaffMember {
  id: number;
  code: string;
  name: string;
  note: string;
  allowed: boolean;
  samples: number;
  last_enrolled: number | null;
}

/** Chế độ điều khiển của phiên: tay hoặc cử chỉ (D-09). Không mang vận tốc. */
export type SessionMode = "manual" | "gesture";

/** Trạng thái vision agent đã lọc ở app server (chỉ trường hiển thị, không có vận tốc). */
export interface VisionInfo {
  link: boolean;
  enabled: boolean;
  state: {
    mode?: boolean;
    state?: string;
    user?: string | null;
    gesture?: string | null;
    guide?: string | null;
    fps?: number;
    cmd_active?: boolean;
  } | null;
  result: LooseRecord | null;
}

export interface Imu {
  ax: number;
  ay: number;
  az: number;
  gx: number;
  gy: number;
  gz: number;
}

/** Trường tự do do robot gửi; trang hệ thống (T09) sẽ đọc chi tiết. */
export type LooseRecord = { [key: string]: unknown };

export interface StateMsg {
  t: "state";
  link: { robot: boolean; rtt_ms: number | null };
  session: {
    armed: boolean;
    has_driver: boolean;
    role: Role | null;
    mode?: SessionMode;
    /** Mã dùng một lần để xin cookie xem video (chỉ gửi cho người lái). */
    video_nonce?: string;
  };
  /** Báo cáo của robot về chế độ cử chỉ và cổng LiDAR; null khi không có. */
  gesture?: LooseRecord | null;
  vision?: VisionInfo;
  vel: BodyVel | null;
  pose: Pose;
  cmd: BodyVel;
  imu: Imu | null;
  voltage: number | null;
  flag_stop: boolean | number | null;
  charge: LooseRecord | null;
  health: LooseRecord | null;
  last_cmd_seq: number | null;
}

export function encodeMessage(msg: ClientMessage): string {
  return JSON.stringify(msg);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Phân tích một tin văn bản từ server. Trả null nếu không phải `state` hợp lệ. */
export function parseServerMessage(text: string): StateMsg | null {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return null;
  }
  if (!isRecord(data) || data.t !== "state") return null;
  const { link, session, pose, cmd } = data;
  if (!isRecord(link) || typeof link.robot !== "boolean") return null;
  if (!isRecord(session) || typeof session.armed !== "boolean") return null;
  if (!isRecord(pose) || !isRecord(cmd)) return null;
  return data as unknown as StateMsg;
}

// PROTO-2: khung nhị phân `scan` (robot -> app server -> web, chuyển nguyên vẹn), little-endian.
// Đầu khung: type u8, ver u8, seq u32, t_mono_ms u64 (14 byte); thân: 360 x u16 mm, 0 là không có điểm.
// Ô i ứng với góc i độ: ô 0 ở phía trước robot (trục x), tăng dần ngược chiều kim đồng hồ.
// Hằng số khớp robot/robot_agent/server.py.
export const SCAN_FRAME_TYPE = 2;
export const SCAN_FRAME_VER = 1;
export const SCAN_BINS = 360;
export const SCAN_HEADER_BYTES = 14;
export const SCAN_FRAME_BYTES = SCAN_HEADER_BYTES + 2 * SCAN_BINS;

export interface ScanFrame {
  seq: number;
  /** Thời điểm mẫu theo đồng hồ đơn điệu của robot (ms); chỉ để so sánh, không phải giờ thực. */
  tMonoMs: number;
  /** Khoảng cách mm theo ô 1 độ; 0 là không có điểm. */
  ranges: Uint16Array;
}

/** Giải mã khung scan. Trả null nếu sai kích thước, sai loại hoặc sai phiên bản (bỏ qua, không ném lỗi). */
export function decodeScanFrame(buffer: ArrayBuffer): ScanFrame | null {
  if (!(buffer instanceof ArrayBuffer) || buffer.byteLength !== SCAN_FRAME_BYTES) return null;
  const view = new DataView(buffer);
  if (view.getUint8(0) !== SCAN_FRAME_TYPE || view.getUint8(1) !== SCAN_FRAME_VER) return null;
  const ranges = new Uint16Array(SCAN_BINS);
  for (let i = 0; i < SCAN_BINS; i++) ranges[i] = view.getUint16(SCAN_HEADER_BYTES + 2 * i, true);
  return {
    seq: view.getUint32(2, true),
    tMonoMs: Number(view.getBigUint64(6, true)),
    ranges,
  };
}

export interface LocationLike {
  protocol: string;
  hostname: string;
}

/** Địa chỉ HTTP của app server suy từ địa chỉ WebSocket (cùng host, cổng). */
export function httpBaseFromWs(wsUrl: string): string {
  const u = new URL(wsUrl);
  return `${u.protocol === "wss:" ? "https" : "http"}://${u.host}`;
}

export const VIDEO_PATH = "/video";
export const VIDEO_SESSION_PATH = "/video/session";

export const WS_PORT = 8000;
export const WS_PATH = "/ws/operator";

/** Địa chỉ WebSocket: biến môi trường nếu có, ngược lại suy từ hostname của trang, cổng 8000. */
export function resolveWsUrl(
  envUrl: string | undefined,
  loc: LocationLike,
): string {
  if (envUrl !== undefined && envUrl.trim() !== "") return envUrl.trim();
  const scheme = loc.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${loc.hostname}:${WS_PORT}${WS_PATH}`;
}
