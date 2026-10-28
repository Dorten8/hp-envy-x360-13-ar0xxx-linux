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
HandleSuspendKey=hibernate
HandleLidSwitch=hibernate
HandleLidSwitchExternalPower=hibernate
HandleLidSwitchDocked=ignore
LOGIND_EOF

echo "[*] 2. Configuring systemd-sleep for Pure Hibernation (Disabling s2idle)..."
mkdir -p /etc/systemd/sleep.conf.d
cat << 'SLEEP_EOF' > /etc/systemd/sleep.conf.d/hibernate.conf
[Sleep]
AllowSuspend=no
AllowHibernation=yes
AllowSuspendThenHibernate=no
AllowHybridSleep=no
HibernateMode=shutdown platform
SLEEP_EOF

echo "[*] 3. Masking Dangerous Suspend Services..."
systemctl mask systemd-suspend.service systemd-hybrid-sleep.service 2>/dev/null || true

echo "[*] 4. Configuring GDM & System-Wide Inactive Power Policy (dconf)..."
mkdir -p /etc/dconf/db/gdm.d /etc/dconf/db/local.d
cat << 'GDM_EOF' > /etc/dconf/db/gdm.d/01-power
[org/gnome/settings-daemon/plugins/power]
sleep-inactive-ac-timeout=0
sleep-inactive-ac-type='nothing'
sleep-inactive-battery-timeout=1800
sleep-inactive-battery-type='hibernate'
GDM_EOF

cat << 'LOCAL_EOF' > /etc/dconf/db/local.d/01-power
[org/gnome/settings-daemon/plugins/power]
sleep-inactive-ac-timeout=0
sleep-inactive-ac-type='nothing'
sleep-inactive-battery-timeout=1800
sleep-inactive-battery-type='hibernate'
power-button-action='hibernate'
LOCAL_EOF

dconf update 2>/dev/null || true

echo "[*] 5. Enabling Wi-Fi (Intel AX210) & Audio Power Savings..."
cat << 'MOD_WIFI' > /etc/modprobe.d/iwlwifi.conf
options iwlwifi power_save=1
MOD_WIFI

cat << 'MOD_AUDIO' > /etc/modprobe.d/audio_powersave.conf
options snd_hda_intel power_save=1 power_save_controller=Y
MOD_AUDIO

echo "[*] 6. Tuning Power Profile..."
if command -v tuned-adm &>/dev/null; then
  tuned-adm profile balanced-battery || true
  echo "    [+] Set tuned profile to balanced-battery"
fi

echo "[*] 7. Reloading systemd-logind cleanly..."
systemctl kill -s HUP systemd-logind 2>/dev/null || true

echo "[✓] System power tweaks successfully applied!"
