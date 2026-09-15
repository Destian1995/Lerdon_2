#!/bin/bash
set -e

APP_VERSION="6.0.0"
KEYSTORE="$HOME/signkey.keystore"
ANDROID_BUILD_TOOLS="$HOME/.buildozer/android/platform/android-sdk/build-tools/36.0.0"
DIST_DIR="$HOME/Lerdon_2/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/dists/lerdonlegends"
APK_DIR="$DIST_DIR/build/outputs/apk/release"

echo "=== Сборка Lerdon Legends v${APP_VERSION} ==="

# Подтягиваем последние изменения
git pull

# Чистим предыдущие артефакты
rm -rf bin
mkdir -p bin

# Сборка Python-бандла и ресурсов через buildozer
# (даже если gradle упадёт, private.tar будет пересобран)
export GRADLE_OPTS="-Xmx4g -Dfile.encoding=utf-8"
buildozer android release 2>&1 || true

# Проверяем: если APK не собран — пересобираем gradle вручную
UNSIGNED_APK=$(ls $APK_DIR/*unsigned*.apk 2>/dev/null | head -1)

if [ -z "$UNSIGNED_APK" ]; then
    echo "=== Buildozer gradle упал, пересобираем gradle вручную ==="
    # Увеличиваем память для gradle
    grep -q 'org.gradle.jvmargs' $DIST_DIR/gradle.properties 2>/dev/null || \
        echo "org.gradle.jvmargs=-Xmx4g" >> $DIST_DIR/gradle.properties
    sed -i 's/DEFAULT_JVM_OPTS=""/DEFAULT_JVM_OPTS="-Xmx4g"/' $DIST_DIR/gradlew 2>/dev/null || true

    cd $DIST_DIR
    ./gradlew clean assembleRelease
    cd ~/Lerdon_2

    UNSIGNED_APK=$(ls $APK_DIR/*unsigned*.apk 2>/dev/null | head -1)
fi

if [ -z "$UNSIGNED_APK" ]; then
    echo "ОШИБКА: unsigned APK не найден в $APK_DIR"
    exit 1
fi

echo "=== Найден: $UNSIGNED_APK ==="

# Zipalign
echo "=== Zipalign ==="
$ANDROID_BUILD_TOOLS/zipalign -f -v -p 4 \
    "$UNSIGNED_APK" \
    bin/lerdonlegends-${APP_VERSION}-aligned.apk

# Подпись
echo "=== Подпись APK ==="
$ANDROID_BUILD_TOOLS/apksigner sign \
    --ks "$KEYSTORE" \
    --ks-key-alias lerdon-release \
    --ks-pass pass:mypassword \
    --key-pass pass:mypassword \
    --out bin/lerdonlegends-${APP_VERSION}-signed.apk \
    bin/lerdonlegends-${APP_VERSION}-aligned.apk

# Удаляем промежуточный файл
rm -f bin/lerdonlegends-${APP_VERSION}-aligned.apk

# Копируем финальный APK
mkdir -p ~/project/bin
cp bin/lerdonlegends-${APP_VERSION}-signed.apk ~/project/bin/

echo "=== Готово ==="
ls -lh bin/lerdonlegends-${APP_VERSION}-signed.apk
