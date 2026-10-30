"""Inventory interface icons and their code/database uses without writing the DB."""
import json
from pathlib import Path
import sqlite3
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def audit():
    icons = [p for p in sorted((ROOT / 'files/pict').rglob('*.png')) if 'artifacts' not in p.parts]
    refs = {}
    for icon in icons:
        with Image.open(icon) as image:
            refs[icon.relative_to(ROOT).as_posix()] = {
                'size': list(image.size), 'mode': image.mode,
                'code': [], 'preload': [], 'legacy': [], 'database': []}
    for source in ROOT.rglob('*.py'):
        if any(p in source.parts for p in ('.git', '__pycache__', '.venv', 'tests', 'tools')):
            continue
        group = 'legacy' if 'old' in source.parts else 'preload' if source.name == 'preload_cache.py' else 'code'
        for number, line in enumerate(source.read_text(encoding='utf-8-sig', errors='replace').splitlines(), 1):
            for name, info in refs.items():
                if name in line.replace('\\', '/') and not line.lstrip().startswith('#'):
                    info[group].append(f'{source.relative_to(ROOT).as_posix()}:{number}')
    db = sqlite3.connect((ROOT / 'game_data.db').as_uri() + '?mode=ro', uri=True)
    try:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            for row in db.execute('SELECT * FROM ' + quoted):
                for value in row:
                    if isinstance(value, str):
                        for name, info in refs.items():
                            if name in value.replace('\\', '/') and table not in info['database']:
                                info['database'].append(table)
    finally:
        db.close()
    for name, info in refs.items():
        info['status'] = ('active' if info['code'] or info['database'] else
                          'preload_only' if info['preload'] else 'legacy_only' if info['legacy'] else 'unused')
        print(name, info['status'], info['database'])
    (ROOT / 'assets/pict-icon-usage.json').write_text(
        json.dumps(refs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('UI icons:', len(refs), 'active:', sum(r['status'] == 'active' for r in refs.values()))
    print('Artifact images:', len(list((ROOT / 'files/pict/artifacts').rglob('*.png'))))


if __name__ == '__main__':
    audit()
