#!/usr/bin/env python3
# One-shot capture for IMX519 16MP Autofocus (JPG / DNG / JPG+DNG).
# Film simulation: post-processes JPG with color grading, grain, vignette.
# Sequential naming: Saturnix_00, Saturnix_01, ...

import os, sys, json, glob, re, shutil, subprocess
from pathlib import Path

# IMX519 full resolution
WIDTH, HEIGHT = 4656, 3496
_HW_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
try:
    import json as _json
    with open(_HW_JSON) as _f: _hwc = _json.load(_f)
    _res = _hwc.get("resolution", [4656, 3496])
    WIDTH, HEIGHT = int(_res[0]), int(_res[1])
except: pass
_HERE = Path(__file__).resolve().parent
OUT_DIR  = str(_HERE / "Pictures")
PREFIX   = "Saturnix"
SETTINGS_JSON = "/tmp/saturnix_settings.json"

_NUM_RE = re.compile(r'^Saturnix_(\d+)')
_RPICAM = shutil.which("rpicam-still") or shutil.which("libcamera-still")
_PROG_FILE = "/tmp/saturnix_film_progress"

def _prog(step, total):
    """Write film processing progress for LiveView to display."""
    try:
        with open(_PROG_FILE, "w") as f: f.write(f"{step}/{total}")
    except: pass

def load_settings():
    try:
        with open(SETTINGS_JSON, "r") as f: return json.load(f)
    except Exception:
        return {}

def next_filename():
    os.makedirs(OUT_DIR, exist_ok=True)
    max_num = -1
    for fpath in glob.iglob(os.path.join(OUT_DIR, f"{PREFIX}_*")):
        base = os.path.splitext(os.path.basename(fpath))[0]
        m = _NUM_RE.match(base)
        if m:
            n = int(m.group(1))
            if n > max_num:
                max_num = n
    return f"{PREFIX}_{max_num + 1:02d}"

# ======================================================================
#                FILM POST-PROCESSING
# ======================================================================

# Old (trademark) names are accepted as aliases so previously saved
# configs keep working after the rename.
FILM_ALIASES = {
    "Gold": "S-Gold", "Ektar": "S-Vivid", "Fuji": "S-Natural",
    "TriX": "S-MonoX", "S-Anime": "S-Saturnix",
}

def film_canonical(name):
    """Map any historical film name to its current canonical name."""
    return FILM_ALIASES.get(name, name)

FILM_PROFILES = {
    "S-Gold": {
        # Kodak Gold 400: warm, soft, creamy, vintage
        "color_r": 1.12, "color_g": 1.00, "color_b": 0.80,
        "saturation": 1.30, "contrast": 1.08, "brightness": 1.03,
        "shadow_r": 30, "shadow_g": 20, "shadow_b": 5,
        "lift_shadows": 18, "compress_highlights": -12,
        "grain": 14, "vignette": 0.45,
    },
    "S-Vivid": {
        # Kodak Ektar 100: neutral, hyper-saturated, razor sharp, max contrast
        "color_r": 0.98, "color_g": 1.00, "color_b": 1.03,
        "saturation": 1.85, "contrast": 1.50, "brightness": 1.00,
        "shadow_r": 0, "shadow_g": 0, "shadow_b": 0,
        "lift_shadows": 0, "compress_highlights": 0,
        "grain": 2, "vignette": 0.05,
    },
    "S-Natural": {
        # Fujifilm 400: cool greens, moderate saturation
        "color_r": 0.92, "color_g": 1.02, "color_b": 1.08,
        "saturation": 1.20, "contrast": 1.10, "brightness": 1.00,
        "shadow_r": 5, "shadow_g": 18, "shadow_b": 14,
        "lift_shadows": 12, "compress_highlights": -8,
        "grain": 10, "vignette": 0.40,
    },
    "S-Saturnix": {
        # Signature preset: golden warm light, lifted indigo shadows,
        # soft contrast, anime-style bloom (added by apply_saturnix()).
        # Green channel is pulled DOWN slightly and blue is kept neutral —
        # warmth must come from red, not from a green cast.
        "color_r": 1.10, "color_g": 0.97, "color_b": 1.00,
        "saturation": 1.26, "contrast": 1.04, "brightness": 1.02,
        "shadow_r": 12, "shadow_g": 6, "shadow_b": 40,
        "lift_shadows": 20, "compress_highlights": -6,
        "grain": 6, "vignette": 0.18,
    },
}


def apply_vhs(jpg_path):
    """VHS tape simulation v2.
    Reworked: all color/tape work happens at HALF resolution (4x less CPU
    and RAM than v1, which processed the full 16MP frame), then the frame
    is upscaled with NEAREST for that crunchy analog pixel look.
    New artifacts vs v1: tracking-error band displacement, ghosting echo,
    and a head-switching noise bar at the bottom of the frame.
    """
    from PIL import Image, ImageEnhance, ImageChops
    import numpy as np
    N = 8; _prog(0, N)

    print("[FILM] PROCESSING VHS...", flush=True)
    t0 = __import__("time").monotonic()

    img = Image.open(jpg_path).convert("RGB")
    W, H = img.size
    pw, ph = W // 2, H // 2
    img = img.resize((pw, ph), Image.BILINEAR); _prog(1, N)

    # 1) Tape softness: crush detail down and back up
    img = img.resize((pw // 2, ph // 2), Image.BILINEAR)
    img = img.resize((pw, ph), Image.NEAREST)

    # 2) Chromatic aberration (color misregistration)
    r, g, b = img.split()
    shift = max(2, pw // 300)
    r = ImageChops.offset(r, shift, 0); b = ImageChops.offset(b, -shift, 0)
    img = Image.merge("RGB", (r, g, b)); _prog(2, N)

    # 3) Tint + lifted shadows (combined LUT, same curve as v1)
    lut_r = [min(255, int(20 + int(i * 1.10) * 0.88)) for i in range(256)]
    lut_g = [min(255, int(20 + int(i * 0.92) * 0.88)) for i in range(256)]
    lut_b = [min(255, int(20 + int(i * 1.05) * 0.88)) for i in range(256)]
    img = img.point(lut_r + lut_g + lut_b); _prog(3, N)

    # 4) Low saturation + contrast
    img = ImageEnhance.Color(img).enhance(0.65)
    img = ImageEnhance.Contrast(img).enhance(0.80)

    # 5) Ghosting echo (signal reflection)
    ghost = ImageChops.offset(img, max(3, pw // 160), 0)
    img = Image.blend(img, ghost, 0.10)
    del ghost; _prog(4, N)

    # 6) Tracking errors: shift a few random horizontal bands sideways
    arr = np.array(img)
    rng = np.random.default_rng()
    for _ in range(rng.integers(2, 5)):
        bh = int(rng.integers(3, max(4, ph // 60)))
        y = int(rng.integers(0, ph - bh))
        dx = int(rng.integers(4, max(5, pw // 60))) * (1 if rng.random() < 0.5 else -1)
        arr[y:y + bh] = np.roll(arr[y:y + bh], dx, axis=1)
        # slight luma pop on the glitched band
        band = arr[y:y + bh].astype(np.int16) + 12
        arr[y:y + bh] = np.clip(band, 0, 255).astype(np.uint8)
    _prog(5, N)

    # 7) Head-switching noise bar at the very bottom of the frame
    hs = max(2, ph // 80)
    noise_bar = rng.integers(0, 90, (hs, pw, 3), dtype=np.uint8)
    bottom = arr[ph - hs:ph].astype(np.int16)
    bottom = np.roll(bottom, int(rng.integers(pw // 40, pw // 12)), axis=1)
    arr[ph - hs:ph] = np.clip(bottom // 2 + noise_bar, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    del arr, noise_bar, bottom; _prog(6, N)

    # 8) Upscale to full res, then full-res scanlines + noise
    img = img.resize((W, H), Image.NEAREST)
    from PIL import ImageDraw as IDraw
    d = IDraw.Draw(img)
    for y in range(0, H, 4):
        d.line([(0, y), (W, y)], fill=(0, 0, 0), width=2)
    nw, nh = W // 6, H // 6
    noise = Image.frombytes("L", (nw, nh), os.urandom(nw * nh))
    noise = noise.resize((W, H), Image.NEAREST)
    noise_rgb = Image.merge("RGB", (noise, noise, noise))
    del noise
    img = Image.blend(img, noise_rgb, 0.08)
    del noise_rgb; _prog(7, N)

    img.save(jpg_path, "JPEG", quality=85); _prog(N, N)
    dt = __import__("time").monotonic() - t0
    print(f"[FILM] VHS COMPLETE in {dt:.1f}s", flush=True)


def apply_saturnix(jpg_path):
    """S-Saturnix: signature retro cel-animation look — golden warm light, lifted indigo
    shadows, gentle contrast and a soft highlight bloom.
    Processed at HALF resolution (like S-MonoX): the softness is part of
    the look and it keeps peak RAM low on the Pi Zero.
    """
    from PIL import Image, ImageEnhance, ImageChops, ImageFilter, ImageStat
    N = 6; _prog(0, N)

    p = FILM_PROFILES["S-Saturnix"]
    print("[FILM] PROCESSING S-SATURNIX...", flush=True)
    t0 = __import__("time").monotonic()

    img = Image.open(jpg_path).convert("RGB")
    W, H = img.size
    pw, ph = W // 2, H // 2
    img = img.resize((pw, ph), Image.LANCZOS); _prog(1, N)

    # 1) Warm/indigo grade (same LUT construction as apply_film)
    cr, cg, cb = p["color_r"], p["color_g"], p["color_b"]
    lift, comp = p["lift_shadows"], p["compress_highlights"]
    sr, sg, sb = p["shadow_r"], p["shadow_g"], p["shadow_b"]

    def make_lut(cm, sh):
        lut = []
        for i in range(256):
            v = min(255, int(i * cm))
            frac = v / 255.0
            v = int(v + lift * (1.0 - frac) + comp * frac)
            v = max(0, min(255, v))
            v = min(255, v + int(sh * (1.0 - v / 255.0)))
            lut.append(v)
        return lut

    img = img.point(make_lut(cr, sr) + make_lut(cg, sg) + make_lut(cb, sb)); _prog(2, N)

    # 2) Saturation, then fused Contrast+Brightness (one LUT pass)
    img = ImageEnhance.Color(img).enhance(p["saturation"])
    mean = int(ImageStat.Stat(img.convert("L")).mean[0] + 0.5)
    c, b = p["contrast"], p["brightness"]
    cb_lut = [int(max(0.0, min(255.0,
              max(0.0, min(255.0, mean + (i - mean) * c)) * b)))
              for i in range(256)]
    img = img.point(cb_lut * 3); _prog(3, N)

    # 3) Bloom: soft-threshold the highlights, blur them small, screen back
    lum = img.convert("L")
    hi_lut = [0] * 170 + [int((i - 170) * 3.0) if (i - 170) * 3.0 < 255 else 255
              for i in range(170, 256)]
    mask = lum.point(hi_lut)
    del lum
    glow = Image.composite(img, Image.new("RGB", (pw, ph), (0, 0, 0)), mask)
    del mask
    glow = glow.resize((pw // 4, ph // 4), Image.BILINEAR)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=5))
    glow = glow.resize((pw, ph), Image.BILINEAR)
    glow = glow.point([int(i * 0.60) for i in range(256)]      # R
                      + [int(i * 0.50) for i in range(256)]    # G
                      + [int(i * 0.42) for i in range(256)])   # B — golden bloom
    img = ImageChops.screen(img, glow)
    del glow; _prog(4, N)

    # 4) Vignette (at half res)
    vig_s = p["vignette"]
    if vig_s > 0:
        VW, VH = 64, 48; vig_data = bytearray(VW * VH)
        vcx, vcy = VW / 2.0, VH / 2.0; mr2 = vcx * vcx + vcy * vcy
        for y2 in range(VH):
            dy = y2 - vcy
            for x2 in range(VW):
                dx = x2 - vcx
                vig_data[y2 * VW + x2] = int(255 * max(0.0, 1.0 - vig_s * ((dx*dx+dy*dy)/mr2)))
        vig_mask = Image.frombytes("L", (VW, VH), bytes(vig_data)).resize((pw, ph), Image.BILINEAR)
        img = Image.composite(img, Image.new("RGB", (pw, ph), (0, 0, 0)), vig_mask)
        del vig_mask

    # 5) Upscale + fine grain
    img = img.resize((W, H), Image.LANCZOS); _prog(5, N)
    grain_amt = p["grain"]
    if grain_amt > 0:
        gw, gh = W // 8, H // 8
        noise = Image.frombytes("L", (gw, gh), os.urandom(gw * gh))
        noise = noise.resize((W, H), Image.NEAREST)
        noise_rgb = Image.merge("RGB", (noise, noise, noise))
        del noise
        img = Image.blend(img, noise_rgb, grain_amt / 255.0)
        del noise_rgb

    img.save(jpg_path, "JPEG", quality=92); _prog(N, N)
    dt = __import__("time").monotonic() - t0
    print(f"[FILM] S-SATURNIX COMPLETE in {dt:.1f}s", flush=True)


def apply_trix(jpg_path):
    """Apply Kodak Tri-X 400 B&W simulation. Optimized: process at 1/2 res."""
    from PIL import Image, ImageEnhance, ImageChops
    N=6; _prog(0,N)

    print("[FILM] PROCESSING TRI-X 400...", flush=True)
    t0 = __import__("time").monotonic()

    img = Image.open(jpg_path).convert("RGB")
    orig_w, orig_h = img.size
    pw, ph = orig_w // 2, orig_h // 2
    img = img.resize((pw, ph), Image.LANCZOS); _prog(1,N)

    # 1) B&W panchromatic
    r, g, b = img.split()
    r_w = r.point([int(i * 0.25) for i in range(256)])
    g_w = g.point([int(i * 0.60) for i in range(256)])
    b_w = b.point([int(i * 0.15) for i in range(256)])
    lum = ImageChops.add(ImageChops.add(r_w, g_w), b_w)
    img = Image.merge("RGB", (lum, lum, lum)); _prog(2,N)

    # 2) S-curve + Contrast + Brightness
    s_lut = []
    for i in range(256):
        x = i / 255.0
        if x < 0.08: v = x * 0.3
        elif x > 0.92: v = 0.92 + (x - 0.92) * 1.2
        else:
            t = (x - 0.08) / 0.84
            v = 0.024 + 0.976 * (t * t * (3 - 2 * t))
        s_lut.append(max(0, min(255, int(v * 255))))
    img = img.point(s_lut * 3)
    img = ImageEnhance.Contrast(img).enhance(1.45)
    img = ImageEnhance.Brightness(img).enhance(1.03)
    img = ImageEnhance.Sharpness(img).enhance(1.5); _prog(3,N)

    # 3) Vignette
    VW, VH = 64, 48; vig_data = bytearray(VW * VH)
    vcx, vcy = VW / 2.0, VH / 2.0; mr2 = vcx * vcx + vcy * vcy
    for y2 in range(VH):
        dy = y2 - vcy
        for x2 in range(VW):
            dx = x2 - vcx
            vig_data[y2 * VW + x2] = int(255 * max(0.0, 1.0 - 0.30 * ((dx*dx+dy*dy)/mr2)))
    vig_mask = Image.frombytes("L", (VW, VH), bytes(vig_data)).resize((pw, ph), Image.BILINEAR)
    img = Image.composite(img, Image.new("RGB", (pw, ph), (0,0,0)), vig_mask); _prog(4,N)

    # Upscale + Grain
    img = img.resize((orig_w, orig_h), Image.LANCZOS)
    gw, gh = orig_w // 6, orig_h // 6
    noise = Image.frombytes("L", (gw, gh), os.urandom(gw * gh))
    noise = noise.resize((orig_w, orig_h), Image.NEAREST)
    noise_rgb = Image.merge("RGB", (noise, noise, noise))
    img = Image.blend(img, noise_rgb, 16 / 255.0); _prog(5,N)

    img.save(jpg_path, "JPEG", quality=92); _prog(N,N)
    dt = __import__("time").monotonic() - t0
    print(f"[FILM] TRI-X COMPLETE in {dt:.1f}s", flush=True)

def apply_film(jpg_path, film_name):
    """Apply film simulation (Gold/Ektar/Fuji). Full resolution.
    Optimized: Contrast+Brightness are fused into a single point() LUT
    (bit-exact vs the sequential ImageEnhance calls, ~2 fewer full-frame
    passes), and intermediates are freed eagerly to cap peak RAM."""
    from PIL import Image, ImageEnhance, ImageStat
    N=5; _prog(0,N)

    film_name = film_canonical(film_name)
    p = FILM_PROFILES.get(film_name)
    if not p:
        return

    print(f"[FILM] PROCESSING {film_name}...", flush=True)
    t0 = __import__("time").monotonic()

    img = Image.open(jpg_path).convert("RGB")
    w, h = img.size; _prog(1,N)

    # 1) Color temperature + tone curve + shadow tint (combined LUTs)
    cr, cg, cb = p["color_r"], p["color_g"], p["color_b"]
    lift, comp = p["lift_shadows"], p["compress_highlights"]
    sr, sg, sb = p["shadow_r"], p["shadow_g"], p["shadow_b"]

    def make_lut(cm, sh):
        lut = []
        for i in range(256):
            v = min(255, int(i * cm))
            frac = v / 255.0
            v = int(v + lift * (1.0 - frac) + comp * frac)
            v = max(0, min(255, v))
            v = min(255, v + int(sh * (1.0 - v / 255.0)))
            lut.append(v)
        return lut

    img = img.point(make_lut(cr, sr) + make_lut(cg, sg) + make_lut(cb, sb)); _prog(2,N)

    # 2) Saturation (cross-channel — stays as ImageEnhance)
    img = ImageEnhance.Color(img).enhance(p["saturation"])

    # 3) Contrast + Brightness fused into ONE LUT pass.
    #    PIL Contrast: round(mean + (v-mean)*c), Brightness: round(v*b) —
    #    both are per-value maps, so the fused LUT reproduces them exactly.
    mean = int(ImageStat.Stat(img.convert("L")).mean[0] + 0.5)
    c, b = p["contrast"], p["brightness"]
    # PIL's blend computes in C float32 and truncates on the uint8 cast when
    # factor > 1 — emulate both to stay bit-identical to sequential enhances.
    import numpy as _np
    _f = _np.float32
    cb_lut = []
    for i in range(256):
        v = int(max(_f(0.0), min(_f(255.0), _f(mean) + _f(c) * _f(i - mean))))
        v = int(max(_f(0.0), min(_f(255.0), _f(b) * _f(v))))
        cb_lut.append(v)
    img = img.point(cb_lut * 3); _prog(3,N)

    # 4) Vignette
    vig_s = p["vignette"]
    if vig_s > 0:
        VW, VH = 64, 48; vig_data = bytearray(VW * VH)
        vcx, vcy = VW / 2.0, VH / 2.0; mr2 = vcx * vcx + vcy * vcy
        for y2 in range(VH):
            dy = y2 - vcy
            for x2 in range(VW):
                dx = x2 - vcx
                vig_data[y2 * VW + x2] = int(255 * max(0.0, 1.0 - vig_s * ((dx*dx+dy*dy)/mr2)))
        vig_mask = Image.frombytes("L", (VW, VH), bytes(vig_data)).resize((w, h), Image.BILINEAR)
        img = Image.composite(img, Image.new("RGB", (w, h), (0,0,0)), vig_mask)
        del vig_mask

    # 5) Grain
    grain_amt = p["grain"]
    if grain_amt > 0:
        gw, gh = w // 8, h // 8
        noise = Image.frombytes("L", (gw, gh), os.urandom(gw * gh))
        noise = noise.resize((w, h), Image.NEAREST)
        noise_rgb = Image.merge("RGB", (noise, noise, noise))
        del noise
        img = Image.blend(img, noise_rgb, grain_amt / 255.0)
        del noise_rgb
    _prog(4,N)

    img.save(jpg_path, "JPEG", quality=92); _prog(N,N)
    dt = __import__("time").monotonic() - t0
    print(f"[FILM] COMPLETE in {dt:.1f}s", flush=True)


def _apply_film_pil(jpg_path, film_name):
    """Original PIL implementation (fallback)."""
    from PIL import Image, ImageEnhance
    N=5; _prog(0,N)

    p = FILM_PROFILES.get(film_name)
    if not p:
        return

    print(f"[FILM] PROCESSING {film_name}...", flush=True)
    t0 = __import__("time").monotonic()

    img = Image.open(jpg_path).convert("RGB")
    w, h = img.size; _prog(1,N)

    # 1) Color temperature + Tone curve + Shadow tint (combined LUTs)
    cr, cg, cb = p["color_r"], p["color_g"], p["color_b"]
    lift, comp = p["lift_shadows"], p["compress_highlights"]
    sr, sg, sb = p["shadow_r"], p["shadow_g"], p["shadow_b"]

    def make_lut(cm, sh):
        lut = []
        for i in range(256):
            v = min(255, int(i * cm))
            frac = v / 255.0
            v = int(v + lift * (1.0 - frac) + comp * frac)
            v = max(0, min(255, v))
            v = min(255, v + int(sh * (1.0 - v / 255.0)))
            lut.append(v)
        return lut

    img = img.point(make_lut(cr, sr) + make_lut(cg, sg) + make_lut(cb, sb)); _prog(2,N)

    # 2) Saturation + Contrast + Brightness
    img = ImageEnhance.Color(img).enhance(p["saturation"])
    img = ImageEnhance.Contrast(img).enhance(p["contrast"])
    img = ImageEnhance.Brightness(img).enhance(p["brightness"]); _prog(3,N)

    # 3) Vignette
    vig_s = p["vignette"]
    if vig_s > 0:
        VW, VH = 64, 48; vig_data = bytearray(VW * VH)
        vcx, vcy = VW / 2.0, VH / 2.0; mr2 = vcx * vcx + vcy * vcy
        for y2 in range(VH):
            dy = y2 - vcy
            for x2 in range(VW):
                dx = x2 - vcx
                vig_data[y2 * VW + x2] = int(255 * max(0.0, 1.0 - vig_s * ((dx*dx+dy*dy)/mr2)))
        vig_mask = Image.frombytes("L", (VW, VH), bytes(vig_data)).resize((w, h), Image.BILINEAR)
        img = Image.composite(img, Image.new("RGB", (w, h), (0,0,0)), vig_mask)

    # 4) Grain
    grain_amt = p["grain"]
    if grain_amt > 0:
        gw, gh = w // 8, h // 8
        noise = Image.frombytes("L", (gw, gh), os.urandom(gw * gh))
        noise = noise.resize((w, h), Image.NEAREST)
        noise_rgb = Image.merge("RGB", (noise, noise, noise))
        img = Image.blend(img, noise_rgb, grain_amt / 255.0)
    _prog(4,N)

    img.save(jpg_path, "JPEG", quality=92); _prog(N,N)
    dt = __import__("time").monotonic() - t0
    print(f"[FILM] COMPLETE in {dt:.1f}s", flush=True)

# ======================================================================
#                     MAIN CAPTURE
# ======================================================================

def _add_exif_and_watermark(jpg_path):
    """Apply EXIF metadata + optional watermark in-place to JPG.
    Reads settings/config to determine watermark on/off and text/color."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return
    # Load camera config
    try:
        with open(_HW_JSON) as f: cfg = json.load(f)
    except Exception:
        cfg = {}
    exif_make = cfg.get("exif_make", "SATURNIX")
    exif_model = cfg.get("exif_model", "Dione")
    exif_software = cfg.get("exif_software", "LantianFW v12-2504")
    wm_text = cfg.get("watermark_text", "SATURNIX • DIONE")
    wm_color = tuple(cfg.get("watermark_color", [232, 165, 61]))
    # Load user prefs (watermark on/off)
    user_cfg_path = os.path.join(os.path.dirname(_HW_JSON), "saturnix_config.json")
    wm_on = False
    try:
        with open(user_cfg_path) as f: uc = json.load(f)
        wm_on = (uc.get("watermark", "Off") == "On")
    except Exception:
        pass

    try:
        img = Image.open(jpg_path)
        # If watermark requested, draw it
        if wm_on:
            d = ImageDraw.Draw(img)
            # Choose font size: scales with image width (~2% of width)
            w, h = img.size
            font_size = max(12, int(w * 0.022))
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                    font_size)
            except Exception:
                font = ImageFont.load_default()
            try:
                x0, y0, x1, y1 = d.textbbox((0, 0), wm_text, font=font)
                tw = x1 - x0; th = y1 - y0
            except Exception:
                tw, th = font.getsize(wm_text) if hasattr(font, 'getsize') else (200, 20)
                x0, y0 = 0, 0
            margin = max(10, int(w * 0.02))
            tx = w - tw - margin - x0
            ty = h - th - margin - y0
            # Black shadow for legibility
            for dx, dy in ((1, 1), (2, 2)):
                d.text((tx + dx, ty + dy), wm_text, font=font, fill=(0, 0, 0))
            # Main text in warm yellow-orange
            d.text((tx, ty), wm_text, font=font, fill=wm_color)

        # Build EXIF and save
        try:
            exif = img.getexif()
            # 271=Make, 272=Model, 305=Software, 270=ImageDescription
            exif[271] = exif_make
            exif[272] = exif_model
            exif[305] = exif_software
            exif[270] = f"{exif_make} {exif_model}"
            img.save(jpg_path, "JPEG", quality=95, exif=exif)
        except Exception:
            # Fallback: save without EXIF helper
            img.save(jpg_path, "JPEG", quality=95)
    except Exception as e:
        print(f"[WARN] EXIF/watermark failed: {e}", flush=True)



def _build_capture_args(jpg_path, st, ev_override=None):
    """Build rpicam-still arguments for given settings + optional EV override."""
    exp_us     = st.get("exposure_us")
    gain       = st.get("gain")
    ev         = st.get("ev", 0.0) if ev_override is None else ev_override
    awb_auto   = st.get("awb_auto", True)
    wb_gains   = st.get("wb_gains")
    denoise    = st.get("denoise", "auto")
    jpegq      = int(st.get("jpeg_quality", 85))
    focus_mode = st.get("focus_mode", "afc")
    lens_pos   = st.get("lens_position", 0.0)
    photo_mode = st.get("photo_mode", "JPG+DNG")

    is_long = exp_us is not None and exp_us > 1_000_000
    timeout_ms = int(exp_us / 1000) + 3000 if is_long else 500

    args = [
        _RPICAM, "-n",
        "--timeout", str(timeout_ms),
        "--width",  str(WIDTH),
        "--height", str(HEIGHT),
        "--thumb", "none",
        "--quality", str(jpegq),
        "--denoise", denoise,
        "-o", jpg_path,
    ]
    if photo_mode in ("JPG+DNG", "DNG"):
        args.append("--raw")

    evf = 0.0
    try: evf = float(ev)
    except: pass

    if exp_us is not None:
        adjusted_us = int(max(100, min(30_000_000, exp_us * (2.0 ** evf))))
        args += ["--shutter", str(adjusted_us)]
        if adjusted_us > 1_000_000:
            timeout_ms = int(adjusted_us / 1000) + 3000
            idx = args.index("--timeout")
            args[idx + 1] = str(timeout_ms)
    else:
        if evf != 0.0:
            args += ["--ev", f"{evf:+.1f}"]

    if gain is not None:
        args += ["--gain", f"{float(gain):.3f}"]

    if not awb_auto and wb_gains:
        try:
            r, b = wb_gains
            args += ["--awbgains", f"{float(r):.3f},{float(b):.3f}"]
        except Exception: pass

    if focus_mode == "mf":
        args += ["--autofocus-mode", "manual"]
        args += ["--lens-position", f"{float(lens_pos):.2f}"]
    elif focus_mode == "afs":
        args += ["--autofocus-mode", "auto"]
    else:
        args += ["--autofocus-mode", "continuous"]

    return args, is_long


def main():
    if _RPICAM is None:
        print("[ERR] rpicam-still / libcamera-still not found", flush=True)
        sys.exit(127)

    os.makedirs(OUT_DIR, exist_ok=True)
    stem = next_filename()
    jpg  = os.path.join(OUT_DIR, f"{stem}.jpg")

    st = load_settings()
    photo_mode = st.get("photo_mode", "JPG+DNG")
    film       = st.get("film", "Off")
    hdr        = st.get("hdr", "Off")  # Off / 3-FILES / MERGED

    # Load HDR EV steps from hw config
    try:
        with open(_HW_JSON) as f: hwcfg = json.load(f)
        hdr_steps = hwcfg.get("hdr_ev_steps", [-2.0, 0.0, 2.0])
    except Exception:
        hdr_steps = [-2.0, 0.0, 2.0]

    # Film mode forces JPG only
    if film != "Off":
        photo_mode = "JPG"
    # HDR forces JPG only (film also disabled by UI when HDR on)
    if hdr != "Off":
        photo_mode = "JPG"
        film = "Off"
        st["photo_mode"] = "JPG"

    # ---------- HDR PATH ----------
    if hdr != "Off":
        ev_list = hdr_steps
        n = len(ev_list)
        bracket_paths = []
        for i, ev_off in enumerate(ev_list):
            bracket_jpg = os.path.join(OUT_DIR, f"{stem}_HDR{ev_off:+.0f}.jpg")
            args, is_long = _build_capture_args(bracket_jpg, st, ev_override=ev_off)
            proc_timeout = 60 if is_long else 15
            print(f"[HDR] frame {i+1}/{n} EV={ev_off:+.1f}", flush=True)
            _prog(i, n)
            r = subprocess.run(args, capture_output=True, text=True, timeout=proc_timeout)
            if r.returncode != 0:
                print(f"[ERR] HDR frame {i+1} rc={r.returncode}: {r.stderr[:200]}", flush=True)
                sys.exit(r.returncode)
            bracket_paths.append(bracket_jpg)

        # Signal capture done (camera free)
        try:
            with open("/tmp/saturnix_captured", "w") as f: f.write("1")
        except: pass

        # Apply watermark/EXIF to each bracket file
        for bp in bracket_paths:
            _add_exif_and_watermark(bp)

        try: os.remove(_PROG_FILE)
        except: pass
        print(f"[OK] {stem} HDR (3-FILES)", flush=True)
        return

    # ---------- NORMAL PATH ----------
    args, is_long = _build_capture_args(jpg, st)
    proc_timeout = 60 if is_long else 15
    result = subprocess.run(args, capture_output=True, text=True, timeout=proc_timeout)

    try:
        with open("/tmp/saturnix_captured", "w") as f: f.write("1")
    except: pass

    if result.returncode != 0:
        print(f"[ERR] capture rc={result.returncode}: {result.stderr[:200]}", flush=True)
        sys.exit(result.returncode)

    if photo_mode == "DNG":
        try: os.remove(jpg)
        except OSError: pass

    # Film post-processing (JPG only)
    if film != "Off" and os.path.exists(jpg):
        _prog(0,1)
        try:
            film = film_canonical(film)
            if film == "VHS":
                apply_vhs(jpg)
            elif film == "S-MonoX":
                apply_trix(jpg)
            elif film == "S-Saturnix":
                apply_saturnix(jpg)
            else:
                apply_film(jpg, film)
        except Exception as e:
            print(f"[WARN] Film processing failed: {e}", flush=True)

    # Apply EXIF metadata + optional watermark to JPG
    if photo_mode != "DNG" and os.path.exists(jpg):
        _add_exif_and_watermark(jpg)

    try: os.remove(_PROG_FILE)
    except: pass

    print(f"[OK] {stem} ({photo_mode}{' +' + film if film != 'Off' else ''})", flush=True)

if __name__ == "__main__":
    main()

# ======================================================================
#   LIBRARY API: callable from LiveView for inline film processing
# ======================================================================
def process_film(jpg_path, film_name):
    """Apply film simulation to an existing JPG file. Used by LiveView's
    inline capture for post-processing without subprocess overhead."""
    if film_name == "Off" or not os.path.exists(jpg_path):
        return
    _prog(0, 1)
    try:
        film_name = film_canonical(film_name)
        if film_name == "VHS":
            apply_vhs(jpg_path)
        elif film_name == "S-MonoX":
            apply_trix(jpg_path)
        elif film_name == "S-Saturnix":
            apply_saturnix(jpg_path)
        else:
            apply_film(jpg_path, film_name)
    except Exception as e:
        print(f"[WARN] Film processing failed: {e}", flush=True)
    finally:
        try: os.remove(_PROG_FILE)
        except: pass

def get_next_filename():
    """Return next sequential filename stem (without extension)."""
    return next_filename()
