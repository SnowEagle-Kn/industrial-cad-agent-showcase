# -*- coding: utf-8 -*-
"""Small standard-library helpers shared by the demo package."""

import hashlib
import json
import os


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def canonical_sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    with open(path, "rb") as handle:
        return json.loads(handle.read().decode("utf-8-sig"))


def write_json(path, value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         indent=2, allow_nan=False) + "\n"
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(payload.encode("utf-8"))


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path
