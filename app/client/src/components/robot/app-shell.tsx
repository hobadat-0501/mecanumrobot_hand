"use client";

// FR-01, FR-09: khung ứng dụng nằm ở root layout nên tồn tại xuyên suốt khi chuyển trang.
// Gồm điều hướng (next/link, chuyển trang phía client không làm rớt WebSocket),
// thanh trạng thái toàn cục (kết nối, arm, dừng khẩn, nguồn lệnh) và ô nhập mã điều khiển.

import {
  Activity,
  Cpu,
  KeyRound,
  LayoutDashboard,
  Move,
  OctagonX,
  Power,
  Radar,
  Waypoints,
  Wifi,
  WifiOff,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useState } from "react";
import type { ComponentType, FormEvent, ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Kbd, KbdGroup } from "@/components/ui/kbd";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { parseSpeed } from "@/robot/control";
import type { Source } from "@/robot/control";
import {
  emergencyStop,
  setArmed,
  setOperatorCode,
  setSpeed,
  startStore,
  useShell,
} from "@/robot/store";
import type { ShellSnapshot } from "@/robot/store";

interface NavItem {
  href: string;
  label: string;
  short: string;
  Icon: ComponentType<{ className?: string }>;
}

const NAV: readonly NavItem[] = [
  { href: "/", label: "Tổng quan", short: "Tổng quan", Icon: LayoutDashboard },
  { href: "/kinematics/forward", label: "Động học thuận", short: "Thuận", Icon: Move },
  { href: "/kinematics/inverse", label: "Động học ngược", short: "Ngược", Icon: Waypoints },
  { href: "/dynamics", label: "Động lực học", short: "Lực", Icon: Activity },
  { href: "/lidar", label: "LiDAR", short: "LiDAR", Icon: Radar },
  { href: "/system", label: "Hệ thống", short: "Hệ thống", Icon: Cpu },
];

const SOURCE_LABEL: Record<Source, string> = {
  idle: "Không có",
  keyboard: "Bàn phím",
  forward: "Chạy động học thuận",
  inverse: "Chạy động học ngược",
};

type Tone = "ok" | "warn" | "bad" | "idle";

const TONE_CLASS: Record<Tone, string> = {
  ok: "text-emerald-700 dark:text-emerald-400",
  warn: "text-amber-700 dark:text-amber-400",
  bad: "text-destructive",
  idle: "text-muted-foreground",
};

function Chip({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border bg-card px-2 py-1 text-xs font-medium tracking-wide whitespace-nowrap",
        TONE_CLASS[tone],
      )}
    >
      {children}
    </span>
  );
}

function connectionChip(s: ShellSnapshot): { tone: Tone; text: string } {
  if (s.conn === "open") {
    return s.hasState
      ? { tone: "ok", text: "Đã kết nối" }
      : { tone: "warn", text: "Chờ dữ liệu" };
  }
  if (s.conn === "connecting") return { tone: "warn", text: "Đang kết nối" };
  return { tone: "bad", text: "Mất kết nối" };
}

function StatusBar({ shell }: { shell: ShellSnapshot }) {
  const connection = connectionChip(shell);
  const driver = shell.role === "driver";
  const canToggleArm =
    shell.conn === "open" && driver && (shell.armed || shell.robotLink);
  return (
    <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2 md:px-6">
        <div className="flex w-full gap-2 sm:order-last sm:ml-auto sm:w-auto">
          <Button
            type="button"
            variant={shell.armed ? "secondary" : "outline"}
            size="lg"
            className="flex-1 sm:flex-none"
            disabled={!canToggleArm}
            onClick={() => setArmed(!shell.armed)}
          >
            <Power data-icon="inline-start" />
            {shell.armed ? "Disarm" : "Arm (R)"}
          </Button>
          <Button
            type="button"
            size="lg"
            className="flex-1 bg-destructive text-white hover:bg-destructive/90 sm:flex-none"
            onClick={() => emergencyStop()}
          >
            <OctagonX data-icon="inline-start" />
            DỪNG KHẨN (X / Esc)
          </Button>
        </div>
        <div
          className="flex flex-wrap items-center gap-2"
          role="status"
          aria-label="Trạng thái hệ thống"
        >
          <Chip tone={connection.tone}>
            {shell.conn === "open" ? (
              <Wifi className="size-3.5" />
            ) : (
              <WifiOff className="size-3.5" />
            )}
            {connection.text}
          </Chip>
          <Chip tone={!shell.hasState ? "idle" : shell.robotLink ? "ok" : "bad"}>
            Robot: {!shell.hasState ? "—" : shell.robotLink ? "đã nối" : "mất link"}
          </Chip>
          <Chip tone={driver ? "ok" : "idle"}>
            <KeyRound className="size-3.5" />
            {driver ? "Quyền lái" : "Chỉ xem"}
          </Chip>
          <Chip tone={shell.armed ? "warn" : "idle"}>
            {shell.armed ? "ĐÃ ARM" : "DISARM"}
          </Chip>
          <Chip tone={shell.source === "idle" ? "idle" : "ok"}>
            Nguồn lệnh: {SOURCE_LABEL[shell.source]}
          </Chip>
        </div>
      </div>
    </header>
  );
}

function ControlSettings({ shell }: { shell: ShellSnapshot }) {
  const linId = useId();
  const angId = useId();
  const codeId = useId();
  const [linText, setLinText] = useState(String(shell.speed.lin));
  const [angText, setAngText] = useState(String(shell.speed.ang));
  const [codeText, setCodeText] = useState("");
  const linValid = parseSpeed(linText) !== null;
  const angValid = parseSpeed(angText) !== null;

  function onLin(text: string) {
    setLinText(text);
    const lin = parseSpeed(text);
    if (lin !== null) setSpeed(lin, shell.speed.ang);
  }

  function onAng(text: string) {
    setAngText(text);
    const ang = parseSpeed(text);
    if (ang !== null) setSpeed(shell.speed.lin, ang);
  }

  function onSubmitCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (codeText.trim() === "") return;
    setOperatorCode(codeText);
    setCodeText("");
  }

  const rejected = shell.hasCode && shell.hasState && shell.role !== "driver";

  return (
    <section
      aria-label="Cài đặt điều khiển"
      className="flex flex-wrap items-end gap-x-6 gap-y-3 border-b bg-muted/40 px-3 py-3 md:px-6"
    >
      <div className="flex gap-3">
        <div className="grid w-32 gap-1.5">
          <Label htmlFor={linId}>Tịnh tiến (m/s)</Label>
          <Input
            id={linId}
            inputMode="decimal"
            autoComplete="off"
            value={linText}
            aria-invalid={!linValid}
            className="tabular-nums"
            onChange={(e) => onLin(e.target.value)}
          />
        </div>
        <div className="grid w-32 gap-1.5">
          <Label htmlFor={angId}>Quay (rad/s)</Label>
          <Input
            id={angId}
            inputMode="decimal"
            autoComplete="off"
            value={angText}
            aria-invalid={!angValid}
            className="tabular-nums"
            onChange={(e) => onAng(e.target.value)}
          />
        </div>
      </div>

      {shell.hasCode ? (
        <div className="grid gap-1.5">
          <span className="text-sm font-medium">Mã điều khiển</span>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              Đã lưu cho phiên này
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setOperatorCode("")}
            >
              Xóa mã
            </Button>
          </div>
          {rejected ? (
            <span className="text-xs text-destructive">
              Mã chưa được chấp nhận hoặc đã có người khác đang lái.
            </span>
          ) : null}
        </div>
      ) : (
        <form onSubmit={onSubmitCode} className="grid gap-1.5">
          <Label htmlFor={codeId}>Mã điều khiển</Label>
          <div className="flex gap-2">
            <Input
              id={codeId}
              type="password"
              autoComplete="off"
              placeholder="Nhập mã để lái"
              value={codeText}
              className="w-44"
              onChange={(e) => setCodeText(e.target.value)}
            />
            <Button type="submit" variant="secondary">
              Xác nhận
            </Button>
          </div>
        </form>
      )}

      <div className="hidden flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground md:flex">
        <span className="flex items-center gap-1.5">
          <KbdGroup>
            <Kbd>W</Kbd>
            <Kbd>A</Kbd>
            <Kbd>S</Kbd>
            <Kbd>D</Kbd>
          </KbdGroup>
          tiến, trái, lùi, phải
        </span>
        <span className="flex items-center gap-1.5">
          <KbdGroup>
            <Kbd>Q</Kbd>
            <Kbd>E</Kbd>
          </KbdGroup>
          quay trái, phải
        </span>
        <span className="flex items-center gap-1.5">
          <Kbd>R</Kbd>
          arm
        </span>
        <span className="flex items-center gap-1.5">
          <KbdGroup>
            <Kbd>X</Kbd>
            <Kbd>Esc</Kbd>
          </KbdGroup>
          dừng và disarm
        </span>
      </div>
    </section>
  );
}

function Navigation() {
  const pathname = usePathname();
  return (
    <aside className="contents md:sticky md:top-0 md:flex md:h-svh md:w-56 md:shrink-0 md:flex-col md:border-r md:bg-sidebar md:text-sidebar-foreground">
      <div className="hidden border-b px-4 py-4 md:block">
        <div className="flex items-center gap-2">
          <span className="grid size-6 place-items-center rounded-sm bg-sidebar-primary text-xs font-bold text-sidebar-primary-foreground">
            M
          </span>
          <span className="text-sm font-semibold tracking-[0.18em]">MECANUM</span>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">Bảng điều khiển robot</p>
      </div>
      <nav
        aria-label="Điều hướng"
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-6 border-t bg-sidebar text-sidebar-foreground md:static md:z-auto md:flex md:flex-col md:gap-1 md:border-t-0 md:p-3"
      >
        {NAV.map(({ href, label, short, Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex flex-col items-center justify-center gap-0.5 px-1 py-2 text-[11px] leading-tight outline-none focus-visible:ring-3 focus-visible:ring-ring/50 md:flex-row md:justify-start md:gap-3 md:rounded-lg md:px-3 md:text-sm",
                active
                  ? "font-medium text-sidebar-primary md:bg-sidebar-accent md:text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:text-foreground md:hover:bg-sidebar-accent/60",
              )}
            >
              <Icon className="size-5 md:size-4" />
              <span className="md:hidden">{short}</span>
              <span className="hidden md:inline">{label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const shell = useShell();

  useEffect(() => {
    startStore();
  }, []);

  return (
    <div className="flex min-h-svh flex-col md:flex-row">
      <Navigation />
      <div className="flex min-w-0 flex-1 flex-col pb-16 md:pb-0">
        <StatusBar shell={shell} />
        <ControlSettings shell={shell} />
        <main className="flex-1 px-3 py-4 md:px-6 md:py-6">{children}</main>
      </div>
    </div>
  );
}
