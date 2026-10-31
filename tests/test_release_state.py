import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from release_state import reset_android_release
from tools.prepare_release_data import prepare
from contextlib import closing


class ReleaseStateTests(unittest.TestCase):
    def test_reset_replaces_old_data_and_icon_cache_only_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = root / 'packaged.db'
            asset.write_bytes(b'clean-database')
            storage = root / 'storage'
            storage.mkdir()
            database = storage / 'game_data.db'
            database.write_bytes(b'old-game')
            cached = storage / 'artifact_icon_cache'
            cached.mkdir()
            (cached / 'old.png').write_bytes(b'old')
            self.assertTrue(reset_android_release(storage, asset))
            self.assertEqual(database.read_bytes(), b'clean-database')
            self.assertFalse(cached.exists())
            database.write_bytes(b'new-campaign')
            self.assertFalse(reset_android_release(storage, asset))
            self.assertEqual(database.read_bytes(), b'new-campaign')

    def test_release_database_cleans_campaign_and_preserves_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'source.db', Path(directory) / 'clean.db'
            with closing(sqlite3.connect(source)) as db:
                db.executescript('CREATE TABLE cities(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);'
                                 'CREATE TABLE dossier(value INTEGER); CREATE TABLE units_default(name TEXT);'
                                 'CREATE TABLE units(name TEXT); CREATE TABLE events(name TEXT);'
                                 "INSERT INTO cities(name) VALUES ('old'); INSERT INTO dossier VALUES (99);"
                                 "INSERT INTO units_default VALUES ('base'); INSERT INTO units VALUES ('changed');"
                                 "INSERT INTO events VALUES ('reference-event');")
            counts = prepare(source, target)
            self.assertEqual(counts['cities'], 0)
            self.assertEqual(counts['dossier'], 0)
            self.assertEqual(counts['units_default'], 1)
            self.assertEqual(counts['units'], 1)
            self.assertEqual(counts['events'], 1)
            with closing(sqlite3.connect(source)) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM cities').fetchone()[0], 1)
