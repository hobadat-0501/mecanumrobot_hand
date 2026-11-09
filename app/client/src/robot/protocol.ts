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
  | { t: "odom_reset" };

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
  session: { armed: boolean; has_driver: boolean; role: Role | null };
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

export interface LocationLike {
  protocol: string;
  hostname: string;
}

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
