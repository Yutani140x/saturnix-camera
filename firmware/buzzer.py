#!/usr/bin/env python3
# buzzer.py — Clean analog sound feedback for SATURNIX Dione.
# Passive buzzer on GPIO pin, software PWM.
# Tones in 800-1500Hz sweet spot for piezo. Volume via duty cycle.

import time, threading, os

_pwm = None
_pin = None
_focus_active = False
_focus_thread = None

SOUND_MUTE_FLAG = "/tmp/saturnix_sound_off"
_HW_JSON = None  # set by init()
_USER_CFG = None  # path to saturnix_config.json (live preferences)
_user_cfg_t = 0.0  # last mtime of user config

# Volume: duty cycle mapping
_VOL_DUTY = {"OFF": 0, "LOW": 8, "MED": 20, "HIGH": 45}
_volume = "MED"

def _load_volume():
    """Read volume from hw config."""
    global _volume
    try:
        import json
        if _HW_JSON and os.path.exists(_HW_JSON):
            with open(_HW_JSON) as f:
                v = json.load(f).get("volume", "MED").upper()
                if v in _VOL_DUTY:
                    _volume = v
    except:
        pass

def _refresh_volume():
    """Re-read volume from user config if it changed (cheap check via mtime)."""
    global _volume, _user_cfg_t
    if not _USER_CFG:
        return
    try:
        mt = os.path.getmtime(_USER_CFG)
        if mt == _user_cfg_t:
            return
        _user_cfg_t = mt
        import json
        with open(_USER_CFG) as f:
            v = json.load(f).get("volume", _volume).upper()
            if v in _VOL_DUTY:
                _volume = v
    except:
        pass

def _duty():
    return _VOL_DUTY.get(_volume, 20)

def init(pin, hw_json=None, user_cfg=None):
    global _pwm, _pin, _HW_JSON, _USER_CFG
    _pin = pin
    _HW_JSON = hw_json
    if user_cfg:
        _USER_CFG = user_cfg
    elif hw_json:
        # Default: saturnix_config.json next to hw json
        _USER_CFG = os.path.join(os.path.dirname(hw_json), "saturnix_config.json")
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)  # LOW-trigger: HIGH = off
        _pwm = GPIO.PWM(pin, 440)
        _pwm.start(0)  # start PWM with 0% duty (silent)
    except Exception as e:
        print(f"[WARN] buzzer init: {e}", flush=True)
    _load_volume()
    _refresh_volume()

def cleanup():
    global _pwm, _focus_active
    _focus_active = False
    if _pwm:
        try:
            _pwm.stop()
        except:
            pass

def is_muted():
    _refresh_volume()  # pick up latest volume change from user config
    if _volume == "OFF":
        return True
    return os.path.exists(SOUND_MUTE_FLAG)

def set_muted(muted: bool):
    if muted:
        try:
            with open(SOUND_MUTE_FLAG, "w") as f:
                f.write("1")
        except:
            pass
    else:
        try:
            os.remove(SOUND_MUTE_FLAG)
        except:
            pass

# ======================================================================
#   CORE: tone and sweep
# ======================================================================

def _tone(freq, duration):
    """Play a fixed tone."""
    if _pwm is None or is_muted():
        return
    try:
        _pwm.ChangeFrequency(max(20, freq))
        _pwm.ChangeDutyCycle(_duty())
        time.sleep(duration)
        _pwm.ChangeDutyCycle(0)
    except:
        pass

def _sweep(f_start, f_end, duration, steps=0):
    """Smooth frequency sweep from f_start to f_end over duration.
    Uses ~15ms per step for reliable software PWM."""
    if _pwm is None or is_muted():
        return
    if steps <= 0:
        steps = max(4, int(duration / 0.015))  # ~15ms per step
    dt = duration / steps
    df = (f_end - f_start) / steps
    duty = _duty()
    try:
        freq = f_start
        _pwm.ChangeFrequency(max(20, int(freq)))
        _pwm.ChangeDutyCycle(duty)
        for i in range(steps):
            freq += df
            _pwm.ChangeFrequency(max(20, int(freq)))
            time.sleep(dt)
        _pwm.ChangeDutyCycle(0)
    except:
        try:
            _pwm.ChangeDutyCycle(0)
        except:
            pass

def _play(sequence):
    """Play a sequence of (freq, duration) or ('sweep', f1, f2, dur)."""
    if is_muted():
        return
    for item in sequence:
        if isinstance(item, tuple) and len(item) == 4 and item[0] == "sweep":
            _, f1, f2, dur = item
            _sweep(f1, f2, dur)
        elif isinstance(item, tuple) and len(item) == 2:
            freq, dur = item
            if freq == 0:
                time.sleep(dur)
            else:
                _tone(freq, dur)

def _play_async(sequence):
    t = threading.Thread(target=_play, args=(sequence,), daemon=True)
    t.start()
    return t

# ======================================================================
#   SOUND DEFINITIONS — clean analog tones
#   Sweet spot for passive piezo: 800-1500Hz
#   Min tone ~20ms to sound musical, not clicky.
# ======================================================================

def startup():
    """System online — gentle tone."""
    _play_async([(1000, 0.08), (0, 0.06), (1200, 0.10)])

def click():
    """Navigation — soft tick."""
    _play_async([(1100, 0.015)])

def select():
    """Confirm — ascending pair."""
    _play_async([(900, 0.030), (0, 0.020), (1200, 0.035)])

def shutter():
    """REC — crisp electronic click."""
    _play_async([(1500, 0.020), (0, 0.025), (1000, 0.025)])

def done():
    """Capture complete — three gentle ascending tones."""
    _play_async([(800, 0.035), (0, 0.030), (1000, 0.035), (0, 0.030), (1300, 0.045)])

def error():
    """Error — two descending tones."""
    _play_async([(900, 0.060), (0, 0.035), (650, 0.080)])

def focus_ok():
    """Focus locked — quick ascending pair."""
    _play_async([(1000, 0.025), (0, 0.015), (1400, 0.030)])

def focus_fail():
    """Focus failed — descending pair."""
    _play_async([(1000, 0.040), (0, 0.025), (700, 0.050)])

def poweroff():
    """System shutdown — gentle descending sequence."""
    _play([
        (1200, 0.070), (0, 0.040),
        (900, 0.070), (0, 0.040),
        (600, 0.090), (0, 0.030),
        (400, 0.120),
    ])

def wifi_on():
    """Network interface enabled."""
    _play_async([(900, 0.030), (0, 0.020), (1300, 0.035)])

def wifi_off():
    """Network interface disabled."""
    _play_async([(1200, 0.030), (0, 0.020), (800, 0.035)])

def gallery():
    """Gallery enter — soft double ping."""
    _play_async([(1100, 0.020), (0, 0.030), (1100, 0.020)])

def delete():
    """Purge confirm."""
    _play_async([(700, 0.045), (0, 0.025), (500, 0.055)])

def tick():
    """Processing heartbeat."""
    _play_async([(1000, 0.012)])

def burst_start():
    """Burst sequence begin — quick ascending pair."""
    _play_async([(1100, 0.020), (0, 0.015), (1500, 0.030)])

def burst_end():
    """Burst sequence complete — descending pair."""
    _play_async([(1300, 0.025), (0, 0.020), (900, 0.040)])

def battery_critical():
    """Critical battery warning — three urgent low beeps.
    Synchronous (blocks) so it's heard before screen updates."""
    _play([
        (650, 0.080), (0, 0.050),
        (650, 0.080), (0, 0.050),
        (650, 0.080),
    ])

def timer_tick():
    """Self-timer countdown tick — very subtle."""
    _play_async([(900, 0.010)])

def timer_done():
    """Self-timer reached zero — like shutter."""
    shutter()

def hdr_progress():
    """One frame of HDR captured — short ascending tone."""
    _play_async([(1200, 0.025)])

# ======================================================================
#   FOCUS CONTINUOUS PULSE (start/stop)
# ======================================================================

def focus_start():
    """Start pulsing sweep while focus button held."""
    global _focus_active, _focus_thread
    if is_muted() or _pwm is None:
        return
    _focus_active = True
    def _pulse():
        while _focus_active:
            if is_muted():
                time.sleep(0.05)
                continue
            _tone(1000, 0.015)
            time.sleep(0.10)
    _focus_thread = threading.Thread(target=_pulse, daemon=True)
    _focus_thread.start()

def focus_stop():
    """Stop focus pulsing."""
    global _focus_active, _focus_thread
    _focus_active = False
    if _focus_thread:
        try:
            _focus_thread.join(timeout=0.3)
        except:
            pass
        _focus_thread = None
    if _pwm:
        try:
            _pwm.ChangeDutyCycle(0)
        except:
            pass

# ======================================================================
#   VOLUME CONTROL
# ======================================================================

def set_volume(level):
    """Set volume level: OFF, LOW, MED, HIGH."""
    global _volume
    level = level.upper()
    if level in _VOL_DUTY:
        _volume = level
    if level == "OFF":
        set_muted(True)
    else:
        set_muted(False)

def get_volume():
    return _volume
