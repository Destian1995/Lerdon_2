"""Heart contracts and a permanent, non-stacking army curse."""
import sqlite3
from city_war import current_turn

HEART_TURNS=20
SOUL_TURNS=15
CURSED_STATS=('Урон','Защита','Живучесть','Инициатива','Мораль','Крит')


def exists(conn,table):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())


def ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_heart_contracts(
        faction TEXT PRIMARY KEY,case_id INTEGER NOT NULL,signed_turn INTEGER NOT NULL,
        deadline INTEGER NOT NULL,cursed INTEGER NOT NULL DEFAULT 0,released INTEGER NOT NULL DEFAULT 0)''')
    if not exists(conn,'portal_soul_pacts'):return
    for faction,case,signed,deadline in conn.execute('SELECT faction,case_id,signed_turn,deadline FROM portal_soul_pacts WHERE case_id>0').fetchall():
        service=None
        if exists(conn,'morgana_covenants'):
            service=conn.execute("SELECT accepted_turn FROM morgana_covenants WHERE faction=? AND status='accepted'",(faction,)).fetchone()
        conn.execute('INSERT OR IGNORE INTO portal_heart_contracts VALUES(?,?,?,?,0,?)',
                     (faction,case,signed,signed+HEART_TURNS,int(service is not None)))
        if service:
            accepted=service[0] if service[0] is not None else signed
            conn.execute('UPDATE portal_soul_pacts SET case_id=0,signed_turn=?,deadline=? WHERE faction=?',(accepted,accepted+SOUL_TURNS,faction))
        else:conn.execute('DELETE FROM portal_soul_pacts WHERE faction=?',(faction,))
    conn.execute('UPDATE portal_soul_pacts SET deadline=signed_turn+? WHERE case_id=0 AND deadline-signed_turn=30',(SOUL_TURNS,))


def state(conn,faction):
    if not exists(conn,'portal_heart_contracts'):return None
    row=conn.execute('SELECT case_id,signed_turn,deadline,cursed,released FROM portal_heart_contracts WHERE faction=?',(faction,)).fetchone()
    return dict(zip(('case_id','signed_turn','deadline','cursed','released'),row)) if row else None


def expire(conn,faction):
    if not exists(conn,'portal_heart_contracts'):return False
    return conn.execute('''UPDATE portal_heart_contracts SET cursed=1
        WHERE faction=? AND cursed=0 AND released=0 AND deadline<=?''',(faction,current_turn(conn))).rowcount>0


def multiplier(conn,faction):
    row=state(conn,faction)
    return .5 if row and (row['cursed'] or not row['released'] and current_turn(conn)>row['deadline']) else 1


def apply_to_army(conn,army):
    """Scale finished stat dictionaries once; templates and equipment stay intact."""
    if not army or not exists(conn,'portal_heart_contracts'):return
    names={u['unit_name'] for u in army};marks=','.join('?' for _ in names)
    owners=dict(conn.execute(f'SELECT unit_name,faction FROM units WHERE unit_name IN ({marks})',tuple(names)))
    factors={f:multiplier(conn,f) for f in set(owners.values())}
    for unit in army:
        if unit.get('_heart_curse_applied') or factors.get(owners.get(unit['unit_name']),1)==1:continue
        stats=unit.setdefault('units_stats',{})
        for key in CURSED_STATS:
            if key in stats:stats[key]=float(stats[key])*.5
        unit['_heart_curse_applied']=True


def caption(conn,faction):
    row=state(conn,faction)
    if not row:return ''
    if multiplier(conn,faction)<1:return 'Проклятие сердца: вся армия −50% до конца кампании'
    if row['released']:return ''
    return 'Сердце: '+str(max(0,row['deadline']-current_turn(conn)))+' х.'
