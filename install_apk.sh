#!/usr/bin/env bash
# install_apk.sh — Transfer and install EngageLens APK on smartboard via ADB
#
# Requirements:
#   sudo apt install adb          (if adb not installed)
#   Enable "Developer Options" and "USB Debugging" on the smartboard
#   Connect smartboard to this PC via USB
#
# Usage:
#   chmod +x install_apk.sh
#   ./install_apk.sh

set -e

APK_PATH="$(dirname "$0")/engagelens_app/build/app/outputs/flutter-apk/app-release.apk"

if [ ! -f "$APK_PATH" ]; then
    echo "❌ APK not found at: $APK_PATH"
    echo "   Run: cd engagelens_app && flutter build apk --release"
    exit 1
fi

echo "📱 Checking connected devices..."
adb devices -l

echo ""
echo "📦 Installing EngageLens APK ($APK_PATH) ..."
adb install -r "$APK_PATH"

echo ""
echo "✅ Installation complete! Launch 'EngageLens' on the smartboard."
echo ""
echo "💡 If you see a 'INSTALL_FAILED_UPDATE_INCOMPATIBLE' error:"
echo "   Run: adb uninstall com.engagelens.engagelens_app"
echo "   Then retry: ./install_apk.sh"
