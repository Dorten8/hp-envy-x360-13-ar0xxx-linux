# HP ENVY x360 Convertible (13-ar0xxx) Linux Master Enablement Suite

[![OS](https://img.shields.io/badge/OS-Fedora%20Linux%2043-blue?logo=fedora)](https://getfedora.org/)
[![Kernel](https://img.shields.io/badge/Kernel-Linux%207.2+-green?logo=linux)](https://kernel.org/)
[![Desktop](https://img.shields.io/badge/DE-GNOME%2049%20Wayland-purple?logo=gnome)](https://gnome.org/)
[![Processor](https://img.shields.io/badge/CPU-AMD%20Ryzen%205%203500U-red?logo=amd)](https://www.amd.com/)
[![Firmware](https://img.shields.io/badge/BIOS-AMI%20F.30-orange)](https://support.hp.com/)
[![License](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)

A battle-tested, software-engineering-grade hardware enablement suite and complete post-install playbook for running modern Linux (Fedora 43 Workstation, GNOME Wayland) on the **HP ENVY x360 Convertible 13-ar0xxx** (AMD Ryzen 5 3500U with Radeon Vega 8 Mobile Graphics).

This repository completely resolves all out-of-the-box hardware issues—transforming an unsupported, thermal-throttling, battery-draining convertible laptop into a rock-solid, responsive daily driver with full biometric fingerprint authentication, silky-smooth 1080p60 video playback, intelligent tablet mode, and safe cold S4 hibernation.

---

## What Is Fixed in This Repository

| Subsystem / Problem | Out-of-the-Box Linux Behavior | Our Engineering Solution | Status |
| :--- | :--- | :--- | :---: |
| **Power Management & Backpack Boiling** | Laptop stays boiling hot in bags, draining from 100% to 0% in ~4 hours. Modern Standby (`s2idle`) is broken on Linux Zen+, and HP BIOS `F.30` completely lacks an ACPI S3 wake vector. S4 hibernation aborts with AMDGPU TTM eviction `error -12`. | Configured **True Fast S4 Hibernation by default**, pre-sleep memory compaction (`drop_caches=3`, `compact_memory=1`) leaving >3.6 GB free for GPU buffer eviction, target 2.0 GB image size, post-resume EC polling, boil-guard watchdog with 2-failure emergency poweroff cutoff, and 60s AMD SP5100 hardware watchdog timer. | **100% Solved** |
| **Synaptics Fingerprint (`06cb:00c9`)** | Zero upstream Linux kernel/libfprint support. Community reverse-engineered drivers fail enrollment after 3 taps due to 4 critical code bugs (auth flag collision, pointer comparison, logic inversion, missing persistent pairing write). | Patched `libfprint` and `fprintd` trees, resolved all 4 driver bugs, automated PAM integration with `authselect`, and version-locked packages in DNF to prevent update overwrites. | **100% Solved** |
| **Tablet Mode & Auto-Rotation** | Display auto-rotation locks up during boot due to AMD SFH MP2 co-processor mailbox contention (`sensor_mask=-1`). The laptop has no physical hinge sensor. Naive heuristics lock the keyboard while typing in clamshell mode. | Fixed kernel module with `amd_sfh.sensor_mask=1`. Decoupled architecture: G-sensor strictly handles display auto-rotation in Mutter/Wayland; user-controlled 1-tap Dash icon and `<Super>F12` shortcut handle physical input locking. Smart dynamic seat monitor suppresses On-Screen Keyboard on `sudo` prompts. | **100% Solved** |
| **Video Hardware Acceleration & YouTube Stutter** | Rhythmic micro-stuttering and frame drops during YouTube/HTML5 video playback on Vega 8 due to missing patent-encumbered codecs in Fedora and buggy hardware VP9 decoding in the Mesa VA-API driver. High CPU load (75%) and continuous fan noise. | Installed Mesa freeworld VA-API drivers from RPM Fusion, configured Firefox overrides (`media.mediasource.vp9.enabled=false`, `media.ffmpeg.vaapi=true`, `media.hardware-video-decoding.force-enabled=true`) to force silky-smooth H.264/HEVC hardware decoding. CPU load drops to 8–12%. | **100% Solved** |
| **Slow PC Performance & Memory Starvation** | Only 5.64 GiB of the 8 GB RAM is usable (2.1 GiB hard-locked by BIOS AMI F.30 for APU VRAM). Multi-tab browsing causes severe disk thrashing and UI freezes. | Deployed dual-tier memory architecture: Tier 1 high-priority compressed in-RAM swap (8 GB ZRAM, `zstd`, priority 100) + Tier 2 persistent 16 GB NVMe swapfile. Tuned `vm.swappiness=100`, `vm.page-cluster=0`, fast 15s shutdown timeout, and Firefox memory process tuning. | **100% Solved** |
| **Nordic Keyboard Layout (`#UUW`)** | Right Alt acts as a duplicate Alt key; typing Danish/Nordic letters (`æ`, `ø`, `å`) is impossible without breaking standard programming keycaps (`'`, `"`, `\`, `{`, `}`). | Persistent `us+altgr-intl` (*English US, intl., with AltGr dead keys*): normal quotes (`'`, `"`) remain immediate normal keys for programming, while `Right Alt + z` = `æ`, `Right Alt + l` = `ø`, `Right Alt + w` = `å`. | **100% Solved** |

---

## Hardware & Firmware Specifications

| Subsystem | Component | Identifiers / Bus IDs | Linux Driver & Firmware Notes |
| :--- | :--- | :--- | :--- |
| **System** | HP ENVY x360 Convertible 13-ar0xxx | Motherboard: `85DE 41.36`, SKU: `6SQ55EA#UUW` | AMI BIOS `F.30` (`10/19/2023`), missing ACPI S3 |
| **Processor** | AMD Ryzen 5 3500U (Zen+, 4C/8T @ 2.1–3.7GHz) | Picasso `1022:15e4` (Root Complex) | `k10temp`, `amd_pstate` / `acpi-cpufreq` |
| **Graphics** | AMD Radeon Vega 8 Mobile (8 CUs, 512 Shaders) | PCI: `1002:15d8` (rev c2) | `amdgpu` (Wayland, Mesa Freeworld VA-API) |
| **Memory** | 8 GB DDR4-2400 (Dual Channel) | 5.64 GiB usable system RAM | 2.1 GiB hardware-reserved by APU VRAM |
| **Storage** | 256 GB NVMe SSD (SK Hynix BC501) | PCI: `1c5c:1327`, Model: `HFM256GDJTNG-8310A` | Btrfs (`root`, `home`) |
| **Swap** | Dual-Tier: 8GB ZRAM (`zstd`, prio 100) + 16GB Swapfile | `/swap/swapfile` (offset `2368768`) | Fast in-memory compression + S4 hibernate target |
| **Battery** | HP KC04053XL 4-Cell Li-ion (53.2 Wh) | Model: `KC04053XL` | Monitored by ACPI EC via `ec_busy_polling` |
| **Wi-Fi / BT** | Intel Wi-Fi 6E AX210 160MHz + Bluetooth 5.2 | PCI: `8086:2725` (rev 1a), USB: `8087:0032` | `iwlwifi` (power save enabled), `btusb` |
| **Fingerprint** | Synaptics Tudor Match-in-Sensor | USB: `06cb:00c9` (`Bus 001 Device 003`) | Patched `synatlsmoc` in `libfprint` + DNF lock |
| **Sensors** | AMD Sensor Fusion Hub (MP2 PCIe) | PCI: `1022:15e4`, HID: `0020:1022:0001.*` | `amd_sfh` with `sensor_mask=1` |
| **Touchscreen** | ELAN2514 Touchscreen & Active Stylus | I2C: `04f3:23ba` (`i2c-ELAN2514:00`) | `i2c_hid_acpi`, `hid_multitouch` |
| **Touchpad** | SYNA328F Precision Touchpad | I2C: `06cb:cd50` (`i2c-SYNA328F:01`) | `i2c_hid_acpi` (grabbed via `EVIOCGRAB` in tablet mode) |
| **Keyboard** | AT Translated Set 2 keyboard | `isa0060/serio0/input0` (`/dev/input/event2`) | Nordic ISO layout, grabbed via `EVIOCGRAB` in tablet mode |
| **Audio** | Realtek ALC285 & AMD Raven HD Audio | PCI: `1022:15e3` & `1002:15de` | `snd_hda_intel`, PipeWire / WirePlumber |

---

## Quick Start: The 1-Command Setup

### Step 1: Disk Partitioning During Fedora 43 Install
When installing Fedora Workstation, create a **Swapfile or Swap Partition of at least 16 GB**. This ensures the kernel has sufficient storage to serialize system memory + active Vega 8 GPU buffers during S4 hibernation.

### Step 2: Clone and Run the Enablement Script
Open a terminal and run:

```bash
git clone https://github.com/Dorten8/hp-envy-x360-linux.git
cd hp-envy-x360-linux
sudo ./install.sh
```

*This single command automatically deploys:*
1. True S4 hibernation routing, fast 2.0 GB image size, and post-resume EC polling.
2. Hardware watchdog protection via AMD SP5100 TCO (`RuntimeWatchdogSec=60s`).
3. Dual-tier high-priority ZRAM (`zstd`, priority 100) and sysctl memory optimizations.
4. AMD SFH sensor restriction (`sensor_mask=1`) and bootloader parameters (`iommu=pt`).
5. Patched Synaptics `06cb:00c9` fingerprint driver binaries, PAM rules, and DNF package update locks.
6. Udev hardware permission rules for sensors, touchscreen, and input event grabbing.
7. Background systemd services for power blackbox monitoring and tablet rotation.
8. Persistent `us+altgr-intl` keyboard layout for Danish/Nordic shortcuts.

### Step 3: Enroll Your Fingerprint
```bash
fprintd-enroll
```
*Touch the sensor on your keyboard deck with your right index finger until all enrollment stages complete.*

### Step 4: Verify Subsystems
Run our automated diagnostics tool:
```bash
./scripts/system-health-check.sh
```

---

## Architecture Deep Dives

For detailed engineering analysis, root causes, kernel logs, and forensic breakdowns, consult our technical deep-dive documentation:

1. **[Power Management & S4 Hibernation](docs/01-power-and-hibernation.md)**  
   *BIOS F.30 missing S3 analysis, Modern Standby drain, AMDGPU TTM buffer eviction failure (`error -12`), target image size memory starvation, boil-guard watchdog, and AMD SP5100 TCO hardware watchdog.*
2. **[Synaptics Tudor Fingerprint Driver (`06cb:00c9`)](docs/02-fingerprint-06cb-00c9.md)**  
   *Hardware TLS architecture, the 4 driver code bugs uncovered (auth flag collision, pointer comparison, logic inversion, missing persistent pairing write), patches, build instructions, and DNF version locking.*
3. **[Tablet Mode, Auto-Rotation & Smart OSK](docs/03-tablet-rotation-and-smart-osk.md)**  
   *AMD SFH MP2 co-processor mailbox collision, the single-sensor lid gravity trap, decoupled Wayland Mutter display rotation vs hardware input grabbing (`EVIOCGRAB`), and dynamic OSK suppression.*
4. **[Video Hardware Acceleration & YouTube Stutter Elimination](docs/04-video-hardware-acceleration.md)**  
   *AMD Vega 8 VP9 hardware decoding bug, RPM Fusion Mesa Freeworld VA-API setup, Firefox `about:config` overrides, and verification via `vainfo`.*
5. **[Memory Architecture & Performance Tuning](docs/05-memory-and-performance-tuning.md)**  
   *The 2.1 GiB APU VRAM lockout, dual-tier ZRAM (`zstd`, priority 100) + 16GB NVMe swapfile, sysctl `vm.swappiness=100`, fast 15s shutdown timeout, and Firefox memory process tuning.*
6. **[Nordic / Danish Keyboard Layout (`us+altgr-intl`)](docs/06-nordic-keyboard-layout.md)**  
   *The programmer's dilemma on Nordic hardware, `us+altgr-intl` configuration, immediate programming quotes (`'`, `"`), and Right Alt (AltGr) shortcuts for `æ`, `ø`, `å`, `ä`, `ö`, `€`.*

---

## Repository Structure & Manifest

```text
hp-envy-x360-linux/
├── README.md                                          <- Master architectural documentation & guide
├── LICENSE                                            <- MIT License
├── install.sh                                         <- 1-command root setup orchestrator
├── docs/                                              <- In-depth technical engineering guides
│   ├── 01-power-and-hibernation.md                    <- Power, s2idle boiling & S4 hibernation fix
│   ├── 02-fingerprint-06cb-00c9.md                    <- Synaptics 06cb:00c9 driver reverse-engineering
│   ├── 03-tablet-rotation-and-smart-osk.md            <- Decoupled rotation, input lock & smart OSK
│   ├── 04-video-hardware-acceleration.md              <- AMD Vega 8 VA-API & YouTube stutter fix
│   ├── 05-memory-and-performance-tuning.md            <- 2.1GB APU lockout, ZRAM & sysctl tuning
│   └── 06-nordic-keyboard-layout.md                   <- US-Intl AltGr Nordic layout reference
├── configs/                                           <- System configuration drop-ins
│   ├── dnf/
│   │   └── dnf.conf.snippet                           <- DNF exclude filter for libfprint & fprintd
│   ├── modprobe.d/
│   │   ├── hp-envy-tablet.conf                        <- options amd_sfh sensor_mask=1, blacklist acer_wmi
│   │   ├── iwlwifi.conf                               <- options iwlwifi power_save=1
│   │   └── audio_powersave.conf                       <- options snd_hda_intel power_save=1
│   ├── sysctl.d/
│   │   └── 99-zram-tweaks.conf                        <- vm.swappiness=100, vm.page-cluster=0
│   ├── systemd/
│   │   ├── logind.conf.d/
│   │   │   └── lid-hibernate.conf                     <- HandleLidSwitch=hibernate
│   │   ├── sleep.conf.d/
│   │   │   └── hibernate.conf                         <- AllowHibernation=yes, HibernateMode=shutdown platform
│   │   ├── system.conf.d/
│   │   │   ├── fast-shutdown.conf                     <- DefaultTimeoutStopSec=15s
│   │   │   └── watchdog.conf                          <- RuntimeWatchdogSec=60s (AMD SP5100 TCO)
│   │   ├── zram-generator.conf                        <- 8GB zram0 zstd compressed swap
│   │   ├── system-sleep/
│   │   │   └── 00-envy-blackbox-and-hibernation.sh    <- Memory compaction, 2GB image_size & EC polling
│   │   └── user/
│   │       ├── lid-hibernate.service                  <- Background lid watchdog & emergency boil-guard
│   │       └── tablet-rotation.service                <- Wayland auto-rotation & smart OSK daemon
│   ├── udev/
│   │   ├── 70-libfprint-2.rules                       <- Synaptics 06cb:00c9 uaccess permissions
│   │   └── 71-amd-sfh-sensors.rules                   <- amd_sfh hidraw & input event uaccess rules
│   └── desktop/
│       └── toggle-tablet-mode.desktop                 <- Pinned Dash/Dock 1-click tablet toggle
├── patches/                                           <- Source code diff patches
│   ├── libfprint-06cb-00c9-tudor-fix.patch            <- Fixes CAPTURE_FLAG_AUTH, retry_idx & check_res
│   └── fprintd-immediate-persistent-save.patch        <- Fixes persistent pairing key serialization
└── scripts/                                           <- Utility, daemon & diagnostic scripts
    ├── apply-all-fixes.sh                             <- Master automated deployment script
    ├── install-synaptics-fingerprint.sh               <- Binary installer for patched fingerprint driver
    ├── lid-hibernate-daemon.py                        <- Power blackbox & boil-guard emergency cutoff
    ├── tablet-rotation-daemon.py                      <- Mutter Wayland rotation & input lock daemon
    ├── toggle-tablet-mode.sh                          <- Manual tablet toggle CLI (<Super>F12)
    ├── test-rotation-live.py                          <- Real-time terminal tilt & OSK visualizer
    ├── sensor-tilt-test.py                            <- 6-position accelerometer calibration tool
    └── system-health-check.sh                         <- Complete hardware & service diagnostics
```

---

## Daily Usage & Shortcuts

- **Tablet Mode Toggle**: Tap the **'Toggle Tablet Mode'** icon pinned to your Dash/Dock, or press **`<Super>F12`**.
  - *Engaged*: Physical keyboard deck and touchpad are fully locked; On-Screen Keyboard is activated.
  - *Disengaged*: Full physical typing restored; On-Screen Keyboard is automatically suppressed.
- **Display Auto-Rotation**: Tilting the laptop seamlessly rotates the display into portrait (90°/270°) or tent (180°) modes without locking physical keys.
- **Danish / Nordic Characters**:
  - `Right Alt + z` $\to$ **`æ`** (`Right Alt + Shift + z` $\to$ **`Æ`**)
  - `Right Alt + l` $\to$ **`ø`** (`Right Alt + Shift + l` $\to$ **`Ø`**)
  - `Right Alt + w` *(or a)* $\to$ **`å`** (`Right Alt + Shift + w` *(or a)* $\to$ **`Å`**)
- **Emergency Boil-Guard Protection**:
  - If the laptop fails hibernation while the lid is closed, the boil-guard daemon pauses 15 seconds to allow drivers to stabilize, retries once, and if it fails a second time, **forces an immediate clean emergency poweroff (`systemctl poweroff -i`)**.
  - Your battery will never drain to 0% inside a backpack.

---

## License

This project is licensed under the [MIT License](LICENSE). Feel free to adapt and share these fixes for other AMD Ryzen HP laptops.
