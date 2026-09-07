#!/usr/bin/env python3
"""Build a local installation ZIP or prepare a HACS repository, without network I/O."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

DOMAIN = "parro"
SOURCE = Path(__file__).resolve().parents[1]
PLACEHOLDERS = re.compile(
    r"__OWNER__|__REPO__|__CODEOWNER__|YOUR[_ -](?:OWNER|REPO)|example\.com|REPLACE_ME",
    re.I,
)
OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
ROOT_FILES = {
    "README.md",
    "hacs.json",
    ".gitignore",
    "LICENSE",
    "CHANGELOG.md",
    "RELEASE_CHECKLIST.md",
}
CORE_DATA = {"manifest.json", "strings.json", "services.yaml", "icons.json"}
REQUIRED_FILES = {
    "README.md",
    "LICENSE",
    "hacs.json",
    *(
        f"custom_components/parro/{name}"
        for name in (
            "__init__.py",
            "api.py",
            "config_flow.py",
            "const.py",
            "coordinator.py",
            "entity.py",
            "sensor.py",
            "binary_sensor.py",
            "services.py",
            "services.yaml",
            "diagnostics.py",
            "manifest.json",
            "strings.json",
            "translations/en.json",
            "translations/nl.json",
            "brand/icon.png",
        )
    ),
}


def fail(message: str) -> None:
    raise ValueError(message)


def read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        fail(f"Geen gewoon bestand: {path}")
    return path.read_bytes()


def payload(root: Path) -> dict[str, bytes]:
    """Only ship integration runtime files and named public documentation.

    An allowlist prevents inclusion of local tests, handoff notes, dashboard files,
    account fixtures, caches or unrelated root-level files. It cannot replace a
    review of the contents of the allowed files.
    """
    result: dict[str, bytes] = {}
    for name in sorted(ROOT_FILES):
        path = root / name
        if path.exists() or path.is_symlink():
            result[name] = read_regular(path)
    components = root / "custom_components"
    component = components / DOMAIN
    if components.is_symlink() or component.is_symlink() or not component.is_dir():
        fail("custom_components/parro ontbreekt of is een symlink.")
    if {p.name for p in components.iterdir() if p.is_dir() or p.is_symlink()} != {DOMAIN}:
        fail("Er mag precies één integratie in custom_components staan: parro.")
    for path in sorted(component.rglob("*")):
        relative = path.relative_to(component)
        if path.is_symlink():
            fail(f"Symlink niet toegestaan: {relative}")
        if "__pycache__" in relative.parts or path.name == ".DS_Store":
            continue
        if path.is_dir():
            continue
        allowed = (
            (len(relative.parts) == 1 and (path.suffix == ".py" or path.name in CORE_DATA))
            or (
                len(relative.parts) == 2
                and relative.parts[0] == "translations"
                and path.suffix == ".json"
            )
            or (
                len(relative.parts) == 2
                and relative.parts[0] == "brand"
                and path.name
                in {
                    "icon.png",
                    "icon@2x.png",
                    "dark_icon.png",
                    "dark_icon@2x.png",
                    "logo.png",
                    "logo@2x.png",
                }
            )
        )
        if not allowed or re.search(
            r"(?:secret|credential|token|private|reference)", path.name, re.I
        ):
            fail(f"Bestand valt buiten de distributielijst: {relative}")
        result[f"custom_components/{DOMAIN}/{relative.as_posix()}"] = read_regular(path)
    for name in sorted(REQUIRED_FILES):
        if name not in result:
            fail(f"Verplicht distributiebestand ontbreekt: {name}")
    return result


def validate(files: dict[str, bytes], *, release: bool = True) -> None:
    """Check local package structure and, by default, publication metadata."""
    for name, data in files.items():
        if not name.endswith(".png"):
            content = data.decode("utf-8")
            if release and PLACEHOLDERS.search(content):
                fail(f"Publicatieplaceholder gevonden in {name}.")
            if name.endswith(".json"):
                json.loads(content)
    manifest = json.loads(files["custom_components/parro/manifest.json"])
    if not isinstance(manifest, dict):
        fail("Manifest moet een JSON-object zijn.")
    if (
        manifest.get("domain") != DOMAIN
        or not manifest.get("name")
        or not re.fullmatch(r"\d+\.\d+\.\d+(?:[ab]\d+|rc\d+)?", manifest.get("version", ""))
        or manifest.get("config_flow") is not True
    ):
        fail("Manifest vereist domain parro, name, version en config_flow true.")
    if manifest.get("requirements") != ["parro==1.1.0"]:
        fail("De eerste versie vereist de vastgezette SDK parro==1.1.0.")
    if release:
        docs = manifest.get("documentation", "")
        if not re.fullmatch(r"https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+", docs):
            fail("Manifest vereist een concrete GitHub-repository als documentation.")
        if manifest.get("issue_tracker") != docs + "/issues":
            fail("issue_tracker hoort bij dezelfde repository.")
        owners = manifest.get("codeowners")
        if (
            not isinstance(owners, list)
            or not owners
            or any(
                not isinstance(owner, str)
                or not re.fullmatch(r"@[A-Za-z0-9-]+(?:/[A-Za-z0-9_-]+)?", owner)
                for owner in owners
            )
        ):
            fail("Minstens één expliciete GitHub-codeowner is vereist.")
    hacs = json.loads(files["hacs.json"])
    if not isinstance(hacs, dict):
        fail("hacs.json moet een JSON-object zijn.")
    if not hacs.get("name") or hacs.get("content_in_root", False) or hacs.get("zip_release", False):
        fail("hacs.json moet de gewone custom_components-repositoryindeling gebruiken.")
    if hacs.get("homeassistant") != "2026.8.3":
        fail("De eerste versie heeft Home Assistant 2026.8.3 als doelminimum.")


def write_archive(files: dict[str, bytes], output: Path) -> None:
    """Make a reproducible manual-install ZIP and a SHA-256 inventory.

    Exclusive creation refuses existing output, including symlinks. No source
    files are changed and the archive has no absolute or parent-relative paths.
    """
    inventory = output.with_suffix(output.suffix + ".inventory.json")
    if output.exists() or output.is_symlink() or inventory.exists() or inventory.is_symlink():
        fail("ZIP of inventaris bestaat al; kies een nieuwe bestandsnaam.")
    output.parent.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        with output.open("xb") as stream:
            created.append(output)
            with ZipFile(stream, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
                for name, data in sorted(files.items()):
                    entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    entry.create_system = 3
                    entry.external_attr = 0o100644 << 16
                    entry.compress_type = ZIP_DEFLATED
                    archive.writestr(entry, data)
        report = {
            "mode": "local-manual-install",
            "release_ready": False,
            "archive": output.name,
            "sha256": sha256(output.read_bytes()).hexdigest(),
            "files": [
                {"path": name, "bytes": len(data), "sha256": sha256(data).hexdigest()}
                for name, data in sorted(files.items())
            ],
        }
        with inventory.open("x", encoding="utf-8") as stream:
            created.append(inventory)
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=SOURCE, help="Bronmap of bestaande stagingmap"
    )
    parser.add_argument(
        "--output", type=Path, help="Nieuwe lokale stagingmap; mag nog niet bestaan"
    )
    parser.add_argument("--owner", help="Expliciete GitHub-eigenaar (persoon of organisatie)")
    parser.add_argument("--repo", help="Expliciete GitHub-repositorynaam")
    parser.add_argument(
        "--codeowner", action="append", help="Verantwoordelijke GitHub-gebruiker/team; herhaalbaar"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true", help="Releasegereedheid controleren; placeholders falen"
    )
    mode.add_argument(
        "--local-archive",
        type=Path,
        metavar="ZIP",
        help="Handmatige installatie-ZIP; placeholders toegestaan, geen HACS-publicatie",
    )
    args = parser.parse_args(argv)
    try:
        source = args.source.resolve()
        files = payload(source)
        if args.check or args.local_archive:
            if any((args.output, args.owner, args.repo, args.codeowner)):
                fail("--check of --local-archive combineert alleen met --source.")
            validate(files, release=args.check)
            if args.check:
                print(
                    f"Distributiecontrole geslaagd: {len(files)} bestanden. Geen installatie of publicatie uitgevoerd."
                )
            else:
                output = args.local_archive.absolute()
                if output.suffix.lower() != ".zip":
                    fail("De naam voor --local-archive moet eindigen op .zip.")
                write_archive(files, output)
                print(
                    f"Lokale installatie-ZIP klaar: {output} ({len(files)} bestanden), met SHA-256-inventaris."
                )
                print(
                    "Alleen voor handmatige installatie; HACS-publicatiemetadata is niet vrijgegeven of online gecontroleerd."
                )
            return 0
        validate(files, release=False)
        if not args.output or not args.owner or not args.repo or not args.codeowner:
            fail("Voorbereiden vereist --output, --owner, --repo en minstens één --codeowner.")
        if (
            not OWNER.fullmatch(args.owner)
            or not REPO.fullmatch(args.repo)
            or args.repo.endswith(".git")
        ):
            fail("Gebruik alleen een GitHub-eigenaar en repositorynaam, geen URL of .git-suffix.")
        codeowners = list(
            dict.fromkeys(name if name.startswith("@") else "@" + name for name in args.codeowner)
        )
        repository = f"https://github.com/{args.owner}/{args.repo}"
        manifest_key = "custom_components/parro/manifest.json"
        manifest = json.loads(files[manifest_key])
        manifest.update(
            documentation=repository, issue_tracker=repository + "/issues", codeowners=codeowners
        )
        files[manifest_key] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
        for name in files:
            if name.endswith(".md"):
                files[name] = (
                    files[name]
                    .replace(b"__OWNER__", args.owner.encode())
                    .replace(b"__REPO__", args.repo.encode())
                )
        validate(files)
        output = args.output.absolute()
        if output.exists() or output.is_symlink():
            fail(
                "De uitvoermap bestaat al; kies een nieuwe map. Bestaande bestanden worden niet overschreven."
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive mkdir prevents overwriting a folder created during validation.
        output.mkdir()
        try:
            for name, data in files.items():
                destination = output / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                destination.chmod(0o644)
            (output / "scripts").mkdir()
            (output / "scripts/prepare_repository.py").write_bytes(read_regular(Path(__file__)))
            validate(payload(output))
        except Exception:
            shutil.rmtree(output)
            raise
        print(
            f"Lokale staging klaar: {output} ({len(files)} distributiebestanden plus controletool)."
        )
        print(
            "Repository-eigendom en bereikbaarheid zijn niet online gecontroleerd. Er is niets gepubliceerd of geïnstalleerd."
        )
        return 0
    except (ValueError, OSError, UnicodeError, TypeError) as error:
        print(f"Voorbereiding geweigerd: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
