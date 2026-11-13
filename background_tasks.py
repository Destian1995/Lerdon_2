"""Own campaign workers until they have stopped, including on UI exceptions.

Never leave a daemon printing to stdout while Python destroys its IO locks.
Cancellation is cooperative: finish the current DB operation, then stop.
"""
import threading


class WorkerCancelled(Exception):
    pass


class TaskGroup:
    def __init__(self):
        self.stopping=threading.Event()
        self._lock=threading.Lock()
        self._threads=set()

    def start(self,target,name):
        def run():
            try:
                if not self.stopping.is_set():target()
            except WorkerCancelled:
                pass
        thread=threading.Thread(target=run,name=name,daemon=False)
        with self._lock:
            if self.stopping.is_set():raise WorkerCancelled('Приложение закрывается.')
            self._threads={t for t in self._threads if t.is_alive()}
            self._threads.add(thread)
            try:thread.start()
            except BaseException:
                self._threads.discard(thread);raise
        return thread

    def shutdown(self):
        self.stopping.set()
        # Never hold the registry lock while joining (workers need it to exit).
        with self._lock:threads=tuple(self._threads)
        for thread in threads:
            if thread is not threading.current_thread():thread.join()
        with self._lock:self._threads={t for t in self._threads if t.is_alive()}


tasks=TaskGroup()


def raise_if_stopping():
    if tasks.stopping.is_set():raise WorkerCancelled('Приложение закрывается; ожидание боя отменено.')
