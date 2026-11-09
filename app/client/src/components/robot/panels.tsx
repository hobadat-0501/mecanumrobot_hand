"use client";

// Bảng số liệu dùng lại giữa các trang (T09 trở đi): khung bảng, ô đọc số, nhãn trạng thái,
// cảnh báo mất dữ liệu, và hook đọc store theo chu kỳ để số liệu 20 Hz không render lại trang.

import { TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Source } from "@/robot/control";
import type { ShellSnapshot } from "@/robot/store";

export const SOURCE_LABEL: Record<Source, string> = {
  idle: "Không có",
  keyboard: "Bàn phím",
  forward: "Chạy động học thuận",
  inverse: "Chạy động học ngược",
};

/** Tình trạng dữ liệu để hiển thị: sống, mất dữ liệu (socket mở nhưng state ngừng), hoặc ngoại tuyến. */
export type DataState = "live" | "stale" | "offline";

export function dataStateOf(shell: ShellSnapshot): DataState {
  if (shell.conn !== "open" || !shell.hasState) return "offline";
  return shell.stale ? "stale" : "live";
}

/**
 * Đọc `read()` mỗi `ms` mili giây và trả giá trị mới nhất. Dùng cho số liệu từ store ngoài React:
 * chỉ render lại theo chu kỳ này (mặc định 10 Hz), không theo từng state 20 Hz (NFR-03).
 * `read` phải ổn định (hàm của module) hoặc bọc bằng useCallback.
 */
export function usePolled<T>(read: () => T, ms = 100): T | null {
  const [value, setValue] = useState<T | null>(null);
  useEffect(() => {
    const tick = () => setValue(read());
    tick();
    const id = setInterval(tick, ms);
    return () => clearInterval(id);
  }, [read, ms]);
  return value;
}

/** Định dạng số cố định chữ số thập phân; null hoặc không hữu hạn: "—". Tránh "-0.00". */
export function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const text = value.toFixed(digits);
  return /^-0(\.0+)?$/.test(text) ? text.slice(1) : text;
}

export type Tone = "ok" | "warn" | "bad" | "idle";

const TONE_TEXT: Record<Tone, string> = {
  ok: "text-emerald-700 dark:text-emerald-400",
  warn: "text-amber-700 dark:text-amber-400",
  bad: "text-destructive",
  idle: "text-muted-foreground",
};

const TONE_DOT: Record<Tone, string> = {
  ok: "bg-emerald-600 dark:bg-emerald-400",
  warn: "bg-amber-600 dark:bg-amber-400",
  bad: "bg-destructive",
  idle: "bg-muted-foreground/60",
};

/** Nhãn trạng thái có chấm màu; màu luôn đi kèm chữ. */
export function StatusBadge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border bg-card px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        TONE_TEXT[tone],
      )}
    >
      <span aria-hidden className={cn("size-1.5 rounded-full", TONE_DOT[tone])} />
      {children}
    </span>
  );
}

/** Khung một nhóm số liệu. */
export function Panel({
  title,
  description,
  action,
  className,
  children,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Card size="sm" className={className}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
        {action ? <CardAction>{action}</CardAction> : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

/** Lưới các ô đọc số, tự xuống hàng theo bề rộng. */
export function ReadoutGrid({
  cols = 3,
  className,
  children,
}: {
  cols?: 2 | 3 | 4;
  className?: string;
  children: ReactNode;
}) {
  const colClass = { 2: "grid-cols-2", 3: "grid-cols-2 sm:grid-cols-3", 4: "grid-cols-2 sm:grid-cols-4" }[cols];
  return <dl className={cn("grid gap-x-4 gap-y-3", colClass, className)}>{children}</dl>;
}

/** Một ô đọc số: nhãn nhỏ, giá trị lớn chữ số đều, đơn vị. `dim` làm mờ khi dữ liệu cũ. */
export function Readout({
  label,
  value,
  unit,
  tone = "idle",
  dim = false,
  text = false,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  tone?: Tone;
  dim?: boolean;
  /** Giá trị là chữ (không phải số): bỏ cỡ chữ số lớn. */
  text?: boolean;
}) {
  return (
    <div className={cn("min-w-0 transition-opacity", dim && "opacity-45")}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 flex items-baseline gap-1">
        <span
          className={cn(
            "truncate font-medium tabular-nums",
            text ? "text-sm" : "font-mono text-lg",
            tone !== "idle" && TONE_TEXT[tone],
          )}
        >
          {value}
        </span>
        {unit ? <span className="text-xs text-muted-foreground">{unit}</span> : null}
      </dd>
    </div>
  );
}

/** Cảnh báo nổi bật khi không có dữ liệu sống. Không hiện khi đang sống. */
export function DataLostAlert({ state }: { state: DataState }) {
  if (state === "live") return null;
  return (
    <Alert variant="destructive">
      <TriangleAlert />
      <AlertTitle>{state === "stale" ? "Mất dữ liệu" : "Chưa có dữ liệu"}</AlertTitle>
      <AlertDescription>
        {state === "stale"
          ? "Kết nối còn mở nhưng quá 1 giây không nhận được trạng thái mới. Số liệu bên dưới là giá trị cũ."
          : "Chưa kết nối tới app server hoặc chưa nhận trạng thái. Số liệu sẽ hiện khi có dữ liệu."}
      </AlertDescription>
    </Alert>
  );
}
