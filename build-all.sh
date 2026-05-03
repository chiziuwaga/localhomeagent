#!/bin/bash

# Build script for creating cross-platform executables
# Supports Windows (32/64-bit), Linux, and macOS

set -e

echo "🏗️  Building Local Home Agent for all platforms..."

# Create dist directory
mkdir -p dist

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt
pip install pyinstaller

# Build for Linux
echo "🐧 Building for Linux..."
pyinstaller build.spec --clean --noconfirm
mv dist/LocalHomeAgent dist/LocalHomeAgent-linux-x64

# Build for Windows 64-bit (requires Wine on Linux)
echo "🪟 Building for Windows 64-bit..."
if command -v wine64 &> /dev/null; then
    wine64 python -m PyInstaller build.spec --clean --noconfirm
    mv dist/LocalHomeAgent.exe dist/LocalHomeAgent-win64.exe
else
    echo "⚠️  Wine64 not found. Skipping Windows 64-bit build."
    echo "   Install Wine to build Windows executables on Linux."
fi

# Build for Windows 32-bit (requires Wine on Linux)
echo "🪟 Building for Windows 32-bit..."
if command -v wine &> /dev/null; then
    wine python -m PyInstaller build.spec --clean --noconfirm
    mv dist/LocalHomeAgent.exe dist/LocalHomeAgent-win32.exe
else
    echo "⚠️  Wine not found. Skipping Windows 32-bit build."
fi

# Build for macOS (only works on macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🍎 Building for macOS..."
    pyinstaller build.spec --clean --noconfirm
    mv dist/LocalHomeAgent dist/LocalHomeAgent-macos
else
    echo "ℹ️  Skipping macOS build (requires macOS system)"
fi

echo "✅ Build complete!"
echo "📁 Executables are in the dist/ directory:"
ls -lh dist/

echo ""
echo "🐳 To build Docker image instead, run:"
echo "   docker build -t local-home-agent ."
echo "   docker-compose up -d"
