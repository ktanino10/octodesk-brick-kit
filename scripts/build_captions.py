from common import ROOT, OUT, kit, read_json, write_json, sha256
from encode_movie import timestamp


def build_captions():
    data = kit()
    locale = read_json(ROOT / "design" / "translations.json")["en"]
    generation = read_json(OUT / "validation" / "blender-generation.json")
    fps = generation["fps"]
    old = read_json(OUT / "media" / "assembly-cues.json")
    english = ["Desk & Cat-Eared Character / starting with an empty table"]
    for item, step in zip(generation["frame_steps"], data["steps"], strict=True):
        assert item["step"] == step["number"] and item["instances"] == step["instances"]
        english.append(f'Step {step["number"]}/{len(data["steps"])} · {locale["steps"][str(step["number"])]["title"]}\n'
                       + "Add: " + " / ".join(step["instances"]))
    english.append(f'Complete / {len(data["instances"])} parts / {len(data["steps"])} steps / turntable')
    assert len(english) == len(old)
    cues = [{**{k: item[k] for k in ("start", "end")}, "ja": item["text"], "en": en}
            for item, en in zip(old, english, strict=True)]
    assert abs(cues[-1]["end"] - generation["frames"] / fps) < 1e-6
    srt, vtt = [], ["WEBVTT\n"]
    for index, cue in enumerate(cues, 1):
        srt.append(f'{index}\n{timestamp(cue["start"],True)} --> {timestamp(cue["end"],True)}\n{cue["en"]}\n')
        vtt.append(f'{timestamp(cue["start"])} --> {timestamp(cue["end"])}\n{cue["en"]}\n')
    (OUT / "media" / "assembly.en.srt").write_text("\n".join(srt), encoding="utf-8")
    (OUT / "media" / "assembly.en.vtt").write_text("\n".join(vtt), encoding="utf-8")
    write_json(OUT / "media" / "assembly-caption-data.json", cues)
    write_json(OUT / "validation" / "captions.json", {
        "status": "PASS", "languages": ["ja", "en"], "steps": len(data["steps"]),
        "cues": len(cues), "instance_ids_from_canonical_steps": True,
        "original_baked_in_language": "ja", "english_provided_as": ["synchronized guide text", "native text track", "SRT", "VTT"],
        "video_rerendered": False,
        "video_hashes": {name: sha256(OUT / "media" / name) for name in ("assembly.mp4", "assembly.webm")},
    })
    print("BILINGUAL_CAPTIONS", len(cues), "cues from the original frame timings")


if __name__ == "__main__":
    build_captions()
