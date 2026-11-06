"""The installed-test guard must distinguish installed and checkout imports."""
import importlib.util
import importlib.metadata
from pathlib import Path
import shutil
from uuid import uuid4
import unittest


class InstalledCheckTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).resolve().parents[1] / 'work'
        work.mkdir(exist_ok=True)
        self.root = work / ('installed-guard-' + uuid4().hex)
        self.root.mkdir()

    def tearDown(self):
        shutil.rmtree(self.root)

    def helper(self):
        script = Path(__file__).resolve().parents[1] / 'tools' / 'check_installed.py'
        self.assertTrue(script.is_file(), 'installed-package verification helper is missing')
        spec = importlib.util.spec_from_file_location('installed_check_tool', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def guard(self):
        return self.helper().validate_origin

    def test_accepts_installed_package_outside_checkout(self):
        guard = self.guard()
        root = self.root
        guard(root/'venv/site-packages/codex_baseline/__init__.py', root/'checkout', root/'venv/site-packages')

    def test_rejects_checkout_import_even_with_matching_metadata_root(self):
        guard = self.guard()
        root = self.root
        with self.assertRaisesRegex(RuntimeError, 'checkout'):
            guard(root/'codex_baseline/__init__.py', root, root)

    def test_rejects_import_outside_installed_distribution(self):
        guard = self.guard()
        root = self.root
        with self.assertRaisesRegex(RuntimeError, 'distribution'):
            guard(root/'other/codex_baseline/__init__.py', root/'checkout', root/'site-packages')

    def test_allows_venv_inside_checkout(self):
        guard = self.guard()
        root = self.root
        guard(root/'.venv/site-packages/codex_baseline/__init__.py', root, root/'.venv/site-packages')

    def distribution(self, wheel=True, editable=False):
        metadata = self.root / 'codex_baseline-0.1.0.dist-info'
        metadata.mkdir()
        (metadata / 'METADATA').write_text('Name: codex-baseline\nVersion: 0.1.0\n', encoding='utf-8')
        if wheel:
            (metadata / 'WHEEL').write_text('Wheel-Version: 1.0\n', encoding='utf-8')
            (metadata / 'RECORD').write_text('codex_baseline/__init__.py,,\n', encoding='utf-8')
        if editable:
            (metadata / 'direct_url.json').write_text('{"dir_info":{"editable":true}}', encoding='utf-8')
        return importlib.metadata.PathDistribution(metadata)

    def test_requires_wheel_metadata(self):
        helper = self.helper()
        self.assertTrue(hasattr(helper, 'validate_distribution'), 'wheel installation guard is missing')
        with self.assertRaisesRegex(RuntimeError, 'wheel'):
            helper.validate_distribution(self.distribution(wheel=False))

    def test_rejects_editable_wheel_metadata(self):
        helper = self.helper()
        self.assertTrue(hasattr(helper, 'validate_distribution'), 'wheel installation guard is missing')
        with self.assertRaisesRegex(RuntimeError, 'editable'):
            helper.validate_distribution(self.distribution(editable=True))

    def test_accepts_noneditable_wheel_metadata(self):
        helper = self.helper()
        self.assertTrue(hasattr(helper, 'validate_distribution'), 'wheel installation guard is missing')
        helper.validate_distribution(self.distribution())

    def test_rejects_symlinked_checkout_package(self):
        guard = self.guard()
        target = self.root / 'other' / 'codex_baseline'
        target.mkdir(parents=True)
        source = self.root / 'checkout'
        source.mkdir()
        try:
            (source / 'codex_baseline').symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('host does not permit directory symlinks')
        with self.assertRaisesRegex(RuntimeError, 'checkout'):
            guard(target / '__init__.py', source, target.parent)
