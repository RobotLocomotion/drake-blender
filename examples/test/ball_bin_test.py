# SPDX-License-Identifier: MIT-0

import os
from pathlib import Path
import subprocess
from typing import Callable
import unittest

from pydrake.common.yaml import yaml_dump, yaml_load_file


class BallBinTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(os.environ["TEST_TMPDIR"])
        self.assertTrue(self.tmpdir.exists(), self.tmpdir)

        self.out_dir = Path(os.environ["TEST_UNDECLARED_OUTPUTS_DIR"])
        self.assertTrue(self.out_dir.exists(), self.out_dir)

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

    def _get_scenario_file(self, *, nerf_function: Callable):
        """Returns the path to a scenario file based on whether nerfing the
        original scenario, i.e., exmaple/ball_bin.yaml, is desired. If
        `nerf_function is not None`, the function will be applied to the yaml
        dictionary and the path to a temporary file containing the nerfed
        data will be returned.
        """
        raw_scenario_file = Path("examples/ball_bin.yaml").absolute().resolve()
        self.assertTrue(raw_scenario_file.exists(), raw_scenario_file)

        if nerf_function is None:
            return raw_scenario_file

        scenario = yaml_load_file(raw_scenario_file)
        scenario = nerf_function(scenario)

        nerfed_scenario_file = self.tmpdir / "ball_bin_nerfed.yaml"
        yaml_dump(scenario, filename=nerfed_scenario_file)
        return nerfed_scenario_file

    def _small_video(self, scenario):
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

    def _no_rendering(self, scenario):
        """Removes the cameras so that there is no rendering."""
        assert "cameras" in scenario
        del scenario["cameras"]
        return scenario

    def test_still_images(self):
        """Checks that the example creates 2x still image files."""
        scenario_file = self._get_scenario_file(nerf_function=None)

        # Add the arg, `--still`, to switch to image creation. We're also
        # using this to implicitly test all image type flags.
        run_args = self.default_run_args + [
            "--still",
            "--color",
            "--depth",
            "--label",
            f"--scenario_file={scenario_file}",
        ]

        result = subprocess.run(run_args, cwd=self.out_dir)
        result.check_returncode()
        self.assertTrue((self.out_dir / "vtk_camera_color.png").exists())
        self.assertTrue((self.out_dir / "blender_camera_color.png").exists())
        self.assertTrue((self.out_dir / "vtk_camera_label.png").exists())
        self.assertTrue((self.out_dir / "blender_camera_label.png").exists())
        self.assertTrue((self.out_dir / "vtk_camera_depth.png").exists())
        self.assertTrue((self.out_dir / "blender_camera_depth.png").exists())

    def test_video(self):
        """Checks that the example creates 2x video files."""
        scenario_file = self._get_scenario_file(
            nerf_function=self._small_video
        )

        # We're implicitly testing the "render color if nothing is said"
        # behavior.
        run_args = self.default_run_args + [f"--scenario_file={scenario_file}"]

        result = subprocess.run(run_args, cwd=self.out_dir)
        result.check_returncode()
        self.assertTrue((self.out_dir / "vtk_camera.mp4").exists())
        self.assertTrue((self.out_dir / "blender_camera.mp4").exists())

    def test_dynamics(self):
        """A regression test to confirm that the simulation runs successfully
        to end."""
        scenario_file = self._get_scenario_file(
            nerf_function=self._no_rendering
        )

        run_args = self.default_run_args + [f"--scenario_file={scenario_file}"]

        result = subprocess.run(run_args, cwd=self.out_dir)
        result.check_returncode()


if __name__ == "__main__":
    unittest.main()
