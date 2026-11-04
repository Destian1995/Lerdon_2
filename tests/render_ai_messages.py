"""Review the shared diplomatic card with production overlay classes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window
from test_responsive_windows import settle
from test_ai_message_style import popup_class
from kivy.metrics import Metrics

out=Path('assets/ai-messages');out.mkdir(exist_ok=True)
Popup=popup_class()
samples=[
    ('alliance','Адепты','[СОЮЗ] Пророчества ясны: наши пути едины. 2 города и 1 воин — всё это ваше, если вы с нами. Адепты выбирают одного союзника — и стоят за него до конца.'),
    ('mercy','Вампиры','[ПОЩАДА] Мы просим прекратить войну. Готовы передать 12 тыс. крон и начать переговоры о мире. Нашим народам нужен покой.'),
    ('warning','Север','[ПРЕДУПРЕЖДЕНИЕ] Разведчики заметили 3 отряда у вашей границы. Будьте готовы защитить свои города.'),
    ('trade','Эльфы','[ТОРГОВЛЯ] Мы отдаём 1 тыс. Кроны, вы — 1.2 тыс. Кристаллы'),
]
for size,density,scale,suffix in (((820,460),1,1,'desktop'),((640,360),1,1,'phone'),((1280,576),2,1.2,'android'),((320,568),1,1.4,'portrait')):
    Window.size=size;Metrics.density=density;Metrics.fontscale=scale;settle()
    for kind,faction,text in samples:
        p=Popup(faction,text,kind);Window.add_widget(p);settle()
        path=out/(kind+'-'+suffix+'.png');saved=Path(Window.screenshot(name=str(path)))
        if saved!=path:saved.replace(path)
        p._cleanup();settle()
print('Rendered diplomatic letters in four screen configurations')
