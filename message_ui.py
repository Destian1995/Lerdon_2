"""A responsive diplomatic message card, hosted by the existing overlay."""
import re
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from strategy_ui import StrategyButton, surface, text_label, GOLD, INK, FACTIONS, MUTED
from responsive_ui import WindowFlow


def trade_terms(message):
    """Read the same explicit offer format that the trade executor accepts."""
    amount = r'([\d.,]+\s*(?:тыс\.|млн\.|млрд\.)?)\s*(Крон|Кристаллов|Кроны|Кристаллы)'
    receive = re.search(r'[Мм]ы отда[её]м\s+' + amount, message)
    give = re.search(r'вы\s*[—–-]\s*' + amount, message)
    if not receive or not give:
        return None
    return tuple((match.group(1).strip(),
                  'Кроны' if match.group(2).startswith('Крон') else 'Кристаллы')
                 for match in (receive, give))


def build_trade_message(owner, faction, message, overlay):
    accent = FACTIONS.get(faction, GOLD)
    root = surface(BoxLayout(orientation='vertical', size_hint=(None, None)), INK, accent)
    owner.card = root
    owner.add_widget(root)
    header = BoxLayout(size_hint_y=None)
    portraits = {'Север': 'people', 'Эльфы': 'elfs', 'Вампиры': 'vampire',
                 'Адепты': 'adept', 'Элины': 'poly'}
    portrait = Image(source=f"files/sov/{portraits.get(faction, 'people')}.jpg",
                     size_hint_x=None)
    header.add_widget(portrait)
    titles = BoxLayout(orientation='vertical')
    title = text_label('Обмен ресурсами', 23, GOLD, bold=True)
    sender = text_label(f'Предложение от фракции {faction}', 14, accent)
    titles.add_widget(title)
    titles.add_widget(sender)
    header.add_widget(titles)
    close = StrategyButton(text='×', size_hint_x=None)
    close.bind(on_release=lambda *_: owner.close())
    header.add_widget(close)
    root.add_widget(header)

    terms = trade_terms(message)
    panels = []
    body = BoxLayout()
    if terms:
        for caption, (amount, resource), color, fill in (
                ('ВЫ ПОЛУЧИТЕ', terms[0], (0.40, 0.88, 0.65, 1), (0.045, 0.13, 0.115, 1)),
                ('ВЫ ОТДАДИТЕ', terms[1], (0.96, 0.72, 0.38, 1), (0.145, 0.10, 0.065, 1))):
            panel = surface(BoxLayout(orientation='vertical'), fill, color)
            heading = text_label(caption, 13, color, bold=True)
            heading.halign = 'center'
            icon = Image(source='files/status/resource_box/' +
                         ('coin.png' if resource == 'Кроны' else 'crystal.png'))
            value = text_label(amount, 32, color, bold=True)
            value.halign = 'center'
            name = text_label(resource, 16)
            name.halign = 'center'
            for widget in (heading, icon, value, name):
                panel.add_widget(widget)
            heading.size_hint_y, icon.size_hint_y = .18, .39
            value.size_hint_y, name.size_hint_y = .25, .18
            body.add_widget(panel)
            panels.append((panel, heading, value, name))
    else:
        body.add_widget(text_label(message.replace('[ТОРГОВЛЯ]', '').strip(), 16))
    root.add_widget(body)
    note = text_label('Ресурсы будут обменены после принятия предложения.' if terms else
                      'Обсудите условия сделки с представителем фракции.', 12, MUTED,
                      size_hint_y=None)
    note.halign = 'center'
    root.add_widget(note)
    actions = BoxLayout(size_hint_y=None)
    buttons = []
    for caption, answer in (('Принять', 'да'), ('Отклонить', 'нет'), ('Обсудить', '__open_chat__')):
        button = StrategyButton(text=caption, accent=(0.40, 0.88, 0.65, 1) if answer == 'да' else GOLD,
                                primary=answer == 'да')
        if answer == '__open_chat__':
            button.bind(on_release=lambda *_: owner._open_chat())
        else:
            button.bind(on_release=lambda *_, answer=answer: owner._respond(answer))
        actions.add_widget(button)
        buttons.append(button)
    root.add_widget(actions)

    def fit(*args):
        overlay.pos, overlay.size = owner.pos, owner.size
        root.size = min(dp(820), max(1, owner.width - dp(20))), min(dp(410), max(1, owner.height - dp(20)))
        root.center = owner.center
        unit = min(dp(1), root.height / 350)
        narrow = root.width < 440 * unit
        root.padding, root.spacing = 12 * unit, 9 * unit
        header.height, header.spacing = 58 * unit, 10 * unit
        portrait.width, close.width = (42 if narrow else 56) * unit, 44 * unit
        title.font_size, sender.font_size = (18 if narrow else 24) * unit, (12 if narrow else 14) * unit
        actions.height, actions.spacing = 48 * unit, 7 * unit
        note.height, note.font_size = (34 if narrow else 24) * unit, 12 * unit
        body.spacing = 10 * unit
        for button in buttons:
            button.font_size = (12 if narrow else 16) * unit
        for panel, heading, value, name in panels:
            panel.padding = 10 * unit
            heading.font_size = (11 if narrow else 14) * unit
            value.font_size = (23 if narrow else 34) * unit
            name.font_size = (14 if narrow else 17) * unit
    owner.bind(pos=fit, size=fit)
    fit()
    return root


def build_diplomacy_message(owner, faction, message, kind):
    accent = FACTIONS.get(faction, GOLD)
    with owner.canvas.before:
        Color(0.01, 0.02, 0.04, 0.78)
        overlay = Rectangle(pos=owner.pos, size=owner.size)
    if kind == 'trade':
        return build_trade_message(owner, faction, message, overlay)
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
