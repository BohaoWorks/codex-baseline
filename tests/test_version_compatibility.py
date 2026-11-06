"""Explicit pinned-version support without changing existing bundle bytes."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from codex_baseline.cli import main
from codex_baseline.core import export_baseline, render_config, compare_config, load_baseline
from codex_baseline.policy import CODEX_VERSION, POLICY_ID, SCHEMA_COMMIT

NEW = '0.166.0'
NEW_POLICY = 'codex-cli-0.166.0-small-v1'
NEW_COMMIT = '6ff1e1ca3b30fc8b914720681fcf5fe62e95f856'


class VersionCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.checkout = Path(__file__).resolve().parents[1]
        work = self.checkout / 'work'
        work.mkdir(exist_ok=True)
        self.root = work / ('version-tests-' + uuid4().hex)
        self.root.mkdir()
        self.fixture = Path(__file__).parent / 'fixtures' / 'version-0.159.3'
        self.source = self.root / 'shared.toml'
        self.source.write_bytes((self.fixture / 'shared.toml').read_bytes())
        self.overlay = self.root / 'overlay.toml'
        self.overlay.write_bytes((self.fixture / 'overlay.toml').read_bytes())

    def tearDown(self):
        shutil.rmtree(self.root)

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main([str(arg) for arg in args])
        return status, out.getvalue(), err.getvalue()

    def new_baseline(self):
        baseline = self.root / 'new-baseline'
        status, out, err = self.invoke('export', '--config', self.source, '--codex-version', NEW, '--out', baseline)
        self.assertEqual(status, 0, err)
        self.assertEqual(json.loads(out)['policy_id'], NEW_POLICY)
        return baseline

    def test_old_default_constants_and_bundle_bytes_are_preserved(self):
        self.assertEqual(CODEX_VERSION, '0.159.3')
        self.assertEqual(POLICY_ID, 'codex-cli-0.159.3-small-v1')
        self.assertEqual(SCHEMA_COMMIT, '01fc69f4026735edfdf6789820549727a4867b11')
        baseline, rendered = self.root / 'old-baseline', self.root / 'old-rendered'
        export_baseline(self.source, CODEX_VERSION, baseline)
        render_config(baseline, self.overlay, rendered)
        for kind, directory in [('baseline', baseline), ('rendered', rendered)]:
            for expected in (self.fixture / kind).iterdir():
                self.assertEqual((directory / expected.name).read_bytes(), expected.read_bytes())
        self.assertEqual(len(load_baseline(baseline)), 2)
        self.assertTrue(compare_config(baseline, self.overlay, rendered / 'config.toml')['matches'])

    def test_new_inspect_and_policy_report_correct_evidence(self):
        status, out, err = self.invoke('inspect', '--config', self.source, '--codex-version', NEW)
        self.assertEqual(status, 0, err)
        self.assertEqual(json.loads(out)['codex_version'], NEW)
        self.assertEqual(json.loads(out)['policy_id'], NEW_POLICY)
        status, out, err = self.invoke('policy', '--codex-version', NEW)
        self.assertEqual(status, 0, err)
        report = json.loads(out)
        self.assertEqual(report['codex_version'], NEW)
        self.assertEqual(report['policy_id'], NEW_POLICY)
        self.assertEqual(report['schema_commit'], NEW_COMMIT)
        self.assertEqual(report['schema_blob'], '0e741b619f29ca531575accba1a2d6d18ebc7403')
        self.assertIn(NEW_COMMIT, report['schema_url'])
        self.assertEqual(len(report['fields']), 14)

    def test_policy_without_version_keeps_old_default(self):
        status, out, err = self.invoke('policy')
        self.assertEqual(status, 0, err)
        self.assertEqual(json.loads(out)['codex_version'], '0.159.3')

    def test_new_export_render_and_compare_keep_version_provenance(self):
        baseline = self.new_baseline()
        manifest = json.loads((baseline / 'manifest.json').read_bytes())
        self.assertEqual((manifest['codex_version'], manifest['policy_id'], manifest['schema_commit']), (NEW, NEW_POLICY, NEW_COMMIT))
        rendered = self.root / 'new-rendered'
        status, out, err = self.invoke('render', '--baseline', baseline, '--overlay', self.overlay, '--out', rendered)
        self.assertEqual(status, 0, err)
        self.assertEqual(json.loads(out)['policy_id'], NEW_POLICY)
        manifest = json.loads((rendered / 'manifest.json').read_bytes())
        self.assertEqual((manifest['codex_version'], manifest['policy_id']), (NEW, NEW_POLICY))
        status, out, err = self.invoke('compare', '--baseline', baseline, '--overlay', self.overlay, '--config', rendered / 'config.toml')
        self.assertEqual(status, 0, err)
        self.assertTrue(json.loads(out)['matches'])
        self.assertEqual((rendered / 'config.toml').read_bytes(), (self.fixture / 'rendered' / 'config.toml').read_bytes())
        self.assertEqual(len(load_baseline(baseline)), 2)

    def test_new_export_is_deterministic(self):
        baseline = self.new_baseline()
        second = self.root / 'second'
        export_baseline(self.source, NEW, second)
        for name in ('baseline.toml', 'manifest.json'):
            self.assertEqual((baseline / name).read_bytes(), (second / name).read_bytes())

    def test_unknown_versions_are_refused_before_file_operations(self):
        for version in ('latest', '0.166', '0.166.1', '0.168.0', '0.166.0-PRIVATE-MARKER'):
            with self.subTest(version=version):
                for command in ('inspect', 'export'):
                    args = [command, '--config', self.root / 'missing.toml', '--codex-version', version]
                    target = self.root / 'must-not-exist'
                    if command == 'export':
                        args += ['--out', target]
                    status, out, err = self.invoke(*args)
                    self.assertEqual(status, 2)
                    self.assertIn('unsupported Codex version', err)
                    self.assertNotIn('PRIVATE-MARKER', err)
                    self.assertFalse(target.exists())

    def test_mixed_policy_manifest_fields_are_refused_without_output(self):
        baseline = self.new_baseline()
        path = baseline / 'manifest.json'
        original = json.loads(path.read_bytes())
        for key, value in [('codex_version', CODEX_VERSION), ('policy_id', POLICY_ID), ('schema_commit', SCHEMA_COMMIT)]:
            with self.subTest(key=key):
                path.write_text(json.dumps({**original, key: value}), encoding='utf-8')
                output = self.root / 'must-not-exist'
                status, out, err = self.invoke('render', '--baseline', baseline, '--out', output)
                self.assertEqual(status, 2)
                self.assertFalse(output.exists())
                self.assertNotIn('Traceback', err)

    def test_malformed_manifest_versions_are_cleanly_refused(self):
        baseline = self.new_baseline()
        path = baseline / 'manifest.json'
        original = json.loads(path.read_bytes())
        for version in (None, [], {}, True, 166, 'latest'):
            with self.subTest(version=version):
                path.write_text(json.dumps({**original, 'codex_version': version}), encoding='utf-8')
                status, out, err = self.invoke('render', '--baseline', baseline, '--out', self.root / 'must-not-exist')
                self.assertEqual(status, 2)
                self.assertNotIn('Traceback', err)
                self.assertFalse((self.root / 'must-not-exist').exists())

    def test_new_version_does_not_widen_supported_fields(self):
        self.source.write_text('model = "example-model"\nnot_a_supported_field = true\n', encoding='utf-8')
        status, out, err = self.invoke('inspect', '--config', self.source, '--codex-version', NEW)
        self.assertEqual(status, 2)
        self.assertTrue(out, 'supported-version inspection must return its structured rejection report')
        report = json.loads(out)
        self.assertEqual(report['unknown_count'], 1)
        self.assertFalse(report['accepted'])
        self.assertNotIn('not_a_supported_field', out)

    def test_new_version_preserves_all_fourteen_field_categories(self):
        self.source.write_text('''model = "example-model"
model_reasoning_effort = "high"
model_reasoning_summary = "concise"
model_verbosity = "medium"
approval_policy = "on-request"
sandbox_mode = "workspace-write"
check_for_update_on_startup = false
hide_agent_reasoning = false
show_raw_agent_reasoning = false
file_opener = "none"
[sandbox_workspace_write]
network_access = false
exclude_slash_tmp = true
exclude_tmpdir_env_var = true
writable_roots = ["/synthetic/project"]
''', encoding='utf-8')
        status, out, err = self.invoke('inspect', '--config', self.source, '--codex-version', NEW)
        self.assertEqual(status, 0, err)
        report = json.loads(out)
        self.assertEqual(len(report['fields']), 14)
        self.assertEqual(sum(field['category'] == 'portable' for field in report['fields']), 12)
        self.assertEqual(sum(field['category'] == 'machine-local' for field in report['fields']), 2)
        baseline = self.new_baseline()
        content = (baseline / 'baseline.toml').read_text(encoding='utf-8')
        self.assertNotIn('/synthetic/project', content)
        self.assertNotIn('file_opener', content)

    def test_new_version_keeps_blocked_section_refusal(self):
        self.source.write_text('model = "example-model"\n[projects]\nsynthetic = {}\n', encoding='utf-8')
        status, out, err = self.invoke('inspect', '--config', self.source, '--codex-version', NEW)
        self.assertEqual(status, 2)
        self.assertTrue(out, 'supported version must report field rejection')
        self.assertEqual(json.loads(out)['blocked_count'], 1)
        status, out, err = self.invoke('export', '--config', self.source, '--codex-version', NEW, '--out', self.root / 'refused')
        self.assertEqual(status, 2)
        self.assertFalse((self.root / 'refused').exists())

    def test_public_merged_config_tuple_shape_for_both_versions(self):
        from codex_baseline.core import merged_config
        for version in (CODEX_VERSION, NEW):
            baseline = self.root / ('baseline-' + version)
            export_baseline(self.source, version, baseline)
            result = merged_config(baseline, self.overlay)
            self.assertEqual(len(result), 3)
            self.assertIsInstance(result[0], dict)
            self.assertIsInstance(result[1], dict)
            self.assertEqual(len(result[2]), 64)

    def test_new_render_is_byte_deterministic(self):
        baseline = self.new_baseline()
        first, second = self.root / 'first-render', self.root / 'second-render'
        render_config(baseline, self.overlay, first)
        render_config(baseline, self.overlay, second)
        for name in ('config.toml', 'manifest.json'):
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

    def test_policy_command_rejects_unknown_versions_without_echoing(self):
        for version in ('latest', '0.166.1', '0.166.0-PRIVATE-MARKER'):
            status, out, err = self.invoke('policy', '--codex-version', version)
            self.assertEqual(status, 2)
            self.assertEqual(out, '')
            self.assertIn('unsupported Codex version', err)
            self.assertNotIn('PRIVATE-MARKER', err)
