# SATURNIX

### Open-source digital camera with film simulation

<p align="center">
  <img src="docs/1.jpg" width="400">
</p>

> 🚧 **Firmware release coming soon.** Star this repo to get notified.

---
Join the **Saturnix** community:

[![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/9S6AgTT6k6)

---

## What it is

SATURNIX is a DIY digital camera built on a Raspberry Pi Zero 2W with a 16MP autofocus sensor and a small LCD viewfinder.
It shoots RAW+JPG and processes photos on-device using simple JPEG presets inspired by film stocks.
Image capture and processing run entirely on the Raspberry Pi. No external apps are required.

---

## Why this exists

This project started as a personal experiment.

I wanted to design and build my own camera from scratch.

I also wanted something open, hackable, and fully under my control.
I couldn’t find an open-source camera project like this, so I made one.

The goal is not to compete with commercial cameras, but to explore:
- minimal camera systems
- local-first workflows
- custom imaging pipelines

---

## Features

**Camera**
- 16MP autofocus sensor (Arducam IMX519)
- RAW (DNG) + JPG capture
- Full manual controls: Shutter (30s–1/4000), ISO (100–3200), WB, EV
- Autofocus modes: AF-C (continuous with lock), AF-S (single shot), MF (manual)

**JPEG presets (film-inspired)**
- **Saturnix** — custom preset (in develop)
- **S-Gold** — warm, vintage, creamy tones
- **S-Vivid** — higher saturation, stronger contrast, more aggressive sharpening
- **S-Natural** — neutral colors with slight green shift
- **S-MonoX** — black & white with added contrast and grain
- **VHS** — lo-fi effect (scanlines, chromatic aberration, noise)

**Interface**
- 2" LCD live preview at 320×240
- Auto-hide UI (clean viewfinder after 15s)
- Live histogram with exposure traffic light
- Composition grids (Thirds, Golden Ratio, Cross)
- AF indicator with auto-detection
- CPU temperature & storage monitoring
- Persistent settings (survive reboot)

**Connectivity**
- Built-in WiFi hotspot for transferring photos
- Simple web interface (terminal-style)
- Works without internet (direct connection to phone)

**Audio**
- Passive buzzer feedback for all actions
- Customizable: shutter, focus, navigation, startup sounds
- Mute mode

---

## Hardware

| Component | Model |
|---|---|
| Board | Raspberry Pi Zero 2W |
| Sensor | Arducam IMX519 16MP Autofocus |
| Display | Waveshare 2" IPS LCD (240×320, SPI) |
| Audio | Passive buzzer (MH-FMD) on GPIO |
| Storage | microSD (32GB+) |
| Power | USB-C / ~~PiSugar2 battery~~ UPS HAT Waveshare (optional) |

**Buttons:** 5× mechanical low profile kailh switches — Left, Right, Select, Capture, Focus

### 3D Printed Case

STL files for the camera case are available in the [`hardware/`](hardware/) directory.

---

## Current limitations

This project is still experimental and has several practical limitations:

### Performance⚠️

- Boot time is relatively long (~1 minute)
- Each photo currently takes ~8–14 seconds to process

The main reason is how the camera pipeline works right now:

- LiveView stops the camera (picamera2.stop + close) — ~1–2s  
- rpicam-still reinitializes the camera from scratch — ~3–5s  
- Capture — ~0.5–2s  
- Saving to SD card — ~1s  
- LiveView starts the camera again — ~3–5s  

Most of the delay comes from restarting the camera twice per shot, not the capture itself.

### Hardware & Assembly

- Requires soldering (not beginner-friendly yet)
- Current enclosure is designed for resin 3D printing
- Assembly is more complex than a typical DIY project
- Instructions are still in progress

### Project Scope

- Designed as a DIY camera, not a polished consumer product
- Strong focus on making the design simpler and more accessible over time
- Considering an FDM-printable version of the enclosure (not implemented yet)

## Despite these limitations, the camera has been tested in real-world use (including multi-day outdoor trips) and works reliably for still photography.

---

## UI Design & Architecture:

Colors: Solid colors only, no gradients in UI elements. We use amber (255,191,0), white, and black as the primary palette.
Typography: TTF — we load the DejaVu Sans Bold 14px font using the ImageFont.truetype() method of the Pillow library. **Custom fonts with a reduced number of glyphs are also suitable and will save some memory.**
Shapes: Rectangles, lines, and polygons — all drawn using the Pillow library's ImageDraw. Circles are intentionally avoided for a more angular/technical aesthetic. No anti-aliasing.
Animation: Minimal — a blinking autofocus indicator, a dotted reticle during capture, and an animated progress bar. Everything is redrawn frame by frame, so any simple state-driven animation is possible.

Regarding icons/images: Technically possible (PIL can compose PNG files), but I haven't used them yet—right now, everything is text and geometry. The priority is a lightweight interface, since each frame must be composed with the camera's video stream and transmitted over SPI.
Resolution: 320x240, so essentially every pixel matters.

The main limitation of the project is the processor: a 2W Pi Zero running at 1 GHz, so the UI rendering time must remain within ~15 ms to maintain an acceptable preview frame rate. The MAIN bottleneck is the limited performance of the Raspberry Pi, so my priority right now is optimizing the process rather than adding new features or improving the interface's visual design.

The UI intentionally follows an old terminal-like aesthetic — simple geometry and symbolic graphics instead of modern interface elements. I like the aesthetics and it also reduces CPU and memory usage.

---

## Camera Photo

<p align="center">
  <img src="docs/1.jpg" width="400">
</p>

<p align="center">
  <img src="docs/2.jpg" width="400">
</p>

<p align="center">
  <img src="docs/3.jpg" width="400">
</p>

<p align="center">
  <img src="docs/4.jpg" width="400">
</p>

<p align="center">
  <img src="docs/5.jpg" width="400">
</p>

---

## UI Photo

<p align="center">
  <img src="docs/1_ui.jpg" width="400">
</p>

<p align="center">
  <img src="docs/2_ui.jpg" width="400">
</p>

<p align="center">
  <img src="docs/3_ui.jpg" width="400">
</p>

---

## Film Samples

No filter
<p align="center">
  <img src="docs/0_filter.jpg" width="400">
</p>


S-Gold
<p align="center">
  <img src="docs/gold.jpg" width="400">
</p>


S-Natural
<p align="center">
  <img src="docs/fuji.jpg" width="400">
</p>


S-MonoX
<p align="center">
  <img src="docs/TriX.jpg" width="400">
</p>


Saturnix film **(in development)**
<p align="center">
  <img src="docs/Saturnix.jpg" width="400">
</p>

---

## Photo Samples — Straight Out of Camera (No Filters)

<p align="center">
  <img src="docs/s_01.jpg" width="400">
</p>

<p align="center">
  <img src="docs/s_02.jpg" width="400">
</p>

<p align="center">
  <img src="docs/s_03.jpg" width="400">
</p>

<p align="center">
  <img src="docs/s_04.jpg" width="400">
</p>

---

## Roadmap

- [x] Live preview + full manual controls
- [x] RAW+JPG capture with sequential naming
- [x] Film simulation engine (6 presets)
- [x] Live histogram + exposure indicator
- [x] Composition grids
- [x] WiFi photo transfer (hotspot + web gallery)
- [x] Auto-hide UI
- [x] Persistent settings
- [x] Buzzer audio feedback
- [x] Gallery with DNG support
- [x] Camera body and design improvements 
- [ ] **Battery indicator (~~PiSugar2~~)** < **project at this stage**
- [ ] Firmware update via USB
- [ ] Firmware cleanup
- [ ] Pre-built SD card image
- [ ] Open source release preparation
- [ ] Release

---

## Installation

> ⏳ Pre-built image and installation guide will be available with the first public release.

---

## Licensing

This project uses a **dual license** model:

| What | License | Commercial use |
|---|---|---|
| **Firmware** (Python code) | [MIT License](LICENSE) | [MIT License](LICENSE) |
| **Hardware** (STL, 3D models) | [CC BY-NC-SA 4.0](hardware/LICENSE-HARDWARE.md) | Requires permission ([details](hardware/LICENSE-HARDWARE.md))|

---

## Support the Project

SATURNIX is a passion project built in spare time. If you find it interesting, consider supporting its development:

[![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/9S6AgTT6k6)

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/yutani140x)

[![Patreon](https://img.shields.io/badge/Patreon-F96854?style=for-the-badge&logo=patreon&logoColor=white)](https://patreon.com/Yutani140x)


⭐ **Star this repo** to follow the development!

---

**Created by Yutani140x**

