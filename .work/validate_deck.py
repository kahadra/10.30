"""Validate the 10.30 deck in headless Edge over the DevTools protocol (stdlib-only websocket client).

Per slide: layout-overflow check + screenshot. Also checks navigation keys, notes modal, timer and the
script/manifest sync, then writes validation.json and .work/contact_sheet.png (Pillow vendored in 10.02/.work/lib).
"""
import base64
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(__file__).resolve().parents[1]
work = root / ".work"
shots = work / "screenshots"
shots.mkdir(exist_ok=True)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
html = (root / "index.html").read_text(encoding="utf8")
data = json.loads(re.search(r"const slideData=(\[.*?\]);\n", html, re.S)[1])
main = sum(1 for s in data if s["seconds"])


def kill_on_exit(proc):
    """Put proc in a Windows job that is killed when this python dies, even by timeout/TerminateProcess."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.OpenProcess.restype = wintypes.HANDLE

    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "w", "o", "rb", "wb", "ob")]

    class BASIC(ctypes.Structure):
        _fields_ = [("a", ctypes.c_longlong), ("b", ctypes.c_longlong), ("LimitFlags", wintypes.DWORD),
                    ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("e", wintypes.DWORD),
                    ("f", ctypes.c_size_t), ("g", wintypes.DWORD), ("h", wintypes.DWORD)]

    class EXT(ctypes.Structure):
        _fields_ = [("basic", BASIC), ("io", IO), ("pm", ctypes.c_size_t), ("jm", ctypes.c_size_t),
                    ("ppm", ctypes.c_size_t), ("pjm", ctypes.c_size_t)]

    job = k32.CreateJobObjectW(None, None)
    info = EXT()
    info.basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
    h = k32.OpenProcess(0x0001 | 0x0100, False, proc.pid)  # PROCESS_TERMINATE | PROCESS_SET_QUOTA
    if not (job and h and k32.AssignProcessToJobObject(job, h)):
        print(f"warning: job assignment failed ({ctypes.get_last_error()}); relying on finally cleanup")
    return job  # keep the handle open for the life of this process


def stop_edge(proc, prof):
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    # renderer/GPU children can outlive the browser process for a moment
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object {{ $_.CommandLine -like '*{prof.name}*' }}"
                    " | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                   creationflags=subprocess.CREATE_NO_WINDOW, check=False)
    time.sleep(1)
    shutil.rmtree(prof, ignore_errors=True)


class WS:
    """Minimal RFC 6455 client: text frames only, enough for CDP."""

    def __init__(self, url):
        host, port, path = re.match(r"ws://([^:/]+):(\d+)(/.*)", url).groups()
        self.s = socket.create_connection((host, int(port)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                       f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(4096)
        assert b" 101 " in buf.split(b"\r\n")[0], buf[:200]
        self.rest = buf.split(b"\r\n\r\n", 1)[1]

    def send(self, text):
        payload = text.encode()
        n = len(payload)
        head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0xFE]) + struct.pack(">H", n) if n < 65536
                                else bytes([0xFF]) + struct.pack(">Q", n))
        mask = os.urandom(4)
        self.s.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _read(self, n):
        while len(self.rest) < n:
            chunk = self.s.recv(1 << 20)
            if not chunk:
                raise ConnectionError("websocket closed")
            self.rest += chunk
        out, self.rest = self.rest[:n], self.rest[n:]
        return out

    def recv(self):
        msg = b""
        while True:
            b0, b1 = self._read(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            msg += self._read(n)
            if b0 & 0x80:
                return msg.decode("utf8", "replace")


CHECK_JS = r"""(()=>{const out=[];const slides=[...document.querySelectorAll('.slide')];
 slides.forEach((s,i)=>{show(i);const issues=[];const sb=s.getBoundingClientRect();const sc=sb.width/1280;
  s.querySelectorAll('.slide-body *').forEach(el=>{const r=el.getBoundingClientRect();if(!r.width&&!r.height)return;
   const name=el.tagName.toLowerCase()+(typeof el.className==='string'&&el.className.trim()?'.'+el.className.trim().split(/\s+/).join('.'):'');
   if(r.right>sb.right-40*sc+1||r.bottom>sb.bottom-48*sc+1)issues.push(['outside-safe-area',name,Math.round((r.right-sb.left)/sc),Math.round((r.bottom-sb.top)/sc)]);
   if(el.scrollWidth>el.clientWidth+2&&['hidden','clip'].includes(getComputedStyle(el).overflowX))issues.push(['clipped-x',name,el.scrollWidth,el.clientWidth]);
   if(el.tagName==='PRE'&&el.scrollHeight>el.clientHeight+2)issues.push(['clipped-y',name,el.scrollHeight,el.clientHeight]);});
  const body=s.querySelector('.slide-body');if(body&&body.scrollHeight>body.clientHeight+2)issues.push(['body-overflow','.slide-body',body.scrollHeight,body.clientHeight]);
  out.push({slide:i+1,issues:issues.slice(0,6)});});show(0);return JSON.stringify(out);})()"""

INTERACT_JS = r"""(()=>{const r={};const key=k=>dispatchEvent(new KeyboardEvent('keydown',{key:k}));
 show(0);key('ArrowRight');r.arrow_right=current===1;key('ArrowLeft');r.arrow_left=current===0;
 key('End');r.end=current===slides.length-1;key('Home');r.home=current===0;
 show(mainCount-1);key('ArrowRight');r.main_end_stops=current===mainCount-1;
 key('n');r.notes_open=document.getElementById('notesModal').classList.contains('open')&&document.getElementById('notesCopy').textContent.length>20;key('Escape');
 key('m');r.map_open=document.getElementById('map').classList.contains('open')&&document.querySelectorAll('.map-item').length===slides.length;key('Escape');
 document.querySelector('[data-jump]').click();r.toc_jump=current===Number(document.querySelector('[data-jump]').dataset.jump)-1;
 number.value=5;number.dispatchEvent(new Event('change'));r.number_jump=current===4;
 r.timer_initial=document.getElementById('timer').textContent.includes('20:00');key('t');r.timer_starts=document.getElementById('timerBtn').textContent==='정지';key('t');
 document.getElementById('timerReset').click();show(0);return JSON.stringify(r);})()"""


def main_run():
    port = 19000 + uuid.uuid4().int % 900
    prof = Path(tempfile.gettempdir()) / f"deck-edge-{uuid.uuid4().hex[:8]}"
    proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                             "--remote-allow-origins=*", f"--remote-debugging-port={port}", f"--user-data-dir={prof}",
                             "--window-size=1280,720", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    job = kill_on_exit(proc)  # noqa: F841 - closing this handle (any exit path) kills Edge
    try:
        for _ in range(100):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1))
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("Edge DevTools endpoint unavailable")
        ws = WS(next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page"))
        seq = [0]
        console_errors = []

        def call(method, params=None):
            seq[0] += 1
            ws.send(json.dumps({"id": seq[0], "method": method, "params": params or {}}))
            deadline = time.monotonic() + 60  # event floods must not keep us waiting forever
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"CDP {method} got no reply in 60 s")
                msg = json.loads(ws.recv())
                if msg.get("method") == "Runtime.exceptionThrown":
                    console_errors.append(msg["params"]["exceptionDetails"].get("text", ""))
                if msg.get("method") == "Log.entryAdded" and msg["params"]["entry"]["level"] == "error":
                    console_errors.append(msg["params"]["entry"].get("text", "") + " " + msg["params"]["entry"].get("url", ""))
                if msg.get("id") == seq[0]:
                    if "error" in msg:
                        raise RuntimeError(msg["error"])
                    return msg.get("result", {})

        def js(expr):
            return call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})["result"].get("value")

        call("Runtime.enable"); call("Log.enable"); call("Page.enable")
        call("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 720, "deviceScaleFactor": 1, "mobile": False})
        call("Page.navigate", {"url": (root / "index.html").as_uri()})
        for _ in range(100):
            if js("document.readyState") == "complete" and js("document.fonts.status") == "loaded":
                break
            time.sleep(0.2)
        time.sleep(1.0)
        for i in range(len(data)):  # screenshots first: the interaction checks below leave toasts on screen
            js(f"show({i})")
            time.sleep(0.15)
            png = base64.b64decode(call("Page.captureScreenshot", {"format": "png"})["data"])
            (shots / f"{i + 1:02}.png").write_bytes(png)
        overflow = json.loads(js(CHECK_JS))
        interact = json.loads(js(INTERACT_JS))
        broken = js("[...document.images].filter(i=>i.getAttribute('src')&&(!i.complete||!i.naturalWidth)).map(i=>i.src)")
        return overflow, interact, broken, console_errors
    finally:
        stop_edge(proc, prof)


overflow, interact, broken, console_errors = main_run()

sys.path.insert(0, str(root.parent / "10.02/.work/lib"))
from PIL import Image  # noqa: E402

thumbs = [Image.open(shots / f"{i:02}.png").convert("RGB").resize((426, 240)) for i in range(1, len(data) + 1)]
cols = 4
sheet = Image.new("RGB", (cols * 430, ((len(thumbs) + cols - 1) // cols) * 244), "white")
for k, t in enumerate(thumbs):
    sheet.paste(t, ((k % cols) * 430 + 2, (k // cols) * 244 + 2))
sheet.save(work / "contact_sheet.png")

script = (root / "presentation_script.md").read_text(encoding="utf8")
result = {
    "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "browser": "Microsoft Edge headless (DevTools protocol)", "viewport": [1280, 720],
    "slides": len(data), "main_slides": main, "appendix_slides": len(data) - main,
    "planned_seconds": sum(s["seconds"] for s in data), "transition_buffer_seconds": 60, "hard_limit_seconds": 1200,
    "actual_speaking_time": "NOT_MEASURED_REHEARSAL_REQUIRED",
    "layout_issues": {r["slide"]: r["issues"] for r in overflow if r["issues"]},
    "broken_images": broken, "console_errors": console_errors, "interaction_checks": interact,
    "script_in_sync": len(re.findall(r"^## Slide ", script, re.M)) == len(data) and all(s["notes"] in script for s in data),
    "pending_placeholders": "실행 대기" in html,
    "screenshots": len(thumbs),
}
(root / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
print(json.dumps(result, ensure_ascii=False, indent=1))
