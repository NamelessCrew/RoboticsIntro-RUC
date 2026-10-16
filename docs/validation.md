# 第一版验证记录

验证日期：2026-10-16。机器：macOS / Apple M2（arm64），Vulkan SDK 1.3.290.0。

在新的 `RoboticsIntro-RUC` 目录创建独立 `.venv`，从网络安装 `requirements-macos.lock.txt` 的 84 个锁定依赖。`uv pip check` 全部通过，未复用旧工程的虚拟环境。

## 验证命令

```bash
bash setup.sh
bash run.sh doctor
bash run.sh scene
bash run.sh scene --human --seconds 2
bash run.sh suite
bash run.sh python -m unittest discover -s tests -v
```

## 实验结果

| 检查 | 结果 |
| --- | --- |
| 整章 suite | 6 组通过 |
| 交互窗口 | 打开场景并在 2 秒后正常关闭 |
| 纹理替换回归检查 | 已存在 PNG 不被覆盖 |
| 场景 compare | 15 个预设全部完成 |
| 匀速算例 | 100 × 0.01 s，位移 0.2 m；这是算术示例 |
| 官方 PickCube | 30 次随机动作和渲染通过，不是抓取成功率测试 |
| URDF origin | 底座不变，全部下游连杆 z 增加 0.05 m，原始文件未变 |
| reset / step | 40 次 step 后首关节接近 0.3 rad，再次 reset 回到 0 |
| 物理 / 控制频率 | 100 Hz / 20 Hz，每次动作 5 个物理小步 |
| 纹理 | 图像变化、地面摩擦不变 |
| 环境光 | 平均亮度 85.173 → 74.163 |
| FOV 90° → 60° | 相机焦距比例 1.7320509，与 √3 一致 |
| 128² → 256² | 像素数 ×4，视野保持相同 |
| 演示相机 / 查看器 | 设置变化不改变算法相机图像 |
| Panda | qpos 维数 9，action 维数 8 |
| 方块开启碰撞 | 最终中心 z=0.0199998766 m，稳定在约 0.02 m |
| 方块关闭碰撞 | 0.6 s 后中心 z=-1.495230 m，穿过地面 |
| 方块 reset | 中心高度恢复至 0.30 m，并清零速度 |

可读机器记录见 [validation-results.json](validation-results.json)。文档中的图像和 GIF 来自此次运行。

## 验证边界

- 真实物理与渲染验证覆盖本机 macOS Apple Silicon；Linux / Windows / WSL 未在本次发布中实机测试。
- 所有课程场景使用 CPU 物理。这里的“无窗口”运行仍调用 Vulkan 渲染。
- SO100 为 5 个臂关节 + 1 个夹爪关节，本章不使用可选 Pinocchio 逆运动学组件。
- 域随机化页用于讲解概念，预设对照不等于完成随机训练；PickCube 随机动作不等于学习抓取策略。
- 数值检查使用容差，不要求不同显卡上的像素与本机截图完全相同。算法相机独立性检查是在同一次、本机运行中比较图像。
