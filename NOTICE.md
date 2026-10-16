# 来源与第三方材料

本仓库为 RoboticsIntro-RUC 课程的配套实验代码。第一版依据第六周“仿真平台”的教学安排整理。

- 初始教学工程：[xwinks/codebase_for_emboided_ai](https://github.com/xwinks/codebase_for_emboided_ai)。本地验证以下载 ZIP 中标识的提交 `ad7a64158264bc273ca77875bd75f08996edbacd` 为起点。场景代码和课程实验在此基础上补充、整理，保留来源说明。该 ZIP 未附仓库级许可证，本仓库不对上游代码另行声明授权。
- 仿真框架：[ManiSkill](https://github.com/haosulab/ManiSkill) 和 [SAPIEN](https://github.com/haosulab/SAPIEN)，作为 Python 依赖安装，遵循各自许可证。
- SO100 模型：来自 [TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100)，使用 ManiSkill 中整理过的版本。模型的原始 [说明](chapters/week06/assets/so100/README.md) 和 [Apache 2.0 许可证](chapters/week06/assets/so100/LICENSE) 随模型保留。
- `chapters/week06/robot.py` 继承 ManiSkill 内置 SO100 类，课程只指定本地 URDF 路径，控制器实现由依赖提供。
- 文档示例图由本仓库的仿真实验生成。

本仓库未将第三方模型许可证扩展到全部课程材料。
