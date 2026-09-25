import html
import sys
import time

import FreeCAD as App
import Part
import TechDraw

from common import OUT, BUILD, kit, read_json, write_json
from freecad_build import matrix


def projection(shape, transform, filename, title):
    shape = shape.copy()
    shape.transformShape(transform, True)
    bb = shape.BoundBox
    group = TechDraw.projectToSVG(shape, App.Vector(0, 0, 1))
    group = group.replace('stroke-width="1.0"', 'stroke-width="0.13"')
    x0, y0, x1, y1 = bb.XMin, -bb.YMax, bb.XMax, -bb.YMin
    w, h = x1 - x0, y1 - y0
    title_font = min(3.5, (w + 20) / (len(title) * .62))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{round((h + 36) / (w + 40) * 1000)}" viewBox="{x0 - 20} {y0 - 18} {w + 40} {h + 36}">
<rect x="{x0 - 20}" y="{y0 - 18}" width="{w + 40}" height="{h + 36}" fill="white"/>
<g fill="#174a40" font-family="sans-serif" font-size="{title_font}"><text x="{x0}" y="{y0 - 12}">{html.escape(title)}</text></g>
{group}
<g stroke="#177765" fill="none" stroke-width=".2">
<path d="M{x0},{y1 + 2}V{y1 + 8} M{x1},{y1 + 2}V{y1 + 8} M{x0},{y1 + 6}H{x1}"/>
<path d="M{x1 + 2},{y0}H{x1 + 8} M{x1 + 2},{y1}H{x1 + 8} M{x1 + 6},{y0}V{y1}"/>
</g><g font-family="sans-serif" font-size="3.6" fill="#174a40">
<text x="{(x0 + x1) / 2}" y="{y1 + 12}" text-anchor="middle">{w:.1f} mm</text>
<text x="{x1 + 9}" y="{(y0 + y1) / 2}" transform="rotate(-90 {x1 + 9} {(y0 + y1) / 2})" text-anchor="middle">{h:.1f} mm</text>
</g></svg>'''
    (OUT / "media" / filename).write_text(svg, encoding="utf-8")
    return {"file": f"media/{filename}", "method": "FreeCAD TechDraw hidden-line projection",
            "projected_bounds_mm": [w, h]}


def section(shape, y):
    wires = shape.slice(App.Vector(0, 1, 0), y)
    assert wires
    paths = []
    for wire in wires:
        for edge in wire.Edges:
            pts = edge.discretize(Deflection=.015)
            coords = " ".join(f"{p.x:.4f},{-p.z:.4f}" for p in pts)
            paths.append(f'<polyline points="{coords}" fill="none" stroke="#183d34" stroke-width=".10"/>')
    return "".join(paths)


def main():
    started = time.monotonic()
    data = kit()
    shapes = {}
    for pid in data["parts"]:
        s = Part.Shape()
        s.read(str(BUILD / "brep" / f"{pid}.brep"))
        shapes[pid] = s
    placed = []
    for inst in data["instances"]:
        s = shapes[inst["part"]].copy()
        s.Placement = App.Placement(matrix(inst))
        placed.append(s)
    shape = Part.makeCompound(placed)
    top = App.Matrix()
    front = App.Matrix(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1)
    right = App.Matrix(0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1)
    if "--details-only" in sys.argv:
        reports = [r for r in read_json(OUT / "validation" / "cad-drawings.json")["drawings"]
                   if r["file"].startswith("media/cad-")]
    else:
        reports = []
        for name, view in (("top", top), ("front", front), ("right", right)):
            reports.append(projection(shape, view, f"cad-{name}.svg", f"R1 / {name.upper()} / mm"))
            print("CAD_PROJECTION", name, flush=True)
    reports.append(projection(shapes["B-2x4"], top, "brick-top.svg", "B-2x4 / TOP"))
    bottom = App.Matrix(1, 0, 0, 0, 0, -1, 0, 32, 0, 0, -1, 12, 0, 0, 0, 1)
    reports.append(projection(shapes["B-2x4"], bottom, "brick-bottom.svg", "B-2x4 / OPEN BOTTOM"))
    for y in (4, 8):
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="-3 -17 22 22" width="650" height="650">
<rect x="-3" y="-17" width="22" height="22" fill="white"/>
<text x="0" y="-14.5" font-family="sans-serif" font-size="1">B-2x4 / SECTION Y={y} mm</text>
{section(shapes["B-2x4"], y)}
<text x="0" y="2.5" font-family="sans-serif" font-size=".85">BODY 9.6 / STUD 1.8 / ROOF 1.6 mm</text>
</svg>'''
        filename = f"brick-section-y{y}.svg"
        (OUT / "media" / filename).write_text(svg, encoding="utf-8")
        reports.append({"file": f"media/{filename}", "method": "Exact BREP plane section, sampled edges",
                        "plane_y_mm": y, "curve_deflection_mm": .015})
    write_json(OUT / "validation" / "cad-drawings.json", {
        "status": "PASS", "drawings": reports, "elapsed_seconds": round(time.monotonic() - started, 1)
    })


if __name__ == "__main__":
    main()
