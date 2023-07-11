# SPDX-License-Identifier: BSD-2-Clause

import sys

from isort.main import main as _isort_main


def _main():
    try:
        _isort_main()
    except SystemExit as e:
        if e.code is not None and e.code != 0:
            print(
                "INFO: Run ./tools/fix_lint.sh to automatically fix this "
                "problem.",
                file=sys.stderr,
            )
        raise


assert __name__ == "__main__"
_main()
