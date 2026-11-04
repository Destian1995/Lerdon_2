import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_otherworlds import fixture
from create_artifacts import workshop_limit
from portal_home import loss_reason,marked_cities
import otherworlds as worlds


class PortalRewardTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)

    def test_workshop_uses_98_percent_of_live_cap_and_buff_expires(self):
        self.assertEqual(workshop_limit(self.db,'Север'),9_800_000)
        self.assertEqual(workshop_limit(self.db,'Элины'),11_760_000)
        self.db.execute('CREATE TABLE portal_quest_buffs(faction PRIMARY KEY,until_turn)')
        self.db.execute("INSERT INTO portal_quest_buffs VALUES('Север',25)")
        self.assertEqual(workshop_limit(self.db,'Север'),13_230_000)
        self.db.execute('UPDATE turn SET turn_count=25')
        self.assertEqual(workshop_limit(self.db,'Север'),9_800_000)

    def test_loss_precedes_victory_and_no_cities_checks(self):
        worlds.enter(self.db,'Север','Home')
        self.db.execute("UPDATE cities SET faction='Эльфы' WHERE name='Home'")
        # Load only the method; importing economic opens the player's database.
        tree=ast.parse(Path('economic.py').read_text(encoding='utf-8'))
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='end_game')
        namespace={};exec(compile(ast.Module(body=[method],type_ignores=[]),'economic.py','exec'),namespace)
        running,reason=namespace['end_game'](SimpleNamespace(conn=self.db,faction='Север'))
        self.assertFalse(running);self.assertIn('Home',reason);self.assertIn('Поражение',reason)

    def test_deleted_origin_is_a_loss_and_unrelated_capture_is_not(self):
        worlds.enter(self.db,'Север','Home')
        self.db.execute("UPDATE cities SET faction='Эльфы' WHERE name='Safe'")
        self.assertFalse(loss_reason(self.db,'Север'))
        self.db.execute("DELETE FROM cities WHERE name='Home'")
        self.assertTrue(loss_reason(self.db,'Север'))
        self.assertFalse(marked_cities(self.db))

    def test_old_save_without_loss_history_still_detects_captured_origin(self):
        worlds.enter(self.db,'Север','Home')
        self.db.execute('DROP TRIGGER portal_home_captured')
        self.db.execute('DROP TRIGGER portal_home_destroyed')
        self.db.execute('DROP TABLE portal_home_losses')
        self.db.execute("UPDATE cities SET faction='Эльфы' WHERE name='Home'")
        self.assertIn('Home',loss_reason(self.db,'Север'))

    def test_quest_glow_pulses_and_clears_without_adding_instructions(self):
        from otherworld_ui import OtherworldMap
        from test_dialog_layout import settle
        worlds.enter(self.db,'Север','Home')
        owner=OtherworldMap(self.db,'Север');owner.open(animation=False)
        self.addCleanup(lambda:owner.dismiss(animation=False))
        settle();effects=owner.map.effects
        effects.stop();count=len(effects.canvas.before.children)
        with patch('otherworld_quests.objectives',return_value={1}):
            effects.age=1;effects._quest_refresh=-1;effects.update(0)
            city,color,shape=next(g for g in effects.quest_glows if g[0]['id']==1)
            first=color.a;effects.update(.1)
            self.assertNotEqual(color.a,first)
            self.assertTrue(all(c.a==0 for city,c,_ in effects.quest_glows if city['id']!=1))
        with patch('otherworld_quests.objectives',return_value=set()):
            effects._quest_refresh=-1;effects.update(0)
            self.assertEqual(color.a,0)
        self.assertEqual(len(effects.canvas.before.children),count)
