# SATURNIX

### Open-source digital camera with film simulation

<p align="center">
  <img src="docs/saturnix_logo_02.png" width="500">
</p>

> ## 🚧 **Firmware release coming soon.** Star this repo to get notified.
> ## ⚠️Project is under active development, structure and features may change

<p align="center">
  <img src="docs/1.jpg" width="500">
</p>

---
## Join our Discord community to stay up to date with development updates and news:

[![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/9S6AgTT6k6)

---

## What it is

SATURNIX is a DIY retrofuturistic digital camera built on a Raspberry Pi Zero 2W with a 16MP autofocus sensor and a small LCD viewfinder.
It shoots RAW+JPG and processes photos on-device using simple JPEG presets inspired by film stocks.
Image capture and processing run entirely on the Raspberry Pi. No external apps are required.

---

## Why I built it

About a year ago I just wanted a camera that felt good to use — something simple, physical, and that I could tweak however I wanted. I didn't like how modern cameras are designed, and I couldn't find anything open-source that felt right. So I built my own.

I spent a lot of time on how it feels to hold and use, not just on the code.

This isn't trying to replace a real camera. It's more of a personal experiment around:

- simple camera setups
- keeping everything local (no cloud)
- work on creating our own image processing system

**This started as a personal project. After sharing it online and seeing the level of interest, I decided to make it publicly available as open source.**

---

## Getting Started
The project is still in active development.

- Firmware &  Hardware release coming soon (I hope to publish the project in full within the next two weeks)
- Join Discord for dev updates and early access
  
---

## Early prototype (v0)

### This was one of the first working versions — about a year ago.

<p align="center">
  <img src="docs/prototype_1.jpg" width="500">
</p>

<p align="center">
  <img src="docs/prototype_2.jpg" width="500">
</p>

<p align="center">
  <img src="docs/prototype_3.jpg" width="500">
</p>

This started as a just-for-fun thing. Me and some friends were messing around with cameras and photography, and at some point I thought — why not try to build one from scratch?
This early version was all about getting things to actually work — sensor, buttons, screen, basic controls. It looked rough, felt rough, and that was fine. It was never meant to be pretty. We just wanted to see if it could work at all.
Turns out it could. So I kept going.
  
---

## Current state (v1)

### A year later — this is where we ended up

<p align="center">
  <img src="docs/1.jpg" width="500"/>
</p>

From a messy pile of wires that barely worked to an actual, usable camera.
The design takes a lot of cues from old 80s–90s electronics — that chunky, slightly industrial look that old gear used to have. I've always liked that aesthetic, so I leaned into it.

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

---

### 3D Printed Case

STL files for the camera case are ~~available~~ in the [`hardware/`](hardware/) directory.

**The case is designed for resin printing (FDM version is being considered)**

<p align="center">
  <img src="docs/Fusion_1.jpg">
</p>

---

## Known issues

This is still experimental. Here's what doesn't work great yet:

### Speed ⚠️

- Takes about a minute to boot
- Each photo takes 8–14 seconds to process

The slowness comes from how the camera pipeline works right now — it stops and restarts the camera twice for every shot. Most of the delay is that restart cycle, not the actual capture.

There's a fix planned: switching to a method that captures full-res without stopping the camera. That should bring it down to about 1.5–2.5 seconds per shot.

### Assembly
 
- Build instructions are not ready yet 
- Assembly is a bit complicated
- Requires soldering — not beginner-friendly for now

### Despite these limitations, the camera has been tested in real-world use (including multi-day outdoor trips) and works reliably for still photography.

---

## UI:

The interface is designed to look like an old terminal. I like that look, and it's also much lighter on the processor than a fancy UI.
- Colors: Solid only — amber (#FFBF00), white, and black
- Font: DejaVu Sans Bold 14px via Pillow
- Animation: Minimal — blinking AF indicator, a capture animation, a progress bar

__The main constraint is the processor — a 1 GHz Pi Zero. UI rendering has to stay under ~15ms per frame to keep the preview smooth. Right now I'm focused on performance rather than adding features.__

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

## What works today

Spent today working on film simulation profiles. Trying to get the color science as close as possible to that classic film look, but it's still very much a work in progress — lots of tweaking ahead.
Also renaming all the filters to avoid any trademark issues: S-Gold, S-Vivid, S-MonoX, S-Natural, and more to come.

<p align="center">
  <img src="docs/1_upd.jpg" width="48%" />
  <img src="docs/2_upd.jpg" width="48%" />
</p>

<p align="center">
  <img src="docs/3_upd.jpg" width="48%" />
  <img src="docs/4_upd.jpg" width="48%" />
</p>

<p align="center">
  <img src="docs/5_upd.jpg" width="48%" />
</p>

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

RAW (DNG) files from Saturnix are available.

No edits, straight from the camera.

Download here:
https://drive.google.com/drive/folders/19HZnG9zmNsQW2zrbjA84-G9dMtUlpbSJ?usp=drive_link

---

## Installation

> ⏳ Pre-built image and installation guide will be available with the first public release. You can follow the dev blog in the project's Discord community.

---

## Licensing

This project uses a **dual license** model:

| What | License | Commercial use |
|---|---|---|
| **Firmware** (Python code) | [MIT License](LICENSE) | [MIT License](LICENSE) |
| **Hardware** (STL, 3D models) | [CC BY-NC-SA 4.0](hardware/LICENSE-HARDWARE.md) | Requires permission ([details](hardware/LICENSE-HARDWARE.md))|

---

## Support the Project

SATURNIX is built independently.
If you want to support development and future releases:

[![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/9S6AgTT6k6)

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/yutani140x)

[![Ko-fi](https://img.shields.io/badge/Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/yutani)

[![Patreon](https://img.shields.io/badge/Patreon-F96854?style=for-the-badge&logo=patreon&logoColor=white)](https://patreon.com/Yutani140x)


⭐ **Star this repo** to follow the development!

---

**Created by Yutani140x**

