[app]

# ---------------------------------
# Основные параметры приложения
# ---------------------------------

version = 4.9.1
title = Легенды Лэрдона
package.name = lerdonlegends
package.domain = com.lerdonlegends
source.main = main.py
source.dir = .
source.include_exts = py,png,jpg,ttf,mp3,mp4,db,sqlite3,json,txt
source.include_patterns = assets/*, files/*, game_data.db, *.py
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/splash.png
description = Стратегическая игра Lerdon с элементами экономики и политики.
author = Vladislav Lerdon Team

# ---------------------------------
# Python / Kivy / зависимости
# ---------------------------------


requirements = python3==3.11.0, kivy==2.2.0, kivymd, pyjnius==1.5.0, cython==0.29.36, ffpyplayer, ffmpeg, sdl2, sdl2_image, sdl2_mixer, sdl2_ttf

# Для python-for-android (p4a)
p4a.python_version = 3.11.0

# ---------------------------------
# Android / SDL2 / Audio
# ---------------------------------

android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.sdk = 33
android.build_tools = 33.0.0
android.archs = arm64-v8a, armeabi-v7a
android.bundle = False
fullscreen = 1
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
log_level = 0

android.add_env = SDL_AUDIODRIVER=opensl, KIVY_AUDIO=ffpyplayer

# 💡 Иногда помогает явно включить старый bootstrap SDL2
p4a.bootstrap = sdl2

# ---------------------------------
# Release / подпись
# ---------------------------------

android.release = True
#android.release_signature = /home/vagrant/Lerdon/signkey.keystore|lerdon-release|mypassword|mypassword
android.release_artifact = apk

# ---------------------------------
# Прочее
# ---------------------------------

buildozer.build_logfile = buildozer.log
android.add_assets = files
orientation = landscape
