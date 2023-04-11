<!-- SPDX-License-Identifier: BSD-2-Clause -->

# Overview

`drake-blender` is an implementation of the Drake
[glTF Render Client-Server API](https://drake.mit.edu/doxygen_cxx/group__render__engine__gltf__client__server__api.html)
atop
[Blender](https://www.blender.org/).

**This repository is currently a WORK IN PROGRESS and still has many bugs.
Please check back later once the code has been battle-tested.**

## Compatibility

This software is only tested on Ubuntu 22.04 "Jammy", but should probably
work with any Python interpreter that supports our `requirements.txt`.

## Building and testing

```sh
./bazel test //...
```

## Running the render server

```sh
./bazel run :server
```

## Examples

See [examples](examples/README.md).

# Licensing

Per [LICENSE.TXT](LICENSE.TXT), this module is offered under the
[BSD-2-Clause](https://spdx.org/licenses/BSD-2-Clause.html) license, but note
that it loads `import bpy` from Blender so is also governed by the terms of
Blender license [GPL-2.0-or-later](https://www.blender.org/about/license/).

Per [examples/LICENSE.TXT](examples/LICENSE.TXT), the `examples` code is
offered under the [MIT-0](https://spdx.org/licenses/MIT-0.html) license.
