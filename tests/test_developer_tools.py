import unittest
from unittest.mock import patch
from test_otherworlds import fixture
import developer_access as dev
from developer_tools_ui import set_resources,RESOURCES
import otherworlds as worlds


class DeveloperToolsTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        self.db.executescript("CREATE TABLE user_faction(faction_name); INSERT INTO user_faction VALUES('Север');")
        self.switch=patch.object(dev,'enabled',return_value=True)
        self.switch.start();self.addCleanup(self.switch.stop)

    def test_unlimited_at_zero_is_player_only_and_does_not_touch_turn(self):
        self.db.execute('UPDATE turn_check_move SET moves_left=0')
        before=list(self.db.execute('SELECT * FROM turn'))
        for _ in range(4):worlds._move(self.db,'Север');dev.consume_action(self.db,'Север')
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0],0)
        self.assertEqual(list(self.db.execute('SELECT * FROM turn')),before)
        self.assertFalse(dev.unlimited_actions(self.db,'Эльфы'))
        with self.assertRaises(ValueError):worlds._move(self.db,'Эльфы')
        with patch.object(dev,'enabled',return_value=False):
            with self.assertRaises(ValueError):worlds._move(self.db,'Север')

    def test_normal_action_still_consumed_when_disabled(self):
        with patch.object(dev,'enabled',return_value=False):dev.consume_action(self.db,'Север')
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0],19)

    def test_set_exact_balances_preserves_other_factions_and_turn(self):
        self.db.execute("INSERT INTO resources VALUES('Эльфы','Кроны',77)")
        values=dict(zip(RESOURCES,('100 000','200000','300','40000')))
        result=set_resources(self.db,'Север',values)
        self.assertEqual(result,dict(zip(RESOURCES,(100000,200000,300,40000))))
        self.assertEqual(dict(self.db.execute("SELECT resource_type,amount FROM resources WHERE faction='Север'")),result)
        self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE faction='Эльфы'").fetchone()[0],77)
        self.assertEqual(self.db.execute('SELECT turn_count FROM turn').fetchone()[0],0)

    def test_bad_input_busy_and_unauthorized_do_not_change_any_balance(self):
        values={key:'100' for key in RESOURCES}
        before=list(self.db.execute('SELECT * FROM resources'))
        for value in ('-1','1.5','nan','999999999999999999999'):
            with self.assertRaises(ValueError):set_resources(self.db,'Север',dict(values,Кроны=value))
        with patch('turn_ui_guard.database_busy',return_value=True):
            with self.assertRaises(ValueError):set_resources(self.db,'Север',values)
        with patch('tactical_battle_bridge.operation_busy',return_value=True):
            with self.assertRaises(ValueError):set_resources(self.db,'Север',values)
        with self.assertRaises(ValueError):set_resources(self.db,'Эльфы',values)
        self.assertEqual(list(self.db.execute('SELECT * FROM resources')),before)

    def test_live_panel_updates_without_restart(self):
        from strategy_ui_fixture import Window
        from developer_tools_ui import show_tools
        from test_dialog_layout import settle
        changed=[]
        popup=show_tools(self.db,'Север',lambda:changed.append(True))
        self.addCleanup(popup.dismiss,animation=False)
        Window.size=(640,360);settle()
        self.assertEqual(set(popup.fields),set(RESOURCES))
        for field in popup.fields.values():field.text='123'
        # Use the actual visible action callback.
        buttons=popup.content.children[0]
        next(button for button in buttons.children if button.text=='Установить').dispatch('on_release')
        self.assertEqual(changed,[True]);self.assertIn('обновлены',popup.status.text)
        self.assertEqual(set(dict(self.db.execute("SELECT resource_type,amount FROM resources WHERE faction='Север'")).values()),{123})


if __name__=='__main__':unittest.main()
