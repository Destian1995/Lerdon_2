"""End-turn regressions without importing the live save's bootstrap module."""
import ast
import threading
from contextlib import redirect_stdout
import io
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from strategy_ui_fixture import ROOT, Clock, Window, hud_fixture, cleanup_hud


def extracted(file, name, namespace, class_name=None):
    tree = ast.parse((ROOT / file).read_text(encoding='utf-8'))
    body = tree.body
    if class_name:
        body = next(n for n in body if isinstance(n, ast.ClassDef) and n.name == class_name).body
    node = next(n for n in body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), file, 'exec'), namespace)
    return namespace[name]


class EndTurnCrashTests(unittest.TestCase):
    def run_worker(self, function):
        errors = []
        def run():
            try:
                function()
            except BaseException as error:
                errors.append(error)
        worker = threading.Thread(target=run)
        worker.start()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])

    def test_vampire_diplomacy_after_greeting_sends_warning(self):
        namespace = {}
        names = ('send_proactive_diplomacy', '_vampires_diplomacy')
        cls = type('Diplomacy', (), {name: extracted('ii.py', name, namespace, 'AIController')
                                     for name in names})
        ai = cls()
        ai.faction, ai.turn = 'Вампиры', 5
        ai.FACTION_PERSONALITIES = {'Вампиры': {}}
        ai.FACTION_PERSONALITIES['Вампиры']['greetings'] = ['Привет']
        ai.FACTION_TRAITS = {}
        ai._get_player_faction_name = lambda: 'Север'
        ai.get_city_count_for_faction = lambda: 2
        ai._is_at_war_with_player = lambda: False
        ai._recently_messaged_player = lambda **kw: False
        ai._get_relations_with_player = lambda: 20
        ai._has_same_ideology_as_player = lambda: False
        ai._get_game_context = lambda: dict(our_strength=100, player_strength=100, our_cities=2)
        ai._send_faction_greeting = lambda *args: False
        messages = []
        ai._send_diplomatic_message = lambda *args: messages.append(args) or True
        with patch('random.random', return_value=0):
            ai.send_proactive_diplomacy()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][0], 'ПРЕДУПРЕЖДЕНИЕ')

    def test_coup_popup_from_turn_worker_builds_on_main_thread(self):
        import nobles_generator as nobles
        calls = []
        original = nobles.BoxLayout
        def layout(*args, **kwargs):
            calls.append(threading.current_thread())
            return original(*args, **kwargs)
        output = io.StringIO()
        before = set(Window.children)
        with patch.object(nobles, 'BoxLayout', side_effect=layout), redirect_stdout(output):
            self.run_worker(lambda: nobles.show_coup_attempt_popup(message_override='Проверка'))
            self.assertEqual(calls, [])
            Clock.tick()
        self.assertEqual(calls, [threading.main_thread()])
        self.assertNotIn('Ошибка', output.getvalue())
        for popup in set(Window.children) - before:
            if hasattr(popup, 'dismiss'):
                popup.dismiss(animation=False)

    def test_resource_payment_callback_rebuilds_hud_on_main_thread(self):
        host = hud_fixture()
        try:
            Clock.tick()
            box = host.resource_box
            box._render_key = None
            calls = []
            original = box.clear_widgets
            def clear(*args, **kwargs):
                calls.append(threading.current_thread())
                return original(*args, **kwargs)
            with patch.object(box, 'clear_widgets', side_effect=clear):
                self.run_worker(lambda: box.update_resources(delta={'Кроны': {'base': 1, 'bonus': 0}}))
                self.assertEqual(calls, [])
                Clock.tick()
            self.assertTrue(calls)
            self.assertTrue(all(t is threading.main_thread() for t in calls))
        finally:
            cleanup_hud(host)

    def test_map_refresh_from_worker_runs_graphics_on_main_thread(self):
        calls = []
        screen = SimpleNamespace(parent=None, update_army_rating=lambda: calls.append(threading.current_thread()))
        namespace = dict(Clock=Clock, _active_game_screen=screen)
        refresh = extracted('game_process.py', 'refresh_map', namespace)
        self.run_worker(refresh)
        self.assertEqual(calls, [])
        Clock.tick()
        self.assertEqual(calls, [threading.main_thread()])


if __name__ == '__main__':
    unittest.main()
