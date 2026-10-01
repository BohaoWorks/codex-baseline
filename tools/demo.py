"""Run the complete synthetic demo; no user configuration or network access."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def run(args, label, expected=0):
    result = subprocess.run([sys.executable, "-B", "-m", "codex_baseline", *map(str, args)], cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != expected:
        raise RuntimeError(f"synthetic demo failed at {label}; exit {result.returncode}")
    print("$ " + label)
    return json.loads(result.stdout)


def main():
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    temp = work / ("demo-" + uuid4().hex)
    temp.mkdir()
    try:
        inspect = run(["inspect", "--config", "examples/shared.toml", "--codex-version", "0.159.3"], "codex-baseline inspect --config examples/shared.toml --codex-version 0.159.3")
        print("accepted=true; portable=9; machine-local=2; blocked=0; unknown=0")
        assert inspect["accepted"] and len(inspect["fields"]) == 11
        print()
        export = run(["export", "--config", "examples/shared.toml", "--codex-version", "0.159.3", "--out", temp / "baseline"], "codex-baseline export --config examples/shared.toml --codex-version 0.159.3 --out TEMP/baseline")
        print(f"exported {export['portable_fields']} portable fields; excluded {export['machine_local_fields_excluded']} machine-local fields")
        print("baseline sha256: " + export["sha256"])
        print()
        render = run(["render", "--baseline", temp / "baseline", "--overlay", "examples/mac-overlay.toml", "--out", temp / "review"], "codex-baseline render --baseline TEMP/baseline --overlay examples/mac-overlay.toml --out TEMP/review")
        print(f"rendered {render['fields']} fields; {render['overlay_fields']} came from the overlay")
        print("config.toml + manifest.json created for review; nothing applied")
        print()
        clean = run(["compare", "--baseline", temp / "baseline", "--overlay", "examples/mac-overlay.toml", "--config", temp / "review" / "config.toml"], "codex-baseline compare --baseline TEMP/baseline --overlay examples/mac-overlay.toml --config TEMP/review/config.toml")
        print("matches=true; exit=0")
        assert clean["matches"]
        print()
        drift = run(["compare", "--baseline", temp / "baseline", "--overlay", "examples/mac-overlay.toml", "--config", "examples/drifted.toml"], "codex-baseline compare --baseline TEMP/baseline --overlay examples/mac-overlay.toml --config examples/drifted.toml", expected=1)
        for field in drift["differences"]:
            detail = field.get("values") or f"{field['actual']!r} -> expected {field['expected']!r}"
            print(f"{field['field']}: {field['change']}; source={field['expected_source']}; {detail}")
        print("matches=false; exit=1")
        assert len(drift["differences"]) == 3
    finally:
        if temp.parent != work or not temp.name.startswith("demo-"):
            raise RuntimeError("refusing cleanup outside the demo workspace")
        shutil.rmtree(temp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
