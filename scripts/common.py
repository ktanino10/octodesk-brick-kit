import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "octodesk-r1"
BUILD = ROOT / "build"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rotation_z(angle):
    a = math.radians(angle)
    return [[round(math.cos(a), 10), -round(math.sin(a), 10), 0],
            [round(math.sin(a), 10), round(math.cos(a), 10), 0], [0, 0, 1]]


def transform(point, instance):
    r = rotation_z(instance["rotation_deg"])
    t = instance["translation_mm"]
    return [round(sum(r[i][j] * point[j] for j in range(3)) + t[i], 7)
            for i in range(3)]


def kit():
    return read_json(ROOT / "design" / "kit.json")
