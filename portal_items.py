"""Turn-bound class-3 relics: personal instances, expiry and equipment restoration."""
import math
import sqlite3
from city_war import current_turn
from otherworld_themes import theme,image_path

WAR_REWARD_NAMES={'Север':'Меч Альдара','Элины':'Посох Мигиона',
                  'Адепты':'Арбалет Гвиндензета','Вампиры':'Клинок Аргана','Эльфы':'Лук Зорина'}


def reward_image(faction,key):
    filename={101:'truth-crown',102:'war-weapon',103:'mirror-heart'}[key]
    return 'files/otherworld/rewards/'+theme(faction)['key']+'/'+filename+'.png'


def refresh_reward_images(conn):
    """Update issued rewards and nested slot snapshots without changing stats."""
    tables={row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'artifacts' not in tables:return
    for aid,faction,key in conn.execute('''SELECT artifact_id,faction,catalog_id
            FROM portal_timed_items WHERE catalog_id IN (101,102,103)''').fetchall():
        image=reward_image(faction,key)
        conn.execute('UPDATE artifacts SET image_url=? WHERE id=? AND image_url IS NOT ?',(image,aid,image))
        if 'hero_equipment' in tables:
            conn.execute('UPDATE hero_equipment SET image_url=? WHERE artifact_id=? AND image_url IS NOT ?',(image,aid,image))
        conn.execute('UPDATE portal_timed_items SET previous_image=? WHERE previous_id=? AND previous_image IS NOT ?',(image,aid,image))


def ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_timed_items(
        artifact_id INTEGER PRIMARY KEY,faction TEXT NOT NULL,hero TEXT NOT NULL,slot TEXT NOT NULL,
        issued_turn INTEGER NOT NULL,expires_turn INTEGER NOT NULL,previous_id INTEGER,
        previous_image TEXT,catalog_id INTEGER NOT NULL,expired INTEGER NOT NULL DEFAULT 0)''')
    # Old saves had permanent portal purchases and no previous-slot snapshot.
    # Give those existing purchases five remaining turns, without erasing them.
    try:
        old=conn.execute('''SELECT r.artifact_id,r.faction,e.hero_name,e.slot_type,r.catalog_id
            FROM portal_artifacts r JOIN hero_equipment e ON e.artifact_id=r.artifact_id
            WHERE NOT EXISTS(SELECT 1 FROM portal_timed_items t WHERE t.artifact_id=r.artifact_id)''').fetchall()
        turn=current_turn(conn)
        for aid,faction,hero,slot,key in old:
            conn.execute('INSERT INTO portal_timed_items VALUES(?,?,?,?,?,?,NULL,NULL,?,0)',
                         (aid,faction,hero,slot,turn,turn+5,key))
    except sqlite3.OperationalError:pass
    refresh_reward_images(conn)


def champions(conn,faction,camp=None):
    if 'faction' not in {r[1] for r in conn.execute('PRAGMA table_info(units)')}:return []
    query='''SELECT DISTINCT u.unit_name FROM units u JOIN garrisons g ON g.unit_name=u.unit_name
        WHERE CAST(u.unit_class AS INTEGER)=3 AND u.faction=? AND g.unit_count>0'''
    params=[faction]
    if camp:query+=' AND g.city_name=?';params.append(camp)
    return [r[0] for r in conn.execute(query+' ORDER BY u.unit_name',params)]


def remaining(conn,aid):
    try:
        row=conn.execute('SELECT expires_turn,expired FROM portal_timed_items WHERE artifact_id=?',(aid,)).fetchone()
        return max(0,row[0]-current_turn(conn)) if row and not row[1] else (0 if row else None)
    except sqlite3.OperationalError:return None


def owner(conn,aid):
    try:
        row=conn.execute('SELECT faction FROM portal_timed_items WHERE artifact_id=?',(aid,)).fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:return None


def analogs(conn):
    """The strongest priced ordinary item of each slot, excluding personal/world goods."""
    available={r[1] for r in conn.execute('PRAGMA table_info(artifacts)')}
    if not {'artifact_type','is_created'}.issubset(available):
        return [dict(id=0,name='Обычный артефакт',attack=30,defense=30,cost=10000,artifact_type=i) for i in range(5)]
    rows=conn.execute('''SELECT id,name,attack,defense,cost,artifact_type,image_url FROM artifacts
        WHERE COALESCE(is_created,0)=0 AND cost>0 AND artifact_type BETWEEN 0 AND 4 ORDER BY cost DESC,id''').fetchall()
    result={}
    for aid,name,a,d,cost,slot,image in rows:
        if 'otherworld/' in (image or '').replace('\\','/'):continue
        try:
            if conn.execute("SELECT 1 FROM monster_artifact_upgrades WHERE artifact_table='artifacts' AND artifact_id=?",(aid,)).fetchone():continue
        except sqlite3.OperationalError:pass
        result.setdefault(int(slot),dict(id=aid,name=name,attack=a or 0,defense=d or 0,cost=cost,artifact_type=int(slot)))
    return [result.get(i,dict(id=0,name='Обычный артефакт',attack=30,defense=30,cost=10000,artifact_type=i)) for i in range(5)]


def offers(conn,faction):
    bases=analogs(conn)
    low=min(b['cost'] for b in bases);high=max(b['cost'] for b in bases)
    keys=('blade','crown','boots','armor','ring')
    names=('Клинок','Венец','Поступь','Доспех','Перстень')
    result=[]
    for i,base in enumerate(bases):
        duration=5+round(7*(base['cost']-low)/(high-low)) if high>low else 8
        result.append(dict(id=i+1,name=names[i]+' '+theme(faction)['prefix'],artifact_type=i,
            attack=math.ceil(base['attack']*3.3),defense=math.ceil(base['defense']*3.3),
            cost=max(1,math.ceil(base['cost']*3.3)),duration=duration,analog_name=base['name'],
            image_url=image_path(faction,'artifacts',keys[i]),season_name='Все',is_created=0))
    return result


def reward(conn,faction,key):
    slot={101:1,102:0,103:4}[key]
    base=analogs(conn)[slot]
    factor={101:5.0,102:6.25,103:6.5}[key]
    attack=math.ceil(base['attack']*factor)
    defense=math.ceil(base['defense']*factor)
    if key==101:
        # Increase the detective reward's previous integer bonuses by 65%.
        attack=(attack*165+99)//100
        defense=(defense*165+99)//100
    name={101:'Венец истины',102:'Меч Альдара',103:'Сердце Зазеркалья'}[key]
    title=WAR_REWARD_NAMES.get(faction,name) if key==102 else name+' · '+theme(faction)['prefix']
    return dict(id=key,name=title,artifact_type=slot,
                attack=attack,defense=defense,
                cost=0,duration=25,image_url=reward_image(faction,key),season_name='Все',is_created=0)


def issue(conn,faction,camp,item,hero=None):
    ensure_schema(conn)
    eligible=champions(conn,faction,camp)
    hero=hero or (eligible[0] if eligible else None)
    if hero not in eligible:raise ValueError('Артефакт доступен только герою 3 класса в отряде.')
    slot=str(item['artifact_type'])
    previous=conn.execute('SELECT artifact_id,image_url FROM hero_equipment WHERE faction_name=? AND hero_name=? AND slot_type=?',
                          (faction,hero,slot)).fetchone()
    aid=conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM artifacts').fetchone()[0]
    columns={r[1] for r in conn.execute('PRAGMA table_info(artifacts)')}
    data={k:v for k,v in item.items() if k in columns};data['id']=aid
    conn.execute('INSERT INTO artifacts('+','.join(data)+') VALUES('+','.join('?' for _ in data)+')',list(data.values()))
    turn=current_turn(conn)
    conn.execute('INSERT INTO portal_timed_items VALUES(?,?,?,?,?,?,?,?,?,0)',
                 (aid,faction,hero,slot,turn,turn+item['duration'],previous[0] if previous else None,
                  previous[1] if previous else None,item['id']))
    conn.execute('''INSERT INTO hero_equipment(faction_name,hero_name,slot_type,artifact_id,image_url)
        VALUES(?,?,?,?,?) ON CONFLICT(faction_name,hero_name,slot_type) DO UPDATE SET
        artifact_id=excluded.artifact_id,image_url=excluded.image_url''',(faction,hero,slot,aid,item['image_url']))
    return aid


def expire(conn):
    """Called before seasonal recalculation, including after save/load."""
    ensure_schema(conn)
    try:
        rows=conn.execute('''SELECT artifact_id,faction,hero,slot,previous_id,previous_image
            FROM portal_timed_items WHERE expired=0 AND expires_turn<=?''',(current_turn(conn),)).fetchall()
    except sqlite3.OperationalError:return False
    if not rows:return False
    for aid,faction,hero,slot,previous,image in rows:
        conn.execute('UPDATE portal_timed_items SET expired=1 WHERE artifact_id=?',(aid,))
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='artifact_effects_log'").fetchone():
            conn.execute('DELETE FROM artifact_effects_log WHERE hero_name=? AND artifact_id=?',(hero,aid))
        seen={aid}
        while previous is not None:
            if previous in seen:previous=None;break
            seen.add(previous)
            old=conn.execute('SELECT expires_turn,expired,previous_id,previous_image FROM portal_timed_items WHERE artifact_id=?',(previous,)).fetchone()
            if old and (old[1] or old[0]<=current_turn(conn)):
                previous,image=old[2],old[3]
            else:break
        conn.execute('''UPDATE hero_equipment SET artifact_id=?,image_url=?
            WHERE faction_name=? AND hero_name=? AND slot_type=? AND artifact_id=?''',(previous,image,faction,hero,slot,aid))
    return True


def inherit(conn,source,target):
    """Legendary upgrades retain the original deadline, never turn permanent."""
    try:
        row=conn.execute('SELECT faction,hero,slot,issued_turn,expires_turn,previous_id,previous_image,catalog_id,expired FROM portal_timed_items WHERE artifact_id=?',(source,)).fetchone()
        if row:conn.execute('INSERT INTO portal_timed_items VALUES(?,?,?,?,?,?,?,?,?,?)',(target,*row))
    except sqlite3.OperationalError:pass
