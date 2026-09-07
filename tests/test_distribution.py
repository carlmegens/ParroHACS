"""Distribution tests use synthetic files and never contact a remote repository."""

from __future__ import annotations

import importlib.util
import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare_repository.py"
_SPEC = importlib.util.spec_from_file_location("parro_prepare_repository", _SCRIPT)
assert _SPEC and _SPEC.loader
prepare = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(prepare)


@pytest.fixture
def package_source(tmp_path: Path) -> Path:
    """Create only synthetic source; no real school/account data in fixtures."""
    root = tmp_path / "source"
    for name in prepare.REQUIRED_FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"{}" if path.suffix == ".json" else b"test fixture\n")
    (root / "custom_components/parro/manifest.json").write_text(
        json.dumps(
            {
                "domain": "parro",
                "name": "Parro",
                "version": "0.1.0",
                "config_flow": True,
                "requirements": ["parro==1.1.0"],
                "codeowners": [],
                "documentation": "https://github.com/__OWNER__/__REPO__",
                "issue_tracker": "https://github.com/__OWNER__/__REPO__/issues",
            }
        )
    )
    (root / "hacs.json").write_text(
        json.dumps(
            {
                "name": "Parro",
                "homeassistant": "2026.8.3",
                "content_in_root": False,
            }
        )
    )
    (root / "README.md").write_text("Repository: https://github.com/__OWNER__/__REPO__\n")
    return root


def stage_args(root: Path, output: Path) -> list[str]:
    # These intentionally fictitious names only exercise local string validation.
    return [
        "--source",
        str(root),
        "--output",
        str(output),
        "--owner",
        "test-owner",
        "--repo",
        "test-parro",
        "--codeowner",
        "test-maintainer",
    ]


def test_local_archive_excludes_unrelated_data_and_matches_inventory(package_source, tmp_path):
    (package_source / "HANDOFF.md").write_text("synthetic internal note")
    (package_source / "family.json").write_text('{"synthetic": true}')
    (package_source / "tests").mkdir()
    (package_source / "tests/account.json").write_text('{"synthetic": true}')
    cache = package_source / "custom_components/parro/__pycache__"
    cache.mkdir()
    (cache / "cached.pyc").write_bytes(b"synthetic cache")
    zip_path = tmp_path / "parro-local.zip"

    assert prepare.main(["--source", str(package_source), "--local-archive", str(zip_path)]) == 0
    report = json.loads(zip_path.with_suffix(".zip.inventory.json").read_text())
    assert report["mode"] == "local-manual-install"
    assert report["release_ready"] is False
    assert report["sha256"] == sha256(zip_path.read_bytes()).hexdigest()
    with ZipFile(zip_path) as archive:
        assert set(archive.namelist()) == prepare.REQUIRED_FILES
        assert set(archive.namelist()) == {item["path"] for item in report["files"]}
        for item in report["files"]:
            data = archive.read(item["path"])
            assert item["bytes"] == len(data)
            assert item["sha256"] == sha256(data).hexdigest()
            assert not item["path"].startswith("/")
            assert ".." not in Path(item["path"]).parts


def test_archive_is_reproducible(package_source, tmp_path):
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    for output in (first, second):
        assert prepare.main(["--source", str(package_source), "--local-archive", str(output)]) == 0
    assert first.read_bytes() == second.read_bytes()


def test_release_check_rejects_source_placeholders(package_source, capsys):
    assert prepare.main(["--source", str(package_source), "--check"]) == 1
    assert "Publicatieplaceholder" in capsys.readouterr().err


def test_staging_updates_metadata_without_changing_source(package_source, tmp_path):
    original = (package_source / "custom_components/parro/manifest.json").read_bytes()
    output = tmp_path / "staging"
    assert (
        prepare.main(stage_args(package_source, output) + ["--codeowner", "@test-org/test-team"])
        == 0
    )
    assert prepare.main(["--source", str(output), "--check"]) == 0
    manifest = json.loads((output / "custom_components/parro/manifest.json").read_text())
    assert manifest["documentation"] == "https://github.com/test-owner/test-parro"
    assert manifest["issue_tracker"] == manifest["documentation"] + "/issues"
    assert manifest["codeowners"] == ["@test-maintainer", "@test-org/test-team"]
    assert "__OWNER__" not in (output / "README.md").read_text()
    assert (output / "scripts/prepare_repository.py").read_bytes() == _SCRIPT.read_bytes()
    assert (package_source / "custom_components/parro/manifest.json").read_bytes() == original


@pytest.mark.parametrize(
    "unexpected", ["tokens.json", "photo.jpg", "account.yaml", "nested/client.py"]
)
def test_unexpected_component_files_are_rejected(package_source, tmp_path, unexpected):
    extra = package_source / "custom_components/parro" / unexpected
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_bytes(b"synthetic private fixture")
    output = tmp_path / "out.zip"
    assert prepare.main(["--source", str(package_source), "--local-archive", str(output)]) == 1
    assert not output.exists()


@pytest.mark.parametrize(
    "relative",
    ["README.md", "custom_components/parro/brand/icon.png", "custom_components/parro/linked"],
)
def test_symlink_payload_is_rejected(package_source, tmp_path, relative):
    target = tmp_path / "outside"
    target.write_text("synthetic external fixture")
    link = package_source / relative
    link.unlink(missing_ok=True)
    link.symlink_to(target)
    assert (
        prepare.main(
            ["--source", str(package_source), "--local-archive", str(tmp_path / "out.zip")]
        )
        == 1
    )


def test_second_integration_is_rejected(package_source, tmp_path):
    (package_source / "custom_components/unrelated").mkdir()
    assert prepare.main(stage_args(package_source, tmp_path / "output")) == 1


def test_missing_runtime_file_is_rejected(package_source, tmp_path):
    (package_source / "custom_components/parro/api.py").unlink()
    assert (
        prepare.main(
            ["--source", str(package_source), "--local-archive", str(tmp_path / "out.zip")]
        )
        == 1
    )


@pytest.mark.parametrize("kind", ["directory", "zip", "inventory", "symlink"])
def test_existing_output_is_not_overwritten(package_source, tmp_path, kind):
    output = tmp_path / "output.zip"
    preserved = b"existing data"
    if kind == "directory":
        output.mkdir()
        marker = output / "keep.txt"
        marker.write_bytes(preserved)
        assert prepare.main(stage_args(package_source, output)) == 1
        assert marker.read_bytes() == preserved
        return
    if kind == "inventory":
        existing = output.with_suffix(".zip.inventory.json")
    else:
        existing = output
    if kind == "symlink":
        target = tmp_path / "keep.txt"
        target.write_bytes(preserved)
        existing.symlink_to(target)
    else:
        existing.write_bytes(preserved)
    assert prepare.main(["--source", str(package_source), "--local-archive", str(output)]) == 1
    assert existing.read_bytes() == preserved


@pytest.mark.parametrize(
    "field,value",
    [
        ("--owner", "https://github.com/test"),
        ("--repo", "bad.git"),
        ("--repo", "../outside"),
        ("--codeowner", "bad owner"),
    ],
)
def test_invalid_publication_fields_leave_no_staging(package_source, tmp_path, field, value):
    output = tmp_path / "staging"
    args = stage_args(package_source, output)
    args[args.index(field) + 1] = value
    assert prepare.main(args) == 1
    assert not output.exists()


@pytest.mark.parametrize(
    "field,value",
    [("version", ""), ("domain", "wrong"), ("requirements", ["parro"]), ("config_flow", False)],
)
def test_invalid_runtime_manifest_rejected_in_local_mode(package_source, tmp_path, field, value):
    path = package_source / "custom_components/parro/manifest.json"
    manifest = json.loads(path.read_text())
    manifest[field] = value
    path.write_text(json.dumps(manifest))
    assert (
        prepare.main(
            ["--source", str(package_source), "--local-archive", str(tmp_path / "out.zip")]
        )
        == 1
    )


def test_release_rejects_empty_codeowners_after_staging(package_source, tmp_path):
    output = tmp_path / "staging"
    assert prepare.main(stage_args(package_source, output)) == 0
    path = output / "custom_components/parro/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["codeowners"] = []
    path.write_text(json.dumps(manifest))
    assert prepare.main(["--source", str(output), "--check"]) == 1


def test_release_rejects_placeholder_in_documentation_after_staging(package_source, tmp_path):
    output = tmp_path / "staging"
    assert prepare.main(stage_args(package_source, output)) == 0
    (output / "README.md").write_text("Unresolved __REPO__")
    assert prepare.main(["--source", str(output), "--check"]) == 1


def test_local_archive_does_not_accept_publication_options(package_source, tmp_path):
    assert (
        prepare.main(
            [
                "--source",
                str(package_source),
                "--local-archive",
                str(tmp_path / "out.zip"),
                "--owner",
                "test-owner",
            ]
        )
        == 1
    )


@pytest.mark.parametrize(
    "relative,content",
    [
        ("hacs.json", "[]"),
        ("custom_components/parro/manifest.json", "null"),
        ("custom_components/parro/strings.json", "invalid JSON"),
    ],
)
def test_malformed_metadata_fails_cleanly(package_source, tmp_path, relative, content):
    (package_source / relative).write_text(content)
    assert prepare.main(stage_args(package_source, tmp_path / "staging")) == 1
    assert (
        prepare.main(
            ["--source", str(package_source), "--local-archive", str(tmp_path / "out.zip")]
        )
        == 1
    )
