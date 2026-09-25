import json
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from common import OUT, BUILD, kit, read_json, write_json


def timestamp(seconds, srt=False):
    millis = round(seconds * 1000)
    minutes, milliseconds = divmod(millis, 60000)
    sec, milli = divmod(milliseconds, 1000)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02}:{minute:02}:{sec:02}{',' if srt else '.'}{milli:03}"


def main():
    data = kit()
    generation = read_json(OUT / "validation" / "blender-generation.json")
    font_path = Path(os.environ.get("JAPANESE_FONT", "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"))
    if not font_path.is_file():
        raise FileNotFoundError("Set JAPANESE_FONT to an installed Japanese TTF/TTC for caption rasterization.")
    title_font = ImageFont.truetype(str(font_path), 22)
    small_font = ImageFont.truetype(str(font_path), 12)
    labeled = BUILD / "labeled-frames"
    labeled.mkdir(parents=True, exist_ok=True)
    cues = [{"start": 0, "end": 1 / 12, "text": "机と猫耳のブロック・ジオラマ / 空の机から"}]
    for item in generation["frame_steps"]:
        step = data["steps"][item["step"] - 1]
        cues.append({"start": (item["start"] - 1) / 12, "end": item["end"] / 12,
                     "text": f'工程 {step["number"]}/{len(data["steps"])} · {step["title"]}\n'
                             + "追加: " + " / ".join(step["instances"])})
    cues.append({"start": generation["assembly_end_frame"] / 12, "end": generation["frames"] / 12,
                 "text": f'完成 / {len(data["instances"])}個 / {len(data["steps"])}工程 / 回転表示'})
    for frame in range(1, generation["frames"] + 1):
        source = BUILD / "frames" / f"frame-{frame:04d}.png"
        with Image.open(source) as im:
            assert im.size == (800, 660), (source, im.size)
            canvas = Image.new("RGB", (800, 760), "#f7f7ef")
            canvas.paste(im.convert("RGB"), (0, 100))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, 800, 100), fill="#173e38")
        time = (frame - 1) / 12
        cue = next((c for c in cues if c["start"] <= time < c["end"]), cues[-1])
        lines = cue["text"].split("\n")
        draw.text((20, 11), lines[0], font=title_font, fill="white")
        if len(lines) > 1:
            detail = lines[1]
            chunks = [detail[:70], detail[70:]] if len(detail) > 70 else [detail]
            for row, text in enumerate(chunks):
                draw.text((20, 46 + row * 17), text, font=small_font, fill="#e8f2e9")
        draw.text((20, 80), "R1 / 配布STLの実レンダー + 工程字幕 / NOT_SLICED / 現物未評価", font=small_font, fill="#d5e6db")
        canvas.save(labeled / f"frame-{frame:04d}.png")
    movie = OUT / "media" / "assembly.mp4"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-framerate", "12",
                    "-start_number", "1", "-i", str(labeled / "frame-%04d.png"),
                    "-c:v", "libx264", "-threads", "2", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(movie)], check=True)
    webm = OUT / "media" / "assembly.webm"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-framerate", "12",
                    "-start_number", "1", "-i", str(labeled / "frame-%04d.png"),
                    "-c:v", "libvpx-vp9", "-threads", "2", "-row-mt", "1",
                    "-deadline", "good", "-cpu-used", "4", "-crf", "32", "-b:v", "0",
                    "-pix_fmt", "yuv420p", "-an", str(webm)], check=True)
    srt, vtt = [], ["WEBVTT\n"]
    for index, cue in enumerate(cues, 1):
        srt.append(f'{index}\n{timestamp(cue["start"],True)} --> {timestamp(cue["end"],True)}\n{cue["text"]}\n')
        vtt.append(f'{timestamp(cue["start"])} --> {timestamp(cue["end"])}\n{cue["text"]}\n')
    (OUT / "media" / "assembly.srt").write_text("\n".join(srt), encoding="utf-8")
    (OUT / "media" / "assembly.vtt").write_text("\n".join(vtt), encoding="utf-8")
    write_json(OUT / "media" / "assembly-cues.json", cues)
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams",
                                               "-show_format", "-of", "json", str(movie)]))
    stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert int(stream["nb_frames"]) == generation["frames"]
    assert stream["pix_fmt"] == "yuv420p" and stream["codec_name"] == "h264"
    assert (stream["width"], stream["height"]) == (800, 760)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(movie), "-f", "null", "-"], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(webm), "-f", "null", "-"], check=True)
    indices = [0, 155, 300, generation["assembly_end_frame"] - 1, generation["frames"] - 1]
    filter_text = "+".join(f"eq(n\\,{i})" for i in indices)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(movie), "-vf", f"select={filter_text}",
                    "-fps_mode", "vfr", str(BUILD / "decoded-%02d.png")], check=True)
    sheet = Image.new("RGB", (400 * len(indices), 380), "#ffffff")
    for i in range(len(indices)):
        with Image.open(BUILD / f"decoded-{i+1:02d}.png") as image:
            sheet.paste(image.resize((400, 380)), (i * 400, 0))
    sheet.save(OUT / "validation" / "video-contact-sheet.png")
    write_json(OUT / "validation" / "video.json", {
        "status": "PASS", "full_decode": True, "codec": "h264", "pixel_format": "yuv420p",
        "frames": generation["frames"], "fps": 12, "duration_seconds": float(stream["duration"]),
        "resolution": [800, 760], "faststart": True, "captioned_steps": len(data["steps"]),
        "decoded_representative_frames": indices,
        "rendering": "Blender Workbench mesh animation; Japanese captions composited with Pillow",
        "caption_font": font_path.name, "font_file_redistributed": False,
        "browser_fallback": {"file": "media/assembly.webm", "codec": "VP9",
                             "full_decode": True, "reason": "Unbranded Chromium may not include H.264."},
    })
    print("MOVIE_ENCODED_DECODED", stream["duration"], "seconds")


if __name__ == "__main__":
    main()
