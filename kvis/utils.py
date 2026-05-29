import sys
import os
import re
import json
import time
import pickle
from pathlib import Path
from datetime import datetime

from .constants import (
    CHECKPOINT_FILE, TRANSCRIPTS_DIR, AUDIO_DIR, CACHE_DIR,
    ANALYSIS_DIR, DATA_DIR,
)


def save_spectral_cache(video_id, features):
    cache_path = CACHE_DIR / f"{video_id}_spectral.pkl"
    with open(cache_path, 'wb') as f:
        pickle.dump(features, f)


def load_spectral_cache(video_id):
    cache_path = CACHE_DIR / f"{video_id}_spectral.pkl"
    if cache_path.exists():
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            pass
    return None


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"videos": [], "version": "3.8"}


def save_checkpoint(data):
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_video_id(url_or_id):
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    patterns = [
        r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return url_or_id


def fix_encoding(text):
    fixes = {
        '\u00c3\u00a1': 'á', '\u00c3\u00a9': 'é', '\u00c3\u00ad': 'í',
        '\u00c3\u00b3': 'ó', '\u00c3\u00ba': 'ú', '\u00c3\u00b1': 'ñ',
        '\u00c3\u00bc': 'ü', 'â€™': "'", 'â€œ': '"', 'â€': '"',
        'â€"': "'", 'â€¢': '•',
    }
    for bad, good in fixes.items():
        text = text.replace(bad, good)
    return text


def normalize_text(text):
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text


def parse_srt_to_text(srt_content):
    lines = srt_content.split('\n')
    clean = []
    prev = ''
    for line in lines:
        line = line.strip()
        if not line or re.match(r'^\d+$', line):
            continue
        if re.match(r'^\d{2}:\d{2}:\d{2},\d{3}\s*-->', line):
            continue
        if line != prev:
            clean.append(line)
            prev = line
    return ' '.join(clean)


def parse_json3_to_text(data):
    if not isinstance(data, dict) or 'events' not in data:
        return None
    parts = []
    for event in data['events']:
        if 'segs' in event:
            text = ''.join(seg.get('utf8', '') for seg in event['segs'] if seg.get('utf8', '').strip())
            if text.strip():
                parts.append(text)
    return ' '.join(parts)


def parse_srt_blocks(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    blocks = re.split(r'\n\n+', content.strip())
    subs = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})', lines[1])
            if match:
                g = match.groups()
                start = int(g[0])*3600 + int(g[1])*60 + int(g[2]) + int(g[3])/1000
                end = int(g[4])*3600 + int(g[5])*60 + int(g[6]) + int(g[7])/1000
                text = ' '.join(lines[2:]).strip()
                if text:
                    subs.append({'start': round(start,2), 'end': round(end,2), 'text': text})
    return subs


def find_srt(vid):
    candidates = sorted(TRANSCRIPTS_DIR.glob(f"{vid}*.srt"),
                        key=lambda x: x.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def parse_timestamped_txt(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    subs = []
    for line in lines:
        m = re.match(r'\[(\d+\.?\d*)s\s*-\s*(\d+\.?\d*)s\]\s*(.*)', line.strip())
        if m:
            subs.append({
                'start': round(float(m.group(1)), 2),
                'end': round(float(m.group(2)), 2),
                'text': m.group(3).strip(),
            })
    return subs


def find_subs(vid):
    srt_path = find_srt(vid)
    if srt_path:
        return parse_srt_blocks(srt_path), 'srt'
    ts_path = TRANSCRIPTS_DIR / f"{vid}_timestamped.txt"
    if ts_path.exists():
        subs = parse_timestamped_txt(ts_path)
        if subs:
            return subs, 'timestamped'
    return None, None


def find_audio(vid):
    cp = CHECKPOINT_FILE
    if cp.exists():
        with open(cp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for v in data.get('videos', []):
            if v['video_id'] == vid and 'audio_file' in v:
                path = AUDIO_DIR / v['audio_file']
                if path.exists():
                    return path
    for f in AUDIO_DIR.iterdir():
        if vid in f.name and f.suffix == '.mp3':
            return f
    mp3s = sorted(AUDIO_DIR.glob('*.mp3'))
    if cp.exists():
        with open(cp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for i, v in enumerate(data.get('videos', [])):
            if v['video_id'] == vid and i < len(mp3s):
                return mp3s[i]
    return None


def freq_to_note(freq):
    import numpy as np
    notes = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    if freq <= 0:
        return '?'
    midi = 12 * np.log2(freq / 440.0) + 69
    return notes[int(round(midi)) % 12] + str(int(round(midi) / 12) - 1)
