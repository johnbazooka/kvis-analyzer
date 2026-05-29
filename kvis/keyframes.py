import os
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime

from .constants import KEYFRAMES_DIR, TRANSCRIPTS_DIR, ANALYSIS_DIR
from .utils import extract_video_id, load_checkpoint, save_checkpoint

def do_keyframes(url, mode='scene', fps=0.5, max_frames=30, threshold=0.3):
    video_id = extract_video_id(url)
    url = url if 'http' in url else f"https://youtu.be/{video_id}"
    out_dir = KEYFRAMES_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"KVIS KEYFRAMES | {video_id} | mode={mode}")
    print(f"  Descargando video (240p para velocidad)...")

    video_path = out_dir / "_source.mp4"
    try:
        import yt_dlp
        opts = {
            'format': 'worst[height<=360]/worst',
            'outtmpl': str(out_dir / '_source.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        mp4_candidates = list(out_dir.glob('_source.*'))
        if not mp4_candidates:
            print("  Error: no se descargo el video")
            return None
        video_path = mp4_candidates[0]
    except Exception as e:
        print(f"  Error descargando: {e}")
        return None

    print(f"  Video: {video_path.name} ({video_path.stat().st_size / 1024 / 1024:.1f} MB)")

    probe_cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', str(video_path),
    ]
    try:
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, encoding='utf-8')
        probe_data = json.loads(probe_result.stdout)
        duration = float(probe_data.get('format', {}).get('duration', 0))
        width = 0
        for stream in probe_data.get('streams', []):
            if stream.get('codec_type') == 'video':
                width = int(stream.get('width', 0))
                break
    except Exception:
        duration = 0
        width = 0

    print(f"  Duracion: {duration:.0f}s | Ancho: {width}px")

    if mode == 'scene':
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-vf', f"select='gt(scene,{threshold})',showinfo",
            '-vsync', 'vfr',
            '-frames:v', str(max_frames),
            '-q:v', '3',
            str(out_dir / 'frame_%03d.jpg'),
        ]
        label = f"scene detection (threshold={threshold})"
    else:
        interval = 1.0 / fps
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-vf', f"fps={fps}",
            '-frames:v', str(max_frames),
            '-q:v', '3',
            str(out_dir / 'frame_%03d.jpg'),
        ]
        label = f"interval ({fps} fps, 1 frame/{interval:.1f}s)"

    print(f"  Extrayendo keyframes: {label}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    except Exception as e:
        print(f"  Error ffmpeg: {e}")
        return None
    finally:
        try:
            video_path.unlink()
        except Exception:
            pass

    frames = sorted(out_dir.glob('frame_*.jpg'))
    if not frames:
        print("  Sin keyframes extraidos. Prueba con --threshold mas bajo.")
        return None

    if len(frames) > max_frames:
        for extra in frames[max_frames:]:
            extra.unlink()
        frames = frames[:max_frames]

    timestamps = []
    if duration > 0:
        step = duration / (len(frames) + 1)
        timestamps = [round(step * (i + 1), 1) for i in range(len(frames))]

    index_data = {
        'video_id': video_id,
        'url': url,
        'total_frames': len(frames),
        'mode': mode,
        'duration': duration,
        'extracted_at': datetime.now().isoformat(),
        'frames': [],
    }

    for i, f in enumerate(frames):
        ts = timestamps[i] if i < len(timestamps) else 0
        yt_ts = f"https://youtu.be/{video_id}?t={int(ts)}"
        frame_info = {
            'file': f.name,
            'timestamp': ts,
            'youtube_url': yt_ts,
            'size_kb': round(f.stat().st_size / 1024, 1),
        }
        index_data['frames'].append(frame_info)

    index_path = out_dir / "keyframes_index.json"
    with open(index_path, 'w', encoding='utf-8') as fj:
        json.dump(index_data, fj, indent=2, ensure_ascii=False)

    checkpoint = load_checkpoint()
    for v in checkpoint['videos']:
        if v['video_id'] == video_id:
            v['keyframes'] = len(frames)
    save_checkpoint(checkpoint)

    print(f"\n  {len(frames)} keyframes extraidos:")
    for i, fr in enumerate(index_data['frames']):
        print(f"    [{i+1:2d}] {fr['timestamp']:6.1f}s | {fr['size_kb']:5.1f}KB | {fr['youtube_url']}")

    print(f"\n  Indice: {index_path}")
    return index_data


def do_describe_keyframes(video_id):
    from PIL import Image
    import numpy as np

    kf_dir = KEYFRAMES_DIR / video_id
    if not kf_dir.exists():
        print(f"KVIS DESCRIBE | Sin keyframes para {video_id}")
        return None

    index_path = kf_dir / "keyframes_index.json"
    if not index_path.exists():
        print(f"KVIS DESCRIBE | Sin indice de keyframes. Ejecuta 'keyframes' primero.")
        return None

    with open(index_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f)

    print(f"KVIS DESCRIBE | {video_id} | {index_data['total_frames']} keyframes")
    print("=" * 60)

    descriptions = []
    for frame_info in index_data.get('frames', []):
        frame_path = kf_dir / frame_info['file']
        if not frame_path.exists():
            continue

        img = Image.open(frame_path).convert('RGB')
        arr = np.array(img)

        brightness = arr.mean()
        contrast = arr.std()
        r, g, b = arr[:,:,0].mean(), arr[:,:,1].mean(), arr[:,:,2].mean()
        dominant = 'dark' if brightness < 64 else 'dim' if brightness < 128 else 'bright' if brightness > 192 else 'normal'
        color_bias = 'warm' if r > b + 20 else 'cool' if b > r + 20 else 'neutral'

        edges = 0
        if arr.shape[0] > 2 and arr.shape[1] > 2:
            gray = np.mean(arr, axis=2)
            dx = np.abs(np.diff(gray, axis=1)).mean()
            dy = np.abs(np.diff(gray, axis=0)).mean()
            edges = (dx + dy) / 2

        complexity = 'simple' if edges < 15 else 'detailed' if edges > 35 else 'moderate'

        desc = {
            'file': frame_info['file'],
            'timestamp': frame_info['timestamp'],
            'width': img.width,
            'height': img.height,
            'brightness': round(brightness, 1),
            'contrast': round(contrast, 1),
            'rgb_mean': [round(r, 1), round(g, 1), round(b, 1)],
            'dominant': dominant,
            'color_bias': color_bias,
            'edge_complexity': round(edges, 1),
            'complexity': complexity,
            'label': f"{dominant}/{color_bias}/{complexity}",
        }
        descriptions.append(desc)

