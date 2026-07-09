=====================================================================
 S A T U R N I X  //  D I O N E  —  SOFTWARE INSTALLATION (README)
=====================================================================

SATURNIX is a free, open-source DIY digital camera inspired by
cassette futurism, built on a Raspberry Pi Zero 2 W with a 16 MP
autofocus sensor and a 2" LCD viewfinder. It shoots DNG+JPEG and
processes photos on-device — no external apps or computer needed. This README covers the SOFTWARE setup only. For wiring,
3D printing and assembly, see the full Assembly Manual (PDF) in the
repository.

  Firmware        : MIT (LICENSE)
  Hardware        : CERN-OHL-S-2.0 (hardware/LICENSE-HARDWARE.md)
  Docs & media    : CC-BY-4.0 (LICENSE-DOCS.md)
  Name & logo     : naming policy (BRANDING)
  Repo            : github.com/Yutani140x/saturnix-camera

Install the software BEFORE final assembly, so you can verify the
electronics with the case still open. Overall flow: flash the base
OS -> enable interfaces -> install packages -> place the project
folders -> adjust config.json -> run the fast-boot script. After
that the camera starts automatically on every power-up.

---------------------------------------------------------------------
 !! IDENTITY VALUES ARE HARD-CODED — DO NOT CHANGE !!
---------------------------------------------------------------------
The firmware is tied to these exact system names. Use them verbatim
during flashing, or the software will not run:

  Hostname : saturnix-dione
  Username : saturnix
  Password : saturnix

---------------------------------------------------------------------
 STEP 1 — Flash the base OS
---------------------------------------------------------------------
Download Raspberry Pi Imager (raspberrypi.com/software) and set:

  Device                       : Raspberry Pi Zero 2 W
  Operating System             : Raspberry Pi OS (Legacy, 32-bit)
                                 — Debian Bookworm
  Storage                      : your microSD card (32 GB+)
  Customisation -> Hostname    : saturnix-dione
  Customisation -> User        : saturnix / saturnix
  Customisation -> Wi-Fi       : your home network
                                 (needed for Step 2 downloads)
  Customisation -> Remote acc. : Enable SSH

---------------------------------------------------------------------
 STEP 2 — Update the system
---------------------------------------------------------------------
Boot the Pi, then:

  sudo apt update
  sudo apt full-upgrade -y
  sudo reboot

---------------------------------------------------------------------
 STEP 3 — Enable interfaces
---------------------------------------------------------------------
  sudo raspi-config

  Interface Options -> I2C -> Enable   (UPS HAT fuel gauge)
  Interface Options -> SPI -> Enable   (LCD)
  Finish -> reboot

---------------------------------------------------------------------
 STEP 4 — System packages + Arducam driver + camera overlay
---------------------------------------------------------------------
Install packages:

  sudo apt install -y \
    python3-pip python3-picamera2 python3-opencv \
    python3-smbus python3-rpi.gpio python3-pil \
    i2c-tools rpicam-apps git

Install the Arducam IMX519 driver:

  cd ~
  wget -O install_pivariety_pkgs.sh \
    https://github.com/ArduCAM/Arducam-Pivariety-V4L2-Driver/releases/download/install_script/install_pivariety_pkgs.sh
  chmod +x install_pivariety_pkgs.sh
  ./install_pivariety_pkgs.sh -p libcamera_dev
  ./install_pivariety_pkgs.sh -p libcamera_apps

Edit the boot config:

  sudo nano /boot/firmware/config.txt

Add at the end (no spaces around "="):

  camera_auto_detect=0
  dtoverlay=imx519

Save (Ctrl+O, Enter, Ctrl+X), then reboot.

---------------------------------------------------------------------
 STEP 5 — Place the project folders
---------------------------------------------------------------------
Copy two folders from this repository onto the Pi — that's all
this step is:

  ~/Desktop/python/       the LCD driver
                          (LCD_2inch.py, lcdconfig.py)

  /home/saturnix-dione/   the camera code and scripts
                          (liveview.py, main.py, capture.py,
                           buzzer.py, ups.py, logger.py,
                           config.json, splash.jpg,
                           setup_fast_boot.sh,
                           setup_wifi_hotspot.sh,
                           and a Pictures/ folder for photos).
                          The .sh scripts are run from this
                          folder via the console.

Folder names and locations are hard-coded, same as the system
identity — keep the exact paths above.

---------------------------------------------------------------------
 STEP 6 — Set up the WiFi hotspot
---------------------------------------------------------------------
  cd /home/saturnix-dione
  chmod +x setup_wifi_hotspot.sh
  sudo ./setup_wifi_hotspot.sh

Creates the hotspot used for photo transfer:

  SSID     : SaturnixCam
  Password : saturnix24
  Camera   : 192.168.4.1

---------------------------------------------------------------------
 STEP 7 — Adjust config.json
---------------------------------------------------------------------
The configuration file lives in the saturnix-dione folder. Open it
in any text editor and review the settings BEFORE enabling
autostart. The full parameter reference is in the Assembly Manual,
section 07. At minimum, check the battery behaviour below.

  !! BATTERY AUTO-SHUTDOWN — READ BEFORE FIRST RUN !!

  By default the camera shuts down at 5% battery to protect the SD
  card from corruption. If the UPS HAT battery gauge is not detected
  on first boot, the reading is treated as empty — and the camera
  will simply power itself off shortly after starting.

  If your camera keeps switching off right after boot: check the
  UPS HAT wiring to the Pi's GPIO pins (SDA / SCL / power) and that
  I2C is enabled (Step 3), or temporarily change
  battery_shutdown_pct in config.json.

  Building without a battery? Set "battery_auto_shutdown": false
  in config.json — this disables both the auto-shutdown and the
  low-battery warning beeps.

---------------------------------------------------------------------
 STEP 8 — Fast boot + autostart
---------------------------------------------------------------------
  cd /home/saturnix-dione
  chmod +x setup_fast_boot.sh
  sudo ./setup_fast_boot.sh
  sudo reboot

After the reboot the camera starts automatically:
splash screen -> live preview.

Installation complete — power on and verify the display, buttons,
autofocus, buzzer and hotspot while the case is still open, then
continue to final assembly (Manual, section 06).

---------------------------------------------------------------------
 UNDO AUTOSTART (return to a normal desktop later)
---------------------------------------------------------------------
  sudo systemctl set-default graphical.target
  # remove the SATURNIX_AUTOSTART block from ~/.bashrc
  sudo reboot

---------------------------------------------------------------------
 DISCLAIMER
---------------------------------------------------------------------
SATURNIX is provided "as is", without any warranty of any kind. You
build, flash and operate this device entirely at your own risk. Read
the safety notices in the Assembly Manual (resin printing, lithium
battery handling) before you build.

Firmware developed with Claude Code (Anthropic) and Codex (OpenAI).
SATURNIX is an independent project, not affiliated with or endorsed
by Anthropic/OpenAI.

The SATURNIX name and logo follow the naming policy in BRANDING:
forks and derived builds are welcome as "SATURNIX-compatible" or
"based on SATURNIX". Suggested attribution: "Based on the SATURNIX
Camera open-source hardware project by Yutani140x." 
