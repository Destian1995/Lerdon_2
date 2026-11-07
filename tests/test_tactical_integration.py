"""Exercise campaign handoff on disposable SQLite databases only."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock

from test_battle_ui import combat_namespace
from test_otherworlds import fixture
from test_tactical_combat import unit
from tactical_combat import TacticalBattle
import otherworlds


class TacticalIntegrationTests(unittest.TestCase):
    def test_campaign_uses_manual_winner_and_shared_garrison_commit_path(self):
        db=fixture();self.addCleanup(db.close)
        db.executescript("CREATE TABLE user_faction(faction_name); INSERT INTO user_faction VALUES('Север');")
        ns=combat_namespace()
        persist=Mock()
        report=Mock();scheduled=[];ui_connection=object()
        ns.update(update_garrisons_after_battle=persist,update_results_table=Mock(),cleanup_equipment_after_battle=Mock(),
                  show_battle_report=report)
        attackers=[unit('troop1',count=1000)]
        defenders=[unit('Enemy',count=1)]
        def manual(a,d,*args):
            model=TacticalBattle(a,d)
            # Holding the city at the round limit wins even outnumbered.
            model.winner='defender';model.round=81
            model._snapshot()
            return model
        with patch('tactical_battle_bridge.request_battle',side_effect=manual) as request, \
             patch('city_war.record_battle'),patch('kivy.clock.Clock.schedule_once',side_effect=lambda cb,*_:scheduled.append(cb)):
            result=ns['fight']('Home','Safe',defenders,attackers,'Север','Адепты',db,ui_conn=ui_connection)
        scheduled[0](0)
        self.assertIs(report.call_args.kwargs['conn'],ui_connection)
        self.assertEqual(request.call_count,1)
        self.assertEqual(result['winner'],'defender')
        self.assertEqual(result['rounds'],80)
        self.assertEqual(persist.call_args.kwargs['winner'],'defending')
        self.assertTrue(persist.call_args.kwargs['preserve_attack_survivors'])
        self.assertEqual(persist.call_args.kwargs['attacking_army'][0]['unit_count'],1000)

    def test_tactical_siege_timeout_returns_survivors_to_the_source_city(self):
        db=fixture();self.addCleanup(db.close)
        db.execute('ALTER TABLE cities ADD COLUMN color_faction TEXT')
        db.execute("UPDATE cities SET faction='Адепты' WHERE name='Safe'")
        db.execute("UPDATE units SET faction='Адепты' WHERE unit_name='troop2'")
        db.execute("INSERT INTO garrisons VALUES('Safe','troop2',100,'',0)")
        a=unit('troop1',count=300);a['initial_count']=800
        d=unit('troop2',count=100);d['initial_count']=100
        ns=combat_namespace()
        ns['reset_third_class_units_if_empty']=Mock()
        ns['update_garrisons_after_battle']('defending','Home','Safe',[a],[d],
            'Север','Адепты',db,preserve_attack_survivors=True)
        # 200 stayed at home; 300 survived out of the 800 who marched.
        self.assertEqual(db.execute("SELECT unit_count FROM garrisons WHERE city_name='Home' AND unit_name='troop1'").fetchone()[0],500)

    def test_mirror_tactics_include_heroes_and_persist_only_after_finish(self):
        db=fixture();self.addCleanup(db.close)
        party=otherworlds.enter(db,'Север','Home')
        profiles=otherworlds.expedition_profiles(db,'Север',party['camp'])
        skirmish=Mock()
        seen=[]
        def manual(a,d,*args):
            seen.extend(copy.deepcopy(a))
            model=TacticalBattle(a,d)
            guard=next(s for s in model.stacks.values() if s.side=='defender')
            guard.count=0;guard.hp=0
            model._check_end();model._snapshot()
            return model
        with patch.dict('sys.modules',{'fight':SimpleNamespace(TYPE_MOD={},_get_season_mult=lambda *args:1)}), \
             patch('tactical_battle_bridge.request_battle',side_effect=manual):
            result=otherworlds.fight_guards(db,'Север',skirmish=skirmish,tactical=True)
        self.assertTrue(result['won'])
        self.assertTrue(result['tactical'])
        self.assertIn('Hero',[u['unit_name'] for u in seen])
        soldier=next(u for u in seen if u['unit_name']=='troop1')
        self.assertEqual(soldier['_quick_combat_power'],(int(profiles['troop1']['attack']),int(profiles['troop1']['defense'])))
        self.assertEqual(soldier['consumption'],1)
        self.assertEqual(result['guards'][0]['unit_count'],0)
        self.assertEqual(db.execute('SELECT unit_count FROM garrisons WHERE city_name=? AND unit_name=?',
                                   (party['camp'],'Hero')).fetchone()[0],1)
        skirmish.assert_not_called()


if __name__=='__main__':unittest.main()
