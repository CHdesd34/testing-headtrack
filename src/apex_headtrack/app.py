import argparse
import math
import pathlib
import socket
import threading
import time
import urllib.request

from .core import Mapper, packet, rotation_angles
from .camera import LatestCamera
from .output import OutputPump

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"


def positive(value):
    number = float(value)
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError("must be positive and finite")
    return number


def main():
    parser = argparse.ArgumentParser(description="Head pose (not gaze) -> OpenTrack UDP")
    parser.add_argument("--model", type=pathlib.Path, default=pathlib.Path("models/face_landmarker.task"))
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, choices=range(1, 65536), metavar="PORT", default=4242)
    parser.add_argument("--gain", type=positive, default=1.3)
    parser.add_argument("--deadzone", type=positive, default=1.5)
    parser.add_argument("--limit", type=positive, default=45)
    parser.add_argument("--max-speed", type=positive, default=100, help="maximum output degrees per second")
    parser.add_argument("--smooth", type=positive, default=0.08, help="smoothing time constant in seconds")
    parser.add_argument("--invert-yaw", action="store_true")
    parser.add_argument("--invert-pitch", action="store_true")
    parser.add_argument("--pitch", action="store_true", help="enable up/down look; default yaw only")
    parser.add_argument("--roll", action="store_true")
    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args()
    if args.download_model:
        args.model.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.model.with_suffix(".download")
        try:
            with urllib.request.urlopen(MODEL_URL, timeout=60) as response, temporary.open("wb") as out:
                import shutil
                shutil.copyfileobj(response, out)
            temporary.replace(args.model)
        finally:
            temporary.unlink(missing_ok=True)
        print(f"Downloaded Google model: {args.model}")
        return
    if not args.model.is_file():
        parser.error("Model missing. Run apex-headtrack --download-model first.")

    import cv2
    import mediapipe as mp
    import numpy as np
    from pynput import keyboard

    # Fixed surface landmarks only. Iris landmarks and gaze are never used.
    indices = [1, 152, 33, 263, 61, 291]
    # Map/filter observations here; time smoothing belongs to the 60 Hz sender.
    mapper = Mapper(args.gain, args.deadzone, args.limit, tau=0, max_speed=1e9)
    center_event, pause_event, stop_event = threading.Event(), threading.Event(), threading.Event()

    def on_release(key):
        if key == keyboard.Key.f8:
            center_event.set()
        elif key == keyboard.Key.f9:
            pause_event.set()
        elif key == keyboard.Key.f10:
            stop_event.set()

    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(args.model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_faces=1,
        output_facial_transformation_matrixes=True)
    cap = cv2.VideoCapture(args.camera)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener = keyboard.Listener(on_release=on_release)
    paused, previous, timestamp = False, time.monotonic(), -1
    lost_since = None
    camera_reader = None
    output_pump = None
    sequence = 0
    fps = 0.0
    try:
        if not cap.isOpened():
            raise RuntimeError("Cannot open camera. Check camera index and Windows privacy settings.")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        camera_reader = LatestCamera(cap)
        output_pump = OutputPump(sock, (args.host, args.port), args.smooth, args.max_speed)
        listener.start()
        print("F8: center | F9: pause/resume | F10: quit. Face forward for initial center.")
        with mp.tasks.vision.FaceLandmarker.create_from_options(options) as detector:
            while not stop_event.is_set():
                sequence, frame = camera_reader.next(sequence)
                now = time.monotonic()
                elapsed = max(now - previous, 1e-6)
                fps = 0.9 * fps + 0.1 / elapsed
                dt, previous = min(elapsed, 0.1), now
                timestamp = max(timestamp + 1, int(now * 1000))
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
                pose = None
                if result.face_landmarks:
                    h, w = frame.shape[:2]
                    points = np.array([(result.face_landmarks[0][i].x * w,
                                        result.face_landmarks[0][i].y * h) for i in indices], dtype=np.float64)
                    if not args.no_preview:
                        landmarks = result.face_landmarks[0]
                        left = max(0, min(w - 1, int(min(p.x for p in landmarks) * w)))
                        right = max(0, min(w - 1, int(max(p.x for p in landmarks) * w)))
                        top = max(0, min(h - 1, int(min(p.y for p in landmarks) * h)))
                        bottom = max(0, min(h - 1, int(max(p.y for p in landmarks) * h)))
                        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                        for x, y in points:
                            cv2.circle(frame, (int(x), int(y)), 3, (0, 255, 255), -1)
                    if result.facial_transformation_matrixes:
                        # MediaPipe fits the canonical face as a whole. Avoid the
                        # six-point PnP solution that can flip behind the camera.
                        basis = np.asarray(result.facial_transformation_matrixes[0], dtype=np.float64)[:3, :3]
                        if np.isfinite(basis).all():
                            try:
                                u, singular_values, vt = np.linalg.svd(basis)
                                if singular_values.min() > 1e-6:
                                    correction = np.eye(3)
                                    correction[2, 2] = np.linalg.det(u @ vt)
                                    pose = rotation_angles(u @ correction @ vt)
                            except (np.linalg.LinAlgError, ValueError):
                                pose = None
                if pause_event.is_set():
                    paused = not paused
                    pause_event.clear()
                if pose is not None:
                    lost_since = None
                    if center_event.is_set():
                        mapper.recenter(pose)
                        output_pump.set_target((0, 0, 0), reset=True)
                        center_event.clear()
                    output = mapper.update(pose, dt)
                else:
                    lost_since = now if lost_since is None else lost_since
                    output = tuple(mapper.filtered)
                    if now - lost_since > 0.35:
                        # Return gradually instead of snapping the view to center.
                        mapper.filtered = [v * math.exp(-dt / 0.25) for v in mapper.filtered]
                        mapper.history.clear()
                        output = tuple(mapper.filtered)
                if paused:
                    output = (0.0, 0.0, 0.0)
                yaw, pitch, roll = output
                output = (-yaw if args.invert_yaw else yaw,
                          (-pitch if args.invert_pitch else pitch) if args.pitch else 0.0,
                          roll if args.roll else 0.0)
                output_pump.set_target(output, reset=paused)
                output = output_pump.current()
                if not args.no_preview:
                    status = "PAUSED" if paused else ("TRACKING" if pose else
                             ("POSE INVALID" if result.face_landmarks else "NO FACE"))
                    cv2.putText(frame, f"{status}  yaw={output[0]:.1f}  FPS={fps:.0f}  F8 center F9 pause F10 quit",
                                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 0), 1)
                    if pose is not None:
                        relative_yaw = (pose[0] - mapper.center[0] + 180) % 360 - 180
                        cv2.putText(frame, f"Head yaw={relative_yaw:.1f} deg  Output yaw={output[0]:.1f} deg",
                                    (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 1)
                    cv2.imshow("Apex HeadTrack", frame)
                    if cv2.waitKey(1) & 0xFF == 27:
                        break
                    if cv2.getWindowProperty("Apex HeadTrack", cv2.WND_PROP_VISIBLE) < 1:
                        break
    finally:
        try:
            if output_pump is not None:
                output_pump.stop()
            sock.sendto(packet(), (args.host, args.port))
        finally:
            listener.stop()
            if camera_reader is not None:
                camera_reader.stop()
            cap.release()
            sock.close()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
