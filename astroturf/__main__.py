"""Entry point for `python -m astroturf`."""

import sys

from astroturf.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
