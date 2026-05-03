#!/bin/bash
# Local Home Agent - macOS DMG Creator Script
# Creates a proper .app bundle and DMG from PyInstaller executable

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

APP_NAME="Local Home Agent"
APP_VERSION="1.0.0"
APP_BUNDLE="LocalHomeAgent.app"
DMG_NAME="LocalHomeAgent-${APP_VERSION}.dmg"
DMG_VOLUME_NAME="${APP_NAME}"
EXECUTABLE="../../dist/LocalHomeAgent"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================================
# COLORS
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Local Home Agent - macOS DMG Builder${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ============================================================================
# CHECK PREREQUISITES
# ============================================================================

echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v create-dmg &> /dev/null; then
    echo -e "${YELLOW}create-dmg not found. Installing via Homebrew...${NC}"
    brew install create-dmg
fi

if [ ! -f "${EXECUTABLE}" ]; then
    echo -e "${RED}Error: LocalHomeAgent executable not found at ${EXECUTABLE}${NC}"
    echo "Please build the app first with: pyinstaller build.spec"
    exit 1
fi

# ============================================================================
# CREATE APP BUNDLE STRUCTURE
# ============================================================================

echo -e "${YELLOW}Creating .app bundle structure...${NC}"

rm -rf "./${APP_BUNDLE}"
mkdir -p "./${APP_BUNDLE}/Contents/MacOS"
mkdir -p "./${APP_BUNDLE}/Contents/Resources"

# Copy executable
cp "${EXECUTABLE}" "./${APP_BUNDLE}/Contents/MacOS/LocalHomeAgent"
chmod +x "./${APP_BUNDLE}/Contents/MacOS/LocalHomeAgent"

# Copy static files and templates if they exist
if [ -d "../../static" ]; then
    cp -r "../../static" "./${APP_BUNDLE}/Contents/Resources/"
fi
if [ -d "../../templates" ]; then
    cp -r "../../templates" "./${APP_BUNDLE}/Contents/Resources/"
fi
if [ -d "../../config" ]; then
    cp -r "../../config" "./${APP_BUNDLE}/Contents/Resources/"
fi

# Create Info.plist
cat > "./${APP_BUNDLE}/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>English</string>
    <key>CFBundleExecutable</key>
    <string>LocalHomeAgent</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>ai.fixitforme.localhomeagent</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>${APP_VERSION}</string>
    <key>CFBundleVersion</key>
    <string>${APP_VERSION}</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.utilities</string>
</dict>
</plist>
EOF

# Create a simple icon if we have a PNG
if [ -f "../../static/icons/icon-256.png" ]; then
    echo -e "${YELLOW}Creating app icon...${NC}"
    # Create iconset
    mkdir -p AppIcon.iconset
    # Use the 256px icon for multiple sizes (basic approach)
    sips -z 16 16 "../../static/icons/icon-256.png" --out AppIcon.iconset/icon_16x16.png 2>/dev/null || true
    sips -z 32 32 "../../static/icons/icon-256.png" --out AppIcon.iconset/icon_16x16@2x.png 2>/dev/null || true
    sips -z 32 32 "../../static/icons/icon-256.png" --out AppIcon.iconset/icon_32x32.png 2>/dev/null || true
    sips -z 64 64 "../../static/icons/icon-256.png" --out AppIcon.iconset/icon_32x32@2x.png 2>/dev/null || true
    sips -z 128 128 "../../static/icons/icon-256.png" --out AppIcon.iconset/icon_128x128.png 2>/dev/null || true
    sips -z 256 256 "../../static/icons/icon-256.png" --out AppIcon.iconset/icon_128x128@2x.png 2>/dev/null || true
    cp "../../static/icons/icon-256.png" AppIcon.iconset/icon_256x256.png 2>/dev/null || true
    sips -z 512 512 "../../static/icons/icon-256.png" --out AppIcon.iconset/icon_256x256@2x.png 2>/dev/null || true

    # Convert to icns
    iconutil -c icns AppIcon.iconset -o "./${APP_BUNDLE}/Contents/Resources/AppIcon.icns" 2>/dev/null || {
        echo -e "${YELLOW}Icon conversion failed, continuing without icon...${NC}"
    }
    rm -rf AppIcon.iconset
fi

# ============================================================================
# CREATE DMG
# ============================================================================

echo -e "${YELLOW}Creating DMG...${NC}"

rm -f "${DMG_NAME}"

# Create a simple staging directory
rm -rf ./staging
mkdir -p ./staging
cp -r "./${APP_BUNDLE}" ./staging/
cd ./staging
ln -s /Applications Applications
cd ..

# Create DMG (simplified - no custom background)
create-dmg \
    --volname "${DMG_VOLUME_NAME}" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "${APP_BUNDLE}" 150 200 \
    --hide-extension "${APP_BUNDLE}" \
    --app-drop-link 450 200 \
    --no-internet-enable \
    "${DMG_NAME}" \
    "./staging/" || {
        # Fallback: create simple DMG with hdiutil if create-dmg fails
        echo -e "${YELLOW}create-dmg failed, using hdiutil fallback...${NC}"
        hdiutil create -volname "${DMG_VOLUME_NAME}" -srcfolder "./staging/" -ov -format UDZO "${DMG_NAME}"
    }

# ============================================================================
# CLEANUP
# ============================================================================

echo -e "${YELLOW}Cleaning up...${NC}"
rm -rf ./staging
rm -rf "./${APP_BUNDLE}"

# ============================================================================
# VERIFICATION
# ============================================================================

if [ -f "${DMG_NAME}" ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  DMG Created Successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "File: ${DMG_NAME}"
    echo "Size: $(du -h "${DMG_NAME}" | cut -f1)"
    echo ""
    echo "To test:"
    echo "  open ${DMG_NAME}"
    echo ""
else
    echo -e "${RED}Error: DMG creation failed${NC}"
    exit 1
fi
