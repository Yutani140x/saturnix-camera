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

SATURNIX is a DIY digital camera built on Raspberry Pi Zero 2W with a 16MP autofocus sensor, 2" LCD viewfinder, and built-in film simulation engine. It shoots RAW+JPG and processes photos on-device with JPEG presets processed on-device, designed to mimic film-inspired color response — from S-Gold to a custom saturnix preset.

---

## Features

**Camera**
- 16MP autofocus sensor (Arducam IMX519)
- RAW (DNG) + JPG capture
- Full manual controls: Shutter (30s–1/4000), ISO (100–3200), WB, EV
- Autofocus modes: AF-C (continuous with lock), AF-S (single shot), MF (manual)

**Film Simulations**
- **SATURNIX** — signature preset: golden light, indigo shadows, bloom
- **S-Gold** — warm, vintage, creamy tones
- **S-Vivid** — higher saturation, stronger contrast, more aggressive sharpening
- **S-Natural** — cool greens, balanced tones
- **S-MonoX** — classic black & white, deep blacks, rich grain
- **VHS** — lo-fi tape look: scanlines, chromatic aberration, noise

**Interface**
- 2" LCD live preview at 320×240
- Auto-hide UI (clean viewfinder after 15s)
- Live histogram with exposure traffic light
- Composition grids (Thirds, Golden Ratio, Cross)
- AF indicator with auto-detection
- CPU temperature & storage monitoring
- Persistent settings (survive reboot)

**Connectivity**
- Built-in WiFi hotspot for photo transfer
- Retro terminal-style web gallery
- No internet required — direct device-to-phone

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

