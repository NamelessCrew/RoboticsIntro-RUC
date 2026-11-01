"""学生纹理只生成一次，重复运行保留原始字节。"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from chapters.week06.scene import RobotEnv


class TexturePersistenceTest(unittest.TestCase):
    def test_preserve_student_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch("chapters.week06.scene.__file__", str(root/"chapters/week06/scene.py")):
                path = RobotEnv._checkerboard_texture()
                self.assertEqual(path, root/".cache/week06/checkerboard.png")
                Image.new("RGB", (16, 16), "orange").save(path)
                content = path.read_bytes()
                self.assertEqual(RobotEnv._checkerboard_texture().read_bytes(), content)
