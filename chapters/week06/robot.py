"""本地模型入口：Panda 原生 MJCF；SO100 经 MuJoCo 的 URDF 编译器导入。"""
from pathlib import Path
import hashlib
import struct
import xml.etree.ElementTree as ET

import mujoco

ROOT = Path(__file__).resolve().parents[2]
SO100_DIR = Path(__file__).parent / "assets/so100"
PANDA_DIR = Path(__file__).parent / "assets/franka_emika_panda"
SO100_JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
PANDA_JOINTS = [f"joint{i}" for i in range(1, 8)] + ["finger_joint1", "finger_joint2"]


def ply_to_obj(source, destination):
    """转换随仓库提供的 Blender binary little-endian PLY 碰撞网格；不更改原件。

    只支持当前资源的 float 属性与 uchar/uint 面索引，遇到新格式显式报错。
    MuJoCo 网格加载器接受 OBJ/STL，不接受 PLY。
    """
    raw = Path(source).read_bytes()
    header, data = raw.split(b"end_header\n", 1)
    lines = header.decode("ascii").splitlines()
    if "format binary_little_endian 1.0" not in lines:
        raise ValueError("Expected binary_little_endian PLY")
    nvertex = int(next(x.split()[-1] for x in lines if x.startswith("element vertex ")))
    nface = int(next(x.split()[-1] for x in lines if x.startswith("element face ")))
    vertex_lines = lines[lines.index(f"element vertex {nvertex}")+1:lines.index(f"element face {nface}")]
    if any(not x.startswith("property float ") for x in vertex_lines):
        raise ValueError("Unsupported PLY vertex property")
    if "property list uchar uint vertex_indices" not in lines:
        raise ValueError("Unsupported PLY face indices")
    nprop = len(vertex_lines)
    stride = nprop * 4
    vertices = [struct.unpack_from("<" + "f"*nprop, data, i*stride)[:3] for i in range(nvertex)]
    offset = nvertex * stride
    faces = []
    for _ in range(nface):
        count = data[offset]
        offset += 1
        faces.append(struct.unpack_from("<" + "I"*count, data, offset))
        offset += 4*count
    text = "# Converted from local SO100 PLY; original license applies.\n"
    text += "".join("v " + " ".join(f"{v:.9g}" for v in p) + "\n" for p in vertices)
    text += "".join("f " + " ".join(str(i+1) for i in f) + "\n" for f in faces)
    Path(destination).write_text(text, encoding="utf-8")


def so100_mjcf(urdf_path=None):
    source = Path(urdf_path or SO100_DIR / "so100.urdf").resolve()
    raw = source.read_bytes()
    key = hashlib.sha256(raw + b"importer-v2" + mujoco.__version__.encode()).hexdigest()[:16]
    cache = ROOT / ".cache/so100" / key
    cache.mkdir(parents=True, exist_ok=True)
    compiled = cache / "imported.xml"
    if not compiled.exists():
        robot = ET.fromstring(raw)
        extension = ET.SubElement(robot, "mujoco")
        ET.SubElement(extension, "compiler", discardvisual="false", fusestatic="false", strippath="false", balanceinertia="true")
        # MuJoCo URDF 导入器会复用名称；移除 visual 名称防止与碰撞代理重名。
        for visual in robot.iter("visual"):
            visual.attrib.pop("name", None)
        for mesh in robot.iter("mesh"):
            name = mesh.get("filename")
            path = SO100_DIR / name
            if path.suffix == ".ply":
                converted = cache / (path.stem + ".obj")
                ply_to_obj(path, converted)
                path = converted
            mesh.set("filename", str(path.resolve()))
        model = mujoco.MjModel.from_xml_string(ET.tostring(robot, encoding="unicode"))
        mujoco.mj_saveLastXML(str(compiled), model)
    root = ET.parse(compiled).getroot()
    # 官方 URDF 导入不产生控制器；这里明确补充关节位置 PD 执行器。
    actuator = ET.SubElement(root, "actuator")
    for joint in SO100_JOINTS:
        node = root.find(f".//joint[@name='{joint}']")
        node.set("damping", "0.3")
        ET.SubElement(actuator, "position", name=joint+"_servo", joint=joint, kp="100", kv="3", ctrllimited="true", ctrlrange=node.get("range"), forcelimited="true", forcerange="-20 20")
    return root


def panda_mjcf():
    root = ET.parse(PANDA_DIR / "panda.xml").getroot()
    root.find("compiler").set("meshdir", str((PANDA_DIR / "assets").resolve()))
    hand = root.find(".//body[@name='hand']")
    ET.SubElement(hand, "site", name="tcp", pos="0 0 0.1034", size="0.004", rgba="0 1 0 0")
    # 场景可能增加自由物体：重置由 Python 按关节名完成，不依赖旧 keyframe 长度。
    root.remove(root.find("keyframe"))
    return root
