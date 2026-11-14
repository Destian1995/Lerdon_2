[app]

# ---------------------------------
# Основные параметры приложения
# ---------------------------------

version = 9.5.15
title = Легенды Лэрдона
package.name = lerdonlegends
package.domain = com.lerdonlegends
source.main = main.py
source.dir = .
source.include_exts = py,png,jpg,ttf,mp3,wav,mp4,db,sqlite3,json,txt,atlas
source.include_patterns = files/*, ai_models/*, utils/*, *.py, game_data.db
source.exclude_dirs = old, .git, __pycache__, .idea, .claude, .buildozer, bin, tests, tools, server, android_billing, .release
source.exclude_patterns = buildozer.spec, developer_access.local.json*, *.log, *.pyc, lerdon.db, assets/frontend-*, assets/responsive-*, assets/unified-*, assets/strategy-*, assets/battle-*, assets/tutorial-guide-*, assets/*review*, assets/*manifest*, assets/mobile-redesign/*, assets/city-smoke-bursts*, assets/event-news-ribbon*, assets/faction-standards*, assets/hero-city-effects*, assets/troop-movement*, assets/mirror-sprites/*, assets/mirror-effect-prompts.json, assets/animated-units/*, assets/*sprite*.json, assets/tactical-*, assets/music/*
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/splash.png
description = Стратегическая игра Lerdon с элементами экономики и политики.
author = Vladislav Lerdon Team

# ---------------------------------
# Python / Kivy / зависимости
# ---------------------------------

requirements = python3==3.11.0, kivy==2.2.0, kivymd==1.1.1, pyjnius==1.5.0, cython==0.29.36, sdl2, sdl2_image, sdl2_mixer, sdl2_ttf, certifi

# Откатываем p4a на версию с Python 3.11 (2024.01.21)
p4a.branch = release-2024.01.21

# ---------------------------------
# Android / SDL2
# ---------------------------------

android.api = 35
android.minapi = 24
android.ndk = 25b
android.ndk_api = 21
android.sdk = 35
android.archs = arm64-v8a, armeabi-v7a
android.bundle = False
fullscreen = 1
android.permissions = INTERNET
orientation = landscape
log_level = 2

# Bootstrap SDL2
p4a.bootstrap = sdl2

# ---------------------------------
# Release / подпись
# ---------------------------------

android.release = True
android.release_artifact = apk
# Keep the legacy p4a prefix (10 + min API 21). Version 6.5.1 used 102160501.
# A short code such as 70000 is LOWER and cannot update the existing store app.
android.numeric_version = 102190518

# ---------------------------------
# Прочее
# ---------------------------------

buildozer.build_logfile = buildozer.log
android.add_gradle_properties = org.gradle.jvmargs=-Xmx6g
android.enable_androidx = True
android.gradle_dependencies = ru.yoomoney.sdk.kassa.payments:yookassa-android-sdk:8.6.0,com.yandex.android:mobileads:8.6.0
android.add_gradle_repositories = maven { url 'https://repo.yoomoney.ru/repository/android-libraries/' }, mavenCentral(), maven { url 'https://developer.huawei.com/repo/' }
android.add_src = android_billing/src
p4a.hook = android_billing/build_hook.py
