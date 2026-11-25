from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from cad_agent_showcase.disclosure import scan_repository


ROOT = Path(__file__).resolve().parents[1]


class DisclosureBoundaryTests(unittest.TestCase):
    def test_public_tree(self):
        self.assertEqual(scan_repository(ROOT), [])

    @unittest.skipUnless(shutil.which("git"), "Git-index test requires a Git executable")
    def test_git_index_detects_executable_imports_in_demo_and_tools(self):
        cases = (
            ("demo", "import io, OCP.gp\n"),
            ("tools", "from PyMuPDF import open\n"),
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            git = ["git", "-C", str(root)]
            subprocess.run(git + ["init", "--quiet", "--template="], check=True)
            (root / "README.md").write_text("OCP, OCCT, DXF and PDF boundary notes.\n", encoding="utf-8")
            (root / "literal.py").write_text("example = 'import OCP.gp'\n", encoding="utf-8")
            subprocess.run(git + ["add", "--", "README.md", "literal.py"], check=True)
            self.assertEqual(scan_repository(root), [])
            for directory, code in cases:
                with self.subTest(directory=directory):
                    name = f"{directory}/sample.py"
                    path = root / name
                    path.parent.mkdir()
                    path.write_text(code, encoding="utf-8")
                    self.assertEqual(scan_repository(root), [])
                    subprocess.run(git + ["add", "--", name], check=True)
                    self.assertEqual(scan_repository(root), [f"{name}:1: prohibited CAD/media import"])
                    subprocess.run(git + ["rm", "--quiet", "--cached", "--", name], check=True)

    def test_source_archive_also_checks_code_and_private_paths(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "examples").mkdir()
            (root / "examples/probe.py").write_text("from PIL import Image\n", encoding="utf-8")
            host_path = chr(67) + ":/" + "Users" + "/sample/"
            (root / "README.md").write_text(f"Illustrative test fixture {host_path}\n", encoding="utf-8")
            self.assertEqual(scan_repository(root), [
                "README.md: private host path",
                "examples/probe.py:1: prohibited CAD/media import",
            ])

    def test_exact_restricted_name_uses_the_reviewer_inventory(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "README.md").write_text("See prototype_core.py.\n", encoding="utf-8")
            self.assertEqual(scan_repository(root), [])
            self.assertEqual(scan_repository(root, private_filenames={"prototype_core.py"}), [
                "README.md: restricted source filename",
            ])
