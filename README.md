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

## Running the render server

There are three ways to run the server.

(1) From pip:

Ensure you are using a virtual environment:
```sh
python3 -m venv env
```

Install into the virtual environment, either from a release tag or from the
development branch:

(a) Using a release tag:
```sh
env/bin/pip install https://github.com/RobotLocomotion/drake-blender/archive/refs/tags/v0.2.1.zip
env/bin/drake-blender-server --help
```

(b) Using the development branch:

```sh
env/bin/pip install https://github.com/RobotLocomotion/drake-blender/archive/refs/heads/main.zip
env/bin/drake-blender-server --help
```

(2) From a git checkout of `drake-blender`:

```sh
./bazel run :server -- --help
```

This way has no extra setup steps. It will automatically download the required
dependencies into the Bazel sandbox, using the same versions as pinned by our
requirements lockfile that is tested in our Continuous Integration build.

(3) From your own virtual environment:

The `server.py` file is self-contained -- it does not import any other files
from drake-blender. Instead of using Bazel, you can also run it as a standalone
Python program (`python3 server.py`) so long as the packages listed in our
`requirements.in` are available in your Python runtime environment. You are
responsible for preparing and activating an appropriate virtual environment on
your own.

## Examples

See [examples](examples/README.md).

## Testing (for developers)

From a git checkout of `drake-blender`:

```sh
./bazel test //...
```

### Linting

Check for lint:

```sh
./bazel test //... --config=lint
```

Fix all lint:

```sh
./tools/fix_lint.sh
```

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
