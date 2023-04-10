# SPDX-License-Identifier: BSD-2-Clause

"""
A glTF render server that services HTTP requests using Blender.
"""

import argparse
import dataclasses as dc
import datetime
import io
import logging
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

    def __init__(self, *, blend_file: Path = None):
        self._blend_file = blend_file

    def reset_scene(self):
        """
        Resets the scene in Blender by removing any default settings, e.g., the
        default object, light, and camera.
        """
        for item in bpy.data.objects:
            item.select_set(True)
        bpy.ops.object.delete()

        for material in bpy.data.materials:
            if not material.users:
                bpy.data.materials.remove(material)

        for texture in bpy.data.textures:
            if not texture.users:
                bpy.data.textures.remove(texture)

    def add_default_light_source(self):
        light = bpy.data.lights.new(name="POINT", type="POINT")
        light.energy = 100
        light_object = bpy.data.objects.new(name="LIGHT", object_data=light)
        bpy.context.collection.objects.link(light_object)
        bpy.context.view_layer.objects.active = light_object
        light_object.location = (0, -5, 0)

    def render_image(self, *, params: RenderParams, output_path: Path):
        """
        Renders the current scene with the given parameters.
        """
        # Always reset the scene to start with.
        self.reset_scene()

        # Load the blend file to set up the basic scene if provided; otherwise,
        # a default lighting is added.
        if self._blend_file is not None:
            bpy.ops.wm.open_mainfile(filepath=str(self._blend_file))
        else:
            self.add_default_light_source()

        # Import glTF.
        bpy.ops.import_scene.gltf(filepath=str(params.scene))

        # Set rendering parameters.
        scene = bpy.context.scene
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(output_path)
        scene.render.resolution_x = params.width
        scene.render.resolution_y = params.height
        aspect_ratio = params.focal_y / params.focal_x
        scene.render.pixel_aspect_x = 1.0
        scene.render.pixel_aspect_y = aspect_ratio

        # Set camera parameters.
        camera = bpy.data.objects.get("Camera Node")
        if camera is None:
            _logger.error(
                "Camera node not found. Check the input glTF file "
                f"'{params.input_path}'."
            )
            return

        scene.camera = camera
        camera.data.show_sensor = True
        # Set the clipping planes using {min, max}_depth when rendering depth
        # images; otherwise, `near` and `far` are set for color and label
        # images.
        camera.data.clip_start = (
            params.min_depth if params.min_depth else params.near
        )
        camera.data.clip_end = (
            params.max_depth if params.max_depth else params.far
        )
        # See: https://www.rojtberg.net/1601/from-Blender-to-opencv-camera-and-back/.  # noqa: E501
        camera.data.shift_x = -1.0 * (params.center_x / params.width - 0.5)
        camera.data.shift_y = (
            params.center_y - 0.5 * params.height
        ) / params.width

        # TODO(bassamul.haq/zachfang): Currently, `camera.data.angle` will not
        # be set if the values of fov_x and fov_y are different. The code path
        # needs to be tested.
        if params.fov_x == params.fov_y:
            camera.data.lens_unit = "FOV"
            camera.data.angle = params.fov_x
        else:
            _logger.warning(
                f"fov_x {params.fov_x} != fov_y {params.fov_y}. "
                "'camera.data.angle' is not set."
            )

        # Set image_type specific functionality.
        if params.image_type == "color":
            scene.render.image_settings.color_mode = "RGBA"
            scene.render.image_settings.color_depth = "8"
        elif params.image_type == "depth":
            scene.render.image_settings.color_mode = "BW"
            scene.render.image_settings.color_depth = "16"
            # NOTE: Display device is set to 'None' because the pixel values of
            # the image are meant to be interpreted as depth measurements. By
            # default, Blender applies a filter that changes the values.
            scene.display_settings.display_device = "None"
            self.depth_render_settings(params.min_depth, params.max_depth)
        else:  # image_type == "label".
            scene.render.image_settings.color_mode = "RGBA"
            scene.render.image_settings.color_depth = "8"
            scene.display_settings.display_device = "None"
            self.label_render_settings()

        # Render the image.
        bpy.ops.render.render(write_still=True)

    def depth_render_settings(self, min_depth, max_depth):
        # Turn anti-aliasing off.
        bpy.context.scene.render.filter_size = 0

        # Set the background.
        bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[
            0
        ].default_value = (_UINT16_MAX, _UINT16_MAX, _UINT16_MAX, 1)

        # Update the render method to use depth image.
        self.create_depth_node_layer(min_depth, max_depth)

    def label_render_settings(self):
        scene = bpy.context.scene

        # Turn anti-aliasing off.
        scene.render.filter_size = 0

        # Set dither to zero because the 8-bit color image tries to create a
        # better perceived transition in color where there is a limited
        # palette.
        scene.render.dither_intensity = 0

        # Set the background to the specific value that Drake will interpret as
        # kEmpty(32766).
        bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[
            0
        ].default_value = (254 / 255, 127 / 255, 0, 1)

        # Iterate over all textures and set their color value.
        for name in bpy.data.objects.keys():
            # Ensure the object is a mesh.
            if "mesh" not in name.lower():
                continue

            # Get the mesh object.
            mesh = bpy.data.objects.get(name)
            assert mesh is not None, f"Mesh {mesh} is None. Check source glTF."

            mesh_color = mesh.data.materials[0].diffuse_color

            mesh.data.materials[0].use_nodes = True
            links = mesh.data.materials[0].node_tree.links
            nodes = mesh.data.materials[0].node_tree.nodes

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

    def create_depth_node_layer(self, min_depth=0.01, max_depth=10.0):
        """
        Creates a node layer to render depth images.
        """
        # Get node and node tree.
        bpy.context.scene.use_nodes = True
        nodes = bpy.data.scenes["Scene"].node_tree.nodes
        links = bpy.data.scenes["Scene"].node_tree.links

        # Clear all nodes before adding necessary nodes.
        nodes.clear()
        render_layers = nodes.new("CompositorNodeRLayers")
        composite = nodes.new("CompositorNodeComposite")
        map_value = nodes.new("CompositorNodeMapValue")

        # Convert depth measurements via a MapValueNode. The depth values are
        # measured in meters, and thus they are converted to millimeters first.
        # Blender scales the pixel values by 65535 (2^16 -1) when producing an
        # UINT16 image, so we need to offset that to get the correct UINT16
        # depth.
        assert (
            max_depth * 1000 / _UINT16_MAX <= 1.0
        ), f"Provided max_depth '{max_depth}' overflows an UINT16 depth image"
        map_value.use_min = True
        map_value.use_max = True
        map_value.size = [1000 / _UINT16_MAX]
        map_value.min = [min_depth * 1000 / _UINT16_MAX]
        map_value.max = [1.0]

        # Make links to a depth image.
        bpy.data.scenes["Scene"].view_layers["ViewLayer"].use_pass_z = True
        links.new(
            render_layers.outputs.get("Depth"), map_value.inputs.get("Value")
        )
        links.new(
            map_value.outputs.get("Value"), composite.inputs.get("Image")
        )


class ServerApp(flask.Flask):
    """The long-running Flask server application."""

    def __init__(self, *, temp_dir, blend_file=None):
        super().__init__("drake_render_gltf_blender")

        self._temp_dir = temp_dir
        self._blender = Blender(blend_file=blend_file)

        self.add_url_rule("/", view_func=self._root_endpoint)

        endpoint = "/render"
        self.add_url_rule(rule=endpoint, endpoint=endpoint, methods=["POST"],
                          view_func=self._render_endpoint)

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
        param_fields = {
            x.name: x
            for x in dc.fields(RenderParams)
        }
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

        # Save the glTF scene data.
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
        "--host", type=str, default="127.0.0.1",
        help="URL to host on, default: %(default)s.")
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port to host on, default: %(default)s.")
    parser.add_argument(
        "--debug", action="store_true",
        help="When true, flask reloads server.py when it changes.")
    parser.add_argument(
        "--blend_file", type=str, default=None,
        help="Path to a blend file.")
    args = parser.parse_args()

    prefix = "drake_render_gltf_blender_"
    with tempfile.TemporaryDirectory(prefix=prefix) as temp_dir:
        app = ServerApp(temp_dir=temp_dir, blend_file=args.blend_file)
        app.run(host=args.host, port=args.port, debug=args.debug,
                threaded=False)


if __name__ == "__main__":
    main()
