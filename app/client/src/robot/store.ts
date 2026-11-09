// Kho trạng thái robot cho cả ứng dụng: một WebSocket ngoài React, tự kết nối lại có back-off,
// một bộ phân xử nguồn lệnh với một timer 20 Hz (FR-02, FR-03, FR-08, FR-09, SAF-03a, NFR-03).
// Dữ liệu tần số cao (state ~20 Hz) không nằm trong React state: trang đọc bằng
// useTelemetry() hoặc subscribeTelemetry() + getTelemetry() (canvas qua ref).
// Trạng thái tần số thấp cho thanh trạng thái nằm trong useShell().

import { useSyncExternalStore } from "react";

import { Arbiter, DEFAULT_SPEED, TICK_MS } from "./control";
import type {
  EndReason,
  Output,
  RunDriver,
  RunEnd,
  RunSource,
  Source,
  Speed,
} from "./control";
import { encodeMessage, parseServerMessage, resolveWsUrl } from "./protocol";
import type { ClientMessage, Role, StateMsg } from "./protocol";

export const BACKOFF_INITIAL_MS = 500;
export const BACKOFF_MAX_MS = 5000;
const MAX_BUFFERED_BYTES = 8192;
const CODE_KEY = "mecanum.operatorCode";

/** Thời gian chờ kết nối lại lần tới: gấp đôi, tối đa BACKOFF_MAX_MS. */
export function nextBackoff(previousMs: number): number {
  return Math.min(previousMs * 2, BACKOFF_MAX_MS);
}

export type Connection = "connecting" | "open" | "closed";

/** Trạng thái tần số thấp: chỉ đổi khi một trường đổi, nên thanh trạng thái không render lại ở 20 Hz. */
export interface ShellSnapshot {
  conn: Connection;
  /** Đã nhận ít nhất một state trên kết nối hiện tại. */
  hasState: boolean;
  robotLink: boolean;
  armed: boolean;
  role: Role | null;
  hasCode: boolean;
  source: Source;
  speed: Speed;
  lastRunEnd: RunEnd | null;
}

const INITIAL_SHELL: ShellSnapshot = {
  conn: "closed",
  hasState: false,
  robotLink: false,
  armed: false,
  role: null,
  hasCode: false,
  source: "idle",
  speed: DEFAULT_SPEED,
  lastRunEnd: null,
};

const arbiter = new Arbiter(DEFAULT_SPEED);

let started = false;
let ws: WebSocket | null = null;
let conn: Connection = "closed";
let backoffMs = BACKOFF_INITIAL_MS;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let tickTimer: ReturnType<typeof setInterval> | null = null;
let lastTickAt = 0;
let seq = 0;
let operatorCode = "";
let telemetry: StateMsg | null = null;
let telemetryAt = Number.NEGATIVE_INFINITY;
let shell: ShellSnapshot = INITIAL_SHELL;
const telemetryListeners = new Set<() => void>();
const shellListeners = new Set<() => void>();

// ---- tồn tại ngoài React: đăng ký và đọc ----

export function subscribeTelemetry(listener: () => void): () => void {
  telemetryListeners.add(listener);
  return () => {
    telemetryListeners.delete(listener);
  };
}

export function getTelemetry(): StateMsg | null {
  return telemetry;
}

/** performance.now() lúc nhận state gần nhất; -Infinity nếu chưa có. */
export function getTelemetryAt(): number {
  return telemetryAt;
}

function subscribeShell(listener: () => void): () => void {
  shellListeners.add(listener);
  return () => {
    shellListeners.delete(listener);
  };
}

function getShell(): ShellSnapshot {
  return shell;
}

function getServerShell(): ShellSnapshot {
  return INITIAL_SHELL;
}

function getServerTelemetry(): StateMsg | null {
  return null;
}

/** State mới nhất ở tần số tới 20 Hz; chỉ trang cần số liệu mới nên dùng. */
export function useTelemetry(): StateMsg | null {
  return useSyncExternalStore(subscribeTelemetry, getTelemetry, getServerTelemetry);
}

/** Trạng thái tần số thấp cho thanh trạng thái và trang cần biết arm, quyền lái, nguồn lệnh. */
export function useShell(): ShellSnapshot {
  return useSyncExternalStore(subscribeShell, getShell, getServerShell);
}

function notifyTelemetry(): void {
  for (const listener of telemetryListeners) listener();
}

function publishShell(): void {
  const next: ShellSnapshot = {
    conn,
    hasState: telemetry !== null,
    robotLink: telemetry?.link.robot ?? false,
    armed: telemetry?.session.armed ?? false,
    role: telemetry?.session.role ?? null,
    hasCode: operatorCode !== "",
    source: arbiter.source,
    speed: arbiter.speed,
    lastRunEnd: arbiter.lastRunEnd,
  };
  const same =
    next.conn === shell.conn &&
    next.hasState === shell.hasState &&
    next.robotLink === shell.robotLink &&
    next.armed === shell.armed &&
    next.role === shell.role &&
    next.hasCode === shell.hasCode &&
    next.source === shell.source &&
    next.speed === shell.speed &&
    next.lastRunEnd === shell.lastRunEnd;
  if (same) return;
  shell = next;
  for (const listener of shellListeners) listener();
}

// ---- gửi ----

function isOpen(): boolean {
  return ws !== null && ws.readyState === WebSocket.OPEN;
}

function send(msg: ClientMessage): void {
  if (ws !== null && ws.readyState === WebSocket.OPEN) ws.send(encodeMessage(msg));
}

function sendCmd(out: Output): void {
  if (ws === null || ws.readyState !== WebSocket.OPEN) return;
  const zero = out.cmd.vx === 0 && out.cmd.vy === 0 && out.cmd.wz === 0;
  // NFR-03: socket đang nghẽn thì bỏ lệnh chuyển động này, không dồn hàng đợi; lệnh 0 vẫn đi.
  if (!zero && ws.bufferedAmount > MAX_BUFFERED_BYTES) return;
  seq += 1;
  send({
    t: "cmd_vel",
    seq,
    vx: out.cmd.vx,
    vy: out.cmd.vy,
    wz: out.cmd.wz,
    src: out.src,
  });
}

function sendZeroNow(): void {
  sendCmd({ cmd: { vx: 0, vy: 0, wz: 0 }, src: "stop" });
}

function sendHello(): void {
  if (operatorCode !== "") send({ t: "hello", token: operatorCode });
}

// ---- điều khiển ----

/** Quyền lái thật: socket mở, đã arm, và client này đang giữ quyền lái. */
function canDrive(): boolean {
  return (
    isOpen() &&
    telemetry !== null &&
    telemetry.session.armed &&
    telemetry.session.role === "driver"
  );
}

function syncTimer(): void {
  if (arbiter.active) {
    if (tickTimer === null) {
      lastTickAt = performance.now() - TICK_MS;
      tickTimer = setInterval(onTick, TICK_MS);
    }
  } else if (tickTimer !== null) {
    clearInterval(tickTimer);
    tickTimer = null;
  }
}

function onTick(): void {
  if (!canDrive()) {
    haltAll("disarmed");
    return;
  }
  const now = performance.now();
  const dt = Math.max(0, (now - lastTickAt) / 1000);
  lastTickAt = now;
  const out = arbiter.tick({
    dt,
    pose: telemetry?.pose ?? null,
    stateAgeS: (now - telemetryAt) / 1000,
    armed: true,
  });
  if (out !== null) sendCmd(out);
  syncTimer();
  publishShell();
}

function flushZero(): void {
  const out = arbiter.flushZero();
  if (out !== null) sendCmd(out);
}

/**
 * SAF-03a: hủy phím và lần chạy, gửi cmd_vel 0 đúng một lần (nếu socket còn mở).
 * Dùng khi mất focus, ẩn tab, disarm, đóng socket.
 */
export function haltAll(reason: EndReason): void {
  arbiter.releaseAll(reason);
  sendZeroNow();
  syncTimer();
  publishShell();
}

/** Dừng khẩn (X, Esc, nút): 0 rồi disarm. */
export function emergencyStop(): void {
  arbiter.releaseAll("stop");
  sendZeroNow();
  send({ t: "arm", on: false });
  syncTimer();
  publishShell();
}

export function setArmed(on: boolean): void {
  send({ t: "arm", on });
}

export function resetOdometry(): void {
  send({ t: "odom_reset" });
}

/** Phím di chuyển nhấn xuống. Bỏ qua khi chưa được phép lái. */
export function pressMotion(code: string): void {
  if (!canDrive()) return;
  arbiter.keyDown(code);
  syncTimer();
  publishShell();
}

export function releaseMotion(code: string): void {
  arbiter.keyUp(code);
  flushZero();
  syncTimer();
  publishShell();
}

/** Focus vào ô nhập: nhả mọi phím đang giữ, giữ nguyên lần chạy. */
export function releaseKeys(): void {
  arbiter.releaseKeys();
  flushZero();
  syncTimer();
  publishShell();
}

/** T10, T11: bắt đầu một lần chạy theo bộ bước của motion.ts. Trả false nếu không được phép. */
export function startRun(driver: RunDriver, source: RunSource): boolean {
  if (!canDrive()) return false;
  if (!arbiter.startRun(driver, source)) return false;
  syncTimer();
  publishShell();
  return true;
}

/** T10, T11: hủy lần chạy, gửi 0 một lần nếu còn nợ. */
export function cancelRun(): void {
  arbiter.cancelRun("cancel");
  flushZero();
  syncTimer();
  publishShell();
}

/** Đặt tốc độ bàn phím. Giá trị không hữu hạn hoặc không dương bị bỏ qua; không có chặn trên. */
export function setSpeed(lin: number, ang: number): void {
  if (!(Number.isFinite(lin) && lin > 0 && Number.isFinite(ang) && ang > 0)) return;
  arbiter.setSpeed({ lin, ang });
  publishShell();
}

// ---- mã điều khiển ----

function readStoredCode(): string {
  try {
    return window.sessionStorage.getItem(CODE_KEY) ?? "";
  } catch {
    return "";
  }
}

function writeStoredCode(code: string): void {
  try {
    if (code === "") window.sessionStorage.removeItem(CODE_KEY);
    else window.sessionStorage.setItem(CODE_KEY, code);
  } catch {
    // sessionStorage bị chặn: mã chỉ sống trong bộ nhớ.
  }
}

/** Đặt mã điều khiển. Rỗng thì xóa mã và kết nối lại ở chế độ chỉ xem. */
export function setOperatorCode(code: string): void {
  operatorCode = code.trim();
  writeStoredCode(operatorCode);
  if (operatorCode !== "") sendHello();
  else if (ws !== null) ws.close();
  publishShell();
}

// ---- kết nối ----

function scheduleReconnect(): void {
  if (reconnectTimer !== null) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, backoffMs);
  backoffMs = nextBackoff(backoffMs);
}

function connect(): void {
  conn = "connecting";
  publishShell();
  let socket: WebSocket;
  try {
    socket = new WebSocket(
      resolveWsUrl(process.env.NEXT_PUBLIC_APP_WS_URL, window.location),
    );
  } catch {
    conn = "closed";
    publishShell();
    scheduleReconnect();
    return;
  }
  socket.binaryType = "arraybuffer";
  ws = socket;
  socket.onopen = () => {
    if (ws !== socket) return;
    conn = "open";
    backoffMs = BACKOFF_INITIAL_MS;
    sendHello();
    publishShell();
  };
  socket.onmessage = (event: MessageEvent) => {
    if (ws !== socket || typeof event.data !== "string") return; // khung nhị phân: LiDAR, T13
    const msg = parseServerMessage(event.data);
    if (msg === null) return;
    const couldDrive = canDrive();
    telemetry = msg;
    telemetryAt = performance.now();
    notifyTelemetry();
    if (couldDrive && !canDrive()) haltAll("disarmed");
    else publishShell();
  };
  socket.onclose = () => {
    if (ws !== socket) return;
    ws = null;
    conn = "closed";
    telemetry = null;
    notifyTelemetry();
    haltAll("closed");
    scheduleReconnect();
  };
  socket.onerror = () => {
    // onclose theo sau; không làm gì thêm.
  };
}

/** Khởi động kết nối một lần (gọi từ effect; gọi lại không làm gì). Không bao giờ đóng khi đổi trang. */
export function startStore(): void {
  if (started || typeof window === "undefined") return;
  started = true;
  operatorCode = readStoredCode();
  connect();
}
