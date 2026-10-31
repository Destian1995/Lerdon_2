"""Exercise the production modal hook with phone widths and Android metrics."""
import time
import ast
import unittest
from types import SimpleNamespace

from strategy_ui_fixture import city_fixture, Window, dp, sp
from strategy_ui_fixture import __dict__ as fixture_globals, ROOT
from kivy.base import EventLoop
from kivy.metrics import Metrics
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from window_theme import install_window_theme
from responsive_ui import WindowFlow
from troop_ui import show_troop_selection
from battle_ui import BattleViewer, BattleReport
from results_ui import show_campaign_results


def settle():
    for _ in range(12):
        time.sleep(0.012)
        EventLoop.idle()


class ResponsiveWindowsTests(unittest.TestCase):
    def setUp(self):
        self.original_open = Popup.open
        self.metrics = (Metrics.density, Metrics.fontscale)
        self.size = Window.size
        self.popups = []
        self.databases = []
        install_window_theme()

    def tearDown(self):
        for popup in self.popups:
            popup.dismiss(animation=False)
        for db in self.databases:
            db.close()
        Popup.open = self.original_open
        Metrics.density, Metrics.fontscale = self.metrics
        Window.size = self.size
        settle()

    def viewport(self, size, density=1, scale=1):
        Metrics.density, Metrics.fontscale = density, scale
        Window.size = size
        settle()

    def check_vertical(self, layout):
        children = list(reversed(layout.children))
        for upper, lower in zip(children, children[1:]):
            self.assertGreaterEqual(upper.y + 1, lower.top,
                                    (type(layout).__name__, upper.pos, upper.size, lower.pos, lower.size))

    def test_long_text_and_actions_do_not_overlap_at_phone_metrics(self):
        for size, density, scale in [((320, 568), 1, 1), ((640, 360), 1, 1.5),
                                     ((1280, 720), 2, 1.3), ((360, 640), 1, 1.5)]:
            with self.subTest(size=size, density=density, scale=scale):
                self.viewport(size, density, scale)
                body = BoxLayout(orientation='vertical', spacing=dp(8))
                message = Label(text='Подробное описание последствий выбранного действия. ' * 12,
                                font_size=sp(16), size_hint_y=None, height=dp(30))
                actions = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
                calls = []
                for caption in ('Подтвердить действие', 'Вернуться к выбору', 'Закрыть'):
                    button = Button(text=caption, font_size=sp(15))
                    button.bind(on_release=lambda *_: calls.append(True))
                    actions.add_widget(button)
                body.add_widget(message)
                body.add_widget(actions)
                popup = Popup(title='Подробное описание операции', content=body, size_hint=(0.96, 0.9))
                self.popups.append(popup)
                popup.open(animation=False)
                settle()
                self.assertIsInstance(popup._window_flow, WindowFlow)
                self.check_vertical(body)
                if actions.orientation == 'vertical':
                    self.check_vertical(actions)
                for button in actions.children:
                    self.assertGreaterEqual(button.height + 1, dp(48))
                    button.dispatch('on_release')
                self.assertEqual(len(calls), 3)
                self.assertGreaterEqual(message.height, popup._window_flow.text_extent(message, message.width - dp(4))[1])
                self.assertGreater(popup._window_flow.body.height, popup._window_flow.height)
                popup.dismiss(animation=False)

    def test_troop_cards_keep_row_actions_and_bulk_selection(self):
        self.viewport((640, 360), scale=1.3)
        owner, db = city_fixture()
        self.databases.append(db)
        db.executemany('INSERT INTO units(unit_name, unit_class) VALUES (?, ?)', [('Первый', '1'), ('Второй', '2')])
        rows = [('Лирандор', 'Первый', 10, ''), ('Миреллия', 'Второй', 1, '')]
        calls = []
        owner.create_troop_group = lambda data, *args: calls.append(data)
        owner.move_selected_group_to_city = lambda *_: calls.append('send')
        popup = show_troop_selection(owner, rows)
        self.popups.append(popup)
        settle()
        for data in rows:
            widgets = owner.table_widgets[f'{data[0]}_{data[1]}']
            widgets['action_button'].dispatch('on_release')
            self.assertEqual(calls[-1], data)
            self.assertGreaterEqual(widgets['action_button'].height, dp(48))
            self.assertGreaterEqual(widgets['count_label'].y, widgets['action_button'].top)
        bulk = next(w for w in popup.content.walk() if isinstance(w, Button) and w.text == 'Добавить классы 1–3')
        bulk.dispatch('on_release')
        bulk.dispatch('on_release')
        settle()
        self.assertEqual(len(owner.selected_group), 2)
        self.assertEqual(len(owner.table_layout.children), 0)
        self.assertFalse(owner.send_group_button.disabled)
        owner.send_group_button.dispatch('on_release')
        self.assertEqual(calls[-1], 'send')

    def test_city_and_battle_use_flow_under_the_actual_open_hook(self):
        self.viewport((640, 360), scale=1.4)
        city, db = city_fixture(populated=True)
        self.databases.append(db)
        self.popups.append(city)
        city.open(animation=False)
        settle()
        self.assertIsInstance(city.content, WindowFlow)
        self.check_vertical(city.city_root)
        city.dismiss(animation=False)
        rounds = [dict(round=1, atk_max=100, def_max=100, atk_total=70, def_total=0)]
        battle = BattleViewer(rounds, 'Адепты', 'Эльфы', 'attacker', 'Адепты', 'Источник', 'Цель')
        self.popups.append(battle)
        battle.open(animation=False)
        settle()
        self.assertIsInstance(battle.content, WindowFlow)
        self.check_vertical(battle.content.body)
        self.assertGreaterEqual(battle.arena.height, dp(170))
        header = list(reversed(battle.content.body.children))[0]
        controls = header.children[0]
        self.assertGreaterEqual(controls.width, dp(232))
        self.assertEqual(controls.orientation, 'horizontal')

    def test_dynamic_content_rotation_and_dismissal(self):
        self.viewport((800, 480))
        body = BoxLayout(orientation='vertical', spacing=dp(8))
        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        row.add_widget(Button(text='Подтвердить'))
        row.add_widget(Button(text='Отменить действие'))
        body.add_widget(row)
        popup = Popup(title='Проверка', content=body)
        self.popups.append(popup)
        popup.open(animation=False)
        settle()
        self.assertEqual(row.orientation, 'horizontal')
        self.viewport((320, 568))
        self.assertEqual(row.orientation, 'vertical')
        self.check_vertical(row)
        self.viewport((800, 480))
        self.assertEqual(row.orientation, 'horizontal', (Window.size, popup.size, row.size, popup._window_flow.size))
        later = Label(text='Новый текст ' * 100, size_hint_y=None, height=dp(20))
        body.add_widget(later)
        settle()
        self.check_vertical(body)
        popup.dismiss(animation=False)
        self.assertFalse(popup._window_flow.refresh.is_triggered)

    def source_function(self, file, name):
        tree = ast.parse((ROOT / file).read_text(encoding='utf-8'))
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
        namespace = dict(fixture_globals, platform='android')
        exec(compile(ast.Module(body=[node], type_ignores=[]), file, 'exec'), namespace)
        return namespace[name]

    def test_real_message_and_event_keep_buttons_below_long_text(self):
        self.viewport((640, 360), scale=1.4)
        show_message = self.source_function('ui_components.py', 'show_message')
        show_message('Сведения', 'Длинное сообщение ' * 100)
        popup = next(w for w in Window.children if isinstance(w, Popup))
        self.popups.append(popup)
        settle()
        self.check_vertical(popup._window_flow.body)
        self.assertGreaterEqual(popup.height, dp(240))
        popup.dismiss(animation=False)
        calls = []
        owner = SimpleNamespace(player_faction='Адепты',
            apply_effects_with_economic_module=lambda value: calls.append(value),
            update_karma=lambda *args: calls.append(args), _schedule_chain_event=lambda *args: None)
        event = self.source_function('event_manager.py', 'show_event_active_popup')
        event(owner, 'Описание события ' * 70, 'Первый вариант', 'Второй вариант', {'option_1': {'gold': 10}})
        popup = next(w for w in Window.children if isinstance(w, Popup))
        self.popups.append(popup)
        settle()
        self.check_vertical(popup._window_flow.body)
        button = next(w for w in popup.content.walk() if isinstance(w, Button) and w.text == 'Первый вариант')
        button.dispatch('on_release')
        self.assertEqual(calls, [{'gold': 10}, ('Адепты', 4)])

    def test_campaign_results_and_diplomacy_have_no_absolute_content_collisions(self):
        self.viewport((320, 568), scale=1.4)
        calls = []
        owner = SimpleNamespace(exit_to_main_menu=lambda *_: calls.append('exit'))
        popup = show_campaign_results(owner, 'Итоги кампании', 'Завершена великая кампания. ' * 10,
                    [dict(faction='Адепты', units_combat=123000000, units_destroyed=90000000,
                          units_killed=100000000, army_efficiency_ratio=1.5)], (1, 1, 1, 1))
        self.popups.append(popup)
        settle()
        self.check_vertical(popup._window_flow.body)
        for w in popup.content.walk():
            if isinstance(w, BoxLayout) and w.orientation == 'vertical':
                self.check_vertical(w)
        popup.dismiss(animation=False)
        tree = ast.parse((ROOT / 'ui_components.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DiplomacyMessagePopup')
        namespace = dict(fixture_globals)
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'ui_components.py', 'exec'), namespace)
        overlay = namespace[cls.name]('Эльфы', '[СОЮЗ] ' + 'Предлагаем союз. ' * 70, 'alliance',
                                     on_respond=lambda *args: calls.append(args))
        Window.add_widget(overlay)
        try:
            settle()
            self.check_vertical(overlay.card.body)
            actions = overlay.card.body.children[0]
            self.assertEqual(actions.orientation, 'vertical')
            self.check_vertical(actions)
            button = next(w for w in overlay.walk() if isinstance(w, Button) and w.text == 'Принять')
            button.dispatch('on_release')
            self.assertEqual(calls[-1][0:2], ('Эльфы', 'да'))
        finally:
            overlay._cleanup()

    def test_equipment_slots_fit_narrow_panels_and_do_not_overlap_portrait(self):
        from kivy.uix.floatlayout import FloatLayout
        from kivy.uix.image import Image
        func = self.source_function('heroes.py', 'position_slots')
        for width in (280, 600):
            panel = FloatLayout(size=(width, 800), size_hint=(None, None))
            portrait = Image(size=(160, 160), size_hint=(None, None))
            slots = {str(i): Button(size_hint=(None, None)) for i in range(5)}
            labels = {str(i): Label(text='Длинное название артефакта', size_hint=(None, None)) for i in range(5)}
            stats = Label(size=(140, 72), size_hint=(None, None))
            func.__globals__.update(right_panel=panel, hero_stats_container=stats, hero_image_widget=portrait,
                                    slot_size=(80, 80), equipment_slots=slots, slot_name_labels=labels)
            func(0)
            panel.height = panel._responsive_min_height
            func(0)
            rectangles = [portrait, stats, *slots.values(), *labels.values()]
            for a in rectangles:
                self.assertGreaterEqual(a.x, panel.x)
                self.assertGreaterEqual(a.y, panel.y)
                self.assertLessEqual(a.right, panel.right)
                for b in rectangles:
                    if a is b:
                        continue
                    overlap_x = min(a.right, b.right) - max(a.x, b.x)
                    overlap_y = min(a.top, b.top) - max(a.y, b.y)
                    self.assertFalse(overlap_x > 1 and overlap_y > 1, (a.pos, b.pos))

    def test_equipment_button_images_survive_the_shared_skin(self):
        from window_theme import skin_button
        image = 'files/status/army.png'
        button = Button(background_normal=image)
        skin_button(button)
        self.assertEqual(button.background_normal, image)
        self.assertEqual(tuple(button.background_color), (1, 1, 1, 1))
        button.background_normal = ''
        self.assertEqual(tuple(button.background_color), (0, 0, 0, 0))
        button.background_normal = image
        self.assertEqual(tuple(button.background_color), (1, 1, 1, 1))

    def test_recruitment_navigation_recovers_after_desktop_to_phone_resize(self):
        from recruitment_ui import RecruitmentSession
        from kivy.uix.floatlayout import FloatLayout
        self.viewport((1000, 600))
        economy = SimpleNamespace(get_resource_now=lambda key: 100000)
        units = {'Паладины': dict(image='files/army/adepts/paladin.jpg', cost=(150, 2),
                    stats={'Класс юнита': '1 класс', 'Урон': 100, 'Защита': 150,
                           'Живучесть': 200, 'Потребление Кристаллов': 5})}
        session = RecruitmentSession('Адепты', SimpleNamespace(class_faction=economy), units, lambda *args: None)
        host = FloatLayout()
        Window.add_widget(host)
        host.add_widget(session)
        self.popups.append(session.popup)
        try:
            session.open()
            settle()
            self.viewport((640, 360))
            self.assertGreaterEqual(session.header_nav.width, dp(100))
            self.assertEqual(session.header_nav.orientation, 'horizontal')
            for button in session.header_nav.children:
                self.assertGreaterEqual(button.width, dp(44))
            card = session.cards[0]
            for row, _, _ in card.stat_rows:
                self.assertLessEqual(row.height, dp(30))
        finally:
            session.release()
            Window.remove_widget(host)

    def test_bottom_navigation_scrolls_without_shrinking_actions(self):
        from responsive_ui import make_action_dock
        from kivy.uix.floatlayout import FloatLayout
        self.viewport((640, 360), scale=1.4)
        host = FloatLayout()
        bar = BoxLayout(size_hint=(None, None), spacing=dp(4), padding=dp(4))
        calls = []
        for text in ('Мастерская', 'Артефакты', 'Развитие', 'Рынок', 'Налоги'):
            button = Button(text=text, font_size=sp(14))
            button.bind(on_release=lambda *args: calls.append(True))
            bar.add_widget(button)
        make_action_dock(bar)
        Window.add_widget(host)
        host.add_widget(bar)
        try:
            settle()
            row = bar._responsive_dock.children[0]
            self.assertGreater(row.width, bar.width)
            for button in row.children:
                self.assertGreaterEqual(button.width, dp(112))
                self.assertGreaterEqual(button.height, dp(48))
                button.dispatch('on_release')
            self.assertEqual(len(calls), 5)
        finally:
            Window.remove_widget(host)
            host.remove_widget(bar)
