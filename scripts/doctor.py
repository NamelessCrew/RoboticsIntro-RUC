"""检查依赖和本地模型；成功导入不等于显卡渲染已经通过。"""
import importlib
import importlib.metadata
import platform
from pathlib import Path
import xml.etree.ElementTree as ET


def main():
    print(f"Python {platform.python_version()} / {platform.system()} {platform.machine()}")
    for module, package in [("mani_skill", "mani-skill"), ("sapien", "sapien"),
                            ("torch", "torch"), ("gymnasium", "gymnasium"),
                            ("numpy", "numpy"), ("imageio", "imageio")]:
        importlib.import_module(module)  # 导入失败直接退出，不吞掉异常。
        print(f"OK {package}=={importlib.metadata.version(package)}")
    model = Path(__file__).resolve().parents[1] / "chapters/week06/assets/so100/so100.urdf"
    tree = ET.parse(model)
    meshes = {e.get("filename") for e in tree.findall(".//mesh")}
    for mesh in meshes:
        if not (model.parent / mesh).is_file():
            raise FileNotFoundError(f"缺少模型网格：{mesh}")
    print(f"OK SO100: {len(tree.findall('link'))} links / {len(tree.findall('joint'))} joints / {len(meshes)} meshes")
    print("导入与文件检查通过。渲染验证请运行 bash run.sh scene。")


if __name__ == "__main__":
    main()
