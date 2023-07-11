# SPDX-License-Identifier: BSD-2-Clause

import sys

import pycodestyle


def _main():
    report = pycodestyle.StyleGuide(parse_argv=True).check_files()
    if report.total_errors:
        print(
            "INFO: It's possible that running ./tools/fix_lint.sh could "
            "automatically fix this problem.",
            file=sys.stderr,
        )
        sys.exit(1)


assert __name__ == "__main__"
_main()
