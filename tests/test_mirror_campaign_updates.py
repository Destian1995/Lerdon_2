import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from test_otherworlds import fixture
import test_soul_pact as soul_cases
import test_morgana_covenant as morgana_cases
import otherworlds as worlds
import mirror_monster_quest as hunt
import morgana_covenant as morgana


class MirrorCampaignUpdateTests(unittest.TestCase):
    def test_any_valid_city_costs_one_action_even_without_road(self):
        db=fixture();self.addCleanup(db.close)
        party=worlds.enter(db,'Север','Home')
        destinations=[r[0] for r in db.execute('SELECT id FROM portal_cities WHERE id<>1')]
        target=next(i for i in destinations if not db.execute('SELECT 1 FROM portal_roads WHERE city1=1 AND city2=?',(i,)).fetchone())
        before=db.execute("SELECT moves_left FROM turn_check_move WHERE faction='Север'").fetchone()[0]
        worlds.travel(db,'Север',target)
        self.assertEqual(worlds.party(db,'Север')['city_id'],target)
        self.assertEqual(db.execute("SELECT moves_left FROM turn_check_move WHERE faction='Север'").fetchone()[0],before-1)
        with self.assertRaises(ValueError):worlds.travel(db,'Север',999)
        with self.assertRaises(ValueError):worlds.travel(db,'Север',target)
        self.assertEqual(db.execute("SELECT moves_left FROM turn_check_move WHERE faction='Север'").fetchone()[0],before-1)

    def test_gender_updates_title_name_links_portrait_and_preserves_deadline(self):
        seed=soul_cases.SoulPactTests();seed.setUp();self.addCleanup(seed.doCleanups);db=seed.db
        case=hunt.state(db,'Север');story=json.loads(case['scenario'])
        story['nobles'][story['culprit']]['name']='Барон Ренар'
        # Use an Adept title for a deterministic Baron -> Baroness regression.
        db.execute("UPDATE portal_monster_cases SET faction='Адепты',scenario=? WHERE id=?",(json.dumps(story,ensure_ascii=False),case['id']))
        db.execute("UPDATE portal_parties SET faction='Адепты'")
        db.execute("UPDATE units SET faction='Адепты' WHERE unit_name='Hero'")
        prize=hunt.sell_soul(db,'Адепты','Hero')
        db.execute('CREATE TABLE test_gear(unit_name TEXT,artifact_id INTEGER)')
        db.execute('INSERT INTO test_gear VALUES(?,42)',(prize['name'],))
        deadline=hunt.pact(db,'Адепты')['deadline']
        female=hunt.choose_gender(db,'Адепты','lady')
        self.assertIn('Баронесса Аделина',female['name'])
        self.assertNotEqual(prize['name'],female['name'])
        self.assertIn('noble-lady',female['image'])
        self.assertEqual(db.execute('SELECT unit_name FROM test_gear').fetchone()[0],female['name'])
        self.assertEqual(hunt.state(db,'Адепты')['reward_unit'],female['name'])
        self.assertEqual(hunt.companion_form(db,'Адепты')['unit_name'],female['name'])
        self.assertEqual(hunt.pact(db,'Адепты')['deadline'],deadline)
        male=hunt.choose_gender(db,'Адепты','lord')
        self.assertEqual(male['name'],prize['name'])
        self.assertEqual((male['attack'],male['defense']),(prize['attack'],prize['defense']))

    def test_completed_quest_unlocks_direct_morgana_soul_sale_with_new_deadline(self):
        seed=morgana_cases.MorganaCovenantTests();seed.setUp();self.addCleanup(seed.doCleanups);db=seed.db
        db.execute('DELETE FROM portal_soul_pacts');db.execute('DELETE FROM portal_heart_contracts');db.execute('DELETE FROM portal_companion_forms')
        db.execute('UPDATE portal_monster_cases SET stage=2')
        self.assertIsNone(morgana.offer(db,'Север'))
        db.execute('UPDATE portal_parties SET city_id=1');worlds.return_home(db,'Север')
        self.assertIsNone(morgana.offer(db,'Север'))
        db.execute('UPDATE portal_monster_cases SET stage=3')
        db.execute('UPDATE turn SET turn_count=9')
        self.assertEqual(morgana.offer(db,'Север')['status'],'offered')
        morgana.accept(db,'Север')
        self.assertEqual(hunt.pact(db,'Север'),dict(case_id=0,signed_turn=9,deadline=24))
        self.assertTrue(morgana.serving(db,'Север'))
        db.execute('UPDATE turn SET turn_count=24')
        self.assertIn('Моргана',hunt.soul_loss_reason(db,'Север'))

    def test_failed_return_does_not_unlock_soul_sale(self):
        db=fixture();self.addCleanup(db.close)
        worlds.enter(db,'Север','Home')
        db.execute('UPDATE portal_parties SET city_id=2')
        with self.assertRaises(ValueError):worlds.return_home(db,'Север')
        self.assertFalse(morgana.returned_from_mirror(db,'Север'))

    def test_legacy_return_without_history_is_recognized_from_personal_quest(self):
        seed=soul_cases.SoulPactTests();seed.setUp();self.addCleanup(seed.doCleanups);db=seed.db
        db.execute('UPDATE portal_parties SET city_id=1');worlds.return_home(db,'Север')
        db.execute('DELETE FROM portal_return_history')
        self.assertTrue(morgana.returned_from_mirror(db,'Север'))
        self.assertIsNone(hunt.pact(db,'Север'))


if __name__=='__main__':unittest.main()
