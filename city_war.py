"""Persistent city battle damage. No Kivy imports; shared by player and AI."""
import math
import sqlite3
from dataclasses import dataclass

DEVASTATION_STRENGTH = 20_000_000
CITY_BUILDING_LIMIT = 25
SMOKE_TURNS = 2


@dataclass(frozen=True)
class CityWarState:
    city: str
    revision: int
    kind: str
    turn: int
    owner: str
    ruined: bool
    smoke_until: int
    ready_turn: object


def ensure_city_war_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS city_war_state (
        city_name TEXT PRIMARY KEY, revision INTEGER NOT NULL DEFAULT 1,
        event_kind TEXT NOT NULL, event_turn INTEGER NOT NULL,
        owner TEXT NOT NULL, ruined INTEGER NOT NULL DEFAULT 0,
        smoke_until INTEGER NOT NULL DEFAULT -1, ready_turn INTEGER,
        attacker_strength REAL NOT NULL DEFAULT 0,
        defender_strength REAL NOT NULL DEFAULT 0)''')


def current_turn(conn):
    try:
        row = conn.execute('SELECT MAX(turn_count) FROM turn').fetchone()
        return int(row[0] or 0) if row else 0
    except sqlite3.OperationalError:
        return 0


def army_strength(army):
    """Same strength formula as AI: (attack * class coefficient + defense + HP) * count.

    Snapshot the participating stacks before losses, not the faction's whole army.
    """
    coefficients = {1: 1.3, 2: 1.7, 3: 2.0, 4: 3.0, 5: 4.0}
    total = 0.0
    for unit in army:
        stats = unit.get('units_stats') or {}
        def number(value):
            try:
                value = float(value or 0)
                return max(0, value) if math.isfinite(value) else 0
            except (ValueError, TypeError):
                return 0
        class_parts = str(stats.get('Класс юнита', unit.get('unit_class', 1))).split()
        raw_class = class_parts[0] if class_parts else '1'
        try:
            coefficient = coefficients.get(int(raw_class), 1.0)
        except ValueError:
            coefficient = 1.0
        total += (number(stats.get('Урон', unit.get('attack', 0))) * coefficient
                  + number(stats.get('Защита', unit.get('defense', 0)))
                  + number(stats.get('Живучесть', unit.get('durability', 0)))) * number(unit.get('unit_count', 0))
    return total


def read_city_war_states(conn):
    try:
        rows = conn.execute('''SELECT city_name, revision, event_kind, event_turn,
            owner, ruined, smoke_until, ready_turn FROM city_war_state''').fetchall()
    except sqlite3.OperationalError:
        return {}
    return {row[0]: CityWarState(*row) for row in rows}


def record_capture(conn, city, owner, kind='peace'):
    """Caller owns the transaction. A peaceful takeover never heals existing ruins."""
    ensure_city_war_schema(conn)
    turn = current_turn(conn)
    conn.execute('''INSERT INTO city_war_state
        (city_name, event_kind, event_turn, owner) VALUES (?, ?, ?, ?)
        ON CONFLICT(city_name) DO UPDATE SET revision=revision+1,
        event_kind=excluded.event_kind, event_turn=excluded.event_turn,
        owner=excluded.owner''', (city, kind, turn, owner))


def record_battle(conn, city, attacker_strength, defender_strength, old_owner):
    ensure_city_war_schema(conn)
    row = conn.execute('SELECT faction FROM cities WHERE name=?', (city,)).fetchone()
    if row is None:
        return
    owner = row[0] or 'Нейтрал'
    turn = current_turn(conn)
    ruined = attacker_strength >= DEVASTATION_STRENGTH and defender_strength >= DEVASTATION_STRENGTH
    if ruined:
        # A city can be devastated even when the defending army holds it.
        conn.execute('DELETE FROM buildings WHERE city_name=?', (city,))
    kind = 'battle_capture' if owner != old_owner else 'battle'
    record_capture(conn, city, owner, kind)
    conn.execute('''UPDATE city_war_state SET ruined=MAX(ruined, ?),
        smoke_until=?, ready_turn=CASE WHEN ? THEN NULL ELSE ready_turn END,
        attacker_strength=?, defender_strength=? WHERE city_name=?''',
        (int(ruined), turn + SMOKE_TURNS, int(ruined),
         attacker_strength, defender_strength, city))


def reconcile_city_rebuilding(conn):
    """At full capacity, wait one game turn before restoring the intact icon.

    Called after construction and at turn boundaries. Caller commits changes.
    """
    states = read_city_war_states(conn)
    ruined = [state for state in states.values() if state.ruined]
    if not ruined:
        return
    turn = current_turn(conn)
    counts = dict(conn.execute('''SELECT b.city_name, SUM(b.count) FROM buildings b
        JOIN cities c ON c.name=b.city_name AND c.faction=b.faction GROUP BY b.city_name'''))
    for state in ruined:
        if counts.get(state.city, 0) < CITY_BUILDING_LIMIT:
            if state.ready_turn is not None:
                conn.execute('UPDATE city_war_state SET ready_turn=NULL WHERE city_name=?', (state.city,))
        elif state.ready_turn is None:
            conn.execute('UPDATE city_war_state SET ready_turn=? WHERE city_name=?', (turn, state.city))
        elif turn > state.ready_turn:
            conn.execute('''UPDATE city_war_state SET ruined=0, smoke_until=-1,
                ready_turn=NULL, revision=revision+1, event_kind='rebuild',
                event_turn=? WHERE city_name=?''', (turn, state.city))


def city_recovery_message(conn, city):
    state = read_city_war_states(conn).get(city)
    if not state or not state.ruined:
        return ''
    if state.ready_turn is not None:
        return 'Город восстанавливается — целая иконка появится на следующем ходу.'
    return 'Город разрушен. Отстройте 25 зданий и завершите ход для восстановления.'
