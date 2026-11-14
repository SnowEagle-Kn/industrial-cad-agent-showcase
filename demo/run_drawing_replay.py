# -*- coding: utf-8 -*-
"""Convenience wrapper: python demo/run_drawing_replay.py [extra args]"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cad_agent_showcase.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["demo", "drawing", "--replay"] + sys.argv[1:]))
