"""Read continuously; inference consumes the latest frame, never a queue."""
import threading


class LatestCamera:
    def __init__(self, capture):
        self.capture = capture
        self.condition = threading.Condition()
        self.stopped = threading.Event()
        self.sequence = 0
        self.frame = None
        self.failed = False
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        while not self.stopped.is_set():
            ok, frame = self.capture.read()
            with self.condition:
                if not ok:
                    self.failed = True
                    self.condition.notify_all()
                    return
                self.frame = frame
                self.sequence += 1
                self.condition.notify_all()

    def next(self, sequence, timeout=2):
        with self.condition:
            ready = self.condition.wait_for(lambda: self.sequence > sequence or self.failed, timeout)
            if not ready or self.failed:
                raise RuntimeError("Camera stopped delivering frames")
            return self.sequence, self.frame.copy()

    def stop(self):
        self.stopped.set()
        self.thread.join(timeout=0.5)
