"""Lossless PNG metadata cleanup and a byte lock for the unchanged r1 geometry."""
import hashlib
import io

from PIL import Image

from common import ROOT, OUT, read_json, sha256, write_json
from publication import PNG_SIGNATURE, audit_file, config, png_chunks


def main():
    lock_path = ROOT / "design" / "r1-geometry-lock.json"
    if not lock_path.exists():
        paths = []
        for folder in ("cad", "stl", "coupons", "plates"):
            paths.extend(p for p in (OUT / folder).iterdir()
                         if p.suffix in (".FCStd", ".step", ".blend", ".stl", ".3mf"))
        paths.extend(OUT / "data" / name for name in ("kit.json", "catalog.json", "print-manifest.json"))
        write_json(lock_path, {"geometry_revision": "1.0.0",
                              "files": {p.relative_to(OUT).as_posix(): sha256(p) for p in sorted(paths)}})
    lock = read_json(lock_path)
    for name, digest in lock["files"].items():
        assert sha256(OUT / name) == digest, f"Geometry changed: {name}"
    report_file = OUT / "validation" / "png-metadata.json"
    previous = read_json(report_file)["images"] if report_file.exists() else {}
    images = {}
    for file in sorted((OUT / "media").glob("*.png")):
        name = file.relative_to(OUT).as_posix()
        raw = file.read_bytes()
        before = hashlib.sha256(raw).hexdigest()
        if name in previous and previous[name]["output_sha256"] == before:
            images[name] = previous[name]
            audit_file(file, name)
            continue
        chunks = list(png_chunks(raw))
        dropped = [kind.decode() for kind, _, _ in chunks if kind in (b"tEXt", b"zTXt", b"iTXt", b"eXIf")]
        clean = PNG_SIGNATURE + b"".join(block for kind, _, block in chunks
                                         if kind not in (b"tEXt", b"zTXt", b"iTXt", b"eXIf"))
        idat = b"".join(body for kind, body, _ in chunks if kind == b"IDAT")
        assert idat == b"".join(body for kind, body, _ in png_chunks(clean) if kind == b"IDAT")
        with Image.open(io.BytesIO(raw)) as a, Image.open(io.BytesIO(clean)) as b:
            assert a.mode == b.mode and a.size == b.size and a.tobytes() == b.tobytes()
            pixels = hashlib.sha256(a.tobytes()).hexdigest()
        if clean != raw:
            file.write_bytes(clean)
        images[name] = {"input_sha256": before, "output_sha256": sha256(file),
                        "idat_sha256": hashlib.sha256(idat).hexdigest(),
                        "pixel_sha256": pixels, "pixels_unchanged": True,
                        "removed_metadata_chunks": dropped}
        audit_file(file, name)
    write_json(report_file, {"status": "PASS", "method": "Drop text/EXIF chunks; IDAT and decoded pixels unchanged",
                             "images": images})
    write_json(OUT / "data" / "publication.json", config())
    print("PUBLICATION_PREPARED", len(lock["files"]), "unchanged geometry/data files;", len(images), "PNG images")


if __name__ == "__main__":
    main()
