#!/bin/bash
# setup_fast_boot.sh — Optimize Raspberry Pi Zero 2W boot for Saturnix camera.
# Run once: sudo bash setup_fast_boot.sh
# Reboot after running.

set -e
echo "=== SATURNIX Fast Boot Setup ==="

# Auto-detect the user who owns the project directory
CURRENT_USER="${SUDO_USER:-$(logname 2>/dev/null || echo pi)}"
USER_HOME="/home/$CURRENT_USER"
PROJECT_DIR="$USER_HOME/saturnix-dione"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "[ERR] Project dir not found: $PROJECT_DIR"
    echo "Run this script from the user account that has saturnix-dione."
    exit 1
fi
echo "User: $CURRENT_USER  Project: $PROJECT_DIR"

# ---- 1. Switch to Console Autologin (skip Desktop) ----
echo "[1/5] Switching to Console Autologin..."
systemctl set-default multi-user.target
# Enable autologin on tty1
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $CURRENT_USER --noclear %I \$TERM
EOF

# ---- 2. Disable unnecessary services ----
echo "[2/5] Disabling unnecessary services..."
SERVICES=(
    bluetooth
    avahi-daemon
    triggerhappy
    apt-daily.timer
    apt-daily-upgrade.timer
    man-db.timer
    ModemManager
    wpa_supplicant  
)
# Note: wpa_supplicant disabled because WiFi is managed by hostapd when needed.
# If you need regular WiFi (not hotspot), remove wpa_supplicant from this list.

for svc in "${SERVICES[@]}"; do
    if systemctl is-enabled "$svc" &>/dev/null 2>&1; then
        systemctl disable "$svc" 2>/dev/null && echo "  Disabled: $svc" || true
    fi
done

# ---- 3. Kernel boot optimization ----
echo "[3/5] Optimizing kernel boot..."

CONFIG="/boot/firmware/config.txt"
CMDLINE="/boot/firmware/cmdline.txt"

# Fallback paths for older Pi OS
[ ! -f "$CONFIG" ] && CONFIG="/boot/config.txt"
[ ! -f "$CMDLINE" ] && CMDLINE="/boot/cmdline.txt"

# config.txt: disable splash, zero boot delay
if ! grep -q "disable_splash" "$CONFIG"; then
    echo "" >> "$CONFIG"
    echo "# Saturnix fast boot" >> "$CONFIG"
    echo "disable_splash=1" >> "$CONFIG"
    echo "boot_delay=0" >> "$CONFIG"
    echo "  Added disable_splash and boot_delay to $CONFIG"
fi

# CMA: libcamera allocates full-resolution sensor buffers from the CMA heap.
# The default is too small for a 16MP still config on a 512MB Zero 2W —
# this is what causes "Unable to request N buffers: Cannot allocate memory".
# 320MB leaves ~190MB for Linux+Python (fine for a headless camera).
# If the system feels starved, change to cma-256.
if ! grep -q "cma-" "$CONFIG"; then
    echo "# Saturnix: enlarge CMA for full-res IMX519 capture (native still path)" >> "$CONFIG"
    echo "dtoverlay=cma,cma-320" >> "$CONFIG"
    echo "  Added CMA 320MB to $CONFIG (verify after reboot: cat /proc/meminfo | grep Cma)"
fi

# cmdline.txt: quiet boot, no logo, no cursor
CMDLINE_CONTENT=$(cat "$CMDLINE")
NEEDS_UPDATE=false

for param in "quiet" "logo.nologo" "loglevel=3" "vt.global_cursor_default=0"; do
    if ! echo "$CMDLINE_CONTENT" | grep -q "$param"; then
        CMDLINE_CONTENT="$CMDLINE_CONTENT $param"
        NEEDS_UPDATE=true
    fi
done

if [ "$NEEDS_UPDATE" = true ]; then
    echo "$CMDLINE_CONTENT" > "$CMDLINE"
    echo "  Updated $CMDLINE with quiet boot params"
fi

# ---- 4. Early splash (shows logo before Python starts) ----
echo "[4/5] Setting up early splash..."
apt-get install -y fbi 2>/dev/null || true

# Create systemd service for early splash
cat > /etc/systemd/system/saturnix-splash.service << EOF
[Unit]
Description=Saturnix Early Splash
DefaultDependencies=no
After=local-fs.target
Before=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/fbi -T 1 -noverbose -a ${PROJECT_DIR}/SaturnixStartUP.jpg
StandardInput=tty
StandardOutput=tty
TTYPath=/dev/tty1

[Install]
WantedBy=multi-user.target
EOF
systemctl enable saturnix-splash.service 2>/dev/null || true

# ---- 5. Autostart Saturnix on login ----
echo "[5/5] Setting up autostart..."

BASHRC="$USER_HOME/.bashrc"
MARKER="# SATURNIX_AUTOSTART"

if ! grep -q "$MARKER" "$BASHRC"; then
    cat >> "$BASHRC" << EOF

$MARKER
if [ "\$(tty)" = "/dev/tty1" ] && [ -z "\$DISPLAY" ]; then
    cd $PROJECT_DIR && python3 -u main.py 2>&1
fi
EOF
    echo "  Added autostart to $BASHRC"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Changes made:"
echo "  - Boot target: console (no desktop)"
echo "  - Autologin: $CURRENT_USER on tty1"
echo "  - Disabled: bluetooth, avahi, triggerhappy, apt timers"
echo "  - Kernel: quiet boot, no splash, no logo"
echo "  - Early splash: LantianOS.jpg shown during boot"
echo "  - Autostart: main.py runs on login"
echo ""
echo "To undo and restore desktop:"
echo "  sudo systemctl set-default graphical.target"
echo "  Remove $MARKER block from $BASHRC"
echo ""
echo "Reboot now to apply: sudo reboot"
