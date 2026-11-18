"""Chụp khung RGB từ Astra S để thu data cử chỉ (T23). Chạy trên Jetson, KHÔNG dùng động cơ.

    python3 -m vision_agent.capture --person p001 --session s2 --kind gesture --consent \
        --labels STOP,FORWARD,BACK,RIGHT,LEFT,OPEN_PALM,OTHER

Trang trạng thái http://<jetson>:8780 cho người đứng trước camera thấy: nhãn đang thu, động tác
cần làm, đếm ngược chuẩn bị (vàng), đang chụp (xanh), và ảnh trực tiếp từ camera. Mỗi nhãn: --prep
giây chuẩn bị, rồi --count khung cách nhau --interval giây, ghi qua Recorder (cần --consent, mã
người ẩn danh). Chỉ ghi RGB .jpg. Trang chỉ đọc, không nhận lệnh nào.
"""
from __future__ import annotations

import argparse
import io
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from vision_agent.record import Recorder

SDK_DEFAULT = "/home/rai/mecanum_base/robot/vendor/openni2/arm64"
HINTS = {
    "STOP": "NẮM TAY (hoặc hạ tay xuống)",
    "FORWARD": "CHỈ NGÓN TRỎ LÊN",
    "BACK": "CHỈ NGÓN TRỎ XUỐNG",
    "RIGHT": "CHỈ SANG PHẢI CỦA ẢNH",
    "LEFT": "CHỈ SANG TRÁI CỦA ẢNH",
    "OPEN_PALM": "XÒE BÀN TAY",
    "OTHER": "TAY TƯ THẾ BẤT KỲ KHÁC",
}
PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width">
<body style="margin:0;font-family:sans-serif;text-align:center;color:#fff;background:#333">
<div id=box style="padding:16px"><div id=phase style="font-size:48px;font-weight:bold"></div>
<div id=label style="font-size:40px"></div><div id=hint style="font-size:32px"></div>
<div id=count style="font-size:64px"></div></div>
<img id=img style="max-width:100%"><script>
const c={PREP:"#c90",CAPTURE:"#0a0",DONE:"#555",WAIT:"#555"};
const t={PREP:"CHUẨN BỊ",CAPTURE:"ĐANG CHỤP",DONE:"XONG",WAIT:"CHỜ"};
async function tick(){try{const s=await (await fetch("/state")).json();
box.style.background=c[s.phase]||"#555";phase.textContent=t[s.phase]||s.phase;
label.textContent=s.label;hint.textContent=s.hint;count.textContent=s.count;}catch(e){}
img.src="/frame.jpg?"+Date.now();setTimeout(tick,250);}tick();</script>"""


def serve(state: dict, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?")[0]
            if path == "/state":
                import json
                body, kind = json.dumps(state["info"]).encode(), "application/json"
            elif path == "/frame.jpg" and state.get("frame"):
                body, kind = state["frame"], "image/jpeg"
            elif path == "/":
                body, kind = PAGE.encode("utf-8"), "text/html; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args) -> None:
            pass

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data/raw")
    ap.add_argument("--person", required=True)
    ap.add_argument("--session", required=True)
    ap.add_argument("--kind", default="gesture")
    ap.add_argument("--labels", required=True, help="danh sách nhãn, cách nhau dấu phẩy")
    ap.add_argument("--count", type=int, default=150)
    ap.add_argument("--interval", type=float, default=0.4)
    ap.add_argument("--skip", type=int, default=5, help="so khung dau moi nhan khong ghi (tay dang doi dong tac)")
    ap.add_argument("--prep", type=float, default=10.0)
    ap.add_argument("--wait", type=float, default=0.0, help="giây chờ trước nhãn đầu")
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--consent", action="store_true", help="người được thu đã đồng ý")
    ap.add_argument("--sdk", default=SDK_DEFAULT)
    args = ap.parse_args(argv)
    rec = Recorder(args.root, args.person, args.session, args.kind, consent=args.consent)

    import numpy as np
    from openni import openni2
    from PIL import Image

    state: dict = {"frame": b"", "info": {"phase": "WAIT", "label": "", "hint": "", "count": ""}}
    server = serve(state, args.port)

    def grab() -> bytes:
        frame = color.read_frame()
        rgb = np.frombuffer(frame.get_buffer_as_uint8(), dtype=np.uint8).reshape(
            frame.height, frame.width, 3
        )
        buffer = io.BytesIO()
        Image.fromarray(rgb).save(buffer, "JPEG", quality=92)
        state["frame"] = buffer.getvalue()
        return state["frame"]

    def show(phase: str, label: str, count: str) -> None:
        state["info"] = {"phase": phase, "label": label, "hint": HINTS.get(label, "") + ("  - đổi nhẹ vị trí/độ cao tay" if phase == "CAPTURE" else ""), "count": count}

    openni2.initialize(args.sdk)
    device = openni2.Device.open_any()
    color = device.create_color_stream()
    color.start()
    try:
        first = args.wait
        for label in args.labels.split(","):
            end = time.time() + first
            first = 0.0
            while time.time() < end:
                show("WAIT", label, f"{end - time.time():.0f}")
                grab()
            print(f"READY {label}", flush=True)
            end = time.time() + args.prep
            while time.time() < end:
                show("PREP", label, f"{end - time.time():.0f}")
                grab()
            print(f"NOW {label}", flush=True)
            for i in range(args.count):
                show("CAPTURE", label, f"{i + 1}/{args.count}")
                jpeg = grab()
                if i >= args.skip:
                    rec.add(jpeg, label)
                time.sleep(args.interval)
            show("DONE", label, "")
            print(f"DONE {label}", flush=True)
    finally:
        show("DONE", "Hoàn tất", "")
        time.sleep(1.5)
        server.shutdown()
        color.stop()
        openni2.unload()
        print(rec.close(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
