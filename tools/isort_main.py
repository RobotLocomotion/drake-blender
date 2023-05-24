import sys

from isort.main import main as _isort_main


def _main():
    try:
        _isort_main()
    except SystemExit as e:
        if (e.code or 0) != 0:
            print(
                "INFO: Run ./tools/fix_lint.sh to automatically fix this "
                "problem.",
                file=sys.stderr,
            )
        raise


assert __name__ == "__main__"
_main()
