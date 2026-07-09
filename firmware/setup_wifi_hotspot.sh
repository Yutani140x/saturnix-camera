#!/bin/bash
# setup_wifi_hotspot.sh — run ONCE on Raspberry Pi to configure WiFi hotspot.
# Usage: sudo bash setup_wifi_hotspot.sh
#
# After running this script, the hotspot is NOT started automatically on boot.
# It will be started/stopped on demand from the Saturnix camera app.

set -e

echo "=== Saturnix WiFi Hotspot Setup ==="

# --- Install packages ---
echo "[1/4] Installing hostapd and dnsmasq..."
apt-get update -qq
apt-get install -y hostapd dnsmasq

# --- Disable auto-start (we control it manually) ---
echo "[2/4] Disabling auto-start..."
systemctl unmask hostapd 2>/dev/null || true
systemctl disable hostapd 2>/dev/null || true
systemctl disable dnsmasq 2>/dev/null || true
systemctl stop hostapd 2>/dev/null || true
systemctl stop dnsmasq 2>/dev/null || true

# --- hostapd config ---
echo "[3/4] Writing hostapd config..."
cat > /etc/hostapd/hostapd_saturnix.conf << 'EOF'
interface=wlan0
driver=nl80211
ssid=SaturnixCam
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=saturnix24
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

# --- dnsmasq config ---
echo "[4/4] Writing dnsmasq config..."
cat > /etc/dnsmasq.d/saturnix.conf << 'EOF'
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
address=/#/192.168.4.1
EOF

echo ""
echo "=== Setup complete! ==="
echo "  SSID:     SaturnixCam"
echo "  Password: saturnix24"
echo "  Address:  192.168.4.1"
echo ""
echo "WiFi will be started/stopped from the camera menu."
echo "To change SSID/password, edit /etc/hostapd/hostapd_saturnix.conf"
