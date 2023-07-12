# SPDX-License-Identifier: MIT-0

import os
from pathlib import Path
import subprocess
import unittest


class BallBinTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(os.environ["TEST_TMPDIR"])
        self.assertTrue(self.tmpdir.exists(), self.tmpdir)

        # Find the server.
        demo_path = Path("examples/ball_bin").absolute().resolve()
        self.assertTrue(demo_path.exists(), demo_path)

        # Find the relevant files for testing.
        settings = Path("examples/test/bpy_use_cycles.py").absolute().resolve()
        scenario_file = (
            Path("examples/test/test_scenario.yaml").absolute().resolve()
        )
        self.assertTrue(settings.exists(), settings)
        self.assertTrue(scenario_file.exists(), scenario_file)

        # The default args to launch the subprocess.
        self.run_args = [
            demo_path,
            f"--scenario_file={scenario_file}",
            f"--bpy_settings_file={settings}",
        ]

    def test_still_images(self):
        """Checks that the example creates 2x still image files."""
        # Add the arg, `--still`, to switch to image creation.
        self.run_args.append("--still")
        result = subprocess.run(
            self.run_args,
            cwd=self.tmpdir,
        )
        result.check_returncode()
        self.assertTrue((self.tmpdir / "vtk_camera.png").exists())
        self.assertTrue((self.tmpdir / "blender_camera.png").exists())

    def test_video(self):
        """Checks that the example creates 2x video files."""
        result = subprocess.run(
            self.run_args,
            cwd=self.tmpdir,
        )
        result.check_returncode()
        self.assertTrue((self.tmpdir / "vtk_camera.mp4").exists())
        self.assertTrue((self.tmpdir / "blender_camera.mp4").exists())


if __name__ == "__main__":
    unittest.main()
