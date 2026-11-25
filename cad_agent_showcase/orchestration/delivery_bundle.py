"""Bind and read back the six public delivery files and their packaged copies."""

import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path

from ..contracts import (CODE_ARTIFACT_HASH_MISMATCH, CODE_READBACK_MISMATCH,
                         ENGINEERING_FLAGS, EVIDENCE_REPLAY, WATERMARK,
                         FixtureIntegrityError)
from ..util import write_json

_PAYLOAD = ("overview.png", "booklet.pdf", "preview.html", "notes.md")
_MANIFEST = "manifest.json"
_ARCHIVE = "bundle.zip"
BUNDLE_FILES = (*_PAYLOAD, _MANIFEST, _ARCHIVE)
_SCHEMA = "cad_agent_showcase.standard_delivery.v1"

_PREVIEW = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>Synthetic CAD replay overview</title>
<h1>Synthetic CAD replay overview</h1>
<p>DEMO / REPLAY - SYNTHETIC FIXTURE - NOT FOR MANUFACTURING</p>
<details open>
<summary>Overview image</summary>
<a href="overview.png"><img src="overview.png" alt="Synthetic replay overview"
style="display:block;max-width:100%;height:auto"></a>
</details>
<p><a href="booklet.pdf">Replay booklet</a> · <a href="notes.md">Scope and notes</a></p>
</html>
"""

_NOTES = """# Synthetic replay delivery

DEMO / REPLAY - SYNTHETIC FIXTURE - NOT FOR MANUFACTURING

The overview comes from the committed synthetic examples. The booklet
describes the replay evidence. The manifest binds this delivery to one input
revision and records each payload's byte count and SHA-256. The archive
contains the four payload files and the manifest. Readback verifies these
bytes and their bindings. Engineering approval and production approval
remain false.
"""


def _fingerprint(data):
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _zip_payload(directory):
    with zipfile.ZipFile(directory / _ARCHIVE, "w") as package:
        for name in (*_PAYLOAD, _MANIFEST):
            package.writestr(zipfile.ZipInfo(name), (directory / name).read_bytes())


def verify_standard_bundle(directory, *, binding):
    """Verify the exact six-file bundle and the five archived byte copies."""
    directory = Path(directory)
    try:
        names = {path.name for path in directory.iterdir()}
        if names != set(BUNDLE_FILES):
            raise ValueError("The six delivery filenames must match the bundle contract.")
        for name in BUNDLE_FILES:
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("A standard delivery member must be a regular file.")
        manifest_raw = (directory / _MANIFEST).read_bytes()
        manifest = json.loads(manifest_raw)
        if (manifest["schema"] != _SCHEMA or manifest["binding"] != binding
                or manifest["watermark"] != WATERMARK
                or manifest["evidence_type"] != EVIDENCE_REPLAY
                or any(manifest.get(flag) is not False for flag in ENGINEERING_FLAGS)
                or set(manifest["files"]) != set(_PAYLOAD)):
            raise ValueError("The standard delivery manifest binding changed.")
        expected = {_MANIFEST: manifest_raw}
        for name in _PAYLOAD:
            data = (directory / name).read_bytes()
            if manifest["files"][name] != _fingerprint(data):
                raise ValueError("A standard delivery member differs from its manifest: " + name)
            expected[name] = data
        archive_data = (directory / _ARCHIVE).read_bytes()
        with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
            if sorted(archive.namelist()) != sorted(expected):
                raise ValueError("The delivery archive member set changed.")
            for name, data in expected.items():
                info = archive.getinfo(name)
                if info.file_size != len(data) or archive.read(info) != data:
                    raise ValueError("A delivery archive member differs from the bundle: " + name)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, EOFError,
            zipfile.BadZipFile, RuntimeError) as exc:
        raise FixtureIntegrityError(CODE_READBACK_MISMATCH, str(exc)) from exc
    return {"verified": True, "files": list(BUNDLE_FILES), "archive_members": list(expected),
            "manifest_sha256": _fingerprint(manifest_raw)["sha256"],
            "archive_sha256": _fingerprint(archive_data)["sha256"],
            "binding": binding}


def write_standard_bundle(out_dir, legacy_manifest, legacy_sha, booklet):
    """Publish the six-piece replay for one revision and verify it on disk."""
    out = Path(out_dir)
    image = next(item for item in legacy_manifest["artifacts"] if item["role"] == "preview-3d")
    overview = (out / image["path"]).read_bytes()
    if _fingerprint(overview)["sha256"] != image["sha256"]:
        raise FixtureIntegrityError(CODE_ARTIFACT_HASH_MISMATCH, image["path"])
    binding = {key: legacy_manifest[key] for key in (
        "task_id", "entry", "revision", "input_digest", "confirmation_binding_sha256")}
    binding["delivery_manifest_sha256"] = legacy_sha
    parent = out / "bundle"
    parent.mkdir(exist_ok=True)
    directory = parent / f"revision-{binding['revision']}-{legacy_sha[:12]}"
    data = {"overview.png": overview, "booklet.pdf": booklet,
            "preview.html": _PREVIEW.encode(), "notes.md": _NOTES.encode()}
    manifest = {"schema": _SCHEMA, "binding": binding, "evidence_type": EVIDENCE_REPLAY,
                "watermark": WATERMARK, **ENGINEERING_FLAGS,
                "files": {name: _fingerprint(data[name]) for name in _PAYLOAD}}
    with tempfile.TemporaryDirectory(dir=parent) as staging:
        stage = Path(staging) / "bundle"
        stage.mkdir()
        for name, content in data.items():
            (stage / name).write_bytes(content)
        write_json(stage / _MANIFEST, manifest)
        _zip_payload(stage)
        try:
            stage.rename(directory)
        except OSError:
            if not directory.is_dir() or directory.is_symlink():
                raise
            # Reuse one completed version only when the same evidence is present.
            for name in BUNDLE_FILES:
                if (directory / name).read_bytes() != (stage / name).read_bytes():
                    raise FixtureIntegrityError(CODE_READBACK_MISMATCH,
                                                "A different delivery occupies this revision.")
    return {**verify_standard_bundle(directory, binding=binding),
            "path": directory.relative_to(out).as_posix()}
