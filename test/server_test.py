# SPDX-License-Identifier: BSD-2-Clause

import test.unittest_path_cleaner  # Disable Ubuntu packages.

from collections import namedtuple
import datetime
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import unittest

import numpy as np
from PIL import Image
import requests

COLOR_PIXEL_THRESHOLD = 0
DEPTH_PIXEL_THRESHOLD = 1  # Depth measurement tolerance in millimeters.
LABEL_PIXEL_THRESHOLD = 0
INVALID_PIXEL_FRACTION = 0.02

# The most basic glTF file containing two diffuse color boxes for testing.
DEFAULT_GLTF_FILE = "test/two_rgba_boxes.gltf"


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.server_proc = None
        self.server_port = None

    def tearDown(self):
        self.server_proc.terminate()
        self.assertEqual(self.server_proc.wait(1.0), -signal.SIGTERM)

    def _start_server(self, blend_file=None):
        # Start the server on the other process. Bind to port 0 and let the OS
        # assign an available port later on.
        server_path = Path("server").absolute().resolve()
        server_args = [
            server_path,
            "--host=127.0.0.1",
            "--port=0",
        ]
        if blend_file:
            server_args.extend([f"--blend_file={blend_file}"])
        self.server_proc = subprocess.Popen(
            server_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        # Wait to hear which port it's using.
        start_time = time.time()
        while time.time() < start_time + 30.0:
            line = self.server_proc.stdout.readline().decode("utf-8")
            print(f"[server] {line}", file=sys.stderr, end="")
            match = re.search(r"Running on http://127.0.0.1:([0-9]+)", line)
            if match:
                (self.server_port,) = match.groups()
                break
        else:
            self.fail("Could not connect after 30 seconds")

    def test_color_render(self):
        self._start_server()
        self._render_and_check(
            gltf_path=DEFAULT_GLTF_FILE,
            image_type="color",
            reference_image_path="test/two_rgba_boxes.color.png",
            threshold=COLOR_PIXEL_THRESHOLD,
        )

    def test_depth_render(self):
        self._start_server()
        self._render_and_check(
            gltf_path=DEFAULT_GLTF_FILE,
            image_type="depth",
            reference_image_path="test/depth.png",
            threshold=DEPTH_PIXEL_THRESHOLD,
        )

    def test_label_render(self):
        self._start_server()
        self._render_and_check(
            gltf_path=DEFAULT_GLTF_FILE,
            image_type="label",
            reference_image_path="test/label.png",
            threshold=LABEL_PIXEL_THRESHOLD,
        )

    def test_texture_render(self):
        self._start_server()
        """Tests whether a texture is rendered properly in a color image."""
        self._render_and_check(
            gltf_path="test/one_rgba_one_texture_boxes.gltf",
            image_type="color",
            reference_image_path="test/one_rgba_one_texture_boxes.color.png",
            threshold=COLOR_PIXEL_THRESHOLD,
        )

    def test_consistency(self):
        """Tests the consistency of the render results from consecutive
        requests. Each image type is first rendered and compared with the
        ground truth images. A second image is then rendered and expected to be
        pixel-identical as the first one.
        """
        self._start_server()
        TestCase = namedtuple(
            "TestCase", ["image_type", "reference_image", "threshold"]
        )
        test_cases = [
            TestCase(
                "color", "test/two_rgba_boxes.color.png", COLOR_PIXEL_THRESHOLD
            ),
            TestCase("depth", "test/depth.png", DEPTH_PIXEL_THRESHOLD),
            TestCase("label", "test/label.png", LABEL_PIXEL_THRESHOLD),
        ]

        returned_image_paths = []
        for test_case in test_cases:
            first_image = self._render_and_check(
                gltf_path=DEFAULT_GLTF_FILE,
                image_type=test_case.image_type,
                reference_image_path=test_case.reference_image,
                threshold=test_case.threshold,
            )
            returned_image_paths.append(first_image)

        for index, test_case in enumerate(test_cases):
            second_image = self._render_and_check(
                gltf_path=DEFAULT_GLTF_FILE,
                image_type=test_case.image_type,
                reference_image_path=returned_image_paths[index],
                threshold=0.0,
                invalid_fraction=0.0,
            )

    def test_gltf_and_blend_render(self):
        self._start_server(
            blend_file="/home/zachfang/drake-blender/test/one_rgba_one_texture_boxes.blend"  # noqa
        )
        self._render_and_check(
            gltf_path=DEFAULT_GLTF_FILE,
            image_type="color",
            reference_image_path="test/two_rgba_boxes.color.png",
            threshold=COLOR_PIXEL_THRESHOLD,
            invalid_fraction=0.3,
        )

    def _render_and_check(
        self,
        gltf_path,
        image_type,
        reference_image_path,
        threshold,
        invalid_fraction=INVALID_PIXEL_FRACTION,
    ):
        """The implementation of the per-pixel image differencing on a specific
        image_type. It first renders an image by calling the server, compares
        the result given a reference image and thresholds, and returns the path
        of the rendered image.
        """
        with open(gltf_path, "rb") as scene:
            form_data = self._create_request_form(image_type=image_type)
            response = requests.post(
                url=f"http://127.0.0.1:{self.server_port}/render",
                data=form_data,
                files={"scene": scene},
                stream=True,
            )
        self.assertEqual(response.status_code, 200)

        # Save the output image for offline inspection. It will be archived
        # into `.bazel/testlogs/server_test/test.outputs/outputs.zip`.
        save_dir = Path(os.environ["TEST_UNDECLARED_OUTPUTS_DIR"])
        timestamp = datetime.datetime.now().strftime("%H-%M-%S-%f")
        rendered_image_path = save_dir / f"{timestamp}.png"
        with open(rendered_image_path, "wb") as image:
            shutil.copyfileobj(response.raw, image)

        self._assert_images_equal(
            rendered_image_path,
            reference_image_path,
            threshold,
            invalid_fraction,
        )
        return rendered_image_path

    @staticmethod
    def _create_request_form(*, image_type):
        # These properties are used when rendering the ground truth images. The
        # Blender server should use the same setting for testing.
        form_data = {
            "scene_sha256": "NOT_USED_IN_THE_TEST",
            "image_type": image_type,
            "width": "640",
            "height": "480",
            "near": "0.01",
            "far": "10.0",
            "focal_x": "579.411",
            "focal_y": "579.411",
            "fov_x": "0.785398",
            "fov_y": "0.785398",
            "center_x": "319.5",
            "center_y": "239.5",
        }
        if image_type == "depth":
            form_data["min_depth"] = 0.01
            form_data["max_depth"] = 10.0
        return form_data

    def _assert_images_equal(
        self,
        rendered_image_path,
        reference_image_path,
        threshold,
        invalid_fraction,
    ):
        # Compare the output image to the ground truth image (from git).
        test = np.array(Image.open(rendered_image_path))
        compare_to = np.array(Image.open(reference_image_path))
        image_diff = (
            np.absolute(compare_to.astype(float) - test.astype(float))
            > threshold
        )

        image_diff_fraction = np.count_nonzero(image_diff) / image_diff.size
        self.assertLessEqual(image_diff_fraction, invalid_fraction)


if __name__ == "__main__":
    unittest.main()
