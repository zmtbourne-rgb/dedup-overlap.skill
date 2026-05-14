#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np


def run(cmd):
    subprocess.run(cmd, check=True)


def natural_key(path: Path):
    nums = re.findall(r"\d+", path.name)
    return [int(n) for n in nums] if nums else [path.name]


def probe_video(path: Path):
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,nb_frames,duration",
            "-of",
            "json",
            str(path),
        ],
        text=True,
    )
    stream = json.loads(out)["streams"][0]
    num, den = stream["r_frame_rate"].split("/")
    fps = float(num) / float(den)
    frames = int(stream.get("nb_frames") or round(float(stream["duration"]) * fps))
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps": fps,
        "frames": frames,
        "duration": float(stream.get("duration", frames / fps)),
    }


def load_gray_window(path: Path, start: int, count: int, resize_width: int, resize_height: int):
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    frames = []
    for offset in range(count):
        ok, frame = cap.read()
        if not ok:
            cap.release()
            raise RuntimeError(f"Cannot read frame {start + offset} from {path}")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames.append(cv2.resize(gray, (resize_width, resize_height), interpolation=cv2.INTER_AREA))
    cap.release()
    return frames


def mad(a, b):
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def consecutive_diffs(frames):
    return [mad(frames[i], frames[i + 1]) for i in range(len(frames) - 1)]


def static_suffix_start(diffs, threshold: float, min_run: int):
    run_len = 0
    first_diff = None
    for idx in range(len(diffs) - 1, -1, -1):
        if diffs[idx] <= threshold:
            run_len += 1
            first_diff = idx
        else:
            break
    if run_len >= min_run and first_diff is not None:
        return first_diff
    return None


def static_prefix_end(diffs, threshold: float, min_run: int):
    run_len = 0
    last_diff = None
    for idx, value in enumerate(diffs):
        if value <= threshold:
            run_len += 1
            last_diff = idx
        else:
            break
    if run_len >= min_run and last_diff is not None:
        return last_diff + 1
    return None


def best_pair(prev_frames, next_frames):
    best = None
    for i, prev in enumerate(prev_frames):
        for j, nxt in enumerate(next_frames):
            score = mad(prev, nxt)
            if best is None or score < best[0]:
                best = (score, i, j)
    return best


def boundary_plan(prev_path: Path, next_path: Path, prev_count: int, args):
    prev_start = max(0, prev_count - args.repeat_frames)
    prev_count_window = min(args.repeat_frames, prev_count - prev_start)
    next_count_window = args.repeat_frames

    prev_frames = load_gray_window(prev_path, prev_start, prev_count_window, args.resize_width, args.resize_height)
    next_frames = load_gray_window(next_path, 0, next_count_window, args.resize_width, args.resize_height)

    best_mad, best_prev_local, best_next_local = best_pair(prev_frames, next_frames)
    prev_diffs = consecutive_diffs(prev_frames)
    next_diffs = consecutive_diffs(next_frames)

    prev_static_local = static_suffix_start(prev_diffs, args.static_threshold, args.min_static_run)
    next_static_end = static_prefix_end(next_diffs, args.static_threshold, args.min_static_run)

    if prev_static_local is not None and next_static_end is not None:
        prev_keep = prev_start + prev_static_local
        next_start = next_static_end + 1
        method = "static-zone"
    else:
        prev_keep = prev_start + best_prev_local
        next_start = best_next_local + 1
        method = "best-pair"

    return {
        "method": method,
        "prev_keep_frame": prev_keep,
        "next_start_frame": next_start,
        "removed_prev_tail_frames": prev_count - 1 - prev_keep,
        "removed_next_head_frames": next_start,
        "best_prev_frame": prev_start + best_prev_local,
        "best_next_frame": best_next_local,
        "best_mad": best_mad,
        "prev_static_start_frame": None if prev_static_local is None else prev_start + prev_static_local,
        "next_static_end_frame": next_static_end,
    }


def cut_clip(video: Path, start: int, end: int, fps: float, clip: Path):
    start_t = start / fps
    end_t = (end + 1) / fps
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            f"select='between(n,{start},{end})',setpts=N/FRAME_RATE/TB",
            "-af",
            f"atrim=start={start_t:.9f}:end={end_t:.9f},asetpts=N/SR/TB",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-colorspace",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(clip),
        ]
    )


def concat_clips(clips, output: Path):
    list_file = output.parent / f".{output.stem}_concat.txt"
    list_file.write_text("".join(f"file '{clip}'\n" for clip in clips), encoding="utf-8")
    try:
        run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(output),
            ]
        )
    finally:
        try:
            list_file.unlink()
        except FileNotFoundError:
            pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Remove repeated overlap freeze frames between ordered videos and concatenate them."
    )
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--pattern", default="P*_tenet.mp4")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--repeat_frames", type=int, default=100)
    parser.add_argument("--static_threshold", type=float, default=0.8)
    parser.add_argument("--min_static_run", type=int, default=10)
    parser.add_argument("--resize_width", type=int, default=180)
    parser.add_argument("--resize_height", type=int, default=320)
    return parser.parse_args()


def main():
    args = parse_args()
    input_dir = args.input_dir.resolve()
    videos = sorted(input_dir.glob(args.pattern), key=natural_key)
    if len(videos) < 2:
        raise SystemExit(f"Need at least two videos matching {args.pattern} in {input_dir}")

    output = args.output or (input_dir / "dedup_overlap_merged.mp4")
    output = output.resolve()
    log_path = args.log or output.with_suffix(".json")

    infos = [probe_video(video) for video in videos]
    fps_values = [info["fps"] for info in infos]
    if max(fps_values) - min(fps_values) > 0.01:
        raise RuntimeError(f"FPS mismatch: {fps_values}")
    fps = fps_values[0]

    starts = [0 for _ in videos]
    ends = [info["frames"] - 1 for info in infos]
    joins = []

    print("Inputs:")
    for video, info in zip(videos, infos):
        print(f"  {video.name}: fps={info['fps']:.6f}, frames={info['frames']}")

    print("\nBoundaries:")
    for idx in range(len(videos) - 1):
        plan = boundary_plan(videos[idx], videos[idx + 1], infos[idx]["frames"], args)
        ends[idx] = plan["prev_keep_frame"]
        starts[idx + 1] = plan["next_start_frame"]
        join = {
            "prev": videos[idx].name,
            "next": videos[idx + 1].name,
            **plan,
        }
        joins.append(join)
        print(
            f"  {join['prev']}->{join['next']}: method={join['method']}, "
            f"keep_prev={join['prev_keep_frame']}, start_next={join['next_start_frame']}, "
            f"remove_prev={join['removed_prev_tail_frames']}, "
            f"remove_next={join['removed_next_head_frames']}, MAD={join['best_mad']:.4f}"
        )

    ranges = []
    print("\nCut plan:")
    for video, start, end in zip(videos, starts, ends):
        if end < start:
            raise RuntimeError(f"Invalid cut for {video.name}: {start}-{end}")
        ranges.append({"video": video.name, "start_frame": start, "end_frame": end, "frames": end - start + 1})
        print(f"  {video.name}: keep frames {start}-{end} ({end - start + 1} frames)")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dedup_overlap_", dir="/private/tmp") as tmp:
        tmp_path = Path(tmp)
        clips = []
        for idx, (video, start, end) in enumerate(zip(videos, starts, ends)):
            clip = tmp_path / f"clip_{idx:03d}.mp4"
            cut_clip(video, start, end, fps, clip)
            clips.append(clip)
        concat_clips(clips, output)

    result = {
        "input_dir": str(input_dir),
        "pattern": args.pattern,
        "output": str(output),
        "repeat_frames": args.repeat_frames,
        "static_threshold": args.static_threshold,
        "min_static_run": args.min_static_run,
        "resize": [args.resize_width, args.resize_height],
        "fps": fps,
        "inputs": [{"path": str(video), **info} for video, info in zip(videos, infos)],
        "joins": joins,
        "ranges": ranges,
        "total_output_frames_expected": sum(item["frames"] for item in ranges),
    }
    log_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nWrote video: {output}")
    print(f"Wrote log:   {log_path}")


if __name__ == "__main__":
    main()
