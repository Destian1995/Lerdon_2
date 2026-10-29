"""
Предзагрузка текстур при старте игры.
Kivy кеширует текстуры глобально — после CoreImage(path) любой
Image(source=path) использует кеш автоматически.
"""
import os

_preloaded = False


def preload_textures(conn):
    """Загружает все изображения в текстурный кеш Kivy. Вызывать из главного потока."""
    global _preloaded
    if _preloaded:
        return 0

    from kivy.core.image import Image as CoreImage

    paths = set()

    # 1) Иконки артефактов (мастерская)
    custom_dir = 'files/pict/artifacts/custom'
    if os.path.exists(custom_dir):
        for f in os.listdir(custom_dir):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                paths.add(os.path.join(custom_dir, f))

    # 2) Изображения артефактов из БД (лавка)
    try:
        cur = conn.cursor()
        cur.execute("SELECT image_url FROM artifacts WHERE image_url IS NOT NULL")
        for row in cur.fetchall():
            if row[0]:
                paths.add(row[0])
        cur.execute("SELECT image_url FROM artifacts_default WHERE image_url IS NOT NULL")
        for row in cur.fetchall():
            if row[0]:
                paths.add(row[0])
    except Exception:
        pass

    # 3) Изображения юнитов из БД (найм)
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT unit_image FROM units WHERE unit_image IS NOT NULL")
        for row in cur.fetchall():
            if row[0]:
                paths.add(row[0])
    except Exception:
        pass

    # 4) Изображения героев
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT image FROM armies WHERE image IS NOT NULL")
        for row in cur.fetchall():
            if row[0]:
                paths.add(row[0])
    except Exception:
        pass

    # 5) UI иконки
    for p in [
        'files/pict/hire/sword.png', 'files/pict/hire/shield.png',
        'files/pict/hire/health.png', 'files/pict/hire/class.png',
        'files/pict/hire/consumption.png', 'files/pict/hire/strong.png',
        'files/pict/hire/weak.png', 'files/pict/hire/type.png',
        'files/pict/hire/moral.png',
        'files/pict/right.png', 'files/pict/close.png',
        'files/pict/up.png', 'files/pict/down.png',
        'files/pict/question.png',
    ]:
        paths.add(p)

    # 6) Фоновые изображения фракций
    for d in ['adepts', 'elfs', 'people', 'vampires', 'poly', 'death', 'rebellion']:
        army_dir = f'files/army/{d}'
        if os.path.exists(army_dir):
            for f in os.listdir(army_dir):
                if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                    paths.add(os.path.join(army_dir, f))

    loaded = 0
    for p in paths:
        try:
            if os.path.exists(p):
                CoreImage(p)
                loaded += 1
        except Exception:
            pass

    _preloaded = True
    print(f"[CACHE] Предзагружено {loaded}/{len(paths)} текстур")
    return loaded
