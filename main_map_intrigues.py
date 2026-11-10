"""Persistent main-map plots. Choices are atomic; UI never invents rewards.

The caller commits. Nothing in this module moves armies or bypasses a battle.
"""
from contextlib import contextmanager
import random
import sqlite3
from city_war import current_turn

TABLES=('map_intrigue_offers','map_intrigue_captures','map_city_secrets',
        'map_companion_temper','map_intrigue_log','map_intrigue_turns')
SECRET_TEXT={
    'factory':('Цена кристаллов',
        'На фабрику по ночам привозят закрытые повозки. Рабочим запрещено спускаться в нижние цеха.',
        'В расчётных книгах вместо жалованья указаны номера заключённых.',
        'Кристаллы добывают пленники. Управляющий предлагает вам долю в обмен на молчание.'),
    'hospital':('Тихие палаты',
        'Больница рапортует об успехах, но семьи неделями не могут увидеть пациентов.',
        'Лекарь тайно передал список заражённых, которых записали выздоровевшими.',
        'Лекари скрывают заражение и собирают плату за лечение. Можно поощрить этот доход или раскрыть обман и направить средства на производство.'),
    'tribute':('Дань за тишину',
        'Каждое новолуние у городских ворот оставляют сундук. Стража в эту ночь уходит со стен.',
        'На старой расписке стоит знак Зазеркалья. Данью город покупает безопасность караванов.',
        'Караван везёт дань существам Зазеркалья. Можно перехватить его и ограбить либо раскрыть сговор и арестовать организаторов.'),
}
# (crowns, crystals, population growth), local percentages, never upkeep.
CITY_POLICIES={
    ('factory','exploit'):(0,15,-15),('factory','expose'):(0,-25,25),
    ('hospital','exploit'):(35,-35,0),('hospital','expose'):(-35,35,0),
}


def exists(conn,table):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())


def ensure_schema(conn):
    statements=(
        '''CREATE TABLE IF NOT EXISTS map_intrigue_offers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,faction TEXT NOT NULL,city TEXT NOT NULL,
            enemy TEXT NOT NULL,noble TEXT NOT NULL,condition TEXT NOT NULL,ally TEXT,
            price INTEGER NOT NULL,created INTEGER NOT NULL,deadline INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'offered',resolved_turn INTEGER NOT NULL DEFAULT -1)''',
        '''CREATE TABLE IF NOT EXISTS map_intrigue_captures(
            id INTEGER PRIMARY KEY AUTOINCREMENT,faction TEXT NOT NULL,city TEXT NOT NULL,
            revision INTEGER NOT NULL,offer_id INTEGER,status TEXT NOT NULL DEFAULT 'pending',
            UNIQUE(faction,city,revision))''',
        '''CREATE TABLE IF NOT EXISTS map_city_secrets(
            faction TEXT NOT NULL,city TEXT NOT NULL,kind TEXT NOT NULL,stage INTEGER NOT NULL DEFAULT 0,
            last_turn INTEGER NOT NULL DEFAULT -1,resolution TEXT,until_turn INTEGER NOT NULL DEFAULT -1,
            PRIMARY KEY(faction,city))''',
        '''CREATE TABLE IF NOT EXISTS map_companion_temper(
            unit_name TEXT PRIMARY KEY,faction TEXT NOT NULL,loyalty INTEGER NOT NULL DEFAULT 60,
            blood INTEGER NOT NULL DEFAULT 0,conflict_until INTEGER NOT NULL DEFAULT -1)''',
        '''CREATE TABLE IF NOT EXISTS map_intrigue_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,faction TEXT NOT NULL,event_turn INTEGER NOT NULL,
            message TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS map_intrigue_turns(faction TEXT PRIMARY KEY,last_turn INTEGER NOT NULL)''',
    )
    for sql in statements:conn.execute(sql)
    for table,name,declaration in (
        ('map_city_secrets','economy_version','INTEGER NOT NULL DEFAULT 0'),
        ('map_city_secrets','policy_active','INTEGER NOT NULL DEFAULT 0'),
        ('map_companion_temper','departed','INTEGER NOT NULL DEFAULT 0'),
        ('map_companion_temper','base_attack','REAL'),
        ('map_companion_temper','base_defense','REAL')):
        if name not in {r[1] for r in conn.execute('PRAGMA table_info('+table+')')}:
            conn.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+declaration)
    # Upgrade old decisions without repeating their historical one-off payouts.
    conn.execute('''UPDATE map_city_secrets SET economy_version=2,
        policy_active=CASE WHEN kind IN ('factory','hospital') AND resolution IN ('expose','exploit')
            AND EXISTS(SELECT 1 FROM cities c WHERE c.name=city AND c.faction=map_city_secrets.faction)
            THEN 1 ELSE 0 END WHERE economy_version=0''')
    conn.execute('''CREATE TRIGGER IF NOT EXISTS intrigue_policy_capture_reset
        AFTER UPDATE OF faction ON cities WHEN OLD.faction IS NOT NEW.faction
        BEGIN UPDATE map_city_secrets SET policy_active=0 WHERE city=NEW.name; END''')


@contextmanager
def action(conn):
    ensure_schema(conn)
    conn.execute('SAVEPOINT main_map_choice')
    try:
        yield
        conn.execute('RELEASE main_map_choice')
    except Exception:
        conn.execute('ROLLBACK TO main_map_choice');conn.execute('RELEASE main_map_choice')
        raise


def _dicts(conn,sql,args=()):
    cursor=conn.execute(sql,args);names=[d[0] for d in cursor.description]
    return [dict(zip(names,row)) for row in cursor.fetchall()]


def owner(conn,city):
    row=conn.execute('SELECT faction FROM cities WHERE name=?',(city,)).fetchone()
    return row[0] if row else None


def _player(conn):
    if not exists(conn,'user_faction'):return None
    row=conn.execute('SELECT faction_name FROM user_faction LIMIT 1').fetchone()
    return row[0] if row else None


def _relation(conn,a,b,status):
    return exists(conn,'diplomacies') and bool(conn.execute('''SELECT 1 FROM diplomacies
        WHERE ((faction1=? AND faction2=?) OR (faction1=? AND faction2=?)) AND relationship=?''',
        (a,b,b,a,status)).fetchone())


def _log(conn,faction,text):
    conn.execute('INSERT INTO map_intrigue_log(faction,event_turn,message) VALUES(?,?,?)',
                 (faction,current_turn(conn),text))


def _pay(conn,faction,resource,amount):
    from utils.resource_payments import ensure_resource_schema
    ensure_resource_schema(conn)
    changed=conn.execute('UPDATE resources SET amount=amount-? WHERE faction=? AND resource_type=? AND amount>=?',
                         (amount,faction,resource,amount)).rowcount
    if changed!=1:raise ValueError('Недостаточно ресурсов: '+resource+'.')


def _credit(conn,faction,resource,amount):
    from utils.resource_payments import ensure_resource_schema
    from utils.resource_caps import caps
    ensure_resource_schema(conn)
    limit=caps(conn,faction).get(resource,100_000_000)
    conn.execute('UPDATE resources SET amount=MIN(?,amount+?) WHERE faction=? AND resource_type=?',
                 (limit,amount,faction,resource))


def companion_multiplier(conn,faction,name,form):
    if not exists(conn,'map_companion_temper'):return 1
    row=conn.execute('SELECT loyalty,blood,conflict_until FROM map_companion_temper WHERE faction=? AND unit_name=?',
                     (faction,name)).fetchone()
    if not row:return 1
    return 1+row[1]*.05 if form=='monster' else (.75 if row[2]>current_turn(conn) else 1)


def _refresh_companion(conn,faction):
    import mirror_monster_quest as hunt
    data=hunt.companion_form(conn,faction) if exists(conn,'portal_companion_forms') else None
    if data and conn.execute('SELECT 1 FROM garrisons WHERE unit_name=? AND unit_count>0',(data['unit_name'],)).fetchone():
        hunt.set_form(conn,faction,data['form'])
    if not exists(conn,'map_companion_temper'):return
    for row in _dicts(conn,'SELECT * FROM map_companion_temper WHERE faction=? AND departed=0 AND base_attack IS NOT NULL',(faction,)):
        if row['unit_name'] not in surviving_companions(conn,faction):continue
        if data and data['unit_name']==row['unit_name']:continue
        factor=1+row['blood']*.05
        conn.execute('UPDATE units SET attack=?,defense=? WHERE unit_name=? AND faction=?',
                     (int(row['base_attack']*factor),int(row['base_defense']*factor),row['unit_name'],faction))


def surviving_companions(conn,faction):
    if not exists(conn,'units') or not exists(conn,'garrisons'):return []
    return [r[0] for r in conn.execute('''SELECT u.unit_name FROM units u WHERE u.faction=?
        AND u.unit_name LIKE 'Спутник: %' AND EXISTS(SELECT 1 FROM garrisons g
        WHERE g.unit_name=u.unit_name AND g.unit_count>0)''',(faction,))]


def react(conn,faction,mercy):
    """Only explicit player choices affect the actual surviving companion."""
    for name in surviving_companions(conn,faction):
        conn.execute('INSERT OR IGNORE INTO map_companion_temper(unit_name,faction) VALUES(?,?)',(name,faction))
        has_form=exists(conn,'portal_companion_forms') and conn.execute('SELECT 1 FROM portal_companion_forms WHERE unit_name=?',(name,)).fetchone()
        if not has_form:
            conn.execute('''UPDATE map_companion_temper SET base_attack=COALESCE(base_attack,(SELECT attack FROM units WHERE unit_name=?)),
                base_defense=COALESCE(base_defense,(SELECT defense FROM units WHERE unit_name=?)) WHERE unit_name=?''',(name,name,name))
        loyalty,blood,until=conn.execute('SELECT loyalty,blood,conflict_until FROM map_companion_temper WHERE unit_name=?',(name,)).fetchone()
        loyalty=max(0,min(100,loyalty+(10 if mercy else -20)))
        blood=max(0,min(5,blood+(-1 if mercy else 1)))
        if loyalty==0:
            conn.execute('DELETE FROM garrisons WHERE unit_name=?',(name,))
            conn.execute('UPDATE map_companion_temper SET loyalty=0,blood=?,departed=1 WHERE unit_name=?',(blood,name))
            _log(conn,faction,name.split(' / ')[0]+' покидает героя: доверие упало до 0. Спутник больше не служит вам.')
            continue
        if not mercy and loyalty<=20:
            until=current_turn(conn)+3 if has_form else -1
            text=('Спутник осуждает жестокость: дворянский облик −25% к атаке и защите на 3 хода. ' if has_form else 'Спутник перестаёт доверять вам. ')+ 'Ещё один жестокий поступок при доверии 20 заставит его уйти.'
        elif not mercy and loyalty<=40:
            text='Спутник сомневается в вас. Ещё один жестокий поступок приведёт к конфликту. Чудовищная сущность питается жестокостью.'
        else:text='Спутник одобряет милосердие.' if mercy else 'Чудовищная сущность спутника становится сильнее.'
        conn.execute('UPDATE map_companion_temper SET loyalty=?,blood=?,conflict_until=? WHERE unit_name=?',
                     (loyalty,blood,until,name));_log(conn,faction,text)
    _refresh_companion(conn,faction)


def _valid_offer(conn,row):
    return (current_turn(conn)<row['deadline'] and owner(conn,row['city'])==row['enemy']
            and _relation(conn,row['faction'],row['enemy'],'война'))


def advance(conn,faction,rng=None):
    """Once per turn, persist a frontier offer rather than rerolling on load."""
    with action(conn):
        turn=current_turn(conn)
        old=conn.execute('SELECT last_turn FROM map_intrigue_turns WHERE faction=?',(faction,)).fetchone()
        if old and old[0]>=turn:return
        conn.execute('INSERT INTO map_intrigue_turns VALUES(?,?) ON CONFLICT(faction) DO UPDATE SET last_turn=excluded.last_turn',(faction,turn))
        for row in _dicts(conn,"SELECT * FROM map_intrigue_offers WHERE faction=? AND status IN ('offered','accepted')",(faction,)):
            if not _valid_offer(conn,row):
                conn.execute("UPDATE map_intrigue_offers SET status='expired' WHERE id=?",(row['id'],))
                _log(conn,faction,'Тайное предложение в городе '+row['city']+' больше не действует.')
        if exists(conn,'map_companion_temper'):_refresh_companion(conn,faction)
        if turn<3:return
        last=conn.execute('SELECT MAX(created) FROM map_intrigue_offers WHERE faction=?',(faction,)).fetchone()[0]
        if last is not None and turn-last<8:return
        broken=conn.execute("SELECT MAX(resolved_turn) FROM map_intrigue_offers WHERE faction=? AND status='broken'",(faction,)).fetchone()[0]
        if broken is not None and turn-broken<15:return
        if not exists(conn,'roads'):return
        cities={r[0]:(r[1],r[2]) for r in conn.execute('SELECT id,name,faction FROM cities')}
        frontier=set()
        for a,b in conn.execute('SELECT city1,city2 FROM roads'):
            for home,target in ((a,b),(b,a)):
                if home in cities and target in cities and cities[home][1]==faction:
                    city,enemy=cities[target]
                    if enemy in ('Нейтрал','Нежить','Мятежники',faction):continue
                    if _relation(conn,faction,enemy,'война'):frontier.add((city,enemy))
        if not frontier:return
        rng=rng or random.SystemRandom();city,enemy=rng.choice(sorted(frontier))
        from mirror_monster_quest import NOBLES
        if enemy not in NOBLES:return
        allies=sorted({r[0] for r in conn.execute('SELECT DISTINCT faction FROM cities')
                       if r[0] not in (faction,enemy,'Нейтрал','Нежить','Мятежники') and _relation(conn,faction,r[0],'союз')})
        condition=rng.choice(['governor','rescue']+(['betray'] if allies else []))
        ally=rng.choice(allies) if condition=='betray' else None
        price=20_000 if condition=='rescue' else 0
        conn.execute('''INSERT INTO map_intrigue_offers(faction,city,enemy,noble,condition,ally,price,created,deadline)
            VALUES(?,?,?,?,?,?,?,?,?)''',(faction,city,enemy,rng.choice(NOBLES[enemy]),condition,ally,price,turn,turn+5))
        _log(conn,faction,'Из города '+city+' прибыл тайный посланник. Предложение доступно в журнале интриг 5 ходов.')


def accept_offer(conn,faction,offer_id):
    with action(conn):
        rows=_dicts(conn,'SELECT * FROM map_intrigue_offers WHERE id=? AND faction=?',(offer_id,faction))
        if not rows or rows[0]['status']!='offered' or not _valid_offer(conn,rows[0]):raise ValueError('Предложение уже недоступно.')
        row=rows[0]
        if row['condition']=='rescue':_pay(conn,faction,'Кроны',row['price'])
        if row['condition']=='betray':
            if not _relation(conn,faction,row['ally'],'союз'):raise ValueError('Названный союз уже не действует.')
            from morgana_covenant import peace_locked
            if peace_locked(conn,faction,row['ally']):raise ValueError('Эта клятва не допускает смены союза.')
            for a,b in ((faction,row['ally']),(row['ally'],faction)):
                changed=conn.execute("UPDATE diplomacies SET relationship='война' WHERE faction1=? AND faction2=?",(a,b)).rowcount
                if not changed:conn.execute("INSERT INTO diplomacies(faction1,faction2,relationship) VALUES(?,?,'война')",(a,b))
            if exists(conn,'relations'):
                conn.execute('UPDATE relations SET relationship=0 WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)',(faction,row['ally'],row['ally'],faction))
            if exists(conn,'truces'):
                conn.execute('DELETE FROM truces WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)',(faction,row['ally'],row['ally'],faction))
            react(conn,faction,False)
        conn.execute("UPDATE map_intrigue_offers SET status='accepted' WHERE id=?",(offer_id,))
        _log(conn,faction,row['noble']+' обещает саботировать оборону города '+row['city']+': защита гарнизона −50% в одном вашем штурме до истечения срока.')


def reject_offer(conn,faction,offer_id):
    with action(conn):
        if conn.execute("UPDATE map_intrigue_offers SET status='rejected' WHERE id=? AND faction=? AND status='offered'",(offer_id,faction)).rowcount!=1:
            raise ValueError('Предложение уже закрыто.')
        _log(conn,faction,'Вы отказались от тайного соглашения.')


def apply_gate(conn,faction,city,defenders):
    """One sabotage, in the ordinary battle pipeline before either battle mode."""
    if not defenders or not exists(conn,'map_intrigue_offers') or faction!=_player(conn):return False
    rows=_dicts(conn,"SELECT * FROM map_intrigue_offers WHERE faction=? AND city=? AND status='accepted' ORDER BY id DESC",(faction,city))
    row=next((r for r in rows if _valid_offer(conn,r)),None)
    if not row:return False
    conn.execute("UPDATE map_intrigue_offers SET status='used' WHERE id=?",(row['id'],))
    for unit in defenders:
        stats=unit.setdefault('units_stats',{});stats['Защита']=float(stats.get('Защита',0))*.5
    _log(conn,faction,'Ворота города '+city+' открыты заговорщиками. Саботаж применён к этому бою.')
    return True


def captured(conn,city,faction,revision):
    if faction!=_player(conn):return
    ensure_schema(conn)
    if conn.execute('SELECT 1 FROM map_intrigue_captures WHERE faction=? AND city=? AND revision=?',(faction,city,revision)).fetchone():return
    conn.execute("UPDATE map_intrigue_captures SET status='superseded' WHERE faction=? AND city=? AND status='pending'",(faction,city))
    offer=conn.execute("SELECT id FROM map_intrigue_offers WHERE faction=? AND city=? AND deadline>? AND status IN ('accepted','used') ORDER BY id DESC LIMIT 1",(faction,city,current_turn(conn))).fetchone()
    conn.execute('INSERT OR IGNORE INTO map_intrigue_captures(faction,city,revision,offer_id) VALUES(?,?,?,?)',(faction,city,revision,offer[0] if offer else None))
    if offer:conn.execute("UPDATE map_intrigue_offers SET status='captured' WHERE id=?",offer)


def settle_capture(conn,faction,capture_id,choice):
    if choice not in ('spare','plunder'):raise ValueError('Выберите судьбу города.')
    with action(conn):
        rows=_dicts(conn,"SELECT * FROM map_intrigue_captures WHERE id=? AND faction=? AND status='pending'",(capture_id,faction))
        if not rows or owner(conn,rows[0]['city'])!=faction:raise ValueError('Город уже не принадлежит вам или решение принято.')
        row=rows[0];city=row['city'];spare=choice=='spare'
        if not spare:
            _credit(conn,faction,'Кроны',15_000);_credit(conn,faction,'Кристаллы',5_000)
        conn.execute('UPDATE map_intrigue_captures SET status=? WHERE id=?',(choice,capture_id))
        if row['offer_id']:
            conn.execute('UPDATE map_intrigue_offers SET status=?,resolved_turn=? WHERE id=?',('honored' if spare else 'broken',current_turn(conn),row['offer_id']))
            if spare:
                noble,condition=conn.execute('SELECT noble,condition FROM map_intrigue_offers WHERE id=?',(row['offer_id'],)).fetchone()
                _log(conn,faction,noble+(' оставлен наместником города '+city+'.' if condition=='governor' else ': обещание выполнено, жители города '+city+' пощажены.'))
        react(conn,faction,spare)
        _log(conn,faction,city+(': горожане пощажены.' if spare else ': разграблен. Получено до 15 000 крон и 5 000 кристаллов с учётом лимитов.'))
        if row['offer_id'] and not spare:_log(conn,faction,'Обещание заговорщикам нарушено. Уцелевшие дворяне запомнят это: 15 ходов без новых тайных предложений.')


def secret(conn,faction,city):
    ensure_schema(conn)
    row=_dicts(conn,'SELECT * FROM map_city_secrets WHERE faction=? AND city=?',(faction,city))
    return row[0] if row else None


def investigate(conn,faction,city,rng=None):
    with action(conn):
        city_owner=owner(conn,city)
        if city_owner not in (faction,'Нейтрал'):raise ValueError('Поговорить с посетителями можно в своих и нейтральных городах.')
        row=secret(conn,faction,city);turn=current_turn(conn)
        if row and row['stage']>=2 and row['resolution']!='conceal':raise ValueError('Вы уже выслушали этот разговор. Выберите решение или вернитесь позже.')
        if not row:
            buildings={r[0] for r in conn.execute('SELECT building_type FROM buildings WHERE city_name=? AND faction=? AND count>0',(city,city_owner))} if exists(conn,'buildings') else set()
            kinds=['tribute']+(['factory'] if 'Фабрика' in buildings else [])+(['hospital'] if 'Больница' in buildings else [])
            kind=(rng or random.SystemRandom()).choice(kinds or ['tribute']) if city_owner==faction else 'tribute'
            conn.execute('INSERT INTO map_city_secrets(faction,city,kind,stage,last_turn,economy_version) VALUES(?,?,?,2,?,2)',(faction,city,kind,turn))
        else:conn.execute('UPDATE map_city_secrets SET stage=2,resolution=NULL,last_turn=? WHERE faction=? AND city=?',(turn,faction,city))
        row=secret(conn,faction,city)
        _log(conn,faction,city+': '+SECRET_TEXT[row['kind']][row['stage']+1])
        return row


def resolve_secret(conn,faction,city,choice):
    if choice not in ('expose','exploit'):raise ValueError('Выберите решение или закройте таверну, чтобы вернуться позже.')
    with action(conn):
        row=secret(conn,faction,city)
        if not row or row['stage']!=2:raise ValueError('Сначала выслушайте посетителя. Решение принимается один раз.')
        if owner(conn,city) not in (faction,'Нейтрал'):raise ValueError('Вы потеряли доступ к городу.')
        kind=row['kind']
        if kind!='tribute' and owner(conn,city)!=faction:raise ValueError('Для этого решения нужно владеть городом.')
        if kind=='tribute':
            quote=caravan_quote(conn,faction,choice)
            if choice=='exploit':_credit(conn,faction,'Кроны',quote['amount'])
            else:_pay(conn,faction,'Кроны',quote['amount'])
            change_relations(conn,faction,-25 if choice=='exploit' else 5)
        react(conn,faction,choice=='expose')
        conn.execute('UPDATE map_city_secrets SET stage=3,resolution=?,until_turn=-1,economy_version=2,policy_active=? WHERE faction=? AND city=?',
                     (choice,int(kind in ('factory','hospital')),faction,city))
        descriptions={'expose':'обман раскрыт; принято решение в пользу жителей.','exploit':'вы поощрили доход ценой чужого благополучия.'}
        _log(conn,faction,city+': '+descriptions[choice])


def secret_income(conn,faction):
    """Compatibility with older callers: the flat five-turn award is retired."""
    return 0


def caravan_quote(conn,faction,choice):
    from utils.resource_payments import ensure_resource_schema
    from utils.resource_caps import caps
    ensure_resource_schema(conn)
    row=conn.execute("SELECT amount FROM resources WHERE faction=? AND resource_type='Кроны'",(faction,)).fetchone()
    balance=max(0,row[0] or 0) if row else 0
    amount=int(balance*(35 if choice=='exploit' else 10)//100)
    actual=min(amount,max(0,caps(conn,faction)['Кроны']-balance)) if choice=='exploit' else -amount
    return dict(balance=balance,amount=amount,actual=int(actual),after=balance+actual)


def change_relations(conn,faction,delta):
    if not exists(conn,'relations'):
        conn.execute('CREATE TABLE relations(faction1 TEXT,faction2 TEXT,relationship INTEGER,UNIQUE(faction1,faction2))')
    rows=conn.execute('SELECT faction1,faction2,relationship FROM relations').fetchall()
    pairs={(a,b):value for a,b,value in rows}
    others={r[0] for r in conn.execute('SELECT DISTINCT faction FROM cities')}
    others.update(b if a==faction else a for a,b,_ in rows if faction in (a,b))
    for other in sorted(others-{faction,'Нейтрал',None,''}):
        fallback=pairs.get((faction,other),pairs.get((other,faction),50))
        for a,b in ((faction,other),(other,faction)):
            value=max(0,min(100,int(pairs.get((a,b),fallback) or 0)+delta))
            if (a,b) in pairs:conn.execute('UPDATE relations SET relationship=? WHERE faction1=? AND faction2=?',(value,a,b))
            else:conn.execute('INSERT INTO relations(faction1,faction2,relationship) VALUES(?,?,?)',(a,b,value))


def economy_adjustments(conn,faction,crowns=0,crystals=0,growth=0,tax_growth=0):
    """Allocate production to towns before applying each town's own percentages.

    Crystal shares use factory counts and town quality; tax shares use towns
    because the game's population and tax base are stored for the whole faction.
    """
    result=dict(crowns=0,crystals=0,population=0)
    if not exists(conn,'map_city_secrets'):return result
    if 'policy_active' not in {r[1] for r in conn.execute('PRAGMA table_info(map_city_secrets)')}:ensure_schema(conn)
    from utils.faction_bonuses import supplied_cities
    supplied=supplied_cities(conn,faction)
    columns={r[1] for r in conn.execute('PRAGMA table_info(cities)')}
    quality='COALESCE(kf_crystal,0)' if 'kf_crystal' in columns else '0'
    cities=dict(conn.execute('SELECT name,'+quality+' FROM cities WHERE faction=?',(faction,)))
    buildings={}
    for city,kind,count in conn.execute('SELECT city_name,building_type,MAX(count) FROM buildings WHERE faction=? AND count>0 GROUP BY city_name,building_type',(faction,)):
        if city in cities and city in supplied:buildings[(city,kind)]=count
    weights={city:buildings.get((city,'Фабрика'),0)*max(0,1+float(kf)) for city,kf in cities.items()}
    total_weight=sum(weights.values());hospitals=sum(n for (city,kind),n in buildings.items() if kind=='Больница')
    rows=conn.execute('SELECT city,kind,resolution FROM map_city_secrets WHERE faction=? AND stage=3 AND policy_active=1',(faction,))
    raw=dict(crowns=0.0,crystals=0.0,population=0.0)
    for city,kind,resolution in rows:
        if city not in cities or city not in supplied or (kind,resolution) not in CITY_POLICIES:continue
        building='Фабрика' if kind=='factory' else 'Больница'
        if not buildings.get((city,building)):continue
        money_pct,crystal_pct,pop_pct=CITY_POLICIES[(kind,resolution)]
        raw['crowns']+=max(0,crowns)/max(1,len(cities))*money_pct/100
        raw['crystals']+=max(0,crystals)*weights.get(city,0)/max(1,total_weight)*crystal_pct/100
        local_growth=(max(0,growth)*buildings.get((city,'Больница'),0)/max(1,hospitals)
                      +max(0,tax_growth)/max(1,len(cities)))
        raw['population']+=local_growth*pop_pct/100
    return {key:int(value) for key,value in raw.items()}


def journal(conn,faction,city=None):
    ensure_schema(conn)
    offers=_dicts(conn,"SELECT * FROM map_intrigue_offers WHERE faction=? AND status IN ('offered','accepted') ORDER BY id DESC",(faction,))
    offers=[row for row in offers if _valid_offer(conn,row)]
    captures=_dicts(conn,"SELECT * FROM map_intrigue_captures WHERE faction=? AND status='pending' ORDER BY id DESC",(faction,))
    captures=[r for r in captures if owner(conn,r['city'])==faction]
    secrets=_dicts(conn,'SELECT * FROM map_city_secrets WHERE faction=? ORDER BY city',(faction,))
    for name in surviving_companions(conn,faction):
        conn.execute('INSERT OR IGNORE INTO map_companion_temper(unit_name,faction) VALUES(?,?)',(name,faction))
    companions=_dicts(conn,'''SELECT t.* FROM map_companion_temper t WHERE faction=?
        AND EXISTS(SELECT 1 FROM garrisons g WHERE g.unit_name=t.unit_name AND g.unit_count>0)''',(faction,))
    log=_dicts(conn,'SELECT * FROM map_intrigue_log WHERE faction=? ORDER BY id DESC LIMIT 15',(faction,))
    if city:
        offers=[r for r in offers if r['city']==city];captures=[r for r in captures if r['city']==city]
        secrets=[r for r in secrets if r['city']==city]
    return dict(offers=offers,captures=captures,secrets=secrets,companions=companions,log=log)
