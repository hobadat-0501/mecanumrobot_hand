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
// KHU 2: LỰC VÀ MÔ-MEN (T12, FR-07). RỖNG. Nhánh T12 chỉ thêm mã vào khu này.
// ================================================================================================
//
// (chỗ dành cho biểu đồ lực/mô-men của T12)
//
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
// KHU 3: LIDAR DẠNG POLAR (T13, FR-10). RỖNG. Nhánh T13 chỉ thêm mã vào khu này.
// ================================================================================================
//
// (chỗ dành cho biểu đồ polar LiDAR của T13)
//
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
// HẾT FILE. Không thêm mã bên dưới dòng này.
// ================================================================================================
