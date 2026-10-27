# Synaptics Tudor Match-in-Sensor Fingerprint (`06cb:00c9`)

**Hardware**: Synaptics Tudor Match-in-Sensor USB Fingerprint Reader  
**USB ID**: `06cb:00c9` (`Bus 001 Device 003`)  
**Architecture**: Match-in-Sensor (Hardware TLS handshake & on-chip cryptographic template storage)  

---

## 1. Problem Overview

Out of the box on Linux, the fingerprint scanner on the HP ENVY x360 is completely unsupported:
- `lsusb` reports `06cb:00c9 Synaptics, Inc.`, but stock upstream `libfprint` has no matching driver entry.
- Community reverse-engineered drivers from the `synaTudorMiS` / `synatlsmoc` projects claimed partial support, but enrollment consistently failed:
  ```text
  Enrolling right-index-finger finger.
  Enroll result: enroll-stage-passed
  Enroll result: enroll-stage-passed
  Enroll result: enroll-retry-scan
  Enroll result: enroll-disconnected
  ```
  The sensor crashed or disconnected after 3 to 5 finger taps, and fingerprints were never saved across reboots.

---

## 2. Root Cause Analysis: 4 Critical Driver Bugs Uncovered

Deep source-code auditing of the compiled `libfprint` and `fprintd` driver trees revealed four critical bugs:

### Bug 1: `CAPTURE_FLAG_AUTH = 15` Value Collision
- **Location**: `libfprint/drivers/synatlsmoc/synatlsmoc.h` and `synatlsmoc.c`
- **Analysis**: In upstream community commit `2f8b3e7` (intended for sensor `06cb:00d8`), the developer redefined `CAPTURE_FLAG_AUTH` from `7` to `15`. However, `CAPTURE_FLAG_ENROLL` was *already* defined as `15`!
- **Consequence**: In `send_frame_acquire()`:
  ```c
  if (capture_flags == CAPTURE_FLAG_AUTH)
      mode = 4116; /* AUTH mode */
  else
      mode = 12;   /* ENROLL mode */
  ```
  Because `15 == 15`, `send_frame_acquire()` sent mode `4116` (AUTH mode) during enrollment instead of mode `12`! The sensor firmware expected enrollment parameters, became desynchronized, and disconnected after 3 frames.
- **Fix**: Restored `#define CAPTURE_FLAG_AUTH 7`.

### Bug 2: Pointer Evaluation Bug in `recv_frame_acquire()`
- **Location**: `libfprint/drivers/synatlsmoc/synatlsmoc.c`
- **Analysis**: The code evaluated: `if (retry_idx > 0)` where `retry_idx` is a pointer argument (`int *retry_idx`).
- **Consequence**: On x86_64, a stack pointer address is always non-zero. The code evaluated the memory address of the pointer rather than its dereferenced integer value, erroneously taking retry branches on valid frames.
- **Fix**: Dereferenced the pointer: `if (*retry_idx > 0)`.

### Bug 3: `check_res = TRUE` Logic Inversion
- **Location**: `libfprint/drivers/synatlsmoc/synatlsmoc.c`
- **Analysis**: In `send_frame_acquire()`, `check_res = TRUE` was passed despite an explicit code comment stating that payload status verification must be skipped during handshake setup.
- **Fix**: Passed `check_res = FALSE`.

### Bug 4: Missing Persistent Pairing Data Save in `fprintd`
- **Location**: `fprintd/src/device.c`
- **Analysis**: Match-in-Sensor devices require the host OS to store a cryptographic pairing key on disk (`/var/lib/fprint/0-persistent/synatlsmoc/0`). In upstream `fprintd`, `store.persistent_data_save()` was only registered inside `fprint_device_dispose()`.
- **Consequence**: `fprintd` is a D-Bus activated service configured with a 30-second idle auto-exit (`Type=dbus`). When the idle timeout fired, systemd stopped `fprintd` without invoking full GObject object disposal. The pairing key was never committed to disk, causing the sensor firmware to reject all subsequent authentication attempts.
- **Fix**: Hooked the `"notify::fpi-persistent-data"` GObject signal in `fprint_device_constructed()` to commit pairing keys to disk immediately upon generation.

---

## 3. The Implementation & Build Process

All patches are provided in the [`patches/`](../patches/) directory:
- [`patches/libfprint-06cb-00c9-tudor-fix.patch`](../patches/libfprint-06cb-00c9-tudor-fix.patch)
- [`patches/fprintd-immediate-persistent-save.patch`](../patches/fprintd-immediate-persistent-save.patch)

### Automated Installation via Script

To install the pre-compiled, patched driver binaries directly:
```bash
sudo ./scripts/install-synaptics-fingerprint.sh
```

### Manual Build Instructions (from Source)

```bash
# 1. Install build dependencies
sudo dnf install -y meson ninja-build gcc git libusb1-devel glib2-devel \
    pixman-devel nss-devel polkit-devel systemd-devel dbus-devel pam-devel

# 2. Clone and patch libfprint
git clone https://gitlab.freedesktop.org/libfprint/libfprint.git
cd libfprint
git checkout 2f8b3e7 # Base synatlsmoc commit
patch -p1 < /path/to/patches/libfprint-06cb-00c9-tudor-fix.patch
meson setup builddir -Ddrivers=synatlsmoc --prefix=/usr
ninja -C builddir
sudo ninja -C builddir install

# 3. Clone and patch fprintd
cd ..
git clone https://gitlab.freedesktop.org/libfprint/fprintd.git
cd fprintd
patch -p1 < /path/to/patches/fprintd-immediate-persistent-save.patch
meson setup builddir --prefix=/usr
ninja -C builddir
sudo ninja -C builddir install
```

---

## 4. System Configuration & Protection

### Udev Access Rule
File: `/etc/udev/rules.d/70-libfprint-2.rules`
```udev
SUBSYSTEM=="usb", ATTRS{idVendor}=="06cb", ATTRS{idProduct}=="00c9", ATTRS{dev}=="*", ENV{ID_SECURITY_TOKEN}="1", ENV{DEVTYPE}=="usb_device", TAG+="uaccess"
```

### PAM Authentication Activation
Enable fingerprint PAM auth in Fedora:
```bash
sudo authselect enable-feature with-fingerprint
sudo authselect apply-changes
```

### DNF Update Version Lock
To prevent `dnf update` from overwriting our patched custom drivers with unpatched stock packages, add an exclusion filter:

File: `/etc/dnf/dnf.conf`
```ini
excludepkgs=libfprint* fprintd*
```

---

## 5. Enrolling & Verifying Fingerprints

1. Enroll your right index finger:
   ```bash
   fprintd-enroll
   ```
   *Touch the sensor repeatedly (typically 8–10 taps) until it outputs: `Enroll result: enroll-completed`.*

2. Verify authentication:
   ```bash
   fprintd-verify
   ```
   *Touch the sensor. Output: `Verify result: verify-match (done)`.*

3. Test with `sudo`:
   ```bash
   sudo -v
   ```
   *The prompt `Place your right index finger on the fingerprint reader` will appear, authenticating immediately.*
