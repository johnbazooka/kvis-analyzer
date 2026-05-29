import sys
import os
import re
import json
import time
from pathlib import Path
from datetime import datetime

from .constants import TRANSCRIPTS_DIR, ANALYSIS_DIR
from .utils import (
    extract_video_id, fix_encoding, normalize_text, load_checkpoint, save_checkpoint,
    parse_srt_to_text, parse_json3_to_text,
)


def get_video_info(url):
    try:
        import yt_dlp
        opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'extract_flat': False}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if info:
            return {
                'title': info.get('title', 'N/A'),
                'channel': info.get('channel', 'N/A'),
                'duration': info.get('duration', 0),
                'upload_date': info.get('upload_date', 'N/A'),
                'view_count': info.get('view_count', 0),
                'has_captions': _check_captions(info),
            }
    except Exception as e:
        print(f"  Warning: get_video_info error: {e}")
    return None


def _check_captions(info):
    manual = info.get('subtitles', {}) if info else {}
    auto = info.get('automatic_captions', {}) if info else {}
    has_manual = lambda d, prefix: any(l.startswith(prefix) for l in (d or {}))
    if has_manual(manual, 'es'):
        return 'es-manual'
    if has_manual(manual, 'en'):
        return 'en-manual'
    if has_manual(auto, 'es'):
        return 'es-auto'
    if has_manual(auto, 'en'):
        return 'en-auto'
    if manual or auto:
        return 'other'
    return None


def extract_with_transcript_api(video_id, lang='es'):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        for method in ['find_generated_transcript', 'find_transcript']:
            try:
                transcript = getattr(transcript_list, method)([lang])
                items = transcript.fetch()
                lines = []
                for item in items:
                    start = item.start
                    end = start + item.duration
                    lines.append(f"[{start:.1f}s - {end:.1f}s] {item.text}")
                text = '\n'.join(lines)
                plain = ' '.join(item.text for item in items)
                return text, plain, f'transcript-api ({method.split("_")[1]})'
            except Exception:
                continue
    except ImportError:
        pass
    return None, None, None


def extract_with_ytdlp(video_id, url, use_android=False):
    try:
        import yt_dlp
        base = str(TRANSCRIPTS_DIR / video_id)
        opts = {
            'quiet': True, 'no_warnings': True, 'skip_download': True,
            'writeautomaticsub': True, 'writesubtitles': True,
            'subtitleslangs': ['es', 'es-419', 'es-orig', 'en'],
            'subtitlesformat': 'srt', 'convertsubtitles': 'srt',
            'outtmpl': base, 'ignoreerrors': True,
        }
        if use_android:
            opts['extractor_args'] = {'youtube': {'player_client': ['android']}}

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        time.sleep(2)

        srt_files = sorted(TRANSCRIPTS_DIR.glob(f"{video_id}*.srt"),
                           key=lambda x: x.stat().st_mtime, reverse=True)
        if srt_files:
            with open(srt_files[0], 'r', encoding='utf-8') as f:
                text = parse_srt_to_text(f.read())
            meta = {
                'title': info.get('title', 'N/A') if info else 'N/A',
                'channel': info.get('channel', 'N/A') if info else 'N/A',
                'duration': info.get('duration', 0) if info else 0,
            }
            return text, text, f'yt-dlp ({"android" if use_android else "standard"})', meta

        json3_files = sorted(TRANSCRIPTS_DIR.glob(f"{video_id}*.json3"),
                             key=lambda x: x.stat().st_mtime, reverse=True)
        if json3_files:
            with open(json3_files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)
            text = parse_json3_to_text(data)
            if text:
                meta = {
                    'title': info.get('title', 'N/A') if info else 'N/A',
                    'channel': info.get('channel', 'N/A') if info else 'N/A',
                    'duration': info.get('duration', 0) if info else 0,
                }
                return text, text, 'yt-dlp (json3)', meta

    except ImportError:
        pass
    except Exception as e:
        print(f"  yt-dlp error: {e}")
    return None, None, None, None


def _split_into_paragraphs(text, max_para_chars=800):
    sentences = re.split(r'(?<=[.!?。])\s+', text)
    paragraphs, current = [], []
    length = 0
    for s in sentences:
        current.append(s)
        length += len(s) + 1
        if length >= max_para_chars:
            paragraphs.append(' '.join(current))
            current = []
            length = 0
    if current:
        paragraphs.append(' '.join(current))
    return paragraphs


def _detect_topic_changes(paragraphs):
    section_keywords = {
        'brainstorm': ['brainstorm', 'top line', 'topline', 'ideas', 'primer paso'],
        'composicion': ['composici', 'escribir', 'letra', 'melod', 'acorde', 'armon'],
        'grabacion': ['grabar', 'grabaci', 'voz', 'micro', 'cabina', 'vocal'],
        'comping': ['comping', 'toma', 'takes'],
        'produccion': ['producci', 'instrument', 'arreglo', 'timbre', 'mezcla', 'mix'],
        'mastering': ['master', 'masteriz', 'loudness', 'limiter'],
        'autotune': ['autotun', 'auto-tun', 'pitch', 'correcci'],
        'marketing': ['spotify', 'playlist', 'lanzamiento', 'promoci', 'redes'],
        'industria': ['discogr', 'warner', 'sello', 'contrato', 'label'],
        'tecnica': ['t\u00e9cnica', 'ecualiz', 'compresi', 'reverb', 'delay', 'efecto'],
    }
    sections = []
    current_topic = 'intro'
    current_paras = []
    for p in paragraphs:
        p_lower = p.lower()
        best_topic = current_topic
        best_score = 0
        for topic, keywords in section_keywords.items():
            score = sum(1 for kw in keywords if kw in p_lower)
            if score > best_score:
                best_score = score
                best_topic = topic
        if best_topic != current_topic and best_score >= 2:
            if current_paras:
                sections.append({'topic': current_topic, 'paragraphs': current_paras})
            current_topic = best_topic
            current_paras = [p]
        else:
            current_paras.append(p)
    if current_paras:
        sections.append({'topic': current_topic, 'paragraphs': current_paras})
    return sections


def _format_structured_transcript(text, video_id, info):
    text = re.sub(r'\[música\]', '[MUSICA]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[canto\]', '[CANTO]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[risas\]', '[RISAS]', text, flags=re.IGNORECASE)
    text = re.sub(r'\[(.*?)\]', r'[\1]', text)
    paragraphs = _split_into_paragraphs(text)
    sections = _detect_topic_changes(paragraphs)
    header = (
        f"Titulo: {info.get('title', 'N/A')}\n"
        f"Canal: {info.get('channel', 'N/A')}\n"
        f"Duracion: {info.get('duration', 0)}s\n"
        f"URL: https://youtu.be/{video_id}\n"
        f"{'=' * 60}\n\n"
    )
    formatted = []
    for sec in sections:
        formatted.append(f"## {sec['topic'].upper()}")
        formatted.append('')
        for p in sec['paragraphs']:
            formatted.append(p.strip())
            formatted.append('')
    return header + '\n'.join(formatted)


def _save_extract(video_id, url, timestamped, plain, method, info):
    info = info or {}
    plain = fix_encoding(normalize_text(plain))

    ts_path = TRANSCRIPTS_DIR / f"{video_id}_timestamped.txt"
    with open(ts_path, 'w', encoding='utf-8') as f:
        f.write(f"# KVIS v3.4 Transcript\n")
        f.write(f"# Video: {video_id}\n")
        f.write(f"# Titulo: {info.get('title', 'N/A')}\n")
        f.write(f"# Canal: {info.get('channel', 'N/A')}\n")
        f.write(f"# Metodo: {method}\n")
        f.write(f"# Fecha: {datetime.now().isoformat()}\n\n")
        f.write(timestamped or plain)

    clean_path = TRANSCRIPTS_DIR / f"{video_id}_clean.txt"
    structured = _format_structured_transcript(plain, video_id, info)
    with open(clean_path, 'w', encoding='utf-8') as f:
        f.write(structured)

    checkpoint = load_checkpoint()
    entry = {
        'video_id': video_id,
        'title': info.get('title', 'N/A'),
        'channel': info.get('channel', 'N/A'),
        'duration': info.get('duration', 0),
        'url': url,
        'method': method,
        'extracted_at': datetime.now().isoformat(),
        'chars': len(plain),
        'words': len(plain.split()),
        'transcript_file': clean_path.name,
        'analyzed': False,
    }
    existing = [v for v in checkpoint['videos'] if v['video_id'] == video_id]
    if existing:
        checkpoint['videos'] = [entry if v['video_id'] == video_id else v for v in checkpoint['videos']]
    else:
        checkpoint['videos'].append(entry)
    save_checkpoint(checkpoint)

    print(f"  OK: {method} | {len(plain.split())} palabras | {len(plain)} chars")
    print(f"  Guardado: {clean_path}")
    return clean_path


def do_extract(url, lang='es', force=False):
    video_id = extract_video_id(url)
    url = url if 'http' in url else f"https://youtu.be/{video_id}"
    print(f"KVIS EXTRACT | {video_id}")
    print(f"  URL: {url}")

    info = get_video_info(url)
    if info:
        print(f"  Titulo: {info['title']}")
        print(f"  Canal: {info['channel']}")
        print(f"  Duracion: {info['duration']}s")
        if info.get('has_captions') is None:
            print("  SKIP: Sin captions disponibles — pipeline abortado")
            return None
        elif '-auto' in (info.get('has_captions') or ''):
            print(f"  Captions: {info['has_captions']} (auto — puede fallar)")
        else:
            print(f"  Captions: {info['has_captions']}")

    if not force:
        print("  Intento 1: youtube-transcript-api...")
        timestamped, plain, method = extract_with_transcript_api(video_id, lang)
        if plain:
            if not info:
                print("  Metadata fallback: obteniendo via yt-dlp --dump-json...")
                info = get_video_info(url)
            return _save_extract(video_id, url, timestamped, plain, method, info)

    print("  Intento 2: yt-dlp standard...")
    timestamped, plain, method, yt_meta = extract_with_ytdlp(video_id, url)
    if plain:
        if not info and yt_meta:
            info = yt_meta
        elif info and yt_meta:
            for k in ('title', 'channel', 'duration'):
                if info.get(k) in (None, 'N/A', 0) and yt_meta.get(k) not in (None, 'N/A', 0):
                    info[k] = yt_meta[k]
        return _save_extract(video_id, url, timestamped, plain, method, info)

    print("  Intento 3: yt-dlp android bypass...")
    timestamped, plain, method, yt_meta = extract_with_ytdlp(video_id, url, use_android=True)
    if plain:
        if not info and yt_meta:
            info = yt_meta
        elif info and yt_meta:
            for k in ('title', 'channel', 'duration'):
                if info.get(k) in (None, 'N/A', 0) and yt_meta.get(k) not in (None, 'N/A', 0):
                    info[k] = yt_meta[k]
        return _save_extract(video_id, url, timestamped, plain, method, info)

    print(f"  FALLA: No se pudo extraer transcripcion de {video_id}")
    return None
