import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_terrain_journeys as journeys
from test_battle_ui import combat_namespace
from terrain_journeys import start_journey,waiting_armies,advance_journeys
from terrain_encounters import resolve_entry


class TerrainEncounterTests(unittest.TestCase):
    setUp=journeys.JourneyTests.setUp
    count=journeys.JourneyTests.count
    send=journeys.JourneyTests.send
    advance=journeys.JourneyTests.advance

    def enemy(self,city='B',relationship='война'):
        self.db.execute('UPDATE cities SET faction=? WHERE name=?',('Эльфы',city))
        self.db.execute("INSERT INTO units VALUES('elf','Эльфы','1',20,8,12,2,'')")
        self.db.execute('INSERT INTO garrisons VALUES(?,?,?,?,?)',(city,'elf',100,'',0))
        self.db.execute('INSERT INTO diplomacies VALUES(?,?,?)',('Север','Эльфы',relationship))
        self.db.commit()

    def send_enemy(self,source='B',target='A'):
        return start_journey(self.db,'Эльфы',source,target,[dict(unit_name='elf',unit_count=50)])

    def history(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT result FROM terrain_battles ORDER BY id')]

    def test_later_army_is_penalized_real_losses_do_not_capture_cities_and_replay_is_idempotent(self):
        self.enemy();first=self.send('B');cities=list(self.db.execute('SELECT * FROM cities'))
        attacks=[]
        def win(unit,other,*args,**kwargs):
            attacks.append((copy.deepcopy(unit),copy.deepcopy(other),kwargs))
            unit['unit_count']-=3;other['unit_count']=0
        with patch.dict('sys.modules',fight=SimpleNamespace(battle_chain=win)):
            second=self.send_enemy()
            resolve_entry(self.db,second)
        self.assertEqual(len(attacks),1)
        new,old,options=attacks[0]
        self.assertEqual((new['_encounter_attack_multiplier'],new['_encounter_defense_multiplier']),(.85,.85))
        self.assertEqual((old['_encounter_attack_multiplier'],old['_encounter_defense_multiplier']),(1,1))
        self.assertFalse(options['damage_infrastructure'])
        self.assertEqual(self.history()[0]['attacker'],'Эльфы')
        self.assertEqual(self.count('@terrain:'+str(first)),0)
        self.assertEqual(self.count('@terrain:'+str(second)),47)
        self.assertEqual(list(self.db.execute('SELECT * FROM cities')),cities)
        self.assertEqual(self.db.execute("SELECT attack,defense FROM units WHERE unit_name='elf'").fetchone(),(20,8))
        self.assertEqual(self.db.execute('SELECT experience FROM garrisons WHERE city_name=?',('@terrain:'+str(second),)).fetchone()[0],1)
        self.assertEqual(len(self.history()),1)

    def test_same_faction_and_peace_or_alliance_do_not_fight(self):
        for relationship in ('мир','союз'):
            with self.subTest(relationship=relationship):
                self.db.execute('DELETE FROM terrain_journeys');self.db.execute("DELETE FROM garrisons WHERE city_name LIKE '@terrain:%'")
                self.db.execute('DELETE FROM diplomacies')
                if not self.db.execute("SELECT 1 FROM units WHERE unit_name='elf'").fetchone():self.enemy(relationship=relationship)
                else:self.db.execute('INSERT INTO diplomacies VALUES(?,?,?)',('Эльфы','Север',relationship))
                self.send('B',10);self.send('B',10)
                with patch.dict('sys.modules',fight=SimpleNamespace(battle_chain=lambda *a,**k:self.fail('Peaceful armies fought'))):
                    self.send_enemy()
                self.assertFalse(self.history())

    def test_arrival_at_second_stop_overrides_older_journey_id(self):
        first=self.send('C');self.enemy('C')
        self.db.execute('UPDATE turn SET turn_count=1');second=self.send_enemy('C','B')
        self.assertFalse(self.history())
        def lose(unit,other,*a,**k):unit['unit_count']=0
        with patch.dict('sys.modules',fight=SimpleNamespace(battle_chain=lose)):
            self.advance(2);self.advance(2)
        result=self.history()[0]
        self.assertEqual(result['feature_id'],2)
        self.assertEqual((result['attacker'],result['defender']),('Север','Эльфы'))
        waiting=waiting_armies(self.db)
        self.assertEqual([r['id'] for r in waiting],[second])
        self.assertEqual(waiting[0]['remaining'],2)
        self.assertEqual(len(self.history()),1)

    def test_stalemate_returns_newcomer_preserves_experience_and_does_not_reward_resident(self):
        self.enemy();first=self.send_enemy()
        with patch.dict('sys.modules',fight=SimpleNamespace(battle_chain=lambda *a,**k:None)):
            self.send('B')
        self.assertEqual(self.count('A'),100)
        self.assertEqual(self.db.execute("SELECT experience FROM garrisons WHERE city_name='A'").fetchone()[0],3)
        self.assertEqual(self.history()[0]['winner'],'draw')
        self.assertEqual([r['id'] for r in waiting_armies(self.db)],[first])

    def test_failure_rolls_back_the_new_march_and_losses(self):
        self.enemy();self.send('B')
        snapshot=list(self.db.iterdump())
        with patch.dict('sys.modules',fight=SimpleNamespace(battle_chain=lambda *a,**k:(_ for _ in ()).throw(ValueError('fail')))):
            with self.assertRaisesRegex(ValueError,'fail'):self.send_enemy()
        self.assertEqual(list(self.db.iterdump()),snapshot)

    def test_real_engine_penalty_affects_both_stats_even_when_sides_reverse(self):
        ns=combat_namespace();ns['random']=SimpleNamespace(uniform=lambda *a:1,random=lambda:1)
        def unit(late):
            return dict(unit_name='troop',unit_count=10000,
                        units_stats={'Урон':100,'Защита':100,'Живучесть':0,'Класс юнита':'1'},
                        _encounter_attack_multiplier=.85 if late else 1,
                        _encounter_defense_multiplier=.85 if late else 1)
        for reversed_sides in (False,True):
            a,d=unit(not reversed_sides),unit(reversed_sides)
            ns['battle_chain'](a,d,'forest','',None,damage_infrastructure=False)
            atk=100*(1 if reversed_sides else .85);ad=100*(1 if reversed_sides else .85)
            da=100*(.85 if reversed_sides else 1);dd=100*(.85 if reversed_sides else 1)
            self.assertEqual(d['unit_count'],10000-int(atk*10000/(dd*ns['BASE_LETHALITY'])))
            self.assertEqual(a['unit_count'],10000-int(da*ns['COUNTER_ATTACK_RATIO']*10000/(ad*ns['BASE_LETHALITY'])))

    def test_battle_view_explains_penalty_and_closing_marks_only_this_report_seen(self):
        from terrain_encounter_ui import show_pending
        from test_dialog_layout import settle
        self.enemy();self.send('B')
        def win(unit,other,*a,**k):other['unit_count']=0
        with patch.dict('sys.modules',fight=SimpleNamespace(battle_chain=win)):self.send_enemy()
        screen=SimpleNamespace(conn=self.db,selected_faction='Север')
        show_pending(screen);popup=screen._terrain_battle_popup
        self.addCleanup(lambda:popup.dismiss(animation=False))
        settle();popup.reveal_result()
        self.assertIn('15%',popup.result_detail.text)
        self.assertNotIn('захватывает город',popup.result_detail.text)
        show_pending(screen);self.assertIs(screen._terrain_battle_popup,popup)
        popup.dismiss(animation=False);settle()
        self.assertIsNone(screen._terrain_battle_popup)
        self.assertEqual(self.db.execute('SELECT seen FROM terrain_battles').fetchone()[0],1)
