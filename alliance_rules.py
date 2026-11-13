"""Shared intelligence and military obligations of the player's direct allies."""
import sqlite3


def allies(conn, faction):
    if not faction:
        return set()
    result = set()
    statuses = {}
    try:
        for a, b, status in conn.execute(
                'SELECT faction1,faction2,relationship FROM diplomacies WHERE faction1=? OR faction2=?',
                (faction, faction)):
            other = b if a == faction else a
            statuses.setdefault(other, set()).add(status)
            if status == 'союз':
                result.add(other)
    except sqlite3.OperationalError:
        pass
    return {other for other in result if other and other != faction
            and not statuses.get(other, set()).intersection(('война', 'уничтожена'))}


def support_player(conn, player):
    """Join the player's wars, irrespective of turn, ideology, strength or truces.

    Direct allies only: no recursive coalition. Caller owns the transaction.
    """
    supporters = allies(conn, player)
    if not supporters:
        return set()
    try:
        living = {row[0] for row in conn.execute('SELECT DISTINCT faction FROM cities')}
        enemies = {b if a == player else a for a, b in conn.execute(
            "SELECT faction1,faction2 FROM diplomacies WHERE relationship='война' AND (faction1=? OR faction2=?)",
            (player, player))} - supporters - {player, 'Нейтрал', None, ''}
    except sqlite3.OperationalError:
        return set()
    joined = set()
    for ally in sorted(supporters & living):
        for enemy in sorted(enemies & living):
            for a, b in ((ally, enemy), (enemy, ally)):
                row = conn.execute('SELECT relationship FROM diplomacies WHERE faction1=? AND faction2=?', (a, b)).fetchone()
                if row and row[0] == 'война':
                    continue
                updated = conn.execute("UPDATE diplomacies SET relationship='война' WHERE faction1=? AND faction2=?", (a, b))
                if not updated.rowcount:
                    conn.execute("INSERT INTO diplomacies(faction1,faction2,relationship) VALUES(?,?,'война')", (a, b))
                joined.add((ally, enemy))
            try:
                conn.execute('DELETE FROM truces WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)',
                             (ally, enemy, enemy, ally))
            except sqlite3.OperationalError:
                pass
    return joined
