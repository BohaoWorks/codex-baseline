import contextlib
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import shutil
import stat
import tomllib
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from codex_baseline.cli import main
from codex_baseline.core import (
    BaselineError, checked_path, compare_config, export_baseline, inspect_data,
    load_baseline, MAX_INPUT_BYTES, parse_config, render_config, validated,
)
from codex_baseline.policy import CODEX_VERSION, RULES, valid_value


SHARED = '''model = "example-model"
model_reasoning_effort = "high"
approval_policy = "on-request"
sandbox_mode = "workspace-write"
file_opener = "vscode"
[sandbox_workspace_write]
network_access = false
writable_roots = ["/synthetic/source/项目"]
'''


class BaselineTests(unittest.TestCase):
    def setUp(self):
        # Python 3.14's Windows 0o700 temp-directory ACL is incompatible with
        # some restricted tokens. Synthetic test data stays in this checkout.
        work = Path(__file__).resolve().parents[1] / "work"
        work.mkdir(exist_ok=True)
        self.root = work / ("tests-" + uuid4().hex)
        self.root.mkdir()
        self.config = self.put("shared.toml", SHARED)
        self.baseline = self.root / "baseline"

    def tearDown(self):
        work = Path(__file__).resolve().parents[1] / "work"
        if self.root.parent != work or not self.root.name.startswith("tests-"):
            raise RuntimeError("refusing cleanup outside the test workspace")
        shutil.rmtree(self.root)

    def put(self, name, text):
        target = self.root / name
        target.write_text(text, encoding="utf-8")
        return target

    def export(self):
        return export_baseline(self.config, CODEX_VERSION, self.baseline)

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main([str(arg) for arg in args])
        return status, stdout.getvalue(), stderr.getvalue()

    def test_inspect_classifies_without_values(self):
        report = inspect_data(parse_config(self.config))
        self.assertTrue(report["accepted"])
        categories = {field["field"]: field["category"] for field in report["fields"]}
        self.assertEqual(categories["file_opener"], "machine-local")
        self.assertEqual(categories["sandbox_workspace_write.writable_roots"], "machine-local")
        self.assertEqual(categories["approval_policy"], "portable")
        status, output, _ = self.invoke("inspect", "--config", self.config, "--codex-version", CODEX_VERSION)
        self.assertEqual(status, 0)
        self.assertNotIn("synthetic/source", output)
        self.assertNotIn("example-model", output)

    def test_export_excludes_machine_paths_and_has_no_source_metadata(self):
        result = self.export()
        self.assertEqual(result["machine_local_fields_excluded"], 2)
        combined = b"".join(path.read_bytes() for path in self.baseline.iterdir())
        self.assertNotIn(b"synthetic/source", combined)
        self.assertNotIn(str(self.root).encode(), combined)
        manifest = json.loads((self.baseline / "manifest.json").read_bytes())
        self.assertNotIn("created_at", manifest)
        self.assertEqual(set(manifest["files"]), {"baseline.toml"})

    def test_export_is_byte_deterministic_across_input_order_and_directory(self):
        self.export()
        second = self.root / "second"
        reordered = self.put("reordered.toml", '''sandbox_mode = "workspace-write"
approval_policy = "on-request"
model_reasoning_effort = "high"
model = "example-model"
[sandbox_workspace_write]
network_access = false
''')
        export_baseline(reordered, CODEX_VERSION, second)
        for name in ("baseline.toml", "manifest.json"):
            self.assertEqual((self.baseline / name).read_bytes(), (second / name).read_bytes())

    def test_overlay_precedence_is_per_field_and_arrays_replace(self):
        self.export()
        overlay = self.put("overlay.toml", '''model_reasoning_effort = "low"
file_opener = "cursor"
[sandbox_workspace_write]
writable_roots = ["C:/synthetic/target/项目", "/synthetic/second"]
''')
        output = self.root / "rendered"
        render_config(self.baseline, overlay, output)
        result = parse_config(output / "config.toml")
        self.assertEqual(result["model_reasoning_effort"], "low")
        self.assertEqual(result["model"], "example-model")
        self.assertFalse(result["sandbox_workspace_write"]["network_access"])
        self.assertEqual(result["sandbox_workspace_write"]["writable_roots"], ["C:/synthetic/target/项目", "/synthetic/second"])
        origins = json.loads((output / "manifest.json").read_bytes())["origins"]
        self.assertEqual(origins["model_reasoning_effort"], "overlay")
        self.assertEqual(origins["sandbox_workspace_write.network_access"], "baseline")

    def test_unicode_filenames_and_roots_round_trip(self):
        self.export()
        overlay = self.put("机器差异.toml", '[sandbox_workspace_write]\nwritable_roots = ["/synthetic/项目/研发", "D:/团队/项目"]\n')
        output = self.root / "待审核"
        render_config(self.baseline, overlay, output)
        self.assertEqual(compare_config(self.baseline, overlay, output / "config.toml")["differences"], [])

    def test_render_is_deterministic(self):
        self.export()
        for name in ("a", "b"):
            render_config(self.baseline, None, self.root / name)
        for name in ("config.toml", "manifest.json"):
            self.assertEqual((self.root / "a" / name).read_bytes(), (self.root / "b" / name).read_bytes())

    def test_compare_explains_drift_and_redacts_machine_local_values(self):
        self.export()
        overlay = self.put("local.toml", 'file_opener = "cursor"\n[sandbox_workspace_write]\nwritable_roots = ["/synthetic/expected"]\n')
        actual = self.put("actual.toml", SHARED.replace('"high"', '"low"'))
        result = compare_config(self.baseline, overlay, actual)
        fields = {item["field"]: item for item in result["differences"]}
        self.assertEqual(fields["model_reasoning_effort"]["expected_source"], "baseline")
        self.assertEqual(fields["model_reasoning_effort"]["expected"], "high")
        self.assertEqual(fields["file_opener"]["expected_source"], "overlay")
        self.assertNotIn("synthetic/expected", json.dumps(result))
        self.assertNotIn("synthetic/source", json.dumps(result))

    def test_compare_exit_codes_clean_and_drift(self):
        self.export()
        render_config(self.baseline, None, self.root / "output")
        args = ("compare", "--baseline", self.baseline, "--config")
        self.assertEqual(self.invoke(*args, self.root / "output" / "config.toml")[0], 0)
        self.assertEqual(self.invoke(*args, self.config)[0], 1)

    def test_missing_and_unexpected_fields_are_distinguished(self):
        self.export()
        actual = self.put("actual.toml", 'model = "example-model"\nhide_agent_reasoning = true\n')
        differences = {item["field"]: item for item in compare_config(self.baseline, None, actual)["differences"]}
        self.assertEqual(differences["approval_policy"]["change"], "missing")
        self.assertEqual(differences["hide_agent_reasoning"]["change"], "unexpected")

    def test_rejects_unknown_top_level_nested_and_ambiguous_dotted_keys(self):
        cases = ['mystery = true', '[sandbox_workspace_write]\nmystery = true', '"sandbox_workspace_write.network_access" = true']
        for index, text in enumerate(cases):
            with self.subTest(text=text):
                config = self.put(f"bad-{index}.toml", text)
                output = self.root / f"out-{index}"
                with self.assertRaises(BaselineError):
                    export_baseline(config, CODEX_VERSION, output)
                self.assertFalse(output.exists())

    def test_unknown_names_are_never_echoed(self):
        marker = "untrusted-field-DO-NOT-ECHO"
        config = self.put("unknown.toml", f'"{marker}" = "private-value"\n')
        status, output, error = self.invoke("inspect", "--config", config, "--codex-version", CODEX_VERSION)
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(output)["unknown_count"], 1)
        self.assertNotIn(marker, output + error)
        self.assertNotIn("private-value", output + error)

    def test_blocked_sections_are_refused_and_only_known_names_reported(self):
        config = self.put("blocked.toml", 'model = "example-model"\n[mcp_servers.private_name]\ncommand = "private-command"\n')
        status, output, error = self.invoke("inspect", "--config", config, "--codex-version", CODEX_VERSION)
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(output)["blocked_count"], 1)
        self.assertIn('"mcp_servers"', output)
        self.assertNotIn("private_name", output + error)
        self.assertNotIn("private-command", output + error)
        with self.assertRaises(BaselineError):
            export_baseline(config, CODEX_VERSION, self.baseline)

    def test_credential_urls_and_query_tokens_refuse_even_in_blocked_sections(self):
        urls = ["https://fake-user:fake-password@example.invalid", "https://example.invalid?api_key=fake", "https://example.invalid?token=fake", "https://example.invalid?signature=fake"]
        for index, url in enumerate(urls):
            with self.subTest(index=index):
                config = self.put("credentials.toml", f'[mcp_servers.synthetic]\nurl = "{url}"\n')
                status, output, error = self.invoke("inspect", "--config", config, "--codex-version", CODEX_VERSION)
                self.assertEqual(status, 2)
                self.assertTrue(json.loads(output)["sensitive_material_detected"])
                self.assertNotIn(url, output + error)
                with self.assertRaises(BaselineError):
                    export_baseline(config, CODEX_VERSION, self.baseline)
        self.assertFalse(self.baseline.exists())

    def test_token_like_model_is_refused_without_echoing(self):
        fake = "sk-" + "synthetic-test-value"
        config = self.put("token.toml", f'model = "{fake}"\n')
        for command in ("inspect", "export"):
            args = [command, "--config", config, "--codex-version", CODEX_VERSION]
            if command == "export":
                args.extend(["--out", self.baseline])
            status, output, error = self.invoke(*args)
            self.assertEqual(status, 2)
            self.assertNotIn(fake, output + error)
        self.assertFalse(self.baseline.exists())

    def test_invalid_toml_and_utf8_do_not_leak_parser_contents(self):
        config = self.put("broken.toml", '"PRIVATE-PARSER-MARKER" = [')
        config2 = self.root / "broken-utf8.toml"
        config2.write_bytes(b"\xff\xfe")
        for path in (config, config2):
            status, output, error = self.invoke("inspect", "--config", path, "--codex-version", CODEX_VERSION)
            self.assertEqual(status, 2)
            self.assertNotIn("PRIVATE-PARSER-MARKER", output + error)
            self.assertNotIn(str(self.root), output + error)

    def test_wrong_versions_are_refused_before_reading(self):
        for version in ("0.154.0", "latest", "0.159.3-PRIVATE-MARKER"):
            status, output, error = self.invoke("inspect", "--config", self.root / "missing.toml", "--codex-version", version)
            self.assertEqual(status, 2)
            self.assertNotIn("PRIVATE-MARKER", output + error)

    def test_strict_values_and_boolean_types(self):
        for key, value in [(('hide_agent_reasoning',), 1), (('sandbox_mode',), "anything"), (('approval_policy',), "untrusted"), (('approval_policy',), {"granular": {"rules": True}}), (('model',), "https://example.invalid"), (('file_opener',), "custom")]:
            with self.subTest(key=key, value=value):
                self.assertFalse(valid_value(RULES[key], value))
        self.assertFalse(inspect_data({"approval_policy": {"granular": {"unknown": True}}})["accepted"])

    def test_writable_roots_reject_traversal_relative_variables_urls_and_ads(self):
        rule = RULES[("sandbox_workspace_write", "writable_roots")]
        for root in ("relative", "../escape", "/safe/../escape", "C:/safe/../escape", "C:relative", "~/work", "/safe/$USER", "C:/%USER%", "https://example.invalid", "C:/file:stream", "/safe/\x7f"):
            with self.subTest(root=root):
                self.assertFalse(valid_value(rule, [root]))

    def test_output_refuses_existing_file_directory_and_hidden_entries(self):
        self.export()
        before = {path.name: path.read_bytes() for path in self.baseline.iterdir()}
        with self.assertRaises(BaselineError):
            self.export()
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.baseline.iterdir()})
        for output in (self.config, self.root / "occupied"):
            if output != self.config:
                output.mkdir()
                (output / ".hidden").write_bytes(b"preserve")
            with self.assertRaises(BaselineError):
                export_baseline(self.config, CODEX_VERSION, output)

    def test_existing_empty_directory_is_allowed(self):
        self.baseline.mkdir()
        self.export()
        self.assertTrue((self.baseline / "manifest.json").is_file())

    def test_missing_output_parent_is_not_created(self):
        with self.assertRaises(BaselineError):
            export_baseline(self.config, CODEX_VERSION, self.root / "missing" / "child")
        self.assertFalse((self.root / "missing").exists())

    def test_path_traversal_is_rejected_for_io(self):
        with self.assertRaises(BaselineError):
            export_baseline(self.config, CODEX_VERSION, self.root / "unused" / ".." / "out")
        with self.assertRaises(BaselineError):
            parse_config(self.root / "unused" / ".." / "shared.toml")
        with self.assertRaises(BaselineError):
            checked_path("synthetic\\..\\escape.toml")

    def test_no_codex_or_agents_home_writes(self):
        for component in (".codex", ".agents"):
            directory = self.root / component
            directory.mkdir()
            with self.assertRaises(BaselineError):
                export_baseline(self.config, CODEX_VERSION, directory / "out")
            self.assertEqual(list(directory.iterdir()), [])

    def test_home_output_root_is_refused(self):
        directory = self.root / "synthetic-home"
        directory.mkdir()
        with patch.dict(os.environ, {"HOME": str(directory), "USERPROFILE": str(directory), "CODEX_HOME": str(directory)}):
            with self.assertRaises(BaselineError):
                export_baseline(self.config, CODEX_VERSION, directory)

    def test_custom_codex_home_descendants_are_refused(self):
        directory = self.root / "custom-runtime-home"
        directory.mkdir()
        with patch.dict(os.environ, {"CODEX_HOME": str(directory)}):
            with self.assertRaises(BaselineError):
                export_baseline(self.config, CODEX_VERSION, directory / "review")
        self.assertEqual(list(directory.iterdir()), [])
        with patch.dict(os.environ, {"CODEX_HOME": str(directory / "unused" / "..")} ):
            with self.assertRaises(BaselineError):
                export_baseline(self.config, CODEX_VERSION, directory / "review")

    def test_symlinked_output_leaf_and_dangling_link_are_refused(self):
        directory = self.root / "outside"
        directory.mkdir()
        for target in (directory, self.root / "missing-target"):
            link = self.root / ("link-" + target.name)
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("symlink privilege unavailable")
            with self.assertRaises(BaselineError):
                export_baseline(self.config, CODEX_VERSION, link)
        self.assertEqual(list(directory.iterdir()), [])

    def test_compiler_never_calls_network_or_subprocess(self):
        with patch("socket.socket", side_effect=AssertionError("network attempted")), \
             patch("subprocess.Popen", side_effect=AssertionError("process attempted")):
            self.export()
            render_config(self.baseline, None, self.root / "review")
            self.assertTrue(compare_config(self.baseline, None, self.root / "review/config.toml")["matches"])

    def test_auth_sessions_and_database_inputs_are_never_read(self):
        for name in ("auth.json", "auth.toml", "sessions", "state.sqlite", "history.jsonl"):
            path = self.root / name
            with patch("codex_baseline.core.os.open") as open_file:
                with self.assertRaises(BaselineError):
                    parse_config(path)
                open_file.assert_not_called()
        directory = self.root / "sessions"
        directory.mkdir()
        nested = directory / "config.toml"
        nested.write_text(SHARED, encoding="utf-8")
        with self.assertRaises(BaselineError):
            parse_config(nested)

    def test_directories_and_oversized_files_are_refused(self):
        directory = self.root / "directory.toml"
        directory.mkdir()
        with self.assertRaises(BaselineError):
            parse_config(directory)
        huge = self.root / "huge.toml"
        huge.write_bytes(b"#" + b"x" * MAX_INPUT_BYTES)
        with self.assertRaises(BaselineError):
            parse_config(huge)

    def test_hard_link_inputs_are_refused(self):
        alias = self.root / "alias.toml"
        try:
            os.link(self.config, alias)
        except OSError:
            self.skipTest("filesystem does not support hard links")
        with self.assertRaises(BaselineError):
            parse_config(alias)

    def test_symlinked_input_output_and_ancestor_escape_are_refused(self):
        link = self.root / "link.toml"
        try:
            link.symlink_to(self.config)
        except OSError:
            self.skipTest("symlink privilege unavailable; reparse-point branch tested separately")
        with self.assertRaises(BaselineError):
            parse_config(link)
        external = self.root / "external"
        external.mkdir()
        ancestor = self.root / "alias-dir"
        ancestor.symlink_to(external, target_is_directory=True)
        with self.assertRaises(BaselineError):
            export_baseline(self.config, CODEX_VERSION, ancestor / "out")
        self.assertEqual(list(external.iterdir()), [])

    def test_windows_junction_attributes_are_refused(self):
        fake = SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        with patch("pathlib.Path.lstat", return_value=fake):
            with self.assertRaisesRegex(BaselineError, "reparse"):
                checked_path(self.root / "junction" / "out")

    def test_manifest_hash_policy_unknown_fields_and_names_are_verified(self):
        self.export()
        manifest_path = self.baseline / "manifest.json"
        original = json.loads(manifest_path.read_bytes())
        mutations = [
            {**original, "files": {"../escape.toml": "0" * 64}},
            {**original, "files": {"baseline.toml": "0" * 64}},
            {**original, "policy_id": "other"},
            {**original, "codex_version": "0.1.0"},
            {**original, "schema_commit": "0" * 40},
            {**original, "unknown": "PRIVATE-MARKER"},
        ]
        for manifest in mutations:
            with self.subTest(manifest=manifest):
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(BaselineError):
                    load_baseline(self.baseline)
        manifest_path.write_text('{"format":"one","format":"two"}', encoding="utf-8")
        with self.assertRaises(BaselineError):
            load_baseline(self.baseline)

    def test_tampered_baseline_and_extra_files_are_refused(self):
        self.export()
        path = self.baseline / "baseline.toml"
        original = path.read_bytes()
        path.write_bytes(original + b"# changed\n")
        with self.assertRaises(BaselineError):
            load_baseline(self.baseline)
        path.write_bytes(original)
        (self.baseline / "extra.txt").write_text("not read", encoding="utf-8")
        with self.assertRaises(BaselineError):
            load_baseline(self.baseline)

    def test_machine_local_field_in_a_rehashed_baseline_is_refused(self):
        self.export()
        path = self.baseline / "baseline.toml"
        # Place at top level to preserve valid TOML, before any table.
        content = b'file_opener = "cursor"\n' + path.read_bytes()
        path.write_bytes(content)
        manifest_path = self.baseline / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["files"]["baseline.toml"] = sha256(content).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(BaselineError, "machine-local"):
            load_baseline(self.baseline)

    def test_unknown_overlay_does_not_create_output(self):
        self.export()
        overlay = self.put("bad-overlay.toml", '[sandbox_workspace_write]\nunknown = true\n')
        output = self.root / "rendered"
        with self.assertRaises(BaselineError):
            render_config(self.baseline, overlay, output)
        self.assertFalse(output.exists())

    def test_empty_or_machine_only_export_is_refused(self):
        for text in ("", 'file_opener = "cursor"\n'):
            config = self.put("empty.toml", text)
            with self.assertRaises(BaselineError):
                export_baseline(config, CODEX_VERSION, self.baseline)

    def test_structural_limit_is_refused(self):
        config = self.put("deep.toml", '"' + '"."'.join(["unknown"] * 20) + '" = true\n')
        with self.assertRaises(BaselineError):
            export_baseline(config, CODEX_VERSION, self.baseline)

    def test_policy_lists_pinned_sources(self):
        status, output, _ = self.invoke("policy")
        data = json.loads(output)
        self.assertEqual(status, 0)
        self.assertEqual(data["codex_version"], CODEX_VERSION)
        self.assertEqual(len(data["fields"]), 14)
        self.assertEqual(len(data["schema_commit"]), 40)


if __name__ == "__main__":
    unittest.main()
