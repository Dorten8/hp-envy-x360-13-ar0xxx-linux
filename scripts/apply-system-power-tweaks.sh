#!/usr/bin/env bash
# ==============================================================================
# HP ENVY x360 System-Wide Power & Hibernation Tweaks
# Requires: sudo / root privileges
# ==============================================================================

set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "[!] Please run this script with sudo: sudo $0"
  exit 1
fi

echo "[*] 1. Configuring systemd-logind for Hibernate on Lid Close..."
mkdir -p /etc/systemd/logind.conf.d
cat << 'LOGIND_EOF' > /etc/systemd/logind.conf.d/lid-hibernate.conf
[Login]
HandlePowerKey=hibernate
HandleLidSwitch=hibernate
HandleLidSwitchExternalPower=hibernate
HandleLidSwitchDocked=ignore
LOGIND_EOF

echo "[*] 2. Configuring systemd-sleep for Hibernation..."
mkdir -p /etc/systemd/sleep.conf.d
cat << 'SLEEP_EOF' > /etc/systemd/sleep.conf.d/hibernate.conf
[Sleep]
AllowHibernation=yes
AllowSuspendThenHibernate=yes
AllowHybridSleep=yes
HibernateMode=platform shutdown
SLEEP_EOF

echo "[*] 3. Enabling Wi-Fi (Intel AX210) & Audio Power Savings..."
cat << 'MOD_WIFI' > /etc/modprobe.d/iwlwifi.conf
options iwlwifi power_save=1
MOD_WIFI

cat << 'MOD_AUDIO' > /etc/modprobe.d/audio_powersave.conf
options snd_hda_intel power_save=1 power_save_controller=Y
MOD_AUDIO

echo "[*] 4. Tuning Power Profile..."
if command -v tuned-adm &>/dev/null; then
  tuned-adm profile balanced-battery || true
  echo "    [+] Set tuned profile to balanced-battery"
fi

echo "[*] 5. Restarting systemd-logind to apply changes..."
systemctl restart systemd-logind

echo "[✓] System power tweaks successfully applied!"
