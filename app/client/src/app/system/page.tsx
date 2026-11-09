"use client";

// FR-11: RTT, độ trễ vòng lệnh (đo ở client), sức khỏe STM32 / LiDAR / writer, dữ liệu sạc,
// tuổi của state gần nhất. Đọc store theo chu kỳ 4 Hz, không render theo từng state.

import { useCallback } from "react";

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
import type { LooseRecord } from "@/robot/protocol";
import { getLatencyStats, getTelemetry, getTelemetryAt, useShell } from "@/robot/store";
import { parseDeviceHealth } from "@/robot/telemetry";

/** Mục tiêu NFR-02: p95 độ trễ vòng lệnh. */
const LATENCY_P95_TARGET_MS = 150;
const POLL_MS = 250;

function DevicePanel({
  title,
  raw,
  kind,
  dim,
}: {
  title: string;
  raw: unknown;
  kind: "device" | "writer";
  dim: boolean;
}) {
  const h = parseDeviceHealth(raw);
  const tone: Tone = h.ok === null ? "idle" : h.ok ? "ok" : "bad";
  return (
    <Panel
      title={title}
      action={
        <StatusBadge tone={tone}>
          {h.ok === null ? "Không rõ" : h.ok ? "Tốt" : "Lỗi"}
        </StatusBadge>
      }
    >
      <ReadoutGrid cols={2}>
        <Readout label="Trạng thái" value={h.state ?? "—"} text dim={dim} />
        <Readout
          label={kind === "writer" ? "Số lỗi ghi" : "Số lần khởi động lại"}
          value={h.errors === null ? "—" : String(h.errors)}
          tone={h.errors !== null && h.errors > 0 ? "warn" : "idle"}
          dim={dim}
        />
        {kind === "writer" ? (
          <Readout
            label="Lệnh bị từ chối"
            value={h.rejected === null ? "—" : String(h.rejected)}
            dim={dim}
          />
        ) : null}
      </ReadoutGrid>
      <div className="mt-3 min-w-0 text-xs">
        <span className="text-muted-foreground">Lỗi gần nhất: </span>
        <span className="font-mono break-words">{h.lastError ?? "Không có"}</span>
      </div>
    </Panel>
  );
}

function yesNo(value: unknown): string {
  return typeof value === "boolean" ? (value ? "Có" : "Không") : "—";
}

export default function SystemPage() {
  const shell = useShell();
  const state = usePolled(getTelemetry, POLL_MS);
  const latency = usePolled(getLatencyStats, POLL_MS);
  const ageMs = usePolled(
    useCallback(() => performance.now() - getTelemetryAt(), []),
    POLL_MS,
  );
  const data = dataStateOf(shell);
  const dim = data !== "live";
  const health = state?.health as LooseRecord | null | undefined;
  const charge = state?.charge as LooseRecord | null | undefined;
  const p95 = latency?.p95 ?? null;
  const ageText =
    state === null || ageMs === null || !Number.isFinite(ageMs) ? "—" : fmt(ageMs / 1000, 2);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Hệ thống</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Độ trễ liên kết, độ trễ vòng lệnh và sức khỏe thiết bị trên robot.
        </p>
      </div>

      <DataLostAlert state={data} />

      <div className="grid gap-4 md:grid-cols-3">
        <Panel title="Liên kết robot" description="Đo giữa app server và robot">
          <ReadoutGrid cols={2}>
            <Readout label="RTT" value={fmt(state?.link.rtt_ms, 1)} unit="ms" dim={dim} />
            <Readout
              label="Link"
              text
              value={
                data === "offline" ? (
                  "—"
                ) : (
                  <StatusBadge tone={data === "stale" ? "bad" : state?.link.robot ? "ok" : "bad"}>
                    {data === "stale" ? "Không rõ" : state?.link.robot ? "Đã nối" : "Mất link"}
                  </StatusBadge>
                )
              }
            />
          </ReadoutGrid>
        </Panel>

        <Panel
          title="Độ trễ vòng lệnh"
          description={`cmd_vel gửi đi đến khi last_cmd_seq đạt seq. Mục tiêu p95 ≤ ${LATENCY_P95_TARGET_MS} ms`}
        >
          <ReadoutGrid cols={3}>
            <Readout label="Gần nhất" value={fmt(latency?.last, 0)} unit="ms" />
            <Readout
              label="p95"
              value={fmt(p95, 0)}
              unit="ms"
              tone={p95 === null ? "idle" : p95 <= LATENCY_P95_TARGET_MS ? "ok" : "warn"}
            />
            <Readout label="Số mẫu" value={String(latency?.count ?? 0)} />
          </ReadoutGrid>
          <p className="mt-2 text-xs text-muted-foreground">
            Chỉ có mẫu khi đang gửi lệnh (giữ phím hoặc chạy tự động). Độ phân giải theo nhịp state (50 ms).
          </p>
        </Panel>

        <Panel title="Dữ liệu trạng thái" description="Từ app server tới trình duyệt">
          <ReadoutGrid cols={2}>
            <Readout
              label="Từ state cuối"
              value={ageText}
              unit="s"
              tone={data === "stale" ? "bad" : "idle"}
            />
            <Readout
              label="Kết nối"
              text
              value={
                <StatusBadge tone={shell.conn === "open" ? "ok" : shell.conn === "connecting" ? "warn" : "bad"}>
                  {shell.conn === "open" ? "Mở" : shell.conn === "connecting" ? "Đang nối" : "Đóng"}
                </StatusBadge>
              }
            />
          </ReadoutGrid>
        </Panel>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <DevicePanel title="STM32" raw={health?.stm} kind="device" dim={dim} />
        <DevicePanel title="LiDAR" raw={health?.lidar} kind="device" dim={dim} />
        <DevicePanel title="Writer (ghi lệnh xuống STM32)" raw={health?.writer} kind="writer" dim={dim} />
      </div>

      <Panel title="Sạc" description="Dữ liệu từ khung phụ của STM32 (giả định A-4, chưa kiểm chứng trên robot thật)">
        {charge ? (
          <ReadoutGrid cols={4}>
            <Readout
              label="Dòng sạc"
              value={fmt(typeof charge.current_a === "number" ? charge.current_a : null, 3)}
              unit="A"
              dim={dim}
            />
            <Readout label="Đang sạc" value={yesNo(charge.charging)} text dim={dim} />
            <Readout
              label="Red"
              value={typeof charge.red === "number" ? String(charge.red) : yesNo(charge.red)}
              text
              dim={dim}
            />
            <Readout
              label="Set state"
              value={charge.set_state === undefined || charge.set_state === null ? "—" : String(charge.set_state)}
              text
              dim={dim}
            />
          </ReadoutGrid>
        ) : (
          <p className="text-sm text-muted-foreground">Chưa có dữ liệu sạc.</p>
        )}
      </Panel>
    </div>
  );
}
