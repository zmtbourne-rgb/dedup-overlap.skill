---
name: dedup-overlap.skill
description: "按顺序拼接多段视频，并删除相邻片段之间的重复定格帧。适合 prev 尾部 N 帧和 next 开头 N 帧重复的场景，支持自动检测 auto 和严格删除完整重复区 strict 两种策略。"
---

# dedup-overlap.skill

这个 skill 用于把多段视频按顺序拼接成一个完整视频，并删除相邻视频之间多余的重复定格帧。

典型输入：

```text
P01_tenet.mp4
P02_tenet.mp4
P03_tenet.mp4
...
```

典型重复帧结构：

```text
prev video tail 100 frames ~= next video head 100 frames
```

## 两种策略

### auto

默认策略，适合重复帧数量不完全稳定的情况。

```text
1. 读取上一段尾部 repeat_frames 帧和下一段开头 repeat_frames 帧。
2. 优先检测静态重复区。
3. 如果静态区可靠，就删除检测到的静态区。
4. 如果静态区不可靠，就退回到最相似帧匹配。
```

### strict

严格删除完整重复区。适合你明确知道重复帧数量的情况，比如人为添加了 30、80、100 帧定格重复帧。

```text
每个拼接点固定删除：
上一段视频尾部 repeat_frames 帧
下一段视频开头 repeat_frames 帧
```

例如 `repeat_frames=30`：

```text
part_01 尾部 30 帧删除
part_02 开头 30 帧删除
```

## 命令

默认自动检测：

```bash
python3 scripts/dedup_overlap.py INPUT_DIR \
  --pattern "P*_tenet.mp4" \
  --repeat_frames 100 \
  --output OUTPUT.mp4
```

严格删除完整重复区：

```bash
python3 scripts/dedup_overlap.py "/path/to/tenet_outputs" \
  --pattern "part_*_tenet.mp4" \
  --repeat_frames 30 \
  --strategy strict \
  --output "/path/to/tenet_outputs/final_dedup_merged_30f_strict.mp4"
```

## 安装依赖

```bash
python3 -m pip install opencv-python numpy
```

需要系统 PATH 里可以访问 `ffmpeg` 和 `ffprobe`。

## 参数

```text
input_dir = 输入视频文件夹
pattern = 输入视频匹配规则，默认 P*_tenet.mp4
output = 输出视频路径，默认 dedup_overlap_merged.mp4
log = 输出 JSON 日志路径，默认和输出视频同名
strategy = 去重策略，默认 auto，可选 auto / strict
repeat_frames = 100
static_threshold = 0.8
min_static_run = 10
resize_width = 180
resize_height = 320
```

`static_threshold`、`min_static_run`、`resize_width`、`resize_height` 只影响 `auto` 策略；`strict` 策略不做画面检测。

## 日志

脚本会在输出视频旁边写一个 JSON 日志。

每个拼接点会记录：

```json
{
  "prev": "part_01_tenet.mp4",
  "next": "part_02_tenet.mp4",
  "method": "strict-repeat",
  "prev_keep_frame": 869,
  "next_start_frame": 30,
  "removed_prev_tail_frames": 30,
  "removed_next_head_frames": 30,
  "output_join_time_sec": 29.0
}
```

## 验证

运行后可以用：

```bash
ffprobe -v error -show_entries stream=index,codec_type,duration,nb_frames \
  -of default=noprint_wrappers=1 output.mp4
```

检查最终视频是否有视频轨、音频轨、时长和帧数是否符合预期。
