# SPDX-License-Identifier: BSD-2-Clause

import test.unittest_path_cleaner  # Disable Ubuntu packages.

import datetime
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

# The most basic glTF file containing two diffuse color boxes for testing.
DEFAULT_GLTF_FILE = "test/two_rgba_boxes.gltf"


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

    def test_color_render(self, gltf_path=DEFAULT_GLTF_FILE):
        rendered_image = self._check_gltf_render(
            gltf_path=gltf_path,
            image_type="color",
        )
        self.asssert_image_equal(
            test_image=rendered_image,
            ground_truth_image="test/color.png",
            threshold=COLOR_PIXEL_THRESHOLD,
        )

    def test_depth_render(self, gltf_path=DEFAULT_GLTF_FILE):
        rendered_image = self._check_gltf_render(
            gltf_path=gltf_path,
            image_type="depth",
        )
        self.asssert_image_equal(
            test_image=rendered_image,
            ground_truth_image="test/depth.png",
            threshold=DEPTH_PIXEL_THRESHOLD,
        )

    def test_label_render(self, gltf_path=DEFAULT_GLTF_FILE):
        rendered_image = self._check_gltf_render(
            gltf_path=gltf_path,
            image_type="label",
        )
        self.asssert_image_equal(
            test_image=rendered_image,
            ground_truth_image="test/label.png",
            threshold=LABEL_PIXEL_THRESHOLD,
        )

    def test_consistency(self):
        """Tests the consistentcy of the render results from consecutive
        requests of different image types.
        """
        string_to_test_function = {
            "color": self.test_color_render,
            "depth": self.test_depth_render,
            "label": self.test_label_render,
        }

        # An arbitrary render sequence to test the Blender state is reset
        # properly every time.
        render_orders = ["label", "depth", "color", "depth", "label", "color"]

        for image_type in render_orders:
            string_to_test_function[image_type]()

    def test_repeatability(self):
        """Tests the repeatability by rendering the same image twice. The
        rendered images should be exactly identitcal.
        """
        test_cases = [
            ("color", COLOR_PIXEL_THRESHOLD),
            ("label", LABEL_PIXEL_THRESHOLD),
            ("depth", DEPTH_PIXEL_THRESHOLD),
        ]

        for image_type, threshold in test_cases:
            with self.subTest(image_type=image_type):
                first_image = self._check_gltf_render(
                    gltf_path=DEFAULT_GLTF_FILE,
                    image_type=image_type,
                )
                second_image = self._check_gltf_render(
                    gltf_path=DEFAULT_GLTF_FILE,
                    image_type=image_type,
                )
                self.asssert_image_equal(
                    test_image=first_image,
                    ground_truth_image=second_image,
                    threshold=threshold,
                    invalid_fraction=0.0,
                )

    def _check_gltf_render(self, gltf_path, image_type):
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
        timestamp = datetime.datetime.now().strftime("%H-%M-%S-%f")
        save_file = save_dir / f"{timestamp}.png"
        with open(save_file, "wb") as image:
            shutil.copyfileobj(response.raw, image)
        return save_file

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

    def asssert_image_equal(
        self,
        test_image,
        ground_truth_image,
        threshold,
        invalid_fraction=INVALID_PIXEL_FRACTION,
    ):
        # Compare the output image to the ground truth image (from git).
        test = np.array(Image.open(test_image))
        ground_truth = np.array(Image.open(ground_truth_image))
        diff = (
            np.absolute(ground_truth.astype(float) - test.astype(float))
            > threshold
        )
        self.assert_error_fraction_less(diff, invalid_fraction)

    def assert_error_fraction_less(self, image_diff, fraction):
        image_diff_fraction = np.count_nonzero(image_diff) / image_diff.size
        self.assertLessEqual(image_diff_fraction, fraction)


if __name__ == "__main__":
    unittest.main()
