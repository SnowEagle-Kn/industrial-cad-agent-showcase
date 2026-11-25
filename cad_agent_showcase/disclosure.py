"""Inspect the public source tree without loading the code under inspection."""

import ast
import os
from pathlib import Path
import re
import subprocess


FORBIDDEN_IMPORTS = frozenset({"ocp", "cadquery", "ezdxf", "fitz", "pymupdf", "pil", "numpy"})
PRIVATE_DIRS = frozenset({".claude", ".codex", "vendor", "runtime-contracts"})
HOST_PATH = re.compile(
    r"(?i)(?<![a-z0-9])[a-z]:[\\/]+(?:users|claude)(?![\w.-])"
    r"|(?<![a-z0-9])[a-z]:[\\/]+[a-z_.-][a-z0-9_. -]{1,48}[\\/]"
    r"|(?:^|[ \t\"'])/(?:Users|home)/[^/\s]+"
)
PRIVATE_CODE_NAME = re.compile(r"[\w.-]+\.py\b")
ARCHIVE_TRANSIENT_DIRS = frozenset({"__pycache__", ".venv", "demo-output"})


def _source_paths(root: Path) -> list[str]:
    if (root / ".git").exists():
        command = ["git", "-C", os.fspath(root), "ls-files", "--cached", "--full-name", "-z"]
        raw = subprocess.run(command, check=True, capture_output=True).stdout
        return sorted(set(raw.decode("utf-8").split("\0")) - {""})

    # Downloaded source snapshots do not have an index. Audit their files
    # directly, with only local Python and replay output excluded.
    paths = []
    for directory, folders, files in os.walk(root):
        current = Path(directory)
        for name in folders[:]:
            path = current / name
            if path.is_symlink():
                paths.append(path.relative_to(root).as_posix())
                folders.remove(name)
            elif name == "__pycache__" or (current == root and name in ARCHIVE_TRANSIENT_DIRS):
                folders.remove(name)
        paths.extend((current / name).relative_to(root).as_posix() for name in files)
    return sorted(paths)


def _private_marker(text: str, filenames: tuple[str, ...], terms: tuple[str, ...]) -> str | None:
    if HOST_PATH.search(text):
        return "private host path"
    folded = text.casefold()
    if any(word and word in folded for word in terms):
        return "restricted source marker"
    for match in PRIVATE_CODE_NAME.finditer(text):
        filename = match.group()
        if not filename.isascii() or filename.casefold() in filenames:
            return "restricted source filename"
    return None


def _import_violations(data: bytes, path: str) -> list[str]:
    try:
        tree = ast.parse(data, filename=path)
    except (SyntaxError, ValueError):
        return [f"{path}: Python source could not be parsed"]
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            modules = [node.module or ""]
        else:
            continue
        if any(module.split(".", 1)[0].casefold() in FORBIDDEN_IMPORTS for module in modules):
            findings.append(f"{path}:{node.lineno}: prohibited CAD/media import")
    return findings


def scan_repository(root, *, private_filenames=(), private_terms=()) -> list[str]:
    """Check every tracked source, or every file in an extracted source snapshot.

    The release reviewer can supply exact restricted names and terms from the
    private inventory. The public checkout carries only the general policy.
    Findings identify affected files without reproducing matched content.
    """
    root = Path(root).resolve()
    filenames = tuple(word.casefold() for word in private_filenames)
    terms = tuple(word.casefold() for word in private_terms)
    try:
        paths = _source_paths(root)
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        return ["Could not enumerate the Git index"]
    if not paths:
        return ["Source tree is empty or unreadable"]

    findings = []
    for index, name in enumerate(paths, 1):
        path = root / name
        private_name = _private_marker(name, filenames, terms)
        if private_name or any(part.casefold() in PRIVATE_DIRS for part in Path(name).parts):
            findings.append(f"Source entry {index}: {private_name or 'restricted source directory'}")
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            findings.append(f"Source entry {index}: unreadable file or path outside the source tree")
            continue
        try:
            data = path.read_bytes()
        except OSError:
            findings.append(f"{name}: could not inspect source file")
            continue
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            contents = data.decode("utf-16", errors="ignore")
        else:
            contents = data.decode("utf-8", errors="replace")
        private_content = _private_marker(contents, filenames, terms)
        if private_content:
            findings.append(f"{name}: {private_content}")
        if path.suffix.casefold() == ".py":
            findings.extend(_import_violations(data, name))
    return findings
