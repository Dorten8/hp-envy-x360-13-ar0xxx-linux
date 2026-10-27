# Tablet Mode, Auto-Rotation & Smart On-Screen Keyboard

**Platform**: HP ENVY x360 Convertible 13-ar0xxx  
**Sensor Architecture**: AMD Sensor Fusion Hub (MP2 PCIe `1022:15e4`, HID `0020:1022:0001.*`)  
**Input Nodes**: AT Translated Set 2 keyboard (`/dev/input/event2`), SYNA328F Touchpad (`/dev/input/event3, event4`), ELAN2514 Touchscreen (`/dev/input/event5`)  

---

## 1. Problem Overview

Convertible 2-in-1 laptops on Linux frequently suffer from three major issues:
1. **Sensor Probe Lockup**: Display auto-rotation fails completely or causes kernel hangs during boot.
2. **The "Hinge Angle" Sensor Fallacy**: The keyboard deck on the back of the folded tablet gets inadvertently unlocked while holding the tablet upright, causing phantom keystrokes.
3. **Aggressive On-Screen Keyboard (OSK)**: GNOME pops up a giant virtual keyboard every time the user enters a password or types `sudo` on the physical laptop keyboard.

---

## 2. Technical Analysis & Root Causes

### 1. AMD SFH MP2 Co-Processor Mailbox Collisions (`sensor_mask = 1`)
- The AMD Sensor Fusion Hub (SFH) uses an embedded MP2 ARM Cortex processor connected via PCIe.
- By default, the Linux `amd_sfh` driver probes six virtual sensor endpoints simultaneously (`sensor_mask = -1`).
- Because this laptop hardware only contains a single 3-axis accelerometer (and lacks gyroscope/magnetometer chips), probing non-existent sensor registers causes MP2 mailbox register contention, deadlocking the driver.
- **Solution**: Restrict driver probing to the primary accelerometer by setting `sensor_mask = 1` in kernel arguments and modprobe:
  ```ini
  options amd_sfh sensor_mask=1
  ```

### 2. The Single Lid G-Sensor Physics Trap
- **Empirical Hardware Discovery**: Hardware probing of the HP ENVY x360 13-ar0xxx motherboard reveals that **no physical hinge rotary encoder or hall-effect angle sensor exists**. Furthermore, this NVMe SKU omits the secondary base accelerometer (`lis3lv02d`).
- **The Physics Problem**: The only motion sensor on the laptop is inside the **screen LID** (`/dev/hidraw0`).
  - When the laptop is placed on a desk in normal clamshell mode, gravity points along $Y \approx -7.0, Z \approx -5.0$.
  - When the screen is folded 360° into a tablet and held upright in front of the user's face, the lid sensor is in the **exact same orientation relative to Earth's gravity** ($Y \approx -7.0, Z \approx -5.0$)!
- **The Consequence**: Any algorithm attempting to guess hinge folding angle from a single gravity vector will mistake an upright tablet for a clamshell laptop, immediately unlocking the physical keyboard on the back.

---

## 3. The Decoupled Architecture

To eliminate false triggers with 100% mathematical certainty, we cleanly decoupled display orientation from input locking:

```mermaid
graph TD
    Sensor["AMD SFH Accelerometer (/dev/hidraw0)"] -->|Poll X/Y/Z Gravity| Daemon["tablet-rotation-daemon.py"]
    Daemon -->|Mutter D-Bus (ApplyTransform)| Display["Display Orientation (0°, 90°, 180°, 270°)"]
    
    User["User Trigger (<Super>F12 or Dash Touch Icon)"] -->|SIGUSR1| Daemon
    Daemon -->|EVIOCGRAB Lock| Kbd["Physical Keyboard (/dev/input/event2)"]
    Daemon -->|EVIOCGRAB Lock| Touchpad["Touchpad (/dev/input/event3, event4)"]
    Daemon -->|GSettings (screen-keyboard-enabled)| OSK["On-Screen Keyboard"]
```

### Component 1: Display Auto-Rotation (Independent of Input Locks)
- The daemon reads raw gravity vectors directly from `/dev/hidraw0` via a dedicated lightweight background thread.
- When tilted, it calculates orientation angles and dispatches rotation calls directly to Mutter's Wayland compositor D-Bus interface (`org.gnome.Mutter.DisplayConfig`).
- Auto-rotation works in all postures (Portrait Right-Up, Portrait Left-Up, Tent, Landscape) smoothly without ever locking the keyboard.

### Component 2: User-Controlled Hardware Input Locking
- When the user folds the screen into tablet mode, inputs are locked on-demand via:
  1. **1-Tap Dash Touch Icon**: Pinned to the GNOME Dash/Dock (`toggle-tablet-mode.desktop`).
  2. **Global Keyboard Shortcut**: **`<Super>F12`** (runs `~/scripts/toggle-tablet-mode.sh`).
- **Hardware Lock Enforcement (`EVIOCGRAB`)**:
  - Synthesizes key release events for all modifier keys (`release_all_modifiers()`) to prevent stuck keys.
  - Acquires exclusive kernel grabs (`ioctl(fd, EVIOCGRAB, 1)`) on `/dev/input/event2` (keyboard) and `/dev/input/event3, event4` (touchpad).
  - Physical keys and touchpad are 100% disabled in hardware. They remain locked until explicitly unlocked by the user.

### Component 3: Smart Dynamic On-Screen Keyboard (OSK)
- **Laptop Mode**: The daemon enforces `org.gnome.desktop.a11y.applications screen-keyboard-enabled = false`. Typing `sudo` on the physical keyboard NEVER summons an unwanted virtual keyboard popup.
- **Tablet Mode**: When inputs are locked, the daemon automatically activates `screen-keyboard-enabled = true`, allowing seamless touch typing on screen.

---

## 4. Associated Files & Tools

| File | Purpose |
| :--- | :--- |
| [`scripts/tablet-rotation-daemon.py`](../scripts/tablet-rotation-daemon.py) | Background Wayland rotation, input grab, and OSK manager |
| [`scripts/toggle-tablet-mode.sh`](../scripts/toggle-tablet-mode.sh) | Instant toggle script dispatched by `<Super>F12` or Dash icon |
| [`scripts/test-rotation-live.py`](../scripts/test-rotation-live.py) | Interactive CLI visualizer displaying live gravity vectors, posture, and OSK state |
| [`scripts/sensor-tilt-test.py`](../scripts/sensor-tilt-test.py) | 6-position accelerometer diagnostic calibration tool |
| [`configs/desktop/toggle-tablet-mode.desktop`](../configs/desktop/toggle-tablet-mode.desktop) | Pinned GNOME Dash/Dock application launcher |
| [`configs/systemd/user/tablet-rotation.service`](../configs/systemd/user/tablet-rotation.service) | User systemd service running the daemon on login |
