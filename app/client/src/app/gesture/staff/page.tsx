"use client";

// FR-14: quản lý nhân viên được điều khiển bằng cử chỉ. Chỉ driver thao tác được; dữ liệu khuôn mặt
// nằm trên Jetson, trang này chỉ thấy số mẫu (NFR-09). Xóa phải xác nhận. Đăng ký mặt thuộc T25.

import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { DataLostAlert, Panel, StatusBadge, dataStateOf } from "@/components/robot/panels";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { StaffMember } from "@/robot/protocol";
import { sendStaff, useShell, useTelemetry } from "@/robot/store";

const REFRESH_MS = 3000;

function asStaff(value: unknown): StaffMember[] | null {
  return Array.isArray(value) ? (value as StaffMember[]) : null;
}

export default function StaffPage() {
  const shell = useShell();
  const telemetry = useTelemetry();
  const driver = shell.role === "driver";
  const result = telemetry?.vision?.result ?? null;
  const resultKey = JSON.stringify(result);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [form, setForm] = useState({ code: "", name: "", note: "" });
  const online = telemetry?.vision?.link === true;

  useEffect(() => {
    if (!driver || !online) return;
    sendStaff({ t: "staff_list" });
    const id = setInterval(() => sendStaff({ t: "staff_list" }), REFRESH_MS);
    return () => clearInterval(id);
  }, [driver, online]);

  // Điều chỉnh state ngay lúc render khi kết quả mới tới (không dùng effect).
  const [seenKey, setSeenKey] = useState("");
  if (resultKey !== seenKey) {
    setSeenKey(resultKey);
    if (result !== null) {
      const list = asStaff(result.staff);
      if (list !== null) setStaff(list);
      if (result.ok === false) setError(typeof result.error === "string" ? result.error : "Lệnh bị từ chối");
      else if (result.ok === true) setError(null);
    }
  }

  const act = (cmd: Parameters<typeof sendStaff>[0]) => {
    sendStaff(cmd);
    sendStaff({ t: "staff_list" });
  };

  const onCreate = (event: FormEvent) => {
    event.preventDefault();
    act({ t: "staff_create", code: form.code.trim(), name: form.name.trim(), note: form.note.trim(), allowed: true });
    setForm({ code: "", name: "", note: "" });
  };

  const target = staff.find((s) => s.id === confirmId);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Nhân viên</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Chỉ nhân viên được phép mới điều khiển được bằng cử chỉ. Tắt quyền hoặc xóa người đang điều khiển
          sẽ khóa robot ngay.
        </p>
      </div>
      <DataLostAlert state={dataStateOf(shell)} />
      {!driver ? <StatusBadge tone="warn">Cần quyền lái để quản lý nhân viên</StatusBadge> : null}
      {driver && !online ? <StatusBadge tone="warn">Vision agent chưa kết nối</StatusBadge> : null}
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}

      <Panel title="Thêm nhân viên">
        <form onSubmit={onCreate} className="grid gap-3 sm:grid-cols-4 sm:items-end">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="staff-code">Mã</Label>
            <Input id="staff-code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="staff-name">Họ tên</Label>
            <Input id="staff-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="staff-note">Ghi chú</Label>
            <Input id="staff-note" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </div>
          <Button type="submit" disabled={!driver || !online || form.code.trim() === "" || form.name.trim() === ""}>
            Thêm
          </Button>
        </form>
      </Panel>

      <Panel title={`Danh sách (${staff.length})`}>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Mã</TableHead>
              <TableHead>Họ tên</TableHead>
              <TableHead>Ghi chú</TableHead>
              <TableHead>Mẫu mặt</TableHead>
              <TableHead>Được phép</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {staff.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="font-mono">{s.code}</TableCell>
                <TableCell>{s.name}</TableCell>
                <TableCell className="text-muted-foreground">{s.note}</TableCell>
                <TableCell>{s.samples}</TableCell>
                <TableCell>
                  <Switch
                    checked={s.allowed}
                    disabled={!driver}
                    aria-label={`Cho phép ${s.name}`}
                    onCheckedChange={(on: boolean) => act({ t: "staff_update", id: s.id, allowed: on })}
                  />
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!driver || s.samples === 0}
                    onClick={() => act({ t: "faces_clear", id: s.id })}
                  >
                    Xóa mẫu mặt
                  </Button>{" "}
                  <Button variant="destructive" size="sm" disabled={!driver} onClick={() => setConfirmId(s.id)}>
                    Xóa
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {staff.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground">
                  Chưa có nhân viên
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </Panel>

      <AlertDialog open={confirmId !== null} onOpenChange={(open) => !open && setConfirmId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xóa {target?.name ?? "nhân viên"}?</AlertDialogTitle>
            <AlertDialogDescription>
              Xóa luôn mọi mẫu khuôn mặt của người này và không hoàn tác được. Nếu đang điều khiển, robot sẽ khóa ngay.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (confirmId !== null) act({ t: "staff_delete", id: confirmId });
                setConfirmId(null);
              }}
            >
              Xóa
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
