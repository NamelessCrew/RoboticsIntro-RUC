# MuJoCo 分支验证记录

验证日期：2026-11-01。分支：`RoboticsIntro-RUC-mujoco`。本记录替代旧 ManiSkill/SAPIEN 验证；不把旧截图或旧依赖结果混入新平台结论。数值摘要保存在 [validation.json](validation.json)，完整原始输出在本机 `outputs/`（不提交 Git）。

## 环境与安装

macOS 26.5.1，Apple Silicon arm64；Python 3.11.14，MuJoCo 3.3.7，NumPy 2.3.4，Pillow 11.3.0。使用仓库 `scripts/setup_env.py` 创建全新 `.venv`，只安装 `requirements.txt` 的固定二进制依赖。`pip check` 输出 `No broken requirements found`，`doctor` 实际加载 Panda 与 SO100，qpos/action 分别为 9/8、6/6。

这台验证机原有默认 Python 为 3.14，不在课程支持范围；下载的 Python 3.11 保存在忽略提交的 `.python-runtime/`，`.venv` 引用该持久位置。正常安装也可使用系统 Python 3.11/3.12。POSIX 环境采用标准 venv 的 symlink 方式，Windows 采用 copies，避免独立发行版 Python 的相对动态库路径失效。

实际运行命令（仓库根目录）：

```text
.python-runtime/cpython-3.11.14-macos-aarch64-none/bin/python3.11 scripts/setup_env.py
python3 run.py doctor
python3 run.py test
.venv/bin/python -m pip check
python3 run.py suite
python3 run.py grasp --release-check
python3 run.py vision-grasp --release-check
python3 run.py vision-grasp --cube-x .43 --cube-y .025 --release-check --output outputs/week07/vision-offset
python3 run.py scene --human --seconds 2 --output outputs/viewer-smoke
```

前几次探索的 `/tmp` 环境不作为最终入口；上述最终工作副本安装与运行均已执行。`run.py` 可从系统 Python 3.14 调用，但课程模块在所选 `.venv` 的 3.11 内运行。

## 第六周结果

`outputs/week06/suite.json`：`status=passed`，`rendered=true`。

| 检查 | 实际结果 |
| --- | --- |
| 时间小步 | 500×0.002 s=1 s；速度0.2 m/s，最终位移0.20000000000000162 m |
| reset / step | 100 个控制步=2 s；第一关节0→0.2999999995 rad；重置 qpos、零速度、零时间均恢复 |
| URDF +5 cm | Base 不动，全部下游 link z 增加0.05 m；原始 URDF SHA256 不变 |
| 方块碰撞开 | 2 s 后中心 z=0.0199607252 m |
| 方块碰撞关 | 中心 z=−19.339620 m |
| 无重力 | 中心保持 z=0.300000 m |
| 14 场景 compare | 全部通过：状态不变量、图片变化、灯光变暗、纹理摩擦不变、FOV焦距√3倍、分辨率焦距2倍、算法/演示相机独立 |

原始 URDF 摘要：`dee987ca9b5a7e961a6bc87eb71c3b00922968f77214527cddd4cfc860822abc`。图片对照平均绝对差见 JSON；这些数值依赖渲染后端，课堂判据只要求有效变化/不变量，不要求所有电脑逐像素与本机相同。

## 第七周结果

以下均为自由方块经真实手指接触抬升；无物体 weld、mocap 或跟随夹爪的重定位。

| 任务 | 结果 | 抬升 | 保持期双指接触/达标高度 | 最大速度 | 相对TCP最大偏离 |
| --- | --- | --- | --- | --- | --- |
| 已知位置 [0.45,0] | 成功 | 0.119174 m | 1.0 / 1.0 | 0.00215 m/s | 0.154 mm |
| RGB-D [0.45,0] | 成功 | 0.119082 m | 1.0 / 1.0 | 0.00211 m/s | 0.174 mm |
| RGB-D [0.43,0.025] | 成功 | 0.119140 m | 1.0 / 1.0 | 0.00215 m/s | 0.157 mm |

每个保持期有50个控制步，即1 s；整个保持期的最低抬升仍高于6 cm。所有释放检查通过：打开夹爪后下降超过5 cm，落到地面后不再报告成功。全程张开夹爪的负对照报告 `success=false`、抬升≈0、双指接触比例0。

最终灯光设置下，默认与偏移场景定位误差分别约 **1.98 mm、1.84 mm**。这是无噪声仿真、已知相机标定、俯视单个平放红块、已知半高0.02 m的结果；颜色阈值可能受光照和边缘影响。它不是 YOLO 香蕉检测准确率，也不是实际相机精度。段末 TCP 跟踪误差约5–6 mm，独立于定位误差。

## 回归与独立复核

`python3 run.py test`：**11 项测试通过**。覆盖：已知坐标变换、无目标/无效深度、相机退化、180°姿态误差不退化为零、轨迹速度/终点、短暂抬升不能误判保持、自由物体无绑定、真实抓取/释放/张开失败对照、重力/碰撞、URDF/重置和学生纹理保留。

另由独立 **Astra medium** 审查并复跑上述11项测试，结果通过；使用未列为教程例子的目标 [0.47,−0.025] 做 RGB-D 抓取/释放，抬升约0.1193 m、接触比例1.0、定位误差0.458 mm。复核同时检查：深度反投影到地面的 z 误差约9.4 μm、改变算法相机 target 后演示图逐像素相同、越界动作/无效深度/不可达 IK 会报错。独立运行输出位于验证机 `/tmp/ruc-acceptance-final/`；关键结果摘要已归档到 JSON。

审查曾指出保持期不能只看末帧高度、IK不能只验位置；最终实现已检查整个保持期高度/速度/相对位置和 IK 的完整旋转向量残差，并补充相应回归。

## 真实截图、查看器与限制

已逐张检查默认 Panda、抓取抬升与检测图，机器人完整可见，红色方块确实位于两指间。文档图片来自上述最终运行：

- `images/baseline.png`：Panda 演示相机；`images/exercise.png`：综合练习算法相机。
- `images/cube_drop.gif`：有碰撞的真实下落；`images/grasp_lifted.png`、`images/grasp_detection.png`：视觉抓取与定位。

macOS `scene --human --seconds 2` 经 `mjpython` 打开查看器并自动退出，退出码0。运行器对独立发行版 Python 的 base-prefix lib 目录做局部动态库回退，用户无需手工设置路径。

当前 CGL 驱动提示 `ARB_clip_control unavailable ... depth accuracy will be limited`；图片/反投影/定位与抓取验证仍通过。误差数据来自这个后端，应保留该精度限制说明。受限沙箱无法建立 CGL 上下文，本次渲染在允许访问本机图形设备的执行环境完成。

Windows / Linux 和 Python 3.12 **未在本次实机执行**。已提供原生脚本和 GitHub Actions：三系统×两Python版本的物理测试，以及 Linux Xvfb 图像/视觉抓取。当前未推送、未运行远端 CI；配置存在不代表这些平台已验证。任意物体/姿态、碰撞规划、真实硬件、香蕉资产和 YOLO 都不在当前验收结果中。

## 后续：默认MP4输出验证

第七周默认输出已改为 `grasp.mp4`，不再生成GIF或阶段图片；历史验证图片保留。新增 `--save-images` 与 `--no-video`。固定依赖 `imageio-ffmpeg==0.6.0` 的平台wheel包含编码器。流式写H.264、512×512、10fps，按仿真时间采样，不受窗口倍速影响。

2026-11-01 实际运行：`grasp --release-check --output outputs/week07/mp4-known` 得到137帧、13.7秒、393259字节；`vision-grasp --output outputs/week07/mp4-vision` 得到116帧、11.6秒、381640字节。已解码全部帧并检查首/末帧，fresh目录仅有MP4和数值JSON/NPZ，无PNG/GIF/阶段目录。两种抓取仍成功。`vision-grasp --no-video --save-images` 已验证可单独保留教学图。原有目录中的旧图不会被删除。

本次只运行相关检查：2项真实小视频编解码/采样/异常关闭测试、3项实时窗口测试、5项物理测试通过。独立Astra复核全部解码、时间轴与无图默认目录，并模拟关闭窗口验证 `aborted / success=false`、可播放 `grasp.partial.mp4`、无完整MP4和部分数值轨迹。编码异常/中止均关闭进程，结果JSON明确标记视频状态。
