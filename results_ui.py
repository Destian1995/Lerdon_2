"""Campaign results without absolute positions or a five-column phone table."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from strategy_ui import StrategyButton, surface, text_label, GOLD, MUTED, FACTIONS


def show_campaign_results(owner, title, message, results, text_color):
    root = BoxLayout(orientation='vertical', spacing=dp(10))
    root.add_widget(text_label(message, 16, text_color, markup=True, size_hint_y=None, height=dp(72)))
    scroll = ScrollView(do_scroll_x=False)
    cards = GridLayout(cols=1, size_hint_y=None, spacing=dp(10))
    cards.bind(minimum_height=cards.setter('height'))
    cards.bind(width=lambda widget, value: setattr(widget, 'cols', 2 if value >= dp(760) else 1))
    for result in results:
        faction = result['faction']
        card = surface(BoxLayout(orientation='vertical', size_hint_y=None, height=dp(160),
                                 padding=dp(12), spacing=dp(8)), accent=FACTIONS.get(faction, GOLD))
        card.add_widget(text_label(faction, 17, FACTIONS.get(faction, GOLD), bold=True))
        for caption, key in (('Ветераны', 'units_combat'), ('Потери', 'units_destroyed'),
                             ('Уничтожено', 'units_killed'), ('Боевой рейтинг', 'army_efficiency_ratio')):
            value = f'{result[key]:.2f}' if key == 'army_efficiency_ratio' else f'{result[key]:,}'.replace(',', ' ')
            card.add_widget(text_label(f'{caption}: {value}', 13, MUTED))
        cards.add_widget(card)
    scroll.add_widget(cards)
    root.add_widget(scroll)
    exit_button = StrategyButton(text='Вернуться в меню', primary=True, size_hint_y=None, height=dp(48))
    exit_button.bind(on_release=owner.exit_to_main_menu)
    root.add_widget(exit_button)
    popup = Popup(title=title, content=root, size_hint=(0.95, 0.94), auto_dismiss=False)
    owner.popup = popup
    popup.open()
    return popup
