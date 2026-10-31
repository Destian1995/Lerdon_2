"""One-time Android data reset for the explicitly clean 6.7.0 release."""
import json
import os
from pathlib import Path
import shutil

RELEASE_DATA_ID = '6.7.0-unified-ui-20261031'


def reset_android_release(storage_dir, asset_database):
    storage = Path(storage_dir).resolve()
    stamp = storage / 'release-data.json'
    try:
        if json.loads(stamp.read_text(encoding='utf-8')).get('release') == RELEASE_DATA_ID:
            return False
    except (OSError, ValueError):
        pass
    target = storage / 'game_data.db'
    if Path(asset_database).resolve() == target.resolve():
        raise RuntimeError('Packaged and writable databases must have distinct paths')
    temporary = storage / 'game_data.db.new-release'
    shutil.copyfile(asset_database, temporary)
    os.replace(temporary, target)
    for suffix in ('-wal', '-shm'):
        sidecar = storage / ('game_data.db' + suffix)
        sidecar.unlink(missing_ok=True)
    for name in ('artifact_icon_cache', 'cache/artifact_icons'):
        cached = (storage / name).resolve()
        if cached.is_relative_to(storage) and cached.is_dir():
            shutil.rmtree(cached)
    stamp.write_text(json.dumps({'release': RELEASE_DATA_ID}), encoding='utf-8')
    return True
