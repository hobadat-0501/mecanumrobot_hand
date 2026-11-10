"use client";

// FR-01, FR-13, SAF-03, NFR-08: chế độ Cử chỉ (D-09). Trang chỉ bật/tắt chế độ và hiển thị trạng thái;
// lệnh chuyển động của chế độ này đi thẳng trên Jetson, không qua trang này. Space dừng khẩn và tắt chế độ.

import { Hand } from "lucide-react";
import Link from "next/link";

import { Panel, Readout, ReadoutGrid, StatusBadge, dataStateOf, DataLostAlert, usePolled } from "@/components/robot/panels";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { getVideoUrl, setGestureMode, useShell, useTelemetry } from "@/robot/store";

const STATE_LABEL: Record<string, string> = {
  OFF: "Tắt",
  ENROLL: "Đăng ký",
  LOCKED: "Khóa — chờ nhận diện",
  BIND: "Gắn người điều khiển",
  "BIND-BACK": "Gắn lưng",
  GESTURE: "Cử chỉ",
  FOLLOW: "Đi theo",
  HOLD: "Giữ — mất người",
  ESTOP: "Dừng khẩn",
};

export default function GesturePage() {
  const shell = useShell();
  const telemetry = useTelemetry();
  const video = usePolled(getVideoUrl, 500);
  const vision = telemetry?.vision;
  const gate = telemetry?.gesture?.lidar_gate as { blocked?: boolean; min_m?: number | null } | undefined;
  const on = shell.mode === "gesture";
  const canToggle = shell.role === "driver" && shell.armed && shell.robotLink;
  const vstate = vision?.state?.state;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Cử chỉ</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Điều khiển bằng cử chỉ qua camera. Cần arm và quyền lái; lái tay luôn thắng.
        </p>
        <Link href="/gesture/staff" className="mt-1 inline-block text-sm underline">
          Quản lý nhân viên
        </Link>
      </div>
      <DataLostAlert state={dataStateOf(shell)} />

      <div className="grid gap-4 lg:grid-cols-5">
        <Panel
          title="Camera"
          description="Luồng video từ Jetson (đã gắn khung nhận dạng)."
          className="lg:col-span-3"
        >
          <div className="aspect-video w-full overflow-hidden rounded-md border bg-muted">
            {video !== null && vision?.link ? (
              // eslint-disable-next-line @next/next/no-img-element -- luồng MJPEG, next/image không áp dụng
              <img src={video} alt="Luồng camera" className="size-full object-contain" />
            ) : (
              <div className="flex size-full items-center justify-center text-sm text-muted-foreground">
                {vision?.enabled ? "Chưa có video" : "Vision agent chưa được bật"}
              </div>
            )}
          </div>
        </Panel>

        <div className="flex flex-col gap-4 lg:col-span-2">
          <Panel
            title="Chế độ"
            action={<StatusBadge tone={on ? "ok" : "idle"}>{on ? "Đang bật" : "Tắt"}</StatusBadge>}
          >
            <div className="flex flex-col gap-3">
              <Button
                variant={on ? "destructive" : "default"}
                disabled={on ? shell.role !== "driver" : !canToggle}
                onClick={() => setGestureMode(!on)}
              >
                <Hand /> {on ? "Tắt chế độ cử chỉ" : "Bật chế độ cử chỉ"}
              </Button>
              <p className="text-xs text-muted-foreground">
                {canToggle || on
                  ? "Nhấn Space bất cứ lúc nào để dừng khẩn và tắt."
                  : "Cần: là người lái, đã arm, robot đã kết nối."}{" "}
                <Kbd>Space</Kbd>
              </p>
            </div>
          </Panel>

          <Panel
            title="Trạng thái"
            action={
              <StatusBadge tone={vision?.link ? "ok" : "idle"}>
                {vision?.link ? "Vision nối" : "Vision ngắt"}
              </StatusBadge>
            }
          >
            <ReadoutGrid cols={2}>
              <Readout text label="Trạng thái" value={vstate ? (STATE_LABEL[vstate] ?? vstate) : "—"} />
              <Readout text label="Người dùng" value={vision?.state?.user ?? "—"} />
              <Readout text label="Cử chỉ" value={vision?.state?.gesture ?? "—"} />
              <Readout label="FPS" value={vision?.state?.fps ?? "—"} />
              <Readout
                text
                label="Cổng LiDAR"
                value={gate === undefined ? "—" : gate.blocked ? "Chặn" : "Thông"}
                tone={gate?.blocked ? "bad" : "idle"}
              />
              <Readout
                text
                label="Nguồn lệnh"
                value={telemetry?.gesture?.src === "vision" ? "Cử chỉ" : "Tay"}
              />
            </ReadoutGrid>
            {vision?.state?.guide ? (
              <p className="mt-3 text-sm">{vision.state.guide}</p>
            ) : null}
          </Panel>
        </div>
      </div>
    </div>
  );
}
