# dedup-overlap.skill

Remove repeated overlap freeze frames between ordered video segments and concatenate them into one smooth video.

This tool is designed for workflows where adjacent generated video clips intentionally share repeated boundary frames, for example:

```text
previous clip tail 100 frames ~= next clip head 100 frames
```

If these clips are directly concatenated, the join may show a visible freeze or stutter. This script detects the duplicated static zone and removes it before merging.

## Features

- Scans only the join window, not the whole video.
- Supports repeated overlap windows such as 30, 60, or 100 frames.
- Prioritizes static-zone detection over simple best-frame matching.
- Falls back to best matching frame pair when no reliable static zone is found.
- Preserves audio by trimming audio to the same kept frame ranges.
- Writes a JSON log with every join decision.

## Requirements

- Python 3
- FFmpeg available in `PATH`
- Python packages:

```bash
python3 -m pip install opencv-python numpy
```

## Usage

```bash
python3 scripts/dedup_overlap.py "/path/to/tenet_outputs" \
  --pattern "P*_tenet.mp4" \
  --repeat_frames 100 \
  --output "/path/to/tenet_outputs/final_dedup_merged.mp4"
```

Example:

```bash
python3 scripts/dedup_overlap.py "/Users/chengbowen/Documents/Codex/video_test/tenet_outputs" \
  --pattern "P*_tenet.mp4" \
  --repeat_frames 100 \
  --output "/Users/chengbowen/Documents/Codex/video_test/tenet_outputs/P01-P14_tenet_dedup_100f_merged.mp4"
```

## Inputs

The input directory should contain ordered video clips, for example:

```text
P01_tenet.mp4
P02_tenet.mp4
P03_tenet.mp4
...
```

Files are sorted naturally by the numbers in their names.

## Output

The script writes:

```text
final_dedup_merged.mp4
final_dedup_merged.json
```

The JSON log includes:

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

## Algorithm

For each adjacent pair:

```text
prev = current clip
next = next clip
```

The script reads:

```text
prev tail repeat_frames
next head repeat_frames
```

Each frame is converted to grayscale and resized to `180x320`.

Then it detects static zones using:

```text
diff = mean(abs(frame_i - frame_i+1))
```

Default parameters:

```text
repeat_frames = 100
static_threshold = 0.8
min_static_run = 10
resize_width = 180
resize_height = 320
```

Priority:

```text
1. Detect static duplicate zones and remove the full duplicate region.
2. If static-zone detection fails, fall back to best-frame matching by MAD.
```

This avoids choosing a frame in the middle of a freeze zone and leaving visible stutter in the output.

## CLI Options

```text
input_dir                  Directory containing input videos
--pattern                  Glob pattern for input videos, default: P*_tenet.mp4
--output                   Output video path, default: dedup_overlap_merged.mp4
--log                      JSON log path, default: same name as output
--repeat_frames            Join window size, default: 100
--static_threshold         Static frame difference threshold, default: 0.8
--min_static_run           Minimum consecutive static diffs, default: 10
--resize_width             Analysis resize width, default: 180
--resize_height            Analysis resize height, default: 320
```

## Notes

- Use frame-based trimming for stable results.
- Keep all input videos at the same frame rate.
- FFmpeg is required for video/audio trimming and final concatenation.
- This tool is especially useful after AI video generation, where repeated boundary frames are inserted to improve cross-segment continuity.

