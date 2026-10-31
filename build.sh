#!/bin/bash
set -e

PROJECT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
cd -- "$PROJECT_DIR"
APP_VERSION="7.0.3"
KEYSTORE="$HOME/signkey.keystore"
ANDROID_BUILD_TOOLS="$HOME/.buildozer/android/platform/android-sdk/build-tools/36.0.0"
DIST_DIR="$PROJECT_DIR/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/dists/lerdonlegends"
APK_DIR="$DIST_DIR/build/outputs/apk/release"

echo "=== Сборка Lerdon Legends v${APP_VERSION} ==="

# Подтягиваем последние изменения
git pull --ff-only
python3 tools/verify_release_version.py
APP_VERSION_CODE=$(python3 -c "import configparser; c=configparser.ConfigParser(interpolation=None); c.read('buildozer.spec'); print(c['app']['android.numeric_version'])")
BUILD_STARTED=$(mktemp)
trap 'rm -f -- "$BUILD_STARTED"' EXIT

# Чистим предыдущие артефакты
if [ -e "$PROJECT_DIR/bin" ]; then
    test "$(realpath "$PROJECT_DIR/bin")" = "$PROJECT_DIR/bin"
    rm -rf -- "$PROJECT_DIR/bin"
fi
mkdir -p bin

# Сборка Python-бандла и ресурсов через buildozer
# (даже если gradle упадёт, private.tar будет пересобран)
export GRADLE_OPTS="-Xmx4g -Dfile.encoding=utf-8"
buildozer android release 2>&1 || true
PRIVATE_TAR="$DIST_DIR/src/main/assets/private.tar"
if [ ! -f "$PRIVATE_TAR" ] || [ ! "$PRIVATE_TAR" -nt "$BUILD_STARTED" ]; then
    echo "ОШИБКА: пакет исходников не обновлён; повторная упаковка старой версии запрещена"
    exit 1
fi

# Проверяем: если APK не собран — пересобираем gradle вручную
UNSIGNED_APK=$(find "$APK_DIR" -maxdepth 1 -name '*unsigned*.apk' -newer "$BUILD_STARTED" -print -quit 2>/dev/null || true)

if [ -z "$UNSIGNED_APK" ]; then
    echo "=== Buildozer gradle упал, пересобираем gradle вручную ==="
    # Увеличиваем память для gradle
    grep -q 'org.gradle.jvmargs' $DIST_DIR/gradle.properties 2>/dev/null || \
        echo "org.gradle.jvmargs=-Xmx4g" >> $DIST_DIR/gradle.properties
    sed -i 's/DEFAULT_JVM_OPTS=""/DEFAULT_JVM_OPTS="-Xmx4g"/' $DIST_DIR/gradlew 2>/dev/null || true

    cd $DIST_DIR
    ./gradlew clean assembleRelease
    cd -- "$PROJECT_DIR"

    UNSIGNED_APK=$(find "$APK_DIR" -maxdepth 1 -name '*unsigned*.apk' -newer "$BUILD_STARTED" -print -quit 2>/dev/null || true)
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

# Check the final manifest, not just the filename or source settings.
FINAL_APK="bin/lerdonlegends-${APP_VERSION}-signed.apk"
BADGING=$($ANDROID_BUILD_TOOLS/aapt dump badging "$FINAL_APK")
if ! printf '%s\n' "$BADGING" | grep -Fq "versionCode='$APP_VERSION_CODE' versionName='$APP_VERSION'"; then
    echo "ОШИБКА: версия в AndroidManifest.xml не совпадает с настройками релиза"
    exit 1
fi
$ANDROID_BUILD_TOOLS/apksigner verify --verbose "$FINAL_APK"
$ANDROID_BUILD_TOOLS/zipalign -c -p 4 "$FINAL_APK"
sha256sum "$FINAL_APK" > "$FINAL_APK.sha256"

# Копируем финальный APK
mkdir -p ~/project/bin
cp bin/lerdonlegends-${APP_VERSION}-signed.apk ~/project/bin/

echo "=== Готово ==="
ls -lh bin/lerdonlegends-${APP_VERSION}-signed.apk
