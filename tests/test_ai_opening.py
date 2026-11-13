from contextlib import redirect_stdout
import io
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from tools.ai_army_audit import snapshot,extracted
from ai_strategy import apply_ai_improvements,early_expansion
from ai_opening import development_cycle
from city_construction import ensure_neutral_buildings,building_counts


class OpeningTests(unittest.TestCase):
    def setUp(self):
        self.output=redirect_stdout(io.StringIO());self.output.__enter__()
        self.addCleanup(self.output.__exit__,None,None,None)
        self.db=snapshot();self.addCleanup(self.db.close)
        self.db.execute('DELETE FROM buildings');self.db.execute('DELETE FROM garrisons')
        self.db.execute('DELETE FROM cities WHERE rowid NOT IN (SELECT rowid FROM cities LIMIT 4)')
        ids=[r[0] for r in self.db.execute('SELECT id FROM cities')]
        for cid,name,pos,owner in zip(ids,('Home','Near','Far','Island'),('[0,0]','[100,0]','[200,0]','[50,1]'),('Север','Нейтрал','Нейтрал','Нейтрал')):
            self.db.execute('UPDATE cities SET name=?,coordinates=?,faction=?,is_undead=0 WHERE id=?',(name,pos,owner,cid))
        self.db.execute('DELETE FROM roads')
        self.db.executemany('INSERT INTO roads(city1,city2) VALUES(?,?)',[(ids[0],ids[1]),(ids[1],ids[2])])
        self.db.execute("DELETE FROM resources WHERE faction='Север'")
        self.db.executemany('INSERT INTO resources(faction,resource_type,amount) VALUES(?,?,?)',
            [('Север',key,value) for key,value in {'Кроны':2500,'Рабочие':1000,'Кристаллы':2000,'Население':200}.items()])
        self.db.execute('DELETE FROM units');self.db.execute('INSERT INTO units SELECT * FROM units_default')
        self.db.execute("UPDATE user_faction SET faction_name='Элины'")
        ensure_neutral_buildings(self.db)
        cls=extracted('ii.py','AIController');apply_ai_improvements(cls)
        self.ai=cls('Север',self.db);self.ai.turn=0;self.ai._action_taken_this_turn=False
        self.ai.raw_material_price=110;self.ai.load_resources_from_db()
        self.ai.get_factions_at_war=lambda:[]
        self.ai.update_trade_resources_from_db=lambda:None
        self.ai.process_trade_agreements=lambda:None
        self.ai._apply_supply_line_losses=lambda:None
        self.ai.check_and_declare_war=Mock()
        self.fights=[]

    def fight(self,**kwargs):
        self.fights.append(kwargs)
        source,dest=kwargs['attacking_city'],kwargs['defending_city']
        for unit in kwargs['attacking_army']:
            self.db.execute('UPDATE garrisons SET unit_count=unit_count-? WHERE city_name=? AND unit_name=?',
                (unit['unit_count'],source,unit['unit_name']))
            self.db.execute('INSERT INTO garrisons(city_name,unit_name,unit_count,unit_image) VALUES(?,?,?,?)',
                (dest,unit['unit_name'],unit['unit_count'],unit['unit_image']))
        self.db.execute('DELETE FROM garrisons WHERE unit_count<=0')
        return dict(winner='attacker',rounds=0)

    def test_first_turn_recruits_then_captures_nearest_road_connected_town(self):
        with patch.dict(sys.modules,{'fight':SimpleNamespace(fight=self.fight),'troop_movement':SimpleNamespace(queue_ai_march=Mock())}), \
                patch('terrain_journeys.start_journey',return_value=False):
            development_cycle(self.ai)
        self.assertEqual(len(self.fights),1)
        self.assertEqual(self.fights[0]['defending_city'],'Near')
        self.assertGreater(sum(u['unit_count'] for u in self.fights[0]['attacking_army']),1)
        self.assertEqual(self.db.execute("SELECT faction FROM cities WHERE name='Near'").fetchone()[0],'Север')
        self.assertEqual(self.db.execute("SELECT faction FROM cities WHERE name='Island'").fetchone()[0],'Нейтрал')
        self.assertNotIn('Стена',building_counts(self.db,'Near','Север'))

    def test_helping_player_spends_action_before_neutral_expansion(self):
        self.ai.player_faction='Элины'
        self.db.executescript("CREATE TABLE IF NOT EXISTS player_allies(player_faction,ally_faction); INSERT INTO player_allies VALUES('Элины','Север');")
        self.db.execute("DELETE FROM diplomacies WHERE (faction1='Элины' AND faction2='Север') OR (faction1='Север' AND faction2='Элины')")
        self.db.execute("INSERT INTO diplomacies(faction1,faction2,relationship) VALUES('Элины','Север','союз')")
        self.ai.get_factions_at_war=lambda:['Адепты']
        self.ai.check_and_declare_war.side_effect=lambda:setattr(self.ai,'_action_taken_this_turn',True)
        with patch('ai_strategy.early_expansion') as expand,patch('ai_strategy.rally_units_to_frontier') as rally:
            development_cycle(self.ai)
        self.ai.check_and_declare_war.assert_called_once()
        rally.assert_called_once()
        expand.assert_not_called()

    def test_terrain_delay_keeps_capture_pending_instead_of_bypassing_route(self):
        self.db.execute("INSERT INTO garrisons(city_name,unit_name,unit_count,unit_image) VALUES('Home','Стрелок',100,'')")
        with patch.dict(sys.modules,{'fight':SimpleNamespace(fight=self.fight)}), \
                patch('terrain_journeys.start_journey',return_value=True) as journey:
            early_expansion(self.ai)
        journey.assert_called_once();self.assertFalse(self.fights)
        self.assertEqual(self.db.execute("SELECT faction FROM cities WHERE name='Near'").fetchone()[0],'Нейтрал')

    def test_market_waits_for_more_than_ten_thousand(self):
        self.ai.resources['Кроны']=10000;self.ai.manage_buildings()
        self.assertNotIn('Рынок',building_counts(self.db,'Home','Север'))
        self.ai.resources['Кроны']=10001;self.ai.manage_buildings()
        self.assertIn('Рынок',building_counts(self.db,'Home','Север'))

    def test_all_factions_launch_by_second_turn_without_starting_workers(self):
        self.db.commit()
        for faction in ('Север','Элины','Эльфы','Адепты','Вампиры'):
            with self.subTest(faction=faction):
                import sqlite3
                db=sqlite3.connect(':memory:');self.db.backup(db)
                try:
                    db.execute("UPDATE cities SET faction=? WHERE name='Home'",(faction,))
                    db.execute('DELETE FROM buildings');db.execute('DELETE FROM garrisons')
                    db.execute('DELETE FROM resources WHERE faction=?',(faction,))
                    db.executemany('INSERT INTO resources(faction,resource_type,amount) VALUES(?,?,?)',
                        [(faction,k,v) for k,v in {'Кроны':2500,'Рабочие':0,'Кристаллы':0,'Население':100}.items()])
                    db.execute('UPDATE user_faction SET faction_name=?',('Элины' if faction!='Элины' else 'Север',))
                    db.commit()
                    cls=extracted('ii.py','AIController');apply_ai_improvements(cls)
                    ai=cls(faction,db);ai.turn=0
                    ai.get_factions_at_war=lambda:[]
                    ai.update_trade_resources_from_db=lambda:None
                    ai.process_trade_agreements=lambda:None
                    ai._apply_supply_line_losses=lambda:None
                    ai.check_and_declare_war=Mock()
                    sent=[]
                    def capture(**kwargs):
                        sent.append(kwargs)
                        return dict(winner='attacker',rounds=0)
                    with patch.dict(sys.modules,{'fight':SimpleNamespace(fight=capture),
                            'troop_movement':SimpleNamespace(queue_ai_march=Mock())}), \
                            patch('terrain_journeys.start_journey',return_value=False):
                        for _ in range(2):ai.make_turn()
                    self.assertEqual(ai.turn,2)
                    self.assertTrue(sent,'No expedition by second turn')
                    self.assertTrue(any(str(u['units_stats']['Класс юнита'])=='1'
                                        and u['unit_count']>0 for u in sent[0]['attacking_army']))
                    self.assertIn('Больница',building_counts(db,'Home',faction))
                    self.assertIn('Фабрика',building_counts(db,'Home',faction))
                finally:db.close()

    def test_hero_can_be_hired_on_first_turn_when_affordable(self):
        self.ai.resources.update({'Кроны':50000,'Рабочие':10000})
        self.ai.hire_army()
        self.assertTrue(self.ai.has_hero_of_class('3'))
        self.assertEqual(self.ai.turn,0)

    def test_expedition_takes_hero_and_soldiers_but_keeps_capital_guardian(self):
        hero=self.db.execute("SELECT unit_name FROM units WHERE faction='Север' AND unit_class='3' LIMIT 1").fetchone()[0]
        guardian=self.db.execute("SELECT unit_name FROM units WHERE faction='Север' AND unit_class='4' LIMIT 1").fetchone()[0]
        self.db.executemany('INSERT INTO garrisons(city_name,unit_name,unit_count,unit_image) VALUES(?,?,?,?)',
            [('Home','Стрелок',100,''),('Home',hero,1,''),('Home',guardian,1,'')])
        with patch.dict(sys.modules,{'fight':SimpleNamespace(fight=self.fight),'troop_movement':SimpleNamespace(queue_ai_march=Mock())}), \
                patch('terrain_journeys.start_journey',return_value=False):
            early_expansion(self.ai)
        sent={u['unit_name'] for u in self.fights[0]['attacking_army']}
        self.assertIn(hero,sent);self.assertNotIn(guardian,sent)
        self.assertEqual(self.db.execute('SELECT city_name FROM garrisons WHERE unit_name=?',(guardian,)).fetchone()[0],'Home')

    def test_five_turn_opening_expands_and_develops_captured_towns(self):
        with patch.dict(sys.modules,{'fight':SimpleNamespace(fight=self.fight),'troop_movement':SimpleNamespace(queue_ai_march=Mock())}), \
                patch('terrain_journeys.start_journey',return_value=False):
            for turn in range(5):
                self.ai.turn=turn
                if turn:
                    self.ai.update_resources();self.ai.apply_political_system_bonus()
                self.ai.raw_material_price=110
                development_cycle(self.ai);self.ai.save_resources_to_db()
        self.assertEqual(len(self.fights),2)
        for city in ('Home','Near','Far'):
            self.assertEqual(self.db.execute('SELECT faction FROM cities WHERE name=?',(city,)).fetchone()[0],'Север')
            counts=building_counts(self.db,city,'Север')
            self.assertIn('Больница',counts);self.assertIn('Фабрика',counts)


if __name__=='__main__':unittest.main()
