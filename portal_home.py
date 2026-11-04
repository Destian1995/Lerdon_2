"""The portal's origin remains vulnerable; losing it ends the expedition's game."""
import sqlite3


def install(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS portal_home_losses(faction TEXT PRIMARY KEY,city TEXT NOT NULL)')
    conn.execute('''CREATE TRIGGER IF NOT EXISTS portal_home_captured AFTER UPDATE OF faction ON cities
        WHEN NEW.faction IS NOT OLD.faction BEGIN
        INSERT OR IGNORE INTO portal_home_losses SELECT faction,source FROM portal_parties
            WHERE source=OLD.name AND faction IS NOT NEW.faction;
        END''')
    conn.execute('''CREATE TRIGGER IF NOT EXISTS portal_home_destroyed AFTER DELETE ON cities BEGIN
        INSERT OR IGNORE INTO portal_home_losses SELECT faction,source FROM portal_parties WHERE source=OLD.name;
        END''')


def loss_reason(conn,faction):
    try:
        has_losses=conn.execute("SELECT 1 FROM sqlite_master WHERE name='portal_home_losses'").fetchone()
        lost=conn.execute('SELECT city FROM portal_home_losses WHERE faction=?',(faction,)).fetchone() if has_losses else None
        if not lost:
            lost=conn.execute('''SELECT p.source FROM portal_parties p LEFT JOIN cities c ON c.name=p.source
                WHERE p.faction=? AND (c.name IS NULL OR c.faction IS NOT p.faction)''',(faction,)).fetchone()
    except sqlite3.OperationalError:
        return ''
    return f'Город входа в портал «{lost[0]}» захвачен. Путь домой потерян. Поражение!' if lost else ''


def marked_cities(conn):
    try:
        return list(conn.execute('''SELECT p.source,p.faction FROM portal_parties p JOIN cities c
            ON c.name=p.source AND c.faction=p.faction'''))
    except sqlite3.OperationalError:
        return []
