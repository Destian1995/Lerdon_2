"""Keep the original Python exception when a later shutdown error hides it."""
import faulthandler
import os
import sys
import threading
import traceback
from pathlib import Path

_crash_fd=None


def record_exception(kind, exc):
    """Persist caught failures too, without relying on buffered console output."""
    if _crash_fd is None:return
    try:
        from datetime import datetime
        message='\n'+datetime.now().isoformat(timespec='seconds')+' '+kind+'\n'
        message+=''.join(traceback.format_exception(type(exc),exc,exc.__traceback__))
        os.write(_crash_fd,message.encode('utf-8','replace'))
    except (OSError,ValueError):
        pass


def install_crash_log(path):
    global _crash_fd
    if _crash_fd is not None:return
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    _crash_fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    # Keep this descriptor alive until process exit. faulthandler writes
    # directly to it and does not acquire Python's buffered stdout lock.
    faulthandler.enable(file=_crash_fd,all_threads=True)
    previous=sys.excepthook
    previous_thread=threading.excepthook
    def record(kind,exc_type,exc,tb):
        try:os.write(_crash_fd,('\n'+kind+'\n'+''.join(traceback.format_exception(exc_type,exc,tb))).encode('utf-8','replace'))
        except OSError:pass
    def exception(exc_type,exc,tb):
        record('Unhandled exception',exc_type,exc,tb)
        previous(exc_type,exc,tb)
    def thread_exception(args):
        record('Worker exception: '+str(args.thread.name),args.exc_type,args.exc_value,args.exc_traceback)
        previous_thread(args)
    sys.excepthook=exception;threading.excepthook=thread_exception
