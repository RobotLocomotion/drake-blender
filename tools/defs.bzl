# SPDX-License-Identifier: BSD-2-Clause

load("@rules_python//python:defs.bzl", "py_test")

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
        deps = [
            "@test_requirements_pycodestyle//:pkg",
        ],
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
        deps = [
            "@test_requirements_black//:pkg",
        ],
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
        deps = [
            "@test_requirements_isort//:pkg",
        ],
    )

def bazel_lint_test(name, srcs):
    """Adds Bazel linter checks for the given `srcs`."""
    locations = [
        "$(location {})".format(src)
        for src in srcs
    ]
    native.sh_test(
        name = name,
        size = "small",
        srcs = ["//tools:buildifier"],
        data = srcs,
        args = ["-mode=check"] + locations,
        tags = ["lint"],
    )
