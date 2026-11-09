"""Twenty-turn heart curse, completed-quest offer and paid deferred allegiance."""
import sqlite3
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import ast
from pathlib import Path
import test_soul_pact as seeds
import test_morgana_covenant as morgana_seeds
import mirror_monster_quest as hunt
import heart_contract as heart
import morgana_covenant as morgana
from campaign_endings import epilogue

class HeartContractTests(unittest.TestCase):
 def seed(self,undead=False):
  seed=morgana_seeds.MorganaCovenantTests() if undead else seeds.SoulPactTests()
  seed.setUp();self.addCleanup(seed.doCleanups);return seed.db

 def test_heart_deadline_and_persistent_army_curse_without_campaign_defeat(self):
  db=self.seed();hunt.claim_heart(db,'Север','Hero')
  self.assertEqual(heart.state(db,'Север')['deadline'],20);self.assertIsNone(hunt.soul_pact(db,'Север'))
  db.execute('UPDATE turn SET turn_count=19');self.assertFalse(heart.expire(db,'Север'))
  db.execute('UPDATE turn SET turn_count=20');self.assertTrue(heart.expire(db,'Север'))
  self.assertFalse(heart.expire(db,'Север'));self.assertEqual(heart.multiplier(db,'Север'),.5)
  self.assertFalse(hunt.soul_loss_reason(db,'Север'))
  db.execute('UPDATE turn SET turn_count=100');self.assertEqual(heart.multiplier(db,'Север'),.5)
  db.commit();copy=sqlite3.connect(':memory:');self.addCleanup(copy.close);db.backup(copy)
  self.assertEqual(heart.multiplier(copy,'Север'),.5)
  hero=dict(unit_name='Hero',units_stats={'Урон':100,'Защита':200,'Живучесть':40,'Инициатива':80,'Мораль':100,'Крит':10})
  soldier=db.execute("SELECT unit_name FROM units WHERE faction='Север' AND CAST(unit_class AS INTEGER)=1 LIMIT 1").fetchone()[0]
  army=[hero,dict(unit_name=soldier,units_stats=dict(hero['units_stats']))]
  heart.apply_to_army(copy,army);heart.apply_to_army(copy,army)
  for unit in army:self.assertEqual(unit['units_stats'],dict(zip(heart.CURSED_STATS,(50,100,20,40,50,5))))
  self.assertEqual(heart.multiplier(copy,'Эльфы'),1)

 def test_legacy_noble_pact_migrates_once_and_keeps_companion(self):
  db=self.seed();prize=hunt.claim_heart(db,'Север','Hero')
  db.execute('DELETE FROM portal_heart_contracts')
  db.execute("INSERT INTO portal_soul_pacts VALUES('Север',1,3,33)")
  hunt.ensure_schema(db);hunt.ensure_schema(db)
  self.assertEqual(heart.state(db,'Север')['deadline'],23)
  self.assertIsNone(hunt.soul_pact(db,'Север'))
  self.assertEqual(hunt.companion_form(db,'Север')['unit_name'],prize['name'])

 def test_only_completed_quests_unlock_morgana(self):
  db=self.seed(undead=True)
  db.execute('UPDATE portal_monster_cases SET stage=2')
  self.assertIsNone(morgana.offer(db,'Север'))
  db.execute('CREATE TABLE IF NOT EXISTS portal_quest_runs(faction,detective,war)')
  db.execute("INSERT INTO portal_quest_runs VALUES('Север',2,0)")
  self.assertIsNone(morgana.offer(db,'Север'))
  db.execute('UPDATE portal_quest_runs SET detective=3')
  self.assertEqual(morgana.offer(db,'Север')['status'],'offered')

 def test_morgana_grants_fresh_fifteen_turns_and_releases_unexpired_heart(self):
  db=self.seed(undead=True);db.execute('UPDATE turn SET turn_count=18')
  morgana.accept(db,'Север')
  self.assertEqual(hunt.soul_pact(db,'Север'),dict(case_id=0,signed_turn=18,deadline=33))
  self.assertTrue(heart.state(db,'Север')['released'])
  db.execute('UPDATE turn SET turn_count=32');heart.expire(db,'Север')
  self.assertEqual(heart.multiplier(db,'Север'),1)
  self.assertIsNotNone(hunt.companion_form(db,'Север'))
  hunt.choose_gender(db,'Север','lady');hunt.set_form(db,'Север','monster')
  self.assertEqual(hunt.soul_pact(db,'Север')['deadline'],33)
  db.execute('UPDATE turn SET turn_count=33');self.assertIn('Моргана',hunt.soul_loss_reason(db,'Север'))
  self.assertIn('15 ходов',hunt.soul_loss_reason(db,'Север'))

 def test_morgana_does_not_remove_an_existing_curse(self):
  db=self.seed(undead=True);db.execute('UPDATE turn SET turn_count=25');heart.expire(db,'Север')
  morgana.accept(db,'Север');self.assertEqual(heart.multiplier(db,'Север'),.5)
  self.assertEqual(hunt.soul_pact(db,'Север')['deadline'],40)

 def test_deferral_fee_is_atomic_and_charged_once_only_when_accepting(self):
  db=self.seed(undead=True);morgana.offer(db,'Север')
  db.execute("UPDATE resources SET amount=1499999 WHERE faction='Север' AND resource_type='Кроны'")
  morgana.defer(db,'Север');morgana.defer(db,'Север')
  before=list(db.execute('SELECT * FROM cities'))
  with self.assertRaisesRegex(ValueError,'1,5 млн'):morgana.accept(db,'Север')
  self.assertEqual(morgana.state(db,'Север')['status'],'deferred')
  self.assertIsNone(hunt.soul_pact(db,'Север'));self.assertEqual(list(db.execute('SELECT * FROM cities')),before)
  db.execute("UPDATE resources SET amount=2000000 WHERE faction='Север' AND resource_type='Кроны'")
  morgana.accept(db,'Север')
  self.assertEqual(db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кроны'").fetchone()[0],500000)
  with self.assertRaises(ValueError):morgana.accept(db,'Север')
  self.assertEqual(db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кроны'").fetchone()[0],500000)

 def test_curse_matches_garrison_strength_and_both_combat_modes(self):
  import copy
  from utils.garrison_stats import garrison_profiles
  from tactical_combat import TacticalBattle
  import otherworlds as worlds
  db=self.seed();hunt.claim_heart(db,'Север','Hero')
  camp=worlds.party(db,'Север')['camp']
  before=garrison_profiles(db,camp,faction='Север')
  db.execute('UPDATE turn SET turn_count=20');heart.expire(db,'Север')
  after=garrison_profiles(db,camp,faction='Север')
  for name in before:
   for key in ('attack','defense'):self.assertAlmostEqual(after[name][key],before[name][key]*.5)
  seen=[]
  def manual(a,d,*args):
   seen.extend(copy.deepcopy(a));model=TacticalBattle(a,d)
   guard=next(s for s in model.stacks.values() if s.side=='defender')
   guard.count=0;guard.hp=0;model._check_end();model._snapshot();return model
  with patch.dict('sys.modules',{'fight':SimpleNamespace(TYPE_MOD={},_get_season_mult=lambda *args:1)}), patch('tactical_battle_bridge.request_battle',side_effect=manual):
   outcome=worlds.fight_guards(db,'Север',skirmish=lambda a,b,*args:(a,b),tactical=True)
  self.assertTrue(outcome['won'])
  for unit in seen:
   name=unit['unit_name']
   if str(unit['units_stats']['Класс юнита'])=='1':
    self.assertEqual(unit['_quick_combat_power'],(int(after[name]['attack']),int(after[name]['defense'])))
   else:
    original=db.execute('SELECT attack FROM units WHERE unit_name=?',(name,)).fetchone()[0]
    self.assertEqual(unit['units_stats']['Урон'],original*.5)

 def test_mirror_quick_fight_also_halves_initiative_crit_and_morale(self):
  import otherworlds as worlds
  db=self.seed();hunt.claim_heart(db,'Север','Hero')
  db.execute('UPDATE turn SET turn_count=20');heart.expire(db,'Север')
  seen=[]
  def quick(a,d,*args,**kwargs):
   seen.append(dict(a['units_stats']));d['unit_count']=0;return a,d
  outcome=worlds.fight_guards(db,'Север',skirmish=quick,encounter=hunt.monster(hunt.state(db,'Север')))
  self.assertTrue(outcome['won'])
  self.assertTrue(seen)
  for stats in seen:
   self.assertEqual(stats['Инициатива'],25);self.assertEqual(stats['Крит'],2.5);self.assertEqual(stats['Мораль'],50)

 def test_epilogues_distinguish_heart_curse_and_morganas_apocalypse(self):
  db=self.seed(undead=True)
  self.assertIn('сердце',epilogue(db,'Север','win','Все фракции были уничтожены')['story'])
  db.execute('UPDATE turn SET turn_count=25');heart.expire(db,'Север')
  self.assertIn('Проклятие сердца',epilogue(db,'Север','win','Все фракции были уничтожены')['story'])
  morgana.accept(db,'Север');ending=epilogue(db,'Север','win','Все фракции были уничтожены')
  self.assertEqual(ending['title'],'Всадник апокалипсиса Морганы')
  self.assertIn('Теперь мир служит вам. А вы — Моргане.',ending['story'])

if __name__=='__main__':unittest.main()
