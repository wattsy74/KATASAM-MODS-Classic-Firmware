# Release Notes Template for GitHub

**Use this content when creating a release on GitHub for v5.0.2**

---

## 🎸 v5.0.2 - Demo Mode & LED Transitions

### ✨ Major Features

**Demo Mode** - Perfect for retail displays and demo setups!
- Activate at boot: Hold **GREEN_FRET + ORANGE_FRET** for 0.5+ seconds at power-on
- Automatically cycles through all 13 standard presets every 5 seconds
- Runs continuously until power-off
- No computer or gamepad needed

**White LED Flashes** - Visual feedback for mode changes
- 2x white flash when entering guide mode
- 2x white flash when exiting guide mode  
- 2x white flash when activating demo mode
- Smooth color restoration after transitions

**Enhanced Color Support**
- Presets now work with both hex (`#XXXXXX`) and rgb(`r,g,b`) color formats
- Fixed BumbleGum Yellow and other presets with rgb() format

### 🛠️ Tools & Utilities

**Smart Deployment Script** (`deploy-to-device.sh`)
- Separate prompts for code vs. config file deployment
- Deploy firmware updates without overwriting user presets
- Prompt 1: Code files (`.py`, `lib/`, data `.json`)
- Prompt 2: User configs (`config.json`, `presets.json`, `user_presets.json`)

**Firmware Backup Tool** (`create_uf2_from_device.sh`)
- Backup device firmware in multiple formats
- Options: 1MB, 750KB, 500KB, 2MB full, or binary format
- Auto-timestamps backup files

### 🐛 Bug Fixes

- **Tiltwave Regression**: Fixed blue frame stuck after guide mode exit
- **Stale LED Frame**: Fixed LEDs not refreshing after animation completion

### 📋 Technical Details

- Boot activation only checks at power-on (prevents accidental triggers during play)
- Demo mode has proper global state declarations to prevent hangs
- All LED transitions properly store and restore colors
- No breaking changes from v5.0.1 - fully backward compatible

### 🧪 Testing Checklist

- [ ] Boot with GREEN+ORANGE held → White flash 2x → Presets cycle every 5s
- [ ] Enter guide mode → White flash 2x
- [ ] Exit guide mode with START → White flash 2x
- [ ] Test UP/DOWN preset cycling in guide mode
- [ ] Verify all 13 presets display correctly
- [ ] Normal gameplay unaffected
- [ ] Demo mode doesn't activate accidentally

### 📦 Installation

```bash
./deploy-to-device.sh
```

Choose:
- **Deploy code files?** → Yes (for firmware update)
- **Deploy config files?** → No (preserve your presets)

---

**Commit**: [Link to commit on GitHub]  
**Branch**: v5.0.1  
**Status**: Ready for testing
