"use client";

// FR-04: động học thuận. Nhập 4 tốc độ bánh và thời gian chạy; chuỗi tính tính lại ngay khi đổi
// số nhập. Số liệu từ store (θ, ω̇) đọc theo chu kỳ bằng usePolled, không nằm trong React state (NFR-03).
// Nút Chạy chỉ gửi cmd_vel đã tính, qua startRun của store (FR-03).

import { OctagonX, Play, TriangleAlert } from "lucide-react";
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
  computeChain,
  createWheelDriver,
  describeRunEnd,
  parsePositive,
  parseWheels,
  runBlockReason,
} from "@/robot/forward";
import type { WheelDriver } from "@/robot/forward";
import { DynamicsEstimator, FILTER_TAU, LEVER, R, SPEED_SUM_LIMIT } from "@/robot/mecanum";
import {
  cancelRun,
  getTelemetry,
  getTelemetryAt,
  startRun,
  subscribeTelemetry,
  useShell,
} from "@/robot/store";

const RAD_TO_DEG = 180 / Math.PI;
const WHEEL_NAMES = ["A", "B", "C", "D"] as const;
const WHEEL_SIGNS = ["ε +, s −", "ε −, s −", "ε +, s +", "ε −, s +"] as const;

/**
 * ω̇ = đạo hàm của wz đo được (vel.wz trong state), lọc thông thấp bậc 1 với hằng số
 * thời gian FILTER_TAU (PHY-4, PHY-5). Cập nhật theo từng state, giữ ngoài React state.
 */
function useWzDot(): () => number | null {
  const est = useRef(new DynamicsEstimator());
  const value = useRef<number | null>(null);
  const lastAt = useRef<number | null>(null);
  useEffect(() => {
    const e = est.current;
    const off = subscribeTelemetry(() => {
      const s = getTelemetry();
      const at = getTelemetryAt();
      if (s === null || s.vel === null || !Number.isFinite(s.vel.wz)) {
        e.reset();
        value.current = null;
        lastAt.current = null;
        return;
      }
      if (lastAt.current === at) return;
      const dt = lastAt.current === null ? 0 : (at - lastAt.current) / 1000;
      lastAt.current = at;
      value.current = e.update(s.vel, [0, 0, 0, 0], dt).wzDot;
    });
    return off;
  }, []);
  return useCallback(() => value.current, []);
}

function Step({ index, title, children }: { index: number; title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border bg-background p-3">
      <h3 className="flex items-center gap-2 text-sm font-medium">
        <span className="grid size-5 place-items-center rounded-full bg-muted text-xs tabular-nums">
          {index}
        </span>
        {title}
      </h3>
      <div className="mt-2">{children}</div>
    </section>
  );
}

export default function ForwardPage() {
  const shell = useShell();
  const state = usePolled(getTelemetry, 100);
  const wzDot = usePolled(useWzDot(), 100);
  const data = dataStateOf(shell);
  const dim = data !== "live";

  const [wheelText, setWheelText] = useState<[string, string, string, string]>(["", "", "", ""]);
  const [durationText, setDurationText] = useState(String(DEFAULT_DURATION_S));
  const [startFailed, setStartFailed] = useState(false);

  const wheels = useMemo(() => parseWheels(wheelText), [wheelText]);
  const duration = parsePositive(durationText);
  const theta = state?.pose.theta ?? null;
  const chain = useMemo(() => (wheels === null ? null : computeChain(wheels, theta)), [wheels, theta]);

  const driver = useRef<WheelDriver | null>(null);
  const remaining = usePolled(
    useCallback(() => driver.current === null ? null : { left: driver.current.remaining(), total: driver.current.durationS }, []),
    100,
  );
  const running = shell.source === "forward";
  const end = describeRunEnd(shell.lastRunEnd);

  // Rời trang thì hủy lần chạy của trang này (cancelRun không làm gì nếu đã xong).
  useEffect(
    () => () => {
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
    if (wheels === null || duration === null) return;
    const d = createWheelDriver(wheels, duration);
    driver.current = d;
    setStartFailed(!startRun(d, "forward"));
  };

  const setWheel = (i: number, text: string) => {
    setWheelText((prev) => {
      const next: [string, string, string, string] = [...prev];
      next[i] = text;
      return next;
    });
  };

  const invalid = (text: string) => text.trim() !== "" && parseWheels([text, "0", "0", "0"]) === null;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Động học thuận</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Nhập tốc độ 4 bánh, xem chuỗi tính tới vận tốc thân và đạo hàm tư thế, rồi chạy trong thời gian giới hạn.
        </p>
      </div>

      <DataLostAlert state={data} />

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <Panel title="Đầu vào" description="Tốc độ bánh (rad/s), dương là quay tiến. Ô trống hoặc sai thì chưa tính.">
            <div className="grid grid-cols-2 gap-3">
              {WHEEL_NAMES.map((name, i) => (
                <div key={name} className="flex flex-col gap-1.5">
                  <Label htmlFor={`w-${name}`} className="justify-between">
                    <span>{`ω_${name}`}</span>
                    <span className="text-xs font-normal text-muted-foreground">{WHEEL_SIGNS[i]}</span>
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
                <Label htmlFor="duration">Thời gian chạy (s)</Label>
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
            description="Gửi cmd_vel (vx, vy, wz) đã tính, giữ nguyên tới hết giờ rồi gửi 0."
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
              <Button type="button" variant="destructive" disabled={!running} onClick={() => cancelRun()}>
                <OctagonX data-icon="inline-start" />
                Dừng
              </Button>
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
                |vx| + |vy| + {fmt(LEVER, 3)}·|wz| = {fmt(Math.abs(chain.body.vx) + Math.abs(chain.body.vy) + LEVER * Math.abs(chain.body.wz), 3)} m/s.
                Chỉ cảnh báo, không chặn lệnh.
              </AlertDescription>
            </Alert>
          ) : null}

          <Panel title="Chuỗi tính" description="Tính lại ngay khi đổi số nhập (PHY-3, PHY-4).">
            <div className="flex flex-col gap-3">
              <Step index={1} title="Tốc độ bánh ω_i">
                <ReadoutGrid cols={4}>
                  {WHEEL_NAMES.map((n, i) => (
                    <Readout
                      key={n}
                      label={`ω_${n}`}
                      value={fmt(wheels?.[i], 3)}
                      unit="rad/s"
                    />
                  ))}
                </ReadoutGrid>
              </Step>
              <Step index={2} title={`Vận tốc dài vành bánh v_i = r·ω_i (r = ${R} m)`}>
                <ReadoutGrid cols={4}>
                  {WHEEL_NAMES.map((n, i) => (
                    <Readout key={n} label={`v_${n}`} value={fmt(chain?.rim[i], 4)} unit="m/s" />
                  ))}
                </ReadoutGrid>
              </Step>
              <Step index={3} title="Vận tốc thân (vx, vy, wz): chính là cmd_vel sẽ gửi">
                <ReadoutGrid cols={3}>
                  <Readout label="vx" value={fmt(chain?.body.vx, 4)} unit="m/s" />
                  <Readout label="vy" value={fmt(chain?.body.vy, 4)} unit="m/s" />
                  <Readout label="wz" value={fmt(chain?.body.wz, 4)} unit="rad/s" />
                </ReadoutGrid>
              </Step>
              <Step index={4} title="Khung thế giới theo θ hiện tại (dx/dt, dy/dt, dθ/dt = wz)">
                <ReadoutGrid cols={4}>
                  <Readout label="θ (đo)" value={fmt(theta === null ? null : theta * RAD_TO_DEG, 1)} unit="°" dim={dim} />
                  <Readout label="dx/dt" value={fmt(chain?.world?.xDot, 4)} unit="m/s" dim={dim} />
                  <Readout label="dy/dt" value={fmt(chain?.world?.yDot, 4)} unit="m/s" dim={dim} />
                  <Readout label="dθ/dt" value={fmt(chain?.world?.thetaDot, 4)} unit="rad/s" />
                </ReadoutGrid>
                {theta === null ? (
                  <p className="mt-2 text-xs text-muted-foreground">Chưa có tư thế từ app server nên chưa đổi sang khung thế giới.</p>
                ) : null}
              </Step>
              <Step index={5} title="Gia tốc góc dω/dt (ω̇) đo được">
                <ReadoutGrid cols={2}>
                  <Readout label="dω/dt (đạo hàm wz đo, đã lọc)" value={fmt(wzDot, 3)} unit="rad/s²" dim={dim} />
                  <Readout label="wz đo" value={fmt(state?.vel?.wz, 3)} unit="rad/s" dim={dim} />
                </ReadoutGrid>
                <p className="mt-2 text-xs text-muted-foreground">
                  dω/dt là đạo hàm theo thời gian của wz đo từ robot, qua bộ lọc thông thấp bậc 1 (τ = {FILTER_TAU} s).
                  Đây là giá trị đo, không phải giá trị tính từ ô nhập.
                </p>
              </Step>
              <Step index={6} title="Thành phần dư e = r/4·(ω_A − ω_B − ω_C + ω_D)">
                <div className="flex flex-wrap items-center gap-4">
                  <Readout
                    label="e"
                    value={fmt(chain?.residual, 5)}
                    unit="m/s"
                    tone={chain === null ? "idle" : chain.residualNonZero ? "warn" : "ok"}
                  />
                  {chain === null ? null : chain.residualNonZero ? (
                    <StatusBadge tone="warn">Khác 0: các bánh đánh nhau, robot sẽ trượt bánh</StatusBadge>
                  ) : (
                    <StatusBadge tone="ok">Bằng 0: bốn bánh nhất quán</StatusBadge>
                  )}
                </div>
              </Step>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
