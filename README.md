<!-- SPDX-License-Identifier: BSD-2-Clause -->

# Overview

`drake-blender` is an implementation of the Drake
[glTF Render Client-Server API](https://drake.mit.edu/doxygen_cxx/group__render__engine__gltf__client__server__api.html)
atop
[Blender](https://www.blender.org/).

**This is a relatively new project and may still have bugs.
Please share your issues and improvements on GitHub.**

## Compatibility

This software is only tested on Ubuntu 22.04 "Jammy", but should probably
work with any Python interpreter that supports our `requirements.txt`.

## Building and testing

From a git checkout of `drake-blender`:

```sh
./bazel test //...
```

## Running the render server

From a git checkout of `drake-blender`:

```sh
./bazel run :server
```

Note that `server.py` is self contained. Instead of using Bazel, you can also
run it as a standalone Python program so long as the `requirements.in` packages
are available in your Python runtime environment.

## Examples

See [examples](examples/README.md).

# Credits

The Drake-Blender project was created by the
[Robotics Division](https://www.tri.global/our-work/robotics/)
at Toyota Research Institute. Many other people have since contributed their
talents. Here's an alphabetical list (note to contributors: *do add yourself*):

* Bassam ul Haq
* Cody Simpson
* Eric Cousineau
* Jeremy Nimmer
* John Shepherd
* Kunimatsu Hashimoto
* Matthew Woehlke
* Sean Curtis
* Stephen McDowell
* Zach Fang

# Licensing

Per [LICENSE.TXT](LICENSE.TXT), this module is offered under the
[BSD-2-Clause](https://spdx.org/licenses/BSD-2-Clause.html) license, but note
that it loads `import bpy` from Blender so is also governed by the terms of
Blender license [GPL-2.0-or-later](https://www.blender.org/about/license/).

Per [examples/LICENSE.TXT](examples/LICENSE.TXT), the `examples` code is
offered under the [MIT-0](https://spdx.org/licenses/MIT-0.html) license.
