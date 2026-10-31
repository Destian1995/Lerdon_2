"""Responsive troop selection cards, retaining FortressInfoPopup's game actions."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from strategy_ui import StrategyButton, surface, text_label, GOLD, MUTED, SURFACE


class TroopCard(BoxLayout):
    def __init__(self, data, owner, **kwargs):
        super().__init__(orientation='vertical', size_hint_y=None, height=dp(172), **kwargs)
        self._responsive_keep_geometry = True
        surface(self, SURFACE)
        city, unit, count, image = data
        city_label = text_label(city, 12, MUTED)
        unit_label = text_label(unit, 15, bold=True)
        count_label = text_label(f'Доступно: {count:,}'.replace(',', ' '), 13, GOLD)
        art = Image(source=image or 'files/status/army.png')
        button = StrategyButton(text='Добавить')
        self.cells = dict(city_label=city_label, unit_label=unit_label, count_label=count_label,
                          image_container=art, action_button=button)
        for widget in self.cells.values():
            widget.size_hint = (None, None)
            self.add_widget(widget)
        # Capture every row's own widgets; the legacy table captured the final row.
        button.bind(on_release=lambda btn: owner.create_troop_group(
            data, btn, city_label, unit_label, count_label, art, button))
        self.bind(pos=self.arrange, size=self.arrange)
        self.arrange()

    def do_layout(self, *args):
        self.arrange()

    def arrange(self, *args):
        if not hasattr(self, 'cells'):
            return
        inset, art_size = dp(12), dp(64)
        text_x, text_width = self.x + dp(88), max(dp(36), self.width - dp(100))
        art = self.cells['image_container']
        art.pos, art.size = (self.x + inset, self.top - inset - art_size), (art_size, art_size)
        for key, top, height in (('unit_label', 12, 32), ('city_label', 46, 28), ('count_label', 76, 28)):
            label = self.cells[key]
            label.pos, label.size = (text_x, self.top - dp(top + height)), (text_width, dp(height))
            label.shorten = True
            label.shorten_from = 'right'
        button = self.cells['action_button']
        button.pos, button.size = (self.x + inset, self.y + inset), (max(1, self.width - 2 * inset), dp(48))


class TroopCards(GridLayout):
    def __init__(self, **kwargs):
        super().__init__(cols=1, size_hint_y=None, spacing=dp(10), **kwargs)
        self.bind(minimum_height=self.setter('height'), width=self.fit)

    def fit(self, *args):
        self.cols = max(1, min(3, int(self.width / dp(360))))


def show_troop_selection(owner, troops_data):
    owner.current_troops_data = list(troops_data)
    owner.table_widgets = {}
    popup = Popup(title='Перемещение войск', size_hint=(0.96, 0.94), auto_dismiss=False)
    owner.current_popup = popup
    root = BoxLayout(orientation='vertical', spacing=dp(10))
    summary = text_label('', 13, GOLD, size_hint_y=None, height=dp(30))
    root.add_widget(summary)
    scroll = ScrollView(do_scroll_x=False)
    scroll._responsive_min_height = dp(112)
    cards = TroopCards()
    owner.table_layout = cards
    for data in troops_data:
        card = TroopCard(data, owner)
        cards.add_widget(card)
        owner.table_widgets[f'{data[0]}_{data[1]}'] = dict(card.cells, card=card)
    scroll.add_widget(cards)
    root.add_widget(scroll)
    if not troops_data:
        cards.add_widget(text_label('Все доступные отряды уже добавлены в группу.', 14,
                                    size_hint_y=None, height=dp(70)))
    actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
    add_all = StrategyButton(text='Добавить классы 1–3')
    send = StrategyButton(text='Отправить группу', primary=True, disabled=not bool(owner.selected_group))
    owner.send_group_button = send
    actions.add_widget(add_all)
    actions.add_widget(send)
    root.add_widget(actions)

    def update_summary():
        total = sum(unit['unit_count'] for unit in owner.selected_group)
        summary.text = f'В группе: {len(owner.selected_group)} отр. · {total:,} бойцов'.replace(',', ' ')

    def add_available(*args):
        for city, unit, count, image in list(owner.current_troops_data):
            result = owner.conn.execute('SELECT unit_class FROM units WHERE unit_name = ?', (unit,)).fetchone()
            if not result or str(result[0]) not in ('1', '2', '3') or (city, unit) in owner.selected_units_set:
                continue
            owner.selected_group.append(dict(city_name=city, unit_name=unit, unit_count=count, unit_image=image))
            owner.selected_units_set.add((city, unit))
            record = owner.table_widgets.pop(f'{city}_{unit}', None)
            if record:
                cards.remove_widget(record['card'])
            owner.current_troops_data = [row for row in owner.current_troops_data
                                         if (row[0], row[1]) != (city, unit)]
        send.disabled = not bool(owner.selected_group)
        add_all.disabled = not bool(owner.current_troops_data)
        update_summary()

    add_all.bind(on_release=add_available)
    send.bind(on_release=owner.move_selected_group_to_city)
    update_summary()
    popup.content = root
    popup.open()
    return popup
