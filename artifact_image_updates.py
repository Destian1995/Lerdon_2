"""Keep crafted artifacts visible after source icon filename corrections."""
ICON_RENAMES={'1hlem_mudretsa.png':'1shlesa.png',
              '1shlem_haosa.png':'1hlem_haosa.png',
              '1shlem_mudretsa.png':'1hlem_tsa.png'}


def migrate_artifact_image_paths(conn):
    tables={row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    changed=0
    fields={name:'image_url' for name in ('artifacts','artifacts_default','artifacts_ai',
                                        'artifacts_ai_default','hero_equipment','ai_hero_equipment')}
    fields['portal_timed_items']='previous_image'
    prefix='files/pict/artifacts/custom/'
    for table,field in fields.items():
        if table not in tables:continue
        if field not in {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}:continue
        for old,new in ICON_RENAMES.items():
            changed+=conn.execute(f'''UPDATE {table} SET {field}=?
                WHERE REPLACE({field},CHAR(92),'/')=?''',(prefix+new,prefix+old)).rowcount
    return changed
