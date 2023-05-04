# SPDX-License-Identifier: BSD-2-Clause

import test.unittest_path_cleaner  # Disable Ubuntu packages.

import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
import unittest

import numpy as np
from PIL import Image
import requests

COLOR_PIXEL_THRESHOLD = 0
DEPTH_PIXEL_THRESHOLD = 1  # Depth measurement tolerance in millimeters.
LABEL_PIXEL_THRESHOLD = 0
INVALID_PIXEL_FRACTION = 0.02


class ServerTest(unittest.TestCase):
    def setUp(self):
        # Find and launch the server in the background.
        server_path = Path("server").absolute().resolve()
        self.server_proc = subprocess.Popen([server_path])
        start_time = time.time()
        while time.time() < start_time + 30.0:
            with socket.socket() as s:
                try:
                    s.connect(("127.0.0.1", 8000))
                    # Success!
                    break
                except ConnectionRefusedError as e:
                    time.sleep(0.1)
        else:
            self.fail("Could not connect after 30 seconds")

    def tearDown(self):
        self.server_proc.terminate()
        self.assertEqual(self.server_proc.wait(1.0), -signal.SIGTERM)

    def test_rgba_gltf_render(self):
        """Renders each type of image given a glTF file containing only diffuse
        color textures and compares the renderings with the ground truth.
        """
        gltf_path = "test/two_rgba_boxes.gltf"
        self._test_color_render(gltf_path)
        self._test_depth_render(gltf_path)
        self._test_label_render(gltf_path)

    def test_consistency(self):
        gltf_path = "test/two_rgba_boxes.gltf"
        string_to_test_function = {
            "color": self._test_color_render,
            "depth": self._test_depth_render,
            "label": self._test_label_render,
        }

        # An arbitrary render sequence to test the Blender state is reset
        # properly every time.
        render_orders = ["label", "depth", "color", "label", "label", "depth"]

        for image_type in render_orders:
            string_to_test_function[image_type](gltf_path)

    def _test_color_render(self, gltf_path):
        self._check_gltf_render(
            gltf_path=gltf_path,
            image_type="color",
            dtype=np.uint8,
            threshold=COLOR_PIXEL_THRESHOLD,
        )

    def _test_depth_render(self, gltf_path):
        self._check_gltf_render(
            gltf_path=gltf_path,
            image_type="depth",
            dtype=float,
            threshold=DEPTH_PIXEL_THRESHOLD,
        )

    def _test_label_render(self, gltf_path):
        self._check_gltf_render(
            gltf_path=gltf_path,
            image_type="label",
            dtype=np.uint8,
            threshold=LABEL_PIXEL_THRESHOLD,
        )

    def _check_gltf_render(self, gltf_path, image_type, dtype, threshold):
        """The implementation of the per-pixel image differencing on a specific
        image_type.
        """
        with open(gltf_path, "rb") as scene:
            form_data = self._create_request_form(image_type=image_type)
            response = requests.post(
                url="http://127.0.0.1:8000/render",
                data=form_data,
                files={"scene": scene},
                stream=True,
            )
        self.assertEqual(response.status_code, 200)

        # Save the output image for offline inspection. It will be archived
        # into `.bazel/testlogs/server_test/test.outputs/outputs.zip`.
        save_dir = Path(os.environ["TEST_UNDECLARED_OUTPUTS_DIR"])
        save_file = save_dir / f"{image_type}.png"
        with open(save_file, "wb") as image:
            shutil.copyfileobj(response.raw, image)

        # Compare the output image to the ground truth image (from git).
        blender = np.array(Image.open(save_file))
        ground_truth = np.array(Image.open(f"test/{image_type}.png"))
        diff = (
            np.absolute(ground_truth.astype(dtype) - blender.astype(dtype))
            > threshold
        )
        self.assert_error_fraction_less(diff, INVALID_PIXEL_FRACTION)

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

    def assert_error_fraction_less(self, image_diff, fraction):
        image_diff_fraction = np.count_nonzero(image_diff) / image_diff.size
        self.assertLess(image_diff_fraction, fraction)


if __name__ == "__main__":
    unittest.main()
