"""Shared public-distribution checks. These checks never print matched values."""
import base64
import io
import json
import re
import struct
import zipfile
import zlib

from common import ROOT, read_json

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PRIVATE_PATTERNS = {
    "home-directory": re.compile(rb"(?:/Users|/home)/[A-Za-z0-9._-]+/"),
    "windows-home-directory": re.compile(rb"[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\"),
    "private-key": re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    "github-token": re.compile(rb"(?<![A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    "aws-key": re.compile(rb"(?<![A-Za-z0-9_])AKIA[0-9A-Z]{16}(?![A-Za-z0-9_])"),
    "personal-email": re.compile(rb"[A-Za-z0-9._%+-]+@(?:gmail|outlook|icloud|yahoo)\.[A-Za-z.]+"),
}


def config():
    return read_json(ROOT / "design" / "publication.json")


def png_chunks(raw):
    assert raw.startswith(PNG_SIGNATURE), "Not a PNG"
    offset = len(PNG_SIGNATURE)
    while offset < len(raw):
        size = struct.unpack_from(">I", raw, offset)[0]
        name = raw[offset + 4:offset + 8]
        end = offset + size + 12
        assert end <= len(raw), "Truncated PNG"
        body = raw[offset + 8:offset + 8 + size]
        crc = struct.unpack_from(">I", raw, offset + 8 + size)[0]
        assert zlib.crc32(name + body) & 0xffffffff == crc, "PNG CRC mismatch"
        yield name, body, raw[offset:end]
        offset = end
    assert offset == len(raw)


def check_bytes(raw, label):
    for category, pattern in PRIVATE_PATTERNS.items():
        assert not pattern.search(raw), f"{label}: forbidden {category}"


def audit_file(file, label=None):
    label = label or file.name
    assert not file.is_symlink(), f"{label}: symlink not allowed"
    raw = file.read_bytes()
    if file.name == "data.js" and raw.startswith(b"window.OCTODESK_DATA="):
        obj = json.loads(raw.removeprefix(b"window.OCTODESK_DATA=").strip().removesuffix(b";"))
        meshes = obj.pop("meshes")
        check_bytes(json.dumps(obj, ensure_ascii=False).encode(), label)
        for pid, encoded in meshes.items():
            check_bytes(base64.b64decode(encoded, validate=True), f"{label}/{pid}")
    else:
        check_bytes(raw, label)
    if file.suffix == ".png":
        for name, _, _ in png_chunks(raw):
            assert name not in (b"tEXt", b"zTXt", b"iTXt", b"eXIf"), f"{label}: unreviewed PNG metadata"
    elif file.suffix in (".FCStd", ".3mf"):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            assert archive.testzip() is None, label
            for name in archive.namelist():
                check_bytes(archive.read(name), f"{label}::{name}")
    elif file.suffix == ".pdf":
        for stream in re.finditer(rb"(?<![A-Za-z])stream\r?\n", raw):
            body = raw[stream.end():]
            if body[:2] in (b"x\x01", b"x\x9c", b"x\xda"):
                check_bytes(zlib.decompress(body), f"{label}::flate-stream")
