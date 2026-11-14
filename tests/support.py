# -*- coding: utf-8 -*-
"""Shared helpers for the public test suite (standard library only)."""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
FIXTURES = os.path.join(ROOT, "fixtures")

# Built from fragments so this helper itself never carries a literal private
# path or credential marker into the public tree.
FORBIDDEN_TOKENS = (
    "G:" + "\\",
    "C:" + "\\Users",
    "C:" + "/Users",
    "/" + "home/",
    "local_" + "0fc3a7e7",
    "s" + "k-",
    "Bea" + "rer ",
)


def run_cli(args, cwd=None, env_extra=None):
    env = {key: value for key, value in os.environ.items()
           if key not in ("PYTHONPATH", "CAD_SHOWCASE_FAIL_ENGINE")}
    env["PYTHONNOUSERSITE"] = "1"
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "-m", "cad_agent_showcase"] + list(args),
        cwd=cwd or ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    envelope = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc.returncode, envelope, proc.stdout, proc.stderr


def assert_no_forbidden(testcase, text):
    for token in FORBIDDEN_TOKENS:
        testcase.assertNotIn(token, text)
