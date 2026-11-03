import random
import unittest
from pathlib import Path

from test_monster_sites import fixture
from monster_sites import art_path,monster_name,sites,ensure_schema,VARIANT_NAMES,reward


class VariantTests(unittest.TestCase):
    def test_35_distinct_saved_assets_and_names(self):
        paths=[];names=[]
        for tier in range(1,8):
            self.assertEqual(len(VARIANT_NAMES[tier-1]),5)
            for variant in range(1,6):
                path=art_path(tier,variant)
                self.assertTrue(path.is_file(),path)
                paths.append(path)
                names.append(monster_name(dict(tier=tier,variant=variant)))
        self.assertEqual(len(set(paths)),35)
        self.assertEqual(len(set(names)),35)

    def test_existing_campaign_keeps_its_original_art_and_rewards(self):
        db=fixture();self.addCleanup(db.close)
        db.execute('ALTER TABLE monster_sites DROP COLUMN variant')
        original=sites(db)
        self.assertTrue(all(s['variant']==1 for s in original))
        ensure_schema(db);ensure_schema(db)
        self.assertEqual(sites(db),original)
        for site in sites(db):
            tier=site['tier']
            self.assertEqual(art_path(tier).name,f'monster_{tier}.png')
            self.assertEqual(reward(tier)['defense'],90_000_000+(tier-1)*25_000_000)

    def test_variant_survives_reload_without_moving_lair_or_resetting_respawn(self):
        import sqlite3
        db=fixture();self.addCleanup(db.close)
        db.execute('UPDATE monster_sites SET variant=5,ready_turn=12,defeats=2 WHERE id=7')
        before=sites(db)
        loaded=sqlite3.connect(':memory:');self.addCleanup(loaded.close)
        loaded.executescript('\n'.join(db.iterdump()))
        ensure_schema(loaded)
        self.assertEqual(sites(loaded),before)
        self.assertEqual(monster_name(sites(loaded)[-1]),'Падший серафим')


if __name__=='__main__':unittest.main()
