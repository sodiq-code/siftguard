#!/usr/bin/env python3
"""
SIFTGuard Demo Video Builder — Narrated v4
Rebuilds video clips with corrected durations to match VO, mixes audio, stitches.
"""

import subprocess, math
from pathlib import Path

REPO   = Path("/home/user/siftguard")
SHOTS  = REPO / "demo/screenshots"
SLIDES = Path("/tmp/demo_slides")
CLIPS  = Path("/tmp/demo_clips_v2")
VO_DIR = Path("/tmp/vo_raw")
OUT    = REPO / "demo"

CLIPS.mkdir(parents=True, exist_ok=True)

W, H, FPS = 1920, 1080, 25

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def vo_duration(vo_file):
    r = run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(vo_file)])
    return float(r.stdout.strip()) if r.stdout.strip() else 0

def png_to_clip(png_path, out_mp4, duration, fade_in=0.3, fade_out=0.4):
    fi = int(fade_in * FPS)
    fo_start = int((duration - fade_out) * FPS)
    fo_len = int(fade_out * FPS)
    vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=#0a0e17,fade=in:0:{fi},fade=out:{fo_start}:{fo_len}"
    r = run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(png_path),
        "-vf", vf, "-t", str(duration), "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "18",
        str(out_mp4)
    ])
    return Path(out_mp4).exists()

def scroll_png_clip(png_path, out_mp4, duration, fade_in=0.3, fade_out=0.4):
    # Get PNG dimensions
    rw = run(["identify", "-format", "%w", str(png_path)])
    rh = run(["identify", "-format", "%h", str(png_path)])
    png_w = int(rw.stdout.strip()) if rw.stdout.strip().isdigit() else W
    png_h = int(rh.stdout.strip()) if rh.stdout.strip().isdigit() else H

    if png_h <= H:
        return png_to_clip(png_path, out_mp4, duration, fade_in, fade_out)

    scale_factor = W / png_w
    scaled_h = int(png_h * scale_factor)
    scroll_dist = scaled_h - H

    fi = int(fade_in * FPS)
    fo_start = int((duration - fade_out) * FPS)
    fo_len = int(fade_out * FPS)

    # Smooth scroll from top to bottom over the segment
    hold = 0.8  # hold at top for 0.8s before scrolling
    scroll_time = duration - hold - 0.5
    vf = (
        f"scale={W}:{scaled_h},"
        f"crop={W}:{H}:0:'if(lt(t,{hold}),0,"
        f"min({scroll_dist},{scroll_dist}*(t-{hold})/{scroll_time}))',"
        f"fade=in:0:{fi},"
        f"fade=out:{fo_start}:{fo_len}"
    )
    r = run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(png_path),
        "-vf", vf, "-t", str(duration), "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "18",
        str(out_mp4)
    ])
    return Path(out_mp4).exists()

def mix_vo_into_clip(video_mp4, vo_mp3, out_mp4, seg_duration):
    """Mix VO audio into silent video clip. VO starts at 0.2s offset."""
    vo_dur = vo_duration(vo_mp3)
    # Pad video if needed
    actual_dur = max(seg_duration, math.ceil(vo_dur) + 1)

    r = run([
        "ffmpeg", "-y",
        "-i", str(video_mp4),
        "-i", str(vo_mp3),
        "-filter_complex",
        # Delay VO by 0.2s, normalize level, pad silent tail
        f"[1:a]adelay=200|200,apad=whole_dur={actual_dur},volume=1.0[vo];"
        f"[vo]aformat=sample_rates=44100:channel_layouts=stereo[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(actual_dur),
        "-shortest",
        str(out_mp4)
    ])
    return Path(out_mp4).exists(), r.stderr[-500:] if not Path(out_mp4).exists() else ""

# ─── Segment definitions with corrected durations ────────────────────────────
# (seg_name, slide_png_name, vo_file, new_duration, scroll)
SEGMENTS = [
    ("00_intro",    "00_intro.png",    "vo_00.mp3",  14, False),
    ("01_problem",  "01_problem.png",  "vo_01.mp3",  15, False),
    ("02_solution", "02_solution.png", "vo_02.mp3",  18, False),
    ("03_stage1",   "03_stage1.png",   "vo_03.mp3",  22, True),
    ("04_stage23",  "04_stage23.png",  "vo_04.mp3",  23, True),
    ("05_stage4",   "05_stage4.png",   "vo_05.mp3",  22, True),
    ("06_stage56",  "06_stage56.png",  "vo_06.mp3",  28, True),
    ("07_stage78",  "07_stage78.png",  "vo_07.mp3",  21, True),
    ("08_audit",    "08_audit.png",    "vo_08.mp3",  22, True),
    ("09_arch",     "09_arch.png",     "vo_09.mp3",  22, False),
    ("10_outro",    "10_outro.png",    "vo_10.mp3",  14, False),
]

final_clips = []
print("Building narrated SIFTGuard demo video...")

for seg_name, slide_png, vo_file, duration, scroll in SEGMENTS:
    png_src = SLIDES / slide_png
    vo_src  = VO_DIR  / vo_file
    silent_mp4   = CLIPS / f"{seg_name}_silent.mp4"
    narrated_mp4 = CLIPS / f"{seg_name}_narrated.mp4"

    if not png_src.exists():
        print(f"  ✗ missing slide PNG: {slide_png}")
        continue
    if not vo_src.exists():
        print(f"  ✗ missing VO: {vo_file}")
        continue

    vo_dur = vo_duration(vo_src)
    # Use VO duration + buffer as the actual duration
    actual_dur = max(duration, math.ceil(vo_dur) + 1)

    print(f"  [{seg_name}]  {actual_dur}s  (VO={vo_dur:.1f}s)", end="  ", flush=True)

    # Step 1: render silent video clip
    if scroll:
        ok = scroll_png_clip(png_src, silent_mp4, actual_dur)
    else:
        ok = png_to_clip(png_src, silent_mp4, actual_dur)

    if not ok:
        print("✗ render failed")
        continue

    # Step 2: mix in VO
    ok, err = mix_vo_into_clip(silent_mp4, vo_src, narrated_mp4, actual_dur)
    if ok:
        print("✓")
        final_clips.append(str(narrated_mp4))
    else:
        print(f"✗ mix failed: {err}")

# ─── Stitch ──────────────────────────────────────────────────────────────────
print(f"\nStitching {len(final_clips)} narrated clips...")

concat_file = Path("/tmp/narrated_concat.txt")
with open(concat_file, "w") as f:
    for c in final_clips:
        f.write(f"file '{c}'\n")

final_out = OUT / "siftguard_demo_v4_narrated.mp4"
r = run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", str(concat_file),
    "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "-preset", "medium", "-crf", "18",
    "-c:a", "aac", "-b:a", "128k",
    "-movflags", "+faststart",
    str(final_out)
])

if final_out.exists():
    size_mb = final_out.stat().st_size / 1e6
    probe = run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(final_out)])
    dur = float(probe.stdout.strip()) if probe.stdout.strip() else 0
    print(f"\n✓ {final_out.name}")
    print(f"  Duration: {int(dur//60)}m {int(dur%60)}s  |  Size: {size_mb:.1f} MB")
else:
    print(f"✗ stitch failed:\n{r.stderr[-2000:]}")
