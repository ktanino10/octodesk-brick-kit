"""English documentation; all instances, counts, slots and positions come from the canonical kit."""
from html import escape

from common import ROOT, OUT, read_json


def build_english(data, catalog, manifest, style, diagram):
    locale = read_json(ROOT / "design" / "translations.json")["en"]
    assert set(locale["steps"]) == {str(s["number"]) for s in data["steps"]}
    assert set(locale["roles"]) == {i["role"] for i in data["instances"]}
    docs = OUT / "docs"
    count = data["counts"]
    pages = []
    size = " × ".join(f"{n:.1f}" for n in catalog["assembly_size_mm"])

    def page(title, body):
        number = len(pages) + 1
        pages.append(f'<section class="page"><p class="eyebrow">DESK / BRICK LAB · R1 · DIGITAL PROTOTYPE</p>'
                     f'<h2>{escape(title)}</h2>{body}<div class="footer">{number} / Units: mm. Printed scale may vary. '
                     'Physically untested. Reference photo and logos not included.</div></section>')

    page("Desk & Cat-Eared Character — Brick Diorama", f"""
<img class="hero" src="../media/hero.png" alt="Blender render of the supplied printable meshes">
<h3>{size} mm / {count['assembly_instances']} parts / {count['assembly_types']} production types / {count['steps']} steps / {count['colors']} colors</h3>
<p>An independent design of a white desk and chair, a black cat-eared character with a plain light-beige face, and a yellow mug. Print separate parts and stack them together. Grid pitch: 8 mm; brick body: 9.6 mm; plate body: 3.2 mm. The box, printed branding and official logos are not modeled.</p>
<p class="note"><b>P1S · 0.2 mm nozzle · PLA / NOT_SLICED</b><br>Digital prototype only. Physical fit, warping, retention, strength, tip-over and durability are untested. The actual plate, PLA brand and slicer profile are not confirmed. Test a small batch before printing the entire kit.</p>
<p>Images are renders, CAD projections/sections, or explicitly labeled bounding-box diagrams, not photographs of printed parts. IDs are guide labels, not physical markings. Identical type/color parts are interchangeable.</p>
<p><a href="assembly-manual.pdf">Japanese PDF</a> / The interactive guide preserves assembly state when switching Japanese / English. The shared video retains its Japanese header; English synchronized subtitles and SRT/VTT files are included.</p>
""")
    page("Test first / Print order is not assembly order", f"""
<h3>1. One loose-fit pair only</h3><p class="code">coupons/01-loose-pair-NOT_SLICED.3mf</p>
<p>FIT-M-D470: male diameter 4.70 mm. FIT-F-CP12: female radial clearance +0.12 mm. Male diameter correction and female radial clearance are independent settings. Check seating and removal with gentle finger pressure. Test pieces are excluded from the {count['assembly_instances']}-part assembly BOM.</p>
<h3>2. Two production 2×2 and two production 2×4 parts</h3><p class="code">coupons/02-representative-NOT_SLICED.3mf</p>
<p>The production candidate uses male diameter 4.80 mm and female radial clearance +0.04 mm; it is untested. A successful loose pair does not qualify the tighter production geometry. If calibration changes are needed, regenerate the affected files consistently. Do not scale the STL and break the 8 mm pitch.</p>
<h3>3. Base seam, then the complete base</h3><p class="code">coupons/03-base-joint-NOT_SLICED.3mf</p>
<p>Arrange two 8×8 plates along X. Turn the 4×8 plate so its long edge follows X, and put its lower corner at X=32, Y=0, Z=3.2 mm. It bridges the X=64 mm seam. Check warping, alignment and retention before printing the full base, desk and remaining parts in small batches.</p>
<h3>Slicer checks</h3><p>Extract the ZIP. Import 3MF as geometry and select your actual P1S / 0.2 mm nozzle / PLA / plate profile. Import STL in mm at 100%. Do not load the same part from both formats. Single-color plates do not require AMS.</p>
<p>Print open undersides down. Do not fill the receiving cavities with brim or support. Check first-layer entrances, roof bridges, studs, the mug-handle bridge (5.2 mm) and key relief (0.7 mm) in a real layer preview. Nominal margins: 10 mm between parts and 10 mm at the bed edge. Actual exclusion zones, brim, supports and toolpaths remain unverified.</p>
<p class="note"><b>Stop if:</b> openings close, parts fail to seat, tools or significant force are needed, stress whitening/cracks appear, retention is weak, or parts warp. Do not start with negative clearance. The mug is not for food/drink. Keep small parts away from infants and toddlers.</p>
""")
    page("Finished dimensions / Projections from the real CAD", """
<div class="wide"><img src="../media/cad-front.svg"></div>
<div class="grid"><img src="../media/cad-top.svg"><img src="../media/cad-right.svg"></div>
<p>FreeCAD TechDraw hidden-line projections of the BRep. Overall size includes the ears and highest studs. These are dimensions of this independent design, not measurements inferred from the photograph. Base: 191.8×127.8 mm; body thickness: 6.4 mm; including exposed studs: 8.2 mm.</p>
""")
    page("Open underside / Connection sections", """
<div class="grid"><img src="../media/brick-top.svg"><img src="../media/brick-bottom.svg"></div>
<div class="grid"><img src="../media/brick-section-y4.svg"><img src="../media/brick-section-y8.svg"></div>
<p>B-2x4 CAD projections and actual planar BRep sections. Body: 15.8×31.8×9.6 mm. Stud diameter: 4.8 mm; stud height: 1.8 mm. Pitch: 8 mm, with centers at 4+8×i. Stack bodies at 9.6 or 3.2 mm intervals; do not add stud height to each course.</p>
<p>The underside is an open cavity with a roof, walls, tubes and 1.2 mm ribs. Standard roof: 1.6 mm; plate roof: 1.0 mm; standard outer wall: 1.46 mm; minimum entrance wall: 1.26 mm; tube bore: 3.2 mm. Nominal thin-plate headroom over an inserted stud is 0.4 mm. Nominal clearance does not prove frictional retention.</p>
""")
    rows = "".join(
        f'<tr><td class="code">{r["part"]}</td><td>{locale["colors"][r["color"]]}</td><td>{r["quantity"]}</td>'
        f'<td>{" × ".join(f"{b-a:.1f}" for a,b in zip(*catalog["parts"][r["part"]]["bounds_mm"]))}</td></tr>'
        for r in data["bom"])
    page("Bill of materials / Assembly parts only", f"""
<table><thead><tr><th>Type ID / STL name</th><th>Color</th><th>Quantity</th><th>Actual bounds, mm</th></tr></thead><tbody>{rows}</tbody></table>
<p>Total: {count['assembly_instances']} parts, {count['assembly_types']} production types. The {count['coupon_types']} coupon types, representative trials and base-joint trial are separate. One STL file describes a type, not the quantity to print. STL has no unit field; use mm.</p>
<p class="tiny">Every slot and assembly candidate: data/plate-to-assembly.csv. Reverse mapping: data/print-manifest.json. Positions and rotations: data/instances.csv. The bilingual interactive guide exposes the same mapping. Native object labels and the original CSV role field may retain Japanese; IDs are unchanged.</p>
""")
    rows = "".join(f'<tr><td class="code">{escape(p["file"].split("/")[-1])}</td><td>{len(p["slots"])}</td>'
                   f'<td>{locale["colors"][p["color"]]}</td></tr>' for p in manifest["plates"])
    page("From a printed file to every assembly location", f"""
<table><thead><tr><th>Production file / example print order</th><th>Parts</th><th>Color</th></tr></thead><tbody>{rows}</tbody></table>
<p><b>Print order is not assembly order.</b> Each step below gives one example slot assignment per instance. Any other slot of the same type and color may be used. The IDs are not physical serial numbers.</p>
<p>Use index.html to follow file → slot → type/color → every candidate instance → step/position/orientation, or instance → every source file/slot. The complete mapping is also in the CSV and manifest.</p>
<p>If the slicer auto-arranges parts, their positions may differ from the supplied plate diagram. Match type, color and quantity. The {len(manifest['plates'])} production 3MF files, BOM, instances and assembly steps all contain the same {count['assembly_instances']} parts.</p>
<h3>Coordinates and orientation</h3><p>X points from chair to desk, Y from front to back, Z upward. The character faces +X. The photo-like view is from +X/−Y. Tables give the lower corner of the placed footprint; rotations are right-handed about Z. The manifest translation_mm field is the position of the part's local origin.</p>
<h3>Insertion and removal</h3><p>Insert downward from above. Fit the yellow mug before the head. Press large faces from above without levering the parts. Build the chair back, shoulders and neck while access is open. Disassemble in reverse order; remove the head before the mug.</p>
""")
    assigned = {s["example_instance"]: (p["file"].split("/")[-1], s["slot"])
                for p in manifest["plates"] for s in p["slots"]}
    by_id = {i["id"]: i for i in data["instances"]}
    for step in data["steps"]:
        translated = locale["steps"][str(step["number"])]
        rows = []
        for iid in step["instances"]:
            inst = by_id[iid]
            file, slot = assigned[iid]
            rows.append(f'<tr><td><b>{iid}</b><br>{locale["roles"][inst["role"]]}</td>'
                        f'<td class="code">{inst["part"]}<br>{locale["colors"][inst["color"]]}</td>'
                        f'<td>{", ".join(f"{v:.1f}" for v in inst["anchor_mm"])}<br>Z rotation {inst["rotation_deg"]}°</td>'
                        f'<td class="code">{file}<br>slot {slot} (example)</td></tr>')
        page(f"Step {step['number']:02d} / {translated['title']}", f"""
<p class="note"><b>Add {len(step['instances'])} {"part" if len(step['instances']) == 1 else "parts"} / insert from above ↓</b> {escape(translated['note'])}</p>
<div class="diagrams">{diagram(data,catalog,step['number'],language="en")}{diagram(data,catalog,step['number'],True,"en")}</div>
<table><thead><tr><th>Instance ID / role</th><th>Type / color</th><th>Lower corner X,Y,Z mm / rotation</th><th>Example print source</th></tr></thead><tbody>{"".join(rows)}</tbody></table>
<p class="tiny">All same-type, same-color parts are interchangeable. The interactive guide shows every source and the real mesh. Diagram labels omit the O- prefix. Front-view labels may overlap in depth; use the top view and the 3D guide together. These are bounding-box layout diagrams, not a substitute for the CAD shape.</p>
""")
    page("Verification scope, provenance and limitations", """
<h3>Digital checks performed</h3><p>See validation/report.json and the individual evidence files. Checks cover native reopening, all STEP solids, mesh closure/normals/dimensions, unintended interference, insertion approaches, support connections, BOM/3MF quantities, decoded video and browser/offline operation. The English guide uses the same source geometry, instance IDs, slot mapping and step order as Japanese.</p>
<h3>Not physically qualified</h3><p>Actual slicing, layer previews, printing, fit, retention, warping, elephant foot, bridge quality, strength, tip-over and durability remain untested. CAD volume or center of mass is not an actual printed weight or stability test. Test the loose pair before any larger batch.</p>
<p>Only FreeCAD GUI display colors are unverified: isolated offscreen GUI startup stalled. Headless native reopening confirmed geometry, positions, steps, color names and PartColor attributes. Default gray display may occur. Use the bilingual guide or Blender for colors; unchanged native object labels may retain Japanese.</p>
<h3>Independent design and rights</h3><p>The 8 mm dimensions and workflow were informed by Copilot Brick Display at commit 0967390547184b342adea0d7e8659dc8ac8f153b. Its original code, CAD, artwork and fonts were not copied; the reference has no blanket license. The user's photo was viewed only as a reference. The photo, box, logos, printed branding and personal information are not included. Hidden/internal structures are independently designed.</p>
<p>This is not an official LEGO, GitHub or Bambu Lab product. No endorsement, commercial-brick compatibility guarantee or toy certification is claimed. Public availability does not grant a blanket reuse license; consult NOTICE and the owner.</p>
<h3>Public and offline editions</h3><p>The approved destinations are ktanino10/octodesk-brick-kit, its GitHub Pages site and Releases. Extract the ZIP and open index.html; select English or use ?lang=en. No CDN, login or local server is required. Three.js is included under MIT. Build-tool binaries and font files are not redistributed.</p>
<p>The shared video still contains baked-in Japanese text. English synchronized captions and downloadable SRT/VTT are added separately; the original frames and geometry were not rerendered. No printer transmission or print start is performed.</p>
""")
    assert len(pages) == len(data["steps"]) + 7
    content = f'<!doctype html><html lang="en"><meta charset="utf-8"><title>Desk Brick Diorama — Assembly Manual R1</title><style>{style}</style><body>{"".join(pages)}</body></html>'
    (docs / "assembly-manual.en.html").write_text(content, encoding="utf-8")
    notices = """<!doctype html><html lang="en"><meta charset="utf-8"><title>Sources and notices</title><style>body{font:16px/1.8 sans-serif;max-width:900px;margin:40px auto;padding:20px}</style><h1>Sources and notices</h1>
<p>Independent, unofficial personal display design. No commercial-brick compatibility, manufacturer endorsement or toy certification is claimed. Not for food/drink or use as an infant/toddler toy. The user-supplied photograph was viewed for composition and color only. The photo, box, logos, branding and existing product CAD are not included.</p>
<p>The 8 mm dimensions and workflow were informed by Copilot Brick Display at commit 0967390547184b342adea0d7e8659dc8ac8f153b. Its code, CAD, artwork and fonts were not copied. There is no blanket license for that reference or for this project's original code/CAD/artwork/documents; ask the repository owner about reuse.</p>
<p>The only redistributed third-party browser runtime is Three.js 0.180.0 under <a href="../licenses/THREE-LICENSE.txt">MIT</a>. Build-tool binaries and font files are not included. PDFs may contain browser-generated font subsets for display.</p>
<p>FreeCAD 1.1.3 and Blender 5.1.1 were run in isolated processes. Shapes, renders, animation, drawings and guide were generated for this design. Approved public destinations: <a href="https://github.com/ktanino10/octodesk-brick-kit">repository</a>, <a href="https://ktanino10.github.io/octodesk-brick-kit/?lang=en">GitHub Pages</a>, and that repository's Releases. Reference photos, private information and local settings remain excluded. PNG text metadata was removed without changing pixels. Geometry, quantities and fit parameters are unchanged from r1.</p>
<p>All 3MF files are NOT_SLICED. Target: P1S / 0.2 mm nozzle / PLA. Actual plate, material brand, profiles, slicing, fit, retention, warping, strength, stability and durability are unverified. Begin with FIT-M-D470 + FIT-F-CP12 only, then representative production parts. No printer transmission or print start is performed.</p>
<p>Native geometry, positions, steps and color attributes were verified by headless reopening. Only FreeCAD GUI display colors remain unverified because offscreen startup stalled. Use this guide or Blender for colors. Native object labels may retain Japanese. Existing interactive application documents were not touched.</p>
<p>The common video retains its Japanese burned-in header. English subtitles are provided by the guide and as SRT/VTT; no claim is made that the original frames were translated. The same bilingual guide works without network access after extracting the ZIP.</p><p><a href="../index.html?lang=en">Back to the English guide</a> / <a href="notices.html" lang="ja">日本語</a></p></html>"""
    (docs / "notices.en.html").write_text(notices, encoding="utf-8")
    print("ENGLISH_MANUAL_HTML", len(pages), "logical pages")
