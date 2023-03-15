# SPDX-License-Identifier: BSD-2-Clause

load("@rules_python//python:defs.bzl", "py_test")

def pycodestyle_test(name, srcs):
    native.filegroup(
        name = "_{}_data".format(name),
        srcs = srcs,
    )
    py_test(
        name = name,
        size = "small",
        srcs = ["@requirements_pycodestyle//:rules_python_wheel_entry_point_pycodestyle.py"],
        main = "@requirements_pycodestyle//:rules_python_wheel_entry_point_pycodestyle.py",
        data = [":_{}_data".format(name)],
        args = ["$(rootpaths :_{}_data)".format(name)],
        deps = [
            "@requirements_pycodestyle//:rules_python_wheel_entry_point_pycodestyle",
        ]
    )
