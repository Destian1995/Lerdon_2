"""Optional disappearance cases: persistent clues, seasonal hunt, one companion."""
import json
import random
import sqlite3
from city_war import current_turn
from faction_seasons import stat_percent

SEASONS=('Зима','Весна','Лето','Осень')
# The acceptance-season multiplier follows the player's faction rules.
MONSTER_ATTACK=260_000_000
MONSTER_DEFENSE=310_000_000
COOLDOWN=15
PREFIX='Спутник: '
NOBLES={
    'Север':('Ярл Эйрик','Леди Сигрид','Тан Хальвард','Леди Ингрид','Ярл Торвальд','Тан Астрид'),
    'Элины':('Эмир Азар','Леди Самира','Визирь Надир','Леди Лейла','Эмир Фарид','Леди Зарифа'),
    'Адепты':('Барон Ренар','Леди Аделина','Граф Северан','Леди Изольда','Барон Годфрид','Леди Беатрис'),
    'Вампиры':('Граф Валериан','Леди Мирцелла','Барон Равен','Леди Эвелина','Граф Корвин','Леди Серафина'),
    'Эльфы':('Князь Эларион','Леди Лиора','Лорд Тириэль','Леди Сильвана','Князь Аэлиндор','Леди Нимриэль'),
}
CRESTS=('серебряный ворон','золотая лилия','белый олень','чёрная луна','алый грифон','синий змей')
MARKS=('треугольная печать','круглая печать','овальная печать','ромбовидная печать','квадратная печать','звёздчатая печать')
STORIES=(
    dict(key='silk',tier=2,title='Нити исчезновений',
         premise='Жители пропадают после заката. На запертых изнутри дверях остаются серебристые нити.',
         witness='Сторож видел придворную карету у ткацкой мастерской. На дверце был герб',
         clue='В коконах найдены приглашения на дворянский приём. На воске сохранилась личная печать'),
    dict(key='well',tier=3,title='Голоса под колодцем',
         premise='У городского колодца находят пустые вёдра. Люди, пришедшие за водой, не возвращаются.',
         witness='Водоноша заметил у колодца придворного в плаще. На застёжке был герб',
         clue='Под колодцем найдены приказы о тайной доставке жителей. На каждом приказе одна личная печать'),
    dict(key='quarry',tier=5,title='Долг каменной жилы',
         premise='Каменщики исчезают по одному. На местах пропажи лежат обломки чёрного камня.',
         witness='Подмастерье видел, как хозяин придворной кареты уводил каменщиков в закрытую шахту. На карете был герб',
         clue='В шахте найден список жертв, составленный под видом рабочего наряда. На нём личная печать'),
    dict(key='crypt',tier=4,title='Похоронный список',
         premise='Писарь находит имена живых жителей в погребальной книге. Наутро эти люди исчезают.',
         witness='Могильщик видел дворянина, выходившего из запертого склепа. На кольце был герб',
         clue='В погребальной книге обнаружены распоряжения о ещё живых горожанах. Их заверяет личная печать'),
    dict(key='frost',tier=6,title='Следы на пустой улице',
         premise='На мостовой остаются ледяные следы даже в тёплую погоду. Жители исчезают возле северных ворот.',
         witness='Стражник видел придворного, после которого на мостовой остался иней. На его плаще был герб',
         clue='У северных ворот найдены ложные охранные грамоты для пропавших караванщиков. На них личная печать'),
    dict(key='mirror',tier=7,title='Те, кто не отражается',
         premise='Горожане замечают знакомых без отражений. Затем исчезают и двойники, и настоящие люди.',
         witness='Зеркальщик видел при дворе человека, отражение которого запаздывало. На его трости был герб',
         clue='На обороте зеркала найден договор о подмене горожан двойниками. Под ним личная печать'),
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
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_companion_forms(
        unit_name TEXT PRIMARY KEY,faction TEXT NOT NULL,case_id INTEGER NOT NULL,
        base_attack INTEGER NOT NULL,base_defense INTEGER NOT NULL,form TEXT NOT NULL)''')


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
        names=generator.sample(NOBLES[faction],3)
        crest,other_crest=generator.sample(CRESTS,2);mark,other_mark=generator.sample(MARKS,2)
        culprit=generator.randrange(3);others=[i for i in range(3) if i!=culprit]
        nobles=[dict(name=n,crest=crest,mark=mark) for n in names]
        nobles[others[0]]['mark']=other_mark;nobles[others[1]]['crest']=other_crest
        story.update(nobles=nobles,culprit=culprit,revealed=False,cleared=[],
                     witness=story['witness']+': '+crest+'.',clue=story['clue']+': '+mark+'.')
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
        if case['stage']==0:return story['witness']
        return story['clue']+(' Сопоставьте две улики с дворянским реестром.' if story.get('nobles') else ' Логово найдено: '+story['monster']+'.')


def revealed(case):
    # Already discovered monsters in older campaigns stay discovered.
    return json.loads(case['scenario']).get('revealed',True)


def accuse(conn,faction,name):
    import otherworlds as worlds
    with worlds.atomic(conn):
        _,city=worlds._party_city(conn,faction);case=state(conn,faction)
        if not case or case['stage']!=2 or city['id']!=case['city_id'] or identified(case):
            raise ValueError('Соберите обе улики и предъявите обвинение в городе расследования.')
        story=json.loads(case['scenario']);names=[n['name'] for n in story['nobles']]
        if name not in names or name in story.get('cleared',[]):raise ValueError('Выберите ещё не оправданного дворянина.')
        if names.index(name)!=story['culprit']:
            story.setdefault('cleared',[]).append(name)
            message='Обвинение ошибочно: герб и печать этого дворянина не совпадают с обеими уликами. Сравните реестр ещё раз.'
        else:
            story['identified']=True
            message=name+' признаёт, что стоит за исчезновениями, но сохраняет человеческий облик. «Я стану вашим союзником в обмен на душу. Откажетесь — увидите мою истинную сущность». Победить в кампании нужно за 30 ходов после сделки.'
        conn.execute('UPDATE portal_monster_cases SET scenario=? WHERE id=?',(json.dumps(story,ensure_ascii=False),case['id']))
        return message


def identified(case):
    story=json.loads(case['scenario'])
    return story.get('identified',False) or revealed(case)


def noble_name(case):
    story=json.loads(case['scenario'])
    return story['nobles'][story['culprit']]['name'] if story.get('nobles') else 'Дворянин Зазеркалья'


def noble_image(case):
    from otherworld_themes import theme
    name=noble_name(case)
    story=json.loads(case['scenario'])
    gender=story.get('companion_gender') or ('lady' if name.startswith('Леди') or name.endswith('Астрид') else 'lord')
    return 'files/otherworld/companions/'+theme(case['faction'])['key']+'/noble-'+gender+'.jpg'


def reject_soul(conn,faction):
    import otherworlds as worlds
    with worlds.atomic(conn):
        _,city=worlds._party_city(conn,faction);case=state(conn,faction)
        if not case or case['stage']!=2 or city['id']!=case['city_id'] or not identified(case) or revealed(case):
            raise ValueError('Сначала разоблачите дворянина и выслушайте предложение.')
        story=json.loads(case['scenario']);story['revealed']=True
        conn.execute('UPDATE portal_monster_cases SET scenario=? WHERE id=?',(json.dumps(story,ensure_ascii=False),case['id']))
        return noble_name(case)+' сбрасывает человеческий облик. Перед вами '+story['monster']+'. Сделка отвергнута — приготовьтесь к бою.'


def monster(case):
    story=json.loads(case['scenario']);tier,variant=story['tier'],story['variant']
    image=f'files/map/monsters/monster_{tier}'+(f'_{variant}' if variant!=1 else '')+'.png'
    multiplier=stat_percent(case['faction'],case['season'])
    attack,defense=MONSTER_ATTACK*multiplier//100,MONSTER_DEFENSE*multiplier//100
    return dict(unit_name=story['monster'],unit_count=1,initial_count=1,unit_image=image,
                unit_class='1',attack=attack,defense=defense,durability=0,unit_type='beast',
                initiative=50,morale=100,crit_chance=5,
                units_stats={'Урон':attack,'Защита':defense,'Живучесть':0,'Класс юнита':'1','Тип':'beast'})


def _award(conn,faction,party,case,hero,attack,defense,noble=False):
    from otherworld_content import FACTION_UNIT_TYPES
    from terrain_journeys import _credit
    name=PREFIX+(noble_name(case) if noble else json.loads(case['scenario'])['monster'])+' / '+faction+' #'+str(case['id'])
    image=noble_image(case) if noble else monster(case)['unit_image']
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
        if not case or case['stage']!=2 or case['city_id']!=city['id'] or not identified(case) or revealed(case):
            raise ValueError('Сделка доступна после верного обвинения, пока дворянин не раскрыл сущность.')
        if hero not in heroes(conn,party['camp'],faction):raise ValueError('Приведите выбранного героя в отряд.')
        if pact(conn,faction):raise ValueError('Душа уже обещана. Повторная сделка не продлевает срок.')
        now=current_turn(conn);enemy=monster(case)
        companion=_award(conn,faction,party,case,hero,enemy['attack'],enemy['defense'],noble=True)
        conn.execute('INSERT INTO portal_soul_pacts VALUES(?,?,?,?)',(faction,case['id'],now,now+30))
        conn.execute('INSERT INTO portal_companion_forms VALUES(?,?,?,?,?,?)',
                     (companion['name'],faction,case['id'],enemy['attack'],enemy['defense'],'noble'))
        companion=set_form(conn,faction,'noble')
    return companion


def companion_form(conn,faction):
    ensure_schema(conn)
    cursor=conn.execute('''SELECT f.* FROM portal_companion_forms f JOIN portal_soul_pacts p
        ON p.faction=f.faction AND p.case_id=f.case_id WHERE f.faction=?''',(faction,))
    row=cursor.fetchone()
    if row:
        data=dict(zip((c[0] for c in cursor.description),row))
        if data['form']=='noble':
            case_cursor=conn.execute('SELECT * FROM portal_monster_cases WHERE id=? AND faction=?',(data['case_id'],faction))
            case_row=case_cursor.fetchone()
            if case_row:
                case=dict(zip((c[0] for c in case_cursor.description),case_row));image=noble_image(case)
                conn.execute('UPDATE units SET image_path=? WHERE unit_name=? AND faction=? AND image_path IS NOT ?',
                             (image,data['unit_name'],faction,image))
                conn.execute('UPDATE garrisons SET unit_image=? WHERE unit_name=? AND unit_image IS NOT ?',
                             (image,data['unit_name'],image))
        return data
    # Existing campaigns may already contain a pact made before forms existed.
    old=conn.execute('''SELECT c.reward_unit,c.id,u.attack,u.defense FROM portal_soul_pacts p
        JOIN portal_monster_cases c ON c.id=p.case_id AND c.faction=p.faction
        JOIN units u ON u.unit_name=c.reward_unit AND u.faction=c.faction
        WHERE p.faction=? AND EXISTS(SELECT 1 FROM garrisons g
        WHERE g.unit_name=u.unit_name AND g.unit_count>0)''',(faction,)).fetchone()
    if old:
        from otherworlds import atomic
        with atomic(conn):
            conn.execute('INSERT INTO portal_companion_forms VALUES(?,?,?,?,?,?)',
                         (old[0],faction,old[1],old[2],old[3],'noble'))
            set_form(conn,faction,'noble')
        return companion_form(conn,faction)
    return None


def set_form(conn,faction,form):
    import otherworlds as worlds
    if form not in ('noble','monster'):raise ValueError('Неизвестный облик спутника.')
    with worlds.atomic(conn):
        data=companion_form(conn,faction)
        if not data or not conn.execute('SELECT 1 FROM garrisons WHERE unit_name=? AND unit_count>0',(data['unit_name'],)).fetchone():
            raise ValueError('Спутника больше нет в вашем войске.')
        cursor=conn.execute('SELECT * FROM portal_monster_cases WHERE id=? AND faction=?',(data['case_id'],faction))
        case=dict(zip((c[0] for c in cursor.description),cursor.fetchone()))
        attack=data['base_attack']*(3 if form=='noble' else 1)//2
        defense=data['base_defense']*(1 if form=='noble' else 3)//2
        image=noble_image(case) if form=='noble' else monster(case)['unit_image']
        conn.execute('UPDATE units SET attack=?,defense=?,image_path=? WHERE unit_name=? AND faction=?',
                     (attack,defense,image,data['unit_name'],faction))
        conn.execute('UPDATE garrisons SET unit_image=? WHERE unit_name=?',(image,data['unit_name']))
        conn.execute('UPDATE portal_companion_forms SET form=? WHERE unit_name=?',(form,data['unit_name']))
        return dict(name=data['unit_name'],attack=attack,defense=defense,image=image,form=form)


def choose_gender(conn,faction,gender):
    import otherworlds as worlds
    if gender not in ('lord','lady'):raise ValueError('Выберите дворянина или дворянку.')
    with worlds.atomic(conn):
        data=companion_form(conn,faction)
        if not data:raise ValueError('Выбор доступен после продажи души.')
        cursor=conn.execute('SELECT * FROM portal_monster_cases WHERE id=?',(data['case_id'],))
        row=cursor.fetchone();case=dict(zip((c[0] for c in cursor.description),row))
        story=json.loads(case['scenario']);story['companion_gender']=gender
        conn.execute('UPDATE portal_monster_cases SET scenario=? WHERE id=?',(json.dumps(story,ensure_ascii=False),case['id']))
        return set_form(conn,faction,data['form'])


def fight(conn,faction,hero,skirmish=None):
    import otherworlds as worlds
    with worlds.atomic(conn):
        party,city=worlds._party_city(conn,faction);case=state(conn,faction)
        if not case or case['stage']!=2 or case['city_id']!=city['id'] or not revealed(case):
            raise ValueError('Сначала разоблачите дворянина-монстра в городе расследования.')
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
