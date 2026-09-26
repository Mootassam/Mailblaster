"""
Public tracking link for MailBlaster via a free Cloudflare quick tunnel.

Recipients' mail apps (Gmail loads images through Google's servers) must be able to
reach the open-tracking pixel. A quick tunnel gives this PC a secure public https
address (https://<random>.trycloudflare.com) with no account or router setup.
The address changes each time the tunnel starts, so MailBlaster only uses it for the
open pixel ("temporary" mode) — links and unsubscribe never depend on it.

Only the tracking routes are reachable through it (see server._guard_public_access).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

DOWNLOAD_URL = ("https://github.com/cloudflare/cloudflared/releases/latest/download/"
                "cloudflared-windows-amd64.exe")
_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

STATE = {"status": "off", "url": "", "error": "", "progress": 0, "started": 0}
_LOCK = threading.Lock()
_PROC = None
_on_url = None          # callback(url) when the public address is known


def _set(**kw):
    with _LOCK:
        STATE.update(**kw)


def status():
    with _LOCK:
        d = dict(STATE)
    d["installed"] = bool(find_binary())
    return d


def _bin_dir():
    try:
        import app_paths
        base = app_paths.data_dir()
    except Exception:
        base = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(base, "bin")
    os.makedirs(d, exist_ok=True)
    return d


def find_binary():
    local = os.path.join(_bin_dir(), "cloudflared.exe")
    if os.path.isfile(local) and os.path.getsize(local) > 1_000_000:
        return local
    for p in os.environ.get("PATH", "").split(os.pathsep):
        c = os.path.join(p.strip('"'), "cloudflared.exe")
        if os.path.isfile(c):
            return c
    return ""


def _download():
    dest = os.path.join(_bin_dir(), "cloudflared.exe")
    tmp = dest + ".part"
    _set(status="downloading", progress=0, error="")
    req = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "MailBlaster"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if total:
                _set(progress=int(got / total * 100))
    if os.path.getsize(tmp) < 1_000_000:
        raise RuntimeError("Download incomplete.")
    os.replace(tmp, dest)
    return dest


def start(port, on_url=None):
    """Start (downloading the tool first if needed) in the background."""
    global _on_url
    _on_url = on_url
    with _LOCK:
        if STATE["status"] in ("downloading", "starting", "on"):
            return
        STATE.update(status="starting", error="", url="")
    threading.Thread(target=_run, args=(port,), daemon=True).start()


def _run(port):
    global _PROC
    try:
        exe = find_binary() or _download()
    except Exception as e:
        _set(status="error", error=f"Couldn't download Cloudflare's tunnel tool ({e}). "
                                   "Check your internet connection and try again.")
        return
    _set(status="starting", progress=100)
    flags = 0x08000000 if sys.platform == "win32" else 0      # CREATE_NO_WINDOW
    try:
        _PROC = subprocess.Popen(
            [exe, "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            creationflags=flags, text=True, encoding="utf-8", errors="replace")
    except OSError as e:
        _set(status="error", error=f"Couldn't start the tunnel ({e}). Windows may be blocking "
                                   "cloudflared.exe — allow it in Windows Security.")
        return
    deadline = time.time() + 60
    found = False
    for line in _PROC.stdout:
        if not found:
            m = _URL_RE.search(line)
            if m:
                found = True
                url = m.group(0)
                _set(status="on", url=url, started=time.time(), error="")
                if _on_url:
                    try:
                        _on_url(url)
                    except Exception:
                        pass
            elif time.time() > deadline:
                break
    code = _PROC.poll() if _PROC else None
    with _LOCK:
        if STATE["status"] != "off":        # not stopped on purpose
            STATE.update(status="error", url="",
                         error="The tunnel closed unexpectedly (internet down?). "
                               "MailBlaster retries automatically." if found else
                         "Cloudflare didn't return a public address — try again in a minute.")
    if found and STATE["status"] == "error":
        time.sleep(15)                      # auto-reconnect after a drop
        with _LOCK:
            retry = STATE["status"] == "error"
            if retry:
                STATE["status"] = "starting"
        if retry:
            _run(port)
    return code


def stop():
    global _PROC
    _set(status="off", url="", error="")
    p, _PROC = _PROC, None
    if p and p.poll() is None:
        try:
            p.terminate()
            p.wait(5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
