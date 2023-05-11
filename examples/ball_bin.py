# SPDX-License-Identifier: MIT-0

"""
Demonstrates combining Drake with the Blender render server to create a
simulation video (or still image).

In this demo, moving objects (some balls) and a fixed object (a bin) are
simulated by Drake and the static visual background (a room with custom
lighting) is provided by a Blender file.
"""

import argparse
import dataclasses as dc
import logging
import os
from pathlib import Path
import time
import typing
import signal
import socket
import subprocess
import tempfile

from bazel_tools.tools.python.runfiles import runfiles
import tqdm

from pydrake.common import configure_logging
from pydrake.common.yaml import yaml_load_typed
from pydrake.geometry.render import (
    RenderEngineGltfClientParams,
    RenderEngineVtkParams,
    MakeRenderEngineGltfClient,
    MakeRenderEngineVtk,
)
from pydrake.multibody.parsing import (
    ModelDirective,
    ModelDirectives,
    ProcessModelDirectives,
)
from pydrake.multibody.plant import (
    AddMultibodyPlant,
    MultibodyPlantConfig,
)
from pydrake.systems.analysis import (
    ApplySimulatorConfig,
    Simulator,
    SimulatorConfig,
)
from pydrake.systems.framework import (
    DiagramBuilder,
)
from pydrake.systems.lcm import (
    LcmBuses,
)
from pydrake.systems.sensors import (
    ApplyCameraConfig,
    CameraConfig,
    ImageWriter,
    PixelType,
)
from pydrake.visualization import (
    VideoWriter,
)


@dc.dataclass
class Scenario:
    """Defines the YAML format for a scenario to be simulated."""

    # The maximum simulation time (in seconds).
    simulation_duration: float = 1.0

    # Simulator configuration (integrator and publisher parameters).
    simulator_config: SimulatorConfig = SimulatorConfig()

    # All of the fully deterministic elements of the simulation.
    directives: typing.List[ModelDirective] = dc.field(default_factory=list)

    # Cameras to add to the scene.
    cameras: typing.Mapping[str, CameraConfig] = dc.field(default_factory=dict)


def _find_resource(bazel_path):
    """Looks up the path to "runfiles" data, as organized by Bazel."""
    manifest = runfiles.Create()
    location = manifest.Rlocation(bazel_path)
    assert location is not None, f"Not a resource: {bazel_path}"
    result = Path(location)
    assert result.exists(), f"Missing resource: {bazel_path}"
    return result


class _ProgressBar:
    def __init__(self, simulation_duration):
        self._tqdm = tqdm.tqdm(total=simulation_duration)
        self._current_time = 0.0

    def __call__(self, context):
        old_time = self._current_time
        self._current_time = context.get_time()
        self._tqdm.update(self._current_time - old_time)


def _run(args):
    """Runs the demo."""
    scenario = yaml_load_typed(
        schema=Scenario,
        filename=args.scenario_file,
        defaults=Scenario())

    # Create the scene.
    builder = DiagramBuilder()
    plant, scene_graph = AddMultibodyPlant(
        config=MultibodyPlantConfig(),
        builder=builder)
    added_models = ProcessModelDirectives(
        directives=ModelDirectives(directives=scenario.directives),
        plant=plant)
    plant.Finalize()

    # Add remote rendering capability to scene graph.
    blender_engine = MakeRenderEngineGltfClient(RenderEngineGltfClientParams(
        base_url="http://127.0.0.1:8000"))
    scene_graph.AddRenderer("blender", blender_engine)
    vtk_engine = MakeRenderEngineVtk(RenderEngineVtkParams())
    scene_graph.AddRenderer("vtk", vtk_engine)

    # Add the camera(s).
    video_writers = []
    for _, camera in scenario.cameras.items():
        if args.still:
            camera.show_rgb = False
        name = camera.name
        ApplyCameraConfig(config=camera, builder=builder)
        sensor = builder.GetSubsystemByName(f"rgbd_sensor_{name}")
        if args.still:
            writer = builder.AddSystem(ImageWriter())
            writer.DeclareImageInputPort(
                pixel_type=PixelType.kRgba8U,
                port_name="color_image",
                file_name_format=f"./{name}",
                publish_period=1.0,
                start_time=0.0)
            builder.Connect(
                sensor.GetOutputPort("color_image"),
                writer.GetInputPort("color_image"))
        else:
            writer = VideoWriter(filename=f"{name}.mp4", fps=16, backend="cv2")
            builder.AddSystem(writer)
            writer.ConnectRgbdSensor(builder=builder, sensor=sensor)
            video_writers.append(writer)

    # Create the simulator.
    simulator = Simulator(builder.Build())
    ApplySimulatorConfig(scenario.simulator_config, simulator)

    # Simulate.
    if args.still:
        logging.info("Creating still image(s)")
        simulator.AdvanceTo(1e-3)
    else:
        logging.info("Creating video(s)")
        simulator.set_monitor(_ProgressBar(scenario.simulation_duration))
        simulator.AdvanceTo(scenario.simulation_duration)
        for writer in video_writers:
            writer.Save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--still", action="store_true",
        help="Don't create a video; instead, capture a single photograph of "
             "the initial conditions.")
    parser.add_argument(
        "--no-server", dest="server", action="store_false",
        help="Don't automatically launch the blender server.")
    args = parser.parse_args()

    scenario_file = _find_resource("__main__/examples/ball_bin.yaml")
    setattr(args, "scenario_file", scenario_file)

    # Launch the server (if requested).
    if args.server:
        logging.info("Starting drake-blender server")
        server = _find_resource("__main__/server")
        blend_file = _find_resource("color_attribute_painting/file/downloaded")
        log_file = open(os.environ["TMPDIR"] + "/server-log.txt", "w")
        # TODO(jwnimmer-tri) Echo the log file to the console.
        server_process = subprocess.Popen([
            server,
            f"--blend_file={blend_file}",
        ], stdout=log_file, stderr=subprocess.STDOUT)
        # Wait until the server is ready.
        while True:
            with socket.socket() as s:
                try:
                    s.connect(("127.0.0.1", 8000))
                    # Success!
                    break
                except ConnectionRefusedError as e:
                    time.sleep(0.1)
            assert server_process.poll() is None
        logging.info("The drake-blender server is ready")
    else:
        server_process = None

    # Run the demo.
    try:
        _run(args)
    finally:
        if server_process is not None:
            server_process.send_signal(signal.SIGINT)
            try:
                server_process.wait(1.0)
            except subprocess.TimeoutExpired:
                server_process.terminate()
            log_file.flush()


def _wrapped_main():
    # Do our best to clean up after ourselves, by advising Drake code to use
    # a directory other than /tmp.
    with tempfile.TemporaryDirectory(prefix="ball_bin_") as temp_dir:
        os.environ["TMPDIR"] = temp_dir
        main()


if __name__ == "__main__":
    # Tell Drake it that even though it's running from Bazel it's not a source
    # build so it needs to use resources from the wheel file not Bazel.
    # TODO(jwnimmer-tri) As of Drake >= v1.16.0, this is no longer necessary.
    os.environ["DRAKE_RESOURCE_ROOT"] = str(_find_resource(
        "examples_requirements_drake/site-packages/"
        "pydrake/share/drake/package.xml").parent.parent)

    # Create output files in $PWD, not runfiles.
    if "BUILD_WORKING_DIRECTORY" in os.environ:
        os.chdir(os.environ["BUILD_WORKING_DIRECTORY"])

    configure_logging()
    _wrapped_main()
