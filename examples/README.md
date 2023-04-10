<!-- SPDX-License-Identifier: MIT-0 -->

# Overview

This directory contains an example of how to use drake-blender in your own code.

TODO(jwnimmer-tri) Add more examples!

## Ball Bin example

This (incomplete) example is still a "work in progress".

From the root directory of the drake-blender source checkout, run:

```sh
$ ./bazel run //examples:ball_bin
```

This will create a videos named blender_camera.mp4 and vtk_camera.mp4.

To create a single photo instead of a movie, use `--still`:

```sh
$ ./bazel run //examples:ball_bin -- --still
```
