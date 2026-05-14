# dedup-overlap.skill

用于把多段视频按顺序拼接成一个完整视频，并自动删除相邻视频之间多余的重复定格帧。

这个工具适合处理下面这种视频结构：

```text
上一段视频结尾 100 帧 ≈ 下一段视频开头 100 帧
```

如果直接拼接，会出现明显的定格、卡顿或重复画面。这个脚本会先识别拼接处的静态重复区，把多余重复帧剪掉，再合成一个完整视频。

## 功能

- 只扫描拼接点附近，不扫描整条视频。
- 支持 30、60、100 等不同数量的重复帧。
- 优先检测静态重复区，而不是直接找最相似帧。
- 如果没有检测到可靠静态区，会自动退回到最相似帧匹配。
- 视频和音频会一起裁剪，尽量保持音画同步。
- 会输出 JSON 日志，记录每个拼接点具体剪了多少帧。

## 环境要求

需要安装：

- Python 3
- FFmpeg
- OpenCV 和 NumPy

安装 Python 依赖：

```bash
python3 -m pip install opencv-python numpy
```

确认 FFmpeg 可用：

```bash
ffmpeg -version
```

## 使用方法

进入仓库目录：

```bash
cd dedup-overlap.skill
```

执行：

```bash
python3 scripts/dedup_overlap.py "/path/to/tenet_outputs" \
  --pattern "P*_tenet.mp4" \
  --repeat_frames 100 \
  --output "/path/to/tenet_outputs/final_dedup_merged.mp4"
```

示例：

```bash
python3 scripts/dedup_overlap.py "/Users/chengbowen/Documents/Codex/video_test/tenet_outputs" \
  --pattern "P*_tenet.mp4" \
  --repeat_frames 100 \
  --output "/Users/chengbowen/Documents/Codex/video_test/tenet_outputs/P01-P14_tenet_dedup_100f_merged.mp4"
```

## 输入视频要求

输入文件夹里放按顺序排列的视频，例如：

```text
P01_tenet.mp4
P02_tenet.mp4
P03_tenet.mp4
P04_tenet.mp4
...
```

脚本会根据文件名里的数字自然排序。

默认匹配规则：

```text
--pattern "P*_tenet.mp4"
```

如果你的视频名字不同，可以改这个参数。

## 输出文件

脚本会生成：

```text
final_dedup_merged.mp4
final_dedup_merged.json
```

其中：

```text
final_dedup_merged.mp4
```

是最终合成视频。

```text
final_dedup_merged.json
```

是拼接日志，记录每个拼接点的处理结果。

日志示例：

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

字段说明：

```text
prev:
  前一段视频

next:
  后一段视频

method:
  使用的剪切方法
  static-zone 表示检测到了静态重复区
  best-pair 表示没有检测到静态区，退回到最相似帧匹配

prev_keep_frame:
  前一段视频保留到哪一帧

next_start_frame:
  后一段视频从哪一帧开始保留

removed_prev_tail_frames:
  前一段视频尾部删除了多少帧

removed_next_head_frames:
  后一段视频头部删除了多少帧

best_mad:
  最相似帧的平均像素差，数值越小越相似
```

## 核心算法

对于每一对相邻视频：

```text
prev = 当前视频
next = 下一个视频
```

脚本只读取：

```text
prev 最后 repeat_frames 帧
next 开头 repeat_frames 帧
```

例如 `repeat_frames = 100` 时：

```text
读取前一段视频最后 100 帧
读取后一段视频开头 100 帧
```

每一帧会先做预处理：

```text
1. 转成灰度图
2. 缩放到 180x320
```

然后计算相邻帧差异：

```text
diff = mean(abs(frame_i - frame_i+1))
```

如果连续多帧的差异都很小，就认为这是定格重复区。

默认参数：

```text
repeat_frames = 100
static_threshold = 0.8
min_static_run = 10
resize_width = 180
resize_height = 320
```

处理优先级：

```text
1. 优先检测静态重复区，并删除完整重复区。
2. 如果静态区检测失败，再用最相似帧兜底。
```

这样做的原因是：

```text
100 帧重复帧里很多画面都非常像。
如果只找最相似帧，可能会选到重复区中间。
这样拼接后仍然会残留一段定格画面。
```

所以这个脚本不是简单找最相似帧，而是优先把完整的静态重复区剪掉。

## 参数说明

```text
input_dir
  输入视频所在文件夹

--pattern
  输入视频匹配规则
  默认：P*_tenet.mp4

--output
  输出视频路径
  默认：dedup_overlap_merged.mp4

--log
  输出 JSON 日志路径
  默认：和输出视频同名

--repeat_frames
  拼接点检查窗口大小
  默认：100

--static_threshold
  判断静态帧的差异阈值
  默认：0.8

--min_static_run
  至少连续多少个相邻帧差异很小，才认为是静态区
  默认：10

--resize_width
  分析时缩放宽度
  默认：180

--resize_height
  分析时缩放高度
  默认：320
```

## 推荐命令模板

100 帧重复帧：

```bash
python3 scripts/dedup_overlap.py "/path/to/tenet_outputs" \
  --pattern "P*_tenet.mp4" \
  --repeat_frames 100 \
  --output "/path/to/tenet_outputs/final_merged.mp4"
```

60 帧重复帧：

```bash
python3 scripts/dedup_overlap.py "/path/to/tenet_outputs" \
  --pattern "P*_tenet.mp4" \
  --repeat_frames 60 \
  --output "/path/to/tenet_outputs/final_merged.mp4"
```

30 帧重复帧：

```bash
python3 scripts/dedup_overlap.py "/path/to/tenet_outputs" \
  --pattern "P*_tenet.mp4" \
  --repeat_frames 30 \
  --output "/path/to/tenet_outputs/final_merged.mp4"
```

## 注意事项

1. 输入视频帧率要一致。
2. 输入视频最好已经按顺序命名。
3. 建议用帧号裁剪，不要只用秒数裁剪。
4. 如果某个拼接点仍然卡顿，可以查看 JSON 日志里的剪切位置。
5. 如果视频命名不是 `P01_tenet.mp4` 这种格式，需要修改 `--pattern`。
6. 如果重复帧不是 100 帧，需要修改 `--repeat_frames`。

## 适用场景

适合：

```text
AI 视频分段生成
DreamFace 输出后的视频拼接
正倒视频 tenet 拼接后的多段合成
相邻视频首尾有重复定格帧的场景
```

不适合：

```text
两个完全不同的视频硬拼
没有任何重复帧区域的视频
帧率不一致且未提前统一的视频
```

