"""Optional disappearance cases: persistent clues, seasonal hunt, one companion."""
import json
import random
import sqlite3
from city_war import current_turn

SEASONS=('Зима','Весна','Лето','Осень')
# Percent multipliers fixed at acceptance: winter strongest, summer weakest.
MONSTER_ATTACK=260_000_000
MONSTER_DEFENSE=310_000_000
SEASON_POWER=(400,100,5,200)
COOLDOWN=15
PREFIX='Спутник: '
STORIES=(
    dict(key='silk',tier=2,title='Нити исчезновений',
         premise='Жители пропадают после заката. На запертых изнутри дверях остаются серебристые нити.',
         witness='Сторож видел, как человек в белом шёлке уводил соседей к заброшенной ткацкой мастерской.',
         clue='В мастерской найдены коконы и заказ купца на живой шёлк. Купец вырастил чудовище, которое вышло из-под контроля.'),
    dict(key='well',tier=3,title='Голоса под колодцем',
         premise='У городского колодца находят пустые вёдра. Люди, пришедшие за водой, не возвращаются.',
         witness='Водоноша слышал из глубины голоса пропавших. Вода стала горькой после вскрытия старого водостока.',
         clue='В водостоке найдены следы яда. Алхимик слил туда неудачный эликсир и пробудил тварь, приманивающую людей голосами.'),
    dict(key='quarry',tier=5,title='Долг каменной жилы',
         premise='Каменщики исчезают по одному. На местах пропажи лежат обломки чёрного камня.',
         witness='Подмастерье рассказал о сияющей жиле, которую вскрыли ради нового городского моста.',
         clue='Кирки покрыты знаками древней печати. Добытчики разбили её и освободили стража, который забирает жизненную силу рабочих.'),
    dict(key='crypt',tier=4,title='Похоронный список',
         premise='Писарь находит имена живых жителей в погребальной книге. Наутро эти люди исчезают.',
         witness='Могильщик видел огонь в закрытом склепе. Пропажи начались после кражи погребального медальона.',
         clue='В склепе найден похищенный медальон. Скупщик вскрыл его и выпустил сущность, записывающую будущих жертв в книгу.'),
    dict(key='frost',tier=6,title='Следы на пустой улице',
         premise='На мостовой остаются ледяные следы даже в тёплую погоду. Жители исчезают возле северных ворот.',
         witness='Торговец привёз запечатанный сундук из ледяной пещеры. После его открытия пропал весь караван.',
         clue='В сундуке была украденная реликвия зимнего логова. Её хозяин пришёл по следу и теперь охотится на горожан.'),
    dict(key='mirror',tier=7,title='Те, кто не отражается',
         premise='Горожане замечают знакомых без отражений. Затем исчезают и двойники, и настоящие люди.',
         witness='Зеркальщик слышал зов из большого зеркала, заказанного для городской ратуши.',
         clue='За зеркалом обнаружен разлом. Мастер пытался вернуть погибшую дочь, но открыл дорогу хищнику, питающемуся чужими жизнями.'),
)


def ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_monster_cases(
        id INTEGER PRIMARY KEY AUTOINCREMENT,faction TEXT NOT NULL,stage INTEGER NOT NULL DEFAULT 0,
        city_id INTEGER NOT NULL,season INTEGER NOT NULL,accepted_turn INTEGER NOT NULL,
        scenario TEXT NOT NULL,attack_bonus INTEGER NOT NULL,defense_bonus INTEGER NOT NULL,
        hero TEXT,reward_unit TEXT,finished_turn INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_soul_pacts(
        faction TEXT PRIMARY KEY,case_id INTEGER NOT NULL,signed_turn INTEGER NOT NULL,
        deadline INTEGER NOT NULL)''')


def pact(conn,faction):
    try:
        row=conn.execute('SELECT case_id,signed_turn,deadline FROM portal_soul_pacts WHERE faction=?',(faction,)).fetchone()
    except sqlite3.OperationalError:return None
    return dict(zip(('case_id','signed_turn','deadline'),row)) if row else None


def soul_loss_reason(conn,faction):
    deal=pact(conn,faction)
    if deal and current_turn(conn)>=deal['deadline']:
        return 'Срок сделки за душу истёк: вы не победили за 30 ходов. Монстр забрал вашу душу. Поражение! Звание не присваивается.'
    return ''


def deadline_caption(conn,faction):
    deal=pact(conn,faction)
    return 'Душа: '+str(max(0,deal['deadline']-current_turn(conn)))+' х.' if deal else ''


def state(conn,faction):
    ensure_schema(conn)
    cursor=conn.execute('SELECT * FROM portal_monster_cases WHERE faction=? ORDER BY id DESC LIMIT 1',(faction,))
    row=cursor.fetchone()
    return dict(zip((c[0] for c in cursor.description),row)) if row else None


def heroes(conn,camp,faction):
    return [r[0] for r in conn.execute('''SELECT DISTINCT u.unit_name FROM units u
        JOIN garrisons g ON g.unit_name=u.unit_name WHERE g.city_name=? AND u.faction=?
        AND CAST(u.unit_class AS INTEGER) IN (2,3) AND g.unit_count>0 ORDER BY u.unit_name''',(camp,faction))]


def season(conn):
    try:
        row=conn.execute('SELECT season_index FROM season WHERE id=1').fetchone()
    except sqlite3.OperationalError:row=None
    if not row or row[0] not in range(4):
        raise ValueError('Сезон ещё не определён. Завершите загрузку игры.')
    return int(row[0])


def begin(conn,faction,rng=None):
    import otherworlds as worlds
    from monster_sites import VARIANT_NAMES
    ensure_schema(conn)
    generator=rng or random
    with worlds.atomic(conn):
        party,_=worlds._party_city(conn,faction)
        if not heroes(conn,party['camp'],faction):raise ValueError('Приведите в отряд героя 2 или 3 класса.')
        old=state(conn,faction)
        if old and (old['stage']<3 or current_turn(conn)<old['finished_turn']+COOLDOWN):
            raise ValueError('Расследование уже идёт или новое дело ещё не появилось.')
        used={json.loads(r[0])['key'] for r in conn.execute('SELECT scenario FROM portal_monster_cases WHERE faction=?',(faction,))}
        pool=[s for s in STORIES if s['key'] not in used] or list(STORIES)
        if old and len(pool)>1:pool=[s for s in pool if s['key']!=json.loads(old['scenario'])['key']]
        story=dict(generator.choice(pool));story['variant']=generator.randint(1,5)
        story['monster']=VARIANT_NAMES[story['tier']-1][story['variant']-1]
        towns=[c for c in worlds.cities(conn,faction) if c['id']!=1]
        city=generator.choice(towns)
        conn.execute('''INSERT INTO portal_monster_cases(faction,city_id,season,accepted_turn,
            scenario,attack_bonus,defense_bonus) VALUES(?,?,?,?,?,?,?)''',
            (faction,city['id'],season(conn),current_turn(conn),json.dumps(story,ensure_ascii=False),
             generator.randint(142,271),generator.randint(142,271)))
    return 'Дело принято: «'+story['title']+'». Расследуйте исчезновения: '+city['name']+'.'


def investigate(conn,faction):
    import otherworlds as worlds
    with worlds.atomic(conn):
        _,city=worlds._party_city(conn,faction);case=state(conn,faction)
        if not case or case['stage'] not in (0,1) or city['id']!=case['city_id']:
            raise ValueError('Расследуйте дело в указанном городе.')
        story=json.loads(case['scenario'])
        conn.execute('UPDATE portal_monster_cases SET stage=stage+1 WHERE id=?',(case['id'],))
        return story['witness'] if case['stage']==0 else story['clue']+' Логово найдено: '+story['monster']+'.'


def monster(case):
    story=json.loads(case['scenario']);tier,variant=story['tier'],story['variant']
    image=f'files/map/monsters/monster_{tier}'+(f'_{variant}' if variant!=1 else '')+'.png'
    multiplier=SEASON_POWER[case['season']]
    attack,defense=MONSTER_ATTACK*multiplier//100,MONSTER_DEFENSE*multiplier//100
    return dict(unit_name=story['monster'],unit_count=1,initial_count=1,unit_image=image,
                unit_class='1',attack=attack,defense=defense,durability=0,unit_type='beast',
                initiative=50,morale=100,crit_chance=5,
                units_stats={'Урон':attack,'Защита':defense,'Живучесть':0,'Класс юнита':'1','Тип':'beast'})


def _award(conn,faction,party,case,hero,attack,defense):
    from otherworld_content import FACTION_UNIT_TYPES
    from terrain_journeys import _credit
    name=PREFIX+json.loads(case['scenario'])['monster']+' / '+faction+' #'+str(case['id'])
    image=monster(case)['unit_image']
    data=dict(faction=faction,unit_name=name,cost_money=0,cost_time=0,image_path=image,
              attack=attack,defense=defense,durability=0,unit_class='1',consumption=0,
              unit_type=FACTION_UNIT_TYPES[faction],initiative=50,morale=100,crit_chance=5)
    columns={r[1] for r in conn.execute('PRAGMA table_info(units)')}
    data={k:v for k,v in data.items() if k in columns}
    conn.execute('INSERT INTO units('+','.join(data)+') VALUES('+','.join('?' for _ in data)+')',tuple(data.values()))
    _credit(conn,party['camp'],name,1,image)
    conn.execute('UPDATE portal_monster_cases SET stage=3,hero=?,reward_unit=?,finished_turn=? WHERE id=?',
                 (hero,name,current_turn(conn),case['id']))
    return dict(name=name,attack=attack,defense=defense,image=image)


def sell_soul(conn,faction,hero):
    import otherworlds as worlds
    ensure_schema(conn)
    with worlds.atomic(conn):
        party,city=worlds._party_city(conn,faction);case=state(conn,faction)
        if not case or case['stage']!=2 or case['city_id']!=city['id']:
            raise ValueError('Сначала найдите логово в городе расследования.')
        if hero not in heroes(conn,party['camp'],faction):raise ValueError('Приведите выбранного героя в отряд.')
        if pact(conn,faction):raise ValueError('Душа уже обещана. Повторная сделка не продлевает срок.')
        now=current_turn(conn);enemy=monster(case)
        companion=_award(conn,faction,party,case,hero,enemy['attack'],enemy['defense'])
        conn.execute('INSERT INTO portal_soul_pacts VALUES(?,?,?,?)',(faction,case['id'],now,now+30))
    return companion


def fight(conn,faction,hero,skirmish=None):
    import otherworlds as worlds
    with worlds.atomic(conn):
        party,city=worlds._party_city(conn,faction);case=state(conn,faction)
        if not case or case['stage']!=2 or case['city_id']!=city['id']:
            raise ValueError('Сначала найдите логово в городе расследования.')
        if hero not in heroes(conn,party['camp'],faction):raise ValueError('Выберите героя 2 или 3 класса из этого отряда.')
        result=worlds.fight_guards(conn,faction,skirmish=skirmish,encounter=monster(case))
        result['hero']=hero;result['companion']=None
        if result['won']:
            # Tenths of a percent, integer arithmetic: no rounding drift or rerolls.
            attack=100_000_000*(1000+case['attack_bonus'])//1000
            defense=100_000_000*(1000+case['defense_bonus'])//1000
            result['companion']=_award(conn,faction,party,case,hero,attack,defense)
        return result


def objectives(conn,faction):
    case=state(conn,faction)
    return {case['city_id']} if case and case['stage']<3 else set()
