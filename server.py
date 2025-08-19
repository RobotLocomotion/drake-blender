# SPDX-License-Identifier: BSD-2-Clause

"""
A glTF render server that services HTTP requests using Blender.
"""

import argparse
import dataclasses as dc
import datetime
import io
import logging
import math
from pathlib import Path
import tempfile
from types import NoneType
import typing

import bpy
import flask

_logger = logging.getLogger("server")

_UINT16_MAX = 2**16 - 1


@dc.dataclass
class RenderParams:
    """A dataclass that encapsulates all the necessary parameters to render a
    color, depth, or label image.

    https://drake.mit.edu/doxygen_cxx/group__render__engine__gltf__client__server__api.html#render-endpoint-form-data
    """

    scene: Path
    """The glTF input file."""

    scene_sha256: str
    """The checksum of `scene`."""

    image_type: typing.Literal["color", "depth", "label"]
    """The type of image being rendered."""

    width: int
    """Width of the desired rendered image in pixels."""

    height: int
    """Height of the desired rendered image in pixels."""

    near: float
    """The near clipping plane of the camera as specified by the
    RenderCameraCore's ClippingRange::near() value."""

    far: float
    """The far clipping plane of the camera as specified by the
    RenderCameraCore's ClippingRange::far() value."""

    focal_x: float
    """The focal length x, in pixels, as specified by the
    systems::sensors::CameraInfo::focal_x() value."""

    focal_y: float
    """The focal length y, in pixels, as specified by the
    systems::sensors::CameraInfo::focal_y() value."""

    fov_x: float
    """The field of view in the x-direction (in radians) as specified by the
    systems::sensors::CameraInfo::fov_x() value."""

    fov_y: float
    """The field of view in the y-direction (in radians) as specified by the
    systems::sensors::CameraInfo::fov_y() value."""

    center_x: float
    """The principal point's x coordinate in pixels as specified by the
    systems::sensors::CameraInfo::center_x() value."""

    center_y: float
    """The principal point's y coordinate in pixels as specified by the
    systems::sensors::CameraInfo::center_y() value."""

    min_depth: typing.Optional[float] = None
    """The minimum depth range as specified by a depth sensor's
    DepthRange::min_depth(). Only provided when image_type="depth"."""

    max_depth: typing.Optional[float] = None
    """The maximum depth range as specified by a depth sensor's
    DepthRange::max_depth(). Only provided when image_type="depth"."""


class Blender:
    """Encapsulates our access to blender.

    Note that even though this is a class, bpy is a singleton so likewise you
    should only ever create one instance of this class.
    """

    def __init__(
        self, *, blend_file: Path = None, bpy_settings_file: Path = None
    ):
        self._blend_file = blend_file
        self._bpy_settings_file = bpy_settings_file
        self._client_objects = None

    def reset_scene(self):
        """
        Resets the scene in Blender by loading the default startup file, and
        then removes the default cube object.
        """
        bpy.ops.wm.read_factory_settings()
        for item in bpy.data.objects:
            item.select_set(True)
        bpy.ops.object.delete()

    def add_default_light_source(self):
        light = bpy.data.lights.new(name="POINT", type="POINT")
        light.energy = 100
        light_object = bpy.data.objects.new(name="LIGHT", object_data=light)
        light_object.location = (0, 0, 5)
        bpy.context.collection.objects.link(light_object)
        bpy.context.view_layer.objects.active = light_object

    def render_image(self, *, params: RenderParams, output_path: Path):
        """
        Renders the current scene with the given parameters.
        """
        # Load the blend file to set up the basic scene if provided; otherwise,
        # the scene gets reset with default lighting.
        if self._blend_file is not None:
            bpy.ops.wm.open_mainfile(filepath=str(self._blend_file))
        else:
            self.reset_scene()
            self.add_default_light_source()

        # Apply the user's custom settings.
        if self._bpy_settings_file:
            with open(self._bpy_settings_file) as f:
                code = compile(f.read(), self._bpy_settings_file, "exec")
                exec(code, {"bpy": bpy}, dict())

        self._client_objects = bpy.data.collections.new("ClientObjects")
        old_count = len(bpy.data.objects)
        # Import a glTF file. Note that the Blender glTF importer imposes a
        # +90 degree rotation around the X-axis when loading meshes. Thus, we
        # counterbalance the rotation right after the glTF-loading.
        bpy.ops.import_scene.gltf(filepath=str(params.scene))
        new_count = len(bpy.data.objects)
        # Reality check that all of the imported objects are selected by
        # default.
        assert new_count - old_count == len(bpy.context.selected_objects)

        # TODO(#39) This rotation is very suspicious. Get to the bottom of it.
        # We explicitly specify the pivot point for the rotation to allow for
        # glTF files with root nodes with arbitrary positioning. We simply want
        # to rotate around the world origin.
        bpy.ops.transform.rotate(
            value=math.pi / 2,
            orient_axis="X",
            orient_type="GLOBAL",
            center_override=(0, 0, 0),
        )

        # All imported objects get put in our "client objects" collection.
        for obj in bpy.context.selected_objects:
            self._client_objects.objects.link(obj)

        # Set rendering parameters.
        scene = bpy.context.scene
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(output_path)
        scene.render.resolution_x = params.width
        scene.render.resolution_y = params.height
        if params.focal_x > params.focal_y:
            scene.render.pixel_aspect_x = 1.0
            scene.render.pixel_aspect_y = params.focal_x / params.focal_y
        else:
            scene.render.pixel_aspect_x = params.focal_y / params.focal_x
            scene.render.pixel_aspect_y = 1.0

        # Set camera parameters.
        camera = bpy.data.objects.get("Camera Node")
        if camera is None:
            _logger.error(
                "Camera node not found. Check the input glTF file "
                f"'{params.scene}'."
            )
            return

        scene.camera = camera
        # By default, the clipping planes are configured to near and far; for
        # depth we may tweak them (see below).
        camera.data.clip_start = params.near
        camera.data.clip_end = params.far

        # See: https://www.rojtberg.net/1601/from-Blender-to-opencv-camera-and-back/.  # noqa: E501
        camera.data.shift_x = -1.0 * (params.center_x / params.width - 0.5)
        camera.data.shift_y = (
            params.center_y - 0.5 * params.height
        ) / params.width

        # Setting FOV Y also implicitly sets FOV X.
        camera.data.lens_unit = "FOV"
        camera.data.angle_y = params.fov_y

        # Set image_type specific functionality.
        if params.image_type == "color":
            scene.render.image_settings.color_mode = "RGBA"
            scene.render.image_settings.color_depth = "8"
        else:
            # NOTE: For depth and label, we don't want to remap the computed
            # values based on perceptual color space. It _may_ appear that the
            # setting display_device to "sRGB" would trigger a mapping to
            # perceptual color space, however the "Raw" view_transform value
            # keeps the rendered result in linear space.
            scene.display_settings.display_device = "sRGB"
            scene.view_settings.view_transform = "Raw"
            # Also disable anti-aliasing for both depth and label.
            bpy.context.scene.render.filter_size = 0
            if params.image_type == "depth":
                # Note: typical RenderEngine implementations in Drake use the
                # near/far range for the camera clipping. For depth it is
                # actually more efficient to set clip_end to the minimum of far
                # and max_depth (this maximizes the precision in the depth
                # map).
                depth_far = min(params.far, params.max_depth)

                # Blender has an additional gotcha. We can't explicitly set the
                # depth map's background color (which we typically set to the
                # "too far" value). Blender automatically initializes it to the
                # _clipping_ far value. We can't decouple them. So, we have to
                # pick a clipping far value that will allow us to distinguish
                # between "valid" depth returns and too value. So, we set the
                # clipping far value epsilon beyond what we consider to be the
                # most distant value we will accept. We then will add
                # compositor machinery to saturate depth returns greater than
                # the target value to "too far" (see depth_render_settings()).
                camera.data.clip_end = depth_far * 1.001
                scene.render.image_settings.color_mode = "BW"
                scene.render.image_settings.color_depth = "16"
                self.depth_render_settings(params.min_depth, depth_far)
            else:  # image_type == "label".
                scene.render.image_settings.color_mode = "RGBA"
                scene.render.image_settings.color_depth = "8"
                self.label_render_settings()

        # Render the image.
        bpy.ops.render.render(write_still=True, animation=False)

    def depth_render_settings(self, min_depth, max_depth):
        scene = bpy.context.scene

        scene.use_nodes = True
        nodes = scene.node_tree.nodes
        links = scene.node_tree.links
        # Clear all nodes before starting anew.
        nodes.clear()
        # The rendering source (with the Depth output enabled).
        render_layers = nodes.new("CompositorNodeRLayers")
        bpy.context.view_layer.use_pass_z = True
        # The rendering endpoint; this gets saved to disk.
        composite = nodes.new("CompositorNodeComposite")

        # This does several things:
        #   1. Maps meters to millimeters.
        #   2. Normalizes on the maximum range in a 16-bit depth map.
        #   3. Clamps to the admissible range.
        map_value = nodes.new("CompositorNodeMapValue")
        map_value.name = "SequeezeToDepth16U"
        map_value.use_min = True
        map_value.use_max = True
        map_value.size = [1000 / _UINT16_MAX]
        map_value.min = [0]
        map_value.max = [1.0]

        # Mask out all values that are "too far" and saturate them above the
        # maximum 16-bit range (they'll clamp down to 1.0)
        too_far = nodes.new("ShaderNodeMath")
        too_far.name = "TooFarDetector"
        too_far.operation = "GREATER_THAN"
        too_far.inputs[1].default_value = max_depth

        far_saturator = nodes.new("ShaderNodeMath")
        far_saturator.name = "SaturateTooFar"
        far_saturator.operation = "MULTIPLY_ADD"
        far_saturator.inputs[1].default_value = (_UINT16_MAX + 1) / 1000

        # Mask out all values that are too close and saturate them below zero
        # (they'll clamp up to zero).
        too_close = nodes.new("ShaderNodeMath")
        too_close.name = "TooCloseDetector"
        too_close.operation = "LESS_THAN"
        too_close.inputs[1].default_value = min_depth

        close_saturator = nodes.new("ShaderNodeMath")
        close_saturator.name = "SaturateTooClose"
        close_saturator.operation = "MULTIPLY_ADD"
        close_saturator.inputs[1].default_value = -2 * min_depth

        # Wire in "too far" detector.
        links.new(
            render_layers.outputs.get("Depth"), too_far.inputs.get("Value")
        )
        links.new(
            too_far.outputs.get("Value"), far_saturator.inputs.get("Value")
        )
        # The "addend" input on far_saturator cannot be accessed via name.
        links.new(render_layers.outputs.get("Depth"), far_saturator.inputs[2])

        # Wire in "too close" detector.
        links.new(
            far_saturator.outputs.get("Value"), too_close.inputs.get("Value")
        )
        links.new(
            too_close.outputs.get("Value"), close_saturator.inputs.get("Value")
        )
        # The "addend" input on close_saturator cannot be accessed via name.
        links.new(
            far_saturator.outputs.get("Value"), close_saturator.inputs[2]
        )

        # Squeeze down to 16-bit and output.
        links.new(
            close_saturator.outputs.get("Value"), map_value.inputs.get("Value")
        )
        links.new(
            map_value.outputs.get("Value"), composite.inputs.get("Image")
        )

    def label_render_settings(self):
        scene = bpy.context.scene

        # Set dither to zero because the 8-bit color image tries to create a
        # better perceived transition in color where there is a limited
        # palette.
        scene.render.dither_intensity = 0

        # Meshes from a blend file and the background will be painted to white.
        background_color = (1.0, 1.0, 1.0, 1.0)
        world_nodes = bpy.data.worlds["World"].node_tree.nodes
        world_nodes["Background"].inputs[0].default_value = background_color

        # Every object imported from the glTF file has been placed in a
        # special collection; simply test for its presence.
        assert self._client_objects is not None

        def is_from_gltf(object):
            return object.name in self._client_objects.objects

        # Iterate over all meshes and set their label values.
        for bpy_object in bpy.data.objects:
            assert bpy_object is not None
            # Ensure the object is a mesh.
            # TODO(zachfang): Revisit if we ever add more types of objects
            # other than `MESH`, e.g., primitives. We need to handle their
            # label values too.
            if bpy_object.type != "MESH":
                continue

            # If a mesh is imported from a glTF, we will set its label value to
            # its diffuse color. If a mesh is loaded from a blend file, its
            # label value will be set to white (same as the background).
            if is_from_gltf(bpy_object):
                mesh_color = bpy_object.data.materials[0].diffuse_color
            else:
                mesh_color = background_color
            bpy_object.data.materials[0].use_nodes = True
            links = bpy_object.data.materials[0].node_tree.links
            nodes = bpy_object.data.materials[0].node_tree.nodes

            # Clear all material nodes before adding necessary nodes.
            nodes.clear()
            rendered_surface = nodes.new("ShaderNodeOutputMaterial")
            # Use 'ShaderNodeBackground' node as it produces a flat color.
            unlit_flat_mesh_color = nodes.new("ShaderNodeBackground")

            links.new(
                unlit_flat_mesh_color.outputs[0],
                rendered_surface.inputs["Surface"],
            )
            unlit_flat_mesh_color.inputs["Color"].default_value = mesh_color


class ServerApp(flask.Flask):
    """The long-running Flask server application."""

    def __init__(
        self,
        *,
        temp_dir,
        blend_file: Path = None,
        bpy_settings_file: Path = None,
    ):
        super().__init__("drake_render_gltf_blender")

        self._temp_dir = temp_dir
        self._blender = Blender(
            blend_file=blend_file, bpy_settings_file=bpy_settings_file
        )

        self.add_url_rule("/", view_func=self._root_endpoint)

        endpoint = "/render"
        self.add_url_rule(
            rule=endpoint,
            endpoint=endpoint,
            methods=["POST"],
            view_func=self._render_endpoint,
        )

    def _root_endpoint(self):
        """Displays a banner page at the server root."""
        return """\
        <!doctype html>
        <html><body><h1>Drake Render glTF Blender Server</h1></body></html>
        """

    def _render_endpoint(self):
        """Accepts a request to render and returns the generated image."""
        try:
            params = self._parse_params(flask.request)
            buffer = self._render(params)
            return flask.send_file(buffer, mimetype="image/png")
        except Exception as e:
            code = 500
            message = f"Internal server error: {repr(e)}"
            return (
                {
                    "error": True,
                    "message": message,
                    "code": code,
                },
                code,
            )

    def _parse_params(self, request: flask.Request) -> RenderParams:
        """Converts an http request to a RenderParams."""
        result = dict()

        # Compute a lookup table for known form field names.
        param_fields = {x.name: x for x in dc.fields(RenderParams)}
        del param_fields["scene"]

        # Copy all of the form data into the result.
        for name, value in request.form.items():
            if name == "submit":
                # Ignore the html boilerplate.
                continue
            field = param_fields[name]
            type_origin = typing.get_origin(field.type)
            type_args = typing.get_args(field.type)
            if field.type in (int, float, str):
                result[name] = field.type(value)
            elif type_origin == typing.Literal:
                if value not in type_args:
                    raise ValueError(f"Invalid literal for {name}")
                result[name] = value
            elif type_origin == typing.Union:
                # In our dataclass we declare a typing.Optional but that's just
                # sugar for typing.Union[T, typing.NoneType]. Here, we need to
                # parse the typing.Union spelling; we can assume the only use
                # of Union is for an Optional.
                assert len(type_args) == 2
                assert type_args[1] == NoneType
                result[name] = type_args[0](value)
            else:
                raise NotImplementedError(name)

        # Save the glTF scene data. Note that we don't check the scene_sha256
        # checksum; it seems unlikely that it could ever fail without flask
        # detecting the error. In any case, the blender glTF loader should
        # reject malformed files; we don't need to fail-fast.
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        scene = Path(f"{self._temp_dir}/{timestamp}.gltf")
        assert len(request.files) == 1
        request.files["scene"].save(scene)
        result["scene"] = scene

        return RenderParams(**result)

    def _render(self, params: RenderParams):
        """Renders the given scene, returning the png data buffer."""
        output_path = params.scene.with_suffix(".png")
        try:
            self._blender.render_image(params=params, output_path=output_path)
            with open(output_path, "rb") as f:
                buffer = io.BytesIO(f.read())
            return buffer
        finally:
            params.scene.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="URL to host on, default: %(default)s.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to host on, default: %(default)s.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="When true, flask reloads server.py when it changes.",
    )
    parser.add_argument(
        "--blend_file",
        type=Path,
        metavar="FILE",
        help="Path to a *.blend file.",
    )
    parser.add_argument(
        "--bpy_settings_file",
        type=Path,
        metavar="FILE",
        help="Path to a *.py file that the server will exec() to configure "
        "blender. For example, the settings file might contain the line "
        '`bpy.context.scene.render.engine = "EEVEE"` (with no backticks). '
        "The settings file will be applied after loading the --blend_file "
        "(if any) so that it has priority.",
    )
    args = parser.parse_args()

    prefix = "drake_blender_"
    with tempfile.TemporaryDirectory(prefix=prefix) as temp_dir:
        app = ServerApp(
            temp_dir=temp_dir,
            blend_file=args.blend_file,
            bpy_settings_file=args.bpy_settings_file,
        )
        app.run(
            host=args.host, port=args.port, debug=args.debug, threaded=False
        )


if __name__ == "__main__":
    main()
