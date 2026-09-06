# FFmpeg 速查（手写命令时用；日常优先用 scripts/）

所有命令加 `-y` 覆盖输出；`-c:a copy` 在无音频输入时也安全。

## 看信息
```bash
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate:format=duration,size,bit_rate -of default=nw=1 in.mp4
```

## 裁时长
```bash
ffmpeg -y -ss 00:00:03.2 -to 00:00:41.0 -i in.mp4 -c:v libx264 -crf 18 -c:a aac out.mp4   # 精确
ffmpeg -y -ss 3 -i in.mp4 -t 30 -c copy out.mp4                                            # 快但只能在关键帧
```

## 加速（口播偏慢）
```bash
ffmpeg -y -i in.mp4 -filter_complex "[0:v]setpts=PTS/1.15[v];[0:a]atempo=1.15[a]" -map "[v]" -map "[a]" -c:v libx264 -crf 18 -c:a aac out.mp4
```

## 横转竖 9:16（1080×1920）
```bash
# 居中裁
ffmpeg -y -i in.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" -c:a copy out.mp4
# 模糊背景
ffmpeg -y -i in.mp4 -filter_complex "[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:2[bg];[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2" -c:a copy out.mp4
# 米白填充
ffmpeg -y -i in.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0xFBFAF7" -c:a copy out.mp4
```

## 720p 放大到 1080p（已有旧成片救急）
```bash
ffmpeg -y -i in720.mp4 -vf "scale=1080:1920:flags=lanczos,unsharp=5:5:0.5" -c:v libx264 -crf 18 -c:a copy out.mp4
```

## 静音检测（只看不剪）
```bash
ffmpeg -hide_banner -i in.mp4 -af "silencedetect=noise=-35dB:d=0.6" -f null - 2>&1 | grep silence_
```

## 字幕
```bash
# SRT 直接烧（字体按名字找；找不到会退回默认字体，中文可能变方块，所以优先用 burn_subs.py）
ffmpeg -y -i in.mp4 -vf "subtitles=subs.srt:fontsdir=/System/Library/Fonts/Supplemental:force_style='FontName=Songti SC,FontSize=22,Outline=2,MarginV=60'" -c:a copy out.mp4
# ASS（PlayResX/Y 与画面一致时字号就是像素）
ffmpeg -y -i in.mp4 -vf "ass=subs.ass:fontsdir=/System/Library/Fonts/Supplemental" -c:a copy out.mp4
```

## 画面上叠一行字（价格角标、来源）
```bash
ffmpeg -y -i in.mp4 -vf "drawtext=fontfile=/System/Library/Fonts/Supplemental/Songti.ttc:text='早鸟价 ¥9.9':fontsize=64:fontcolor=white:borderw=3:bordercolor=0x14161A:x=(w-text_w)/2:y=h-700" -c:a copy out.mp4
```

## 抽帧 / 封面
```bash
ffmpeg -y -ss 12.5 -i in.mp4 -frames:v 1 -vf "scale=1242:1656:force_original_aspect_ratio=increase,crop=1242:1656" cover.png
ffmpeg -y -i in.mp4 -vf "fps=1/2,scale=270:-2,tile=4x4" -frames:v 1 contact.jpg
```

## 拼接
```bash
printf "file '%s'\n" a.mp4 b.mp4 c.mp4 > list.txt
ffmpeg -y -f concat -safe 0 -i list.txt -c copy out.mp4      # 要求各段编码参数一致，否则用 concat.py
```

## 音频
```bash
ffmpeg -y -i in.mp4 -af "loudnorm=I=-16:TP=-1.5:LRA=11" -c:v copy -c:a aac -b:a 192k out.mp4   # 响度归一
ffmpeg -y -i video.mp4 -i vo.m4a -map 0:v -map 1:a -c:v copy -c:a aac -shortest out.mp4        # 换配音
ffmpeg -y -i video.mp4 -i bgm.mp3 -filter_complex "[1:a]volume=0.2[b];[0:a][b]amix=inputs=2:duration=first" -c:v copy -c:a aac out.mp4   # 叠 BGM
ffmpeg -y -i in.mp4 -af "afade=t=in:d=0.3,afade=t=out:st=29.5:d=0.5" -c:v copy -c:a aac out.mp4   # 淡入淡出
ffmpeg -y -i in.mp4 -an out.mp4                                                                   # 去声
```

## 局部放大（演示关键处）
```bash
# 从 10s 到 14s 把画面放大 1.6 倍聚焦左上区域
ffmpeg -y -i in.mp4 -vf "zoompan=z='if(between(in_time,10,14),1.6,1)':x='iw*0.15':y='ih*0.2':d=1:s=1080x1920:fps=30" -c:a copy out.mp4
```

## 最终导出（等价于 xhs_export.py 默认）
```bash
ffmpeg -y -i in.mp4 -vf "fps=30,format=yuv420p" -c:v libx264 -profile:v high -level 4.1 -preset slow -crf 19 -maxrate 12M -bufsize 24M -af "loudnorm=I=-16:TP=-1.5:LRA=11" -c:a aac -b:a 192k -ar 48000 -movflags +faststart out.mp4
```
