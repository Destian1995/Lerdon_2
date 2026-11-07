"""Campaign results without absolute positions or a five-column phone table."""
from kivy.metrics import dp,Metrics
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
from mirror_readable_ui import ReadableText
from campaign_endings import epilogue
from strategy_ui import StrategyButton, surface, text_label, GOLD, MUTED, FACTIONS


def show_campaign_results(owner, title, message, results, text_color):
    root = BoxLayout(orientation='vertical', spacing=dp(10))
    ending=epilogue(getattr(owner,'conn',None),getattr(owner,'current_faction','Север'),
                    getattr(owner,'game_status','win'),getattr(owner,'reason',message))
    body=BoxLayout(orientation='vertical',spacing=dp(8))
    art=Image(source=ending['image'],fit_mode='contain',size_hint_y=None,height=dp(210))
    body.add_widget(art)
    story_scroll=ScrollView(do_scroll_x=False)
    story=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(10),padding=dp(8))
    story.bind(minimum_height=story.setter('height'))
    for text,size,color in ((ending['title'],21,GOLD),(ending['chronicle'],14,MUTED),
                            (ending['story'],16,(.9,.91,.88,1)),(ending['reason'],14,text_color),
                            (ending['consequence'],14,GOLD)):
        story.add_widget(ReadableText(text,size=size,color=color))
    story_scroll.add_widget(story);body.add_widget(story_scroll)
    root.add_widget(body)
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
    tabs=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(8))
    summary=StrategyButton(text='Концовка');statistics=StrategyButton(text='Статистика')
    tabs.add_widget(summary);tabs.add_widget(statistics);root.add_widget(tabs)
    def select(widget):
        for child in (body,scroll):
            if child.parent is root:root.remove_widget(child)
        root.add_widget(widget,index=2)
    summary.bind(on_release=lambda *_:select(body));statistics.bind(on_release=lambda *_:select(scroll))
    exit_button = StrategyButton(text='Вернуться в меню', primary=True, size_hint_y=None, height=dp(48))
    exit_button.bind(on_release=owner.exit_to_main_menu)
    root.add_widget(exit_button)
    popup = Popup(title=title, content=root, size_hint=(0.95, 0.94), auto_dismiss=False)
    owner.popup = popup
    popup.ending=ending;popup.epilogue_body=body;popup.ending_art=art
    popup.story_scroll=story_scroll;popup.statistics_scroll=scroll
    popup.summary_button=summary;popup.statistics_button=statistics
    def fit(*_):
        tabs.height=dp(44);exit_button.height=dp(48)
        root.spacing=dp(8);body.spacing=dp(8)
        portrait=popup.height>popup.width
        body.orientation='vertical' if portrait else 'horizontal'
        art.size_hint=(1,None) if portrait else (.48,1)
        if portrait:art.height=min(dp(240),max(dp(80),popup.height*.30))
    popup.bind(size=fit);Metrics.bind(density=fit)
    popup.bind(on_dismiss=lambda *_:Metrics.unbind(density=fit));fit()
    popup.open()
    return popup
