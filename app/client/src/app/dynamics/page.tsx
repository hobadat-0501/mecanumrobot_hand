"use client";

// FR-07, PHY-5: động lực học realtime. Mỗi state đi qua DynamicsEstimator đúng một lần (dynamics.ts,
// ngoài React); trang chỉ đọc kết quả theo chu kỳ 10 Hz và vẽ canvas bằng ref (NFR-03).

import { TriangleAlert } from "lucide-react";
import { useEffect } from "react";

import { ForceHistoryChart, WheelTorqueChart } from "@/components/robot/charts";
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { OVER_HOLD_MS, anyOver, dynamicsFeed, startDynamicsFeed } from "@/robot/dynamics";
import { TAU_RATED } from "@/robot/mecanum";
import { useShell } from "@/robot/store";

const WHEEL_NAMES = ["A", "B", "C", "D"];

const readFeed = () => ({
  result: dynamicsFeed.result,
  wheels: dynamicsFeed.wheels,
  lastOver: dynamicsFeed.lastOver,
  now: performance.now(),
});

export default function Page() {
  useEffect(() => startDynamicsFeed(), []);
  const shell = useShell();
  const data = dataStateOf(shell);
  const dim = data !== "live";
  const snap = usePolled(readFeed, 100);
  const r = snap?.result ?? null;
  const wheels = snap?.wheels ?? null;
  const held = snap?.lastOver && snap.now - snap.lastOver.at < OVER_HOLD_MS ? snap.lastOver : null;
  const overNow = r !== null && anyOver(r);
  const overNames = WHEEL_NAMES.filter((_, i) => held?.wheels[i]);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Động lực học</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Lực và mô-men từng bánh ước lượng từ vận tốc đo, lọc thông thấp τ = 0.1 s.
        </p>
      </div>

      <DataLostAlert state={data} />

      {held ? (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>{overNow ? "Vượt mô-men định mức" : "Vừa vượt mô-men định mức"}</AlertTitle>
          <AlertDescription>
            Bánh {overNames.join(", ")} vượt {TAU_RATED} N·m (đỉnh {fmt(held.pct, 0)}% định mức).
            {dim ? " Giá trị đang cũ." : ""}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Lực và mô-men thân" description="Fx = m·a_x, Fy = m·a_y, Mz = I_z·ẇz">
          <ReadoutGrid cols={3}>
            <Readout label="Fx" value={fmt(r?.Fx, 2)} unit="N" dim={dim} />
            <Readout label="Fy" value={fmt(r?.Fy, 2)} unit="N" dim={dim} />
            <Readout label="Mz" value={fmt(r?.Mz, 2)} unit="N·m" dim={dim} />
            <Readout label="a_x" value={fmt(r?.ax, 3)} unit="m/s²" dim={dim} />
            <Readout label="a_y" value={fmt(r?.ay, 3)} unit="m/s²" dim={dim} />
            <Readout label="ẇz" value={fmt(r?.wzDot, 3)} unit="rad/s²" dim={dim} />
          </ReadoutGrid>
        </Panel>

        <Panel
          title="Mô-men từng bánh"
          description={`Định mức ${TAU_RATED} N·m mỗi bánh`}
          action={
            r ? (
              <StatusBadge tone={anyOver(r) ? "bad" : "ok"}>
                {anyOver(r) ? "Vượt định mức" : "Trong định mức"}
              </StatusBadge>
            ) : null
          }
        >
          <div className={cn("h-48 overflow-hidden rounded-md border bg-background", dim && "opacity-45")}>
            <WheelTorqueChart />
          </div>
        </Panel>
      </div>

      <Panel title="Chi tiết từng bánh" description="F_d,i = (Fx + ε·Fy + s·Mz/lever)/4; τ_i = r·(F_d,i + F_c·sign ω_i)">
        <div className={cn("transition-opacity", dim && "opacity-45")}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Bánh</TableHead>
                <TableHead className="text-right">ω (rad/s)</TableHead>
                <TableHead className="text-right">F_d (N)</TableHead>
                <TableHead className="text-right">τ (N·m)</TableHead>
                <TableHead className="text-right">% định mức</TableHead>
                <TableHead className="hidden text-right sm:table-cell">Trạng thái</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {WHEEL_NAMES.map((name, i) => (
                <TableRow key={name}>
                  <TableCell className="font-medium">{name}</TableCell>
                  <TableCell className="text-right font-mono tabular-nums">{fmt(wheels?.[i], 2)}</TableCell>
                  <TableCell className="text-right font-mono tabular-nums">{fmt(r?.Fd[i], 3)}</TableCell>
                  <TableCell className="text-right font-mono tabular-nums">{fmt(r?.tau[i], 4)}</TableCell>
                  <TableCell className={cn("text-right font-mono tabular-nums", r?.over[i] && "font-semibold text-destructive")}>{fmt(r?.tauPct[i], 1)}</TableCell>
                  <TableCell className="hidden text-right sm:table-cell">
                    {r ? (
                      <StatusBadge tone={r.over[i] ? "bad" : "ok"}>{r.over[i] ? "Vượt" : "Đạt"}</StatusBadge>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Panel>

      <Panel title="Lịch sử Fx, Fy, Mz" description="Khoảng 20 s gần nhất">
        <div className={cn("h-56 overflow-hidden rounded-md border bg-background", dim && "opacity-45")}>
          <ForceHistoryChart />
        </div>
      </Panel>
    </div>
  );
}
