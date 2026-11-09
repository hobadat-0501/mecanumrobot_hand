"use client";

// FR-10: scan LiDAR dạng polar, 5 đến 10 Hz. Scan nằm ngoài React state (store); canvas tự vẽ lại
// theo khung hình. Số liệu bên cạnh đọc theo chu kỳ 100 ms (usePolled), không render theo từng scan.

import { TriangleAlert } from "lucide-react";

import { PolarScanChart } from "@/components/robot/charts";
import { Panel, Readout, ReadoutGrid, StatusBadge, fmt, usePolled } from "@/components/robot/panels";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { getScanSummary, useShell } from "@/robot/store";

export default function LidarPage() {
  const shell = useShell();
  const summary = usePolled(getScanSummary, 100);
  const status = shell.conn !== "open" ? "none" : (summary?.status ?? "none");
  const dim = status !== "live";
  const nearestM = summary?.nearestMm != null ? summary.nearestMm / 1000 : null;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">LiDAR</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Quét 360 độ quanh robot, vẽ theo thời gian thực.
        </p>
      </div>

      {status !== "live" ? (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>{status === "stale" ? "Mất dữ liệu" : "Chưa có dữ liệu"}</AlertTitle>
          <AlertDescription>
            {status === "stale"
              ? "Quá 1 giây không nhận được scan mới. Hình vẽ là scan cuối cùng, đã mờ đi."
              : "Chưa kết nối tới máy điều khiển hoặc chưa nhận scan LiDAR nào."}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-5">
        <Panel
          title="Scan polar"
          description="Phía trước robot ở trên; góc tăng ngược chiều kim đồng hồ (trái là 90°). Chấm là điểm đo, đường đứt là điểm gần nhất."
          className="lg:col-span-3"
        >
          <div className="mx-auto aspect-square w-full max-w-xl overflow-hidden rounded-md border bg-background">
            <PolarScanChart />
          </div>
        </Panel>

        <div className="flex flex-col gap-4 lg:col-span-2">
          <Panel
            title="Số liệu scan"
            action={
              <StatusBadge tone={status === "live" ? "ok" : status === "stale" ? "bad" : "idle"}>
                {status === "live" ? "Đang nhận" : status === "stale" ? "Mất dữ liệu" : "Chưa có"}
              </StatusBadge>
            }
          >
            <ReadoutGrid cols={2}>
              <Readout label="Tốc độ scan" value={fmt(summary?.rateHz, 1)} unit="Hz" dim={dim} />
              <Readout label="Số điểm" value={summary?.count ?? "—"} unit="/ 360" dim={dim} />
              <Readout label="Vật cản gần nhất" value={fmt(nearestM, 2)} unit="m" dim={dim} />
              <Readout
                label="Góc vật cản gần nhất"
                value={fmt(summary?.nearestDeg, 0)}
                unit="°"
                dim={dim}
              />
              <Readout
                label="Tuổi scan"
                value={summary?.ageMs != null ? fmt(summary.ageMs / 1000, 1) : "—"}
                unit="s"
                dim={dim}
              />
            </ReadoutGrid>
            <p className="mt-3 text-xs text-muted-foreground">
              Góc 0° là phía trước, 90° là bên trái. Ô không có điểm không được đếm.
            </p>
          </Panel>
        </div>
      </div>
    </div>
  );
}
