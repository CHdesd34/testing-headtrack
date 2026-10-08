import math
import socket
import struct
import unittest

from apex_headtrack.core import Mapper, difference, map_axis, packet, rotation_angles
from apex_headtrack.output import PoseSmoother, OutputPump


class CoreTests(unittest.TestCase):
    def test_sender_continues_between_inference_frames(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(1)
            pump = OutputPump(sender, receiver.getsockname(), 0.08, 80)
            try:
                pump.set_target((30, 0, 0))
                values = [struct.unpack('<6d', receiver.recvfrom(128)[0])[3] for _ in range(5)]
                self.assertGreater(values[-1], values[0])
                self.assertTrue(all(a <= b for a, b in zip(values, values[1:])))
            finally:
                pump.stop()
            self.assertFalse(pump.thread.is_alive())

    def test_sender_smoothing_speed_and_frame_invariance(self):
        a, b = PoseSmoother(0.08, 10000), PoseSmoother(0.08, 10000)
        a.update((30, 0, 0), 0.04)
        b.update((30, 0, 0), 0.02)
        b.update((30, 0, 0), 0.02)
        self.assertAlmostEqual(a.value[0], b.value[0])
        limited = PoseSmoother(0.08, 80)
        self.assertLessEqual(limited.update((90, 0, 0), 0.01)[0], 0.8)

    def test_single_frame_spike_is_rejected(self):
        mapper = Mapper(tau=0, max_speed=10000)
        for _ in range(3):
            mapper.update((0, 0, 0), 0.02)
        self.assertEqual(mapper.update((70, 0, 0), 0.02), (0, 0, 0))
        self.assertEqual(mapper.update((0, 0, 0), 0.02), (0, 0, 0))

    def test_output_speed_is_limited(self):
        mapper = Mapper(tau=0, max_speed=80)
        mapper.recenter((0, 0, 0))
        previous = 0
        for _ in range(10):
            output = mapper.update((70, 0, 0), 0.02)[0]
            self.assertLessEqual(abs(output - previous), 1.600001)
            previous = output

    def test_both_yaw_directions_beyond_twenty_degrees(self):
        for angle in (-70, -45, -20, 0, 20, 45, 70):
            c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            result = rotation_angles(((c, 0, s), (0, 1, 0), (-s, 0, c)))
            self.assertAlmostEqual(result[0], angle)
            self.assertAlmostEqual(result[1], 0)
            self.assertAlmostEqual(result[2], 0)

    def test_pitch_does_not_become_yaw(self):
        c, s = math.cos(0.4), math.sin(0.4)
        result = rotation_angles(((1, 0, 0), (0, c, -s), (0, s, c)))
        self.assertAlmostEqual(result[0], 0)
        self.assertAlmostEqual(result[1], math.degrees(0.4))

    def test_udp_receiver(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(1)
            sender.sendto(packet(30, -10, 2), receiver.getsockname())
            data, _ = receiver.recvfrom(128)
        self.assertEqual(len(data), 48)
        self.assertEqual(struct.unpack("<6d", data), (0, 0, 0, 30, -10, 2))

    def test_invalid_pose(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                packet(value)

    def test_deadzone_gain_limit_and_sign(self):
        self.assertEqual(map_axis(1, 3, 2, 90), 0)
        self.assertEqual(map_axis(12, 3, 2, 90), 30)
        self.assertEqual(map_axis(-12, 3, 2, 90), -30)
        self.assertEqual(map_axis(100, 3, 2, 90), 90)

    def test_wrap_and_recenter(self):
        self.assertEqual(difference(-179, 179), 2)
        mapper = Mapper(tau=0)
        self.assertEqual(mapper.update((179, 0, 0), 0.02), (0, 0, 0))
        self.assertGreater(mapper.update((-170, 0, 0), 0.02)[0], 0)
        mapper.recenter((-170, 0, 0))
        self.assertEqual(mapper.update((-170, 0, 0), 0.02), (0, 0, 0))

    def test_filter_is_time_based(self):
        a, b = Mapper(), Mapper()
        a.recenter((0, 0, 0))
        b.recenter((0, 0, 0))
        a.update((20, 0, 0), 0.04)
        b.update((20, 0, 0), 0.02)
        b.update((20, 0, 0), 0.02)
        self.assertAlmostEqual(a.filtered[0], b.filtered[0])


if __name__ == "__main__":
    unittest.main()
