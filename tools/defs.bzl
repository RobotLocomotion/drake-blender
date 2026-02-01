# SPDX-License-Identifier: BSD-2-Clause

load("@examples_requirements//:requirements.bzl", examples_requirement = "requirement")
load("@requirements//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_test")
load("@rules_shell//shell:sh_test.bzl", "sh_test")
load("@test_requirements//:requirements.bzl", test_requirement = "requirement")

def pip(name, extra = None):
    """Translates a pip package name to the bazel deps name.

    The `extra` can be used to select which requirements.txt to use. When
    None, uses the root `requirements.txt`. Otherwise can be `"[test]"` for
    `test/requiremens.txt` or `"[examples]"` for `examples/requirements.txt`.
    """
    if not extra:
        return requirement(name)
    if extra == "[examples]":
        return examples_requirement(name)
    if extra == "[test]":
        return test_requirement(name)
    fail("Bad extra: " + repr(extra))

def py_lint_test(
        name,
        srcs,
        *,
        use_black = True,
        use_codestyle = True,
        use_isort = True):
    """Adds Python linter checks for the given `srcs`."""
    native.filegroup(
        name = "_{}_data".format(name),
        srcs = srcs,
    )
    (not use_codestyle) or py_test(
        name = "pycodestyle_{}".format(name),
        size = "small",
        srcs = ["//tools:pycodestyle_main.py"],
        main = "//tools:pycodestyle_main.py",
        data = [":_{}_data".format(name)],
        args = ["$(rootpaths :_{}_data)".format(name)],
        tags = ["lint", "pycodestyle"],
        deps = [pip("pycodestyle", "[test]")],
    )
    (not use_black) or py_test(
        name = "black_{}".format(name),
        size = "small",
        srcs = ["//tools:black_main.py"],
        main = "//tools:black_main.py",
        data = [
            ":_{}_data".format(name),
            "//:pyproject.toml",
        ],
        args = [
            "--quiet",
            "--check",
            "--diff",
            "$(rootpaths :_{}_data)".format(name),
        ],
        tags = ["lint", "black"],
        deps = [pip("black", "[test]")],
    )

    (not use_isort) or py_test(
        name = "isort_{}".format(name),
        size = "small",
        srcs = ["//tools:isort_main.py"],
        main = "//tools:isort_main.py",
        data = [
            ":_{}_data".format(name),
            "//:pyproject.toml",
        ],
        args = [
            "--check-only",
            "$(rootpaths :_{}_data)".format(name),
        ],
        tags = ["lint", "isort"],
        deps = [pip("isort", "[test]")],
    )

def bazel_lint_test(name, srcs):
    """Adds Bazel linter checks for the given `srcs`."""
    locations = [
        "$(location {})".format(src)
        for src in srcs
    ]
    sh_test(
        name = name,
        size = "small",
        srcs = ["//tools:buildifier"],
        data = srcs,
        args = ["-mode=check"] + locations,
        tags = ["lint"],
    )
