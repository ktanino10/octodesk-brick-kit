"""Independent desk diorama layout; all downstream outputs consume kit.json."""
from collections import Counter
from common import ROOT, OUT, rotation_z, transform, write_json

PARTS = {}
INSTANCES = []
STEPS = []


def part(nx, ny, height=9.6, kind="brick", studs=True, part_id=None, **extra):
    prefix = "B" if height == 9.6 else "P"
    part_id = part_id or f"{prefix}-{nx}x{ny}"
    record = {
        "id": part_id, "kind": kind, "nx": nx, "ny": ny,
        "body_height": height, "studs": studs,
        "male_diameter_correction": 0.0, "female_radial_clearance": 0.04,
        "roof_mm": 1.0 if height == 3.2 else 1.6,
        "open_bottom": True, "print_orientation": "open_bottom_down",
        "print_rotation_deg": [0, 0, 0], **extra,
    }
    if part_id in PARTS:
        assert PARTS[part_id] == record, part_id
    PARTS[part_id] = record
    return part_id


def step(title, note=""):
    number = len(STEPS) + 1
    STEPS.append({"number": number, "title": title, "note": note,
                  "instances": [], "insertion_vector": [0, 0, -1],
                  "approach_clearance_mm": 40})


def add(nx, ny, x, y, z, color, role, height=9.6, custom=None, rotation=None):
    canonical = sorted((nx, ny))
    pid = custom or part(*canonical, height)
    p = PARTS[pid]
    angle = rotation if rotation is not None else (0 if p["nx"] == nx else 90)
    r = rotation_z(angle)
    center = [p["nx"] * 4, p["ny"] * 4, 0]
    target = [x + nx * 4, y + ny * 4, z]
    t = [round(target[i] - sum(r[i][j] * center[j] for j in range(3)), 6)
         for i in range(3)]
    instance = {
        "id": f"O-{len(INSTANCES) + 1:03d}", "part": pid, "color": color,
        "role": role, "step": len(STEPS), "anchor_mm": [x, y, z],
        "footprint_studs": [nx, ny], "rotation_deg": angle, "translation_mm": t,
        "connections": [], "foundation": z == 0,
    }
    INSTANCES.append(instance)
    STEPS[-1]["instances"].append(instance["id"])
    return instance


def rectangle_2x4(x, y, nx, ny, z, color, role, alternate=False):
    if alternate:
        assert nx % 2 == 0 and ny % 4 == 0
        for a in range(0, nx, 2):
            for b in range(0, ny, 4):
                add(2, 4, x + a * 8, y + b * 8, z, color, role)
    else:
        assert nx % 4 == 0 and ny % 2 == 0
        for a in range(0, nx, 4):
            for b in range(0, ny, 2):
                add(4, 2, x + a * 8, y + b * 8, z, color, role)


def main():
    step("緑の台座・下段", "平らな机で6枚を並べる。まだ互いに固定されていません。")
    for y in (0, 64):
        for x in (0, 64, 128):
            add(8, 8, x, y, 0, "green", "台座下段", 3.2)
    step("緑の台座・継ぎ目をまたぐ上段", "下段のX=64/128、Y=64の継ぎ目を上段でまたぎます。")
    for y, ny in ((0, 4), (32, 8), (96, 4)):
        for x, nx in ((0, 4), (32, 8), (96, 8), (160, 4)):
            add(nx, ny, x, y, 3.2, "green", "台座上段", 3.2)
    for course in range(3):
        step(f"椅子の脚・{course + 1}段目")
        for x in (24, 72):
            for y in (32, 80):
                add(2, 2, x, y, 6.4 + course * 9.6, "white", "椅子脚")
    # A hollow square pedestal and two left legs support every tabletop segment.
    ring = [(0, 0, 4, 2), (4, 0, 4, 2), (0, 6, 4, 2),
            (4, 6, 4, 2), (0, 2, 2, 4), (6, 2, 2, 4)]
    for course in range(5):
        step(f"机の中空脚・{course + 1}段目", "右の中空台脚と左の2本脚。前段と継ぎ目を交差させます。")
        z = 6.4 + course * 9.6
        for gx, gy, nx, ny in ring:
            if course % 2:
                gx, gy, nx, ny = 8 - gy - ny, gx, ny, nx
            add(nx, ny, 112 + gx * 8, 32 + gy * 8, z, "white", "机中空台脚")
        for y in (32, 80):
            add(2, 2, 96, y, z, "white", "机左脚")
    step("椅子の座面・下段")
    for x in (24, 56):
        add(4, 8, x, 32, 35.2, "white", "座面下段", 3.2)
    step("椅子の座面・上段")
    for y in (32, 64):
        add(8, 4, 24, y, 38.4, "white", "座面上段", 3.2)
    for course in range(4):
        step(f"白い背もたれ・{course + 1}段目")
        lengths = [4, 4] if course % 2 == 0 else [2, 4, 2]
        y = 32
        for n in lengths:
            add(2, n, 24, y, 41.6 + course * 9.6, "white", "椅子背もたれ")
            y += n * 8
    flat_back = part(2, 8, 3.2, "tile", False, "T-2x8")
    step("背もたれの上を閉じる")
    add(2, 8, 24, 32, 80.0, "white", "背もたれ天面", 3.2, flat_back)
    step("座ったキャラクターの足と胴・下段")
    rectangle_2x4(48, 48, 4, 4, 41.6, "black", "胴下段")
    for y in (48, 64):
        add(1, 2, 80, y, 41.6, "black", "足先")
    step("キャラクターの胴・上段")
    rectangle_2x4(48, 48, 4, 4, 51.2, "black", "胴上段", True)
    step("机の天板・下段", "各板は脚に支持されます。続けて上段を付けて3枚を連結します。")
    for x in (88, 120, 152):
        add(4, 10, x, 24, 54.4, "white", "天板下段", 3.2)
    step("机の天板・上段", "下段の継ぎ目と直交・ずらして固定します。")
    for x in (88, 136):
        for y, ny in ((24, 4), (56, 4), (88, 2)):
            add(6, ny, x, y, 57.6, "white", "天板上段", 3.2)
    step("机へ伸びる両腕", "胴と机をまたぐプレート。胴と天板の上面は同じZ=60.8 mmです。")
    for y in (40, 72):
        add(4, 2, 64, y, 60.8, "black", "腕", 3.2)
    step("肩と首")
    add(4, 2, 48, 56, 60.8, "black", "肩")
    add(2, 2, 56, 56, 70.4, "black", "首")
    mug = part(2, 3, 3.2, "mug", False, "MUG-2x3",
               feature_notes="Cup wall 1.8 mm; handle 2.4 mm; handle roof span 5.2 mm.")
    step("黄色いマグを手元に取り付ける", "頭を付ける前に差し込みます。外す時は先に頭を外してください。飲食用ではありません。")
    add(2, 3, 80, 32, 64.0, "yellow", "マグ", 3.2, mug)
    step("頭の黒い下縁", "首の4スタッドへ。マグの上を覆うので順序を変えないでください。")
    add(6, 6, 40, 40, 80.0, "black", "頭下縁", 3.2)
    for course in range(3):
        step(f"四角い頭とベージュの顔・{course + 1}段目", "顔は+X（机側）。目やゴーグル、ロゴはありません。")
        z = 83.2 + course * 9.6
        if course % 2 == 0:
            rectangle_2x4(40, 40, 4, 6, z, "black", "頭後部")
        else:
            for x in (40, 56):
                add(2, 4, x, 40, z, "black", "頭後部")
            add(4, 2, 40, 72, z, "black", "頭後部")
        y = 40
        for n in ([4, 2] if course % 2 == 0 else [2, 4]):
            add(2, n, 72, y, z, "beige", "顔")
            y += n * 8
    step("頭の黒い上縁")
    add(6, 6, 40, 40, 112.0, "black", "頭上縁", 3.2)
    ear = part(2, 2, 3.2, "ear", False, "EAR-2x2",
               feature_notes="Solid sloping ear above an open-bottom 2x2 plate.")
    step("2つの猫耳", "同じ型を180度回して左右に使います。高い側を外側へ。")
    add(2, 2, 56, 40, 115.2, "black", "手前の耳", 3.2, ear, 0)
    add(2, 2, 56, 72, 115.2, "black", "奥の耳", 3.2, ear, 180)
    step("モニターの支柱")
    add(2, 4, 144, 48, 60.8, "white", "モニター支柱")
    for course in range(4):
        step(f"白いモニター・{course + 1}段目", "写真で見える白い背面を表現。未確認の画面表示は追加しません。")
        y = 32
        for n in ([4, 4] if course % 2 == 0 else [2, 4, 2]):
            add(2, n, 144, y, 70.4 + course * 9.6, "white", "モニター")
            y += n * 8
    step("モニター上端")
    add(2, 8, 144, 32, 108.8, "white", "モニター上端", 3.2, flat_back)
    keyboard = part(2, 6, 3.2, "keyboard", False, "KEY-2x6",
                    feature_notes="20 integral raised keys, 0.7 mm relief; no separate keycaps.")
    step("白いキーボード", "長辺をY方向に。これで完成です。")
    add(2, 6, 104, 40, 60.8, "white", "キーボード", 3.2, keyboard)

    studs = []
    for inst in INSTANCES:
        p = PARTS[inst["part"]]
        lower_z = inst["anchor_mm"][2]
        inverse = rotation_z(-inst["rotation_deg"])
        for previous_id, stud in studs:
            if abs(stud[2] - lower_z) > 1e-5:
                continue
            d = [stud[i] - inst["translation_mm"][i] for i in range(3)]
            local = [sum(inverse[i][j] * d[j] for j in range(3)) for i in range(3)]
            if 0 < local[0] < p["nx"] * 8 and 0 < local[1] < p["ny"] * 8:
                assert all(abs((v - 4) / 8 - round((v - 4) / 8)) < 1e-5 for v in local[:2])
                connection = next((c for c in inst["connections"] if c["lower"] == previous_id), None)
                if connection is None:
                    connection = {"lower": previous_id, "stud_centers_mm": []}
                    inst["connections"].append(connection)
                connection["stud_centers_mm"].append(stud)
        assert inst["foundation"] or inst["connections"], f"Unsupported {inst}"
        if p["studs"]:
            for ix in range(p["nx"]):
                for iy in range(p["ny"]):
                    studs.append((inst["id"], transform([4 + ix * 8, 4 + iy * 8, p["body_height"]], inst)))

    assembly_parts = set(p["part"] for p in INSTANCES)
    tests = []
    for d in (4.7, 4.8, 4.9):
        tests.append(part(2, 2, 9.6, "brick", True, f"FIT-M-D{round(d * 100):03d}",
                          male_diameter_correction=round(d - 4.8, 2), test_only=True))
    for code, c in (("CN04", -.04), ("C000", 0), ("CP04", .04), ("CP08", .08), ("CP12", .12)):
        tests.append(part(2, 2, 9.6, "tile", False, f"FIT-F-{code}",
                          female_radial_clearance=c, test_only=True))
    counts = Counter((i["part"], i["color"]) for i in INSTANCES)
    data = {
        "revision": "1.0.0", "id": "octodesk-r1", "title": "机と猫耳のブロック・ジオラマ",
        "created": "2026-09-24", "units": "mm",
        "status": "DIGITAL_PROTOTYPE_PHYSICAL_FIT_UNVERIFIED",
        "printer": {"model": "Bambu Lab P1S", "nozzle_mm": 0.2, "material": "PLA",
                    "bed_mm": [256, 256, 256], "edge_margin_mm": 10,
                    "part_gap_mm": 10, "sliced": False, "profile": None, "plate_type": None},
        "parameters": {"pitch": 8.0, "brick_height": 9.6, "plate_height": 3.2,
                       "body_gap": .2, "reference_stud_diameter": 4.8,
                       "stud_height": 1.8, "stud_lead_in": .25,
                       "socket_lead_in": .2, "socket_lead_in_height": .3,
                       "tube_inner_diameter": 3.2, "rib_width": 1.2},
        "coordinates": {"x": "椅子から机へ", "y": "手前から奥へ", "z": "上",
                        "front": "-Y", "character_faces": "+X",
                        "rotation": "Z軸の右手回り。translation_mm は部品ローカル原点の世界位置。"},
        "colors": {"green": {"name": "緑", "hex": "#409878"},
                   "white": {"name": "白", "hex": "#ededdf"},
                   "black": {"name": "黒", "hex": "#252730"},
                   "beige": {"name": "薄いベージュ", "hex": "#e1cb91"},
                   "yellow": {"name": "黄色", "hex": "#efbf23"}},
        "parts": PARTS, "instances": INSTANCES, "steps": STEPS,
        "bom": [{"part": p, "color": c, "quantity": n}
                for (p, c), n in sorted(counts.items())],
        "counts": {"assembly_instances": len(INSTANCES), "assembly_types": len(assembly_parts),
                   "steps": len(STEPS), "colors": len(set(i["color"] for i in INSTANCES)),
                   "coupon_types": len(tests)},
        "trial_batches": [
            {"id": "01-loose-pair", "title": "最初はこのゆるい1組だけ",
             "parts": [{"part": "FIT-M-D470", "quantity": 1}, {"part": "FIT-F-CP12", "quantity": 1}]},
            {"id": "02-representative", "title": "本番2x2と2x4を各2個",
             "parts": [{"part": "B-2x2", "quantity": 2}, {"part": "B-2x4", "quantity": 2}]},
            {"id": "03-base-joint", "title": "台座2枚と継ぎ目ブリッジ1枚",
             "parts": [{"part": "P-8x8", "quantity": 2}, {"part": "P-4x8", "quantity": 1}]},
        ],
        "physical_status": {
            "fit": "NOT_TESTED", "strength": "NOT_TESTED", "stability": "NOT_TESTED",
            "slicer_preview": "NOT_EXECUTED_PROFILE_UNKNOWN", "printed_samples": 0,
            "compatibility": "NO_COMMERCIAL_BRICK_COMPATIBILITY_GUARANTEE",
        },
        "provenance": {
            "photo": "ユーザー提供写真を目視参照。原写真・箱・ロゴ・印字は同梱しない。",
            "design": "見える配色と配置に着想を得た独立した非公式の個人用設計。寸法の複製ではない。",
            "mechanical_reference_commit": "0967390547184b342adea0d7e8659dc8ac8f153b",
            "reference_reuse": "寸法とワークフローを参照。既存コード・CAD・画像・フォントは複製していない。",
        },
    }
    write_json(ROOT / "design" / "kit.json", data)
    write_json(OUT / "data" / "kit.json", data)
    print(data["counts"])


if __name__ == "__main__":
    main()
