# SPDX-License-Identifier: MIT-0

import os
from pathlib import Path
import subprocess
import unittest

from pydrake.common.yaml import yaml_dump, yaml_load_file


class BallBinTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(os.environ["TEST_TMPDIR"])
        self.assertTrue(self.tmpdir.exists(), self.tmpdir)

        # Find the server.
        demo_path = Path("examples/ball_bin").absolute().resolve()
        self.assertTrue(demo_path.exists(), demo_path)

        settings = Path("examples/test/bpy_use_cycles.py").absolute().resolve()
        self.assertTrue(settings.exists(), settings)

        # Generate the scenario file on the fly for testing.
        updated_scenario_file = self._get_updated_scenario_file()

        # The default args to launch the subprocess.
        self.run_args = [
            demo_path,
            f"--scenario_file={updated_scenario_file}",
            f"--bpy_settings_file={settings}",
        ]

    def _get_updated_scenario_file(self):
        """Given the raw scenario file used in the example, swaps some
        rendering configs to shorten the rendering time for testing while
        keeping the scene the same.
        """
        raw_scenario_file = Path("examples/ball_bin.yaml").absolute().resolve()
        self.assertTrue(raw_scenario_file.exists(), raw_scenario_file)

        scenario = yaml_load_file(raw_scenario_file)

        # Shrink the simulation time and the image size. Ensure that thevideos
        # have more than one frame.
        scenario["simulation_duration"] = 0.3
        for camera in ["blender_camera", "vtk_camera"]:
            scenario["cameras"][camera]["width"] = 100
            scenario["cameras"][camera]["height"] = 100

        updated_scenario_file = self.tmpdir / "ball_bin_updated.yaml"
        yaml_dump(scenario, filename=updated_scenario_file)

        return updated_scenario_file

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
