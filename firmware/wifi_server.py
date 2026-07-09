#!/usr/bin/env python3
# wifi_server.py — SATURNIX Dione file transfer system.
# Sci-fi terminal interface. Serves gallery files over HTTP.

import os, re, io, zipfile, json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PICTURES_DIR = str(Path(__file__).resolve().parent / "Pictures")
PORT = 80
_NUM_RE = re.compile(r'^Saturnix_(\d+)\.(jpg|dng)$', re.IGNORECASE)

# Load config
_HW = {}
try:
    _hw_path = Path(__file__).resolve().parent / "config.json"
    if _hw_path.exists():
        with open(_hw_path) as f:
            _HW = json.load(f)
except:
    pass

_CAM_NAME = _HW.get("camera_name", "SATURNIX Dione").upper()

def get_files():
    files = []
    try:
        for f in sorted(os.listdir(PICTURES_DIR)):
            if _NUM_RE.match(f):
                fp = os.path.join(PICTURES_DIR, f)
                try:
                    files.append((f, os.path.getsize(fp)))
                except:
                    pass
    except:
        pass
    return files

def fmt(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n/1024:.1f} KB"
    return f"{n/1024/1024:.1f} MB"

def count_jpg(files):
    return sum(1 for f, _ in files if f.lower().endswith(".jpg"))

HTML_TEMPLATE = """<!DOCTYPE html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{cam_name} // FILE TRANSFER</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --bg:#0d0e0a;
  --panel:#13140f;
  --text:#c7b299;
  --dim:#82765a;
  --label:#aa916e;
  --accent:#e5c051;
  --warn:#dc4628;
  --success:#a0be78;
  --divider:#3c372d;
  --border:#2d2920;
}}
html,body{{
  background:var(--bg);
  color:var(--text);
  font-family:'JetBrains Mono','Courier New',Courier,monospace;
  font-weight:400;
  min-height:100vh;
}}
body{{
  padding:20px 16px;max-width:680px;margin:0 auto;
  text-transform:uppercase;letter-spacing:0.05em;
  font-size:13px;line-height:1.5;
}}
.header{{
  display:flex;justify-content:space-between;align-items:baseline;
  border-bottom:1px solid var(--divider);
  padding-bottom:14px;margin-bottom:6px;
}}
.brand{{
  font-size:20px;font-weight:700;letter-spacing:0.15em;
  color:var(--accent);
}}
.brand-sub{{
  font-size:10px;color:var(--label);letter-spacing:0.2em;
  font-weight:500;
}}
.divider{{
  display:flex;align-items:center;gap:10px;margin:18px 0 12px 0;
  color:var(--label);font-size:10px;letter-spacing:0.25em;
  font-weight:500;
}}
.divider::before,.divider::after{{
  content:'';flex:1;height:1px;background:var(--divider);
}}
.sub{{
  color:var(--label);font-size:10px;
  letter-spacing:0.2em;margin-bottom:18px;
  font-weight:500;
}}
.section-bar{{
  display:flex;justify-content:space-between;align-items:center;
  padding:6px 10px;background:var(--panel);
  border:1px solid var(--border);
  font-size:10px;color:var(--label);letter-spacing:0.2em;
  margin-bottom:14px;
}}
.section-bar .key{{color:var(--accent);font-weight:700}}
.file{{
  display:flex;justify-content:space-between;align-items:center;
  padding:11px 10px;
  border-bottom:1px solid var(--border);
  transition:background 0.15s;
}}
.file:hover{{background:var(--panel)}}
.finfo{{display:flex;align-items:center;gap:10px;flex:1;min-width:0}}
.fname{{
  font-size:13px;color:var(--text);font-weight:500;
  letter-spacing:0.05em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}}
.fsize{{
  font-size:10px;color:var(--label);letter-spacing:0.15em;
  flex-shrink:0;
}}
.tag{{
  font-size:9px;padding:2px 6px;border:1px solid var(--divider);
  color:var(--accent);letter-spacing:0.15em;font-weight:700;
}}
a.dl{{
  background:transparent;color:var(--accent);text-decoration:none;
  padding:6px 14px;font-size:10px;font-weight:700;font-family:inherit;
  border:1px solid var(--accent);letter-spacing:0.2em;
  margin-left:8px;flex-shrink:0;
}}
a.dl:active,a.dl:hover{{background:var(--accent);color:var(--bg)}}
.btn-all{{
  display:inline-block;margin:14px 0;
  background:transparent;color:var(--accent);text-decoration:none;
  padding:10px 20px;font-size:12px;font-weight:700;font-family:inherit;
  border:1px solid var(--accent);letter-spacing:0.2em;
}}
.btn-all:active,.btn-all:hover{{background:var(--accent);color:var(--bg)}}
.empty{{
  color:var(--label);font-size:12px;
  margin:60px 0;text-align:center;letter-spacing:0.25em;
  border:1px dashed var(--divider);padding:40px;
}}
.count{{
  color:var(--label);font-size:10px;
  margin-top:24px;letter-spacing:0.25em;
  padding-top:14px;border-top:1px solid var(--divider);
  display:flex;justify-content:space-between;
}}
.count .accent{{color:var(--accent)}}
.corner{{
  position:fixed;width:14px;height:14px;
  border:1px solid var(--label);
}}
.corner.tl{{top:8px;left:8px;border-right:0;border-bottom:0}}
.corner.tr{{top:8px;right:8px;border-left:0;border-bottom:0}}
.corner.bl{{bottom:8px;left:8px;border-right:0;border-top:0}}
.corner.br{{bottom:8px;right:8px;border-left:0;border-top:0}}
@media (max-width:480px){{
  body{{padding:16px 12px;font-size:12px}}
  .brand{{font-size:16px}}
  .corner{{display:none}}
  .fsize{{display:none}}
}}
</style></head><body>
<div class="corner tl"></div><div class="corner tr"></div>
<div class="corner bl"></div><div class="corner br"></div>
<div class="header">
  <div class="brand">{cam_name}</div>
  <div class="brand-sub">v1.0 / DIONE</div>
</div>
<div class="sub">// FILE TRANSFER SYSTEM // {file_count} OBJECTS</div>
{download_all}
<div class="divider">DATA STREAM</div>
{file_list}
<div class="count">
  <span>{status_line}</span>
  <span class="accent">[ ONLINE ]</span>
</div>
</body></html>"""

def build_html():
    files = get_files()
    njpg = count_jpg(files)

    if not files:
        fl = '<div class="empty">// NO DATA //</div>'
        dl_all = ""
        status = "STORAGE EMPTY"
    else:
        rows = []
        for fname, sz in files:
            ext = fname.rsplit(".", 1)[-1].upper()
            rows.append(
                f'<div class="file">'
                f'<div class="finfo">'
                f'<span class="tag">{ext}</span>'
                f'<span class="fname">{fname}</span>'
                f'<span class="fsize">{fmt(sz)}</span>'
                f'</div>'
                f'<a class="dl" href="/files/{fname}" download="{fname}">SAVE</a>'
                f'</div>'
            )
        fl = "\n".join(rows)
        if njpg > 0:
            dl_all = f'<a class="btn-all" href="/download_all_jpg">DOWNLOAD ALL JPEG ({njpg})</a>'
        else:
            dl_all = ""
        # Storage info
        try:
            import shutil
            u = shutil.disk_usage(PICTURES_DIR)
            gb = u.free / (1024**3)
            stor = f"{gb:.1f}G FREE" if gb >= 1 else f"{int(u.free/(1024**2))}M FREE"
        except:
            stor = ""
        status = f"{len(files)} FILES // {stor}"

    return HTML_TEMPLATE.format(
        cam_name=_CAM_NAME,
        file_count=len(files),
        download_all=dl_all,
        file_list=fl,
        status_line=status,
    )


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            h = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(h)))
            self.end_headers()
            self.wfile.write(h)

        elif self.path == "/download_all_jpg":
            # Stream ZIP of all JPEGs
            files = get_files()
            jpgs = [(f, os.path.join(PICTURES_DIR, f)) for f, _ in files if f.lower().endswith(".jpg")]
            if not jpgs:
                self.send_error(404, "NO JPEG FILES")
                return
            # Spool the ZIP to a temp file on the SD card instead of RAM:
            # a full gallery of JPEGs easily exceeds the Pi Zero's free
            # memory and an in-RAM BytesIO would OOM-kill the camera.
            import tempfile
            tmp = None
            try:
                tmp = tempfile.NamedTemporaryFile(
                    prefix="saturnix_zip_", suffix=".zip", delete=False)
                with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_STORED) as zf:
                    for fname, fpath in jpgs:
                        zf.write(fpath, fname)
                tmp.close()
                sz = os.path.getsize(tmp.name)
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(sz))
                self.send_header("Content-Disposition", 'attachment; filename="saturnix_photos.zip"')
                self.end_headers()
                with open(tmp.name, "rb") as f:
                    while True:
                        ch = f.read(65536)
                        if not ch:
                            break
                        self.wfile.write(ch)
            except Exception as e:
                print(f"[WARN] ZIP: {e}", flush=True)
                try:
                    self.send_error(500, "ZIP FAILED")
                except Exception:
                    pass
            finally:
                if tmp is not None:
                    try:
                        os.unlink(tmp.name)
                    except OSError:
                        pass

        elif self.path.startswith("/files/"):
            fn = self.path[7:]
            if not _NUM_RE.match(fn):
                self.send_error(404)
                return
            fp = os.path.join(PICTURES_DIR, fn)
            if not os.path.isfile(fp):
                self.send_error(404)
                return
            try:
                sz = os.path.getsize(fp)
                self.send_response(200)
                ct = "image/x-adobe-dng" if fn.lower().endswith(".dng") else "image/jpeg"
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(sz))
                self.send_header("Content-Disposition", f'attachment; filename="{fn}"')
                self.end_headers()
                with open(fp, "rb") as f:
                    while True:
                        ch = f.read(65536)
                        if not ch:
                            break
                        self.wfile.write(ch)
            except:
                pass
        else:
            self.send_error(404)


if __name__ == "__main__":
    os.makedirs(PICTURES_DIR, exist_ok=True)
    s = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[NET] FILE TRANSFER ONLINE :{PORT}", flush=True)
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        s.server_close()
