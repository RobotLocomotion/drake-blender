from json import loads
from urllib.request import Request, urlopen

response = urlopen("https://api.github.com/repos/bazelbuild/bazel/releases")
body = response.read()
encoding = response.info().get_content_charset("iso-8859-1")
tag = sorted(
    [
        release["tag_name"]
        for release in loads(body.decode(encoding))
        if not release["prerelease"]
    ],
    key=lambda tag: tuple(int(n) for n in tag.split(".")),
    reverse=True,
)[0]
with open(".bazeliskrc", "w", encoding="utf-8") as rc:
    rc.write("# SPDX-License-Identifier: BSD-2-Clause\n\n")
    rc.write(f"USE_BAZEL_VERSION={tag}\n")
