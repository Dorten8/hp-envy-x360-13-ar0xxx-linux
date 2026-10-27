# Nordic / Danish Keyboard Layout (`us+altgr-intl`)

**Hardware SKU**: HP `#UUW` (Nordic physical keycaps)  
**Target Languages**: English (Programming / US QWERTY) & Danish / Nordic (`æ`, `ø`, `å`, `ä`, `ö`)  
**Recommended Keymap**: `English (US, intl., with AltGr dead keys)` (`us+altgr-intl`)  

---

## 1. The Programmer's Dilemma on Nordic Hardware

The HP ENVY x360 convertible SKU `#UUW` is manufactured with a physical Nordic keyboard. When developing software on Linux, engineers face a frustrating trade-off:

1. **Native Danish/Swedish Layouts (`dk` / `se`)**:
   - Offers native single-key typing for `æ`, `ø`, `å`.
   - **The Problem for Developers**: Essential programming characters (`[`, `]`, `{`, `}`, `\`, `|`, `~`) are banished to awkward AltGr key combinations. Furthermore, the `'` and `"` keys are repositioned, disrupting standard muscle memory.
2. **Standard US Layout (`us`)**:
   - Ideal for coding, terminal navigation, and markdown formatting.
   - **The Problem**: Right Alt acts only as a duplicate Alt key; typing Danish or Nordic characters (`æ`, `ø`, `å`) is impossible without switching layouts.
3. **Traditional US-International with Dead Keys (`us(intl)`)**:
   - Makes the apostrophe (`'`) and double-quote (`"`) into "dead keys". Pressing `'` does not output a quote until you press the Spacebar, causing extreme friction when writing code or JSON.

---

## 2. The Ideal Solution: `us+altgr-intl`

The `English (US, intl., with AltGr dead keys)` variant (`us+altgr-intl`) solves this dilemma completely:

- **100% Clean US QWERTY for Coding**:
  - The apostrophe (`'`) and double-quote (`"`) are **normal, immediate characters** (dead keys are moved strictly to Level 3).
  - All programming symbols (`{`, `}`, `[`, `]`, `\`, `|`, `~`, `/`, `<Super>`) are positioned in standard US QWERTY locations.
- **Instant Nordic Characters via Right Alt (AltGr)**:
  - Holding **`Right Alt`** allows you to type Danish and Nordic characters directly with zero dead-key latency.

---

## 3. Complete AltGr Shortcut Reference Table

### Danish Characters (æ, ø, å)

| Character | Lowercase Shortcut | Uppercase Shortcut |
| :---: | :--- | :--- |
| **æ / Æ** | **`Right Alt + z`** | **`Right Alt + Shift + z`** |
| **ø / Ø** | **`Right Alt + l`** | **`Right Alt + Shift + l`** |
| **å / Å** | **`Right Alt + w`** *(or `Right Alt + a`)* | **`Right Alt + Shift + w`** *(or `Right Alt + Shift + a`)* |

### Other Nordic & European Characters

| Symbol | Shortcut | Note |
| :---: | :--- | :--- |
| **ä / Ä** | `Right Alt + q` / `Right Alt + Shift + q` | Swedish / German umlaut A |
| **ö / Ö** | `Right Alt + p` / `Right Alt + Shift + p` | Swedish / German umlaut O |
| **é / É** | `Right Alt + e` / `Right Alt + Shift + e` | French acute E |
| **á / Á** | `Right Alt + a` / `Right Alt + Shift + a` | Acute A |
| **ß** | `Right Alt + s` | German sharp S (Eszett) |
| **€** | `Right Alt + 5` | Euro currency symbol |
| **© / ®** | `Right Alt + c` / `Right Alt + r` | Copyright / Registered |

---

## 4. Activation & Persistence

### Immediate GNOME Wayland Activation
To enable this layout immediately in your current desktop session:
```bash
gsettings set org.gnome.desktop.input-sources sources "[('xkb', 'us+altgr-intl')]"
```

### System-Wide Persistence (Console & Reboots)
To ensure systemd and XKB persist this layout across all reboots:
```bash
sudo localectl set-x11-keymap us pc105 altgr-intl
```

This configuration is automatically applied and verified by [`scripts/apply-all-fixes.sh`](../scripts/apply-all-fixes.sh).
