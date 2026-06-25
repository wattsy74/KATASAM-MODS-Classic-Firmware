#!/bin/bash

# Deploy script for CircuitPython device
# Copies Python files, JSON configs, and lib directory to CIRCUITPY volume

set -e

CIRCUITPY_MOUNT="/Volumes/CIRCUITPY"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🎸 KATASAM CircuitPython Device Deployer${NC}"
echo ""

# Check if CIRCUITPY volume is mounted
if [ ! -d "$CIRCUITPY_MOUNT" ]; then
    echo -e "${RED}⚠️  CIRCUITPY volume not found!${NC}"
    echo ""
    echo "Please put your device into CircuitPython mode:"
    echo "  1. Unplug the device"
    echo "  2. Plug it back in WHILE HOLDING the D-Pad DOWN button"
    echo "  3. Wait for the CIRCUITPY volume to appear"
    echo ""
    read -p "Press ENTER once you've plugged in the device in CP mode..."
    
    # Wait a bit for the volume to mount
    echo "Waiting for device to mount..."
    sleep 2
    
    # Check again
    if [ ! -d "$CIRCUITPY_MOUNT" ]; then
        echo -e "${RED}❌ CIRCUITPY volume still not found. Please try again.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ CIRCUITPY volume found!${NC}"
echo ""

# List files to be copied
echo "Files available for deployment:"
echo ""
echo "  ${YELLOW}CODE FILES (firmware + data):${NC}"
echo "    • All .py files"
echo "    • lib/ directory (entire contents)"
echo "    • All .json files except config/presets/user_presets"
echo ""
echo "  ${YELLOW}USER CONFIG FILES:${NC}"
echo "    • config.json"
echo "    • presets.json"
echo "    • user_presets.json"
echo ""

# Prompt for code files deployment
read -p "Deploy code files (.py, lib/, and data .json files)? [y/N]: " -n 1 -r
echo
DEPLOY_CODE=0
if [[ $REPLY =~ ^[Yy]$ ]]; then
    DEPLOY_CODE=1
fi

# Prompt for config files deployment
read -p "Deploy user config files (config.json, presets.json, user_presets.json)? [y/N]: " -n 1 -r
echo
DEPLOY_CONFIG=0
if [[ $REPLY =~ ^[Yy]$ ]]; then
    DEPLOY_CONFIG=1
fi

# Check if anything is selected
if [ $DEPLOY_CODE -eq 0 ] && [ $DEPLOY_CONFIG -eq 0 ]; then
    echo -e "${YELLOW}Nothing selected. Cancelled.${NC}"
    exit 0
fi

echo ""
echo "Deploying files..."

# Copy Python files
if [ $DEPLOY_CODE -eq 1 ]; then
    echo "  → Copying .py files..."
    find "$SOURCE_DIR" -maxdepth 1 -name "*.py" -type f -exec cp {} "$CIRCUITPY_MOUNT/" \;

    # Copy lib directory
    if [ -d "$SOURCE_DIR/lib" ]; then
        echo "  → Copying lib/ directory..."
        rm -rf "$CIRCUITPY_MOUNT/lib"
        cp -r "$SOURCE_DIR/lib" "$CIRCUITPY_MOUNT/"
    fi

    # Copy data JSON files (all except config/presets/user_presets)
    echo "  → Copying data .json files..."
    for jsonfile in "$SOURCE_DIR"/*.json; do
        filename=$(basename "$jsonfile")
        if [[ "$filename" != "config.json" && "$filename" != "presets.json" && "$filename" != "user_presets.json" ]]; then
            cp "$jsonfile" "$CIRCUITPY_MOUNT/"
            echo "      ✓ $filename"
        fi
    done
fi

# Copy user config JSON files
if [ $DEPLOY_CONFIG -eq 1 ]; then
    echo "  → Copying user config files..."
    for configfile in config.json presets.json user_presets.json; do
        if [ -f "$SOURCE_DIR/$configfile" ]; then
            cp "$SOURCE_DIR/$configfile" "$CIRCUITPY_MOUNT/"
            echo "      ✓ $configfile"
        fi
    done
fi

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""

# Eject the volume
echo "Ejecting CIRCUITPY volume..."
diskutil eject "$CIRCUITPY_MOUNT" 2>/dev/null || true
echo -e "${GREEN}✓ Volume ejected${NC}"
echo ""
echo "Next steps:"
echo "  1. Unplug the device to exit CircuitPython mode"
echo "  2. Plug it back in normally to run the firmware"
echo ""
