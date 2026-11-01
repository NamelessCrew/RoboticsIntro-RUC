# 来源与第三方材料

本仓库是 RoboticsIntro-RUC 课程配套实验。MuJoCo 分支包含第六周仿真平台和第七周抓取实践，保留原课程资源的来源说明。

- 最初教学工程：[xwinks/codebase_for_emboided_ai](https://github.com/xwinks/codebase_for_emboided_ai)，原验证起点是 ZIP 标识提交 `ad7a64158264bc273ca77875bd75f08996edbacd`。该 ZIP 没有仓库级许可证，本仓库不为上游代码另行声明授权。
- 仿真引擎：[Google DeepMind MuJoCo](https://github.com/google-deepmind/mujoco)，以 Python 依赖安装，遵循其 Apache-2.0 许可证。[Python 文档](https://mujoco.readthedocs.io/en/3.3.7/python.html)与 [MJCF 文档](https://mujoco.readthedocs.io/en/3.3.7/XMLreference.html)是 API 依据。
- Franka Panda：[官方 MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie/tree/b0655057a9df2abe39ea7fc989914ba6f248301c/franka_emika_panda)，固定提交 `b0655057a9df2abe39ea7fc989914ba6f248301c`。模型是从 Franka 公开 URDF 整理的简化 MJCF，并非现实机器人参数校准。本仓库保留原始 XML、引用的网格、README、CHANGELOG、示例图与 [Apache-2.0 LICENSE](chapters/week06/assets/franka_emika_panda/LICENSE)；文件摘要在 [PROVENANCE.json](chapters/week06/assets/franka_emika_panda/PROVENANCE.json)。课程 TCP、灯光、相机和物体在 Python 中组合，没有修改所分发的上游文件。
- SO100 模型：[TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100)，使用旧课程从 ManiSkill 整理的版本。原始 [README](chapters/week06/assets/so100/README.md)与 [Apache-2.0 LICENSE](chapters/week06/assets/so100/LICENSE)完整保留。该 README 称“6DOF”，本课程更精确区分为 5 个臂关节＋1 个夹爪关节。PLY→OBJ 仅在缓存生成格式转换副本。
- 原课程基于 ManiSkill / SAPIEN；本分支活动代码与依赖已迁移，不再继承它们的机器人类或控制器。
- 教学内容参考《动手学具身智能》的综合抓取与视觉抓取两节，保留概念和层次对应；差异见 [migration-plan.md](docs/migration-plan.md)。没有分发香蕉资产或 YOLO 权重，也不声明对应检测功能已实现。
- `docs/images/` 是本课程程序的真实运行截图/动画；模型目录中的 `panda.png` 是保留的上游说明图，两者来源不同。

第三方模型许可证不自动覆盖全部课程材料。
