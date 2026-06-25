#!/bin/bash

# Create UF2 or binary file from RP2040 device using picotool
# Usage: 
#   ./create_uf2_from_device.sh              (creates UF2 - full 2MB) ✓ DEFAULT
#   ./create_uf2_from_device.sh -1           (creates UF2 - first 1MB)
#   ./create_uf2_from_device.sh -s           (creates UF2 - first 750KB)
#   ./create_uf2_from_device.sh -x           (creates UF2 - first 500KB)
#   ./create_uf2_from_device.sh -b           (creates binary - full 2MB)
#   ./create_uf2_from_device.sh -b -1        (creates binary - first 1MB)
#   ./create_uf2_from_device.sh -b -s        (creates binary - first 750KB)
#   ./create_uf2_from_device.sh -b -x        (creates binary - first 500KB)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse options
FORMAT="uf2"  # default: UF2 format (compact)
MEMORY_TYPE="all"  # default: full 2MB
MEMORY_RANGE="-r 0x10000000 0x10200000"  # default: full 2MB range
CUSTOM_FILENAME=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -1|--1mb)
            # 1MB (0x100000 bytes)
            MEMORY_TYPE="1MB"
            MEMORY_RANGE="-r 0x10000000 0x10100000"
            shift
            ;;
        -s|--small)
            # 750KB (0xBB800 bytes)
            MEMORY_TYPE="750KB"
            MEMORY_RANGE="-r 0x10000000 0x100BB800"
            shift
            ;;
        -x|--extra-small)
            # 500KB (0x7D000 bytes)
            MEMORY_TYPE="500KB"
            MEMORY_RANGE="-r 0x10000000 0x1007D000"
            shift
            ;;
        -b|--binary)
            FORMAT="bin"
            shift
            ;;
        *)
            CUSTOM_FILENAME="$1"
            shift
            ;;
    esac
done

# Check if picotool is installed
if ! command -v picotool &> /dev/null; then
    echo -e "${RED}Error: picotool not found${NC}"
    echo "Install with: brew install picotool (macOS) or pip install picotool (other)"
    exit 1
fi

# Create dist folder if it doesn't exist
mkdir -p dist

# Set output filename (default: dist/Classic-v2.uf2)
if [ -z "$CUSTOM_FILENAME" ]; then
    OUTPUT_FILE="dist/Classic-v2.${FORMAT}"
else
    OUTPUT_FILE="$CUSTOM_FILENAME"
fi

# If file exists, back it up with creation date
if [ -f "$OUTPUT_FILE" ]; then
    CREATION_DATE=$(stat -f %SB -t "%Y%m%d_%H%M%S" "$OUTPUT_FILE" 2>/dev/null || date -r "$OUTPUT_FILE" +%Y%m%d_%H%M%S 2>/dev/null || echo "unknown")
    BACKUP_FILE="${OUTPUT_FILE%.*}_${CREATION_DATE}.${OUTPUT_FILE##*.}"
    echo -e "${YELLOW}File exists. Backing up to: $BACKUP_FILE${NC}"
    mv "$OUTPUT_FILE" "$BACKUP_FILE"
fi

# Ensure correct extension
if [[ "$FORMAT" == "bin" && ! "$OUTPUT_FILE" =~ \.bin$ ]]; then
    OUTPUT_FILE="${OUTPUT_FILE}.bin"
elif [[ "$FORMAT" == "uf2" && ! "$OUTPUT_FILE" =~ \.uf2$ ]]; then
    OUTPUT_FILE="${OUTPUT_FILE}.uf2"
fi

# Check if device is connected
echo -e "${YELLOW}Checking for connected RP2040 device...${NC}"
if ! picotool info > /dev/null 2>&1; then
    echo -e "${RED}Error: No RP2040 device found${NC}"
    echo "Connect the device in BOOTSEL mode or with CircuitPython running"
    exit 1
fi

echo -e "${GREEN}Device found!${NC}"

# Create backup file
echo -e "${YELLOW}Creating ${FORMAT} file (${MEMORY_TYPE}): ${OUTPUT_FILE}${NC}"

# Always use -r to specify memory range (avoids binary size detection issues)
eval picotool save $MEMORY_RANGE -t "${FORMAT}" "${OUTPUT_FILE}"

# Verify file was created
if [ -f "${OUTPUT_FILE}" ]; then
    FILE_SIZE=$(du -h "${OUTPUT_FILE}" | cut -f1)
    echo -e "${GREEN}✓ Backup created successfully!${NC}"
    echo -e "  File: ${OUTPUT_FILE}"
    echo -e "  Size: ${FILE_SIZE}"
    echo -e "  Format: ${FORMAT}"
else
    echo -e "${RED}Error: Failed to create backup file${NC}"
    exit 1
fi
