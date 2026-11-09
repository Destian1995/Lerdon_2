"""Ordinary faction troops use their own attack and five-round cooldowns."""
import ast
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
from test_tactical_combat import unit
from tactical_combat import TacticalBattle
from tactical_abilities import TROOPS,ABILITIES,troop_abilities
import morgana_covenant as covenant


def field(name,kind='infantry',faction=''):
 m=TacticalBattle([unit(name,100,kind,initiative=100),unit('Союзники',100,kind,initiative=10)],
                  [unit('Враг',10000,initiative=50),unit('Другой враг',10000,initiative=40)],
                  terrain={(x,y):'plain' for x in range(10) for y in range(6)},factions=(faction,''))
 a,g,b,c=list(m.stacks.values());a.pos=(1,2);g.pos=(1,0);b.pos=(5,2);c.pos=(5,3)
 return m,a,g,b,c

class TroopAbilityTests(unittest.TestCase):
 def test_all_faction_troops_and_image_aliases_have_five_round_skills(self):
  for key,(images,names) in TROOPS.items():
   for name in names:self.assertIn(key,troop_abilities({'unit_name':name}))
   for path in images:self.assertIn(key,troop_abilities({'unit_image':'files/army/'+path}))
   self.assertEqual(ABILITIES[key].cooldown,5)
   m,a,*_=field(names[0]);self.assertEqual(m.skills(),(key,))

 def test_paladin_defense_grows_ninety_percent_until_next_activation(self):
  m,a,g,b,c=field('Паладин');before=m._power(a,False)
  m.use_ability('paladin_shield',a.pos)
  self.assertAlmostEqual(m._power(a,False),before*1.9)
  self.assertEqual(a.cooldowns['paladin_shield'],6)
  m.queue.insert(0,a.id);m._activate()
  self.assertNotIn('paladin_shield',a.effects)
  self.assertEqual(m._power(a,False),before)
  m.round=5;self.assertFalse(m.ability_valid('paladin_shield',a.pos,a))
  m.round=6;self.assertTrue(m.ability_valid('paladin_shield',a.pos,a))

 def test_priest_shield_reduces_normal_and_periodic_damage_by_forty_five_percent(self):
  m,a,g,b,c=field('Жрица','mage');m.use_ability('priest_shield',a.pos)
  old=a.hp;hit=m._hurt(a,100,b.id)
  self.assertAlmostEqual(hit['damage'],55);self.assertAlmostEqual(a.hp,old-55)
  m.queue.insert(0,a.id);m._activate();self.assertNotIn('priest_shield',a.effects)
  self.assertEqual(m._hurt(a,100,b.id)['damage'],100)

 def test_northern_burst_hits_only_enemies_in_area_for_115_percent(self):
  m,a,g,b,c=field('Охотник','archer');g.pos=(6,2)
  expected={t.id:m._damage(a,t)*1.15 for t in (b,c)};old={t.id:t.hp for t in (g,b,c)}
  event=m.use_ability('auto_burst',b.pos)
  for t in (b,c):self.assertAlmostEqual(old[t.id]-t.hp,expected[t.id])
  self.assertEqual(g.hp,old[g.id]);self.assertEqual(len(event['strikes']),6)
  self.assertEqual(sum(hit['volley_lead'] for hit in event['strikes']),3)

 def test_elf_double_arrow_is_two_hits_with_145_percent_total_damage(self):
  m,a,g,b,c=field('Лучница','archer');old=b.hp;expected=m._damage(a,b)*1.45
  event=m.use_ability('twin_arrow',b.pos)
  self.assertEqual(len(event['strikes']),2);self.assertAlmostEqual(old-b.hp,expected)
  self.assertEqual(event['strikes'][0]['shot'],0);self.assertEqual(event['strikes'][1]['shot'],1)

 def test_vortex_moves_and_hits_only_enemies_exactly_five_times(self):
  m,a,g,b,c=field('Маг крови','mage','Элины');g.pos=(5,1)
  old=b.hp;friendly=g.hp;power=m._power(a,True)*a.count*1.05
  event=m.use_ability('blood_vortex',b.pos)
  self.assertAlmostEqual(old-b.hp,power/m._resistance(b));self.assertEqual(g.hp,friendly)
  self.assertEqual(len(m.vortices),1);self.assertEqual(m.vortices[0]['remaining'],4)
  b.pos=(8,4);c.pos=(8,5)
  previous=m.vortices[0]['pos'];m._new_round()
  self.assertNotEqual(m.vortices[0]['pos'],previous)
  for _ in range(3):m._new_round()
  self.assertEqual(m.vortices,[]);self.assertEqual(g.hp,friendly)
  status=[e for e in m.events if e.get('ability')=='blood_vortex' and e['action']=='status']
  self.assertEqual(len(status),4)
  self.assertTrue(all(m.stacks[hit['target']].side=='defender' for e in status for hit in e['strikes']))

 def test_vampire_strike_restores_a_quarter_of_fallen_soldiers_including_dead_stack(self):
  m,a,g,b,c=field('Вестник смерти','beast','Вампиры');b.pos=(2,2)
  a.count=60;a.hp=60*a.health_per_unit
  g.count=0;g.hp=0
  event=m.use_ability('vampire_raise',b.pos)
  self.assertEqual(a.count,70);self.assertEqual(g.count,25)
  self.assertEqual(sum(r['count'] for r in event['restored']),35)
  self.assertLess(b.hp,b.max_hp)
  self.assertLessEqual(a.hp,a.max_hp);self.assertLessEqual(g.hp,g.max_hp)

 def test_vampire_resurrection_skips_occupied_graves_and_other_troop_types(self):
  m,a,g,b,c=field('Вестник смерти','beast','Вампиры');b.pos=(2,2)
  g.count=0;g.hp=0;c.pos=g.pos
  event=m.use_ability('vampire_raise',b.pos)
  self.assertEqual(g.count,0);self.assertFalse(event['restored'])

 def test_ai_uses_all_new_troop_abilities(self):
  cases=(('Паладин','infantry','paladin_shield'),('Жрица','mage','priest_shield'),
         ('Охотник','archer','auto_burst'),('Лучница','archer','twin_arrow'),('Маг крови','mage','blood_vortex'),
         ('Вестник смерти','beast','vampire_raise'))
  for name,kind,key in cases:
   m,a,g,b,c=field(name,kind)
   if key=='vampire_raise':b.pos=(2,2);g.hp*=.5;g.count=50
   self.assertEqual(m.ai_step().get('ability'),key)


def extracted(file,cls,name):
 tree=ast.parse(Path(file).read_text(encoding='utf-8'));node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
 fn=next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name==name)
 namespace={};exec(compile(ast.Module(body=[fn],type_ignores=[]),file,'exec'),namespace);return namespace[name]

class UndeadPeaceOfferTests(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
  self.db.executescript('''CREATE TABLE morgana_covenants(faction,status,offered_turn,accepted_turn,notified);
   INSERT INTO morgana_covenants VALUES('Север','accepted',0,0,1);
   CREATE TABLE negotiation_history(faction1,faction2,message,is_player,is_incoming,timestamp);''')

 def test_ai_writer_drops_peace_but_preserves_war_messages_and_ordinary_diplomacy(self):
  fn=extracted('ii.py','AIController','_create_message_in_negotiation_history')
  ai=SimpleNamespace(db_connection=self.db)
  for player in ('Север','Нежить'):fn(ai,'Элины',player,'[ПОЩАДА] Мы готовы заключить мир.')
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM negotiation_history').fetchone()[0],0)
  fn(ai,'Элины','Север','[ВОЙНА] Мы будем сражаться!')
  fn(ai,'Элины','Эльфы','Предлагаем мир.')
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM negotiation_history').fetchone()[0],2)
  self.assertFalse(covenant.blocked_peace_message(self.db,'Элины','Север','Вы служите Моргане. Мир невозможен.'))

 def test_mercy_generator_stops_before_creating_a_message(self):
  fn=extracted('ii.py','AIController','send_mercy_request_if_needed')
  ai=SimpleNamespace(db_connection=self.db,faction='Элины',_get_player_faction_name=lambda:'Север',get_city_count_for_faction=Mock())
  fn(ai);ai.get_city_count_for_faction.assert_not_called()

if __name__=='__main__':unittest.main()
