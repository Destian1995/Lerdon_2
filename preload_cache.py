"""
Предзагрузка текстур при старте игры.
Загружает порциями через Clock.schedule_once чтобы не блокировать UI.
"""
import os

_preloaded = False
_texture_paths = []


def collect_paths(conn):
    """Собирает все пути изображений для предзагрузки."""
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

    # 4) Изображения армий
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

    # 6) Портреты юнитов по фракциям
    for d in ['adepts', 'elfs', 'people', 'vampires', 'poly', 'death', 'rebellion']:
        army_dir = f'files/army/{d}'
        if os.path.exists(army_dir):
            for f in os.listdir(army_dir):
                if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                    paths.add(os.path.join(army_dir, f))

    return [p for p in paths if os.path.exists(p)]


def start_preload(conn, on_progress=None, on_done=None):
    """Запускает предзагрузку текстур порциями через Clock (не блокирует UI)."""
    global _preloaded, _texture_paths
    if _preloaded:
        if on_done:
            on_done()
        return

    from kivy.clock import Clock
    from kivy.core.image import Image as CoreImage

    _texture_paths = collect_paths(conn)
    total = len(_texture_paths)
    batch_size = 5  # по 5 текстур за кадр
    idx = [0]
    loaded = [0]

    def _load_batch(dt):
        end = min(idx[0] + batch_size, total)
        for i in range(idx[0], end):
            try:
                CoreImage(_texture_paths[i])
                loaded[0] += 1
            except Exception:
                pass
        idx[0] = end

        if on_progress and total > 0:
            on_progress(idx[0], total)

        if idx[0] < total:
            Clock.schedule_once(_load_batch, 0)
        else:
            _preloaded = True
            print(f"[CACHE] Предзагружено {loaded[0]}/{total} текстур")
            if on_done:
                on_done()

    Clock.schedule_once(_load_batch, 0)
