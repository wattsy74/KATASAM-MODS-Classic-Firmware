# BGG Firmware Updates Repository

This repository hosts firmware updates for BumbleGum Guitars devices.

## Current Version

**Version:** 3.1  
**Generated:** 2025-08-02T13:44:20.329686Z  
**Files:** 8 firmware files  

## How It Works

1. **Automatic Detection**: BGG Windows App checks this repository every 24 hours
2. **Version Comparison**: Compares device firmware with `version_manifest.json`
3. **Safe Updates**: Downloads and stages files in `/updates/` folder
4. **Atomic Installation**: Boot-time migration ensures device safety

## Repository Structure

```
/
├── version_manifest.json     # Version information and checksums
├── boot.py                   # Boot configuration with update processor
├── code.py                   # Main application code  
├── serial_handler.py         # Serial communication handler
├── utils.py                  # Utility functions
├── hardware.py               # Hardware abstraction
├── gamepad.py                # Gamepad functionality
├── config.json               # Default configuration
├── presets.json              # Default presets
└── README.md                 # This file
```

## Security

- All files verified with SHA-256 checksums
- HTTPS downloads only
- Staged deployment prevents device corruption
- Atomic file operations ensure stability

## Version History

- **v3.1**: Automatic update system with staged deployment
- **v3.0**: Initial firmware release

## Usage

BGG devices automatically detect and install updates from this repository. Users can also manually check for updates using the "Check for Updates" button in the BGG Windows App.

---

**Generated automatically by BGG Firmware Update System**
