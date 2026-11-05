"""Touch-friendly reserve cards and garrison quantity selection."""
import math

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from strategy_ui import StrategyButton, surface, text_label, GOLD, MUTED
from utils.helpers import format_number


def wrapped(text, size=14, color=MUTED, **kwargs):
    label = text_label(text, size, color, size_hint_y=None, **kwargs)
    label.unbind(size=label._strategy_text_sizer)
    label.bind(width=lambda w, v: setattr(w, 'text_size', (max(1, v), None)),
               texture_size=lambda w, v: setattr(w, 'height', max(dp(24), v[1])))
    return label


class ReserveCard(BoxLayout):
    def __init__(self, row, owner, **kwargs):
        super().__init__(orientation='vertical', padding=dp(12), spacing=dp(10),
                         size_hint_y=None, **kwargs)
        self._responsive_keep_geometry = True
        surface(self)
        name, count, attack, defense, durability, unit_class, image = row
        self.unit_data = dict(unit_type=name, quantity=count, unit_image=image,
                              stats={'Атака': attack, 'Защита': defense,
                                     'Живучесть': durability, 'Класс': unit_class})
        top = BoxLayout(spacing=dp(12), size_hint_y=None)
        self.art = AsyncImage(source=image or 'files/status/army.png', fit_mode='contain',
                              size_hint=(None, None), size=(dp(88), dp(88)),
                              pos_hint={'center_y': .5})
        info = BoxLayout(orientation='vertical', spacing=dp(4), size_hint_y=None)
        info.bind(minimum_height=info.setter('height'))
        self.name_label = wrapped(name, 16, GOLD, bold=True)
        self.stats_label = wrapped(
            f'Атака: {format_number(attack)} · Защита: {format_number(defense)}\n'
            f'Живучесть: {format_number(durability)} · Класс: {unit_class}', 13)
        self.count_label = wrapped(f'Доступно: {format_number(count)}', 14)
        for label in (self.name_label, self.stats_label, self.count_label):
            info.add_widget(label)
        info.bind(height=lambda w, v: setattr(top, 'height', max(dp(100), v)))
        top.add_widget(self.art)
        top.add_widget(info)
        self.add_widget(top)
        self.add_button = StrategyButton(text='Добавить в гарнизон', primary=True,
                                         size_hint_y=None, height=dp(48))
        self.add_button.bind(on_release=lambda button: owner.add_to_garrison_with_slider(
            self.unit_data, button))
        self.add_widget(self.add_button)
        self.bind(minimum_height=self.setter('height'))
        self.bind(width=self.arrange)

    def arrange(self, *_):
        wide = self.width >= dp(440)
        self.orientation = 'horizontal' if wide else 'vertical'
        self.add_button.size_hint_x = None if wide else 1
        self.add_button.width = dp(142) if wide else self.width - dp(24)
        self.add_button.pos_hint = {'center_y': .5}


class ReserveGrid(GridLayout):
    def __init__(self, **kwargs):
        super().__init__(cols=1, spacing=dp(10), size_hint_y=None, **kwargs)
        self.bind(minimum_height=self.setter('height'), width=self.fit)

    def fit(self, *_):
        self.cols = max(1, min(3, int((self.width + dp(10)) / dp(340))))


def show_army_reserve(owner, rows):
    popup = Popup(title='Разместить армию', size_hint=(.98, .96))
    owner.current_popup = popup
    from window_theme import prepare_custom_popup
    prepare_custom_popup(popup)
    root = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
    root._responsive_keep_geometry = True
    root._strategy_fixed_layout = True
    header = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
    title = wrapped(f'Разместить армию · {owner.city_name}', 16, GOLD, bold=True)
    title.pos_hint = {'center_y': .5}
    title.bind(texture_size=lambda w, v: setattr(header, 'height', max(dp(48), v[1] + dp(8))))
    header.add_widget(title)
    close = StrategyButton(text='×', size_hint=(None, None), size=(dp(48), dp(48)),
                           pos_hint={'center_y': .5})
    close.bind(on_release=popup.dismiss)
    header.add_widget(close)
    root.add_widget(header)
    scroll = ScrollView(do_scroll_x=False, bar_width=dp(4), scroll_type=['content', 'bars'])
    cards = ReserveGrid()
    for row in rows:
        if row[1] > 0:
            cards.add_widget(ReserveCard(row, owner))
    scroll.add_widget(cards)
    root.add_widget(scroll)
    popup.cards, popup.list_scroll = cards, scroll
    popup.content = root
    popup.open()
    return popup


def show_deployment_quantity(owner, data):
    available = int(data['quantity'])
    current, limit = owner.get_army_consumption_and_limit()
    row = owner.conn.execute('SELECT consumption FROM units WHERE unit_name = ?',
                             (data['unit_type'],)).fetchone()
    consumption = float(row[0] or 0) if row else 0
    capacity = max(0, math.floor((limit - current) / consumption)) if consumption > 0 else available
    maximum = min(available, capacity)
    if available == 1:
        if maximum == 1:
            owner.transfer_army_to_garrison(data, 1)
        else:
            from ui_components import show_message
            show_message('Лимит армии', 'Недостаточно свободного лимита армии для размещения юнита.')
        return
    popup = Popup(title='Количество войск', size_hint=(.96, .94), auto_dismiss=False)
    root = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(10))
    root._responsive_keep_geometry = True
    body = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
    body.bind(minimum_height=body.setter('height'))
    details = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8), pos_hint={'top': 1})
    details.bind(minimum_height=details.setter('height'))
    details.add_widget(wrapped(data['unit_type'], 18, GOLD, bold=True))
    details.add_widget(wrapped(f'В резерве: {format_number(available)}\nМожно разместить: {format_number(maximum)}'))
    usage = wrapped('')
    details.add_widget(usage)
    body.add_widget(details)
    selection = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8), pos_hint={'top': 1})
    selection.bind(minimum_height=selection.setter('height'))
    body.add_widget(selection)

    def arrange(*_):
        wide = root.width >= dp(520) and root.height < dp(480)
        body.orientation = 'horizontal' if wide else 'vertical'
        details.size_hint_x = .46 if wide else 1
        selection.size_hint_x = .54 if wide else 1

    root.bind(size=arrange)
    arrange()
    controls = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
    minus = StrategyButton(text='−', size_hint_x=None, width=dp(48))
    value = text_label('', 20, GOLD, bold=True)
    value.halign = 'center'
    plus = StrategyButton(text='+', size_hint_x=None, width=dp(48))
    for widget in (minus, value, plus):
        controls.add_widget(widget)
    selection.add_widget(controls)
    slider = Slider(min=0, max=max(1, maximum), value=min(1, maximum), step=1,
                    disabled=maximum == 0, size_hint_y=None, height=dp(48))
    selection.add_widget(slider)
    quick = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
    for title, fraction in (('1', None), ('Половина', .5), ('Максимум', 1)):
        button = StrategyButton(text=title, disabled=maximum == 0)
        button.bind(on_release=lambda _, fraction=fraction: setattr(
            slider, 'value', min(1, maximum) if fraction is None else max(1, int(maximum * fraction))))
        quick.add_widget(button)
    selection.add_widget(quick)
    scroll = ScrollView(do_scroll_x=False)
    scroll.add_widget(body)
    root.add_widget(scroll)
    actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
    cancel = StrategyButton(text='Отмена')
    confirm = StrategyButton(text='Разместить', primary=True)
    actions.add_widget(cancel)
    actions.add_widget(confirm)
    root.add_widget(actions)

    def update(*_):
        count = min(maximum, int(slider.value))
        value.text = format_number(count)
        usage.text = f'Потребление: {current + consumption * count:.1f} / {limit:.1f}'
        if maximum == 0:
            usage.text += '\nНедостаточно свободного лимита армии.'
        confirm.disabled = count < 1
        minus.disabled = count <= 1
        plus.disabled = count >= maximum

    def deploy(*_):
        count = min(maximum, int(slider.value))
        if count > 0:
            owner.transfer_army_to_garrison(data, count)
            popup.dismiss()

    minus.bind(on_release=lambda _: setattr(slider, 'value', max(1, int(slider.value) - 1)))
    plus.bind(on_release=lambda _: setattr(slider, 'value', min(maximum, int(slider.value) + 1)))
    slider.bind(value=update)
    cancel.bind(on_release=popup.dismiss)
    confirm.bind(on_release=deploy)
    update()
    popup.slider, popup.confirm_button = slider, confirm
    popup.quick_buttons, popup.quantity_controls = quick, controls
    popup.content = root
    popup.open()
    return popup
