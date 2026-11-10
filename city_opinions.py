"""Tavern conversations follow current taxes and the city's capture history."""
import sqlite3


def tax_number(value):
    try:return max(0,min(100,float(str(value).rstrip('%'))))
    except (TypeError,ValueError):return None


def conversations(conn,city,tax_rates=None):
    rates=tax_rates or {}
    owner=conn.execute('SELECT faction FROM cities WHERE name=?',(city,)).fetchone()
    faction=owner[0] if owner else None
    rate=tax_number(rates.get(faction))
    result=[]
    try:
        history=conn.execute("SELECT status FROM map_intrigue_captures WHERE city=? AND status IN ('spare','plunder') ORDER BY id DESC LIMIT 1",(city,)).fetchone()
        plundered=bool(conn.execute("SELECT 1 FROM map_intrigue_captures WHERE city=? AND status='plunder' LIMIT 1",(city,)).fetchone())
    except sqlite3.OperationalError:history=None;plundered=False
    if plundered:
        result.append(('Хозяин лавки','После разграбления у людей забрали сбережения. Красивым обещаниям правителя больше не верят: сначала пусть вернёт городу спокойную жизнь.'))
        result.append(('Соседка','Мой дом разграбили. Даже если подати снизят, забыть это сразу не получится.'))
    if history and history[0]=='spare':
        result.append(('Староста','При взятии города правитель запретил грабить наши дома. Люди запомнили пощаду — может, с новой властью удастся наладить жизнь.'))
    if rate is not None and rate>=35:
        lower=[name for tax,name in sorted((tax_number(rates.get(owner)),name)
               for name,owner in conn.execute('SELECT name,faction FROM cities')
               if name!=city and tax_number(rates.get(owner)) is not None and tax_number(rates.get(owner))<rate)]
        destination='Говорят, города «'+'», «'.join(lower[:2])+'» берут меньше податей. ' if lower else 'Надо разузнать, в каких городах подати ниже. '
        result.extend([
            ('Ремесленник','Такие налоги выгоняют людей из города. Правитель собирает всё больше, а соседние дома пустеют.'),
            ('Горожанка',destination+'Как бы уехать туда всей семьёй, пока ещё есть на что?')])
    elif rate is not None and rate<25:
        result.extend([
            ('Каменщик','При таких небольших налогах можно откладывать на свой дом. Уже присматриваю участок — хочется остаться здесь надолго.'),
            ('Горожанка','Напишу родным, пусть перебираются к нам. Правитель оставляет людям достаточно на жизнь, и детям будет где расти.')])
        if plundered:result.append(('Хозяин лавки','Низкие подати дают надежду, но доверие после грабежа придётся заслужить заново.'))
    else:
        result.extend([
            ('Купец','Смотрю, какие здесь перспективы: будет ли работа, оживёт ли торговля? В других городах тоже обещают перемены.'),
            ('Путник','Пока остаёмся. Посмотрим, как правитель распорядится доходами города, а там решим, где семье будет лучше.')])
    return result
