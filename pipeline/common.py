"""Paths, the month index and the 0.25 degree grid, shared by the pipeline scripts."""

import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "global"
CELLS = DATA / "cells"
MODEL = DATA / "model"
APP_DATA = ROOT / "frontend" / "public" / "world"

CELL = 0.25  # grid step, degrees
T0 = 2000 * 12 + 10  # the record starts in November 2000


def month_index(s):
    """'2012-02' -> months since November 2000."""
    return int(s[:4]) * 12 + int(s[5:7]) - 1 - T0


def month_name(t):
    """Inverse of month_index."""
    return f"{(T0 + t) // 12}-{(T0 + t) % 12 + 1:02d}"


def cell_key(ilat, ilon):
    """One integer per grid cell, from the cell's row and column (floor(lat / CELL), floor(lon / CELL))."""
    return (np.asarray(ilat).astype(np.int64) + 400) * 4000 + (np.asarray(ilon) + 800)


def cell_lat(keys):
    return (keys // 4000 - 400) * CELL


def cell_lon(keys):
    return (keys % 4000 - 800) * CELL


def log(*args):
    print(time.strftime("%H:%M:%S"), *args, flush=True)
