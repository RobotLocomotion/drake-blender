# SPDX-License-Identifier: BSD-2-Clause

load("@rules_python//python:defs.bzl", "py_test")

def py_lint_test(name, srcs):
    native.filegroup(
        name = "_{}_data".format(name),
        srcs = srcs,
    )
    py_test(
        name = "pycodestyle_{}".format(name),
        size = "small",
        srcs = ["@test_requirements_pycodestyle//:rules_python_wheel_entry_point_pycodestyle.py"],
        main = "@test_requirements_pycodestyle//:rules_python_wheel_entry_point_pycodestyle.py",
        data = [":_{}_data".format(name)],
        args = ["$(rootpaths :_{}_data)".format(name)],
        tags = ["lint", "pycodestyle"],
        deps = [
            "@test_requirements_pycodestyle//:rules_python_wheel_entry_point_pycodestyle",
        ]
    )
    py_test(
        name = "black_{}".format(name),
        size = "small",
        srcs = ["@test_requirements_black//:rules_python_wheel_entry_point_black.py"],
        main = "@test_requirements_black//:rules_python_wheel_entry_point_black.py",
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
            "@test_requirements_black//:rules_python_wheel_entry_point_black",
        ]
    )
