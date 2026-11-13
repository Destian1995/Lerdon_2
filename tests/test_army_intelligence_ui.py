import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from strategy_ui_fixture import city_fixture,Window,Label
from strategy_ui_fixture import __dict__ as ui_globals
from test_dialog_layout import settle
from test_army_intelligence import fixture
import army_intelligence as intel


class IntelligenceUITests(unittest.TestCase):
    def setUp(self):self.size=Window.size;self.popups=[]

    def tearDown(self):
        for popup,db in self.popups:popup.dismiss(animation=False);db.close()
        Window.size=self.size;settle()

    def rating(self,db):
        node=next(n for n in ast.parse(Path('politic.py').read_text(encoding='utf-8-sig')).body
                  if isinstance(n,ast.FunctionDef) and n.name=='create_army_rating_table')
        local=Mock(side_effect=lambda conn,f: {'Север':100,'Адепты':987654321,'Эльфы':123456789}[f])
        total=Mock(side_effect=lambda conn,f: {'Север':1000,'Адепты':987654322,'Эльфы':123456788}[f])
        ns=dict(ui_globals,calculate_peace_army_points=local,calculate_total_faction_power=total,
                faction_names={},format_number=str)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'politic.py','exec'),ns)
        table=ns[node.name](db)
        return [w.text for w in reversed(table.children)],local,total

    def test_rating_hides_values_and_does_not_rank_unknown_factions_by_power(self):
        db=fixture();self.addCleanup(db.close)
        text,local,total=self.rating(db)
        self.assertEqual(text[3:6],['Север','100','1000'])
        self.assertEqual(text[6:],['Адепты',intel.UNKNOWN,intel.UNKNOWN,'Эльфы',intel.UNKNOWN,intel.UNKNOWN])
        self.assertEqual([call.args[1] for call in total.call_args_list],['Север'])
        intel.gather(db,'Север','Эльфы','Дом')
        text,_,_=self.rating(db)
        self.assertIn('123456789',text);self.assertNotIn('987654321',text)
        db.execute('UPDATE turn SET turn_count=7')
        text,_,_=self.rating(db)
        self.assertNotIn('123456789',text)

    def test_city_roster_totals_and_stale_detail_callbacks_are_hidden(self):
        Window.size=(640,360)
        popup,db=city_fixture(owner='Эльфы',populated=True);self.popups.append((popup,db))
        db.executescript("CREATE TABLE resources(faction,resource_type,amount);INSERT INTO resources VALUES('Адепты','Кроны',5000000); CREATE TABLE turn(turn_count);INSERT INTO turn VALUES(5); INSERT INTO cities VALUES('Дом','Адепты','[1, 1]',0);")
        popup.open(animation=False);settle()
        self.assertEqual(popup.garrison_attack_total.text,'?')
        self.assertIsNone(popup.garrison_totals_snapshot)
        self.assertNotIn('Стражи рассвета',' '.join(w.text for w in popup.attacking_units_box.walk() if isinstance(w,Label)))
        intel.gather(db,'Адепты','Эльфы','Дом');popup.get_garrison();settle()
        self.assertEqual(popup.garrison_totals_snapshot['count'],4500)
        self.assertNotEqual(popup.garrison_attack_total.text,'?')
        db.execute('UPDATE turn SET turn_count=7');popup.get_garrison()
        self.assertIsNone(popup.garrison_totals_snapshot)
        self.assertFalse(popup.garrison_profiles_snapshot)
        error=Mock()
        with patch.dict(popup._show_unit_stats_popup.__globals__,{'_show_dark_error_popup':error}):
            popup._show_unit_stats_popup('Стражи рассвета',999,999,999,4500,'1')
        error.assert_called_once()

    def test_own_garrison_never_requires_reconnaissance(self):
        popup,db=city_fixture(populated=True);self.popups.append((popup,db))
        self.assertEqual(popup.garrison_totals_snapshot['count'],4500)
        self.assertNotEqual(popup.garrison_attack_total.text,'?')

    def test_allied_garrison_and_rating_are_visible_without_report(self):
        popup,db=city_fixture(owner='Эльфы',populated=True);self.popups.append((popup,db))
        db.executescript("CREATE TABLE diplomacies(faction1,faction2,relationship); INSERT INTO diplomacies VALUES('Адепты','Эльфы','союз');")
        popup.get_garrison();settle()
        self.assertEqual(popup.garrison_totals_snapshot['count'],4500)
        self.assertNotEqual(popup.garrison_attack_total.text,'?')
        db=fixture();self.addCleanup(db.close)
        db.executescript("CREATE TABLE diplomacies(faction1,faction2,relationship); INSERT INTO diplomacies VALUES('Эльфы','Север','союз');")
        text,_,_=self.rating(db)
        self.assertIn('123456789',text)
        self.assertNotIn('987654321',text)

    def test_tavern_gathers_real_two_turn_reports_on_small_screens(self):
        from test_main_map_intrigues import fixture as tavern_fixture
        from main_intrigue_ui import MainIntriguesPopup
        db=tavern_fixture()
        popup=MainIntriguesPopup(db,'Север','Дом');self.popups.append((popup,db))
        popup.open(animation=False);popup.select_category('intel');settle()
        for size in ((640,360),(320,568)):
            Window.size=size;settle();popup.fit();settle()
            for button in popup.tabs.values():
                self.assertGreaterEqual(button.y,popup.navigation.y-1)
                self.assertLessEqual(button.top,popup.navigation.top+1)
            popup.scroll.scroll_y=1;settle()
            popup.export_to_png('.release/scout-selection-'+str(size[0])+'.png')
        screen=SimpleNamespace(refresh_map=Mock())
        with patch.dict('sys.modules',game_process=screen):
            db.execute("UPDATE resources SET amount=5000000 WHERE resource_type='Кроны'");popup.select_intelligence('Адепты');settle()
            popup.controls['intel','Адепты','gather'].dispatch('on_release');settle()
        self.assertEqual(intel.remaining(db,'Север','Адепты'),2)
        self.assertTrue(intel.city_visible(db,'Север','Вражеский'))
        self.assertIn('ещё 2 х.',' '.join(w.text for w in popup.body.walk() if hasattr(w,'text')))
        popup.export_to_png('.release/tavern-intelligence-phone.png')


if __name__=='__main__':unittest.main()
