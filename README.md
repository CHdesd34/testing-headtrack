# Apex HeadTrack

I wanted to look into corners while racing without buying a separate head tracker, so I put together this Python project. It uses a regular webcam to track your head and sends the angles to OpenTrack, which passes them to the game.

Turn your head left to look left, and right to look right. It tracks **head movement, not where your eyes are looking**. Left/right movement is enabled by default. You can also turn on up/down movement and head tilt.

This is still an early project. It works on my ACC setup, but smoothness and tracking stability could use more work.

## Games I've tested

I've only tried this with **Assetto Corsa Competizione (ACC) on Windows** so far. Left/right camera movement works on my setup, but that doesn't mean it'll work perfectly on every PC.

| Game | Status |
| --- | --- |
| Assetto Corsa Competizione (ACC) | Tried on my setup; left/right head tracking works |
| Assetto Corsa (AC) | Not tested yet |
| F1 25 | Not tested yet |

I'd like to support AC and F1 25 too, but I haven't tested them, so I can't promise they'll work. Other AC games, like EVO and Rally, need their own testing. This project is for PC, not console.

## What you'll need

- A Windows PC. Windows 10 or 11 is the suggested setup.
- Python 3.11, 64-bit. The project allows Python 3.10 through 3.12.
- A webcam with a clear view of your face.
- [OpenTrack](https://github.com/opentrack/opentrack/releases).

Put the webcam near the middle of your monitor and try to light your face evenly. You shouldn't need to turn your head very far to look into a corner.

## Getting started

Download and extract the project, then open PowerShell in the folder that contains `pyproject.toml`. Run these commands **one at a time**, waiting for each one to finish:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\apex-headtrack.exe --download-model
.\.venv\Scripts\apex-headtrack.exe
```

You only need to download the model once. After that, start the app from the same folder with:

```powershell
.\.venv\Scripts\apex-headtrack.exe
```

If `py` isn't recognized but `python --version` shows Python 3.11, use `python -m venv .venv` for the first command. If neither works, check that Python is installed and reopen PowerShell after installing it.

The model comes from Google. You can also [download it yourself](https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task) and save it as `models/face_landmarker.task`, or pass its location with `--model "path/to/face_landmarker.task"`. The default model path is relative to the folder you run the app from.

## Setting up OpenTrack

1. Set **Input** to **UDP over network**, with port **4242**.
2. Set **Output** to **freetrack 2.0 Enhanced**. For ACC, enable the TrackIR interface in its output settings. The wording may vary between OpenTrack versions.
3. Start with **Filter: None** and a straight **1:1 yaw mapping** through zero. The app already handles sensitivity and smoothing.
4. Keep X, Y and Z disabled. The app sends zero for those axes.
5. Click **Start**, then launch the game and enter a cockpit view. For ACC, start with the view that shows the steering wheel.
6. Face your monitor and press **F8** to center the view.

Turn your head both ways and check **Raw tracker data** and **Game data**. Yaw should change on both sides of zero.

If left and right are backwards, add `--invert-yaw` to the launch command. You can reverse yaw in OpenTrack instead, but only reverse it in one place.

If OpenTrack's numbers move but the game doesn't, check the output interface, camera view and any head tracking settings in the game. Restart the game after starting OpenTrack. Close other camera tools while testing. Don't replace port 4242 with the game's telemetry port; telemetry isn't a camera input.

## Controls

| Key | Action |
| --- | --- |
| F8 | Center the view at your current head position |
| F9 | Pause or resume |
| F10 | Quit |
| Esc | Quit when the preview window has focus |

The function keys work while the game is in front and trigger when you release the key. You can change them in the `on_release` function in `app.py` if they clash with your game controls.

The first valid head pose becomes the center automatically. Press F8 again whenever you change your sitting position.

## Finding settings that feel right

Here's a starting point with a smaller view range and a little more smoothing:

```powershell
.\.venv\Scripts\apex-headtrack.exe --gain 1.3 --deadzone 1 --smooth 0.10 --limit 40 --max-speed 100
```

Add `--invert-yaw` if the game moves the wrong way. These are starting settings, so feel free to adjust them for your screen and seating position.

| Option | Default | What it does |
| --- | --- | --- |
| `--gain` | 1.3 | Multiplies your head angle after the deadzone. Higher means you need less head movement. |
| `--deadzone` | 1.5 | Ignores small movements near the center, in degrees. |
| `--smooth` | 0.08 | Smoothing time in seconds. Higher feels steadier but adds lag. |
| `--limit` | 45 | Maximum angle sent to OpenTrack for each axis, in degrees. |
| `--max-speed` | 100 | Maximum output turning speed, in degrees per second. |
| `--pitch` / `--roll` | Off | Enables looking up/down or tilting the view. |
| `--invert-yaw` / `--invert-pitch` | Off | Reverses left/right or up/down movement. |
| `--camera` | 0 | Selects the webcam. Try 1 if the wrong camera opens. |
| `--no-preview` | Off | Hides the camera window. Shortcuts still work. |
| `--host` / `--port` | 127.0.0.1 / 4242 | OpenTrack's receiving address and port. |

For example, with a 1.5-degree deadzone and gain of 1.3, a 15-degree head turn gives a target of 17.55 degrees before smoothing. OpenTrack can change that angle again, so keep its mapping at 1:1 while you get things working.

## Reading the preview

The green box marks the detected face. The six yellow dots are just visual markers. They aren't pupil tracking points and aren't used on their own to calculate the head angle.

| Label | Meaning |
| --- | --- |
| `TRACKING` | The app has a valid head pose. |
| `NO FACE` | It can't detect a face right now. |
| `POSE INVALID` | It found a face, but couldn't get a valid rotation. |
| `PAUSED` | Output is paused. |
| `Head yaw` | Your left/right head angle relative to the center. |
| `Output yaw` | The angle currently being sent to OpenTrack. |
| `FPS` | The camera and recognition loop's frame rate, not the game's FPS. |

## Things that still need work

Tracking can struggle with side views, uneven lighting or part of your face being covered. Smiling and other expressions may still affect the angle. There isn't a fixed 20-degree cutoff, but turning too far can make the detector lose your face.

The app reads the latest camera frame and filters short angle spikes. A separate thread aims to send smoothed output at 60 Hz, even when recognition is slower. That helps with stepping between updates, but it can't recover movement the camera missed. Low recognition FPS can still feel delayed or choppy. The three-frame filter also adds a little delay.

If your face disappears briefly, the app holds the last target. After 0.35 seconds without a valid pose, it starts easing back to center. When tracking returns, it keeps the original center. Pausing sends zero, and a normal exit sends a final zero packet. Force-closing the process may skip that last packet.

If the camera won't open, check Windows camera permissions, close apps using it, or try `--camera 1`. If the launcher is missing, check that `pip install -e .` finished successfully and that you're in the project folder.

There isn't a settings window, camera calibration tool or virtual controller fallback yet. Smoothness and stability are still the main things I want to improve.

## How it works

MediaPipe estimates a transformation for the whole face. The app takes the rotation from that transformation, turns it into head angles, and sends them to OpenTrack over UDP. It doesn't calculate eye gaze or use iris movement to steer the view.

Camera frames stay on your PC. The app doesn't record or upload them, and UDP output goes to localhost by default. Installing packages and downloading the model need an internet connection.

## Running the tests

From the project folder:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests cover packets, local UDP delivery, angle mapping, centering, smoothing, spike filtering and output speed limits. GitHub Actions is set up for Python 3.10, 3.11 and 3.12. These tests don't use a real webcam or launch a game, so passing them doesn't prove game compatibility.

For a quick check, center the view, turn both ways, try moving only your eyes, cover your face briefly, and test the shortcuts with the game in front. If you try another game, include the game version, OpenTrack version, webcam and launch settings when sharing your results.

The code is in `src/apex_headtrack`: `app.py` runs the app, `core.py` handles angles and mapping, `camera.py` reads frames, and `output.py` handles the UDP sender.

## Useful links

- [MediaPipe Face Landmarker documentation](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python)
- [OpenTrack quick start guide](https://github.com/opentrack/opentrack/wiki/Quick-Start-Guide-%28WIP%29)
- [OpenTrack UDP receiver source](https://github.com/opentrack/opentrack/blob/master/tracker-udp/ftnoir_tracker_udp.cpp)
- [ACC's official TrackIR update notes](https://assettocorsa.gg/1-0-8-is-out-now-on-steam/)
- [HeadTrack's F1 25 setup guide](https://headtrack.app/games/f1-25/) — another app's guide, not proof that this project works with F1 25.

## License

This project's code is under the MIT license. See [LICENSE](LICENSE). MediaPipe, OpenTrack, the downloaded model and other dependencies have their own licenses.
