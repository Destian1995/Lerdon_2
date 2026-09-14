#!/bin/bash
set -e

# Сбрасываем локальные изменения и подтягиваем последнее
git checkout -- . 2>/dev/null || true
git pull

APP_VERSION="6.0.0"
KEYSTORE="$HOME/signkey.keystore"
ANDROID_BUILD_TOOLS="$HOME/.buildozer/android/platform/android-sdk/build-tools/36.0.0"

echo "=== Сборка Lerdon Legends v${APP_VERSION} ==="

# Очистка бинарников
rm -rf bin

# Сборка APK (без clean — сохраняем кеш скачанных пакетов)
buildozer android release

# Проверяем что сборка прошла
cd ~/Lerdon_2/bin || { echo "ОШИБКА: директория bin не создана, сборка провалилась"; exit 1; }

UNSIGNED_APK="lerdonlegends-${APP_VERSION}-arm64-v8a_armeabi-v7a-release-unsigned.apk"
ALIGNED_APK="lerdonlegends-${APP_VERSION}-multiabi-release-aligned.apk"
SIGNED_APK="lerdonlegends-${APP_VERSION}-multiabi-release-signed.apk"

if [ ! -f "$UNSIGNED_APK" ]; then
    echo "ОШИБКА: $UNSIGNED_APK не найден!"
    ls -la
    exit 1
fi

echo "=== Zipalign ==="
$ANDROID_BUILD_TOOLS/zipalign -v -p 4 "$UNSIGNED_APK" "$ALIGNED_APK"

echo "=== Подпись APK ==="
if [ ! -f "$KEYSTORE" ]; then
    echo "ОШИБКА: Keystore не найден: $KEYSTORE"
    exit 1
fi

$ANDROID_BUILD_TOOLS/apksigner sign \
    --ks "$KEYSTORE" \
    --ks-key-alias lerdon-release \
    --ks-pass pass:Lerdon \
    --key-pass pass:Lerdon \
    --out "$SIGNED_APK" \
    "$ALIGNED_APK"

cd ~/Lerdon_2
cp -rf bin ~/project 2>/dev/null || true

echo "=== Готово ==="
ls -lh "bin/$SIGNED_APK"
