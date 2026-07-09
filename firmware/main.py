#!/usr/bin/env python3
# main.py — GPIO controller for SATURNIX Dione.
# 16=LEFT 20=RIGHT 21=SELECT 23=CAPTURE 24=FOCUS 26=BUZZER
# CAPTURE in menu/gallery/settings → exit to liveview (no photo)
# CAPTURE in liveview → take photo

import os, sys, time, signal, subprocess, json
from pathlib import Path
from collections import deque
import RPi.GPIO as GPIO

HERE=Path(__file__).resolve().parent
LIVEVIEW=HERE/"liveview.py"; CAPTURE_SCRIPT=HERE/"capture.py"
PYTHON=sys.executable; sys.path.insert(0,str(HERE))
import buzzer

PAUSE_FLAG="/tmp/saturnix_cam_paused"; UI_CMD_FILE="/tmp/saturnix_ui_cmd"
AF_STATE_FILE="/tmp/saturnix_af_state"
# File that LiveView writes to indicate current UI mode
UI_MODE_FILE="/tmp/saturnix_ui_mode"

# ---- GPIO pin defaults (used if config.json missing/invalid) ----
_DEFAULT_PINS = {
    "left": 16, "right": 20, "select": 21,
    "capture": 23, "focus": 24, "buzzer": 26,
}

def _load_gpio_pins():
    """Load GPIO pin assignments from config.json with validation.
    Falls back to defaults if file missing, malformed, or values invalid.
    Validates: each pin is int in 0..27, all pins unique."""
    cfg_path = HERE / "config.json"
    pins = dict(_DEFAULT_PINS)
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
        user_pins = cfg.get("gpio_pins", {})
        if not isinstance(user_pins, dict):
            print("[GPIO] gpio_pins not an object — using defaults", flush=True)
            return pins
        validated = {}
        for key, default in _DEFAULT_PINS.items():
            v = user_pins.get(key, default)
            try:
                v = int(v)
            except (TypeError, ValueError):
                print(f"[GPIO] {key}={v!r} not int — using default {default}", flush=True)
                v = default
            if not (0 <= v <= 27):
                print(f"[GPIO] {key}={v} out of range 0..27 — using default {default}", flush=True)
                v = default
            validated[key] = v
        # Check for duplicate pins
        seen = {}
        for key, v in validated.items():
            if v in seen:
                print(f"[GPIO] {key} and {seen[v]} both assigned to GPIO {v} — using defaults", flush=True)
                return dict(_DEFAULT_PINS)
            seen[v] = key
        return validated
    except FileNotFoundError:
        print("[GPIO] config.json not found — using default pins", flush=True)
        return pins
    except Exception as e:
        print(f"[GPIO] config load failed ({e}) — using defaults", flush=True)
        return pins

_PINS = _load_gpio_pins()
PIN_LEFT    = _PINS["left"]
PIN_RIGHT   = _PINS["right"]
PIN_SELECT  = _PINS["select"]
PIN_CAPTURE = _PINS["capture"]
PIN_FOCUS   = _PINS["focus"]
PIN_BUZZER  = _PINS["buzzer"]
ALL_PINS=(PIN_LEFT,PIN_RIGHT,PIN_SELECT,PIN_CAPTURE,PIN_FOCUS,PIN_BUZZER)
print(f"[GPIO] L={PIN_LEFT} R={PIN_RIGHT} S={PIN_SELECT} C={PIN_CAPTURE} F={PIN_FOCUS} BUZ={PIN_BUZZER}", flush=True)

DEBOUNCE_S=0.030;SELECT_HOLD_TO_QUIT=2.0;COMBO_QUIT_HOLD_S=1.5;POLL_INTERVAL_S=0.0015
NAV_MIN_GAP_S=0.18;SELECT_MIN_GAP_S=0.18;CAPTURE_MIN_GAP_S=0.40
REPEAT_DELAY_S=0.40;REPEAT_INTERVAL_S=0.08

def start_liveview():
    if not LIVEVIEW.exists(): sys.exit(1)
    try: os.remove(PAUSE_FLAG)
    except: pass
    return subprocess.Popen([PYTHON,"-u",str(LIVEVIEW)],cwd=str(HERE),start_new_session=True)

def pg_kill(p,s):
    try: os.killpg(os.getpgid(p.pid),s)
    except: pass
def wait_flag(path,want,t):
    end=time.time()+t
    while time.time()<end:
        if os.path.exists(path)==want: return True
        time.sleep(0.01)
    return os.path.exists(path)==want
def pause_lv(p): pg_kill(p,signal.SIGUSR1); wait_flag(PAUSE_FLAG,True,1.5); time.sleep(0.04)
def resume_lv(p): pg_kill(p,signal.SIGUSR2); wait_flag(PAUSE_FLAG,False,2.0)
def stop_lv(p):
    if not p or p.poll() is not None: return
    for s,t in((signal.SIGTERM,0.7),(signal.SIGINT,0.5),(signal.SIGKILL,0.3)):
        pg_kill(p,s)
        try: p.wait(timeout=t); return
        except: continue

def do_capture():
    """Request inline capture from LiveView via flag file."""
    try:
        # Clear stale flags
        for f in("/tmp/saturnix_captured","/tmp/saturnix_capture_done"):
            try: os.remove(f)
            except: pass
        # Write request
        with open("/tmp/saturnix_capture_request","w") as f: f.write("1")
    except Exception as e:
        print(f"[CAP] req err: {e}",flush=True)
        return 1
    # Wait for capture done flag (max 60s for film processing)
    end=time.time()+60
    while time.time()<end:
        if os.path.exists("/tmp/saturnix_capture_done"):
            try: os.remove("/tmp/saturnix_capture_done")
            except: pass
            return 0
        time.sleep(0.05)
    return 2  # timeout

def send_cmd(cmd):
    try:
        tmp=f"{UI_CMD_FILE}.tmp"
        with open(tmp,"w") as f: f.write(cmd)
        os.replace(tmp,UI_CMD_FILE)
    except: pass

def read_af():
    try:
        with open(AF_STATE_FILE) as f: return f.read().strip()
    except: return "idle"

def gpio_init():
    GPIO.setmode(GPIO.BCM); GPIO.setwarnings(False)
    for p in ALL_PINS:
        try: GPIO.remove_event_detect(p)
        except: pass
    try: GPIO.cleanup(ALL_PINS)
    except: pass
    for p in(PIN_LEFT,PIN_RIGHT,PIN_SELECT,PIN_CAPTURE,PIN_FOCUS):
        GPIO.setup(p,GPIO.IN,pull_up_down=GPIO.PUD_UP)

class Btn:
    __slots__=("pin","lr","db","lc","pa")
    def __init__(s,p): s.pin=p; s.lr=True; s.db=True; s.lc=time.monotonic(); s.pa=None
    def read(s):
        n=time.monotonic(); r=bool(GPIO.input(s.pin))
        if r!=s.lr: s.lr=r; s.lc=n
        if n-s.lc>=DEBOUNCE_S: s.db=r
    def pressed(s): return not s.db

class RL:
    def __init__(s): s.l={"L":0.0,"R":0.0,"S":0.0,"C":0.0}
    def can(s,k,n):
        g=NAV_MIN_GAP_S if k in("L","R") else CAPTURE_MIN_GAP_S if k=="C" else SELECT_MIN_GAP_S
        if n-s.l[k]>=g: s.l[k]=n; return True
        return False

def _is_in_menu():
    """Check if LiveView is in a menu/fullscreen mode (not liveview)."""
    # We check the pause flag — if not paused and we're about to capture,
    # send EXIT_TO_LIVE if we detect a menu mode.
    # Simple approach: always send EXIT_TO_LIVE first, if we're not sure.
    # Better: read ui_mode from a file LiveView writes.
    try:
        with open(UI_MODE_FILE) as f: mode=f.read().strip()
        return mode not in ("main","submenu","mf_live","")
    except: return False

def main():
    print("SATURNIX DIONE v1.0",flush=True)
    gpio_init()
    HW_JSON=str(HERE/"config.json")
    buzzer.init(PIN_BUZZER, hw_json=HW_JSON)
    # Check saved sound setting before startup sound
    _cfg_path = os.path.join(str(HERE), "saturnix_config.json")
    try:
        with open(_cfg_path) as f:
            _cfg = json.load(f)
        vol = _cfg.get("volume", "MED").upper()
        buzzer.set_volume(vol)
    except:
        pass
    buzzer.startup()
    lv=start_liveview()

    bl=Btn(PIN_LEFT);br=Btn(PIN_RIGHT);bs=Btn(PIN_SELECT)
    bc=Btn(PIN_CAPTURE);bf=Btn(PIN_FOCUS)
    pl=pr=ps=pc=pf=False; rl=RL()
    combo_at=None;combo_fired=False
    lp_ts=None;rp_ts=None;ll_rep=0.0;rl_rep=0.0
    _af_snd="idle"

    actions=deque(); running=True
    lv_restarts=deque(maxlen=5)  # timestamps of recent LiveView restarts
    try:
        while running:
            if lv.poll() is not None:
                now_r=time.monotonic()
                lv_restarts.append(now_r)
                # 5 deaths within 60s => something is fatally wrong
                # (e.g. camera missing). Stop instead of looping forever.
                if len(lv_restarts)==5 and now_r-lv_restarts[0]<60.0:
                    print("[ERR] LiveView crash loop — giving up",flush=True)
                    buzzer.error(); running=False; continue
                lv=start_liveview()

            bl.read();br.read();bs.read();bc.read();bf.read()
            cl=bl.pressed();cr=br.pressed();cs=bs.pressed()
            cc=bc.pressed();cf=bf.pressed();now=time.monotonic()

            # Combo quit
            if cl and cr:
                if combo_at is None: combo_at=now; combo_fired=False
                elif not combo_fired and now-combo_at>=COMBO_QUIT_HOLD_S:
                    actions.append(("quit",None)); combo_fired=True
            else: combo_at=None; combo_fired=False

            # LEFT + repeat
            if cl and not pl: actions.append(("ui","LEFT")); buzzer.click(); lp_ts=now; ll_rep=now
            elif cl and lp_ts is not None:
                if now-lp_ts>=REPEAT_DELAY_S and now-ll_rep>=REPEAT_INTERVAL_S:
                    actions.append(("ui","LEFT")); ll_rep=now
            if not cl: lp_ts=None

            # RIGHT + repeat
            if cr and not pr: actions.append(("ui","RIGHT")); buzzer.click(); rp_ts=now; rl_rep=now
            elif cr and rp_ts is not None:
                if now-rp_ts>=REPEAT_DELAY_S and now-rl_rep>=REPEAT_INTERVAL_S:
                    actions.append(("ui","RIGHT")); rl_rep=now
            if not cr: rp_ts=None

            # SELECT
            if cs and not ps and rl.can("S",now):
                bs.pa=now; actions.append(("ui","SELECT")); buzzer.select()
            if not cs and ps:
                if bs.pa and now-bs.pa>=SELECT_HOLD_TO_QUIT: actions.append(("quit",None))
                bs.pa=None

            # CAPTURE: in menu → exit to live; in liveview → take photo
            if cc and not pc and rl.can("C",now):
                if _is_in_menu():
                    send_cmd("EXIT_TO_LIVE"); buzzer.click()
                else:
                    buzzer.shutter(); actions.append(("capture",None))

            # FOCUS
            if cf and not pf: send_cmd("FOCUS_START"); buzzer.focus_start(); _af_snd="focusing"
            if not cf and pf: send_cmd("FOCUS_STOP"); buzzer.focus_stop(); _af_snd="idle"
            if cf and _af_snd=="focusing":
                af=read_af()
                if af=="focused": buzzer.focus_stop(); buzzer.focus_ok(); _af_snd="focused"
                elif af=="failed": buzzer.focus_stop(); buzzer.focus_fail(); _af_snd="failed"

            pl,pr,ps,pc,pf=cl,cr,cs,cc,cf

            if actions:
                k,p2=actions.popleft()
                if k=="ui": send_cmd(p2)
                elif k=="capture":
                    rc=do_capture()
                    if rc==0: buzzer.done()
                    else: buzzer.error()
                elif k=="quit": buzzer.poweroff(); running=False

            time.sleep(POLL_INTERVAL_S)
    finally:
        try: buzzer.cleanup()
        except: pass
        try: stop_lv(lv)
        finally: GPIO.cleanup(ALL_PINS)
        print("Bye.",flush=True)

if __name__=="__main__": main()
