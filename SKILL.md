---
name: dedup-overlap.skill
description: "Deduplicate and concatenate ordered video segments with repeated boundary freeze frames. Use when videos have duplicated overlap frames at joins, such as prev tail 100 frames matching next head 100 frames, and the goal is to remove static duplicate frames before merging into one smooth video."
---

# dedup-overlap.skill

This skill removes repeated freeze-frame overlap between ordered video segments and concatenates them into one output video.

Typical input:

```text
P01_tenet.mp4
P02_tenet.mp4
P03_tenet.mp4
...
```

Typical repeated-frame structure:

```text
prev video tail 100 frames ~= next video head 100 frames
```

## Core Rule

Do not use best-frame matching as the first strategy.

Priority:

```text
1. Detect static duplicate zones in prev tail and next head.
2. If both static zones are found, remove the full static duplicate zones.
3. If static zones are not reliable, fall back to best matching frame pair.
```

This avoids picking a frame in the middle of a freeze zone and leaving visible stutter in the final video.

## Script

Use the bundled script:

```bash
python3 scripts/dedup_overlap.py INPUT_DIR --output OUTPUT.mp4
```

GitHub usage after cloning this repository:

```bash
cd dedup-overlap.skill
python3 -m pip install opencv-python numpy
python3 scripts/dedup_overlap.py "/path/to/tenet_outputs" \
  --pattern "P*_tenet.mp4" \
  --repeat_frames 100 \
  --output "/path/to/tenet_outputs/final_dedup_merged.mp4"
```

Common command:

```bash
python3 scripts/dedup_overlap.py "/path/to/tenet_outputs" \
  --pattern "P*_tenet.mp4" \
  --repeat_frames 100 \
  --output "/path/to/tenet_outputs/final_dedup_merged.mp4"
```

## Default Parameters

```text
repeat_frames = 100
static_threshold = 0.8
min_static_run = 10
resize_width = 180
resize_height = 320
similarity_method = MAD
```

`MAD` means:

```text
mean(abs(frame_a - frame_b))
```

Lower score means more similar.

## Algorithm

For each adjacent pair:

```text
prev = videos[i]
next = videos[i + 1]
```

Read:

```text
prev_tail = last repeat_frames frames of prev
next_head = first repeat_frames frames of next
```

Preprocess:

```text
convert to grayscale
resize to 180x320
```

Detect static zones:

```text
prev_diffs[i] = mean(abs(prev_tail[i] - prev_tail[i + 1]))
next_diffs[i] = mean(abs(next_head[i] - next_head[i + 1]))
```

For `prev_tail`, scan backward to find the static suffix start.

For `next_head`, scan forward to find the static prefix end.

If both are found:

```text
prev_keep_frame = prev_tail_global_start + prev_static_start
next_start_frame = next_static_end + 1
```

Otherwise, fall back to all-pairs matching inside the two 100-frame windows:

```text
prev_keep_frame = best_prev_frame
next_start_frame = best_next_frame + 1
```

## Output Log

The script writes a JSON log next to the output video unless `--log` is provided.

Each join records:

```json
{
  "prev": "P01_tenet.mp4",
  "next": "P02_tenet.mp4",
  "method": "static-zone",
  "prev_keep_frame": 800,
  "next_start_frame": 100,
  "removed_prev_tail_frames": 99,
  "removed_next_head_frames": 100,
  "best_mad": 1.725
}
```

## Validation

After running, verify:

```bash
ffprobe -v error -show_entries stream=index,codec_type,duration,nb_frames \
  -of default=noprint_wrappers=1 output.mp4
```

The output should:

- Have one video stream.
- Preserve audio when inputs have audio.
- Have frame count equal to the sum of all kept frame ranges.
- Avoid long static runs at joins.
