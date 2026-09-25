"""Audit the exact public files, then optionally stage only the static site."""
import argparse
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

from common import ROOT, OUT, BUILD, read_json, sha256, write_json
from package_release import check_links, source_copy
from publication import audit_file, config

ROOT_FILES = {".gitattributes", ".gitignore", "README.md", "README.en.md", "NOTICE", "requirements.txt", "package.json", "package-lock.json"}
SOURCE_DIRS = {"scripts", "tests", "web", "design"}
SITE_DIRS = {"assets", "cad", "coupons", "data", "docs", "licenses", "media", "plates", "stl", "validation"}
FORBIDDEN_PARTS = {".venv", "node_modules", "__pycache__", ".git", ".copilot", ".local", "build", "attachments"}


def allowed_path(name):
    p = Path(name)
    if p.is_absolute() or ".." in p.parts or any(part in FORBIDDEN_PARTS for part in p.parts):
        return False
    if name in ROOT_FILES or name == ".github/workflows/pages.yml":
        return True
    if p.parts[0] in SOURCE_DIRS and p.suffix in {".py", ".mjs", ".js", ".json", ".css", ".html"}:
        return True
    if name == "dist/release-receipt.json":
        return True
    if p.parts[:2] == ("dist", "octodesk-r1"):
        relative = p.parts[2:]
        if relative in (("index.html",), ("checksums.sha256",)):
            return True
        return len(relative) > 1 and relative[0] in SITE_DIRS and p.suffix in {
            ".js", ".css", ".json", ".csv", ".html", ".svg", ".png", ".mp4", ".webm", ".srt",
            ".vtt", ".pdf", ".FCStd", ".step", ".blend", ".stl", ".3mf", ".txt"}
    return False


def candidates(staged):
    if staged:
        output = subprocess.check_output(["git", "ls-files", "--cached", "-z"], cwd=ROOT)
        names = [name.decode() for name in output.split(b"\0") if name]
        for name in names:
            assert allowed_path(name), f"Unapproved staged path: {name}"
            blob = subprocess.check_output(["git", "show", f":{name}"], cwd=ROOT)
            assert hashlib.sha256(blob).hexdigest() == sha256(ROOT / name), f"Staged/disk mismatch: {name}"
        return [ROOT / name for name in names]
    files = [ROOT / name for name in ROOT_FILES]
    files.append(ROOT / ".github" / "workflows" / "pages.yml")
    for directory in SOURCE_DIRS:
        files.extend(p for p in (ROOT / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    files.extend(p for p in OUT.rglob("*") if p.is_file() and "source" not in p.relative_to(OUT).parts)
    files.append(ROOT / "dist" / "release-receipt.json")
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--stage", action="store_true")
    args = parser.parse_args()
    source_copy()
    files = candidates(args.staged)
    for file in files:
        name = file.relative_to(ROOT).as_posix()
        assert allowed_path(name), f"Unapproved public path: {name}"
        assert file.stat().st_size < 100 * 1024 * 1024, f"Exceeds GitHub regular-file size: {name}"
        audit_file(file, name)
    lock = read_json(ROOT / "design" / "r1-geometry-lock.json")
    for name, digest in lock["files"].items():
        assert sha256(OUT / name) == digest, f"r1 geometry/data changed: {name}"
    manifest = read_json(OUT / "data" / "print-manifest.json")
    for plate in manifest["plates"] + manifest["trials"]:
        assert sha256(OUT / plate["file"]) == plate["sha256"]
    checksum_names = set()
    for line in (OUT / "checksums.sha256").read_text().splitlines():
        expected, name = line.split("  ", 1)
        assert sha256(OUT / name) == expected, f"Package checksum mismatch: {name}"
        checksum_names.add(name)
    for file in OUT.rglob("*"):
        if file.is_file() and file.name != "checksums.sha256":
            assert file.relative_to(OUT).as_posix() in checksum_names, f"Unmanifested file: {file}"
    landing = (OUT / "index.html").read_text(encoding="utf-8")
    assert "LOCAL EDITION" not in landing and "公開・プリンター送信はしていません" not in landing
    for text in ("NOT_SLICED", "0.2 mm", "現物", "FreeCAD", "表示色は未確認"):
        assert text in landing, f"Missing limitation: {text}"
    assert config()["archive_url"] in landing and config()["repository"] in landing
    assert 'id="language-en"' in landing and 'id="language-ja"' in landing
    locale = read_json(ROOT / "design" / "translations.json")["en"]
    data = read_json(OUT / "data" / "kit.json")
    assert set(locale["steps"]) == {str(s["number"]) for s in data["steps"]}
    assert set(locale["roles"]) == {i["role"] for i in data["instances"]}
    assert (OUT / "docs" / "assembly-manual.en.pdf").is_file()
    assert (OUT / "media" / "assembly.en.srt").is_file()
    assert not re.search(r'(?:src|href)=["\']/(?!/)', landing), "Root-absolute website path"
    report = {"status": "PASS", "public_candidate_files": len(files), "staged": args.staged,
              "geometry_lock_files": len(lock["files"]), "geometry_byte_identical_to_local_r1": True,
              "internal_links_checked": check_links(OUT), "personal_metadata_and_credentials_found": False,
              "publication": config()}
    if args.stage:
        target = BUILD / "pages"
        target.mkdir(parents=True, exist_ok=True)
        expected = set()
        for file in OUT.rglob("*"):
            if not file.is_file():
                continue
            relative = file.relative_to(OUT)
            if relative.parts[0] in SITE_DIRS or relative.as_posix() == "index.html":
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, destination)
                expected.add(relative.as_posix())
        checksum_text = "".join(f"{sha256(target / name)}  {name}\n" for name in sorted(expected))
        (target / "checksums.sha256").write_text(checksum_text, encoding="utf-8")
        expected.add("checksums.sha256")
        actual = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
        assert actual == expected, f"Unexpected staging files: {actual - expected}"
        report["staged_site_files"] = len(actual)
        report["staged_site_bytes"] = sum(p.stat().st_size for p in target.rglob("*") if p.is_file())
        report["staged_site_links_checked"] = check_links(target)
    write_json(BUILD / "publication-audit.json", report)
    print("PUBLICATION_AUDIT_PASS", len(files), "files,", len(lock["files"]), "unchanged geometry/data files")


if __name__ == "__main__":
    main()
