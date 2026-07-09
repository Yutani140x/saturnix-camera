#!/usr/bin/env python3
# LiveView + UI for Arducam IMX519 — SATURNIX Dione
# Splash → Liveview (auto-hide) → Settings (fullscreen pages) → Gallery → WiFi

import os,sys,time,json,signal,glob,subprocess,shutil,spidev as SPI
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from picamera2 import Picamera2
from libcamera import Transform

_LCD_PATHS=[Path.home()/"Desktop/python",Path(__file__).resolve().parent.parent/"python"]
for _p in _LCD_PATHS:
    if _p.exists():
        if str(_p) not in sys.path: sys.path.append(str(_p))
        break
from lib import LCD_2inch

STILL_W,STILL_H=4656,3496
_HERE=Path(__file__).resolve().parent
PICTURES_DIR=str(_HERE/"Pictures")
HW_JSON=str(_HERE/"config.json")
_startup_time=time.monotonic()

# ---- Load HW config ----
_HW={}
try:
    with open(HW_JSON) as f: _HW=json.load(f)
except: pass
def _hw(k,d): return _HW.get(k,d)
def _hw_rgb(k,d):
    try: r,g,b=_HW[k];return(int(r),int(g),int(b))
    except: return d

# ---- IPC ----
PAUSE_FLAG="/tmp/saturnix_cam_paused";UI_CMD_FILE="/tmp/saturnix_ui_cmd"
SETTINGS_JSON="/tmp/saturnix_settings.json"
AF_STATE_FILE="/tmp/saturnix_af_state";SOUND_MUTE_FLAG="/tmp/saturnix_sound_off"
UI_MODE_FILE="/tmp/saturnix_ui_mode";CONFIG_JSON=str(_HERE/"saturnix_config.json")
FILM_PROGRESS_FILE="/tmp/saturnix_film_progress"

def _flag_set():
    try: os.close(os.open(PAUSE_FLAG,os.O_CREAT|os.O_WRONLY,0o664))
    except: pass
def _flag_clear():
    try: os.remove(PAUSE_FLAG)
    except: pass
def _take_cmd():
    try:
        with open(UI_CMD_FILE) as f: c=f.read().strip().upper()
        os.remove(UI_CMD_FILE)
        return c if c in("LEFT","RIGHT","SELECT","FOCUS_START","FOCUS_STOP","EXIT_TO_LIVE") else None
    except: return None
def _save_stg(d):
    try:
        with open(SETTINGS_JSON,"w") as f: json.dump(d,f)
    except: pass
def _wr_af(s):
    try:
        with open(AF_STATE_FILE,"w") as f: f.write(s)
    except: pass

# ---- Colors (grouped config with backwards compatibility) ----
def _crgb(group,key,default):
    """Read color from grouped config; fallback to old flat keys; then default."""
    try:
        v=_HW.get("colors",{}).get(group,{}).get(key)
        if v: return(int(v[0]),int(v[1]),int(v[2]))
    except: pass
    # Legacy flat keys fallback
    legacy_map={
        ("text","primary"):"ui_text_color",
        ("cursor","fill"):"ui_cursor_color",
        ("background","main"):"ui_bg_color",
        ("accent","primary"):"ui_accent_color",
        ("reticle","color"):"ui_reticle_color",
    }
    lk=legacy_map.get((group,key))
    if lk:
        try:
            v=_HW.get(lk)
            if v: return(int(v[0]),int(v[1]),int(v[2]))
        except: pass
    return default

# Text
C_TEXT=_crgb("text","primary",(240,235,224))
C_TEXT_DIM=_crgb("text","dim",(120,117,112))
C_TEXT_LABEL=_crgb("text","label",(123,167,188))
# Cursor
C_CURSOR=_crgb("cursor","fill",(255,250,240))
C_CURSOR_TEXT=_crgb("cursor","text",(10,14,20))
C_CURSOR_GLOW=_crgb("cursor","glow",(40,56,63))
# Background
C_BG=_crgb("background","main",(10,14,20))
C_BG_PANEL=_crgb("background","panel",(15,20,28))
# Accent
C_ACCENT=_crgb("accent","primary",(123,167,188))
C_WARN=_crgb("accent","warning",(255,0,0))
C_SUCCESS=_crgb("accent","success",(123,167,188))
# Reticle
C_RETICLE=_crgb("reticle","color",(123,167,188))
C_AF_FOCUSING=_crgb("reticle","af_focusing",(123,167,188))
C_AF_FOCUSED=_crgb("reticle","af_focused",(240,235,224))
C_AF_FAILED=_crgb("reticle","af_failed",(60,80,90))
# UI elements
C_GRID=_crgb("ui_elements","grid",(240,235,224))
C_CAL=_crgb("ui_elements","cal_marks",(25,33,38))
C_BAR_FILL=_crgb("ui_elements","bar_meter_fill",(123,167,188))
C_BAR_MARK=_crgb("ui_elements","bar_meter_marker",(255,0,0))
C_PROGRESS=_crgb("ui_elements","progress_bar",(123,167,188))
C_BATTERY=_crgb("ui_elements","battery",(123,167,188))
C_STATIC=_crgb("ui_elements","static_noise",(123,167,188))
C_TRANSITION=_crgb("ui_elements","transition_noise",(240,235,224))
C_TECHNOSPAM=_crgb("ui_elements","technospam",(123,167,188))
C_CORNER=_crgb("ui_elements","corner_marker",(123,167,188))
C_DIVIDER=_crgb("ui_elements","divider",(123,167,188))
C_DYNAMIC=_crgb("ui_elements","dynamic_indicator",(255,0,0))
# Compatibility alias for cursor glow used in UI
C_ACCENT_DIM=C_CURSOR_GLOW
FINAL_ROTATE=_hw("screen_rotation",180)
# Feature toggles
UI_STATIC=_hw("ui_static_noise",True)
UI_TRANSITIONS=_hw("ui_transitions",True)
UI_TECHNOSPAM=_hw("ui_technospam",True)

# ---- LCD ----
disp=LCD_2inch.LCD_2inch(spi=SPI.SpiDev(0,0),spi_freq=90_000_000,rst=27,dc=25,bl=18)
disp.Init();disp.clear();disp.bl_DutyCycle(100)
LCD_W,LCD_H=disp.height,disp.width

# ---- Font: DejaVu Sans Mono Bold 14 (terminal style) ----
def _load_font(size, bold=True):
    paths_bold=["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    paths_reg=["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    paths=paths_bold if bold else paths_reg
    for p in paths:
        try: return ImageFont.truetype(p,size)
        except: pass
    return ImageFont.load_default()

F=_load_font(13,bold=True)
FS=_load_font(10,bold=False)
FT=_load_font(24,bold=True)

def _tw(d,t,f=None):
    if f is None: f=F
    try: x0,y0,x1,y1=d.textbbox((0,0),t,font=f);return(x1-x0,y1-y0)
    except: return(len(t)*8,14)
def _el(d,t,mw,f=None):
    if f is None: f=F
    w,_=_tw(d,t,f)
    if w<=mw: return t
    k=max(3,int(len(t)*mw/max(w,1))-2);s=t[:k]+".."
    while _tw(d,s,f)[0]>mw and k>3: k-=1;s=t[:k]+".."
    return s

# ---- Splash ----
def _splash():
    from PIL import ImageEnhance
    import random as _srnd
    def _add_splash_noise(img,density=60):
        """Add static noise to a splash frame."""
        d=ImageDraw.Draw(img)
        col=C_STATIC
        col_dim=tuple(c//2 for c in C_STATIC)
        for _ in range(density):
            x=_srnd.randint(0,LCD_W-1);y=_srnd.randint(0,LCD_H-1)
            d.point((x,y),fill=col if _srnd.random()<0.5 else col_dim)
    def _final(img):
        if FINAL_ROTATE==90: img=img.transpose(Image.ROTATE_90)
        elif FINAL_ROTATE==180: img=img.transpose(Image.ROTATE_180)
        elif FINAL_ROTATE==270: img=img.transpose(Image.ROTATE_270)
        return img
    def show_jpg(name,dur):
        p=_HERE/name
        if not p.exists(): return False
        try:
            img=Image.open(str(p)).convert("RGB").resize((LCD_W,LCD_H),Image.LANCZOS)
            _add_splash_noise(img,80)
            disp.ShowImage(_final(img))
            time.sleep(dur);return True
        except: return False
    # Frame 1: splash.jpg with CRT warm-up fade-in
    sp=_HERE/"splash.jpg"
    if sp.exists():
        try:
            base=Image.open(str(sp)).convert("RGB").resize((LCD_W,LCD_H),Image.LANCZOS)
            enh=ImageEnhance.Brightness(base)
            # CRT warm-up: 10 steps, 0→1.0 brightness, with noise on each frame
            for i in range(11):
                b=i/10.0
                fr=enh.enhance(b).copy()
                _add_splash_noise(fr,80)
                disp.ShowImage(_final(fr))
                time.sleep(0.12)
            # Hold full brightness with refreshing noise
            for _ in range(5):
                fr=base.copy()
                _add_splash_noise(fr,80)
                disp.ShowImage(_final(fr))
                time.sleep(0.10)
        except:
            # Fallback to text
            img=Image.new("RGB",(LCD_W,LCD_H),C_BG);d=ImageDraw.Draw(img)
            tw,th=_tw(d,"SATURNIX",FT);d.text(((LCD_W-tw)//2,(LCD_H-th)//2),"SATURNIX",font=FT,fill=C_TEXT)
            _add_splash_noise(img,80)
            disp.ShowImage(_final(img));time.sleep(2.0)
    else:
        # No splash image — show text
        img=Image.new("RGB",(LCD_W,LCD_H),C_BG);d=ImageDraw.Draw(img)
        tw,th=_tw(d,"SATURNIX",FT);d.text(((LCD_W-tw)//2,(LCD_H-th)//2),"SATURNIX",font=FT,fill=C_TEXT)
        _add_splash_noise(img,80)
        disp.ShowImage(_final(img));time.sleep(2.0)
    # Frame 2: LantianOS.jpg with noise
    show_jpg("LantianOS.jpg",1.5)

# ---- Camera ----
def open_cam():
    cam=Picamera2()
    cam.configure(cam.create_preview_configuration(main={"format":"BGR888","size":(LCD_W,LCD_H)},
                  transform=Transform(rotation=0),buffer_count=2))
    cam.start();return cam

def make_still_config(cam):
    """Build full-resolution still config for inline capture."""
    return cam.create_still_configuration(
        main={"size":(STILL_W,STILL_H)},
        raw={"size":(STILL_W,STILL_H)},
        buffer_count=1)

# ---- Signals ----
want_pause=want_resume=want_exit=False
signal.signal(signal.SIGUSR1,lambda*_:globals().__setitem__("want_pause",True))
signal.signal(signal.SIGUSR2,lambda*_:globals().__setitem__("want_resume",True))
signal.signal(signal.SIGINT,lambda*_:globals().__setitem__("want_exit",True))
signal.signal(signal.SIGTERM,lambda*_:globals().__setitem__("want_exit",True))

# ---- Inline capture (no subprocess, no full restart) ----
CAPTURE_REQUEST_FILE="/tmp/saturnix_capture_request"
CAPTURED_FLAG="/tmp/saturnix_captured"
CAPTURE_DONE_FLAG="/tmp/saturnix_capture_done"
_capture_busy=False
_film_thread=None
_film_phase=False  # True while film/effects post-processing is running (separate from raw capture)

# Burst state
_burst_active=False
_burst_count=0
_burst_total=0
_burst_abort=False

# Self-timer state
_timer_active=False
_timer_end_t=0.0
_timer_total=0
_timer_last_tick=-1
_timer_abort=False

# Battery critical alert state
_bat_critical_t=0.0
_bat_critical_announced=False
_bat_shutdown_initiated=False
_bat_low_first_t=0.0  # first time a <=shutdown reading was seen (two-strike)

def _next_capture_path():
    """Return (jpg_path, dng_path, stem) for next capture."""
    os.makedirs(PICTURES_DIR,exist_ok=True)
    import re as _re
    rx=_re.compile(r'^Saturnix_(\d+)\.(jpg|dng)$',_re.IGNORECASE)
    n=0
    for f in os.listdir(PICTURES_DIR):
        m=rx.match(f)
        if m:
            try: n=max(n,int(m.group(1))+1)
            except: pass
    stem=f"Saturnix_{n:02d}"
    return (os.path.join(PICTURES_DIR,stem+".jpg"),
            os.path.join(PICTURES_DIR,stem+".dng"), stem)

def _process_film_async(jpg_path,film_name):
    """Run film processing in background thread (used by Dynamic mode)."""
    global _film_thread
    import threading
    try:
        sys.path.insert(0,str(_HERE))
        import capture as _cap
        def _run():
            global _film_phase
            _film_phase=True
            try:_cap.process_film(jpg_path,film_name)
            except Exception as e:print(f"[FILM] err: {e}",flush=True)
            _film_phase=False
        _film_thread=threading.Thread(target=_run,daemon=True)
        _film_thread.start()
    except Exception as e:
        print(f"[FILM] import err: {e}",flush=True)


# ---- Native in-process still capture (no camera restart) ----
# Uses picamera2.switch_mode_and_capture_request: the preview pipeline is
# reconfigured to full resolution, one request is captured, and the camera
# returns to preview automatically. AE/AWB/AF state carries over, so
# shot-to-shot time drops from seconds to well under a second.
# Requires enough CMA for the full-res buffers (see setup_fast_boot.sh).
# On ANY failure we fall back to the legacy rpicam-still subprocess path.
_NATIVE_STILL = True
try:
    with open(str(_HERE/"config.json")) as _f:
        _NATIVE_STILL = bool(json.load(_f).get("native_still", True))
except: pass

def _native_still_capture(cam, jpg, dng, stem, mode, film):
    """Returns True on success. Raises on failure (caller falls back)."""
    global _capture_busy, _film_phase, _film_thread
    st = {}
    try:
        with open(SETTINGS_JSON) as f: st = json.load(f)
    except: pass

    # Long exposures need FrameDurationLimits plumbing — keep them on the
    # battle-tested subprocess path for now.
    exp_us = st.get("exposure_us")
    if exp_us is not None and exp_us > 1_000_000:
        raise RuntimeError("long exposure -> legacy path")

    want_raw = mode in ("JPG+DNG", "DNG")
    if want_raw:
        cfg = cam.create_still_configuration(
            main={"size": (STILL_W, STILL_H)},
            raw={"size": (STILL_W, STILL_H)},
            buffer_count=1)
    else:
        cfg = cam.create_still_configuration(
            main={"size": (STILL_W, STILL_H)},
            buffer_count=1)

    try: cam.options["quality"] = int(st.get("jpeg_quality", 85))
    except: pass

    # Show the REC "do not move" squares BEFORE the blocking capture:
    # this call runs synchronously in the main loop, which therefore
    # cannot render the animation itself until the request returns.
    try:
        _fr = Image.new("RGB", (LCD_W, LCD_H), C_BG)
        draw_rec_anim(_fr)
        if FINAL_ROTATE == 90: _fr = _fr.transpose(Image.ROTATE_90)
        elif FINAL_ROTATE == 180: _fr = _fr.transpose(Image.ROTATE_180)
        elif FINAL_ROTATE == 270: _fr = _fr.transpose(Image.ROTATE_270)
        disp.ShowImage(_fr)
    except: pass

    # Film presets lock the preview's white balance (FILM_WB gains).
    # The still must be captured with NEUTRAL auto WB — the film's own
    # color grade is applied afterwards in process_film(). Otherwise the
    # look is applied twice and photos come out badly tinted.
    if film != "Off" and st.get("awb_auto", True):
        try:
            cam.set_controls({"AwbEnable": True})
            time.sleep(0.35)   # a few frames for AWB to settle
        except: pass

    t0 = time.monotonic()
    req = cam.switch_mode_and_capture_request(cfg)
    # The exposure is complete the moment the request returns — the user may
    # move the camera NOW; encode/save continue in the background.
    try:
        with open(CAPTURED_FLAG, "w") as f: f.write("1")
    except: pass
    print(f"[CAP] {stem} native capture in {time.monotonic()-t0:.2f}s", flush=True)

    # JPEG encode, DNG write, film and EXIF all run in a background thread —
    # the main loop keeps animating (PROC circles) meanwhile.
    def _post():
        global _film_phase, _capture_busy
        _film_phase = True
        try:
            try:
                if mode != "DNG":
                    req.save("main", jpg)
                if want_raw:
                    req.save_dng(dng)
            finally:
                req.release()
            sys.path.insert(0, str(_HERE))
            import capture as _cap
            if film != "Off" and mode != "DNG" and os.path.exists(jpg):
                _cap.process_film(jpg, film)
            if mode != "DNG" and os.path.exists(jpg):
                _cap._add_exif_and_watermark(jpg)
        except Exception as e:
            print(f"[CAP] post-process err: {e}", flush=True)
        _film_phase = False
        try:
            with open(CAPTURE_DONE_FLAG, "w") as f: f.write("1")
        except: pass
        _capture_busy = False   # allow the next shot only when fully done

    import threading as _th
    _th.Thread(target=_post, daemon=True).start()
    return True

def _inline_capture(cam_ref):
    """Capture handler. For Dynamic — synchronous (instant).
    For JPG/DNG/JPG+DNG — starts subprocess in background thread so main loop
    can continue rendering REC animation."""
    global _capture_busy
    if _capture_busy: return cam_ref[0]
    _capture_busy=True
    try:
        try: os.remove(CAPTURED_FLAG)
        except: pass
        try: os.remove(CAPTURE_DONE_FLAG)
        except: pass

        cam=cam_ref[0]
        jpg,dng,stem=_next_capture_path()
        mode=s_mode
        film=s_film
        print(f"[CAP] {stem} mode={mode} film={film}",flush=True)

        if mode=="Dynamic":
            # Synchronous instant capture from preview
            t0=time.monotonic()
            cam.capture_file(jpg,format="jpeg")
            dt=time.monotonic()-t0
            print(f"[CAP] {stem} captured in {dt:.2f}s",flush=True)
            try:
                with open(CAPTURED_FLAG,"w") as f: f.write("1")
            except: pass
            if film!="Off" and os.path.exists(jpg):
                # Film async — busy clears in _check_film_done
                _process_film_async(jpg,film)
            else:
                try:
                    with open(CAPTURE_DONE_FLAG,"w") as f: f.write("1")
                except: pass
            _capture_busy=False
            return cam_ref[0]

        # JPG / DNG / JPG+DNG — try the native in-process path first
        if _NATIVE_STILL and cam is not None and s_hdr=="Off":
            try:
                _native_still_capture(cam, jpg, dng, stem, mode, film)
                return cam_ref[0]
            except Exception as e:
                print(f"[CAP] native path failed ({e}) -> subprocess fallback", flush=True)
                # camera state may be dirty after a failed switch — rebuild it
                try: cam.stop()
                except: pass
                try: cam.close()
                except: pass
                cam_ref[0]=None
                try:
                    cam=open_cam();_apply_cam(cam);cam_ref[0]=cam
                except Exception:
                    cam=None

        # JPG / DNG / JPG+DNG — async subprocess path
        # Stop and close camera in main thread (must be done synchronously
        # before subprocess starts, else camera conflict)
        if cam is not None:
            try: cam.stop()
            except: pass
            try: cam.close()
            except: pass
        cam_ref[0]=None

        # Launch subprocess in background thread — main loop keeps rendering
        import threading,subprocess as _sp
        def _run_capture():
            global _film_phase
            t0=time.monotonic()
            try:
                cap_script=str(_HERE/"capture.py")
                _sp.run(["python3","-u",cap_script],cwd=str(_HERE),
                        check=True,timeout=60)
            except _sp.CalledProcessError as e:
                print(f"[CAP] subprocess err rc={e.returncode}",flush=True)
            except _sp.TimeoutExpired:
                print(f"[CAP] subprocess timeout",flush=True)
            except Exception as e:
                print(f"[CAP] subprocess fail: {e}",flush=True)
            dt=time.monotonic()-t0
            print(f"[CAP] {stem} captured in {dt:.2f}s",flush=True)
            try:
                with open(CAPTURED_FLAG,"w") as f: f.write("1")
            except: pass
            # Film post-processing — switch to PROC phase so main loop shows circles
            if film!="Off" and os.path.exists(jpg):
                _film_phase=True
                try:
                    sys.path.insert(0,str(_HERE))
                    import capture as _capm
                    _capm.process_film(jpg,film)
                except Exception as e:
                    print(f"[FILM] err: {e}",flush=True)
                _film_phase=False
            try:
                with open(CAPTURE_DONE_FLAG,"w") as f: f.write("1")
            except: pass

        global _capture_thread
        _capture_thread=threading.Thread(target=_run_capture,daemon=True)
        _capture_thread.start()
        # _capture_busy stays True; main loop will check thread and reopen cam after
    except Exception as e:
        print(f"[CAP] ERROR: {e}",flush=True)
        try:
            with open(CAPTURE_DONE_FLAG,"w") as f: f.write("1")
        except: pass
        _capture_busy=False
    return cam_ref[0]

_capture_thread=None

def _check_capture_done(cam_ref):
    """Called from main loop. If subprocess capture thread finished, reopen cam.
    Returns updated cam (or None if reopen failed)."""
    global _capture_busy,_capture_thread
    if _capture_thread is None: return cam_ref[0]
    if _capture_thread.is_alive(): return cam_ref[0]
    # Thread finished: reopen preview camera
    _capture_thread=None
    try:
        cam=open_cam()
        _apply_cam(cam)
        cam_ref[0]=cam
    except Exception as e:
        print(f"[CAP] preview reopen failed: {e}",flush=True)
        time.sleep(0.5)
        try:
            cam=open_cam();_apply_cam(cam);cam_ref[0]=cam
        except Exception as e2:
            print(f"[CAP] preview reopen retry failed: {e2}",flush=True)
            cam_ref[0]=None
    _capture_busy=False
    return cam_ref[0]

def _check_film_done():
    """If film thread finished, write done flag."""
    global _film_thread
    if _film_thread and not _film_thread.is_alive():
        _film_thread=None
        try:
            with open(CAPTURE_DONE_FLAG,"w") as f: f.write("1")
        except: pass

def _fast_burst(cam_ref,n):
    """Fast burst capture for Dynamic mode.
    A: Freezes AE/AWB before burst (no convergence between frames).
    C: Captures arrays into RAM, writes JPGs to disk after.
    Returns when complete or aborted."""
    global _burst_active,_burst_count,_burst_total,_burst_abort,_capture_busy
    cam=cam_ref[0]
    _burst_active=True
    _burst_total=n
    _burst_count=0
    _burst_abort=False
    _capture_busy=True

    # Show REC frame before locking the loop
    try:
        _fr=Image.new("RGB",(LCD_W,LCD_H),C_BG)
        draw_rec_anim(_fr)
        if FINAL_ROTATE==90:_fr=_fr.transpose(Image.ROTATE_90)
        elif FINAL_ROTATE==180:_fr=_fr.transpose(Image.ROTATE_180)
        elif FINAL_ROTATE==270:_fr=_fr.transpose(Image.ROTATE_270)
        disp.ShowImage(_fr)
    except: pass

    # ---- A: Freeze AE/AWB ----
    saved_ctrls=None
    try:
        meta=cam.capture_metadata()
        exp=meta.get("ExposureTime")
        gain=meta.get("AnalogueGain")
        cgains=meta.get("ColourGains")
        lock={"AeEnable":False,"AwbEnable":False}
        if exp is not None: lock["ExposureTime"]=int(exp)
        if gain is not None: lock["AnalogueGain"]=float(gain)
        if cgains is not None: lock["ColourGains"]=tuple(cgains)
        cam.set_controls(lock)
        saved_ctrls=True
    except Exception as e:
        print(f"[BURST] AE freeze failed: {e}",flush=True)

    # ---- C: Tight capture loop into RAM ----
    arrays=[]
    try:
        for i in range(n):
            if _burst_abort: break
            try:
                arr=cam.capture_array("main")
                arrays.append(arr)
                _burst_count=i+1
                print(f"[BURST] frame {_burst_count}/{n}",flush=True)
            except Exception as e:
                print(f"[BURST] capture frame {i+1} err: {e}",flush=True)
    finally:
        # Restore AE/AWB
        if saved_ctrls:
            try: cam.set_controls({"AeEnable":True,"AwbEnable":True})
            except: pass

    # Write all arrays to disk as JPGs
    print(f"[BURST] writing {len(arrays)} files to disk...",flush=True)
    for arr in arrays:
        try:
            jpg,_,stem=_next_capture_path()
            img=Image.fromarray(arr)
            img.save(jpg,format="JPEG",quality=int(s_jpq))
        except Exception as e:
            print(f"[BURST] write err: {e}",flush=True)

    _burst_active=False;_burst_count=0;_burst_total=0;_burst_abort=False
    _capture_busy=False
    try:
        with open(CAPTURED_FLAG,"w") as f: f.write("1")
        with open(CAPTURE_DONE_FLAG,"w") as f: f.write("1")
    except: pass
    print(f"[BURST] done",flush=True)

def _check_capture_request(cam_ref):
    """Check for capture request file. If present, perform inline capture
    (single shot, burst sequence, or start timer countdown).
    Returns possibly-replaced camera object."""
    global _burst_abort,_timer_active,_timer_end_t,_timer_total,_timer_last_tick,_timer_abort
    if not os.path.exists(CAPTURE_REQUEST_FILE):
        return cam_ref[0]
    try: os.remove(CAPTURE_REQUEST_FILE)
    except: pass

    # If timer already counting down, second press aborts it
    if _timer_active:
        _timer_abort=True
        return cam_ref[0]

    # If timer set, start countdown — actual capture triggered by main loop when 0 reached
    if s_timer!="Off":
        try:
            secs=int(s_timer)
            if secs>0:
                _timer_active=True
                _timer_total=secs
                _timer_end_t=time.monotonic()+secs
                _timer_last_tick=-1
                _timer_abort=False
                return cam_ref[0]
        except: pass

    # No timer — capture immediately
    return _do_capture_now(cam_ref)

def _do_capture_now(cam_ref):
    """Perform actual capture (burst if Dynamic+burst, otherwise single)."""
    # Burst mode: only when Dynamic + burst configured
    if s_mode=="Dynamic" and s_burst!="Off":
        try:
            n=int(s_burst)
            if n>1:
                _fast_burst(cam_ref,n)
                return cam_ref[0]
        except: pass
    return _inline_capture(cam_ref)

def _step_timer(cam_ref):
    """Called from main loop. Advances timer countdown, plays ticks,
    triggers capture when 0 reached. Returns cam (possibly updated)."""
    global _timer_active,_timer_last_tick,_timer_abort
    if not _timer_active: return cam_ref[0]
    if _timer_abort:
        _timer_active=False;_timer_abort=False
        return cam_ref[0]
    now=time.monotonic()
    remaining=_timer_end_t-now
    sec_int=int(remaining+0.999)  # ceiling so it shows 5,4,3,2,1
    if sec_int<=0:
        # Time's up — capture now
        _timer_active=False
        try: import buzzer as _bz;_bz.timer_done()
        except: pass
        return _do_capture_now(cam_ref)
    # Tick on each new whole second
    if sec_int!=_timer_last_tick:
        _timer_last_tick=sec_int
        try: import buzzer as _bz;_bz.timer_tick()
        except: pass
    return cam_ref[0]

def _step_burst(cam_ref):
    """No-op now — burst runs synchronously in _fast_burst.
    Kept for main-loop compatibility."""
    return cam_ref[0]

# ======================================================================
#                          UI MODEL
# ======================================================================
SHUTTER_OPT=_hw("shutter_options",["Auto","30s","15s","8s","4s","2s","1s","1/2","1/4","1/8","1/15","1/30","1/60","1/125","1/250","1/500","1/1000","1/2000","1/4000"])
ISO_OPT=_hw("iso_options",["Auto",100,200,400,800,1600,3200])
WB_OPT=_hw("wb_options",["Auto","Daylight","Cloudy","Tungsten","Fluorescent","Shade"])
EV_OPT=_hw("ev_options",[-3.0,-2.0,-1.0,0.0,1.0,2.0,3.0])
DN_OPT=_hw("denoise_options",["Auto","Off","Fast","HQ"])
JPG_OPT=_hw("jpeg_quality_options",[1,10,20,70,80,85,90,95,100])
AF_OPT=_hw("focus_options",["AF-C","AF-S","MF"])
MODE_OPT=_hw("mode_options",["JPG+DNG","JPG","Dynamic"])
GRID_OPT=_hw("grid_options",["Off","Thirds","Golden","Cross"])
FILM_OPT=_hw("film_options",["Off","S-Saturnix","S-Gold","S-Vivid","S-Natural","S-MonoX","VHS"])
VOL_OPT=["OFF","LOW","MED","HIGH"]
GDNG_OPT=["Off","On"]
BURST_OPT=_hw("burst_options",["Off",3,5,10,20])
HDR_OPT=_hw("hdr_options",["Off","3-FILES","MERGED"])
TIMER_OPT=_hw("timer_options",["Off",2,5,10])
WM_OPT=_hw("watermark_options",["Off","On"])
BURST_INTERVAL_MS=int(_hw("burst_interval_ms",150))
STORAGE_WARN_MB=int(_hw("storage_warning_mb",500))
BAT_CRITICAL_PCT=int(_hw("battery_critical_pct",5))
BAT_SHUTDOWN_PCT=int(_hw("battery_shutdown_pct",3))
# Set to false in config.json for builds without a battery/UPS: disables
# both the low-battery beeps and the automatic shutdown.
BAT_AUTO_SHUTDOWN=bool(_hw("battery_auto_shutdown",True))

MAIN_MENU=["Shutter","ISO","WB","EV","Film","Settings"]
_SECTION_PREFIX="──"
SET_ITEMS=[
    "── CAPTURE ──",
    "MODE","BURST","HDR","TIMER","JPEG","GALDNG","FOCUS",
    "── IMAGE ──",
    "DENOISE","GRID","WATERMARK",
    "── SYSTEM ──",
    "VOLUME","NETWORK INTERFACE","GALLERY","SYSTEM DIAGNOSTIC",
    "── DANGER ──",
    "PURGE DATA","SHUTDOWN",
    "BACK",
]
_S_SUB={"DENOISE","JPEG","FOCUS","MODE","GRID","VOLUME","GALDNG","BURST","HDR","TIMER","WATERMARK"}
_S_ACT={"NETWORK INTERFACE","GALLERY","SYSTEM DIAGNOSTIC","PURGE DATA","SHUTDOWN","BACK"}

s_shut="Auto";s_iso="Auto";s_wb="Auto";s_ev=0.0
s_dn="Auto";s_jpq=85;s_af="AF-C";s_mode="JPG+DNG"
s_grid="Off";s_film="Off";s_vol="MED";s_gdng="Off";s_burst="Off"
s_hdr="Off";s_timer="Off";s_wm="Off"

ui_idx=0;ui_mode="main";sub_idx=0;set_idx=0
_ui_mode_written=None  # last value written to UI_MODE_FILE
set_sub_items=[];set_sub_cur=0

# ---- Cursor animation ----
_cur_state="static";_cur_vis=True;_cur_blink_t=0.0;_cur_confirm_n=0
def _cur_reset():
    global _cur_state,_cur_vis,_cur_confirm_n
    _cur_state="static";_cur_vis=True;_cur_confirm_n=0
def _cur_move():
    global _cur_state,_cur_vis,_cur_blink_t
    _cur_state="move";_cur_vis=False;_cur_blink_t=time.monotonic()
def _cur_start_active():
    global _cur_state,_cur_blink_t
    _cur_state="active";_cur_blink_t=time.monotonic()
def _cur_update():
    global _cur_vis,_cur_blink_t,_cur_confirm_n,_cur_state
    now=time.monotonic()
    if _cur_state=="static":_cur_vis=True
    elif _cur_state=="move":
        if now-_cur_blink_t>=0.18:_cur_state="static";_cur_vis=True
    elif _cur_state=="confirm":
        if now-_cur_blink_t>=0.04:_cur_vis=not _cur_vis;_cur_blink_t=now
        if not _cur_vis:_cur_confirm_n+=1
        if _cur_confirm_n>=4:_cur_state="static";_cur_vis=True
    elif _cur_state=="active":
        if now-_cur_blink_t>=0.25:_cur_vis=not _cur_vis;_cur_blink_t=now

mf_lp=0.0;MF_S=0.2;MF_MIN=0.0;MF_MAX=10.0
focus_held=False;af_state="idle"
af_blink=True;_af_bt=0.0;AF_BP=0.3
_af_change_t=0.0;AF_AUTO_HIDE_S=1.5  # auto-hide AF indicator after state change

gal_files=[];gal_idx=0;gal_act=0
GAL_ACT=["DELETE","BACK"]
gal_del_confirm=False;gal_del_sel=1
_gc_idx=-1;_gc_img=None

# Delete All state
del_all_confirm=False;del_all_sel=1

poff=False;poff_sel=1
WIFI_SSID=_hw("wifi_ssid","SaturnixCam");WIFI_PASS=_hw("wifi_password","saturnix24");WIFI_ADDR=_hw("wifi_address","192.168.4.1");WIFI_IF=_hw("wifi_interface","wlan0")
wifi_on=False;wifi_act=0;_wifi_p=None

FILM_PRE={"SATURNIX":{"Saturation":1.4,"Contrast":1.2,"Sharpness":0.6},
           "S-Gold":{"Saturation":1.3,"Contrast":1.05,"Sharpness":0.7},
           "S-Vivid":{"Saturation":1.85,"Contrast":1.5,"Sharpness":1.5},
           "S-Natural":{"Saturation":1.2,"Contrast":1.1,"Sharpness":0.9},
           "S-MonoX":{"Saturation":0.0,"Contrast":1.4,"Sharpness":1.2},
           "S-Saturnix":{"Saturation":1.28,"Contrast":1.04,"Sharpness":0.6},
           "VHS":{"Saturation":0.7,"Contrast":0.85,"Sharpness":0.3}}
FILM_WB={"SATURNIX":(1.7,1.25),"S-Gold":(1.8,1.2),"S-Vivid":(1.5,1.55),
         "S-Natural":(1.4,1.7),"S-MonoX":(1.5,1.5),"S-Saturnix":(1.9,1.55),
         "VHS":(1.6,1.3)}
FILM_NM={"SATURNIX":"SATURNIX","S-Gold":"S-GOLD 400","S-Vivid":"S-VIVID 100",
         "S-Natural":"S-NATURAL 400","S-MonoX":"S-MONOX 400",
         "S-Saturnix":"S-SATURNIX","VHS":"VHS TAPE"}
# Legacy film names from old saved configs -> canonical names
FILM_ALIASES={"Gold":"S-Gold","Ektar":"S-Vivid","Fuji":"S-Natural","TriX":"S-MonoX",
              "S-Anime":"S-Saturnix"}

AUTO_HIDE=float(_hw("auto_hide_seconds",15));_last_act=time.monotonic();_ui_hid=False
_stor_t="";_stor_nx=0.0

# ---- Config ----
def _save_cfg():
    try:
        with open(CONFIG_JSON,"w") as f:
            json.dump({"shutter":s_shut,"iso":s_iso,"wb":s_wb,"ev":s_ev,
                "denoise":s_dn,"jpegq":s_jpq,"focus":s_af,"mode":s_mode,
                "grid":s_grid,"film":s_film,"volume":s_vol,
                "galdng":s_gdng,"burst":s_burst,
                "hdr":s_hdr,"timer":s_timer,"watermark":s_wm,
                "mf_lens_pos":mf_lp},f,indent=2)
    except: pass

def _load_cfg():
    global s_shut,s_iso,s_wb,s_ev,s_dn,s_jpq,s_af,s_mode,s_grid,s_film,s_vol,s_gdng,s_burst,s_hdr,s_timer,s_wm,mf_lp
    try:
        with open(CONFIG_JSON) as f: c=json.load(f)
    except: return
    def pk(k,o,cur): v=c.get(k,cur);return v if v in o else cur
    s_shut=pk("shutter",SHUTTER_OPT,s_shut);s_iso=pk("iso",ISO_OPT,s_iso)
    s_wb=pk("wb",WB_OPT,s_wb);s_dn=pk("denoise",DN_OPT,s_dn)
    s_af=pk("focus",AF_OPT,s_af);s_mode=pk("mode",MODE_OPT,s_mode)
    s_grid=pk("grid",GRID_OPT,s_grid)
    try: c["film"]=FILM_ALIASES.get(c.get("film"),c.get("film"))
    except: pass
    s_film=pk("film",FILM_OPT,s_film);s_vol=pk("volume",VOL_OPT,s_vol)
    s_gdng=pk("galdng",GDNG_OPT,s_gdng);s_burst=pk("burst",BURST_OPT,s_burst)
    s_hdr=pk("hdr",HDR_OPT,s_hdr);s_timer=pk("timer",TIMER_OPT,s_timer)
    s_wm=pk("watermark",WM_OPT,s_wm)
    try: v=float(c.get("ev",0));s_ev=v if v in EV_OPT else 0.0
    except: pass
    try: v=int(c.get("jpegq",85));s_jpq=v if v in JPG_OPT else 85
    except: pass
    try: mf_lp=max(0.0,min(10.0,float(c.get("mf_lens_pos",0.0))))
    except: pass
    if s_vol=="OFF":
        try:
            with open(SOUND_MUTE_FLAG,"w") as f: f.write("1")
        except: pass
    else:
        try: os.remove(SOUND_MUTE_FLAG)
        except: pass

def _get_stor():
    global _stor_t,_stor_nx
    now=time.monotonic()
    if now<_stor_nx: return _stor_t
    _stor_nx=now+5
    try:
        u=shutil.disk_usage(PICTURES_DIR);gb=u.free/(1024**3)
        _stor_t=f"{gb:.1f}G" if gb>=1 else f"{int(u.free/(1024**2))}M"
    except: _stor_t="?"
    return _stor_t

_stor_low=False
_stor_warn_shown_t=0.0
_stor_warn_active=False
def _check_storage_low():
    """Returns True if storage is below threshold. Triggers one-shot popup
    notification when crossing the threshold."""
    global _stor_low,_stor_warn_shown_t,_stor_warn_active
    try:
        u=shutil.disk_usage(PICTURES_DIR)
        free_mb=u.free/(1024*1024)
        was_low=_stor_low
        _stor_low=free_mb<STORAGE_WARN_MB
        if _stor_low and not was_low:
            _stor_warn_shown_t=time.monotonic()
            _stor_warn_active=True
        if _stor_warn_active and time.monotonic()-_stor_warn_shown_t>3.0:
            _stor_warn_active=False
        return _stor_low
    except:
        return False

def _check_battery_critical():
    """Monitor battery level. Plays warning sound at <CRITICAL_PCT,
    initiates shutdown at <SHUTDOWN_PCT. Skipped while charging."""
    global _bat_critical_t,_bat_critical_announced,_bat_shutdown_initiated
    if not BAT_AUTO_SHUTDOWN: return
    if _bat_shutdown_initiated: return
    pct,charging=_get_battery()
    if charging:
        # Reset state when charging — user knows about issue
        _bat_critical_announced=False
        globals()["_bat_low_first_t"]=0.0
        return
    now=time.monotonic()
    # Critical shutdown threshold — require a CONFIRMED second low reading
    # >=15s after the first, so one bad I2C sample can't power off the camera.
    global _bat_low_first_t
    if pct<=BAT_SHUTDOWN_PCT:
        if _bat_low_first_t==0.0:
            _bat_low_first_t=now
            return
        if now-_bat_low_first_t<15.0:
            return
        _bat_shutdown_initiated=True
        try:
            import buzzer as _bz
            _bz.battery_critical()
        except: pass
        try: import logger as _lg;_lg.error(f"Battery shutdown at {pct}%")
        except: pass
        # Save config and shutdown
        try: _save_cfg()
        except: pass
        os.system("sudo shutdown -h now")
        return
    else:
        _bat_low_first_t=0.0  # reading recovered — clear the first strike
    # Critical warning threshold — beep every 30 seconds
    if pct<=BAT_CRITICAL_PCT:
        if not _bat_critical_announced or (now-_bat_critical_t)>30.0:
            _bat_critical_announced=True
            _bat_critical_t=now
            try:
                import buzzer as _bz
                _bz.battery_critical()
            except: pass

_cpu_t="";_cpu_nx=0.0
def _get_cpu():
    global _cpu_t,_cpu_nx
    now=time.monotonic()
    if now<_cpu_nx: return _cpu_t
    _cpu_nx=now+3
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp=int(f.read().strip())//1000
        with open("/proc/loadavg") as f:
            load=f.read().split()[0]
        _cpu_t=f"{temp}C {load}"
    except: _cpu_t=""
    return _cpu_t

def _uptime():
    s=int(time.monotonic()-_startup_time)
    h,r=divmod(s,3600);m,sec=divmod(r,60)
    return f"{h:02d}:{m:02d}:{sec:02d}"

# UPS HAT integration — try to import and init INA219
try:
    import ups as _ups
    _ups.init(addr=0x43, bus_num=1)
except Exception as _e:
    print(f"[LV] UPS module load failed: {_e}", flush=True)
    _ups=None

def _get_battery():
    """Returns (percent, charging). Reads from UPS HAT INA219 if available."""
    if _ups and _ups.is_available():
        pct, chg, _v = _ups.get_status()
        return (pct, chg)
    return (60, False)  # fallback if UPS not detected

def _bat_icon(pct):
    """Symbolic battery: 5 cells. ▮ filled, ▯ empty."""
    cells=max(0,min(5,int(round(pct/20.0))))
    return "▮"*cells+"▯"*(5-cells)

# ======================================================================
#                     CAMERA
# ======================================================================
def _shut_us(s):
    if s=="Auto": return None
    if s.endswith("s"): return int(float(s[:-1])*1e6)
    if "/" in s: n,d=s.split("/");return int(int(n)/int(d)*1e6)
    return None
WB_G={"Auto":None,"Daylight":(2.0,1.5),"Cloudy":(1.9,1.5),
      "Tungsten":(1.4,2.2),"Fluorescent":(1.7,1.8),"Shade":(2.2,1.4)}
DN_M={"off":0,"fast":1,"hq":2,"auto":3}

def _fm(): return "afc" if s_af=="AF-C" else "afs" if s_af=="AF-S" else "mf"
def _apply_af(cam):
    fm=_fm()
    try:
        if fm=="afc": cam.set_controls({"AfMode":2})
        elif fm=="afs": cam.set_controls({"AfMode":0})  # manual hold; trigger on button
        else: cam.set_controls({"AfMode":0,"LensPosition":float(mf_lp)})
    except: pass

def _apply_cam(cam):
    eu=_shut_us(s_shut);g=None
    if s_iso!="Auto": g=max(1.0,min(32.0,int(s_iso)/100.0))
    c={};ev=float(s_ev)
    if eu is None and g is None: c["AeEnable"]=True;c["ExposureValue"]=ev
    elif eu is not None and g is not None:
        c["AeEnable"]=False;c["ExposureTime"]=int(max(100,min(30e6,eu*(2**ev))));c["AnalogueGain"]=float(g)
    elif eu is not None: c["AeEnable"]=True;c["ExposureTime"]=int(max(100,min(30e6,eu*(2**ev))));c["ExposureValue"]=ev
    else: c["AeEnable"]=True;c["AnalogueGain"]=float(g);c["ExposureValue"]=ev
    if s_film!="Off" and s_film in FILM_WB: c["AwbEnable"]=False;c["ColourGains"]=FILM_WB[s_film]
    else:
        wb=WB_G.get(s_wb)
        if wb is None: c["AwbEnable"]=True
        else: c["AwbEnable"]=False;c["ColourGains"]=wb
    if s_film!="Off": c["NoiseReductionMode"]=0
    else:
        m=DN_M.get(s_dn.lower())
        if m is not None: c["NoiseReductionMode"]=m
    if s_film!="Off" and s_film in FILM_PRE:
        for k,v in FILM_PRE[s_film].items(): c[k]=float(v)
    else:
        # Reset film preview controls to defaults
        c["Saturation"]=1.0;c["Contrast"]=1.0;c["Sharpness"]=1.0
    try: cam.set_controls(c)
    except: pass
    _apply_af(cam)
    wb=WB_G.get(s_wb)
    _save_stg({"exposure_us":eu,"gain":g,"ev":ev,"awb_auto":wb is None,"wb_gains":wb,
        "denoise":s_dn.lower(),"jpeg_quality":s_jpq,"focus_mode":_fm(),
        "lens_position":float(mf_lp),"photo_mode":s_mode,"film":s_film,
        "hdr":s_hdr,"watermark":s_wm})

# ======================================================================
#               OPTION HELPERS
# ======================================================================
def _opts(n):
    return {"Shutter":SHUTTER_OPT,"ISO":[str(x) for x in ISO_OPT],
            "WB":WB_OPT,"EV":[f"{x:+.1f}" for x in EV_OPT],"Film":FILM_OPT,
            "DENOISE":DN_OPT,"JPEG":[str(x) for x in JPG_OPT],"FOCUS":AF_OPT,
            "MODE":MODE_OPT,"GRID":GRID_OPT,"VOLUME":VOL_OPT,"GALDNG":GDNG_OPT,
            "GalDNG":GDNG_OPT,"BURST":[str(x) for x in BURST_OPT],
            "HDR":HDR_OPT,"TIMER":[str(x) for x in TIMER_OPT],
            "WATERMARK":WM_OPT}.get(n,[])

def _cidx(n):
    try:
        m={"Shutter":(SHUTTER_OPT,s_shut),"ISO":(ISO_OPT,s_iso),"WB":(WB_OPT,s_wb),
           "EV":(EV_OPT,s_ev),"Film":(FILM_OPT,s_film),"Denoise":(DN_OPT,s_dn),
           "JPEG":(JPG_OPT,s_jpq),"Focus":(AF_OPT,s_af),"Mode":(MODE_OPT,s_mode),
           "GRID":(GRID_OPT,s_grid),"VOLUME":(VOL_OPT,s_vol),"GALDNG":(GDNG_OPT,s_gdng),
           "GalDNG":(GDNG_OPT,s_gdng),"BURST":(BURST_OPT,s_burst),
           "HDR":(HDR_OPT,s_hdr),"TIMER":(TIMER_OPT,s_timer),
           "WATERMARK":(WM_OPT,s_wm)}
        l,v=m[n];return l.index(v)
    except: return 0

def _app_sub(n,idx,cam):
    global s_shut,s_iso,s_wb,s_ev,s_film,s_dn,s_jpq,s_af,s_mode,s_grid,s_vol,s_gdng,s_burst,s_hdr,s_timer,s_wm,ui_mode
    if n=="Shutter":s_shut=SHUTTER_OPT[idx]
    elif n=="ISO":s_iso=ISO_OPT[idx]
    elif n=="WB":s_wb=WB_OPT[idx]
    elif n=="EV":s_ev=EV_OPT[idx]
    elif n=="Film":
        # Block film changes when in Dynamic OR HDR mode
        if s_mode=="Dynamic" or s_hdr!="Off":
            return
        s_film=FILM_OPT[idx]
    elif n=="DENOISE":s_dn=DN_OPT[idx]
    elif n=="JPEG":s_jpq=JPG_OPT[idx]
    elif n=="FOCUS":
        s_af=AF_OPT[idx]
        if s_af=="MF": ui_mode="mf_live"
        if cam:_apply_cam(cam);_save_cfg();return
    elif n=="MODE":
        s_mode=MODE_OPT[idx]
        # When entering Dynamic: reset film + HDR + timer to Off
        if s_mode=="Dynamic":
            if s_film!="Off": s_film="Off"
            if s_hdr!="Off": s_hdr="Off"
    elif n=="GRID":s_grid=GRID_OPT[idx]

    elif n=="VOLUME":
        s_vol=VOL_OPT[idx]
        if s_vol=="OFF":
            try:
                with open(SOUND_MUTE_FLAG,"w") as f:f.write("1")
            except:pass
        else:
            try:os.remove(SOUND_MUTE_FLAG)
            except:pass
        try:
            import buzzer as _bz;_bz.set_volume(s_vol)
        except:pass
    elif n=="GALDNG":s_gdng=GDNG_OPT[idx]
    elif n=="BURST":
        # Burst only meaningful in Dynamic mode
        if s_mode!="Dynamic":
            return
        s_burst=BURST_OPT[idx]
    elif n=="HDR":
        # HDR not allowed in Dynamic mode
        if s_mode=="Dynamic":
            return
        s_hdr=HDR_OPT[idx]
        # When enabling HDR, reset film to Off
        if s_hdr!="Off" and s_film!="Off":
            s_film="Off"
    elif n=="TIMER":s_timer=TIMER_OPT[idx]
    elif n=="WATERMARK":s_wm=WM_OPT[idx]
    if cam:_apply_cam(cam)
    _save_cfg()

# ======================================================================
#                       GALLERY / WIFI
# ======================================================================
def _scan_gal():
    global gal_files,gal_idx
    os.makedirs(PICTURES_DIR,exist_ok=True)
    jpgs=sorted(glob.glob(os.path.join(PICTURES_DIR,"Saturnix_*.jpg")))
    if s_gdng=="On":
        dngs=sorted(glob.glob(os.path.join(PICTURES_DIR,"Saturnix_*.dng")))
        gal_files=sorted(set(jpgs+dngs))
    else:
        gal_files=jpgs
    if gal_idx>=len(gal_files):gal_idx=max(0,len(gal_files)-1)

def _gal_img():
    """Load gallery image. For DNG files returns None (placeholder drawn by draw_gal)."""
    if not gal_files:return None
    path=gal_files[gal_idx]
    if path.lower().endswith(".dng"):return None  # DNG placeholder handled in draw
    try:
        img=Image.open(path);img.draft("RGB",(LCD_W*3,LCD_H*3))
        img.load();img=img.convert("RGB");w,h=img.size;lr=LCD_W/LCD_H;ir=w/h
        if ir>lr:nw=int(h*lr);o=(w-nw)//2;img=img.crop((o,0,o+nw,h))
        elif ir<lr:nh=int(w/lr);o=(h-nh)//2;img=img.crop((0,o,w,o+nh))
        try:img=img.resize((LCD_W,LCD_H),Image.LANCZOS)
        except:img=img.resize((LCD_W,LCD_H),Image.ANTIALIAS)
        return img
    except:return None

def _gal_del():
    """Delete current file. For JPG also deletes paired DNG. For DNG deletes only DNG."""
    global gal_idx,_gc_idx,_gc_img
    if not gal_files:return
    p=gal_files[gal_idx]
    try:os.remove(p)
    except:pass
    # If deleting JPG, also delete paired DNG
    if p.lower().endswith(".jpg"):
        try:os.remove(os.path.splitext(p)[0]+".dng")
        except:pass
    _scan_gal();_gc_idx=-1;_gc_img=None

def _del_all():
    """Delete ALL files in Pictures directory."""
    global _gc_idx,_gc_img
    for f in glob.glob(os.path.join(PICTURES_DIR,"Saturnix_*.*")):
        try:os.remove(f)
        except:pass
    _scan_gal();_gc_idx=-1;_gc_img=None

def _wifi_start():
    global wifi_on,_wifi_p
    if wifi_on:return
    try:
        subprocess.run(["sudo","ifconfig",WIFI_IF,WIFI_ADDR,"netmask","255.255.255.0"],timeout=5)
        subprocess.run(["sudo","hostapd","-B","/etc/hostapd/hostapd_saturnix.conf"],timeout=5)
        subprocess.run(["sudo","dnsmasq","--conf-file=/etc/dnsmasq.d/saturnix.conf","-x","/tmp/saturnix_dnsmasq.pid"],timeout=5)
        srv=_HERE/"wifi_server.py"
        if srv.exists():_wifi_p=subprocess.Popen(["sudo",sys.executable,"-u",str(srv)],start_new_session=True)
        wifi_on=True
    except:pass

def _wifi_stop():
    global wifi_on,_wifi_p
    if _wifi_p and _wifi_p.poll() is None:
        try:os.killpg(os.getpgid(_wifi_p.pid),signal.SIGTERM);_wifi_p.wait(3)
        except:pass
    _wifi_p=None
    for p in("dnsmasq","hostapd"):
        try:subprocess.run(["sudo","killall",p],timeout=3,capture_output=True)
        except:pass
    wifi_on=False

# ======================================================================
#                    COMMAND HANDLER
# ======================================================================
def handle(cmd,cam):
    global ui_idx,ui_mode,sub_idx,focus_held,af_state
    global gal_idx,gal_act,gal_del_confirm,gal_del_sel,_gc_idx,_gc_img
    global poff,poff_sel,mf_lp,wifi_act,set_idx
    global _last_act,_ui_hid,set_sub_items,set_sub_cur
    global del_all_confirm,del_all_sel

    if cmd=="FOCUS_START":
        focus_held=True;fm=_fm()
        if fm=="afs" and cam:
            try:cam.set_controls({"AfMode":1,"AfTrigger":0})  # switch to auto, trigger
            except:pass
            af_state="focusing"; _af_change_t=time.monotonic()
        elif fm=="afc" and cam:
            try:cam.set_controls({"AfMode":0})  # stop AF, lock focus
            except:pass
            af_state="focused"; _af_change_t=time.monotonic()
        _wr_af(af_state);return
    if cmd=="FOCUS_STOP":
        focus_held=False
        fm=_fm()
        if fm=="afs" and cam:
            try:cam.set_controls({"AfMode":0})  # back to manual hold
            except:pass
        elif fm=="afc" and cam:
            try:cam.set_controls({"AfMode":2})  # resume continuous AF
            except:pass
        af_state="idle";_wr_af("idle");return
    if cmd=="EXIT_TO_LIVE":
        if ui_mode not in("main","submenu","mf_live"):
            ui_mode="main";gal_del_confirm=False;poff=False;del_all_confirm=False
        return

    if cmd in("LEFT","RIGHT","SELECT"):
        _last_act=time.monotonic()
        if _ui_hid:_ui_hid=False;return

    if poff:
        if cmd in("LEFT","RIGHT"):poff_sel=1-poff_sel
        elif cmd=="SELECT":
            if poff_sel==0:
                print("[POFF] Shutdown requested",flush=True)
                try:
                    r=subprocess.run(["sudo","-n","shutdown","-h","now"],
                                     capture_output=True,text=True,timeout=5)
                    if r.returncode!=0:
                        print(f"[POFF] shutdown failed rc={r.returncode}: {r.stderr}",flush=True)
                        # Fallback: try poweroff
                        try:
                            subprocess.Popen(["sudo","-n","poweroff"])
                        except Exception as e2:
                            print(f"[POFF] poweroff fallback err: {e2}",flush=True)
                except Exception as e:
                    print(f"[POFF] err: {e}",flush=True)
            else:poff=False;poff_sel=1
        return

    if del_all_confirm:
        if cmd in("LEFT","RIGHT"):del_all_sel=1-del_all_sel
        elif cmd=="SELECT":
            if del_all_sel==0:_del_all()
            del_all_confirm=False;del_all_sel=1;ui_mode="settings"
        return

    if ui_mode=="mf_live":
        if cmd=="RIGHT":
            mf_lp=min(MF_MAX,round(mf_lp+MF_S,1))
            if cam:
                try:cam.set_controls({"AfMode":0,"LensPosition":float(mf_lp)})
                except:pass
        elif cmd=="LEFT":
            mf_lp=max(MF_MIN,round(mf_lp-MF_S,1))
            if cam:
                try:cam.set_controls({"AfMode":0,"LensPosition":float(mf_lp)})
                except:pass
        elif cmd=="SELECT":ui_mode="main";_save_cfg()
        return

    if gal_del_confirm:
        if cmd in("LEFT","RIGHT"):gal_del_sel=1-gal_del_sel
        elif cmd=="SELECT":
            if gal_del_sel==0:
                _gal_del();gal_del_confirm=False;gal_del_sel=1
                if not gal_files:ui_mode="main"
                else:ui_mode="gallery"
            else:gal_del_confirm=False;gal_del_sel=1;ui_mode="gallery_nav"
        return

    if ui_mode=="gallery":
        if cmd=="LEFT" and gal_files:gal_idx=(gal_idx-1)%len(gal_files);_gc_idx=-1
        elif cmd=="RIGHT" and gal_files:gal_idx=(gal_idx+1)%len(gal_files);_gc_idx=-1
        elif cmd=="SELECT":ui_mode="gallery_nav";gal_act=0
        return
    if ui_mode=="gallery_nav":
        if cmd in("LEFT","RIGHT"):gal_act=1-gal_act
        elif cmd=="SELECT":
            if GAL_ACT[gal_act]=="BACK":draw_transition();ui_mode="main";gal_del_confirm=False
            else:gal_del_confirm=True;gal_del_sel=1
        return

    if ui_mode=="wifi":
        if cmd in("LEFT","RIGHT"):wifi_act=1-wifi_act
        elif cmd=="SELECT":
            if wifi_act==0:
                if wifi_on:_wifi_stop()
                else:_wifi_start()
            else:draw_transition();ui_mode="main"
        return

    if ui_mode=="info":
        if cmd=="SELECT":ui_mode="settings"
        return

    if ui_mode=="set_sub":
        n=len(set_sub_items)
        if cmd=="RIGHT":set_sub_cur=(set_sub_cur-1)%n;_cur_move()
        elif cmd=="LEFT":set_sub_cur=(set_sub_cur+1)%n;_cur_move()
        elif cmd=="SELECT":
            item=set_sub_items[set_sub_cur]
            if item=="< BACK":ui_mode="settings"
            else:
                name=SET_ITEMS[set_idx];opts=_opts(name)
                opts_upper=[str(x).upper() for x in opts]
                if item in opts_upper:
                    _app_sub(name,opts_upper.index(item),cam)
                    if ui_mode=="mf_live":return
                ui_mode="settings"
        return

    if ui_mode=="settings":
        n=len(SET_ITEMS)
        def _is_sect(i): return SET_ITEMS[i].startswith(_SECTION_PREFIX)
        def _skip(idx,direction):
            # Skip section markers when navigating
            for _ in range(n):
                idx=(idx+direction)%n
                if not _is_sect(idx): return idx
            return idx
        if cmd=="RIGHT":set_idx=_skip(set_idx,-1);_cur_move()
        elif cmd=="LEFT":set_idx=_skip(set_idx,+1);_cur_move()
        elif cmd=="SELECT":
            item=SET_ITEMS[set_idx]
            # Section markers are not selectable (shouldn't happen due to skip logic)
            if item.startswith(_SECTION_PREFIX): return
            # Block BURST when Mode is not Dynamic
            if item=="BURST" and s_mode!="Dynamic":
                try: import buzzer as _bz;_bz.error()
                except: pass
                return
            # Block HDR when in Dynamic mode
            if item=="HDR" and s_mode=="Dynamic":
                try: import buzzer as _bz;_bz.error()
                except: pass
                return
            if item in _S_SUB:
                opts=_opts(item);set_sub_items=[str(x).upper() for x in opts]+["< BACK"]
                set_sub_cur=_cidx(item);ui_mode="set_sub"
            elif item=="NETWORK INTERFACE":draw_transition(None);ui_mode="wifi";wifi_act=0
            elif item=="GALLERY":
                _scan_gal()
                if gal_files:draw_transition(None);ui_mode="gallery";gal_act=0;_gc_idx=-1;_gc_img=None
            elif item=="SYSTEM DIAGNOSTIC":draw_transition(None);ui_mode="info"
            elif item=="PURGE DATA":del_all_confirm=True;del_all_sel=1
            elif item=="SHUTDOWN":poff=True;poff_sel=1
            elif item=="BACK":draw_transition();ui_mode="main";_cur_reset()
        return

    if ui_mode=="main":
        if cmd=="LEFT":ui_idx=(ui_idx-1)%len(MAIN_MENU);_cur_move()
        elif cmd=="RIGHT":ui_idx=(ui_idx+1)%len(MAIN_MENU);_cur_move()
        elif cmd=="SELECT":
            item=MAIN_MENU[ui_idx]
            if item=="Settings":
                draw_transition(None);ui_mode="settings"
                # Find first non-section item
                set_idx=0
                while set_idx<len(SET_ITEMS) and SET_ITEMS[set_idx].startswith(_SECTION_PREFIX):
                    set_idx+=1
                return
            # Block Film when in Dynamic mode
            if item=="Film" and s_mode=="Dynamic":
                try: import buzzer as _bz;_bz.error()
                except: pass
                return
            ui_mode="submenu";sub_idx=_cidx(item);_cur_start_active()
        return

    if ui_mode=="submenu":
        name=MAIN_MENU[ui_idx];opts=_opts(name);L=len(opts)
        if L==0:ui_mode="main";return
        if cmd=="LEFT":sub_idx=(sub_idx-1)%L
        elif cmd=="RIGHT":sub_idx=(sub_idx+1)%L
        elif cmd=="SELECT":_app_sub(name,sub_idx,cam);ui_mode="main";_cur_reset()

# ======================================================================
#                    DRAWING
# ======================================================================
def _dsegs(s,e,d,g,ph):
    p=d+g;pos=s-(ph%p)
    while pos<e:
        a=max(pos,s);b=min(pos+d,e)
        if b>a:yield int(a),int(b)
        pos+=p

def _drect(dr,x0,y0,x1,y1,fill,w=2,d=6,g=4,ph=0):
    for a,b in _dsegs(x0,x1,d,g,ph):dr.line([(a,y0),(b,y0)],fill=fill,width=w);dr.line([(a,y1),(b,y1)],fill=fill,width=w)
    for a,b in _dsegs(y0,y1,d,g,ph):dr.line([(x0,a),(x0,b)],fill=fill,width=w);dr.line([(x1,a),(x1,b)],fill=fill,width=w)

def draw_ret(img,shoot=False,ph=0):
    """Corner brackets reticle — rangefinder style."""
    r=int(min(LCD_W,LCD_H)*0.38/3);cx,cy=LCD_W//2,LCD_H//2
    x0,y0,x1,y1=cx-r,cy-r,cx+r,cy+r;d=ImageDraw.Draw(img)
    L=int(r*0.5)  # bracket arm length
    c=C_RETICLE;w=2
    if shoot:
        # Dashed brackets during recording
        for a,b in _dsegs(x0,x0+L,6,4,ph):d.line([(a,y0),(b,y0)],fill=c,width=w)
        for a,b in _dsegs(x0,x0+L,6,4,ph):d.line([(a,y1),(b,y1)],fill=c,width=w)
        for a,b in _dsegs(x1-L,x1,6,4,ph):d.line([(a,y0),(b,y0)],fill=c,width=w)
        for a,b in _dsegs(x1-L,x1,6,4,ph):d.line([(a,y1),(b,y1)],fill=c,width=w)
        for a,b in _dsegs(y0,y0+L,6,4,ph):d.line([(x0,a),(x0,b)],fill=c,width=w)
        for a,b in _dsegs(y0,y0+L,6,4,ph):d.line([(x1,a),(x1,b)],fill=c,width=w)
        for a,b in _dsegs(y1-L,y1,6,4,ph):d.line([(x0,a),(x0,b)],fill=c,width=w)
        for a,b in _dsegs(y1-L,y1,6,4,ph):d.line([(x1,a),(x1,b)],fill=c,width=w)
    else:
        # Top-left
        d.line([(x0,y0),(x0+L,y0)],fill=c,width=w);d.line([(x0,y0),(x0,y0+L)],fill=c,width=w)
        # Top-right
        d.line([(x1-L,y0),(x1,y0)],fill=c,width=w);d.line([(x1,y0),(x1,y0+L)],fill=c,width=w)
        # Bottom-left
        d.line([(x0,y1-L),(x0,y1)],fill=c,width=w);d.line([(x0,y1),(x0+L,y1)],fill=c,width=w)
        # Bottom-right
        d.line([(x1,y1-L),(x1,y1)],fill=c,width=w);d.line([(x1-L,y1),(x1,y1)],fill=c,width=w)

def draw_af_ind(img):
    """AF indicator: ][ brackets — square style."""
    global af_blink,_af_bt
    if af_state=="idle":return
    now=time.monotonic()
    if not focus_held:
        if now-_af_change_t>AF_AUTO_HIDE_S:return
    cx,cy=LCD_W//2,LCD_H//2;d=ImageDraw.Draw(img)
    bh=10  # bracket half-height
    aw=4   # bracket arm width

    def draw_bracket_right(x,y,h,arm,col,w):
        # ] shape: vertical line with top and bottom serifs going LEFT
        d.line([(x,y-h),(x,y+h)],fill=col,width=w)
        d.line([(x,y-h),(x-arm,y-h)],fill=col,width=w)
        d.line([(x,y+h),(x-arm,y+h)],fill=col,width=w)
    def draw_bracket_left(x,y,h,arm,col,w):
        # [ shape: vertical line with top and bottom serifs going RIGHT
        d.line([(x,y-h),(x,y+h)],fill=col,width=w)
        d.line([(x,y-h),(x+arm,y-h)],fill=col,width=w)
        d.line([(x,y+h),(x+arm,y+h)],fill=col,width=w)

    if af_state=="focusing":
        col=C_AF_FOCUSING
        pulse=int(3*abs((now*4)%2-1))+4  # 4-7px oscillating gap
        # ] on left, [ on right
        draw_bracket_right(cx-pulse,cy,bh,aw,col,2)
        draw_bracket_left(cx+pulse,cy,bh,aw,col,2)
    elif af_state=="focused":
        if now-_af_bt>=AF_BP:af_blink=not af_blink;_af_bt=now
        if not af_blink:return
        col=C_AF_FOCUSED
        # Brackets joined: ][
        draw_bracket_right(cx-1,cy,bh,aw,col,2)
        draw_bracket_left(cx+1,cy,bh,aw,col,2)
    elif af_state=="failed":
        col=C_AF_FAILED
        gap=8
        draw_bracket_right(cx-gap,cy,bh,aw,col,2)
        draw_bracket_left(cx+gap,cy,bh,aw,col,2)

def draw_grid(img):
    if s_grid=="Off":return
    d=ImageDraw.Draw(img)
    if s_grid=="Thirds":
        for i in range(1,3):
            y=LCD_H*i//3;d.line([(0,y),(LCD_W,y)],fill=C_GRID,width=1)
            x=LCD_W*i//3;d.line([(x,0),(x,LCD_H)],fill=C_GRID,width=1)
    elif s_grid=="Golden":
        for r in(0.382,0.618):
            y=int(LCD_H*r);d.line([(0,y),(LCD_W,y)],fill=C_GRID,width=1)
            x=int(LCD_W*r);d.line([(x,0),(x,LCD_H)],fill=C_GRID,width=1)
    elif s_grid=="Cross":
        cx,cy=LCD_W//2,LCD_H//2;d.line([(cx,0),(cx,LCD_H)],fill=C_GRID,width=1);d.line([(0,cy),(LCD_W,cy)],fill=C_GRID,width=1)

# ---- Calibration marks ----
_CAL_MARKS=_hw("ui_cal_marks",True)
_CAL_COL=C_CAL
_CAL_SP=20;_CAL_L=3

def draw_cal_marks(img):
    if not _CAL_MARKS:return
    d=ImageDraw.Draw(img);c=_CAL_COL;L=_CAL_L
    # Top edge ticks
    for x in range(_CAL_SP,LCD_W-_CAL_SP+1,_CAL_SP):
        d.line([(x,0),(x,L)],fill=c,width=1)
    # Bottom edge ticks
    for x in range(_CAL_SP,LCD_W-_CAL_SP+1,_CAL_SP):
        d.line([(x,LCD_H-L-1),(x,LCD_H-1)],fill=c,width=1)
    # Left edge ticks
    for y in range(_CAL_SP,LCD_H-_CAL_SP+1,_CAL_SP):
        d.line([(0,y),(L,y)],fill=c,width=1)
    # Right edge ticks
    for y in range(_CAL_SP,LCD_H-_CAL_SP+1,_CAL_SP):
        d.line([(LCD_W-L-1,y),(LCD_W-1,y)],fill=c,width=1)

_BW=8;_BH=60;_BM=4
def draw_bar_meter(img):
    """Vertical bar-meter on right edge. Top=bright, bottom=dark."""
    bx=LCD_W-_BW-_BM;by=(LCD_H-_BH)//2
    try:_,g,_=img.split()[:3];hd=g.histogram()
    except:return
    if not hd or len(hd)<256:return
    total=sum(hd);avg=sum(i*hd[i] for i in range(256))/max(total,1)
    pos=1.0-avg/255.0  # invert: 0=top(bright), 1=bottom(dark)
    d=ImageDraw.Draw(img)
    d.rectangle((bx,by,bx+_BW,by+_BH),fill=C_BG)
    d.rectangle((bx,by,bx+_BW,by+_BH),outline=C_TEXT)
    # Red ideal marker at center
    my=by+_BH//2;d.line([(bx+1,my),(bx+_BW-1,my)],fill=C_BAR_MARK,width=1)
    # Indicator position
    bpos=int(pos*(_BH-4))+2
    d.rectangle((bx+2,by+bpos-2,bx+_BW-2,by+bpos+2),fill=C_BAR_FILL)

_dev_start_t=0.0
_REC_SYMS=["▤","▥","▦","▧","▨","▩"]
_PROC_SYMS=["◐","◓","◑","◒"]

F_BIG=_load_font(80,bold=True)

# ======================================================================
#                  SCI-FI VISUAL EFFECTS
# ======================================================================
import random as _rnd

_static_seed=0
def draw_static_noise(img,density=80):
    """Random pixels — sensor noise / CRT static. Uses full configured color."""
    if not UI_STATIC: return
    global _static_seed
    _static_seed+=1
    _rnd.seed(_static_seed)
    d=ImageDraw.Draw(img)
    # Bright (full color) and dim (50%) variants for visibility
    bright=C_STATIC
    dim=tuple(c//2 for c in C_STATIC)
    for _ in range(density):
        x=_rnd.randint(0,LCD_W-1);y=_rnd.randint(0,LCD_H-1)
        d.point((x,y),fill=bright if _rnd.random()<0.5 else dim)

_TRANS_CHARS="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ#@%&*+=<>/\\|[]{}()░▒▓█■□◆"
def draw_transition(target_img=None):
    """Full-screen grid of random chars — TV interference / system boot effect."""
    if not UI_TRANSITIONS: return
    # Char dimensions — measure once
    tmp=Image.new("RGB",(20,20),C_BG);td=ImageDraw.Draw(tmp)
    try:
        x0,y0,x1,y1=td.textbbox((0,0),"M",font=F)
        cw=x1-x0; ch=y1-y0
    except:
        cw,ch=8,14
    cols=LCD_W//cw + 1
    rows=LCD_H//ch + 1
    base=tuple(c*3//4 for c in C_TRANSITION)  # main char color
    glitch=C_TRANSITION  # full bright glitch chars
    # Render 3 frames of static
    for frame in range(3):
        img=Image.new("RGB",(LCD_W,LCD_H),C_BG)
        d=ImageDraw.Draw(img)
        _rnd.seed(time.monotonic_ns()+frame)
        for r in range(rows):
            y=r*ch
            for c in range(cols):
                x=c*cw
                ch_pick=_rnd.choice(_TRANS_CHARS)
                # 15% chance: bright glitch char
                col=glitch if _rnd.random()<0.15 else base
                d.text((x,y),ch_pick,font=F,fill=col)
        # Overlay static noise on top
        draw_static_noise(img,100)
        if FINAL_ROTATE==90: img=img.transpose(Image.ROTATE_90)
        elif FINAL_ROTATE==180: img=img.transpose(Image.ROTATE_180)
        elif FINAL_ROTATE==270: img=img.transpose(Image.ROTATE_270)
        disp.ShowImage(img)
        time.sleep(0.08)

def draw_corner_markers(img,inset=4,size=6):
    """Small L-shaped brackets in 4 corners of fullscreen panels."""
    d=ImageDraw.Draw(img);c=C_CORNER;w=1
    # Top-left
    d.line([(inset,inset),(inset+size,inset)],fill=c,width=w)
    d.line([(inset,inset),(inset,inset+size)],fill=c,width=w)
    # Top-right
    d.line([(LCD_W-inset-size,inset),(LCD_W-inset,inset)],fill=c,width=w)
    d.line([(LCD_W-inset,inset),(LCD_W-inset,inset+size)],fill=c,width=w)
    # Bottom-left
    d.line([(inset,LCD_H-inset-size),(inset,LCD_H-inset)],fill=c,width=w)
    d.line([(inset,LCD_H-inset),(inset+size,LCD_H-inset)],fill=c,width=w)
    # Bottom-right
    d.line([(LCD_W-inset,LCD_H-inset-size),(LCD_W-inset,LCD_H-inset)],fill=c,width=w)
    d.line([(LCD_W-inset-size,LCD_H-inset),(LCD_W-inset,LCD_H-inset)],fill=c,width=w)

def draw_divider_with_label(img,y,label):
    """Horizontal line with embedded label: ─── LABEL ────────"""
    d=ImageDraw.Draw(img)
    label=f" {label} "
    tw,th=_tw(d,label,F)
    pre=10  # left dashes width
    # Left dashes
    for x in range(pre,pre+18,4):
        d.line([(x,y),(x+2,y)],fill=C_DIVIDER,width=1)
    # Label
    lx=pre+22
    d.text((lx,y-th//2),label.strip(),font=F,fill=C_TEXT)
    # Right dashes
    rx_start=lx+tw+4
    x=rx_start
    while x<LCD_W-6:
        d.line([(x,y),(x+2,y)],fill=C_DIVIDER,width=1)
        x+=4

def caret(t=None):
    """Blinking terminal caret: returns '_' or ''. Period 0.5s."""
    if t is None: t=time.monotonic()
    return "_" if int(t*2)%2==0 else " "

def draw_technospam(img):
    """Tiny techno labels along top and bottom edges — sci-fi flavor.
    Positioned to avoid conflicts with side stacks (DYNAMIC left, PARAMS right)."""
    if not UI_TECHNOSPAM: return
    d=ImageDraw.Draw(img)
    col=tuple(c//3 for c in C_TECHNOSPAM)
    col2=tuple(c//4 for c in C_TECHNOSPAM)  # extra dim
    now=time.monotonic()

    # ===== TOP ROW (just below status bar) =====
    top_y=18
    # Top-left: system tag
    d.text((4,top_y),"[SYS.04A]",font=FS,fill=col)
    # Top-center: camera/optics
    cam_id=f"CAM.IMX519 OPT.A{int(now)%99:02d}"
    tw,_=_tw(d,cam_id,FS)
    d.text(((LCD_W-tw)//2,top_y),cam_id,font=FS,fill=col2)

    # ===== BOTTOM ROW =====
    # Above-bottom row (one line above timecode)
    above_y=LCD_H-26
    d.text((4,above_y),f"FREQ.{(int(now*3))%99:02d}MHZ",font=FS,fill=col2)
    rstr=f"REC.READY BUF.{(int(now*2))%999:03d} GAIN.x{(int(now/2))%9+1}"
    tw,_=_tw(d,rstr,FS)
    d.text((LCD_W-tw-4,above_y),rstr,font=FS,fill=col2)

    # Bottom row
    bottom_y=LCD_H-12
    # Bottom-left: timecode
    s=int(now-_startup_time)
    h,r=divmod(s,3600);m,sec=divmod(r,60)
    tc=f"T+{h:02d}:{m:02d}:{sec:02d}"
    d.text((4,bottom_y),tc,font=FS,fill=col)
    # Bottom-center: firmware version
    cd=f"V.{_hw('firmware_version','1.0.0')}"
    tw,_=_tw(d,cd,FS)
    d.text(((LCD_W-tw)//2,bottom_y),cd,font=FS,fill=col2)
    # Bottom-right: random hex code
    hex_cycle=int(now/3)%256
    hx=f"0x{hex_cycle:02X}.{(hex_cycle*7)&0xFF:02X}"
    tw,_=_tw(d,hx,FS)
    d.text((LCD_W-tw-4,bottom_y),hx,font=FS,fill=col)

def _draw_chip(img,x,cy,txt,col,fg=None,align="left"):
    """Draw centered text inside filled rectangle. Returns rect height for stacking.
    align='left': x is left edge of rect.
    align='right': x is right edge of rect."""
    if fg is None: fg=C_BG
    d=ImageDraw.Draw(img)
    try:
        x0,y0,x1,y1=d.textbbox((0,0),txt,font=FS)
        tw=x1-x0;th=y1-y0
    except:
        tw,th=_tw(d,txt,FS);x0=0;y0=0
    pad_x=6;pad_y=3
    bw=tw+pad_x*2;bh=th+pad_y*2
    if align=="right":
        bx=x-bw
    else:
        bx=x
    by=cy-bh//2
    d.rectangle((bx,by,bx+bw,by+bh),fill=col)
    tx=bx+pad_x-x0
    ty=by+pad_y-y0
    d.text((tx,ty),txt,font=FS,fill=fg)
    return bh

def draw_dynamic_indicator(img):
    """Stacked indicators on left side of liveview:
       [TIMER N]    ← top, always visible when s_timer != Off (blinks during countdown)
       [HDR ...]    ← when HDR != Off
       [FILM_NAME]  ← when film != Off
       [DYNAMIC]    ← when Mode == Dynamic (blinks)
       [BURST 5]    ← when Dynamic AND burst != Off
    All hide with UI auto-hide."""
    show_dyn=(s_mode=="Dynamic")
    show_film=(s_film!="Off")
    show_burst=(s_mode=="Dynamic" and s_burst!="Off")
    show_hdr=(s_hdr!="Off")
    show_timer=(s_timer!="Off")  # always shown when timer enabled

    if not (show_dyn or show_film or show_hdr or show_timer): return

    cx=4
    items=[]
    if show_timer:
        if _timer_active:
            # Live countdown with remaining seconds
            remaining=int(_timer_end_t-time.monotonic()+0.999)
            if remaining<1: remaining=1
            items.append(("timer_active",f"TIMER {remaining}"))
        else:
            # Static indicator with configured value
            items.append(("timer",f"TIMER {s_timer}"))
    if show_hdr: items.append(("hdr",f"HDR {s_hdr}"))
    if show_film: items.append(("film",s_film.upper()))
    if show_dyn:  items.append(("dyn","DYNAMIC"))
    if show_burst: items.append(("burst",f"BURST {s_burst}"))

    chip_h=18
    gap=2
    total=len(items)*chip_h + (len(items)-1)*gap
    y_start=(LCD_H-total)//2 + chip_h//2

    timer_blink=int(time.monotonic()*4)%2==0  # 4Hz during active countdown
    dyn_blink=int(time.monotonic()*2)%2==0    # 2Hz for Dynamic
    y=y_start
    for kind,txt in items:
        # Skip drawing on blink-off frame
        if kind=="dyn" and not dyn_blink:
            y+=chip_h+gap
            continue
        if kind=="timer_active" and not timer_blink:
            y+=chip_h+gap
            continue
        # Static timer (not active) — solid, doesn't blink
        _draw_chip(img,cx,y,txt,C_DYNAMIC,fg=C_BG,align="left")
        y+=chip_h+gap

def draw_param_chips(img):
    """Right-side stack of shooting parameter chips (always visible during liveview).
    SHUT / ISO / EV / WB / AF — golden chips, hides with UI auto-hide.
    Positioned to the left of bar-meter so they don't overlap."""
    # Right edge offset: bar-meter width + margin + spacing
    rx=LCD_W-_BW-_BM-6
    items=[
        s_shut.upper() if s_shut!="Auto" else "AUTO",
        f"ISO {s_iso}" if s_iso!="Auto" else "ISO AUTO",
        f"EV {s_ev:+.1f}",
        s_wb.upper(),
        s_af,
    ]
    chip_h=18
    gap=2
    total=len(items)*chip_h + (len(items)-1)*gap
    y_start=(LCD_H-total)//2 + chip_h//2
    y=y_start
    for txt in items:
        _draw_chip(img,rx,y,txt,C_DYNAMIC,fg=C_BG,align="right")
        y+=chip_h+gap

def draw_rec_anim(img):
    """Black screen with large animated square symbol — for active capture.
    500ms per frame, 6 squares cycling."""
    d=ImageDraw.Draw(img);d.rectangle((0,0,LCD_W,LCD_H),fill=C_BG)
    idx=int(time.monotonic()*2)%len(_REC_SYMS)  # 2Hz = 500ms
    sym=_REC_SYMS[idx]
    try:
        x0,y0,x1,y1=d.textbbox((0,0),sym,font=F_BIG)
        sw=x1-x0;sh=y1-y0
        px=(LCD_W-sw)//2-x0
        py=(LCD_H-sh)//2-y0
    except:
        sw,sh=_tw(d,sym,F_BIG)
        px=(LCD_W-sw)//2;py=(LCD_H-sh)//2
    d.text((px,py),sym,font=F_BIG,fill=C_ACCENT)
    # Burst counter
    if _burst_active and _burst_total>0:
        bt=f"BURST {_burst_count:02d}/{_burst_total:02d}"
        try:
            x0,y0,x1,y1=d.textbbox((0,0),bt,font=F)
            tw=x1-x0;th=y1-y0
            tx=(LCD_W-tw)//2-x0
            ty=LCD_H-th-12-y0
        except:
            tw,th=_tw(d,bt,F)
            tx=(LCD_W-tw)//2;ty=LCD_H-th-12
        d.text((tx,ty),bt,font=F,fill=C_TEXT)
    draw_static_noise(img,40)

def draw_proc_anim(img):
    """Black screen with rotating circle symbol — for film processing/effects.
    250ms per frame, 4 circles cycling (smooth rotation)."""
    d=ImageDraw.Draw(img);d.rectangle((0,0,LCD_W,LCD_H),fill=C_BG)
    idx=int(time.monotonic()*4)%len(_PROC_SYMS)  # 4Hz = 250ms
    sym=_PROC_SYMS[idx]
    try:
        x0,y0,x1,y1=d.textbbox((0,0),sym,font=F_BIG)
        sw=x1-x0;sh=y1-y0
        px=(LCD_W-sw)//2-x0
        py=(LCD_H-sh)//2-y0
    except:
        sw,sh=_tw(d,sym,F_BIG)
        px=(LCD_W-sw)//2;py=(LCD_H-sh)//2
    d.text((px,py),sym,font=F_BIG,fill=C_ACCENT)
    draw_static_noise(img,40)

def draw_dev(img,ph):
    """PROCESSING screen — circle animation."""
    draw_proc_anim(img)

def draw_gal(img):
    d=ImageDraw.Draw(img)
    if not gal_files:
        tw,th=_tw(d,"// NO DATA //");d.text(((LCD_W-tw)//2,(LCD_H-th)//2),"// NO DATA //",font=F,fill=C_TEXT);return
    fn=os.path.basename(gal_files[gal_idx]);st=os.path.splitext(fn)[0]
    ext=fn.rsplit(".",1)[-1].upper()
    # DNG placeholder (no preview)
    if ext=="DNG":
        cy=LCD_H//2-20
        tw1,th1=_tw(d,"DNG RAW");d.text(((LCD_W-tw1)//2,cy-th1-4),"DNG RAW",font=F,fill=C_TEXT)
        tw2,th2=_tw(d,fn);d.text(((LCD_W-tw2)//2,cy+6),fn,font=F,fill=C_TEXT)
        try:
            sz=os.path.getsize(gal_files[gal_idx])
            sztxt=f"{sz/(1024*1024):.1f} MB"
        except:sztxt=""
        if sztxt:
            tw3,_=_tw(d,sztxt);d.text(((LCD_W-tw3)//2,cy+24),sztxt,font=F,fill=C_ACCENT)
    # Bottom bar
    bh=int(LCD_H*0.18);by=LCD_H-bh;d.rectangle((0,by,LCD_W,LCD_H),fill=C_BG)
    cnt=f"{gal_idx+1:03d}/{len(gal_files):03d}";ty=by+(bh-14)//2
    if gal_del_confirm:
        pre="PURGE? ";ys="[CONFIRM]" if gal_del_sel==0 else " CONFIRM ";ns="[CANCEL]" if gal_del_sel==1 else " CANCEL "
        yc=C_ACCENT if gal_del_sel==0 else C_TEXT;nc=C_ACCENT if gal_del_sel==1 else C_TEXT
        full=pre+ys+" "+ns;tw,_=_tw(d,full);bx=(LCD_W-tw)//2
        d.text((bx,ty),pre,font=F,fill=C_TEXT)
        pw,_=_tw(d,pre);d.text((bx+pw,ty),ys,font=F,fill=yc)
        yw,_=_tw(d,ys+" ");d.text((bx+pw+yw,ty),ns,font=F,fill=nc)
    elif ui_mode=="gallery":
        info=f"< {st} {cnt} >";info=_el(d,info,LCD_W-8);tw,_=_tw(d,info)
        d.text(((LCD_W-tw)//2,ty),info,font=F,fill=C_TEXT)
    else:
        # Action selection: selected amber, rest white
        parts=[];
        for i,a in enumerate(GAL_ACT):
            parts.append((f"[{a}]",C_ACCENT) if i==gal_act else (f" {a} ",C_TEXT))
        pre=f"{st}  ";tw_full,_=_tw(d,pre+"".join(p[0] for p in parts))
        bx=(LCD_W-tw_full)//2;d.text((bx,ty),pre,font=F,fill=C_TEXT)
        cx=bx+_tw(d,pre)[0]
        for txt,col in parts:
            d.text((cx,ty),txt,font=F,fill=col);cx+=_tw(d,txt)[0]

def draw_wifi(img):
    d=ImageDraw.Draw(img);d.rectangle((0,0,LCD_W,LCD_H),fill=C_BG)
    draw_divider_with_label(img,12,"NETWORK INTERFACE"+caret())
    y=32;lh=18
    st="ONLINE" if wifi_on else "OFFLINE"
    st_col=C_ACCENT if wifi_on else C_TEXT
    d.text((10,y),"STATUS    ",font=F,fill=C_ACCENT);d.text((10+_tw(d,"STATUS    ")[0],y),st,font=F,fill=st_col);y+=lh
    d.text((10,y),"SSID      ",font=F,fill=C_ACCENT);d.text((10+_tw(d,"SSID      ")[0],y),WIFI_SSID.upper(),font=F,fill=C_TEXT);y+=lh
    d.text((10,y),"KEY       ",font=F,fill=C_ACCENT);d.text((10+_tw(d,"KEY       ")[0],y),"*"*len(WIFI_PASS),font=F,fill=C_TEXT);y+=lh
    d.text((10,y),"ADDR      ",font=F,fill=C_ACCENT);d.text((10+_tw(d,"ADDR      ")[0],y),WIFI_ADDR,font=F,fill=C_TEXT);y+=lh
    bh=int(LCD_H*0.18);by=LCD_H-bh
    bl="DISABLE" if wifi_on else "ENABLE"
    btns=[bl,"EXIT"]
    parts=[(f"[{a}]" if i==wifi_act else f" {a} ",C_ACCENT if i==wifi_act else C_TEXT) for i,a in enumerate(btns)]
    full="  ".join(p[0] for p in parts);tw,th=_tw(d,full)
    bx=(LCD_W-tw)//2;by2=by+(bh-th)//2;cx2=bx
    for i,(p,col) in enumerate(parts):
        pw,_=_tw(d,p);d.text((cx2,by2),p,font=F,fill=col);cx2+=pw
        if i<len(parts)-1:cx2+=_tw(d,"  ")[0]
    draw_static_noise(img,30)
    draw_corner_markers(img)

def draw_info(img):
    d=ImageDraw.Draw(img);d.rectangle((0,0,LCD_W,LCD_H),fill=C_BG)
    draw_divider_with_label(img,12,"SYSTEM DIAGNOSTIC"+caret())
    y=32;lh=18
    # Battery info
    bat_pct,bat_chg=_get_battery()
    if _ups and _ups.is_available():
        _,_,bv=_ups.get_status()
        bat_str=f"{bat_pct}% / {bv:.2f}V"
        if bat_chg: bat_str+=" (CHARGING)"
    else:
        bat_str=f"{bat_pct}% (NO UPS)"
    lines=[
        ("UNIT",_hw("camera_name","SATURNIX Dione").upper()),
        ("BUILD","LANTIAN V11-0904"),
        ("AUTHOR","YUTANI"),
        ("SENSOR",_hw("sensor","IMX519").upper()+" 16MP AF"),
        ("PLATFORM","RPI ZERO 2W"),
        ("BATTERY",bat_str),
        ("STORAGE",_get_stor()+" FREE"),
        ("UPTIME",_uptime()),
    ]
    for label,val in lines:
        lbl=f"{label:10s}";d.text((10,y),lbl,font=F,fill=C_ACCENT)
        tw,_=_tw(d,lbl);d.text((10+tw+4,y),val,font=F,fill=C_TEXT)
        y+=lh
    y+=4;d.text((10,y),"SELECT = BACK",font=FS,fill=C_ACCENT)
    draw_static_noise(img,30)
    draw_corner_markers(img)

def _fsl(img,title,items,cur,disabled=None,sections=None):
    """Fullscreen list with sci-fi divider header.
    disabled: optional iterable of item indices that should appear dimmed.
    sections: optional iterable of item indices that are section markers
              (rendered as dividers, smaller line, accent color)."""
    if disabled is None: disabled=set()
    else: disabled=set(disabled)
    if sections is None: sections=set()
    else: sections=set(sections)
    d=ImageDraw.Draw(img);d.rectangle((0,0,LCD_W,LCD_H),fill=C_BG)
    draw_divider_with_label(img,12,title+caret())
    y0=28;avail=LCD_H-y0-8
    lh=22  # normal item height
    sh=14  # section header height (smaller)
    n=len(items)
    # Compute viewport: include all items but use smaller line for sections
    # First, build cumulative heights
    heights=[sh if i in sections else lh for i in range(n)]
    # Find viewport that contains cur
    # Simple approach: scroll so that cur is roughly centered
    # Compute total visible items by averaging
    avg=sum(heights)/max(n,1)
    mv=int(avail/avg)
    if n<=mv:vs,ve=0,n
    else:
        half=mv//2;vs=cur-half;ve=vs+mv
        if vs<0:vs=0;ve=mv
        elif ve>n:ve=n;vs=ve-mv
    y=y0
    for i in range(vs,ve):
        is_dim=i in disabled
        is_sect=i in sections
        h=sh if is_sect else lh
        if is_sect:
            # Section marker: small accent text, no cursor
            txt=items[i]
            tw,th=_tw(d,txt,FS)
            d.text(((LCD_W-tw)//2,y+(h-th)//2),txt,font=FS,fill=C_TEXT_LABEL)
        else:
            if i==cur and _cur_vis:
                d.rectangle((6,y-2,LCD_W-6,y+lh-4),fill=C_CURSOR);tc=C_CURSOR_TEXT
                d.rectangle((6,y-3,LCD_W-6,y+lh-3),outline=C_ACCENT_DIM)
                if is_dim: tc=C_TEXT_DIM
            else:
                tc=C_TEXT_DIM if is_dim else C_TEXT
            d.text((14,y),_el(d,items[i],LCD_W-28),font=F,fill=tc)
        y+=h
    if vs>0:d.text((LCD_W-16,y0),"^",font=FS,fill=C_ACCENT)
    if ve<n:d.text((LCD_W-16,y-heights[ve-1]),"V",font=FS,fill=C_ACCENT)
    draw_static_noise(img,30)
    draw_corner_markers(img)

def draw_settings(img):
    vals={"DENOISE":s_dn.upper(),"JPEG":str(s_jpq),"FOCUS":s_af,"MODE":s_mode.upper(),
          "GRID":s_grid.upper(),"VOLUME":s_vol,"GALDNG":s_gdng.upper(),"BURST":str(s_burst).upper(),
          "HDR":s_hdr.upper(),"TIMER":str(s_timer).upper(),"WATERMARK":s_wm.upper(),
          "NETWORK INTERFACE":"ONLINE" if wifi_on else "","GALLERY":"",
          "SYSTEM DIAGNOSTIC":"","PURGE DATA":"","SHUTDOWN":"","BACK":""}
    items=[]
    disabled=set()
    sections=set()
    for i,it in enumerate(SET_ITEMS):
        if it.startswith(_SECTION_PREFIX):
            items.append(it)
            sections.add(i)
            continue
        v=vals.get(it,"")
        if it in _S_ACT and it!="BACK":items.append(f"{it} >")
        elif it=="BACK":items.append("< BACK")
        else:items.append(f"{it}  [{v}]" if v else it)
        # Disabled logic
        if it=="BURST" and s_mode!="Dynamic":
            disabled.add(i)
        elif it=="HDR" and s_mode=="Dynamic":
            disabled.add(i)
    _fsl(img,"SETTINGS",items,set_idx,disabled,sections)

def draw_set_sub(img):
    name=SET_ITEMS[set_idx]
    _fsl(img,name,set_sub_items,set_sub_cur)

def draw_battery(img):
    """Battery indicator only — always visible on liveview, doesn't hide with UI."""
    d=ImageDraw.Draw(img)
    bat_pct,bat_chg=_get_battery();bat_icon=_bat_icon(bat_pct)
    bolt="+" if bat_chg else " "
    bat_str=f"{bat_icon}{bolt}{bat_pct}%"
    bat_col=C_WARN if bat_pct<15 and not bat_chg else C_BATTERY
    y=2
    if ui_mode=="submenu":y=int(LCD_H*0.14)+2
    btw,_=_tw(d,bat_str,FS)
    d.text((LCD_W-btw-4,y),bat_str,font=FS,fill=bat_col)

def draw_status(img):
    """Top status bar: storage only (battery drawn separately, always visible).
    Storage hides with UI auto-hide."""
    d=ImageDraw.Draw(img)
    stor=_get_stor()
    bat_pct,bat_chg=_get_battery();bat_icon=_bat_icon(bat_pct)
    bolt="+" if bat_chg else " "
    bat_str=f"{bat_icon}{bolt}{bat_pct}%"
    is_low=_check_storage_low()
    y=2
    if ui_mode=="submenu":y=int(LCD_H*0.14)+2
    # Battery still drawn here for menu screens (where we don't call draw_battery separately)
    bat_col=C_WARN if bat_pct<15 and not bat_chg else C_BATTERY
    btw,_=_tw(d,bat_str,FS)
    d.text((LCD_W-btw-4,y),bat_str,font=FS,fill=bat_col)
    # Storage to the left of battery
    stw,_=_tw(d,stor,FS)
    d.text((LCD_W-btw-stw-12,y),stor,font=FS,fill=C_WARN if is_low else C_TEXT)

def draw_storage_popup(img):
    """Brief notification when storage just crossed warning threshold."""
    if not _stor_warn_active: return
    # Blink ~2Hz
    if int(time.monotonic()*4)%2!=0: return
    d=ImageDraw.Draw(img)
    txt="[STORAGE LOW]"
    try:
        x0,y0,x1,y1=d.textbbox((0,0),txt,font=F)
        tw=x1-x0;th=y1-y0
    except:
        tw,th=_tw(d,txt,F);x0=0;y0=0
    pad_x=8;pad_y=4
    bw=tw+pad_x*2;bh=th+pad_y*2
    bx=(LCD_W-bw)//2;by=LCD_H-bh-30
    d.rectangle((bx,by,bx+bw,by+bh),fill=C_WARN)
    tx=bx+pad_x-x0;ty=by+pad_y-y0
    d.text((tx,ty),txt,font=F,fill=C_BG)

# ======================================================================
#                    MAIN UI
# ======================================================================
def draw_ui(img,shoot=False,aph=0):
    global ui_mode,_ui_hid
    if time.monotonic()-_last_act>AUTO_HIDE:_ui_hid=True
    _cur_update()

    if ui_mode in("gallery","gallery_nav") or gal_del_confirm:draw_gal(img);return
    if ui_mode=="wifi":draw_wifi(img);return
    if poff:
        d=ImageDraw.Draw(img);d.rectangle((0,0,LCD_W,LCD_H),fill=C_BG)
        tw1,th1=_tw(d,"SHUTDOWN SYSTEM?")
        cy=LCD_H//2;d.text(((LCD_W-tw1)//2,cy-th1-6),"SHUTDOWN SYSTEM?",font=F,fill=C_TEXT)
        ys="[CONFIRM]" if poff_sel==0 else " CONFIRM ";ns="[CANCEL]" if poff_sel==1 else " CANCEL "
        yc=C_ACCENT if poff_sel==0 else C_TEXT;nc=C_ACCENT if poff_sel==1 else C_TEXT
        sep="  ";full=ys+sep+ns;tw2,_=_tw(d,full);bx=(LCD_W-tw2)//2;by2=cy+6
        d.text((bx,by2),ys,font=F,fill=yc)
        yw,_=_tw(d,ys);sw,_=_tw(d,sep)
        d.text((bx+yw+sw,by2),ns,font=F,fill=nc)
        draw_static_noise(img,30);draw_corner_markers(img);return
    if del_all_confirm:
        d=ImageDraw.Draw(img);d.rectangle((0,0,LCD_W,LCD_H),fill=C_BG)
        tw1,th1=_tw(d,"PURGE ALL DATA?")
        cy=LCD_H//2
        d.text(((LCD_W-tw1)//2,cy-th1-12),"PURGE ALL DATA?",font=F,fill=C_TEXT)
        tw3,th3=_tw(d,"JPG AND DNG FILES");d.text(((LCD_W-tw3)//2,cy-2),"JPG AND DNG FILES",font=F,fill=C_TEXT)
        ys="[CONFIRM]" if del_all_sel==0 else " CONFIRM ";ns="[CANCEL]" if del_all_sel==1 else " CANCEL "
        yc=C_ACCENT if del_all_sel==0 else C_TEXT;nc=C_ACCENT if del_all_sel==1 else C_TEXT
        sep="  ";full=ys+sep+ns;tw2,_=_tw(d,full);bx=(LCD_W-tw2)//2;by2=cy+th3+8
        d.text((bx,by2),ys,font=F,fill=yc)
        yw,_=_tw(d,ys);sw,_=_tw(d,sep)
        d.text((bx+yw+sw,by2),ns,font=F,fill=nc)
        draw_static_noise(img,30);draw_corner_markers(img);return
    if ui_mode=="settings":draw_settings(img);return
    if ui_mode=="set_sub":draw_set_sub(img);return
    if ui_mode=="info":draw_info(img);return

    # Liveview overlays (always visible)
    draw_cal_marks(img);draw_grid(img);draw_ret(img,shoot,aph);draw_af_ind(img);draw_bar_meter(img)
    draw_technospam(img)  # always visible, doesn't hide with UI
    draw_battery(img)  # always visible, doesn't hide with UI
    if _ui_hid:
        draw_static_noise(img,15)  # noise on top even when UI hidden
        return

    draw_status(img);d=ImageDraw.Draw(img)
    draw_dynamic_indicator(img)  # left stack: film/dynamic/burst, hides with UI
    draw_param_chips(img)  # right stack: shut/iso/ev/wb/af, hides with UI
    draw_storage_popup(img)  # brief warning on threshold crossing

    if ui_mode=="mf_live":
        bh=int(LCD_H*0.22);by=LCD_H-bh;d.rectangle((0,by,LCD_W,LCD_H),fill=C_BG)
        m=10;tx0=m;tx1=LCD_W-m;ty=by+bh//2;tw2=tx1-tx0
        d.line([(tx0,ty),(tx1,ty)],fill=C_TEXT,width=2)
        fr=mf_lp/MF_MAX if MF_MAX>0 else 0;kx=int(tx0+fr*tw2);kr=5
        d.rectangle((kx-kr,ty-kr,kx+kr,ty+kr),fill=C_ACCENT)
        d.text((m,by+3),f"MF: {mf_lp:.1f}",font=F,fill=C_TEXT)
        h="< L/R  SEL=EXIT >";twh,_=_tw(d,h);d.text((LCD_W-m-twh,by+3),h,font=F,fill=C_TEXT)
        d.text((tx0,ty+8),"INF",font=FS,fill=C_TEXT)
        mt="MACRO";twm,_=_tw(d,mt,FS);d.text((tx1-twm,ty+8),mt,font=FS,fill=C_TEXT)
        return

    # Bottom bar
    bh=int(LCD_H*0.22);by=LCD_H-bh;d.rectangle((0,by,LCD_W,LCD_H),fill=C_BG)
    tot=len(MAIN_MENU);ps=(ui_idx//3)*3;vis=list(range(ps,min(ps+3,tot)))
    n=len(vis);cw=LCD_W//max(n,1);pad=int(cw*0.05);li=ui_idx-ps
    lm={"Shutter":f"SHUT [{s_shut.upper()}]","ISO":f"ISO [{s_iso}]","WB":f"WB [{s_wb.upper()}]",
        "EV":f"EV [{s_ev:+.1f}]","Film":f"FILM [{s_film.upper()}]","Settings":"SETTINGS"}
    labels=[lm.get(MAIN_MENU[i],MAIN_MENU[i]) for i in vis]
    if _cur_vis:
        d.rectangle((li*cw+pad,by+int(bh*0.15),(li+1)*cw-pad,by+int(bh*0.78)),fill=C_CURSOR)
        d.rectangle((li*cw+pad-1,by+int(bh*0.15)-1,(li+1)*cw-pad+1,by+int(bh*0.78)+1),outline=C_ACCENT_DIM)
    for i,t in enumerate(labels):
        t=_el(d,t,int(cw*0.92));tx=i*cw+cw//2;ty2=by+int(bh*0.46)
        tw,th=_tw(d,t)
        item_name=MAIN_MENU[vis[i]]
        is_dim_item=(item_name=="Film" and s_mode=="Dynamic")
        if i==li and _cur_vis:
            c=C_TEXT_DIM if is_dim_item else C_CURSOR_TEXT
        else:
            c=C_TEXT_DIM if is_dim_item else C_TEXT
        d.text((tx-tw//2,ty2-th//2),t,font=F,fill=c)
    np2=(tot+2)//3;cp=ui_idx//3;dy=by+bh-6;dtw=np2*6;dx=(LCD_W-dtw)//2
    for p in range(np2):
        x=dx+p*6+2;c=C_TEXT if p==cp else C_ACCENT_DIM;d.rectangle((x,dy,x+2,dy+2),fill=c)

    if ui_mode=="submenu":
        sh=int(LCD_H*0.14);d.rectangle((0,0,LCD_W,sh),fill=C_BG)
        name=MAIN_MENU[ui_idx];opts=_opts(name)
        if opts:
            # Adaptive window: grow around the selected item only while the
            # rendered line still fits the display. Guarantees the selected
            # item is always fully visible (so its highlight always works)
            # regardless of how many/long the options are.
            maxw=LCD_W-6
            def _line(a,b):
                ps=[]
                if a>0:ps.append("<")
                for j in range(a,b):
                    ps.append(f"[{str(opts[j]).upper()}]" if j==sub_idx
                              else str(opts[j]).upper())
                if b<len(opts):ps.append(">")
                return " | ".join(ps)
            vs=ve=sub_idx;ve+=1
            while True:
                grown=False
                if ve<len(opts) and _tw(d,_line(vs,ve+1))[0]<=maxw:
                    ve+=1;grown=True
                if vs>0 and _tw(d,_line(vs-1,ve))[0]<=maxw:
                    vs-=1;grown=True
                if not grown:break
            txt=_line(vs,ve)
            tw,th=_tw(d,txt)
            d.text(((LCD_W-tw)//2,(sh-th)//2),txt,font=F,fill=C_TEXT)
            sel_txt=f"[{str(opts[sub_idx]).upper()}]"
            idx_in=txt.find(sel_txt)
            if idx_in>=0:
                pre=txt[:idx_in]
                pw,_=_tw(d,pre)
                sx=(LCD_W-tw)//2+pw;sy=(sh-th)//2
                d.rectangle((sx,sy,sx+_tw(d,sel_txt)[0],sy+th),fill=C_BG)
                d.text((sx,sy),sel_txt,font=F,fill=C_ACCENT)

    # FINAL pass: subtle static noise OVER all UI on liveview
    draw_static_noise(img,15)

# ======================================================================
#              AF POLL
# ======================================================================
def _poll_af(cam):
    global af_state, _af_change_t
    fm=_fm()
    if fm=="mf":
        if af_state!="idle": af_state="idle";_wr_af("idle")
        return
    # AF-S: only poll when button held
    if fm=="afs" and not focus_held: return
    # AF-C: always poll (auto-indication)
    try:
        md=cam.capture_metadata();v=md.get("AfState",0);prev=af_state
        if v==1:af_state="focusing"
        elif v==2:af_state="focused"
        elif v==3:af_state="failed"
        if af_state!=prev:
            _af_change_t=time.monotonic()
            _wr_af(af_state)
    except:pass

# ======================================================================
#                         MAIN LOOP
# ======================================================================
_splash()
_flag_clear();_wr_af("idle");_load_cfg()
cam=open_cam()
try:_apply_cam(cam)
except:pass

try:
    w,h=LCD_W,LCD_H;SI=disp.ShowImage;FB=Image.frombuffer
    st=False;paused=False;last_raw=None;aph=0;nat=0.0;AS=2;AP=0.06

    while not want_exit:
        if want_pause and not paused:
            want_pause=False
            try:cam.stop();cam.close()
            except:pass
            paused=True;_flag_set();continue
        if want_resume and paused:
            _flag_clear()
            try:
                cam=open_cam();_apply_cam(cam);paused=False;want_resume=False
            except:
                time.sleep(0.1);continue
            continue

        cmd=_take_cmd()
        if cmd:handle(cmd,cam if not paused else None)

        # Check for inline capture request (only when not paused)
        if not paused and not _capture_busy:
            if os.path.exists(CAPTURE_REQUEST_FILE):
                # If burst is active, second press aborts it
                if _burst_active:
                    try: os.remove(CAPTURE_REQUEST_FILE)
                    except: pass
                    _burst_abort=True
                else:
                    _cam_ref=[cam]
                    cam=_check_capture_request(_cam_ref)
                    if cam is not None:
                        try:_apply_cam(cam)
                        except:pass

        # Check if subprocess capture thread finished — reopen preview cam
        if _capture_busy:
            _cam_ref=[cam]
            cam=_check_capture_done(_cam_ref)

        # Continue burst sequence if active
        if not paused and _burst_active and not _capture_busy:
            _cam_ref=[cam]
            cam=_step_burst(_cam_ref)

        # Self-timer countdown
        if not paused and _timer_active and not _capture_busy:
            _cam_ref=[cam]
            cam=_step_timer(_cam_ref)

        # Battery critical check (every loop, but rate-limited internally)
        _check_battery_critical()

        # Check if film processing finished
        _check_film_done()

        if ui_mode!=_ui_mode_written:
            try:
                with open(UI_MODE_FILE,"w") as f:f.write(ui_mode)
                _ui_mode_written=ui_mode
            except:pass

        # Two-phase animation:
        # - REC (squares ▤▥▦▧▨▩): during raw capture — DON'T MOVE camera!
        # - PROC (circles ◐◓◑◒): capture complete, camera can move; processing in background
        # CAPTURED_FLAG file is written by capture.py the moment rpicam-still finishes
        # (before film/effects processing starts). That's the precise moment the user
        # can move the camera safely.
        capture_done = os.path.exists(CAPTURED_FLAG)
        if _burst_active:
            # Burst: keep showing squares throughout — sequence isn't done yet
            showing_rec = True
            showing_proc = False
        elif _capture_busy and not capture_done:
            # Raw capture in progress — squares (don't move!)
            showing_rec = True
            showing_proc = False
        elif _capture_busy or _film_phase:
            # Capture finished but processing/cleanup still ongoing — circles
            showing_rec = False
            showing_proc = True
        else:
            showing_rec = False
            showing_proc = False

        if paused:
            now=time.monotonic()
            if last_raw and now>=nat:
                fr=Image.new("RGB",(LCD_W,LCD_H),C_BG)
                draw_rec_anim(fr)
                if FINAL_ROTATE==90:fr=fr.transpose(Image.ROTATE_90)
                elif FINAL_ROTATE==180:fr=fr.transpose(Image.ROTATE_180)
                elif FINAL_ROTATE==270:fr=fr.transpose(Image.ROTATE_270)
                SI(fr);aph=(aph+AS)%200;nat=now+AP
            time.sleep(0.001);continue

        if showing_rec or showing_proc:
            fr=Image.new("RGB",(LCD_W,LCD_H),C_BG)
            if showing_rec:
                draw_rec_anim(fr)
            else:
                draw_proc_anim(fr)
            if FINAL_ROTATE==90:fr=fr.transpose(Image.ROTATE_90)
            elif FINAL_ROTATE==180:fr=fr.transpose(Image.ROTATE_180)
            elif FINAL_ROTATE==270:fr=fr.transpose(Image.ROTATE_270)
            SI(fr);time.sleep(0.04);continue

        if ui_mode in("gallery","gallery_nav") or gal_del_confirm:
            if _gc_idx!=gal_idx or _gc_img is None:
                _gc_img=_gal_img();_gc_idx=gal_idx
            fr=_gc_img.copy() if _gc_img else Image.new("RGB",(w,h),C_BG)
            draw_ui(fr)
            draw_static_noise(fr,30)
            if FINAL_ROTATE==90:fr=fr.transpose(Image.ROTATE_90)
            elif FINAL_ROTATE==180:fr=fr.transpose(Image.ROTATE_180)
            elif FINAL_ROTATE==270:fr=fr.transpose(Image.ROTATE_270)
            SI(fr);time.sleep(0.05);continue

        if ui_mode in("wifi","settings","set_sub","info") or poff or del_all_confirm:
            fr=Image.new("RGB",(w,h),C_BG);draw_ui(fr)
            if FINAL_ROTATE==90:fr=fr.transpose(Image.ROTATE_90)
            elif FINAL_ROTATE==180:fr=fr.transpose(Image.ROTATE_180)
            elif FINAL_ROTATE==270:fr=fr.transpose(Image.ROTATE_270)
            SI(fr);time.sleep(0.05);continue

        # Guard: if camera died, try to reopen (but NOT during active capture)
        if cam is None:
            if _capture_busy:
                # subprocess holds the camera; just wait
                time.sleep(0.05);continue
            try:
                cam=open_cam();_apply_cam(cam)
            except:
                time.sleep(0.5);continue
        try:
            buf=cam.capture_buffer("main");st=not st
        except Exception as e:
            print(f"[LV] capture_buffer err: {e}",flush=True)
            try: cam.close()
            except: pass
            cam=None
            time.sleep(0.2);continue
        if not st:continue
        img=FB("RGB",(w,h),buf,"raw","RGB",0,1)
        try:last_raw=img.copy()
        except:last_raw=None
        _poll_af(cam);draw_ui(img)
        if FINAL_ROTATE==90:img=img.transpose(Image.ROTATE_90)
        elif FINAL_ROTATE==180:img=img.transpose(Image.ROTATE_180)
        elif FINAL_ROTATE==270:img=img.transpose(Image.ROTATE_270)
        SI(img)

finally:
    if wifi_on:
        try:_wifi_stop()
        except:pass
    try:
        if not paused:cam.stop();cam.close()
    except:pass
    _flag_clear();_wr_af("idle");disp.module_exit()
