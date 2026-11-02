import ast
import json
import random
import sqlite3
import unittest
from types import SimpleNamespace

from strategy_ui_fixture import Window, FloatLayout, ROOT, dp
from test_frontend_ui import settle
from event_ticker import EventQueue, GOOD, BAD, effect_kind
from kivy.uix.modalview import ModalView


class EventTickerTests(unittest.TestCase):
    def setUp(self):
        self.size = Window.size
        Window.size = (800, 600)
        self.screen = FloatLayout()
        Window.add_widget(self.screen)
        self.queue = EventQueue(self.screen)
        settle()

    def tearDown(self):
        Window.remove_widget(self.screen)
        Window.size = self.size
        settle()

    def test_events_share_ribbon_and_resource_signs_have_independent_colors(self):
        self.queue.push('Торговля выросла', changes=[('Кроны', 150)])
        ticker = self.queue.active
        settle()
        ticker.cancel()
        self.queue.push('Неурожай', changes=[('Население', -50)])
        self.assertIs(self.queue.active, ticker)
        self.assertEqual(effect_kind([('Кроны', 10), ('Рабочие', -5)]), 'mixed')
        seen = []
        for _ in range(1200):
            if ticker.closed:
                break
            ticker.advance(.1)
            seen.extend((label.text, tuple(label.color)) for label in ticker.segments)
        self.assertTrue(any('Торговля' in text and color == tuple(GOOD) for text, color in seen))
        self.assertTrue(any('Неурожай' in text and color == tuple(BAD) for text, color in seen))
        self.assertTrue(any('+150' in text and color == tuple(GOOD) for text, color in seen))
        self.assertTrue(any('−50' in text and color == tuple(BAD) for text, color in seen))
        self.assertTrue(ticker.closed)
        self.assertIsNone(self.queue.active)

    def test_long_events_are_lazy_bounded_and_resize_keeps_progress(self):
        self.queue.push('Длинное сообщение о последствиях выбора ' * 100, 'negative')
        settle()
        ticker = self.queue.active
        ticker.cancel()
        ticker.advance(.1)
        before = ticker.offset
        Window.size = (320, 568)
        settle()
        self.assertEqual(ticker.offset, before)
        self.assertLess(len(ticker.segments), 6)
        self.assertTrue(self.queue.pending)
        self.assertLessEqual(ticker.right, self.screen.right)
        self.assertTrue(all(label.texture.width < 1800 for label in ticker.segments))

    def test_modal_pauses_ribbon_and_screen_removal_cancels_timer(self):
        self.queue.push('Положительное последствие', 'positive')
        settle()
        ticker = self.queue.active
        modal = ModalView()
        modal.open(animation=False)
        try:
            before = ticker.offset
            ticker.advance(.1)
            self.assertEqual(ticker.offset, before)
        finally:
            modal.dismiss(animation=False)
        Window.remove_widget(self.screen)
        self.assertFalse(ticker.events)
        self.assertIsNone(self.queue.active)
        Window.add_widget(self.screen)

    def test_detached_ribbon_can_be_replaced_by_next_notification(self):
        self.queue.push('Первое событие', 'positive')
        ticker = self.queue.active
        self.screen.remove_widget(ticker)
        self.assertIsNone(self.queue.active)
        self.assertFalse(ticker.events)
        self.queue.push('Новое событие', 'negative')
        self.assertIsNotNone(self.queue.active)
        self.assertIsNot(self.queue.active, ticker)


class ChoiceEffectTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((ROOT / 'event_manager.py').read_text(encoding='utf-8'))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'EventManager')
        ns = dict(json=json, random=random, format_number=str)
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'event_manager.py', 'exec'), ns)
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
            CREATE TABLE resources(faction TEXT, resource_type TEXT, amount INTEGER);
            INSERT INTO resources VALUES('Север', 'Кроны', 1000);
            INSERT INTO resources VALUES('Север', 'Рабочие', 100);
        ''')
        self.notifications = []
        def update(resource, amount):
            self.db.execute('UPDATE resources SET amount=? WHERE resource_type=?', (amount, resource))
        self.manager = ns['EventManager']('Север', None, SimpleNamespace(update_resource_now=update), self.db)
        self.manager.show_temporary_build = lambda *args: self.notifications.append(args)

    def tearDown(self):
        self.db.close()

    def test_choice_reports_actual_mixed_changes_once(self):
        self.manager.apply_effects_with_economic_module({'resource_changes': {
            'Кроны': {'kf': 1.5}, 'Рабочие': {'kf': .5}}})
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(self.notifications[0][2], [('Кроны', 500), ('Рабочие', -50)])
        self.assertEqual(self.manager.get_resource_amount('Рабочие'), 50)

    def test_deferred_choice_consequence_reports_loss_and_fires_once(self):
        self.db.executescript('''
            CREATE TABLE event_chains(id INTEGER, faction TEXT, trigger_turn INTEGER,
                choice_type TEXT, original_event TEXT, fired INTEGER);
            INSERT INTO event_chains VALUES(1, 'Север', 5, 'negative', 'Выбор', 0);
        ''')
        self.manager.CHAIN_CONSEQUENCES = {'negative': [
            {'desc': 'Саботаж', 'effect': {'resource': 'Рабочие', 'kf': .75}}]}
        self.assertTrue(self.manager._check_pending_chains(5))
        self.assertEqual(self.notifications[0][2], [('Рабочие', -25)])
        self.assertFalse(self.manager._check_pending_chains(6))

    def test_karma_sequence_reports_the_resource_delta(self):
        self.db.execute('CREATE TABLE events(id INTEGER, description TEXT, event_type TEXT, effects TEXT)')
        self.db.execute('INSERT INTO events VALUES(1, ?, ?, ?)',
                        ('Купцы прибыли', 'sequences', json.dumps({'resource': 'Кроны', 'kf': 1.5})))
        self.assertTrue(self.manager.generate_sequence_event('posi'))
        self.assertEqual(self.notifications[0][2], [('Кроны', 500)])

    def test_repeated_passive_events_update_one_balance_and_leave_it_spendable(self):
        from utils.resource_payments import spend_resources
        self.manager.update_resource('Кроны', 200)
        self.manager.update_resource('Кроны', -100)
        self.assertEqual(self.manager.get_resource_amount('Кроны'), 1100)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM resources WHERE resource_type='Кроны'").fetchone()[0], 1)
        self.assertTrue(spend_resources(self.db, 'Север', {'Кроны': 1100}))
