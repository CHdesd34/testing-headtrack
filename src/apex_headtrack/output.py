"""Send smoothed poses independently of inference frame rate."""
import math
import threading
import time

from .core import packet


class PoseSmoother:
    def __init__(self, tau, max_speed):
        self.tau, self.max_speed = tau, max_speed
        self.value = (0.0, 0.0, 0.0)

    def update(self, target, dt):
        alpha = 1 - math.exp(-dt / self.tau)
        bound = self.max_speed * dt
        self.value = tuple(v + max(-bound, min(bound, alpha * (t - v)))
                           for v, t in zip(self.value, target))
        return self.value


class OutputPump:
    def __init__(self, sock, address, tau, max_speed):
        self.sock, self.address = sock, address
        self.smoother = PoseSmoother(tau, max_speed)
        self.target = (0.0, 0.0, 0.0)
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def set_target(self, target, reset=False):
        with self.lock:
            self.target = tuple(target)
            if reset:
                self.smoother.value = self.target
        if self.error is not None:
            raise RuntimeError("UDP output failed") from self.error

    def current(self):
        with self.lock:
            return self.smoother.value

    def _run(self):
        previous = time.monotonic()
        try:
            while not self.stopped.is_set():
                now = time.monotonic()
                with self.lock:
                    value = self.smoother.update(self.target, min(now - previous, 0.05))
                previous = now
                self.sock.sendto(packet(*value), self.address)
                self.stopped.wait(max(0, 1 / 60 - (time.monotonic() - now)))
        except OSError as error:
            self.error = error

    def stop(self):
        self.stopped.set()
        self.thread.join(timeout=1)
