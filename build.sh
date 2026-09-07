APP_VERSION="6.0.0"

# Обновляем код (без clean — сохраняем скачанные пакеты)
git pull
rm -rf bin

# Сборка (используем кеш скачанных зависимостей)
buildozer android release

cd ~/Lerdon_2/bin
ANDROID_BUILD_TOOLS="$HOME/.buildozer/android/platform/android-sdk/build-tools/36.0.0"

# 1) Zipalign нового мульти-ABI unsigned-APK
$ANDROID_BUILD_TOOLS/zipalign -v -p 4 \
    lerdonlegends-${APP_VERSION}-arm64-v8a_armeabi-v7a-release-unsigned.apk \
    lerdonlegends-${APP_VERSION}-multiabi-release-aligned.apk

# 2) Apksigner нового aligned-APK
$ANDROID_BUILD_TOOLS/apksigner sign \
    --ks ../signkey.keystore \
    --ks-key-alias lerdon-release \
    --ks-pass pass:Lerdon \
    --key-pass pass:Lerdon \
    --out lerdonlegends-${APP_VERSION}-multiabi-release-signed.apk \
    lerdonlegends-${APP_VERSION}-multiabi-release-aligned.apk

cd ../
cp -rf bin ~/project
ls -l bin
