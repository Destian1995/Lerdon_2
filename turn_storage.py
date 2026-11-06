"""Storage checks without opening or changing the player's database."""
import errno
from pathlib import Path
import shutil
import sqlite3
import tempfile

MIN_FREE_BYTES=128*1024*1024


def check_turn_storage(conn):
    paths={Path(tempfile.gettempdir()).resolve()}
    for _,_,filename in conn.execute('PRAGMA database_list'):
        if filename:paths.add(Path(filename).resolve().parent)
    for path in paths:
        if shutil.disk_usage(path).free<MIN_FREE_BYTES:
            raise OSError(errno.ENOSPC,'Недостаточно свободного места для обработки хода')


def is_storage_full(error):
    return (isinstance(error,OSError) and error.errno==errno.ENOSPC or
            getattr(error,'sqlite_errorcode',None)==sqlite3.SQLITE_FULL or
            'database or disk is full' in str(error).lower())
