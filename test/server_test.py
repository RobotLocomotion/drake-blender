# SPDX-License-Identifier: BSD-2-Clause

from collections import namedtuple
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import unittest

from PIL import Image
import numpy as np
import requests

COLOR_PIXEL_THRESHOLD = 0
DEPTH_PIXEL_THRESHOLD = 1  # Depth measurement tolerance in millimeters.
LABEL_PIXEL_THRESHOLD = 0
INVALID_PIXEL_FRACTION = 0.02

# The most basic glTF file containing two diffuse color boxes for testing.
DEFAULT_GLTF_FILE = "test/two_rgba_boxes.gltf"
# The basic blend file for testing. It contains only a texture box and a
# default point light that is added in `server.py`.
DEFAULT_BLEND_FILE = "test/one_texture_box.blend"


class ServerFixture(unittest.TestCase):
    """Encapsulates the testing infrastructure, e.g., starting and stopping the
    server subprocess, sending rendering requests, and conducting the per-pixel
    image differencing.
    """

    def setUp(self, extra_server_args=None):
        # Start the server on the other process. Bind to port 0 and let the OS
        # assign an available port later on.
        server_path = Path("server").absolute().resolve()
        server_args = [
            server_path,
            "--host=127.0.0.1",
            "--port=0",
        ]
        # Append extra server args, e.g., the path to a blend file.
        if extra_server_args:
            server_args.extend(extra_server_args)

        self.server_proc = subprocess.Popen(
            server_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        # Wait to hear which port it's using.
        self.server_port = None
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

    def tearDown(self):
        self.server_proc.terminate()
        self.assertEqual(self.server_proc.wait(10.0), -signal.SIGTERM)

    def _render_and_check(
        self,
        gltf_path,
        image_type,
        reference_image_path,
        threshold,
        invalid_fraction=INVALID_PIXEL_FRACTION,
        min_depth=None,
        max_depth=None,
    ):
        """The implementation of the per-pixel image differencing on a specific
        image_type. It first renders an image by calling the server, compares
        the result given a reference image and thresholds, and returns the path
        of the rendered image.
        """
        with open(gltf_path, "rb") as scene:
            form_data = self._create_request_form(
                image_type=image_type,
                min_depth=min_depth,
                max_depth=max_depth,
            )
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
            f"Rendered image: {rendered_image_path.name} vs "
            f"{reference_image_path}",
        )
        return rendered_image_path

    @staticmethod
    def _create_request_form(*, image_type, min_depth=None, max_depth=None):
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
            form_data["min_depth"] = 0.01 if min_depth is None else min_depth
            form_data["max_depth"] = 10.0 if max_depth is None else max_depth
        return form_data

    def _assert_images_equal(
        self,
        rendered_image_path,
        reference_image_path,
        threshold,
        invalid_fraction,
        error_message,
    ):
        # Compare the output image to the ground truth image (from git).
        test = np.array(Image.open(rendered_image_path))
        compare_to = np.array(Image.open(reference_image_path))
        image_diff = (
            np.absolute(compare_to.astype(float) - test.astype(float))
            > threshold
        )

        image_diff_fraction = np.count_nonzero(image_diff) / image_diff.size
        self.assertLessEqual(
            image_diff_fraction, invalid_fraction, error_message
        )


class RpcOnlyServerTest(ServerFixture):
    """Tests the server with only RPC data as input. No additional command line
    arguments nor *.blend files are involved.
    """

    def test_color_render(self):
        self._render_and_check(
            gltf_path=DEFAULT_GLTF_FILE,
            image_type="color",
            reference_image_path="test/two_rgba_boxes.color.png",
            threshold=COLOR_PIXEL_THRESHOLD,
        )

    def test_depth_render(self):
        self._render_and_check(
            gltf_path=DEFAULT_GLTF_FILE,
            image_type="depth",
            reference_image_path="test/depth.png",
            threshold=DEPTH_PIXEL_THRESHOLD,
        )

    def test_depth_render_clipped(self):
        """Tests the conditions where the geometry extends beyond the depth
        sensor's [min_depth, max_depth] range.

        Note: the output image is difficult to interpret. Compared to depth.png
        two things can be noted:

            1. depth_clipped.png shows fewer dark pixels; the portions of the
               boxes farthest from the camera are now labeled as "too far" --
               the same as the rest of the background.
            2. Harder to see, the "near" pixels are set to a perfect black
               color. This cannot be discerned visually (the distinction
               between the black and the near black is too fine for the human
               eye). It *can* be observed programmatically or in image editing
               software by playing with the "levels" (IYKYK).
        """
        self._render_and_check(
            gltf_path=DEFAULT_GLTF_FILE,
            image_type="depth",
            reference_image_path="test/depth_clipped.png",
            threshold=DEPTH_PIXEL_THRESHOLD,
            # Due to the statistical nature of the image equality test, small
            # changes to depth range will test equal.
            min_depth=0.32,  # Test will fail with min_depth <= 0.31
            max_depth=0.33,  # Test will fail with max_depth >= 0.35
        )

    def test_label_render(self):
        self._render_and_check(
            gltf_path=DEFAULT_GLTF_FILE,
            image_type="label",
            reference_image_path="test/label.png",
            threshold=LABEL_PIXEL_THRESHOLD,
        )

    # Test color and depth image rendering given a rgba and a textured mesh.
    # (We do not check a label image because by definition an RPC for a label
    # image will never contain any textured objects.)
    def test_texture_color_render(self):
        self._render_and_check(
            gltf_path="test/one_rgba_one_texture_boxes.gltf",
            image_type="color",
            reference_image_path="test/one_rgba_one_texture_boxes.color.png",
            threshold=COLOR_PIXEL_THRESHOLD,
        )

    def test_texture_depth_render(self):
        self._render_and_check(
            gltf_path="test/one_rgba_one_texture_boxes.gltf",
            image_type="depth",
            reference_image_path="test/depth.png",
            threshold=DEPTH_PIXEL_THRESHOLD,
        )

    def test_consistency(self):
        """Tests the consistency of the render results from consecutive
        requests. Each image type is first rendered and compared with the
        ground truth images. A second image is then rendered and expected to be
        pixel-identical as the first one. As with all things Drake, we expect
        reproducible simulations, so if there is any randomness in the render
        pipeline it's the responsibility of the server to configure it so that
        the exact same RPC call produces the exact same image output no matter
        how it's called or how many times it's called.
        """
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
            self._render_and_check(
                gltf_path=DEFAULT_GLTF_FILE,
                image_type=test_case.image_type,
                reference_image_path=returned_image_paths[index],
                threshold=0.0,
                invalid_fraction=0.0,
            )


class BlendFileServerTest(ServerFixture):
    """Tests the server with both RPC data and a blend file as input."""

    def setUp(self):
        super().setUp(extra_server_args=[f"--blend_file={DEFAULT_BLEND_FILE}"])

    def test_rpc_blend_color_render(self):
        self._render_and_check(
            gltf_path="test/one_rgba_box.gltf",
            image_type="color",
            reference_image_path="test/one_rgba_one_texture_boxes.color.png",
            threshold=COLOR_PIXEL_THRESHOLD,
        )

    def test_rpc_blend_depth_render(self):
        self._render_and_check(
            gltf_path="test/one_rgba_box.gltf",
            image_type="depth",
            reference_image_path="test/depth.png",
            threshold=DEPTH_PIXEL_THRESHOLD,
        )

    def test_rpc_blend_label_render(self):
        # See label_render_settings() for more details. The meshes loaded via a
        # blend file will be treated as the background in a label image.
        self._render_and_check(
            gltf_path="test/one_rgba_box.gltf",
            image_type="label",
            reference_image_path="test/one_gltf_one_blend.label.png",
            threshold=LABEL_PIXEL_THRESHOLD,
        )


class ExtraSettingsServerTest(ServerFixture):
    """Tests the server against custom settings files."""

    def setUp(self):
        # Create a placeholder settings file.
        tmpdir = Path(os.environ["TEST_TMPDIR"])
        self._settings_path = tmpdir / "bpy_settings.py"
        with open(self._settings_path, "w", encoding="utf-8") as f:
            pass

        # Tell the server to use it.
        args = [f"--bpy_settings_file={self._settings_path}"]
        super().setUp(extra_server_args=args)

    def _call_rpc(self, status_code=200):
        """Makes a basic RPC call and returns the http response."""
        with open("test/one_rgba_box.gltf", "rb") as scene:
            response = requests.post(
                url=f"http://127.0.0.1:{self.server_port}/render",
                data=self._create_request_form(image_type="color"),
                files={"scene": scene},
                stream=True,
            )
        return response

    def test_settings_no_crash(self):
        """Checks that a valid settings file produces no errors."""
        with open(self._settings_path, "w", encoding="utf-8") as f:
            f.write("bpy.context.scene.render.threads = 1")
        response = self._call_rpc()
        self.assertEqual(response.status_code, 200)

    def test_settings_not_noop(self):
        """Checks that an invalid settings file produces errors."""
        with open(self._settings_path, "w", encoding="utf-8") as f:
            f.write("raise RuntimeError('Kilroy was here')")
        response = self._call_rpc()
        self.assertEqual(response.status_code, 500)
        error = json.loads(response.text)
        self.assertIn("Kilroy was here", error["message"])


if __name__ == "__main__":
    unittest.main()
