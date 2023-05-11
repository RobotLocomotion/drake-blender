<!-- SPDX-License-Identifier: MIT-0 -->

# Overview

This directory contains an example of how to use drake-blender in your own code.

TODO(jwnimmer-tri) Add more examples!

## Ball Bin example

This shows how to use the Drake Simulator to create videos of a dynamic scene,
where moving objects (some balls) and a fixed object (a bin) are simulated by
Drake and the static visual background (a room with custom lighting) is provided
by a Blender file.

https://github.com/RobotLocomotion/drake-blender/assets/17596505/c0f5f6ae-db51-42cb-9a86-09fa1c9ae18e

From the root directory of the drake-blender source checkout, run:

```sh
$ ./bazel run //examples:ball_bin
```

This will create a videos named blender_camera.mp4 and vtk_camera.mp4.
The blender-rendered video will show the balls, bin, and room in the background.
The VTK-rendered video will show only the balls and bin.
Expect the video rendering to take 5 minutes or longer.

To create a single photo instead of a movie, use `--still`:

```sh
$ ./bazel run //examples:ball_bin -- --still
```

Thanks to Ramil Roosileht (https://twitter.com/limarest_art) for creating
the blender scene we use (from https://www.blender.org/download/demo-files/).

