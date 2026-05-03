#!/bin/bash
# Local Home Agent - Linux AppImage Builder
# Creates an AppImage from PyInstaller executable

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

APP_NAME="LocalHomeAgent"
APP_VERSION="1.0.0"
APP_ID="ai.fixitforme.localhomeagent"
EXECUTABLE="../../dist/LocalHomeAgent"
APPDIR="./AppDir"

# ============================================================================
# COLORS
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Local Home Agent - Linux AppImage${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ============================================================================
# CHECK PREREQUISITES
# ============================================================================

echo -e "${YELLOW}Checking prerequisites...${NC}"

if [ ! -f "${EXECUTABLE}" ]; then
    echo -e "${RED}Error: LocalHomeAgent executable not found at ${EXECUTABLE}${NC}"
    echo "Please build the app first with: pyinstaller build.spec"
    exit 1
fi

# Download appimagetool if not available
APPIMAGETOOL="./appimagetool"
if [ ! -f "${APPIMAGETOOL}" ]; then
    echo -e "${YELLOW}Downloading appimagetool...${NC}"
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O "${APPIMAGETOOL}"
    chmod +x "${APPIMAGETOOL}"
fi

# ============================================================================
# CREATE APPDIR STRUCTURE
# ============================================================================

echo -e "${YELLOW}Creating AppDir structure...${NC}"

rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${APPDIR}/usr/share/metainfo"

# ============================================================================
# COPY APPLICATION FILES
# ============================================================================

echo -e "${YELLOW}Copying application files...${NC}"

# Copy the PyInstaller executable
cp "${EXECUTABLE}" "${APPDIR}/usr/bin/${APP_NAME}"
chmod +x "${APPDIR}/usr/bin/${APP_NAME}"

# Copy static files and templates if they exist
if [ -d "../../static" ]; then
    mkdir -p "${APPDIR}/usr/share/${APP_NAME}"
    cp -r "../../static" "${APPDIR}/usr/share/${APP_NAME}/"
fi
if [ -d "../../templates" ]; then
    cp -r "../../templates" "${APPDIR}/usr/share/${APP_NAME}/"
fi
if [ -d "../../config" ]; then
    cp -r "../../config" "${APPDIR}/usr/share/${APP_NAME}/"
fi

# Copy or create icon
if [ -f "../../static/icons/icon-256.png" ]; then
    cp "../../static/icons/icon-256.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/${APP_ID}.png"
    cp "../../static/icons/icon-256.png" "${APPDIR}/${APP_ID}.png"
else
    # Create a simple placeholder icon
    echo -e "${YELLOW}No icon found, creating placeholder...${NC}"
    convert -size 256x256 xc:navy -fill white -gravity center -pointsize 48 -annotate 0 'LHA' "${APPDIR}/${APP_ID}.png" 2>/dev/null || {
        # If imagemagick not available, create a simple 1x1 PNG
        printf '\x89PNG\r\n\x1a\n' > "${APPDIR}/${APP_ID}.png"
    }
fi

# ============================================================================
# CREATE DESKTOP FILE
# ============================================================================

echo -e "${YELLOW}Creating desktop entry...${NC}"

cat > "${APPDIR}/usr/share/applications/${APP_ID}.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Local Home Agent
GenericName=Smart Home Controller
Comment=AI-powered smart home management running locally
Exec=${APP_NAME}
Icon=${APP_ID}
Terminal=false
Categories=Utility;System;
Keywords=smart;home;iot;automation;ai;
StartupNotify=true
StartupWMClass=${APP_NAME}
EOF

# Copy desktop file to root for AppImage
cp "${APPDIR}/usr/share/applications/${APP_ID}.desktop" "${APPDIR}/${APP_ID}.desktop"

# ============================================================================
# CREATE APPSTREAM METADATA
# ============================================================================

echo -e "${YELLOW}Creating AppStream metadata...${NC}"

cat > "${APPDIR}/usr/share/metainfo/${APP_ID}.appdata.xml" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>${APP_ID}</id>
  <name>Local Home Agent</name>
  <summary>AI-powered smart home management running locally</summary>
  <metadata_license>MIT</metadata_license>
  <project_license>MIT</project_license>
  <description>
    <p>
      Local Home Agent is a privacy-focused smart home controller that runs
      entirely on your local network. No cloud services required.
    </p>
    <p>Features:</p>
    <ul>
      <li>AI-powered natural language control via local LLMs (Ollama)</li>
      <li>Home Assistant integration for device control</li>
      <li>IoT device auto-discovery</li>
      <li>Works completely offline</li>
    </ul>
  </description>
  <launchable type="desktop-id">${APP_ID}.desktop</launchable>
  <url type="homepage">https://fixitforme.ai</url>
  <developer_name>FixItForMe.ai</developer_name>
  <releases>
    <release version="${APP_VERSION}" date="2025-01-01">
      <description>
        <p>Initial release</p>
      </description>
    </release>
  </releases>
  <content_rating type="oars-1.1" />
  <provides>
    <binary>${APP_NAME}</binary>
  </provides>
</component>
EOF

# ============================================================================
# CREATE APPRUN SCRIPT
# ============================================================================

echo -e "${YELLOW}Creating AppRun script...${NC}"

cat > "${APPDIR}/AppRun" << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
export XDG_DATA_DIRS="${HERE}/usr/share:${XDG_DATA_DIRS}"
exec "${HERE}/usr/bin/LocalHomeAgent" "$@"
EOF

chmod +x "${APPDIR}/AppRun"

# ============================================================================
# BUILD APPIMAGE
# ============================================================================

echo -e "${YELLOW}Building AppImage...${NC}"

APPIMAGE_NAME="${APP_NAME}-${APP_VERSION}-x86_64.AppImage"
rm -f "${APPIMAGE_NAME}"

# Build with appimagetool
ARCH=x86_64 "${APPIMAGETOOL}" --no-appstream "${APPDIR}" "${APPIMAGE_NAME}" || {
    echo -e "${YELLOW}AppImage creation with appstream failed, trying without validation...${NC}"
    ARCH=x86_64 "${APPIMAGETOOL}" "${APPDIR}" "${APPIMAGE_NAME}"
}

# ============================================================================
# CLEANUP
# ============================================================================

echo -e "${YELLOW}Cleaning up...${NC}"
rm -rf "${APPDIR}"

# ============================================================================
# VERIFICATION
# ============================================================================

if [ -f "${APPIMAGE_NAME}" ]; then
    chmod +x "${APPIMAGE_NAME}"
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  AppImage Created Successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "File: ${APPIMAGE_NAME}"
    echo "Size: $(du -h "${APPIMAGE_NAME}" | cut -f1)"
    echo ""
    echo "To run:"
    echo "  chmod +x ${APPIMAGE_NAME}"
    echo "  ./${APPIMAGE_NAME}"
    echo ""
else
    echo -e "${RED}Error: AppImage creation failed${NC}"
    exit 1
fi
