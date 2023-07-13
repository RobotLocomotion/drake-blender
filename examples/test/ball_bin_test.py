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

        # Find the demo.
        demo_path = Path("examples/ball_bin").absolute().resolve()
        self.assertTrue(demo_path.exists(), demo_path)

        settings = Path("examples/test/bpy_use_cycles.py").absolute().resolve()
        self.assertTrue(settings.exists(), settings)

        # The default args to launch the subprocess.
        self.default_run_args = [
            demo_path,
            f"--bpy_settings_file={settings}",
        ]

    def _get_scenario_file(self, *, nerf_scenario: bool):
        """Returns the path to a scenario file based on whether nerfing the
        original scenario, i.e., exmaple/ball_bin.yaml, is desired. If
        `nerf_scenario=True`, some rendering configs will be swapped to shorten
        the rendering time for testing while keeping the scene the same.
        """
        raw_scenario_file = Path("examples/ball_bin.yaml").absolute().resolve()
        self.assertTrue(raw_scenario_file.exists(), raw_scenario_file)

        if not nerf_scenario:
            return raw_scenario_file

        scenario = yaml_load_file(raw_scenario_file)
        scenario = self._nerf_scenario(scenario)

        nerfed_scenario_file = self.tmpdir / "ball_bin_nerfed.yaml"
        yaml_dump(scenario, filename=nerfed_scenario_file)
        return nerfed_scenario_file

    def _nerf_scenario(self, scenario):
        """Shrinks the simulation time and the image size. The modifications
        ensure that the generated videos will have more than one frame.
        """
        assert "simulation_duration" in scenario
        scenario["simulation_duration"] = 0.3

        assert "cameras" in scenario
        for camera in ["blender_camera", "vtk_camera"]:
            assert camera in scenario["cameras"]
            assert "width" in scenario["cameras"][camera]
            assert "height" in scenario["cameras"][camera]
            scenario["cameras"][camera]["width"] = 100
            scenario["cameras"][camera]["height"] = 100
        return scenario

    def test_still_images(self):
        """Checks that the example creates 2x still image files."""
        scenario_file = self._get_scenario_file(nerf_scenario=False)

        # Add the arg, `--still`, to switch to image creation.
        run_args = self.default_run_args + [
            "--still",
            f"--scenario_file={scenario_file}",
        ]

        result = subprocess.run(run_args, cwd=self.tmpdir)
        result.check_returncode()
        self.assertTrue((self.tmpdir / "vtk_camera.png").exists())
        self.assertTrue((self.tmpdir / "blender_camera.png").exists())

    def test_video(self):
        """Checks that the example creates 2x video files."""
        scenario_file = self._get_scenario_file(nerf_scenario=True)

        run_args = self.default_run_args + [f"--scenario_file={scenario_file}"]

        result = subprocess.run(run_args, cwd=self.tmpdir)
        result.check_returncode()
        self.assertTrue((self.tmpdir / "vtk_camera.mp4").exists())
        self.assertTrue((self.tmpdir / "blender_camera.mp4").exists())


if __name__ == "__main__":
    unittest.main()
