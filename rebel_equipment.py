"""Transfer equipped player artifacts and immediately synchronize combat stats."""
import sys


def transfer_artifact(conn, faction, hero, slot, artifact_id, season_manager=None):
    game = sys.modules.get('game_process')
    screen = getattr(game, '_active_game_screen', None)
    manager = season_manager or getattr(screen, 'season_manager', None)
    if manager is None:
        from seasons import SeasonManager
        manager = SeasonManager()
    if manager.last_idx is None:
        row = conn.execute('SELECT season_index FROM season LIMIT 1').fetchone()
        if not row or row[0] not in range(4):
            raise ValueError('Не удалось определить текущий сезон')
        manager.last_idx = row[0]

    with conn:
        artifact = conn.execute('SELECT artifact_type FROM artifacts WHERE id=?', (artifact_id,)).fetchone()
        if not artifact or int(artifact[0]) not in range(5):
            raise ValueError('Неизвестный тип артефакта')
        # Validate the exact selection again: a stale popup cannot duplicate gifts.
        cur = conn.execute('UPDATE hero_equipment SET artifact_id=NULL WHERE faction_name=? '
                           'AND hero_name=? AND slot_type=? AND artifact_id=?',
                           (faction, hero, slot, artifact_id))
        if cur.rowcount != 1:
            raise ValueError('Артефакт уже снят или передан')
        aliases = ('weapon', 'armor', 'helmet', 'boots', 'accessory')
        for index, alias in enumerate(aliases):
            old = conn.execute("SELECT artifact_id FROM hero_equipment WHERE faction_name='Мятежники' "
                               "AND hero_name='Кейдж' AND slot_type=?", (alias,)).fetchone()
            current = conn.execute("SELECT artifact_id FROM hero_equipment WHERE faction_name='Мятежники' "
                                   "AND hero_name='Кейдж' AND slot_type=?", (str(index),)).fetchone()
            if current is None:
                conn.execute('INSERT INTO hero_equipment(faction_name,hero_name,slot_type,artifact_id) '
                             "VALUES('Мятежники','Кейдж',?,?)", (str(index), old[0] if old else None))
            elif old and old[0] is not None and current[0] is None:
                conn.execute("UPDATE hero_equipment SET artifact_id=? WHERE faction_name='Мятежники' "
                             "AND hero_name='Кейдж' AND slot_type=?", (old[0], str(index)))
        conn.execute("DELETE FROM hero_equipment WHERE faction_name='Мятежники' AND hero_name='Кейдж' "
                     "AND slot_type IN ('weapon','armor','helmet','boots','accessory','shield')")
        conn.execute("UPDATE hero_equipment SET artifact_id=? WHERE faction_name='Мятежники' "
                     "AND hero_name='Кейдж' AND slot_type=?", (artifact_id, str(int(artifact[0]))))
    # The season manager owns effect logs, replacement and base-stat recalculation.
    manager.apply_artifact_bonuses(conn)
    if screen:
        for controller in getattr(screen, 'ai_controllers', {}).values():
            controller.army = controller.load_army()
            controller.garrison = controller.load_garrison()
        refresh = getattr(game, 'refresh_map', None)
        if refresh:
            refresh()
