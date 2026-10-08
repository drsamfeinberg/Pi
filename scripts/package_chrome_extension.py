"""Create a Chrome Web Store review ZIP with manifest.json at its root."""
from pathlib import Path
import json
import argparse
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FILES = ["manifest.json", "api.js", "bridge.js", "content.js", "popup.js", "popup.html", "popup.css", "reports.json", "launch.js", "workspace.html", "intake.js", "core.js", "vendor/pdf.mjs", "vendor/pdf.worker.mjs", "vendor/LICENSE"]


def package(output: Path) -> Path:
    source = ROOT / "extension"
    manifest = json.loads((source / "manifest.json").read_text())
    icons = sorted(set(manifest.get("icons", {}).values()) | set(manifest["action"].get("default_icon", {}).values()))
    paths = FILES + icons
    for name in paths:
        if not (source / name).is_file():
            raise ValueError(f"Missing package resource: {name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name in paths:
            archive.write(source / name, name)
    with ZipFile(output) as archive:
        assert "manifest.json" in archive.namelist()
        assert archive.testzip() is None
        assert json.loads(archive.read("manifest.json"))["manifest_version"] == 3
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path('/workspace/artifacts/pi-chrome-web-store-review.zip'))
    print(package(parser.parse_args().output))
