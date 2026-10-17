from lerdon_libraries import *
# ==========================
# 1. Определяем путь к папке “файлов” (storage) на Android
# ==========================
if platform == 'android':
    from android.storage import app_storage_path
    # модуль android.storage даёт гарантированный путь к директории /data/data/<package>/files/
    try:
        storage_dir = app_storage_path()
    except ImportError:
        # На старых версиях p4a этот модуль может отсутствовать,
        # в таком случае fallback на os.getcwd(), но с осторожностью:
        storage_dir = os.getcwd()
else:
    # На десктопе (разработка) просто каталог с этим скриптом
    storage_dir = os.path.dirname(__file__)

# ==========================
# 2. Пути к файлам базы
# ==========================
# Поскольку мы переместили game_data.db в assets/, при установке APK
# Kivy помещает его внутрь /assets/game_data.db. Чтобы получить путь до
# “упакованного” asset-файла, используем resource_find.

# resource_find вернёт путь вида:
#   - при запуске на настольной ОС: абсолютный путь ../assets/game_data.db
#   - при запуске внутри APK: путь вида '/data/app/.../base.apk/assets/game_data.db'
original_asset_path = resource_find('game_data.db')
# Если по какой-то причине resource_find вернул None — база не упакована
if original_asset_path is None:
    raise FileNotFoundError("❌ Couldn't find game_data.db in assets. Check the source.include_patterns and assets folder/.")

# Путь, куда будем копировать базу для фактической работы:
copied_db = os.path.join(storage_dir, 'game_data.db')

# ==========================
# 3. Копируем базу при первом запуске или при обновлении
# ==========================
# Проверяем нужно ли обновить БД: сравниваем версию в assets и в storage
_need_copy = False
if not os.path.exists(copied_db):
    _need_copy = True
else:
    # Проверяем версию: если assets-БД новее — перекопируем default-таблицы
    try:
        import sqlite3 as _sq
        _src = _sq.connect(original_asset_path)
        _dst = _sq.connect(copied_db)
        # Сравниваем структуру units_default (наличие новых колонок/данных)
        _src_cols = {r[1] for r in _src.execute("PRAGMA table_info(units)").fetchall()}
        _dst_cols = {r[1] for r in _dst.execute("PRAGMA table_info(units)").fetchall()}
        if _src_cols != _dst_cols:
            _need_copy = True
        else:
            # Сравниваем unit_type из units_default — если отличается, обновляем
            try:
                _src_types = set(_src.execute("SELECT unit_name, unit_type FROM units_default").fetchall())
                _dst_types = set(_dst.execute("SELECT unit_name, unit_type FROM units_default").fetchall())
                if _src_types != _dst_types:
                    # Обновляем только default-таблицы, не трогая прогресс игрока
                    _tables_to_refresh = [
                        ("units_default", "units_default"),
                        ("units", "units"),
                    ]
                    for _tbl in _tables_to_refresh:
                        try:
                            _dst.execute(f"DELETE FROM {_tbl[0]}")
                            for row in _src.execute(f"SELECT * FROM {_tbl[0]}").fetchall():
                                _placeholders = ','.join('?' * len(row))
                                _dst.execute(f"INSERT INTO {_tbl[0]} VALUES ({_placeholders})", row)
                        except Exception:
                            pass
                    _dst.commit()
                    print("✅ Default tables refreshed from assets")
            except Exception:
                pass
        _src.close()
        _dst.close()
    except Exception as _e:
        print(f"[WARN] DB version check: {_e}")

if _need_copy:
    try:
        shutil.copyfile(original_asset_path, copied_db)
        print(f"✅ Database copying success: {copied_db}")
    except Exception as e:
        raise RuntimeError(f"❌ Database copying error: {e}")

# ==========================
# 4. Задаём глобальный db_path
# ==========================
# В дальнейшем остальные модули (например, ваши DAO/ORM или SQL-запросы)
# могут просто импортировать db_path из этого файла
db_path = copied_db
