# Do not run this by hand.  Instead, run the full tools/upgrade.sh.

import ast
import hashlib
import json
from pprint import pformat
from urllib.request import urlopen


def _get_current_bazelisk_version() -> str:
    """Parses ``./bazel`` for the old version of bazelisk."""
    with open("bazel", encoding="utf-8") as f:
        lines = f.read().splitlines()
    prefix = "_VERSION = "
    for line in lines:
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip('"')
    raise RuntimeError(f"Could not find a line starting with {prefix!r}")


def _write_bazelisk_version(new, sha256):
    """Updates ``./bazel`` with the new version of bazelisk."""
    with open("bazel", encoding="utf-8") as f:
        lines = f.read().splitlines()
    for prefix, value in (("_VERSION = ", new), ("_SHA256 = ", sha256)):
        for i in range(len(lines)):
            if lines[i].startswith(prefix):
                lines[i] = f'{prefix}"{value}"'
                break
        else:
            raise RuntimeError(f"Could not find line starting with {prefix!r}")
    new_content = "\n".join(lines) + "\n"
    with open("bazel", "w", encoding="utf-8") as f:
        f.write(new_content)


def _get_current_buildifier_version():
    """Parses ``buildifier_version.bzl`` for the old version."""
    with open("tools/buildifier_version.bzl", encoding="utf-8") as f:
        content = f.read()
    prefix = "BUILDIFIER_VERSION = "
    assert content.startswith(prefix)
    return ast.literal_eval(content.removeprefix(prefix))


def _write_buildifier_version(new):
    """Overwrites ``buildifier_version.bzl`` with the new version.
    We assume that tools/update.sh will run buildifier formatting afterwards.
    """
    prefix = "BUILDIFIER_VERSION = "
    content = prefix + pformat(new, width=1, sort_dicts=False)
    with open("tools/buildifier_version.bzl", "w", encoding="utf-8") as f:
        f.write(content)


def _find_latest_github_release(repo) -> str:
    """Finds the highest-numbered release (excluding prereleases)."""
    response = urlopen(f"https://api.github.com/repos/{repo}/releases")
    body = response.read()
    encoding = response.info().get_content_charset("iso-8859-1")
    releases = json.loads(body.decode(encoding))
    tags = sorted(
        [
            release["tag_name"].lstrip("v")
            for release in releases
            if not release["prerelease"]
        ],
        key=lambda tag: tuple(int(n) for n in tag.split(".")),
        reverse=True,
    )
    return tags[0]


def _get_url_checksum(url) -> str:
    """Returns the sha256sum string of the given url."""
    print(f"Downloading {url} ...")
    hasher = hashlib.sha256()
    with urlopen(url) as response:
        while True:
            data = response.read(4096)
            if not data:
                break
            hasher.update(data)
    return hasher.hexdigest()


def _upgrade_bazelisk():
    """Upgrades bazelisk to its latest version (if necessary)."""
    old = _get_current_bazelisk_version()
    new = _find_latest_github_release("bazelbuild/bazelisk")
    if new == old:
        print(f"bazelisk is already at the latest version {new}")
        return
    print(f"bazelisk will be upgraded to version {new}")
    raw_download = "https://raw.githubusercontent.com/bazelbuild/bazelisk"
    sha256 = _get_url_checksum(f"{raw_download}/v{new}/bazelisk.py")
    _write_bazelisk_version(new, sha256)


def _upgrade_buildifier():
    """Upgrades buildifier to its latest version (if necessary)."""
    buildifier_version = _get_current_buildifier_version()
    old = buildifier_version["version"]
    new = _find_latest_github_release("bazelbuild/buildtools")
    if new == old:
        print(f"buildifier is already at the latest version {new}")
        return
    print(f"buildifier will be upgraded to version {new}")
    buildifier_version["version"] = new
    names = list(buildifier_version["binaries"].keys())
    releases = "https://github.com/bazelbuild/buildtools/releases"
    for name in names:
        buildifier_version["binaries"][name] = _get_url_checksum(
            f"{releases}/download/v{new}/{name}"
        )
    _write_buildifier_version(buildifier_version)


def _main():
    _upgrade_bazelisk()
    _upgrade_buildifier()


assert __name__ == "__main__"
_main()
