"use client";

// Biểu đồ canvas của ứng dụng (plan.md §3). Mỗi biểu đồ nằm trong MỘT KHU RIÊNG bên dưới, cách nhau
// nhiều dòng trống để các nhánh song song (T12, T13) chỉ thêm vào khu của mình và không xung đột khi merge.
// Quy ước chung: dữ liệu tần số cao đọc từ store ngoài React, vẽ bằng ref + requestAnimationFrame.
// Import cần thêm cho khu của mình thì đặt ngay trong khu đó (import hợp lệ ở bất kỳ chỗ nào trên cùng module).

import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";
import { subscribeTelemetry, trajectory } from "@/robot/store";

// ================================================================================================
// KHU 1: QUỸ ĐẠO ODOMETRY (T09, FR-12). Không sửa khu này trong T12, T13.
// ================================================================================================

interface ChartColors {
  grid: string;
  axis: string;
  path: string;
  marker: string;
  text: string;
}

function readColors(el: HTMLElement): ChartColors {
  const style = getComputedStyle(el);
  const v = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
  const dark = document.documentElement.classList.contains("dark");
  return {
    grid: v("--border", "#e4e4e7"),
    axis: v("--muted-foreground", "#71717a"),
    path: v(dark ? "--chart-1" : "--chart-3", "#4f46e5"),
    marker: v("--foreground", "#18181b"),
    text: v("--muted-foreground", "#71717a"),
  };
}

/** Bước lưới 1, 2, 5 x 10^k sao cho có khoảng `target` vạch trên `span`. */
export function niceStep(span: number, target = 5): number {
  const raw = span / target;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const f = raw / pow;
  return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * pow;
}

function drawTrajectory(canvas: HTMLCanvasElement, colors: ChartColors): void {
  const ctx = canvas.getContext("2d");
  if (ctx === null) return;
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (w === 0 || h === 0) return;
  const pw = Math.round(w * dpr);
  const ph = Math.round(h * dpr);
  if (canvas.width !== pw || canvas.height !== ph) {
    canvas.width = pw;
    canvas.height = ph;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const n = trajectory.length;
  // Khung nhìn vuông tự co giãn theo quỹ đạo, tối thiểu 1 m mỗi chiều.
  let minX = 0;
  let maxX = 0;
  let minY = 0;
  let maxY = 0;
  if (n > 0) {
    minX = maxX = trajectory.x(0);
    minY = maxY = trajectory.y(0);
    for (let i = 1; i < n; i++) {
      const x = trajectory.x(i);
      const y = trajectory.y(i);
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
  }
  const half = Math.max(0.5, (Math.max(maxX - minX, maxY - minY) / 2) * 1.25);
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const pad = 22;
  const scale = (Math.min(w, h) - 2 * pad) / (2 * half);
  const toX = (x: number) => w / 2 + (x - cx) * scale;
  const toY = (y: number) => h / 2 - (y - cy) * scale; // y của odometry hướng lên

  // Lưới và nhãn trục (m).
  const step = niceStep(2 * half);
  ctx.font = "10px ui-monospace, monospace";
  ctx.lineWidth = 1;
  ctx.strokeStyle = colors.grid;
  ctx.fillStyle = colors.text;
  ctx.textBaseline = "top";
  ctx.textAlign = "left";
  const x0 = Math.ceil((cx - w / 2 / scale) / step) * step;
  for (let gx = x0; gx <= cx + w / 2 / scale; gx += step) {
    const px = Math.round(toX(gx)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(px, 0);
    ctx.lineTo(px, h);
    ctx.stroke();
    ctx.fillText(`${+gx.toFixed(3)}`, px + 3, h - 14);
  }
  const y0 = Math.ceil((cy - h / 2 / scale) / step) * step;
  for (let gy = y0; gy <= cy + h / 2 / scale; gy += step) {
    const py = Math.round(toY(gy)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(0, py);
    ctx.lineTo(w, py);
    ctx.stroke();
    ctx.fillText(`${+gy.toFixed(3)}`, 3, py + 3);
  }
  ctx.textAlign = "right";
  ctx.fillText("m", w - 4, 4);

  // Gốc odometry.
  ctx.strokeStyle = colors.axis;
  const ox = toX(0);
  const oy = toY(0);
  ctx.beginPath();
  ctx.moveTo(ox - 5, oy);
  ctx.lineTo(ox + 5, oy);
  ctx.moveTo(ox, oy - 5);
  ctx.lineTo(ox, oy + 5);
  ctx.stroke();

  if (n === 0) {
    ctx.fillStyle = colors.text;
    ctx.font = "13px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("Chưa có dữ liệu quỹ đạo", w / 2, h / 2);
    return;
  }

  // Đường đi.
  ctx.strokeStyle = colors.path;
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(toX(trajectory.x(0)), toY(trajectory.y(0)));
  for (let i = 1; i < n; i++) ctx.lineTo(toX(trajectory.x(i)), toY(trajectory.y(i)));
  ctx.stroke();

  // Vị trí hiện tại: mũi tên theo hướng θ.
  const last = n - 1;
  const px = toX(trajectory.x(last));
  const py = toY(trajectory.y(last));
  const th = trajectory.theta(last);
  ctx.save();
  ctx.translate(px, py);
  ctx.rotate(-th); // canvas có trục y hướng xuống
  ctx.fillStyle = colors.marker;
  ctx.beginPath();
  ctx.moveTo(10, 0);
  ctx.lineTo(-6, 6);
  ctx.lineTo(-3, 0);
  ctx.lineTo(-6, -6);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

/** Quỹ đạo gần đây từ vòng đệm của store; vẽ lại theo khung hình khi có state mới hoặc đổi kích thước. */
export function TrajectoryChart({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (canvas === null) return;
    let frame = 0;
    const paint = () => {
      frame = 0;
      drawTrajectory(canvas, readColors(canvas));
    };
    const schedule = () => {
      if (frame === 0) frame = requestAnimationFrame(paint);
    };
    const unsubscribe = subscribeTelemetry(schedule);
    const observer = new ResizeObserver(schedule);
    observer.observe(canvas);
    schedule();
    return () => {
      unsubscribe();
      observer.disconnect();
      if (frame !== 0) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      role="img"
      aria-label="Quỹ đạo odometry gần đây trong khung x, y (mét)"
      className={cn("block h-full w-full", className)}
    />
  );
}










// ================================================================================================
// KHU 2: LỰC VÀ MÔ-MEN (T12, FR-07). Nhánh T12 chỉ thêm mã vào khu này.
// ================================================================================================
//
// Hai biểu đồ canvas đọc dynamicsFeed (ngoài React): cột mô-men từng bánh so với định mức, và
// chuỗi thời gian Fx, Fy, Mz. Vẽ lại theo khung hình khi có state mới hoặc đổi kích thước.

import { dynamicsFeed } from "@/robot/dynamics";
import { TAU_RATED } from "@/robot/mecanum";

interface DynColors {
  grid: string;
  text: string;
  ok: string;
  bad: string;
  fx: string;
  fy: string;
  mz: string;
}

function readDynColors(el: HTMLElement): DynColors {
  const style = getComputedStyle(el);
  const v = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
  const dark = document.documentElement.classList.contains("dark");
  return {
    grid: v("--border", "#e4e4e7"),
    text: v("--muted-foreground", "#71717a"),
    ok: dark ? "#34d399" : "#059669",
    bad: v("--destructive", "#dc2626"),
    fx: dark ? "#60a5fa" : "#2563eb",
    fy: dark ? "#fbbf24" : "#d97706",
    mz: dark ? "#c084fc" : "#9333ea",
  };
}

/** Chuẩn bị canvas theo devicePixelRatio; trả ngữ cảnh và kích thước CSS, hoặc null nếu chưa có kích thước. */
function prepareCanvas(canvas: HTMLCanvasElement): { ctx: CanvasRenderingContext2D; w: number; h: number } | null {
  const ctx = canvas.getContext("2d");
  if (ctx === null) return null;
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (w === 0 || h === 0) return null;
  const pw = Math.round(w * dpr);
  const ph = Math.round(h * dpr);
  if (canvas.width !== pw || canvas.height !== ph) {
    canvas.width = pw;
    canvas.height = ph;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return { ctx, w, h };
}

/** Gắn một hàm vẽ vào canvas: vẽ theo khung hình khi có state mới hoặc đổi kích thước. */
function useCanvasPainter(draw: (canvas: HTMLCanvasElement, colors: DynColors) => void) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (canvas === null) return;
    let frame = 0;
    const paint = () => {
      frame = 0;
      draw(canvas, readDynColors(canvas));
    };
    const schedule = () => {
      if (frame === 0) frame = requestAnimationFrame(paint);
    };
    const unsubscribe = subscribeTelemetry(schedule);
    const observer = new ResizeObserver(schedule);
    observer.observe(canvas);
    schedule();
    return () => {
      unsubscribe();
      observer.disconnect();
      if (frame !== 0) cancelAnimationFrame(frame);
    };
  }, [draw]);
  return ref;
}

const WHEEL_NAMES = ["A", "B", "C", "D"];

function drawWheelTorque(canvas: HTMLCanvasElement, c: DynColors): void {
  const p = prepareCanvas(canvas);
  if (p === null) return;
  const { ctx, w, h } = p;
  const r = dynamicsFeed.result;
  const padL = 8;
  const padR = 8;
  const padT = 18;
  const padB = 22;
  const plotH = h - padT - padB;
  // Trục dọc đối xứng quanh 0: tối thiểu 1.25 lần định mức, mở rộng nếu vượt.
  let peak = TAU_RATED * 1.25;
  if (r !== null) for (const t of r.tau) peak = Math.max(peak, Math.abs(t) * 1.1);
  const zeroY = padT + plotH / 2;
  const toY = (t: number) => zeroY - (t / peak) * (plotH / 2);

  ctx.font = "10px ui-monospace, monospace";
  ctx.lineWidth = 1;
  ctx.textBaseline = "middle";
  ctx.fillStyle = c.text;
  ctx.strokeStyle = c.grid;
  ctx.beginPath();
  ctx.moveTo(padL, Math.round(zeroY) + 0.5);
  ctx.lineTo(w - padR, Math.round(zeroY) + 0.5);
  ctx.stroke();

  // Đường định mức ±τ_rated, nét đứt.
  ctx.strokeStyle = c.bad;
  ctx.setLineDash([5, 4]);
  for (const sign of [1, -1]) {
    const y = Math.round(toY(sign * TAU_RATED)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(w - padR, y);
    ctx.stroke();
  }
  ctx.setLineDash([]);
  ctx.fillStyle = c.bad;
  ctx.textAlign = "right";
  ctx.fillText(`định mức ±${TAU_RATED} N·m`, w - padR, Math.max(8, toY(TAU_RATED) - 8));

  const slot = (w - padL - padR) / 4;
  const barW = Math.min(48, slot * 0.5);
  for (let i = 0; i < 4; i++) {
    const cx = padL + slot * (i + 0.5);
    ctx.fillStyle = c.text;
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    ctx.fillText(`Bánh ${WHEEL_NAMES[i]}`, cx, h - 6);
    if (r === null) continue;
    const t = r.tau[i];
    const over = r.over[i];
    ctx.fillStyle = over ? c.bad : c.ok;
    const y = toY(t);
    ctx.fillRect(cx - barW / 2, Math.min(y, zeroY), barW, Math.max(1, Math.abs(y - zeroY)));
    ctx.fillStyle = over ? c.bad : c.text;
    ctx.textBaseline = "middle";
    const labelY = t >= 0 ? y - 8 : y + 8;
    ctx.fillText(t.toFixed(3), cx, Math.min(h - padB - 4, Math.max(8, labelY)));
  }
  if (r === null) {
    ctx.fillStyle = c.text;
    ctx.font = "13px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("Chưa có dữ liệu", w / 2, h / 2 - 14);
  }
}

/** Mô-men τ_i từng bánh (cột) so với đường định mức; cột chuyển đỏ khi vượt. */
export function WheelTorqueChart({ className }: { className?: string }) {
  const ref = useCanvasPainter(drawWheelTorque);
  return (
    <canvas
      ref={ref}
      role="img"
      aria-label="Mô-men từng bánh so với mô-men định mức, đơn vị N·m"
      className={cn("block h-full w-full", className)}
    />
  );
}

const SERIES: { key: "fx" | "fy" | "mz"; label: string }[] = [
  { key: "fx", label: "Fx (N)" },
  { key: "fy", label: "Fy (N)" },
  { key: "mz", label: "Mz (N·m)" },
];

function drawForceHistory(canvas: HTMLCanvasElement, c: DynColors): void {
  const p = prepareCanvas(canvas);
  if (p === null) return;
  const { ctx, w, h } = p;
  const hist = dynamicsFeed.history;
  const n = hist.length;
  const padL = 40;
  const padR = 8;
  const padT = 22;
  const padB = 8;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;

  let peak = 1;
  for (let k = 0; k < 3; k++) for (let i = 0; i < n; i++) peak = Math.max(peak, Math.abs(hist.at(k, i)));
  peak = Math.ceil(peak * 1.1);
  const zeroY = padT + plotH / 2;
  const toY = (v: number) => zeroY - (v / peak) * (plotH / 2);

  ctx.font = "10px ui-monospace, monospace";
  ctx.lineWidth = 1;
  ctx.strokeStyle = c.grid;
  ctx.fillStyle = c.text;
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (const v of [peak, 0, -peak]) {
    const y = Math.round(toY(v)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(w - padR, y);
    ctx.stroke();
    ctx.fillText(`${v}`, padL - 4, y);
  }

  // Chú giải.
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
  let lx = padL;
  for (const s of SERIES) {
    ctx.fillStyle = c[s.key];
    ctx.fillRect(lx, 6, 10, 3);
    ctx.fillStyle = c.text;
    ctx.fillText(s.label, lx + 14, 12);
    lx += 14 + ctx.measureText(s.label).width + 14;
  }

  if (n < 2) {
    ctx.fillStyle = c.text;
    ctx.font = "13px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("Chưa có dữ liệu", w / 2, h / 2);
    return;
  }
  const dx = plotW / (hist.capacity - 1);
  const x0 = padL + plotW - (n - 1) * dx; // mẫu mới nhất ở mép phải
  ctx.lineWidth = 1.75;
  ctx.lineJoin = "round";
  SERIES.forEach((s, k) => {
    ctx.strokeStyle = c[s.key];
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = x0 + i * dx;
      const y = toY(hist.at(k, i));
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  });
}

/** Chuỗi thời gian Fx, Fy, Mz gần đây (khoảng 20 s ở 20 Hz). */
export function ForceHistoryChart({ className }: { className?: string }) {
  const ref = useCanvasPainter(drawForceHistory);
  return (
    <canvas
      ref={ref}
      role="img"
      aria-label="Lịch sử Fx, Fy, Mz theo thời gian"
      className={cn("block h-full w-full", className)}
    />
  );
}
//
//
//
//
//
//
//
//
//
// ================================================================================================
// KHU 3: LIDAR DẠNG POLAR (T13, FR-10). Nhánh T13 chỉ thêm mã vào khu này.
// ================================================================================================
//
import { SCAN_BINS } from "@/robot/protocol";
import { getScan, getScanAgeMs, subscribeScan } from "@/robot/store";
import { scanStatus } from "@/robot/telemetry";

const SCAN_REPAINT_MS = 250; // vẽ lại định kỳ để thấy trạng thái mất dữ liệu khi scan ngừng tới

/** Bán kính lưới (m) làm tròn lên bội của 1 m (tối thiểu 2 m) sao cho chứa điểm xa nhất. */
export function scanRangeM(maxMm: number): number {
  return Math.max(2, Math.ceil(maxMm / 1000));
}

function drawScan(canvas: HTMLCanvasElement, colors: ChartColors): void {
  const ctx = canvas.getContext("2d");
  if (ctx === null) return;
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (w === 0 || h === 0) return;
  const pw = Math.round(w * dpr);
  const ph = Math.round(h * dpr);
  if (canvas.width !== pw || canvas.height !== ph) {
    canvas.width = pw;
    canvas.height = ph;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const scan = getScan();
  const status = scanStatus(getScanAgeMs());
  let maxMm = 0;
  let nearestMm = 0;
  let nearestIdx = -1;
  if (scan !== null) {
    for (let i = 0; i < SCAN_BINS; i++) {
      const mm = scan.ranges[i];
      if (mm === 0) continue;
      if (mm > maxMm) maxMm = mm;
      if (nearestIdx < 0 || mm < nearestMm) {
        nearestMm = mm;
        nearestIdx = i;
      }
    }
  }
  const rangeM = scanRangeM(maxMm);
  const cx = w / 2;
  const cy = h / 2;
  const radius = Math.min(w, h) / 2 - 22;
  const scale = radius / rangeM; // px mỗi mét
  // Robot nhìn lên trên (x tiến); góc tăng ngược chiều kim đồng hồ nên y của robot (trái) ở bên trái màn hình.
  const toPx = (angleRad: number, metres: number): [number, number] => [
    cx - Math.sin(angleRad) * metres * scale,
    cy - Math.cos(angleRad) * metres * scale,
  ];

  // Vòng khoảng cách mỗi 1 m (hoặc thưa hơn khi xa) và nhãn.
  const ringStep = rangeM > 6 ? 2 : 1;
  ctx.lineWidth = 1;
  ctx.strokeStyle = colors.grid;
  ctx.fillStyle = colors.text;
  ctx.font = "10px ui-monospace, monospace";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  for (let m = ringStep; m <= rangeM; m += ringStep) {
    ctx.beginPath();
    ctx.arc(cx, cy, m * scale, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.fillText(`${m} m`, cx + 3, cy - m * scale + 2);
  }
  // Tia mỗi 45 độ, nhãn ở mép.
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (let deg = 0; deg < 360; deg += 45) {
    const [ex, ey] = toPx((deg * Math.PI) / 180, rangeM);
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(ex, ey);
    ctx.stroke();
    const [lx, ly] = toPx((deg * Math.PI) / 180, rangeM + 11 / scale);
    ctx.fillText(`${deg}°`, lx, ly);
  }

  // Điểm quét. Mờ đi khi dữ liệu đã cũ.
  if (scan !== null) {
    ctx.globalAlpha = status === "live" ? 1 : 0.3;
    ctx.fillStyle = colors.path;
    for (let i = 0; i < SCAN_BINS; i++) {
      const mm = scan.ranges[i];
      if (mm === 0) continue;
      const [px, py] = toPx((i * Math.PI) / 180, mm / 1000);
      ctx.fillRect(px - 1.5, py - 1.5, 3, 3);
    }
    ctx.globalAlpha = 1;
    if (nearestIdx >= 0) {
      // Điểm gần nhất: đoạn nối từ robot và vòng đánh dấu.
      const [nx, ny] = toPx((nearestIdx * Math.PI) / 180, nearestMm / 1000);
      ctx.globalAlpha = status === "live" ? 1 : 0.3;
      ctx.strokeStyle = colors.marker;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(nx, ny);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.arc(nx, ny, 6, 0, 2 * Math.PI);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  }

  // Robot: mũi tên hướng về phía trước (lên trên).
  ctx.fillStyle = colors.marker;
  ctx.beginPath();
  ctx.moveTo(cx, cy - 9);
  ctx.lineTo(cx + 6, cy + 6);
  ctx.lineTo(cx, cy + 3);
  ctx.lineTo(cx - 6, cy + 6);
  ctx.closePath();
  ctx.fill();

  if (status !== "live") {
    ctx.fillStyle = colors.marker;
    ctx.font = "600 14px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(status === "stale" ? "Mất dữ liệu" : "Chưa có scan", cx, cy + radius * 0.45);
  }
}

/** Scan LiDAR dạng polar: vẽ lại theo khung hình khi có scan mới, đổi kích thước, hoặc định kỳ để báo mất dữ liệu. */
export function PolarScanChart({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (canvas === null) return;
    let frame = 0;
    const paint = () => {
      frame = 0;
      drawScan(canvas, readColors(canvas));
    };
    const schedule = () => {
      if (frame === 0) frame = requestAnimationFrame(paint);
    };
    const unsubscribe = subscribeScan(schedule);
    const observer = new ResizeObserver(schedule);
    observer.observe(canvas);
    const timer = setInterval(schedule, SCAN_REPAINT_MS);
    schedule();
    return () => {
      unsubscribe();
      observer.disconnect();
      clearInterval(timer);
      if (frame !== 0) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      role="img"
      aria-label="Quét LiDAR dạng polar quanh robot, phía trước ở trên"
      className={cn("block h-full w-full", className)}
    />
  );
}


// ================================================================================================
// HẾT FILE. Không thêm mã bên dưới dòng này.
// ================================================================================================
