import os
from pathlib import Path
import subprocess
import unittest


class BallBinTest(unittest.TestCase):
    def test_still_images(self):
        """Checks that the example creates 2x still image files."""
        tmpdir = Path(os.environ["TEST_TMPDIR"])
        self.assertTrue(tmpdir.exists(), tmpdir)
        # Find the server.
        demo_path = Path("examples/ball_bin").absolute().resolve()
        self.assertTrue(demo_path.exists(), demo_path)
        settings = Path("examples/test/bpy_use_cycles.py").absolute().resolve()
        self.assertTrue(settings.exists(), settings)
        # Run it.
        result = subprocess.run(
            [demo_path, "--still", f"--bpy_settings_file={settings}"],
            cwd=tmpdir,
        )
        result.check_returncode()
        self.assertTrue((tmpdir / "vtk_camera.png").exists())
        self.assertTrue((tmpdir / "blender_camera.png").exists())


if __name__ == "__main__":
    unittest.main()
