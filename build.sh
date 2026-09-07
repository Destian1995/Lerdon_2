#!/bin/bash
APP_VERSION="6.0.0"

echo "=== Сборка Lerdon Legends v${APP_VERSION} ==="

# Очистка и сборка
rm -rf bin
buildozer android clean
git pull
clear
buildozer android release

# Переходим в директорию с APK
cd ~/Lerdon_2/bin || { echo "Директория bin не найдена"; exit 1; }

# Путь к build-tools (подбираем автоматически)
BUILD_TOOLS_DIR=$(ls -d $HOME/.buildozer/android/platform/android-sdk/build-tools/*/ 2>/dev/null | sort -V | tail -1)
if [ -z "$BUILD_TOOLS_DIR" ]; then
    echo "Build tools не найдены!"
    exit 1
fi
echo "Используем build-tools: $BUILD_TOOLS_DIR"

# Находим unsigned APK
UNSIGNED_APK=$(ls lerdonlegends-*-release-unsigned.apk 2>/dev/null | head -1)
if [ -z "$UNSIGNED_APK" ]; then
    echo "Unsigned APK не найден!"
    ls -la
    exit 1
fi
echo "Найден APK: $UNSIGNED_APK"

# 1) Zipalign
${BUILD_TOOLS_DIR}zipalign -v -p 4 \
    "$UNSIGNED_APK" \
    "lerdonlegends-${APP_VERSION}-aligned.apk"

# 2) Подпись
${BUILD_TOOLS_DIR}apksigner sign \
    --ks ../signkey.keystore \
    --ks-key-alias lerdon-release \
    --ks-pass pass:mypassword \
    --key-pass pass:mypassword \
    --out "lerdonlegends-${APP_VERSION}-signed.apk" \
    "lerdonlegends-${APP_VERSION}-aligned.apk"

cd ../
echo "=== Готово ==="
ls -lh bin/lerdonlegends-${APP_VERSION}-signed.apk
