"""Two-turn player reconnaissance. Combat calculations never use this UI gate."""
import sqlite3
import random
from dataclasses import dataclass
from city_war import current_turn

DURATION=2
UNKNOWN='Нет разведданных'
TABLE='map_army_intelligence'


@dataclass(frozen=True)
class ScoutQuote:
    relation:int
    cities:int
    rate:int

    @property
    def relation_cost(self):return max(0,100-self.relation)*self.rate

    @property
    def total(self):return 76000+self.relation_cost+25000*self.cities


def relation(conn,viewer,target):
    try:
        row=conn.execute('''SELECT relationship FROM relations
            WHERE faction1=? AND faction2=?''',(viewer,target)).fetchone()
        if not row:row=conn.execute('SELECT relationship FROM relations WHERE faction1=? AND faction2=?',(target,viewer)).fetchone()
        return max(0,min(100,int(float(row[0])))) if row else 50
    except (sqlite3.OperationalError,TypeError,ValueError):return 50


def quote(conn,viewer,target):
    cities=conn.execute('SELECT COUNT(*) FROM cities WHERE faction=?',(target,)).fetchone()[0]
    return ScoutQuote(relation(conn,viewer,target),cities,min(9000,3000+max(0,cities-1)*1000))


def player_faction(conn):
    try:
        row=conn.execute('SELECT faction_name FROM user_faction LIMIT 1').fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:return None


def remaining(conn,viewer,target):
    if not viewer or not target:return 0
    try:
        row=conn.execute('''SELECT acquired_turn,expires_turn FROM map_army_intelligence
            WHERE viewer=? AND target=?''',(viewer,target)).fetchone()
    except sqlite3.OperationalError:return 0
    turn=max(1,current_turn(conn))
    return max(0,row[1]-turn) if row and row[0]<=turn else 0


def visible(conn,viewer,target):
    from alliance_rules import allies
    return bool(viewer and target and (viewer==target or target in allies(conn,viewer)
                                      or remaining(conn,viewer,target)>0))


def city_visible(conn,viewer,city):
    row=conn.execute('SELECT faction FROM cities WHERE name=?',(city,)).fetchone()
    return bool(row and visible(conn,viewer,row[0]))


def gather(conn,viewer,target,source_city,rng=None,expected_cost=None):
    """Talk to scouts at a friendly/neutral tavern. Caller commits the action."""
    row=conn.execute('SELECT faction FROM cities WHERE name=?',(source_city,)).fetchone()
    if not viewer or not row or row[0] not in (viewer,'Нейтрал'):
        raise ValueError('Разведчиков можно встретить в таверне своего или нейтрального города.')
    if target==viewer or not conn.execute('SELECT 1 FROM cities WHERE faction=?',(target,)).fetchone():
        raise ValueError('Выберите другую фракцию с городами на карте.')
    from alliance_rules import allies
    if target in allies(conn,viewer):
        raise ValueError('Войска союзника всегда известны. Разведка не требуется.')
    if remaining(conn,viewer,target)==DURATION:
        raise ValueError('Сведения уже получены на этом ходу. Повторная оплата не нужна.')
    price=quote(conn,viewer,target)
    if expected_cost is not None and expected_cost!=price.total:
        raise ValueError('Цена разведки изменилась. Обновите выбор фракции.')
    from utils.resource_payments import ensure_resource_schema
    ensure_resource_schema(conn)
    conn.execute('''CREATE TABLE IF NOT EXISTS map_army_intelligence(
        viewer TEXT NOT NULL,target TEXT NOT NULL,acquired_turn INTEGER NOT NULL,
        expires_turn INTEGER NOT NULL,PRIMARY KEY(viewer,target))''')
    turn=max(1,current_turn(conn));conn.execute('SAVEPOINT scout_purchase')
    try:
        paid=conn.execute("UPDATE resources SET amount=amount-? WHERE faction=? AND resource_type='Кроны' AND amount>=?",
                          (price.total,viewer,price.total))
        if paid.rowcount!=1:raise ValueError('Недостаточно крон для разведки.')
        detected=(rng or random).random()<.4
        if detected:
            conn.execute('''CREATE TABLE IF NOT EXISTS relations(faction1 TEXT,faction2 TEXT,relationship INTEGER,
                UNIQUE(faction1,faction2))''')
            old_values=(relation(conn,viewer,target),relation(conn,target,viewer))
            for (a,b),old in zip(((viewer,target),(target,viewer)),old_values):
                updated=conn.execute('UPDATE relations SET relationship=? WHERE faction1=? AND faction2=?',
                                     (max(0,old-35),a,b))
                if not updated.rowcount:conn.execute('INSERT INTO relations VALUES(?,?,?)',(a,b,max(0,old-35)))
        conn.execute('''INSERT INTO map_army_intelligence VALUES(?,?,?,?)
            ON CONFLICT(viewer,target) DO UPDATE SET
            acquired_turn=excluded.acquired_turn,expires_turn=excluded.expires_turn''',
            (viewer,target,turn,turn+DURATION))
        conn.execute('RELEASE scout_purchase')
    except Exception:
        conn.execute('ROLLBACK TO scout_purchase');conn.execute('RELEASE scout_purchase');raise
    return dict(expires=turn+DURATION,cost=price.total,detected=detected,relation=relation(conn,viewer,target))
