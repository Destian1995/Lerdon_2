"""Faction worlds have unique landscapes and art over a shared quest network."""
ROOT='files/otherworld/themes/'
# Presentation coordinates on the 1200x800 world canvas. Stable city IDs keep
# expedition, market and quest progress while each realm has its own landmass.
CITY_LAYOUTS={
    'north':((210,265),(1010,235),(285,590),(905,600),(500,190),(600,495),(815,390)),
    'elves':((220,420),(960,510),(430,620),(775,610),(325,200),(610,380),(840,210)),
    'vampires':((190,260),(995,530),(275,600),(780,625),(480,180),(555,460),(915,230)),
    'adepts':((245,410),(1010,290),(420,615),(865,550),(380,235),(650,430),(760,200)),
    'elines':((200,525),(1020,245),(385,615),(1000,600),(330,220),(645,525),(765,205)),
}
CONFLICT_SIDES={
    'Север':('Клан Медведя','Клан Грома'),
    'Адепты':('Аббатство','Тарминат'),
    'Вампиры':('Теплокровные','Жнецы'),
    'Элины':('Отступники','Академия'),
    'Эльфы':('Город Зари','Вестники Шианы'),
}
THEMES={
    'Север':dict(key='north',name='Острова Инея',accent=(.46,.79,1,1),prefix='Инея',
        units=('Страж инея','Северный охотник','Снежный всадник','Рунный проводник','Ледяной исполин'),
        cities=('Врата странников','Гавань инея','Серебряный приют','Лунный оплот','Северный торг','Башни сияния','Звёздный перевал'),
        attack=1.05,defense=1.20),
    'Эльфы':dict(key='elves',name='Древолесье отражений',accent=(.43,.90,.63,1),prefix='Древолесья',
        units=('Страж древолесья','Звёздная лучница','Всадник белого оленя','Ткач живых ветвей','Древний энт'),
        cities=('Врата странников','Изумрудная гавань','Приют древолесья','Лунная роща','Торг светлячков','Башни рассвета','Звёздная поляна'),
        attack=1.15,defense=.95),
    'Вампиры':dict(key='vampires',name='Багровое Зазеркалье',accent=(.97,.43,.67,1),prefix='Кровавой луны',
        units=('Рыцарь крови','Сумеречный стрелок','Призрачный всадник','Кровавый чародей','Обсидиановая горгулья'),
        cities=('Врата странников','Багровая гавань','Приют теней','Цитадель луны','Обсидиановый торг','Ночные башни','Перекрёсток душ'),
        attack=1.20,defense=1.0),
    'Адепты':dict(key='adepts',name='Янтарное Зазеркалье',accent=(1,.70,.34,1),prefix='Янтарного леса',
        units=('Астральный страж','Кристальный арбалетчик','Всадник эфира','Звёздный геометр','Бронзовый голем'),
        cities=('Врата странников','Монастырская гавань','Приют рыжего леса','Цитадель ордена','Янтарный торг','Башни аббатства','Осенний перекрёсток'),
        attack=1.10,defense=1.15),
    'Элины':dict(key='elines',name='Песчаное Зазеркалье',accent=(1,.86,.48,1),prefix='Песчаного солнца',
        units=('Солнечный гоплит','Златолук','Всадник пегаса','Оракул солнца','Мраморный колосс'),
        cities=('Врата странников','Лазурный оазис','Приют караванов','Песчаная цитадель','Торг барханов','Башни пустыни','Солнечный перекрёсток'),
        attack=1.0,defense=1.15),
}


def theme(faction):return THEMES.get(faction,THEMES['Адепты'])


def city_position(faction,city_id):return CITY_LAYOUTS[theme(faction)['key']][city_id-1]


def image_path(faction,group,key):
    from pathlib import Path
    female={'north':('archer','weaver','boss'),'elves':('archer','weaver','boss'),
            'vampires':('archer','boss'),'adepts':('archer','boss'),'elines':('archer','weaver','boss')}
    skin=theme(faction)['key']
    if group=='units' and key in female[skin] and Path(ROOT+skin+'/women.atlas').is_file():group='women'
    return 'atlas://'+ROOT+theme(faction)['key']+'/'+group+'/'+key


def resolve_unit_image(source):
    for faction,data in THEMES.items():
        prefix='atlas://'+ROOT+data['key']+'/units/'
        if source and source.startswith(prefix):return image_path(faction,'units',source[len(prefix):])
    return source


def background(faction):return ROOT+theme(faction)['key']+'/map.png'


def asset_exists(path):
    from pathlib import Path
    if not path:return False
    if path.startswith('atlas://'):
        return Path(path[len('atlas://'):].rsplit('/',1)[0]+'.atlas').is_file()
    return Path(path).is_file()
