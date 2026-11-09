"use client";

// FR-04: động học thuận. Nhập tốc độ 4 bánh (A, B, C, D) và thời gian chạy; vận tốc dài và quãng
// đường tính toán đổi ngay theo từng ký tự gõ. Quãng đường thực tế đo từ odometry trong lúc chạy.
// Nút Chạy chỉ gửi cmd_vel (vx, vy, wz) đã tính, qua startRun của store (FR-03).
// Số liệu tần số cao nằm ngoài React state (NFR-03): MotionMeter cập nhật theo từng state.

import { Play, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  DEFAULT_DURATION_S,
  MotionMeter,
  computeChain,
  createWheelDriver,
  describeRunEnd,
  parsePositive,
  parseWheelsLive,
  plannedMotion,
  runBlockReason,
} from "@/robot/forward";
import type { Motion, WheelDriver } from "@/robot/forward";
import { LEVER, SPEED_SUM_LIMIT } from "@/robot/mecanum";
import {
  cancelRun,
  getTelemetry,
  startRun,
  subscribeTelemetry,
  useShell,
} from "@/robot/store";

const RAD_TO_DEG = 180 / Math.PI;
const WHEEL_NAMES = ["A", "B", "C", "D"] as const;

export default function ForwardPage() {
  const shell = useShell();
  const data = dataStateOf(shell);
  const dim = data !== "live";

  const [wheelText, setWheelText] = useState<[string, string, string, string]>(["", "", "", ""]);
  const [durationText, setDurationText] = useState(String(DEFAULT_DURATION_S));
  const [startFailed, setStartFailed] = useState(false);
  // Quãng đường tính toán của lần chạy gần nhất (chốt lúc bấm Chạy) để so với thực tế.
  const [runPlan, setRunPlan] = useState<Motion | null>(null);

  // Tính lại ngay ở mỗi lần render, tức mỗi ký tự gõ: ô trống tính là 0, ô sai thì chưa tính.
  const wheels = useMemo(() => parseWheelsLive(wheelText), [wheelText]);
  const duration = parsePositive(durationText);
  const chain = useMemo(() => (wheels === null ? null : computeChain(wheels, null)), [wheels]);
  const planned = useMemo(
    () => (chain === null || duration === null ? null : plannedMotion(chain.body, duration)),
    [chain, duration],
  );
  const speed = chain === null ? null : Math.hypot(chain.body.vx, chain.body.vy);

  // Đo quãng đường thực tế từ odometry: cộng dồn theo từng state, chỉ trong lúc chạy.
  const meter = useRef(new MotionMeter());
  useEffect(
    () =>
      subscribeTelemetry(() => {
        meter.current.update(getTelemetry()?.pose ?? null);
      }),
    [],
  );
  const actual = usePolled(useCallback(() => meter.current.get(), []), 100);
  const measured = usePolled(useCallback(() => meter.current.active || meter.current.get().distance > 0, []), 100);

  const driver = useRef<WheelDriver | null>(null);
  const remaining = usePolled(
    useCallback(
      () => (driver.current === null ? null : { left: driver.current.remaining(), total: driver.current.durationS }),
      [],
    ),
    100,
  );
  const running = shell.source === "forward";
  const end = describeRunEnd(shell.lastRunEnd);

  // Hết lần chạy (xong hoặc bị hủy) thì chốt số đo.
  useEffect(() => {
    if (!running) meter.current.stop();
  }, [running]);

  // Rời trang thì hủy lần chạy của trang này (cancelRun không làm gì nếu đã xong).
  useEffect(
    () => () => {
      meter.current.stop();
      if (driver.current !== null) cancelRun();
    },
    [],
  );

  const block = runBlockReason({
    open: shell.conn === "open",
    hasState: shell.hasState,
    stale: shell.stale,
    robotLink: shell.robotLink,
    armed: shell.armed,
    isDriver: shell.role === "driver",
    wheelsValid: wheels !== null,
    durationValid: duration !== null,
  });

  const onRun = () => {
    if (wheels === null || duration === null || planned === null) return;
    const d = createWheelDriver(wheels, duration);
    driver.current = d;
    meter.current.start(getTelemetry()?.pose ?? null);
    setRunPlan(planned);
    const ok = startRun(d, "forward");
    if (!ok) meter.current.stop();
    setStartFailed(!ok);
  };

  const setWheel = (i: number, text: string) => {
    setWheelText((prev) => {
      const next: [string, string, string, string] = [...prev];
      next[i] = text;
      return next;
    });
  };

  const invalid = (text: string) => text.trim() !== "" && parseWheelsLive([text, "0", "0", "0"]) === null;
  const deviation =
    actual !== null && runPlan !== null && measured ? actual.distance - runPlan.distance : null;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Động học thuận</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Nhập tốc độ bốn bánh để xem vận tốc dài và quãng đường sẽ đi được, rồi chạy và so với quãng đường thực tế.
        </p>
      </div>

      <DataLostAlert state={data} />

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <Panel title="Đầu vào" description="Tốc độ bốn bánh (rad/s), dương là quay tiến. Ô trống tính là 0.">
            <div className="grid grid-cols-2 gap-3">
              {WHEEL_NAMES.map((name, i) => (
                <div key={name} className="flex flex-col gap-1.5">
                  <Label htmlFor={`w-${name}`} className="justify-between">
                    <span>{name}</span>
                    <span className="text-xs font-normal text-muted-foreground">rad/s</span>
                  </Label>
                  <Input
                    id={`w-${name}`}
                    inputMode="decimal"
                    autoComplete="off"
                    placeholder="0"
                    value={wheelText[i]}
                    aria-invalid={invalid(wheelText[i])}
                    onChange={(e) => setWheel(i, e.target.value)}
                    className="font-mono tabular-nums"
                  />
                </div>
              ))}
              <div className="col-span-2 flex flex-col gap-1.5">
                <Label htmlFor="duration" className="justify-between">
                  <span>Thời gian chạy</span>
                  <span className="text-xs font-normal text-muted-foreground">giây</span>
                </Label>
                <Input
                  id="duration"
                  inputMode="decimal"
                  autoComplete="off"
                  value={durationText}
                  aria-invalid={duration === null}
                  onChange={(e) => setDurationText(e.target.value)}
                  className="font-mono tabular-nums"
                />
              </div>
            </div>
          </Panel>

          <Panel
            title="Chạy"
            description="Gửi vận tốc đã tính, giữ nguyên tới hết giờ rồi gửi 0."
            action={
              running ? (
                <StatusBadge tone="ok">Đang chạy</StatusBadge>
              ) : end ? (
                <StatusBadge tone={end.tone}>{end.tone === "ok" ? "Xong" : "Đã hủy"}</StatusBadge>
              ) : (
                <StatusBadge tone="idle">Chưa chạy</StatusBadge>
              )
            }
          >
            <div className="flex flex-wrap gap-2">
              <Button type="button" disabled={block !== null || running} onClick={onRun}>
                <Play data-icon="inline-start" />
                Chạy
              </Button>
              <p className="self-center text-sm text-muted-foreground">
                Bấm <kbd className="rounded border bg-muted px-1.5 py-0.5 font-mono text-xs">Space</kbd> để dừng khẩn (xe dừng và disarm).
              </p>
            </div>
            {block !== null && !running ? (
              <p className="mt-2 text-sm text-muted-foreground">Chưa chạy được: {block}</p>
            ) : null}
            {startFailed && !running && block === null ? (
              <p className="mt-2 text-sm text-amber-700 dark:text-amber-400">
                Không bắt đầu được (đang giữ phím di chuyển?). Thả phím rồi thử lại.
              </p>
            ) : null}
            <ReadoutGrid cols={2} className="mt-3">
              <Readout
                label="Còn lại"
                value={running && remaining !== null ? fmt(remaining.left, 1) : "—"}
                unit="s"
              />
              <Readout
                label="Tổng thời gian"
                value={running && remaining !== null ? fmt(remaining.total, 1) : fmt(duration, 1)}
                unit="s"
              />
            </ReadoutGrid>
            {end && !running ? (
              <p
                className={
                  end.tone === "ok"
                    ? "mt-2 text-sm text-emerald-700 dark:text-emerald-400"
                    : "mt-2 text-sm text-amber-700 dark:text-amber-400"
                }
              >
                {end.text}
              </p>
            ) : null}
            <p className="mt-2 text-xs text-muted-foreground">
              Lần chạy dùng số nhập tại lúc bấm. Bấm phím di chuyển, disarm, mất dữ liệu hoặc mất kết nối sẽ hủy và gửi lệnh 0.
            </p>
          </Panel>
        </div>

        <div className="flex flex-col gap-4 lg:col-span-3">
          {chain?.exceeds ? (
            <Alert className="text-amber-700 dark:text-amber-400">
              <TriangleAlert />
              <AlertTitle>Tổng tốc độ vượt {SPEED_SUM_LIMIT} m/s</AlertTitle>
              <AlertDescription>
                |vx| + |vy| + {fmt(LEVER, 3)}·|wz| ={" "}
                {fmt(Math.abs(chain.body.vx) + Math.abs(chain.body.vy) + LEVER * Math.abs(chain.body.wz), 3)} m/s.
                Chỉ cảnh báo, không chặn lệnh.
              </AlertDescription>
            </Alert>
          ) : null}

          <Panel title="Vận tốc dài" description="Tính lại ngay khi gõ. Đây cũng là lệnh sẽ gửi khi bấm Chạy.">
            <ReadoutGrid cols={4}>
              <Readout label="vx (tiến)" value={fmt(chain?.body.vx, 4)} unit="m/s" />
              <Readout label="vy (ngang trái)" value={fmt(chain?.body.vy, 4)} unit="m/s" />
              <Readout label="Tốc độ |v|" value={fmt(speed, 4)} unit="m/s" />
              <Readout label="Tốc độ xoay wz" value={fmt(chain?.body.wz, 4)} unit="rad/s" />
            </ReadoutGrid>
            {chain === null ? (
              <p className="mt-2 text-xs text-muted-foreground">Có ô nhập chưa phải số hợp lệ nên chưa tính.</p>
            ) : chain.residualNonZero ? (
              <div className="mt-3">
                <StatusBadge tone="warn">Bốn bánh không nhất quán: các bánh đánh nhau, xe sẽ trượt bánh</StatusBadge>
              </div>
            ) : null}
          </Panel>

          <Panel
            title="Quãng đường"
            description="Tính toán = vận tốc × thời gian chạy. Thực tế = đo từ odometry của robot trong lúc chạy."
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <section>
                <h3 className="text-sm font-medium">Tính toán</h3>
                <ReadoutGrid cols={2} className="mt-2">
                  <Readout label="Quãng đường" value={fmt(planned?.distance, 3)} unit="m" />
                  <Readout label="Góc xoay" value={fmt(planned === null ? null : planned.turn * RAD_TO_DEG, 1)} unit="°" />
                </ReadoutGrid>
              </section>
              <section>
                <h3 className="flex items-center gap-2 text-sm font-medium">
                  Thực tế
                  {running ? <StatusBadge tone="ok">đang đo</StatusBadge> : null}
                </h3>
                <ReadoutGrid cols={2} className="mt-2">
                  <Readout
                    label="Quãng đường"
                    value={measured ? fmt(actual?.distance, 3) : "—"}
                    unit="m"
                    dim={dim && !running}
                  />
                  <Readout
                    label="Góc xoay"
                    value={measured && actual ? fmt(actual.turn * RAD_TO_DEG, 1) : "—"}
                    unit="°"
                    dim={dim && !running}
                  />
                </ReadoutGrid>
              </section>
            </div>
            {deviation !== null ? (
              <p className="mt-3 text-sm text-muted-foreground">
                So với lần chạy đã bấm (tính toán {fmt(runPlan?.distance, 3)} m): lệch{" "}
                <span className="font-medium tabular-nums text-foreground">
                  {deviation >= 0 ? "+" : ""}
                  {fmt(deviation, 3)} m
                </span>
                {runPlan !== null && runPlan.distance > 1e-6
                  ? ` (${deviation >= 0 ? "+" : ""}${fmt((deviation / runPlan.distance) * 100, 1)}%)`
                  : ""}
                .
              </p>
            ) : null}
            <p className="mt-2 text-xs text-muted-foreground">
              Quãng đường thực tế là chiều dài đường đi cộng dồn từ odometry, nên chính xác bằng độ chính xác của
              odometry (cộng dồn từ vận tốc đo), không phải số đo bằng thước.
            </p>
          </Panel>
        </div>
      </div>
    </div>
  );
}
