# MuJoCo 迁移计划、执行状态与教材对照

目标分支：`RoboticsIntro-RUC-mujoco`。范围为第六周仿真平台与第七周抓取实践，不推送远程。默认 Franka Panda，SO100 本地 URDF 保留为模型导入实验。用户明确允许更换机器人和下载 Franka 模型。

## 决策与完成状态

| 工作 | 状态 | 可审查结果 |
| --- | --- | --- |
| 替换活动 ManiSkill/SAPIEN/Gym/Torch/Vulkan 依赖 | 已完成 | 原生 MuJoCo＋NumPy＋Pillow；requirements 固定版本；无框架注册 |
| Windows 原生安装/启动 | 已实现，待 Windows 实机验证 | Python Launcher 命令，cmd/PowerShell 入口，共用安装器与 run.py；CI 包含 Windows |
| Panda 模型与许可证 | 已完成 | Menagerie 官方模型、全部引用 mesh、Apache 2.0、固定提交与资源摘要 |
| SO100 URDF、网格与许可 | 已保留并验证 | 原生 URDF 导入，PLY→OBJ 缓存，+5 cm/source SHA256 实验 |
| 第六周完整教学目标 | 已完成并在 Mac 执行 | reset/step、时间、URDF、相机、FOV、分辨率、独立演示相机、纹理、光照、qpos、机器人对照、重力/碰撞、14 场景 compare、suite |
| 第七周已知位置真实抓取 | 已完成并执行 | 规划→IK→关节 PD→物理接触；双指接触与抬升/稳定保持；释放/张开负对照 |
| RGB-D 扩展 | 已完成并执行 | 唯一红色方块掩码、K/T、米制深度、顶面补偿；默认与移动物体抓取 |
| 两周教材与课件文字 | 已完成 | week06 更新、week07 教程、40 页文字稿；未生成 PPTX |
| 回归、数据与真实截图 | 已完成 | 自动物理/几何/纹理测试，Mac 实际渲染与抓取记录；见 validation.md |
| Windows / Linux 实机与 CI 结果 | 待执行 | 仅提交 CI 工作流，不把配置文件当作已经通过的跨平台验证 |
| SO100 香蕉与 YOLO | 扩展，未实现 | 不下载/伪造缺失香蕉资产或权重，不声称复现教材检测性能 |

## 实施顺序

1. 核对旧课件目标、教材两节与本地模型资源；建立依赖/接口替换表。
2. 用固定的 MuJoCo 与 Python 版本建立可编译、可渲染的单环境；导入 Panda 与本地 SO100。
3. 完成第六周数值与图像对照，保留可编辑 URDF 和学生纹理。
4. 用已知位置方块隔离感知误差，完成物理抓取、释放与失败对照。
5. 用 RGB-D 定位替换目标来源，移动物体做独立验证；补充数据、截图和课堂任务。
6. 运行回归与干净安装，记录已验证/未验证平台；本地审查，不自动 push。

## 源教材对齐

本次读取 `/Users/lozo/Desktop/动手学具身智能/sections/9_example_grasp_object.tex` 和 `sections/15_vision_grasp_practice.tex`，并检查 `main.tex`。两个相关 `input` 当前均被注释，不能仅按文件名前缀断言它们在最终书中是“第 9 / 第 15 章”，也不能把后者误写成课程第七章。课程“第七周”是教学安排。

| 教材内容 | 课程保持的目标 | 本实现与差异 |
| --- | --- | --- |
| 综合实践：planner→controller | 人工关键点→线性轨迹→逐点跟踪 | LinearPlanner 显式独立；CartesianController 展开 IK 和 PD 调用 |
| `cartesian_pose` 控制模式 | 笛卡尔目标经雅可比 IK 转成关节目标 | 原生 MuJoCo site Jacobian，独立虚拟 MjData；无原控制模式字符串 |
| 预备、下降、闭合、抬起 | 分阶段组织抓取系统 | 同样阶段；几何偏移按 Panda 方块重新设置，不能照抄香蕉参数 |
| 环境位置查询 | 先提供已知位置基线 | known 模式读取稳定后的方块中心；这是显式真值基线 |
| `evaluate()` 的抓住/抬起/成功 | 让控制与评价解耦 | 双指真实力、≥6 cm 抬升、1 s 保持期高度/接触/速度/相对位置；另加负对照 |
| 视觉扩展的感知→规划→控制 | 替换位置来源，复用后两层 | RGB-D 分割/反投影输出同样世界 xyz；真值只作误差评估 |
| YOLO 香蕉框 | 从 RGB 选目标像素 | 基础版用唯一红块颜色掩码；没有 YOLO、没有香蕉识别能力声明 |
| K、反投影、外参、深度统计 | 像素＋深度→世界坐标 | 保留公式；适配 MuJoCo/CV 轴约定，主点明确；对点云取中位数 |
| ManiSkill 深度毫米→米 | 单位一致 | MuJoCo Renderer 直接返回米制光轴深度，保存 depth_m，不再除1000 |
| 香蕉上某个可见点 | 定位结果应能供抓取使用 | 方块顶面点需减已知半高，显式说明中心估计的几何先验 |

## 关键工程边界

Panda 资产原样随仓库保存，课程修改（TCP site、相机、灯光、物体）在 Python 组合场景中完成。资源来源固定于 Menagerie 提交 `b0655057a9df2abe39ea7fc989914ba6f248301c`，详见 `assets/franka_emika_panda/PROVENANCE.json`。SO100 原件不改写，转换结果放忽略提交的 `.cache/`。

新接口直接使用 `MjModel/MjData`，不提供完整 Gymnasium 契约（如 action_space / observation_space / registry）。`reset/step` 的小型教学返回值用于课程一致性，不声称兼容旧训练程序。原 `official` 命令不再保留，因为其随机动作测试不能代表迁移后抓取能力。

线性轨迹没有碰撞规划；IK 与接触参数只在示例工作区验证。自由方块完全受重力与接触力驱动，机器人与物体之间没有 weld/mocap/parenting。Panda 的等式约束只连接两个手指，不连接物体。

更换为香蕉＋YOLO 需要独立补齐：资源许可、合理质量/惯量与碰撞代理、可达抓取点、类别/权重与预处理、遮挡下有效深度采样、误差与接触保持验证。当前分支对这些留有清晰层边界，不以默认返回真值替代失败的视觉检测。
