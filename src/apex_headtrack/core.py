"""Pure Python mapping and OpenTrack wire format; no camera dependencies."""
import math
import struct
from collections import deque
from statistics import median


def rotation_angles(rotation):
    """Yaw, pitch, roll in degrees from a rigid Rz @ Ry @ Rx rotation."""
    if not all(math.isfinite(float(rotation[i][j])) for i in range(3) for j in range(3)):
        raise ValueError("Rotation must be finite")
    yaw = math.atan2(-rotation[2][0], math.hypot(rotation[0][0], rotation[1][0]))
    pitch = math.atan2(rotation[2][1], rotation[2][2])
    roll = math.atan2(rotation[1][0], rotation[0][0])
    return tuple(math.degrees(a) for a in (yaw, pitch, roll))


def difference(angle, center):
    return (angle - center + 180) % 360 - 180


def map_axis(angle, gain, deadzone, limit):
    magnitude = max(0.0, abs(angle) - deadzone) * gain
    return math.copysign(min(limit, magnitude), angle)


def packet(yaw=0.0, pitch=0.0, roll=0.0):
    values = (0.0, 0.0, 0.0, yaw, pitch, roll)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Pose must be finite")
    return struct.pack("<6d", *values)


class Mapper:
    def __init__(self, gain=2.5, deadzone=1.5, limit=90, tau=0.08, max_speed=100):
        self.gain, self.deadzone, self.limit, self.tau = gain, deadzone, limit, tau
        self.max_speed = max_speed
        self.center = None
        self.filtered = [0.0] * 3
        self.history = deque(maxlen=3)

    def recenter(self, pose):
        self.center = tuple(pose)
        self.filtered = [0.0] * 3
        self.history.clear()

    def update(self, pose, dt):
        if self.center is None:
            self.recenter(pose)
        self.history.append(tuple(difference(angle, self.center[i]) for i, angle in enumerate(pose)))
        alpha = 1 - math.exp(-max(dt, 0) / self.tau) if self.tau else 1
        for i in range(3):
            angle = median(row[i] for row in self.history)
            target = map_axis(angle, self.gain, self.deadzone, self.limit)
            step = alpha * (target - self.filtered[i])
            bound = self.max_speed * max(dt, 0)
            self.filtered[i] += max(-bound, min(bound, step))
        return tuple(self.filtered)
