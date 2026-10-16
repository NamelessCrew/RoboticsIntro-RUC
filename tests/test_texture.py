"""验证学生替换纹理后不会被自动生成逻辑覆盖，无需创建 GPU 场景。"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from chapters.week06.scene import SO100Env


class TexturePersistenceTest(unittest.TestCase):
    def test_create_once_then_preserve_student_image(self):
        # 临时根目录避免读写真实课堂纹理。
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            fake_source = root / "chapters/week06/scene.py"
            with patch("chapters.week06.scene.__file__", str(fake_source)):
                path = SO100Env._checkerboard_texture()
                self.assertEqual(path, root / ".cache/week06/checkerboard.png")
                self.assertTrue(path.read_bytes().startswith(b"\x89PNG"))
                original = path.read_bytes()
                student_image = original + b"student-image-marker"
                path.write_bytes(student_image)
                self.assertEqual(SO100Env._checkerboard_texture().read_bytes(), student_image)


if __name__ == "__main__":
    unittest.main()
