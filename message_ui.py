"""A responsive diplomatic message card, hosted by the existing overlay."""
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from strategy_ui import StrategyButton, surface, text_label, GOLD, INK, FACTIONS
from responsive_ui import WindowFlow


def build_diplomacy_message(owner, faction, message, kind):
    accent = FACTIONS.get(faction, GOLD)
    with owner.canvas.before:
        Color(0.01, 0.02, 0.04, 0.78)
        overlay = Rectangle(pos=owner.pos, size=owner.size)
    root = surface(BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(12)), INK, accent)
    header = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
    header.add_widget(text_label(faction, 19, accent, bold=True))
    close = StrategyButton(text='×', size_hint_x=None, width=dp(48))
    close.bind(on_release=lambda *_: owner.close())
    header.add_widget(close)
    root.add_widget(header)
    for tag in ('СОЮЗ', 'ТОРГОВЛЯ', 'УГРОЗА', 'ПРЕДУПРЕЖДЕНИЕ', 'ПОЩАДА', 'УМОЛЯЮ', 'ПОМОЩЬ', 'ПРОСЬБА', 'ДРУЖБА'):
        message = message.replace(f'[{tag}]', '').strip()
    root.add_widget(text_label(message, 15, size_hint_y=None, height=dp(140)))
    actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
    if kind in ('trade', 'alliance', 'mercy', 'help'):
        for text, answer in (('Принять', 'да'), ('Отклонить', 'нет')):
            button = StrategyButton(text=text, primary=answer == 'да')
            button.bind(on_release=lambda *_, answer=answer: owner._respond(answer))
            actions.add_widget(button)
    else:
        button = StrategyButton(text='Ясно')
        button.bind(on_release=lambda *_: owner.close())
        actions.add_widget(button)
    reply = StrategyButton(text='Ответить')
    reply.bind(on_release=lambda *_: owner._open_chat())
    actions.add_widget(reply)
    root.add_widget(actions)
    flow = WindowFlow(root, size_hint=(None, None))
    owner.card = flow
    owner.add_widget(flow)

    def fit(*args):
        overlay.pos, overlay.size = owner.pos, owner.size
        flow.size = (min(dp(600), max(1, owner.width - dp(16))),
                     min(dp(440), max(1, owner.height - dp(16))))
        flow.center = owner.center
    owner.bind(pos=fit, size=fit)
    fit()
    return flow
