#!/usr/bin/env python
"""Django management entrypoint for the MarketDebater frontend."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    root_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "marketdebater_frontend.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
