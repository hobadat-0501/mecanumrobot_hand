"use client";

// FR-05, FR-06, PHY-6: động học ngược. Kiểu A (quãng đường + hướng so với thân tại lúc bấm chạy)
// hoặc kiểu B (đích x, y, θ theo khung odometry). Chạy bằng bộ bám đích của motion.ts qua store;
// đầu ra duy nhất là cmd_vel. Số liệu tần số cao đọc theo chu kỳ 10 Hz, không nằm trong React state.

import { Play } from "lucide-react";
import { useId, useState } from "react";

import {
  DataLostAlert,
  Panel,
  Readout,
  ReadoutGrid,
  StatusBadge,
  dataStateOf,
  fmt,
  usePolled,
} from "@/components/robot/panels";
import type { Tone } from "@/components/robot/panels";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  DEFAULT_FIELDS,
  END_REASON_LABEL,
  InverseRun,
  parseInverseFields,
  radToDeg,
  resolveGoal,
} from "@/robot/inverse";
import type { FieldKey, InputKind, InverseFields } from "@/robot/inverse";
import { inverseKinematics } from "@/robot/mecanum";
import { getTelemetry, startRun, useShell } from "@/robot/store";
import type { ShellSnapshot } from "@/robot/store";

// Lần chạy gần nhất, giữ ở module để không mất khi chuyển trang trong lúc đang chạy.
let currentRun: InverseRun | null = null;

const ZERO_CMD = { vx: 0, vy: 0, wz: 0 };
const WHEEL_NAMES = ["A", "B", "C", "D"] as const;

function Field({
  id,
  label,
  unit,
  value,
  error,
  onChange,
}: {
  id: string;
  label: string;
  unit: string;
  value: string;
  error?: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label htmlFor={id}>
        {label} <span className="font-normal text-muted-foreground">({unit})</span>
      </Label>
      <Input
        id={id}
        type="text"
        inputMode="decimal"
        autoComplete="off"
        value={value}
        aria-invalid={error !== undefined}
        aria-describedby={error !== undefined ? `${id}-err` : undefined}
        onChange={(e) => onChange(e.target.value)}
        className="font-mono tabular-nums"
      />
      {error !== undefined ? (
        <p id={`${id}-err`} className="text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Lý do chưa chạy được do phiên điều khiển; null nếu đủ điều kiện. */
function sessionBlocker(shell: ShellSnapshot): string | null {
  if (shell.conn !== "open") return "Chưa kết nối tới app server.";
  if (!shell.hasState || shell.stale) return "Chưa có dữ liệu trạng thái mới từ robot.";
  if (shell.role !== "driver") return "Chưa có quyền lái: nhập mã điều khiển ở thanh trên cùng.";
  if (!shell.armed) return "Robot đang disarm: bấm Arm (R) trước khi chạy.";
  if (shell.source === "keyboard") return "Đang giữ phím di chuyển: nhả phím rồi chạy.";
  return null;
}

interface Snap {
  run: InverseRun;
  cur: { x: number; y: number; theta: number } | null;
}

function readSnap(): Snap | null {
  if (currentRun === null) return null;
  const t = getTelemetry();
  return { run: currentRun, cur: t === null ? null : { ...t.pose } };
}

function statusOf(shell: ShellSnapshot): { tone: Tone; text: string } {
  if (shell.source === "inverse") return { tone: "warn", text: "Đang chạy" };
  const end = shell.lastRunEnd;
  if (end === null || end.source !== "inverse") return { tone: "idle", text: "Chưa chạy" };
  if (end.done) return { tone: "ok", text: "Đã tới đích" };
  const why = END_REASON_LABEL[end.reason ?? "error"] ?? String(end.reason);
  return { tone: "bad", text: `Đã hủy: ${why}` };
}

export default function Page() {
  const uid = useId();
  const shell = useShell();
  const snap = usePolled(readSnap, 100);
  const [kind, setKind] = useState<InputKind>("distance");
  const [fields, setFields] = useState<InverseFields>(DEFAULT_FIELDS);
  const [startError, setStartError] = useState<string | null>(null);

  const set = (key: FieldKey) => (v: string) => {
    setFields((f) => ({ ...f, [key]: v }));
    setStartError(null);
  };

  const parsedResult = parseInverseFields(kind, fields);
  const errors = parsedResult.ok ? {} : parsedResult.errors;
  const running = shell.source === "inverse";
  const blocker = running
    ? null
    : (sessionBlocker(shell) ?? (parsedResult.ok ? null : `Dữ liệu nhập chưa hợp lệ: ${parsedResult.message}.`));
  const canRun = !running && blocker === null;

  const run = () => {
    if (!parsedResult.ok) return;
    const pose = getTelemetry()?.pose;
    if (pose === undefined) {
      setStartError("Chưa có tư thế từ server.");
      return;
    }
    try {
      const start = { x: pose.x, y: pose.y, theta: pose.theta };
      const goal = resolveGoal(parsedResult.value.target, start);
      const next = new InverseRun(start, goal, parsedResult.value.params);
      if (!startRun(next, "inverse")) {
        setStartError("Không bắt đầu được: kiểm tra arm, quyền lái và phím đang giữ.");
        return;
      }
      currentRun = next;
      setStartError(null);
    } catch (e) {
      setStartError(e instanceof Error ? e.message : "Không bắt đầu được.");
    }
  };

  const data = dataStateOf(shell);
  const active = snap?.run ?? null;
  const status = active !== null ? statusOf(shell) : { tone: "idle" as Tone, text: "Chưa chạy" };
  const progress = active?.progress() ?? null;
  // Khi không chạy thì không có lệnh nào được gửi: hiển thị 0 thay vì lệnh cũ.
  const cmd = active === null ? null : running ? active.lastCmd : ZERO_CMD;
  const wheels = active === null ? null : running ? active.wheels() : inverseKinematics(ZERO_CMD);

  const kindButton = (k: InputKind, text: string) => (
    <Button
      type="button"
      size="lg"
      variant={kind === k ? "secondary" : "outline"}
      aria-pressed={kind === k}
      disabled={running}
      className="flex-1"
      onClick={() => setKind(k)}
    >
      {text}
    </Button>
  );

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Động học ngược</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Đặt đích rồi chạy: bộ bám đích chạy trên trình duyệt ở 20 Hz và chỉ gửi cmd_vel. Nhấn phím di chuyển, Esc hoặc nút Hủy để dừng.
        </p>
      </div>

      <DataLostAlert state={data} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Đích" description="Chọn một trong hai cách nhập.">
          <div className="flex flex-col gap-4">
            <div className="flex gap-2" role="group" aria-label="Kiểu nhập đích">
              {kindButton("distance", "A: Quãng đường + hướng")}
              {kindButton("pose", "B: Đích x, y, θ")}
            </div>

            {kind === "distance" ? (
              <div className="grid grid-cols-2 gap-3">
                <Field id={`${uid}-distance`} label="Quãng đường" unit="m" value={fields.distance} error={errors.distance} onChange={set("distance")} />
                <Field id={`${uid}-heading`} label="Hướng" unit="độ" value={fields.heading} error={errors.heading} onChange={set("heading")} />
                <p className="col-span-2 text-xs text-muted-foreground">
                  Hướng đo so với mũi xe tại lúc bấm Chạy, dương ngược chiều kim đồng hồ (0 độ là tiến thẳng, 90 độ là sang trái). Xe giữ nguyên hướng thân.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Field id={`${uid}-x`} label="x" unit="m" value={fields.x} error={errors.x} onChange={set("x")} />
                <Field id={`${uid}-y`} label="y" unit="m" value={fields.y} error={errors.y} onChange={set("y")} />
                <Field id={`${uid}-theta`} label="θ" unit="độ" value={fields.theta} error={errors.theta} onChange={set("theta")} />
                <p className="col-span-2 text-xs text-muted-foreground sm:col-span-3">
                  Theo khung odometry của app server (nút đặt lại ở trang Tổng quan).
                </p>
              </div>
            )}
          </div>
        </Panel>

        <Panel title="Tham số chạy" description="Mọi giá trị dương đều được nhận. Gia tốc do STM đảm nhiệm nên không nhập ở đây.">
          <div className="grid grid-cols-2 gap-3">
            <Field id={`${uid}-v`} label="Tốc độ chạy" unit="m/s" value={fields.vCruise} error={errors.vCruise} onChange={set("vCruise")} />
            <Field id={`${uid}-w`} label="Tốc độ quay" unit="rad/s" value={fields.wzCruise} error={errors.wzCruise} onChange={set("wzCruise")} />
          </div>
        </Panel>
      </div>

      <div className="flex flex-col gap-2 rounded-lg border bg-card p-3 sm:flex-row sm:items-center">
        <div className="flex gap-2">
          <Button type="button" size="lg" className="flex-1 sm:flex-none" disabled={!canRun} onClick={run}>
            <Play data-icon="inline-start" />
            Chạy
          </Button>
          <p className="self-center text-sm text-muted-foreground">
            Bấm <kbd className="rounded border bg-muted px-1.5 py-0.5 font-mono text-xs">Space</kbd> để dừng.
          </p>
        </div>
        <p role="status" className="min-w-0 text-sm text-muted-foreground sm:ml-2">
          {startError ?? blocker ?? (running ? "Đang chạy tới đích." : "Sẵn sàng.")}
        </p>
        <div className="sm:ml-auto">
          <StatusBadge tone={status.tone}>{status.text}</StatusBadge>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Tiến độ" description="Đích và sai số tính theo khung odometry.">
          <div className="flex flex-col gap-4">
            <Progress value={progress?.percent ?? 0} aria-label="Phần trăm hoàn thành">
              <span className="text-sm font-medium">Hoàn thành</span>
              <span className="ml-auto font-mono text-sm tabular-nums">{progress === null ? "—" : `${progress.percent}%`}</span>
            </Progress>
            <ReadoutGrid cols={2}>
              <Readout label="Còn lại (khoảng cách)" value={fmt(progress?.remainingDist, 3)} unit="m" />
              <Readout label="Còn lại (góc)" value={fmt(progress === null ? null : radToDeg(progress.remainingAngle), 1)} unit="độ" />
              <Readout label="T dự kiến" value={fmt(active?.tExpected, 1)} unit="s" />
              <Readout label="Hạn chót (3T + 5)" value={fmt(active === null ? null : 3 * active.tExpected + 5, 1)} unit="s" />
              <Readout label="Đích x" value={fmt(active?.goal.x, 3)} unit="m" />
              <Readout label="Đích y" value={fmt(active?.goal.y, 3)} unit="m" />
              <Readout label="Đích θ" value={fmt(active === null ? null : radToDeg(active.goal.theta), 1)} unit="độ" />
              <Readout label="Hiện tại (x, y, θ)" text value={snap?.cur ? `${fmt(snap.cur.x, 3)}, ${fmt(snap.cur.y, 3)}, ${fmt(radToDeg(snap.cur.theta), 1)}°` : "—"} />
            </ReadoutGrid>
          </div>
        </Panel>

        <Panel title="Lệnh đang gửi" description="Động học ngược PHY-2 cho cmd_vel của chu kỳ gần nhất.">
          <div className="flex flex-col gap-4">
            <ReadoutGrid cols={4}>
              {WHEEL_NAMES.map((name, i) => (
                <Readout key={name} label={`Bánh ${name}`} value={fmt(wheels?.[i], 2)} unit="rad/s" />
              ))}
            </ReadoutGrid>
            <ReadoutGrid cols={3}>
              <Readout label="vx" value={fmt(cmd?.vx, 3)} unit="m/s" />
              <Readout label="vy" value={fmt(cmd?.vy, 3)} unit="m/s" />
              <Readout label="wz" value={fmt(cmd?.wz, 3)} unit="rad/s" />
            </ReadoutGrid>
          </div>
        </Panel>
      </div>
    </div>
  );
}
