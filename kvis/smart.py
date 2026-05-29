#!/usr/bin/env python3
"""
KVIS Smart v1.0 — Auto-detect video type and route to optimal pipeline.
MUSIC → comments + spectral (no transcript analysis)
PODCAST → process (transcript + nutrients)
TUTORIAL → process (transcript + nutrients)
DOCUMENTARY → process (transcript + nutrients)
ARTIST_CHANNEL → comments (all videos)
"""

import re
from typing import Optional

from .utils import extract_video_id
from .classify import classify_video
from .comments import do_comments
from .pipeline import do_process, do_deep


def _detect_input_type(url: str) -> str:
    """Detect if URL is a channel, video, or playlist."""
    if re.search(r'youtube\.com/(@|c/|channel/)', url):
        return 'channel'
    if re.search(r'youtube\.com/playlist', url):
        return 'playlist'
    return 'video'


def _quick_classify(url: str) -> str:
    """Classify video — uses checkpoint first, then title patterns."""
    video_id = extract_video_id(url)
    if not video_id:
        return 'VIDEO'

    from .utils import load_checkpoint
    cp = load_checkpoint()
    entry = None
    for v in cp.get('videos', []):
        if v['video_id'] == video_id:
            entry = v
            break

    if entry and entry.get('video_type'):
        return entry['video_type']

    title = (entry.get('title', '') if entry else '').lower()
    channel = (entry.get('channel', '') if entry else '').lower()
    duration = (entry.get('duration', 0) if entry else 0)

    # Podcast patterns (check FIRST — podcasts often have "music" in title)
    podcast_channels = ['creadores de hits', 'hablemos de hits', 'beno espinosa',
                        'profesor rayado', 'dimelo smooth', 'matías parkman']
    podcast_kw = ['podcast', 'episodio', 'entrevista', 'charla', 'cap #',
                  'hablamos de', 'creadores de', 'cap #', 'entrevista']
    if any(ch in channel for ch in podcast_channels):
        return 'PODCAST'
    if any(kw in title for kw in podcast_kw):
        return 'PODCAST'

    # Long talking videos = likely podcast/interview
    words = (entry.get('words', 0) if entry else 0)
    if words > 5000 and duration > 600:
        return 'PODCAST'

    # Music patterns
    music_kw = ['mv', 'music video', 'video oficial', 'official video', 'lyric video',
                'audio', 'reggaeton', 'remix', 'feat.', 'ft.', 'prod.', 'beat',
                'mv', 'm/v', 'kpop', 'k-pop', 'reggaetón', 'perreo']
    if any(kw in title for kw in music_kw):
        return 'MUSIC'

    # Tutorial
    tutorial_kw = ['tutorial', 'como hacer', 'how to', 'fl studio', 'produccion']
    if any(kw in title for kw in tutorial_kw):
        return 'TUTORIAL'

    return 'VIDEO'


def do_smart(url, lang='es', quiet=False):
    """Auto-detect content type and run optimal pipeline."""
    input_type = _detect_input_type(url)

    if not quiet:
        print(f"\nKVIS SMART | {url[:60]}")
        print("=" * 60)

    if input_type == 'channel':
        if not quiet:
            print(f"Detectado: CANAL → comments analysis")
        return do_comments(url, quiet=quiet)

    video_id = extract_video_id(url)
    vtype = _quick_classify(url)

    if not quiet:
        print(f"Detectado: {vtype}")

    if vtype == 'MUSIC':
        if not quiet:
            print(f"Pipeline MUSIC → comments + spectral")
        comments_result = do_comments(url, quiet=quiet)
        return comments_result
    else:
        if not quiet:
            print(f"Pipeline {vtype} → process (transcript + nutrients)")
        return do_process(url, lang=lang, quiet=quiet)
