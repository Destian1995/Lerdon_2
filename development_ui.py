"""Development choices share one viewport, including on landscape phones."""
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget

from strategy_ui import (BUILDING_ICONS, GOLD, INK, MUTED, TEXT, StrategyButton,
                         surface, text_label)
from utils.helpers import format_number
from window_theme import prepare_custom_popup, center_after_resize


STRATEGIES = (
    ((1, 1), 'Баланс', 'Население и добыча растут равномерно.'),
    ((2, 1), 'Население', 'Больше населения и налогов; меньше прирост добычи.'),
    ((1, 2), 'Добыча', 'Больше добыча кристаллов; медленнее рост населения.'),
)


class DevelopmentChoice(ButtonBehavior, BoxLayout):
    def __init__(self, ratio, title, **kwargs):
        super().__init__(orientation='vertical', padding=dp(6), spacing=dp(2), **kwargs)
        surface(self)
        self.caption = text_label(title, 14, TEXT, bold=True)
        self.add_widget(self.caption)
        icons = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(3))
        for index, (kind, count) in enumerate(zip(('Больница', 'Фабрика'), ratio)):
            if index:
                icons.add_widget(text_label(':', 14, MUTED, size_hint_x=.35))
            icons.add_widget(Image(source=BUILDING_ICONS[kind], mipmap=True))
            icons.add_widget(text_label(str(count), 16, GOLD, bold=True, size_hint_x=.5))
        self.add_widget(icons)

    def set_selected(self, selected):
        self._strategy_frame.outer_color.rgba = (*GOLD[:3], 1 if selected else .25)
        self._strategy_frame.corners_color.rgba = (*GOLD[:3], 1 if selected else .25)
        self.caption.color = GOLD if selected else MUTED


def open_development(faction, show_message):
    current = getattr(faction, 'auto_build_ratio', (1, 1))
    selected = [next((i for i, item in enumerate(STRATEGIES) if item[0] == current), 0)]
    root = surface(BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(4)), INK)
    root._strategy_fixed_layout = True
    popup = Popup(title='Развитие', content=root, size_hint=(None, None), auto_dismiss=False)
    prepare_custom_popup(popup)
    header = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
    header.add_widget(text_label('Развитие', 19, GOLD, bold=True))
    close = StrategyButton(text='×', size_hint_x=None, width=dp(48))
    close._strategy_close = True
    close.bind(on_release=popup.dismiss)
    header.add_widget(close)
    root.add_widget(header)

    choices = BoxLayout(size_hint_y=None, height=dp(76), spacing=dp(6))
    root.add_widget(choices)
    info = BoxLayout(orientation='vertical', padding=[dp(8), 0], spacing=dp(2))
    ratio_label = text_label('', 12, GOLD, bold=True)
    explanation = text_label('', 13, TEXT)
    stats = text_label(
        f'Больницы: {format_number(faction.hospitals)}   ·   '
        f'Фабрики: {format_number(faction.factories)}   ·   '
        f'Кроны/ход: {format_number(faction.money_up)}', 11, MUTED)
    for label in (ratio_label, explanation, stats):
        label.unbind(size=label._strategy_text_sizer)
        label.size_hint_y = None
        label.bind(width=lambda widget, width: setattr(widget, 'text_size', (max(1, width), None)))
        label.bind(texture_size=lambda widget, size: setattr(widget, 'height', max(dp(18), size[1])))
        info.add_widget(label)
    info.add_widget(Widget())
    root.add_widget(info)
    cards = []

    def select(index):
        selected[0] = index
        (hospitals, factories), title, description = STRATEGIES[index]
        for i, card in enumerate(cards):
            card.set_selected(i == index)
        ratio_label.text = f'{title} · Больницы {hospitals} : Фабрики {factories}'
        explanation.text = description

    for i, (ratio, title, _) in enumerate(STRATEGIES):
        card = DevelopmentChoice(ratio, title)
        card.bind(on_release=lambda _, index=i: select(index))
        cards.append(card)
        choices.add_widget(card)

    actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
    cancel = StrategyButton(text='Отмена')
    apply = StrategyButton(text='Применить', primary=True)
    cancel.bind(on_release=popup.dismiss)

    def save(*_):
        faction.auto_build_ratio = STRATEGIES[selected[0]][0]
        faction.auto_build_enabled = True
        faction.save_auto_build_settings()
        popup.dismiss()
        show_message('Сохранено', f'Выбран режим: {STRATEGIES[selected[0]][1]}')

    apply.bind(on_release=save)
    actions.add_widget(cancel)
    actions.add_widget(apply)
    root.add_widget(actions)

    def fit(*_):
        popup.size = (max(1, min(dp(900), Window.width - dp(12))),
                      max(1, min(dp(520), Window.height - dp(12))))
        compact = popup.height < dp(340)
        choices.height = dp(68 if compact else 96)
        center_after_resize(popup)

    def release(*_):
        Window.unbind(on_resize=fit)

    popup.bind(on_dismiss=release)
    Window.bind(on_resize=fit)
    select(selected[0])
    fit()
    popup.open()
    return popup
