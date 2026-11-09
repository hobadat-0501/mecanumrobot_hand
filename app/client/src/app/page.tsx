"use client";

// FR-08, FR-12: tổng quan realtime. Số liệu đọc từ store theo chu kỳ 10 Hz (usePolled); quỹ đạo vẽ
// bằng canvas từ vòng đệm ngoài React. Trạng thái tần số thấp lấy từ useShell().

import { RotateCcw } from "lucide-react";

import { TrajectoryChart } from "@/components/robot/charts";
import {
  DataLostAlert,
  Panel,
  Readout,
  ReadoutGrid,
  SOURCE_LABEL,
  StatusBadge,
  dataStateOf,
  fmt,
  usePolled,
} from "@/components/robot/panels";
import { Button } from "@/components/ui/button";
import { getTelemetry, resetOdometry, useShell } from "@/robot/store";

const RAD_TO_DEG = 180 / Math.PI;

function flagStopText(flag: boolean | number | null | undefined): {
  text: string;
  tone: "ok" | "bad" | "idle";
} {
  if (flag === null || flag === undefined) return { text: "—", tone: "idle" };
  return flag ? { text: "Đang dừng", tone: "bad" } : { text: "Không", tone: "ok" };
}

export default function Home() {
  const shell = useShell();
  const state = usePolled(getTelemetry, 100);
  const data = dataStateOf(shell);
  const dim = data !== "live";
  const canReset = shell.conn === "open" && shell.role === "driver";
  const stop = flagStopText(state?.flag_stop);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Tổng quan</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Vận tốc đo, tư thế, lệnh hiện hành và cảm biến, cập nhật theo thời gian thực.
        </p>
      </div>

      <DataLostAlert state={data} />

      <div className="grid gap-4 lg:grid-cols-5">
        <Panel
          title="Quỹ đạo odometry"
          description="Khung odometry (m), x sang phải, y lên trên. Mũi tên chỉ hướng θ."
          className="lg:col-span-3"
          action={
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!canReset}
              onClick={() => resetOdometry()}
              title={canReset ? undefined : "Cần có quyền lái để đặt lại odometry"}
            >
              <RotateCcw data-icon="inline-start" />
              Đặt lại odometry
            </Button>
          }
        >
          <div className="h-72 overflow-hidden rounded-md border bg-background sm:h-96">
            <TrajectoryChart />
          </div>
          {!canReset ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Đặt lại odometry chỉ dành cho người đang giữ quyền lái.
            </p>
          ) : null}
        </Panel>

        <div className="flex flex-col gap-4 lg:col-span-2">
          <Panel title="Vận tốc đo" description="Đơn vị web, thân robot">
            <ReadoutGrid>
              <Readout label="vx" value={fmt(state?.vel?.vx, 3)} unit="m/s" dim={dim} />
              <Readout label="vy" value={fmt(state?.vel?.vy, 3)} unit="m/s" dim={dim} />
              <Readout label="wz" value={fmt(state?.vel?.wz, 3)} unit="rad/s" dim={dim} />
            </ReadoutGrid>
          </Panel>

          <Panel title="Tư thế" description="Odometry trên app server">
            <ReadoutGrid>
              <Readout label="x" value={fmt(state?.pose.x, 3)} unit="m" dim={dim} />
              <Readout label="y" value={fmt(state?.pose.y, 3)} unit="m" dim={dim} />
              <Readout
                label="θ"
                value={fmt(state ? state.pose.theta * RAD_TO_DEG : null, 1)}
                unit="°"
                dim={dim}
              />
            </ReadoutGrid>
          </Panel>

          <Panel
            title="Lệnh hiện hành"
            description="cmd_vel đang áp dụng ở app server"
            action={
              <StatusBadge tone={shell.source === "idle" ? "idle" : "ok"}>
                {SOURCE_LABEL[shell.source]}
              </StatusBadge>
            }
          >
            <ReadoutGrid>
              <Readout label="vx" value={fmt(state?.cmd.vx, 3)} unit="m/s" dim={dim} />
              <Readout label="vy" value={fmt(state?.cmd.vy, 3)} unit="m/s" dim={dim} />
              <Readout label="wz" value={fmt(state?.cmd.wz, 3)} unit="rad/s" dim={dim} />
            </ReadoutGrid>
            <p className="mt-2 text-xs text-muted-foreground">
              Nguồn lệnh tính ở máy này (bàn phím hoặc lần chạy tự động).
            </p>
          </Panel>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Panel title="IMU và nguồn">
          <ReadoutGrid cols={3}>
            <Readout label="ax" value={fmt(state?.imu?.ax, 2)} unit="m/s²" dim={dim} />
            <Readout label="ay" value={fmt(state?.imu?.ay, 2)} unit="m/s²" dim={dim} />
            <Readout label="az" value={fmt(state?.imu?.az, 2)} unit="m/s²" dim={dim} />
            <Readout label="gx" value={fmt(state?.imu?.gx, 3)} unit="rad/s" dim={dim} />
            <Readout label="gy" value={fmt(state?.imu?.gy, 3)} unit="rad/s" dim={dim} />
            <Readout label="gz" value={fmt(state?.imu?.gz, 3)} unit="rad/s" dim={dim} />
            <Readout label="Điện áp" value={fmt(state?.voltage, 2)} unit="V" dim={dim} />
            <Readout label="Cờ dừng" value={stop.text} tone={stop.tone} text dim={dim} />
          </ReadoutGrid>
        </Panel>

        <Panel title="Liên kết và phiên">
          <ReadoutGrid cols={2}>
            <Readout
              label="Link robot"
              text
              dim={dim}
              value={
                data === "offline" ? (
                  "—"
                ) : (
                  <StatusBadge tone={data === "stale" ? "bad" : shell.robotLink ? "ok" : "bad"}>
                    {data === "stale" ? "Không rõ" : shell.robotLink ? "Đã nối" : "Mất link"}
                  </StatusBadge>
                )
              }
            />
            <Readout label="RTT robot" value={fmt(state?.link.rtt_ms, 1)} unit="ms" dim={dim} />
            <Readout
              label="Phiên"
              text
              value={
                <StatusBadge tone={shell.role === "driver" ? "ok" : "idle"}>
                  {shell.role === "driver" ? "Quyền lái" : "Chỉ xem"}
                </StatusBadge>
              }
            />
            <Readout
              label="Arm"
              text
              value={
                <StatusBadge tone={shell.armed ? "warn" : "idle"}>
                  {shell.armed ? "Đã arm" : "Disarm"}
                </StatusBadge>
              }
            />
          </ReadoutGrid>
        </Panel>
      </div>
    </div>
  );
}
