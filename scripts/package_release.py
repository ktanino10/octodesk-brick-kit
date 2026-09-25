"""Build and audit the public/offline kit; finalization records the ZIP browser run."""
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from common import ROOT, OUT, BUILD, kit, read_json, sha256, write_json
from publication import audit_file, config

ARCHIVE = ROOT / "dist" / "octodesk-r1-offline.zip"
EXTRACT = BUILD / "archive-test"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("href", "src") and value:
                self.links.append(value)


def check_links(folder):
    checked = 0
    for file in folder.rglob("*.html"):
        if "source" in file.relative_to(folder).parts:
            continue
        parser = Links()
        parser.feed(file.read_text(encoding="utf-8"))
        for link in parser.links:
            parsed = urlsplit(link)
            if parsed.scheme or not parsed.path:
                continue
            resolved = (file.parent / unquote(parsed.path)).resolve()
            assert resolved.is_relative_to(folder.resolve()), (file, link, "escapes package")
            assert resolved.is_file(), (file, link, "missing")
            checked += 1
    return checked


def source_copy():
    target = OUT / "source"
    for directory, pattern in (("scripts", "*.py"), ("scripts", "*.mjs"), ("web", "*"),
                               ("tests", "*.mjs"), ("design", "*.json")):
        for file in (ROOT / directory).glob(pattern):
            if file.is_file():
                dest = target / directory / file.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, dest)
    for file in ("README.md", "NOTICE", "requirements.txt", "package.json", "package-lock.json"):
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / file, target / file)


def selected_files():
    suffixes = {".html", ".css", ".js", ".json", ".csv", ".png", ".svg", ".mp4", ".webm",
                ".srt", ".vtt", ".pdf", ".FCStd", ".step", ".blend", ".stl", ".3mf",
                ".txt", ".py", ".mjs", ".md"}
    return sorted(file for file in OUT.rglob("*") if file.is_file()
                  and (file.suffix in suffixes or file.name == "NOTICE")
                  and not any(p.startswith(".") for p in file.relative_to(OUT).parts))


def payload_digest(files):
    entries = {}
    for file in files:
        relative = file.relative_to(OUT).as_posix()
        if relative.startswith("validation/") or relative == "checksums.sha256":
            continue
        entries[relative] = sha256(file)
    serialized = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(serialized).hexdigest(), entries


def audit_pdf():
    file = OUT / "docs" / "assembly-manual.pdf"
    info = subprocess.check_output(["pdfinfo", str(file)], text=True)
    page_count = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    expected_pages = len(kit()["steps"]) + 7
    assert page_count == expected_pages, (page_count, expected_pages)
    text = subprocess.check_output(["pdftotext", "-layout", str(file), "-"]).decode("utf-8")
    compact = re.sub(r"\s+", "", text)
    assert "0.2mm" in compact and "NOT_SLICED" in compact and "色表示は未確認" in compact
    for inst in kit()["instances"]:
        assert inst["id"] in text, inst["id"]
    for step in kit()["steps"]:
        assert re.search(rf"工程\s+{step['number']:02d}\s*/", text), step["number"]
    write_json(OUT / "validation" / "pdf.json", {
        "status": "PASS", "pages": page_count, "all_137_instance_ids_in_extracted_text": True,
        "all_37_numbered_steps_in_extracted_text": True,
        "critical_nozzle_not_sliced_and_gui_limitations_in_text": True,
        "pdfinfo_readable": True, "fonts": "Chromium embedded/subset Japanese glyphs; font files not redistributed",
    })


def audit_movie_container():
    raw = (OUT / "media" / "assembly.mp4").read_bytes()
    atoms, position = [], 0
    while position + 8 <= len(raw):
        size, name = struct.unpack_from(">I4s", raw, position)
        if size == 1:
            size = struct.unpack_from(">Q", raw, position + 8)[0]
        if size == 0:
            size = len(raw) - position
        assert size >= 8
        atoms.append(name.decode("ascii"))
        position += size
    assert atoms.index("moov") < atoms.index("mdat")
    assert position == len(raw)
    return atoms


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    data = kit()
    catalog = read_json(OUT / "data" / "catalog.json")
    reports = {}
    for filename in ("cad.json", "native-documents.json", "meshes-and-plates.json",
                     "cad-drawings.json", "blender.json", "video.json", "browser.json", "pdf-generation.json"):
        report = read_json(OUT / "validation" / filename)
        assert report["status"] == "PASS", filename
        reports[filename] = report
    assert not reports["browser.json"]["smoke_only"]
    assert reports["blender.json"]["render_output_relative"]
    assert read_json(OUT / "validation" / "lighting.json")["all_stills_refreshed"]
    assert reports["meshes-and-plates.json"]["assembly_bom_equals_3mf_equals_instances"] == len(data["instances"])
    audit_pdf()
    atoms = audit_movie_container()
    source_copy()
    # Copy visual test evidence, never the source photograph or diagnostic app logs.
    for filename in ("desktop-http-guide.png", "mobile-http-guide.png", "desktop-http-top.png", "offline-file-guide.png"):
        source = BUILD / "browser" / filename
        assert source.is_file()
        shutil.copyfile(source, OUT / "validation" / filename)
    timestamp = datetime.now(timezone.utc).isoformat()
    report = {
        "revision": data["revision"],
        "digital_status": "PASS_WITH_DECLARED_LIMITATIONS" if args.finalize else "AWAITING_ARCHIVE_BROWSER_TEST",
        "checked_at": timestamp, "units": "mm",
        "publication": config(),
        "size_mm": [round(x, 1) for x in catalog["assembly_size_mm"]],
        "counts": data["counts"], "production_3mf_plates": 8,
        "evidence": {name: "PASS" for name in reports},
        "pdf_pages": len(data["steps"]) + 7, "movie_faststart_atoms": atoms,
        "unverified": [
            "Actual slicer profile, plate exclusion regions, support and layer preview",
            "PLA fit, retention, warping, bridge quality, strength, tip-over and durability",
            "FreeCAD GUI viewport colors; native geometry and explicit PartColor attributes are verified",
        ],
        "physical_status": data["physical_status"],
        "printer": data["printer"],
        "privacy": {"source_photo_included": False, "reference_artwork_included": False,
                    "original_reference_code_copied": False, "public_distribution_authorized": True,
                    "printer_sent": False, "existing_gui_documents_touched": False},
        "first_print": "coupons/01-loose-pair-NOT_SLICED.3mf",
    }
    write_json(OUT / "validation" / "report.json", report)
    files = selected_files()
    for file in files:
        relative = file.relative_to(OUT).as_posix()
        assert not any(token in relative for token in ("clipboard", "reference-b-completed", ".FCStd1", ".blend1", "node_modules"))
        audit_file(file, relative)
    digest, entries = payload_digest(files)
    if args.finalize:
        previous = read_json(BUILD / "archive-snapshot.json")
        assert previous["payload_sha256"] == digest, "Runtime/source payload changed after extracted ZIP test"
        offline = read_json(BUILD / "archive-browser.json")
        assert offline["status"] == "PASS" and not offline["smoke_only"]
        report["extracted_zip_browser"] = {
            "status": "PASS", "payload_sha256": digest, "file_protocol": True,
            "network_disabled": True, "checks": len(offline["checks"]),
        }
        write_json(OUT / "validation" / "report.json", report)
        write_json(OUT / "validation" / "archive-browser.json", offline)
    else:
        write_json(BUILD / "archive-snapshot.json", {"payload_sha256": digest, "files": entries})
    link_count = check_links(OUT)
    files = selected_files()
    checksums = "".join(f"{sha256(file)}  {file.relative_to(OUT).as_posix()}\n" for file in files)
    (OUT / "checksums.sha256").write_text(checksums, encoding="utf-8")
    files.append(OUT / "checksums.sha256")
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file in files:
            archive.write(file, "octodesk-r1/" + file.relative_to(OUT).as_posix())
    with zipfile.ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(files)
        for name in archive.namelist():
            assert not Path(name).is_absolute() and ".." not in Path(name).parts
        archive.extractall(EXTRACT)
    extracted = EXTRACT / "octodesk-r1"
    for line in (extracted / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        assert sha256(extracted / name) == expected, name
    assert check_links(extracted) == link_count
    receipt = {"file": ARCHIVE.name, "bytes": ARCHIVE.stat().st_size, "sha256": sha256(ARCHIVE),
               "files": len(files), "internal_links_checked": link_count,
               "extracted_files_hash_verified": len(files) - 1, "payload_sha256": digest,
               "finalized": args.finalize, "publication": config()}
    write_json(ROOT / "dist" / "release-receipt.json", receipt)
    print("RELEASE_PACKAGE", json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
