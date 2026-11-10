"""Starting treasuries; apply only when creating or packaging a fresh campaign."""
STARTING_CROWNS=2500
SPECIAL_STARTING_CROWNS=100000


def reset_starting_crowns(conn,table='resources'):
    if table not in ('resources','resources_default'):
        raise ValueError('Unknown starting resource table')
    conn.execute(f'''UPDATE {table} SET amount=CASE
        WHEN faction IN ('Нежить','Мятежники') THEN ? ELSE ? END
        WHERE resource_type='Кроны' AND faction IN
        ('Север','Элины','Адепты','Вампиры','Эльфы','Нежить','Мятежники')''',
        (SPECIAL_STARTING_CROWNS,STARTING_CROWNS))
