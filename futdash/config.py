"""Defaults, in one place so a new game year is a one-line change."""

from __future__ import annotations

import os

# FC 27. Bump when the next title lands; the scraping sources build their
# URLs from this.
GAME_YEAR = int(os.environ.get("FUTDASH_YEAR", "27"))

# 'pc' or 'console'. The two markets are completely separate and their
# prices are not interchangeable, so this is not a cosmetic setting.
PLATFORM = os.environ.get("FUTDASH_PLATFORM", "pc")

# Default target margin for the snipe calculator: 20% after tax.
TARGET_MARGIN = float(os.environ.get("FUTDASH_MARGIN", "0.2"))

HOST = os.environ.get("FUTDASH_HOST", "127.0.0.1")
PORT = int(os.environ.get("FUTDASH_PORT", "8765"))
