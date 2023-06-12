# Do not run this by hand.  Instead, run the full requirements_upgrade.sh.

from json import loads
from urllib.request import urlopen

# Find the highest-numbered release (excluding prereleases).
response = urlopen("https://api.github.com/repos/bazelbuild/bazel/releases")
body = response.read()
encoding = response.info().get_content_charset("iso-8859-1")
releases = loads(body.decode(encoding))
tag = sorted(
    [release["tag_name"] for release in releases if not release["prerelease"]],
    key=lambda tag: tuple(int(n) for n in tag.split(".")),
    reverse=True,
)[0]

# Update the dotfile.
with open(".bazeliskrc", "w", encoding="utf-8") as rc:
    rc.write("# SPDX-License-Identifier: BSD-2-Clause\n\n")
    rc.write(f"USE_BAZEL_VERSION={tag}\n")
