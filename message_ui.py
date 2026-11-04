"""One responsive presentation for every diplomatic letter and resource offer."""
import re
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.utils import escape_markup
from strategy_ui import StrategyButton, surface, text_label, GOLD, INK, FACTIONS, MUTED
from mirror_layout import FitLabel, compact_frame

GREEN=(.40,.88,.65,1)
AMBER=(.96,.72,.38,1)
RED=(.98,.42,.40,1)
BLUE=(.48,.76,.96,1)
PORTRAITS={'Север':'people','Эльфы':'elfs','Вампиры':'vampire','Адепты':'adept','Элины':'poly'}
TAGS={'ТОРГОВЛЯ':'trade','СОЮЗ':'alliance','ПОЩАДА':'mercy','УМОЛЯЮ':'mercy',
      'ПОМОЩЬ':'help','ПРОСЬБА':'help','УГРОЗА':'threat','ПРЕДУПРЕЖДЕНИЕ':'warning',
      'ТРЕБОВАНИЕ':'demand','ВОЙНА':'war','ДРУЖБА':'friendship','ПРИВЕТСТВИЕ':'greeting',
      'МИР':'mercy','ИНФОРМАЦИЯ':'info'}
PRESENTATION={
    'trade':('Обмен ресурсами',AMBER),
    'alliance':('Предложение союза',GREEN),
    'mercy':('Предложение мира',BLUE),
    'help':('Просьба о помощи',AMBER),
    'threat':('Угроза',RED),
    'warning':('Предупреждение',AMBER),
    'demand':('Требование',RED),
    'war':('Объявление войны',RED),
    'friendship':('Дружеское послание',GREEN),
    'greeting':('Приветствие',BLUE),
    'info':('Дипломатическое послание',BLUE),
}


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


def letter_content(message,kind='info'):
    """Metadata affects presentation only; the response receives the original."""
    if kind not in PRESENTATION:kind='info'
    tag=re.match(r'^\s*\[([^\]]+)\]',message)
    if kind=='info' and tag:kind=TAGS.get(tag.group(1),kind)
    clean=re.sub(r'\[('+ '|'.join(TAGS) +r')\]\s*','',message).strip()
    return kind,clean


def highlighted_letter(message,color):
    safe=escape_markup(message)
    rgb=''.join(f'{int(c*255):02x}' for c in color[:3])
    return re.sub(r'(?<!\w)\d+(?:[.,]\d+)?(?:\s*(?:тыс\.|млн\.|млрд\.))?(?:\s*%)?',
                  lambda m:f'[b][color={rgb}]'+m.group(0)+'[/color][/b]',safe)


def build_trade_message(owner,faction,message,overlay):
    return _build_message(owner,faction,message,'trade',overlay)


def build_diplomacy_message(owner,faction,message,kind):
    with owner.canvas.before:
        Color(.01,.02,.04,.78)
        overlay=Rectangle(pos=owner.pos,size=owner.size)
    return _build_message(owner,faction,message,kind,overlay)


def _build_message(owner,faction,message,kind,overlay):
    kind,clean=letter_content(message,kind)
    caption,tone=PRESENTATION[kind]
    accent=FACTIONS.get(faction,GOLD)
    root=surface(BoxLayout(orientation='vertical',size_hint=(None,None)),INK,accent)
    root._strategy_fixed_layout=True
    compact_frame(root)
    owner.card=root;owner.add_widget(root)
    header=BoxLayout(size_hint_y=None)
    portrait=Image(source=f"files/sov/{PORTRAITS.get(faction,'people')}.jpg",size_hint_x=None)
    header.add_widget(portrait)
    titles=BoxLayout(orientation='vertical')
    title=FitLabel(text=caption,color=GOLD,bold=True,maximum=sp(24))
    sender=FitLabel(text=f'Послание от фракции {faction}',color=accent,maximum=sp(14))
    titles.add_widget(title);titles.add_widget(sender);header.add_widget(titles)
    close=StrategyButton(text='×',size_hint_x=None)
    close.bind(on_release=lambda *_:owner.close())
    compact_frame(close);header.add_widget(close);root.add_widget(header)

    terms=trade_terms(message) if kind=='trade' else None
    panels=[];body=BoxLayout()
    root.message_label=root.message_scroll=None
    if terms:
        for heading_text,(amount,resource),color,fill in (
            ('ВЫ ПОЛУЧИТЕ',terms[0],GREEN,(.045,.13,.115,1)),
            ('ВЫ ОТДАДИТЕ',terms[1],AMBER,(.145,.10,.065,1))):
            panel=surface(BoxLayout(orientation='vertical'),fill,color);compact_frame(panel)
            heading=FitLabel(text=heading_text,color=color,bold=True,halign='center')
            icon=Image(source='files/status/resource_box/'+('coin.png' if resource=='Кроны' else 'crystal.png'))
            value=FitLabel(text=amount,color=color,bold=True,halign='center')
            name=FitLabel(text=resource,halign='center')
            for widget in (heading,icon,value,name):panel.add_widget(widget)
            heading.size_hint_y,icon.size_hint_y=.18,.39
            value.size_hint_y,name.size_hint_y=.25,.18
            panels.append((panel,heading,value,name));body.add_widget(panel)
    else:
        panel=surface(BoxLayout(orientation='vertical'),(.055,.075,.105,1),tone);compact_frame(panel)
        heading=FitLabel(text='СЛОВА ПОСЛАННИКА',color=tone,bold=True,size_hint_y=None)
        panel.add_widget(heading)
        scroll=ScrollView(do_scroll_x=False,bar_width=dp(4))
        letter=text_label(highlighted_letter(clean,tone),16,markup=True,
                          size_hint_y=None)
        letter.valign='top'
        letter.unbind(size=letter._strategy_text_sizer)
        letter.bind(width=lambda w,v:setattr(w,'text_size',(max(1,v),None)),
                    texture_size=lambda w,v:setattr(w,'height',v[1]+dp(8)))
        scroll.add_widget(letter);panel.add_widget(scroll);body.add_widget(panel)
        root.message_label,root.message_scroll=letter,scroll
    root.add_widget(body)
    note=FitLabel(text=('Ресурсы будут обменены после принятия предложения.' if terms else
                        'Обсудите условия с представителем фракции.' if kind=='trade' else
                        'Выберите ответ или продолжите переговоры.' if kind in ('alliance','mercy','help') else
                        'Вы можете ответить представителю фракции.'),
                  color=MUTED,size_hint_y=None,halign='center')
    root.add_widget(note)
    actions=BoxLayout(size_hint_y=None)
    buttons=[]
    if kind in ('trade','alliance','mercy','help'):
        choices=[('Принять','да'),('Отклонить','нет')]
    else:choices=[('Ясно','__close__')]
    choices.append(('Обсудить' if kind=='trade' else 'Ответить','__open_chat__'))
    for text,answer in choices:
        button=StrategyButton(text=text,accent=GREEN if answer=='да' else GOLD,primary=answer=='да')
        compact_frame(button)
        if answer=='__open_chat__':button.bind(on_release=lambda *_:owner._open_chat())
        elif answer=='__close__':button.bind(on_release=lambda *_:owner.close())
        else:button.bind(on_release=lambda *_,a=answer:owner._respond(a))
        actions.add_widget(button);buttons.append(button)
    root.add_widget(actions)
    root.actions,root.title_label,root.sender_label=actions,title,sender
    root.portrait,root.close_button,root.offer_panels=portrait,close,panels

    def fit(*_):
        overlay.pos,overlay.size=owner.pos,owner.size
        narrow=owner.width<dp(440)
        root.size=(min(dp(820),max(1,owner.width-dp(20))),
                   min(dp(580 if narrow else 420),max(1,owner.height-dp(20))))
        root.center=owner.center
        compact=root.height<dp(360)
        root.padding,root.spacing=(dp(8),dp(6)) if compact else (dp(12),dp(8))
        header.height,header.spacing=dp(52 if compact else 64),dp(10)
        portrait.width,close.width=dp(48 if narrow else 60),dp(48)
        title.maximum,sender.maximum=sp(21 if narrow else 24),sp(13 if narrow else 14)
        actions.orientation='vertical' if narrow else 'horizontal'
        actions.spacing=dp(8)
        actions.height=dp(48)*len(buttons)+dp(8)*(len(buttons)-1) if narrow else dp(48)
        for button in buttons:button.font_size=sp(16)
        note.height,note.maximum=(0 if compact else dp(36 if narrow else 28)),sp(12)
        note.opacity=0 if compact else 1
        body.spacing=dp(10)
        for trade_panel,trade_heading,value,name in panels:
            trade_panel.padding=dp(10)
            trade_heading.maximum=sp(11 if narrow else 14)
            value.maximum=sp(25 if narrow else 34)
            name.maximum=sp(15 if narrow else 17)
        if not terms:
            panel.padding,panel.spacing=(dp(8),dp(4)) if compact else (dp(12),dp(8))
            heading.height,heading.maximum=dp(20 if compact else 26),sp(12)
            letter.font_size=sp(16)
            letter.text_size=(max(1,letter.width),None)
    owner.bind(pos=fit,size=fit)
    fit()
    return root
