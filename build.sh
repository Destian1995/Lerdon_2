#!/bin/bash
set -e

APP_VERSION="6.0.0"
KEYSTORE="$HOME/signkey.keystore"
ANDROID_BUILD_TOOLS="$HOME/.buildozer/android/platform/android-sdk/build-tools/36.0.0"
DIST_DIR="$HOME/Lerdon_2/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/dists/lerdonlegends"

echo "=== Сборка Lerdon Legends v${APP_VERSION} ==="

# Сбрасываем локальные изменения и подтягиваем последнее
git checkout -- . 2>/dev/null || true
git pull

# Сборка
rm -rf bin
export GRADLE_OPTS="-Xmx4g -Dfile.encoding=utf-8"
buildozer android release || true

# Если buildozer упал на gradle — собираем gradle вручную с увеличенной памятью
if [ ! -d "bin" ] || [ -z "$(ls bin/*.apk 2>/dev/null)" ]; then
    echo "=== Buildozer gradle failed, retrying with more memory ==="
    echo "org.gradle.jvmargs=-Xmx4g" >> $DIST_DIR/gradle.properties
    sed -i 's/DEFAULT_JVM_OPTS=""/DEFAULT_JVM_OPTS="-Xmx4g"/' $DIST_DIR/gradlew 2>/dev/null || true
    cd $DIST_DIR
    ./gradlew clean assembleRelease
    cd ~/Lerdon_2
fi

# Находим unsigned APK
mkdir -p bin
APK_DIR="$DIST_DIR/build/outputs/apk/release"
UNSIGNED_APK=$(ls $APK_DIR/*unsigned*.apk 2>/dev/null | head -1)

if [ -z "$UNSIGNED_APK" ]; then
    echo "ОШИБКА: unsigned APK не найден"
    exit 1
fi

echo "=== Zipalign ==="
$ANDROID_BUILD_TOOLS/zipalign -v -p 4 \
    "$UNSIGNED_APK" \
    bin/lerdonlegends-${APP_VERSION}-aligned.apk

echo "=== Подпись APK ==="
$ANDROID_BUILD_TOOLS/apksigner sign \
    --ks "$KEYSTORE" \
    --ks-key-alias lerdon-release \
    --ks-pass pass:mypassword \
    --key-pass pass:mypassword \
    --out bin/lerdonlegends-${APP_VERSION}-signed.apk \
    bin/lerdonlegends-${APP_VERSION}-aligned.apk

cp -rf bin ~/project 2>/dev/null || true

echo "=== Готово ==="
ls -lh bin/lerdonlegends-${APP_VERSION}-signed.apk
