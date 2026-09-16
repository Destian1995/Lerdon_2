import sqlite3
import threading

class DBManager:
    _instance = None

    def __new__(cls, db_path=None):
        if cls._instance is None:
            cls._instance = super(DBManager, cls).__new__(cls)
            cls._instance.db_path = db_path
            cls._instance.conn = sqlite3.connect(db_path, check_same_thread=False)
            cls._instance._apply_pragmas(cls._instance.conn)
            cls._instance._ensure_indexes()
            cls._instance._lock = threading.Lock()
        return cls._instance

    @staticmethod
    def _apply_pragmas(conn):
        """Применяет оптимизирующие PRAGMA к соединению."""
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA cache_size=-8000;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA mmap_size=67108864;")

    def create_thread_connection(self):
        """Создаёт отдельное соединение для фонового потока."""
        conn = sqlite3.connect(self._instance.db_path, check_same_thread=False)
        self._apply_pragmas(conn)
        return conn

    def _ensure_indexes(self):
        """Создаёт индексы для ускорения частых запросов"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_garrisons_city ON garrisons(city_name)",
            "CREATE INDEX IF NOT EXISTS idx_garrisons_unit ON garrisons(city_name, unit_name)",
            "CREATE INDEX IF NOT EXISTS idx_units_name ON units(unit_name)",
            "CREATE INDEX IF NOT EXISTS idx_units_faction ON units(faction)",
            "CREATE INDEX IF NOT EXISTS idx_units_faction_class ON units(faction, unit_class)",
            "CREATE INDEX IF NOT EXISTS idx_units_default_name ON units_default(unit_name)",
            "CREATE INDEX IF NOT EXISTS idx_cities_faction ON cities(faction)",
            "CREATE INDEX IF NOT EXISTS idx_cities_name ON cities(name)",
            "CREATE INDEX IF NOT EXISTS idx_buildings_city ON buildings(city_name)",
            "CREATE INDEX IF NOT EXISTS idx_buildings_faction ON buildings(faction)",
            "CREATE INDEX IF NOT EXISTS idx_buildings_city_faction ON buildings(city_name, faction, building_type)",
            "CREATE INDEX IF NOT EXISTS idx_roads_cities ON roads(city1, city2)",
            "CREATE INDEX IF NOT EXISTS idx_relations_factions ON relations(faction1, faction2)",
            "CREATE INDEX IF NOT EXISTS idx_hero_equipment_hero ON hero_equipment(hero_name)",
            "CREATE INDEX IF NOT EXISTS idx_ai_hero_equipment_hero ON ai_hero_equipment(faction_name, hero_name)",
            "CREATE INDEX IF NOT EXISTS idx_artifact_effects_hero ON artifact_effects_log(hero_name, artifact_id)",
            "CREATE INDEX IF NOT EXISTS idx_negotiation_history ON negotiation_history(faction2, is_player)",
        ]
        for idx_sql in indexes:
            try:
                self._instance.conn.execute(idx_sql)
            except Exception:
                pass
        self._instance.conn.commit()

    def get_connection(self):
        return self._instance.conn

    def close_all(self):
        if self._instance.conn:
            self._instance.conn.execute("PRAGMA wal_checkpoint(FULL);")
            self._instance.conn.execute("PRAGMA journal_mode=DELETE;")
            self._instance.conn.close()