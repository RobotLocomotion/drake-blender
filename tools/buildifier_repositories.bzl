load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_file")
load("//tools:buildifier_version.bzl", "BUILDIFIER_VERSION")

def _impl(_ctx):
    releases = "https://github.com/bazelbuild/buildtools/releases"
    version = BUILDIFIER_VERSION["version"]
    for name, sha256 in BUILDIFIER_VERSION["binaries"].items():
        http_file(
            name = name,
            executable = True,
            sha256 = sha256,
            url = "{releases}/download/v{version}/{name}".format(
                releases = releases,
                version = version,
                name = name,
            ),
        )

buildifier_repositories = module_extension(
    implementation = _impl,
)
