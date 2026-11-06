import sqlite3
import unittest
from pathlib import Path
from artifact_image_updates import ICON_RENAMES,migrate_artifact_image_paths


class ArtifactImageUpdateTests(unittest.TestCase):
    def test_saved_items_equipment_and_previous_slots_keep_all_gameplay_data(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.executescript('CREATE TABLE artifacts(id,attack,defense,image_url);'
                         'CREATE TABLE hero_equipment(artifact_id,image_url);'
                         'CREATE TABLE portal_timed_items(artifact_id,expires_turn,previous_image);')
        for i,(old,new) in enumerate(ICON_RENAMES.items()):
            image='files/pict/artifacts/custom/'+old
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(i,100+i,200+i,image))
            db.execute('INSERT INTO hero_equipment VALUES(?,?)',(i,image.replace('/','\\')))
            db.execute('INSERT INTO portal_timed_items VALUES(?,?,?)',(i,25+i,image))
            self.assertTrue(Path('files/pict/artifacts/custom/'+new).is_file())
        before=list(db.execute('SELECT id,attack,defense FROM artifacts'))
        self.assertEqual(migrate_artifact_image_paths(db),9)
        for i,new in enumerate(ICON_RENAMES.values()):
            image='files/pict/artifacts/custom/'+new
            self.assertEqual(db.execute('SELECT image_url FROM artifacts WHERE id=?',(i,)).fetchone()[0],image)
            self.assertEqual(db.execute('SELECT image_url FROM hero_equipment WHERE artifact_id=?',(i,)).fetchone()[0],image)
            self.assertEqual(db.execute('SELECT expires_turn,previous_image FROM portal_timed_items WHERE artifact_id=?',(i,)).fetchone(),(25+i,image))
        self.assertEqual(list(db.execute('SELECT id,attack,defense FROM artifacts')),before)
        self.assertEqual(migrate_artifact_image_paths(db),0)

    def test_empty_or_partial_schema_is_safe(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.execute('CREATE TABLE artifacts(id)')
        self.assertEqual(migrate_artifact_image_paths(db),0)
