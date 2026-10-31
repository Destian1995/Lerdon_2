"""Fail a release when its public versions disagree or Android code goes backwards."""
import argparse
import ast
import configparser
import json
from pathlib import Path
import re


def legacy_android_code(version, min_sdk):
    parts = version.split('.')
    if len(parts) != 3 or any(not part.isdecimal() or int(part) > 99 for part in parts):
        raise ValueError('Version must be major.minor.patch, with components from 0 to 99')
    numeric = 0
    for part in parts:
        numeric = numeric * 100 + int(part)
    # python-for-android used this scheme before explicit numeric_version was set.
    return int(f'10{min_sdk}{numeric}')


def validate(root, previous_code=None):
    root = Path(root)
    config = configparser.ConfigParser(interpolation=None)
    config.read(root / 'buildozer.spec', encoding='utf-8')
    app = config['app']
    version = app['version'].strip()
    code = int(app['android.numeric_version'])
    legacy_floor = legacy_android_code(version, int(app['android.minapi']))
    if not legacy_floor <= code <= 2_100_000_000:
        raise ValueError(f'Version Code {code} must be at least {legacy_floor}, within Android limits')
    if previous_code is not None and code <= previous_code:
        raise ValueError(f'Version Code {code} must exceed the previous store code {previous_code}')
    tree = ast.parse((root / 'frontend_ui.py').read_text(encoding='utf-8'))
    menu_version = next(ast.literal_eval(node.value) for node in tree.body
                        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'VERSION'
                                                               for target in node.targets))
    script = (root / 'build.sh').read_text(encoding='utf-8')
    match = re.search(r'^APP_VERSION="([^"]+)"', script, re.MULTILINE)
    if menu_version != version or match is None or match.group(1) != version:
        raise ValueError(f'Versions disagree: spec={version}, menu={menu_version}, build={match.group(1) if match else None}')
    return dict(version=version, version_code=code, legacy_floor=legacy_floor, previous_store_code=previous_code)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', default=Path(__file__).resolve().parents[1])
    parser.add_argument('--previous-code', type=int)
    args = parser.parse_args()
    print(json.dumps(validate(args.root, args.previous_code), indent=2))
