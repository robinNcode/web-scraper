"""Passenger entry point used by cPanel's WSGI application manager."""

import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
os.chdir(APP_ROOT)
sys.path.insert(0, str(APP_ROOT))

# Set PAPER_PYTHON to the app's virtualenv interpreter when Passenger does not
# start this app with that interpreter already.
INTERPRETER = os.getenv("PAPER_PYTHON")
if INTERPRETER and sys.executable != INTERPRETER:
    os.execl(INTERPRETER, INTERPRETER, *sys.argv)

from paper_scraper.web import application  # noqa: E402
