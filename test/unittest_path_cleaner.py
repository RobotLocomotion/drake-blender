# Ignore Ubuntu-installed packages during local testing, so we fail-fast when
# there are missing `deps = []` in the BUILD file.
import sys

ubuntu_paths = [x for x in sys.path if x.endswith("/dist-packages")]  # noqa
[sys.path.remove(x) for x in ubuntu_paths]  # noqa
