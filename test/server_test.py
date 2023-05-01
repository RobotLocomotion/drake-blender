import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
import unittest
import urllib

from bazel_tools.tools.python.runfiles import runfiles
import numpy as np
from PIL import Image
import requests

DEPTH_PIXEL_THRESHOLD = 1  # Depth measurement tolerance in millimeters.
LABEL_PIXEL_THRESHOLD = 0
INVALID_PIXEL_FRACTION = 0.2


def _find_resource(bazel_path):
    """Looks up the path to "runfiles" data, as organized by Bazel."""
    manifest = runfiles.Create()
    location = manifest.Rlocation(bazel_path)
    assert location is not None, f"Not a resource: {bazel_path}"
    result = Path(location)
    assert result.exists(), f"Missing resource: {bazel_path}"
    return result


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = os.environ.get("TEST_TMPDIR", "/tmp")
        # Find and launch the server in the background.
        server_path = Path("server").absolute().resolve()
        self.assertTrue(server_path.exists(), server_path)
        self.server_proc = subprocess.Popen([server_path])

    def _wait_for_server(self):
        """Waits for the server to start accepting connections."""
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

    def _shutdown_server(self):
        self.server_proc.terminate()
        self.assertEqual(self.server_proc.wait(1.0), -signal.SIGTERM)

    def _create_request_form(self, image_type):
        # These properties are used when rendering the ground truth images. The
        # Blender server should use the same setting for testing.
        form_data = {
            "scene_sha256": "NO_USED_IN_THE_TEST",
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

    def test_gltf_render(self):
        """Renders images given a pre-generated glTF file and compares the
        rendering from the Blender server with the ground truth image.
        """ 
        self._wait_for_server()

        test_args = [
            # (image_type, ndarray dtype, threshold)
            ("label", np.uint8, LABEL_PIXEL_THRESHOLD),
            ("depth", float, DEPTH_PIXEL_THRESHOLD),
        ]

        for image_type, dtype, threshold in test_args:
            with self.subTest(image_type=image_type):
                gltf_file = _find_resource(
                    f"__main__/test/{image_type}_000.gltf"
                )
                with open(gltf_file, "rb") as scene:
                    form_data = self._create_request_form(image_type)
                    response = requests.post(
                        url="http://127.0.0.1:8000/render",
                        data=form_data,
                        files={"scene": scene},
                        stream=True,
                    )
                self.assertEqual(response.status_code, 200)

                # Save the returned image to a temporary location.
                blender_image_path = os.path.join(
                    self.tmp_dir, f"{image_type}.png")
                with open(blender_image_path, "wb") as image:
                    shutil.copyfileobj(response.raw, image)

                ground_truth_image_path = _find_resource(
                    f"__main__/test/{image_type}_000.png"
                )
                ground_truth = np.array(Image.open(ground_truth_image_path))
                blender = np.array(Image.open(blender_image_path))

                diff = (
                    np.absolute(
                        ground_truth.astype(dtype) - blender.astype(dtype)
                    )
                    > threshold
                )
                self.assert_error_fraction_less(diff, INVALID_PIXEL_FRACTION)

        self._shutdown_server()


if __name__ == "__main__":
    unittest.main()
