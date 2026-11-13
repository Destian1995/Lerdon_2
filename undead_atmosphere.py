"""Read-only town warnings; no changes to invasion timing or combat bonuses."""
import sqlite3

FORTRESS_WARNING='Столица Нежити · мощные укрепления'


def town_omens(conn,city):
    try:
        row=conn.execute('SELECT COALESCE(is_undead,0) FROM cities WHERE name=?',(city,)).fetchone()
        if not row or not row[0]:return False
        try:
            invasion=conn.execute('SELECT invasion_started FROM undead_invasion WHERE id=1').fetchone()
        except sqlite3.OperationalError:invasion=None
        return not invasion or invasion[0]==0
    except sqlite3.OperationalError:return False


def fortified_capital(conn,city):
    try:
        row=conn.execute('''SELECT 1 FROM cities c JOIN undead_invasion i ON i.capital_city=c.name
            WHERE i.id=1 AND c.name=? AND c.faction='Нежить' AND i.invasion_started=1''',(city,)).fetchone()
        return bool(row)
    except sqlite3.OperationalError:return False
