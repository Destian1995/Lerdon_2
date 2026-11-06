"""All quest rewards have distinct packaged art; saved slots migrate safely."""
from pathlib import Path
import hashlib
import unittest
from PIL import Image
from test_otherworlds import fixture
import otherworlds as worlds
import portal_items as items
from otherworld_themes import THEMES,asset_exists


class QuestRewardArtTests(unittest.TestCase):
    def test_all_fifteen_images_are_distinct_transparent_and_packaged(self):
        db=fixture();self.addCleanup(db.close)
        paths=[];hashes=[]
        for faction in THEMES:
            for key in (101,102,103):
                path=items.reward(db,faction,key)['image_url'];paths.append(path)
                self.assertTrue(asset_exists(path),path)
                hashes.append(hashlib.sha256(Path(path).read_bytes()).hexdigest())
                with Image.open(path) as image:
                    self.assertEqual(image.mode,'RGBA')
                    self.assertEqual(image.size,(512,512))
                    self.assertEqual(image.getchannel('A').getextrema()[0],0)
                    self.assertIsNotNone(image.getchannel('A').getbbox())
        self.assertEqual(len(set(paths)),15)
        self.assertEqual(len(set(hashes)),15)

    def test_issued_items_equipment_and_nested_restore_keep_stats_and_deadlines(self):
        db=fixture();self.addCleanup(db.close);party=worlds.enter(db,'Север','Home')
        crown=items.issue(db,'Север',party['camp'],items.reward(db,'Север',101))
        weapon=items.issue(db,'Север',party['camp'],items.reward(db,'Север',102))
        db.execute("UPDATE artifacts SET name='Меч Альдара' WHERE id=?",(weapon,))
        cover=items.issue(db,'Север',party['camp'],items.offers(db,'Север')[1])
        for aid in (crown,weapon):db.execute("UPDATE artifacts SET image_url='old.png' WHERE id=?",(aid,))
        db.execute("UPDATE hero_equipment SET image_url='old.png' WHERE artifact_id=?",(weapon,))
        db.execute("UPDATE portal_timed_items SET previous_image='old.png' WHERE previous_id=?",(crown,))
        stats=list(db.execute('SELECT id,attack,defense FROM artifacts ORDER BY id'))
        deadlines=list(db.execute('SELECT artifact_id,issued_turn,expires_turn,previous_id FROM portal_timed_items ORDER BY artifact_id'))
        items.ensure_schema(db)
        self.assertEqual(db.execute('SELECT name FROM artifacts WHERE id=?',(weapon,)).fetchone()[0],'Винтовка Маркова')
        self.assertEqual(db.execute('SELECT image_url FROM artifacts WHERE id=?',(crown,)).fetchone()[0],items.reward_image('Север',101))
        self.assertEqual(db.execute('SELECT image_url FROM hero_equipment WHERE artifact_id=?',(weapon,)).fetchone()[0],items.reward_image('Север',102))
        self.assertEqual(db.execute('SELECT previous_image FROM portal_timed_items WHERE artifact_id=?',(cover,)).fetchone()[0],items.reward_image('Север',101))
        self.assertEqual(list(db.execute('SELECT id,attack,defense FROM artifacts ORDER BY id')),stats)
        self.assertEqual(list(db.execute('SELECT artifact_id,issued_turn,expires_turn,previous_id FROM portal_timed_items ORDER BY artifact_id')),deadlines)
        snapshot=list(db.iterdump());items.ensure_schema(db)
        self.assertEqual(list(db.iterdump()),snapshot)
        expiry=db.execute('SELECT expires_turn FROM portal_timed_items WHERE artifact_id=?',(cover,)).fetchone()[0]
        db.execute('UPDATE turn SET turn_count=?',(expiry,));items.expire(db)
        self.assertEqual(db.execute("SELECT artifact_id,image_url FROM hero_equipment WHERE slot_type='1'").fetchone(),(crown,items.reward_image('Север',101)))


if __name__=='__main__':unittest.main()
