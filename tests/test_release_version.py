from pathlib import Path
import io
import subprocess
import tarfile
import tempfile
import unittest

from tools.verify_release_version import legacy_android_code, validate


class ReleaseVersionTests(unittest.TestCase):
    def test_p4a_historical_code_is_larger_than_short_explicit_code(self):
        self.assertEqual(legacy_android_code('6.5.1', 21), 102160501)
        self.assertGreater(legacy_android_code('7.0.1', 21), 102160501)

    def test_current_release_is_consistent_and_updates_historical_store_version(self):
        result = validate(Path(__file__).resolve().parents[1], 102160501)
        self.assertEqual(result['version'], '7.0.5')
        self.assertEqual(result['version_code'], 102170005)

    def fixture(self, directory, code=102170001, menu='7.0.1'):
        root = Path(directory)
        (root / 'buildozer.spec').write_text('[app]\nversion=7.0.1\nandroid.minapi=21\n'
                                             f'android.numeric_version={code}\n', encoding='utf-8')
        (root / 'frontend_ui.py').write_text(f'VERSION={menu!r}\n', encoding='utf-8')
        (root / 'build.sh').write_text('APP_VERSION="7.0.1"\n', encoding='utf-8')
        return root

    def test_short_code_is_rejected_even_when_version_name_is_new(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'at least'):
                validate(self.fixture(folder, code=70001))

    def test_mismatched_menu_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'disagree'):
                validate(self.fixture(folder, menu='7.0.0'))

    def test_equal_or_higher_store_code_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'exceed'):
                validate(self.fixture(folder), previous_code=102170001)

    def test_windows_source_archive_preserves_linux_shell_line_endings(self):
        root = Path(__file__).resolve().parents[1]
        data = subprocess.check_output(['git', 'archive', '--worktree-attributes', 'HEAD', 'build.sh'], cwd=root)
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            script = archive.extractfile('build.sh').read()
        self.assertNotIn(b'\r', script)


if __name__ == '__main__':
    unittest.main()
