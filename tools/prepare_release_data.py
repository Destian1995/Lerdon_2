"""Copy a consistent SQLite snapshot and erase campaign data for packaging."""
import argparse
import json
from pathlib import Path
import sys
import sqlite3
from contextlib import closing
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unit_updates import migrate_morgana
from undead_garrison import migrate_capital_archers


def prepare(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError('Release preparation requires a separate output database')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(f'file:{source.as_posix()}?mode=ro', uri=True)) as original:
        with closing(sqlite3.connect(destination)) as clean:
            original.backup(clean)
    with closing(sqlite3.connect(destination)) as clean:
        clean.execute('PRAGMA foreign_keys=OFF')
        tables = {row[0] for row in clean.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        reference = {name for name in tables if name.endswith('_default')} | {'events', 'sqlite_sequence'}
        for name in sorted(tables - reference):
            clean.execute('DELETE FROM "' + name.replace('"', '""') + '"')
        for name in sorted(tables - reference):
            clean.execute('DELETE FROM sqlite_sequence WHERE name=?', (name,))
        for name in ('diplomacies', 'relations', 'resources', 'units', 'artifacts', 'artifacts_ai'):
            default = name + '_default'
            if name in tables and default in tables:
                # Old reference snapshots may contain a newly added unit with
                # a NULL ID before explicit IDs. SQLite would allocate an ID
                # already used by a later row when copying that snapshot.
                if name == 'units':
                    columns = {row[1] for row in clean.execute('PRAGMA table_info(units_default)')}
                    if 'id' in columns:
                        next_id = clean.execute('SELECT COALESCE(MAX(id),0)+1 FROM units_default').fetchone()[0]
                        missing = clean.execute('SELECT rowid FROM units_default WHERE id IS NULL').fetchall()
                        for (rowid,) in missing:
                            clean.execute('UPDATE units_default SET id=? WHERE rowid=?', (next_id, rowid))
                            next_id += 1
                clean.execute(f'INSERT INTO "{name}" SELECT * FROM "{default}"')
        from starting_economy import reset_starting_crowns
        for table in ('resources_default','resources'):
            if table in tables:reset_starting_crowns(clean,table)
        clean.commit()
        migrate_morgana(clean)
        migrate_capital_archers(clean)
        clean.commit()
        clean.execute('VACUUM')
        assert clean.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        counts = {name: clean.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
                  for name in sorted(tables) if name != 'sqlite_sequence'}
    return counts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.destination), indent=2))
