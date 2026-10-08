# Apex HeadTrack

用普通摄像头追踪**头部朝向**，通过 OpenTrack 控制赛车游戏视角。向左转头向左看，向右转头向右看。默认只输出水平旋转，可选开启俯仰和侧倾。

这是可运行的初始版本。算法、UDP 协议和自动测试已提供；摄像头识别效果及各游戏接入需要实机验收，不能视为已经完成游戏兼容认证。面向 Windows PC，不支持主机版。AC 指 Assetto Corsa 原版，ACC 指 Assetto Corsa Competizione；其他 AC 系列作品需要单独验证。

## 原理

摄像头 → MediaPipe 人脸整体变换矩阵 → 头部旋转角度 → 回中/死区/增益/平滑 → UDP → OpenTrack → 游戏相机。

使用 MediaPipe 的整体人脸变换矩阵估计旋转，不再单独用六点 solvePnP 求解。预览中的六个黄色点仅作为检测标记。**不读取虹膜或瞳孔关键点来计算视线，不估计视线方向**。通用人脸模型会影响角度精度；侧脸、遮挡、强逆光仍可能造成丢失。表情干扰仍需实机验证。

预览 `TRACKING` 表示姿态有效，`NO FACE` 表示没有检测到人脸，`POSE INVALID` 表示检测到人脸但矩阵无效。`Head yaw` 是相对于回中姿态的头部角度，`Output yaw` 是映射后发给 OpenTrack 的角度，二者不是同一数值。没有设置 20° 的输出上限，默认最大输出 45°。

图像只在本机内存处理，不录制或上传；默认 UDP 只发送到本机。下载模型需要网络，模型和第三方依赖遵循各自许可，不包含在本仓库 MIT 许可中。

## 安装与启动

推荐 Windows 10/11、Python 3.11 64 位、普通 USB 摄像头，先安装 [OpenTrack](https://github.com/opentrack/opentrack/releases)。在项目根目录打开 PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\apex-headtrack.exe --download-model
.\.venv\Scripts\apex-headtrack.exe
```

模型来自 Google 官方固定版本地址。也可手动下载 [face_landmarker.task](https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task)，放在 `models/face_landmarker.task`，或传 `--model 路径`。请从项目根目录启动，默认模型路径相对于当前工作目录。

## OpenTrack 设置

1. Input 选择 **UDP over network**，端口 **4242**。
2. Output 选择 **freetrack 2.0 Enhanced**；在其设置中按游戏要求启用 TrackIR 接口。
3. 初次调试 Filter 选 None，yaw 映射先设成线性 1:1。本程序已经处理平滑和增益，叠加曲线会放大或增加延迟。
4. 禁用 X/Y/Z；默认只用 yaw。点击 Start，再启动游戏。
5. 正对屏幕按 F8 回中，观察 OpenTrack 的 Raw tracker data 和 Game data。转头后 yaw 应连续变化，X/Y/Z 始终为零。
6. 若左右方向相反，用 `--invert-yaw` 或 OpenTrack 的轴反向功能，选择一处反向即可。预览是未镜像画面，不能仅凭画面里的左右判断游戏方向。

本程序不会直接读写游戏内存、安装 DLL 或模拟方向盘输入。游戏接入依赖 OpenTrack 和游戏的头追接口。

## 游戏接入与验证状态

| 游戏 | 预期接入方式 | 本项目实测状态 |
| --- | --- | --- |
| Assetto Corsa | OpenTrack 的 TrackIR/FreeTrack 输出，驾驶舱视角 | 待验证 |
| Assetto Corsa Competizione | OpenTrack 的 TrackIR 输出，游戏开启头追（若当前版本提供开关） | 待验证 |
| F1 25 | 尝试 OpenTrack 的 FreeTrack/TrackIR 输出，驾驶舱视角 | 待验证，不能保证所有版本可用 |

AC/ACC 的 TrackIR 接口有公开记录。F1 25 有第三方头追软件的 FreeTrack 接入说明，但这不是本项目或游戏官方的兼容认证。若 OpenTrack 数值正确而游戏无响应，先检查游戏视角、输出接口设置、启动顺序和是否有其他相机/头追软件争用；不要用游戏 UDP 遥测端口替代 4242，遥测不等于相机输入。

AC 装有 CSP/NeckFX 或其他相机插件时，先关闭冲突功能做基线测试。不要将 AC 的行为直接推断到 EVO、Rally 等其他作品。

## 操作与调参

全局快捷键即使游戏在前台也可使用：**F8 回中、F9 暂停/恢复、F10 退出**（松开按键时触发，避免长按重复切换）。预览窗口内 Esc 也可退出。快捷键冲突可在 `app.py` 的 `on_release` 中修改。无预览模式依然启用这些快捷键。

```powershell
# 水平头追，轻转头即可看向弯心
.\.venv\Scripts\apex-headtrack.exe --gain 2.5 --deadzone 1.5 --smooth 0.08
# 开启上下看；切换摄像头；方向反转
.\.venv\Scripts\apex-headtrack.exe --camera 1 --pitch --invert-yaw
# 不显示摄像头窗口
.\.venv\Scripts\apex-headtrack.exe --no-preview
```

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `--gain` | 1.3 | 死区之外的输入角度倍数 |
| `--deadzone` | 1.5 | 头部旋转死区，度 |
| `--limit` | 45 | 每轴最大输出，度 |
| `--max-speed` | 100 | 每轴最大输出转速，度/秒 |
| `--smooth` | 0.08 | 时间平滑常数，秒；越大越稳、越迟 |
| `--pitch` / `--roll` | 关闭 | 俯仰 / 侧倾输出 |
| `--invert-yaw` / `--invert-pitch` | 关闭 | 对应轴方向反转 |
| `--host` / `--port` | 127.0.0.1 / 4242 | OpenTrack 接收地址 |

例：输入转头 15°、死区 1.5°、增益 2.5，目标输出 33.75°（平滑逐渐达到）。第一帧有效姿态自动作为中心；每次调整坐姿后按 F8。短暂丢脸保持最后输出，持续超过 0.35 秒逐渐回到零；恢复后继续使用原来的中心。暂停期间发送零，正常退出也发送零。强制终止进程无法保证发送最后一个归零包。

针对跳变和延迟：只消费最新摄像头帧，加入三帧角度中值过滤、输出转速限制，并降低默认增益和最大角度。预览 FPS 是实际识别循环帧率，不是 UDP 接收或显示器帧率；持续低于约 20 时，仍可能感到卡顿。中值过滤会增加约一帧延迟，转速限制会使快速转头的视角稍晚到达。

UDP 发送现已独立于识别循环，目标频率 60 Hz。识别循环仅更新目标角度，发送线程负责时间平滑与转速限制，避免识别每帧完成时才突然更新游戏角度。它不能补回未观测到的头部运动，也不能保证低识别帧率时没有延迟。OpenTrack 测试时仍建议线性 1:1 映射、Filter None，避免叠加平滑。

摄像头无法打开时，检查 Windows 摄像头隐私权限、关闭占用摄像头的软件，或尝试 `--camera 1`。安装失败时先确认 Python 版本与位数，使用独立虚拟环境。

## 验收与开发

```powershell
$env:PYTHONPATH = "src"
py -3.11 -m unittest discover -s tests -v
```

测试覆盖 UDP 实际回环收发、48 字节布局、非有限值拒绝、死区/增益/限幅、角度跨 ±180°、回中与不同帧率下的平滑一致性。GitHub Actions 在 Python 3.10/3.11/3.12 上运行核心测试，不代表摄像头或游戏端到端测试通过。

实机验收：正对屏幕回中 → 左右各转 15–30° → 确认游戏视角同向连续转动 → 只动眼睛时不产生持续视角变化 → 遮脸超过 0.35 秒回零 → 游戏在前台测试 F8/F9/F10。每个游戏分别记录版本、OpenTrack 版本、相机型号、参数和结果，再更新兼容状态。

源码在 `src/apex_headtrack`；`core.py` 负责映射和数据包，`app.py` 负责摄像头、姿态与生命周期。当前没有 GUI 设置页、摄像头标定或虚拟手柄后备接口。

## 发布到 GitHub

将本目录内容上传到新仓库即可。仓库建议名称 `apex-headtrack`。模型、虚拟环境和缓存已加入 `.gitignore`。填写你自己的作者信息，按需要调整 MIT 版权行；第三方模型与依赖不应声称为自己的作品。此交付没有替你创建或推送远程 GitHub 仓库。

## 参考

- [MediaPipe Face Landmarker Python 官方文档](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python)
- [OpenTrack UDP 接收器源码](https://github.com/opentrack/opentrack/blob/master/tracker-udp/ftnoir_tracker_udp.cpp)
- [OpenTrack Quick Start](https://github.com/opentrack/opentrack/wiki/Quick-Start-Guide-%28WIP%29)
- [TrackIR 官方游戏列表](https://www.trackir.com/games/)
- [ACC 官方 1.0.8 更新说明：TrackIR](https://assettocorsa.gg/1-0-8-is-out-now-on-steam/)
- [HeadTrack 的 F1 25 FreeTrack 接入说明（第三方）](https://headtrack.app/games/f1-25/)

## License

MIT，见 LICENSE。
