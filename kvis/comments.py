#!/usr/bin/env python3
"""
KVIS Comments v1.0 — YouTube Comment Analysis
Extrae y analiza comentarios de videos YouTube para feedback de audiencia.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter, defaultdict
from datetime import datetime

from .constants import DATA_DIR, ANALYSIS_DIR, CHANNEL_CACHE_FILE
from .utils import extract_video_id

COMMENTS_DIR = DATA_DIR / "comments"
COMMENTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_channel_cache() -> dict:
    if CHANNEL_CACHE_FILE.exists():
        try:
            with open(CHANNEL_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_channel_cache(cache: dict):
    with open(CHANNEL_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def _resolve_handle(handle: str, quiet: bool = False) -> Optional[str]:
    """Resolver @handle a channel URL via cache o yt-dlp."""
    cache = _load_channel_cache()
    cache_key = handle.lower()

    if cache_key in cache:
        entry = cache[cache_key]
        url = f"https://www.youtube.com/channel/{entry['channel_id']}/videos"
        if not quiet:
            print(f"  Cache: {entry['name']} ({entry['channel_id']})")
        return url

    try:
        import yt_dlp
    except ImportError:
        return None

    if not quiet:
        print(f"Resolviendo @{handle}...")

    ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f'https://www.youtube.com/@{handle}', download=False)
            if info:
                channel_id = info.get('channel_id') or info.get('uploader_id', '')
                channel_name = info.get('channel', info.get('title', ''))
                entries = [e for e in (info.get('entries') or []) if e]
                if entries:
                    cache[cache_key] = {'channel_id': channel_id, 'name': channel_name, 'handle': handle}
                    _save_channel_cache(cache)
                    if not quiet:
                        print(f"  Canal: {channel_name} ({channel_id}) | {len(entries)} videos")
                    return f"https://www.youtube.com/channel/{channel_id}/videos"
        except Exception:
            pass

    ydl_search = {'quiet': True, 'no_warnings': True, 'extract_flat': True, 'default_search': 'ytsearch5'}
    with yt_dlp.YoutubeDL(ydl_search) as ydl:
        try:
            results = ydl.extract_info(f"ytsearch5:{handle} channel", download=False)
            entries = results.get('entries', []) if results else []
            for entry in entries:
                if not entry:
                    continue
                channel = (entry.get('channel') or '').lower().replace(' ', '')
                handle_clean = handle.lower().replace('_', '')
                if handle_clean in channel or channel in handle_clean:
                    channel_id = entry.get('channel_id', '')
                    if channel_id:
                        cache[cache_key] = {'channel_id': channel_id, 'name': entry.get('channel', ''), 'handle': handle}
                        _save_channel_cache(cache)
                        if not quiet:
                            print(f"  Canal: {entry.get('channel', 'N/A')} ({channel_id})")
                        return f"https://www.youtube.com/channel/{channel_id}/videos"
        except Exception:
            pass

    print(f"ERROR: No se pudo resolver @{handle}")
    return None


def do_comments(url_or_channel: str, video_ids: List[str] = None, quiet: bool = False) -> Optional[Dict]:
    """Analizar comentarios de YouTube — video único o canal completo."""

    if video_ids:
        return _analyze_video_list(video_ids, quiet)

    is_channel = bool(re.search(r'youtube\.com/(@|c/|channel/)', url_or_channel))

    if not is_channel:
        video_id = extract_video_id(url_or_channel)
        if video_id:
            return _analyze_video_list([video_id], quiet)

    return _analyze_channel(url_or_channel, quiet)


def _analyze_channel(channel_url: str, quiet: bool = False) -> Optional[Dict]:
    """Analizar comentarios de todos los videos de un canal."""
    try:
        import yt_dlp
    except ImportError:
        print("ERROR: yt-dlp no instalado. pip install yt-dlp")
        return None

    if not quiet:
        print(f"\nKVIS COMMENTS | Canal: {channel_url}")
        print("=" * 60)

    # Para handles @, primero resolver el channel ID via un video conocido
    resolved_url = channel_url
    handle_match = re.search(r'youtube\.com/@([\w.]+)', channel_url)
    if handle_match:
        resolved_url = _resolve_handle(handle_match.group(1), quiet)
        if not resolved_url:
            return None

    ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(resolved_url, download=False)
        except Exception as e:
            print(f"ERROR: No se pudo acceder al canal — {str(e)[:80]}")
            return None

    channel_name = info.get('channel', info.get('title', 'Desconocido'))
    entries = [e for e in (info.get('entries') or []) if e]

    if not entries:
        print("No se encontraron videos en el canal.")
        return None

    if not quiet:
        print(f"Canal: {channel_name} | Videos encontrados: {len(entries)}")

    video_ids = [e['id'] for e in entries if e.get('id')]
    return _analyze_video_list(video_ids, quiet, channel_name)


def _analyze_video_list(video_ids: List[str], quiet: bool = False, channel_name: str = "") -> Optional[Dict]:
    """Extraer y analizar comentarios de una lista de videos."""
    try:
        import yt_dlp
    except ImportError:
        print("ERROR: yt-dlp no instalado. pip install yt-dlp")
        return None

    if not quiet:
        print(f"\nKVIS COMMENTS | {len(video_ids)} video(s)")
        print("=" * 60)

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'writesubtitles': False,
        'writeautomaticsub': False,
        'getcomments': True,
    }

    all_comments_data = {}
    channel_detected = channel_name

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for i, vid in enumerate(video_ids, 1):
            if not quiet:
                print(f"  [{i}/{len(video_ids)}] {vid}...", end=" ")

            try:
                info = ydl.extract_info(f'https://www.youtube.com/watch?v={vid}', download=False)
                comments = info.get('comments') or []
                title = info.get('title', 'N/A')
                views = info.get('view_count', 0)
                likes_vid = info.get('like_count', 0)
                upload_date = info.get('upload_date', '')

                if not channel_detected:
                    channel_detected = info.get('channel', '')

                valid = []
                for c in comments:
                    text = c.get('text', '').strip()
                    if text and len(text) > 2 and not _is_spam(text):
                        valid.append({
                            'text': text,
                            'author': c.get('author', 'N/A'),
                            'likes': c.get('like_count', 0),
                            'timestamp': c.get('timestamp', 0),
                            'is_reply': c.get('parent', 'root') != 'root',
                        })

                all_comments_data[vid] = {
                    'title': title,
                    'views': views,
                    'video_likes': likes_vid,
                    'upload_date': upload_date,
                    'total_comments': len(comments) if comments else 0,
                    'valid_comments': len(valid),
                    'comments': valid,
                }

                if not quiet:
                    nc = len(comments) if comments else 0
                    print(f"{title[:40]} | {views} views | {nc} comms | {len(valid)} validos")

            except Exception as e:
                if not quiet:
                    print(f"ERROR: {str(e)[:50]}")
                all_comments_data[vid] = {
                    'title': 'N/A', 'views': 0, 'video_likes': 0,
                    'upload_date': '', 'total_comments': 0,
                    'valid_comments': 0, 'comments': [], 'error': str(e)[:80],
                }

    analysis = _analyze(all_comments_data, quiet)
    result = {
        'channel': channel_detected,
        'videos_analyzed': len(video_ids),
        'comments_data': all_comments_data,
        'analysis': analysis,
    }

    _save(result, quiet)
    return result


def _is_spam(text: str) -> bool:
    patterns = [
        r'subscribe.*channel|check my channel|visit my profile',
        r'free.*followers|followers.*free',
        r'winner.*congrats|congrats.*winner',
    ]
    lower = text.lower()
    return any(re.search(p, lower) for p in patterns)


def _analyze(data: Dict, quiet: bool = False) -> Dict:
    sentiment = _sentiment(data)
    keywords = _keywords(data)
    categories = _categorize(data)
    requests = _requests(data)
    top = _top_comments(data)
    engagement = _engagement(data)
    fans = _loyal_fans(data)

    if not quiet:
        print(f"\n{'─' * 60}")
        print(f"ANALISIS COMENTARIOS")
        print(f"{'─' * 60}")

        total_c = engagement['total_comments']
        total_v = sum(d.get('views', 0) for d in data.values())
        print(f"Videos: {len(data)} | Comentarios validos: {total_c} | Views totales: {total_v}")

        if sentiment:
            print(f"Sentimiento: +{sentiment['positive_pct']:.0f}% / -{sentiment['negative_pct']:.0f}% / ={sentiment['neutral_pct']:.0f}%")

        if fans:
            fan_strs = [f"{f['author']} ({f['comments']}x)" for f in fans[:5]]
            print(f"Fans leales: {', '.join(fan_strs)}")

        if categories:
            print(f"Categorias: {', '.join(f'{k} ({len(v)})' for k, v in categories.items() if v)}")

        if requests:
            print(f"Solicitudes: {len(requests)} detectadas")

        print(f"{'─' * 60}")

    return {
        'sentiment': sentiment,
        'keywords': keywords,
        'categories': categories,
        'requests': requests,
        'top_comments': top,
        'engagement': engagement,
        'loyal_fans': fans,
    }


def _sentiment(data: Dict) -> Dict:
    positive = ['bueno', 'buena', 'buen', 'bien', 'excelente', 'genial', 'cool', 'amazing',
                'hermoso', 'perfecto', 'gusta', 'encanta', 'amo', 'increíble', 'potente',
                'duro', 'killer', 'crack', 'king', 'queen', 'bacán', 'raja', 'joya',
                '🔥', '❤️', '😍', '👏', '💪', '🎵', '🎶', '🎧', '💯', '❤️‍🔥']
    negative = ['malo', 'mala', 'feo', 'fea', 'odio', 'horrible', 'terrible', 'peor',
                'aburrido', 'mediocre', 'flojo', '💔', '😢', '😡']

    pos = neg = neu = 0
    for d in data.values():
        for c in d.get('comments', []):
            text = c['text'].lower()
            ps = sum(1 for w in positive if w in text)
            ns = sum(1 for w in negative if w in text)
            if c.get('likes', 0) > 5:
                ps += 1
            if ps > ns:
                pos += 1
            elif ns > ps:
                neg += 1
            else:
                neu += 1

    total = pos + neg + neu
    if total == 0:
        return {'positive_pct': 0, 'negative_pct': 0, 'neutral_pct': 0, 'total': 0,
                'positive': 0, 'negative': 0, 'neutral': 0}

    return {
        'positive': pos, 'negative': neg, 'neutral': neu, 'total': total,
        'positive_pct': (pos / total) * 100,
        'negative_pct': (neg / total) * 100,
        'neutral_pct': (neu / total) * 100,
    }


def _keywords(data: Dict) -> List:
    stopwords = {'que', 'de', 'la', 'el', 'en', 'y', 'a', 'los', 'las', 'del',
                 'un', 'una', 'con', 'por', 'para', 'como', 'muy', 'pero', 'todo',
                 'tan', 'está', 'estoy', 'tienes', 'tengo', 'pero', 'mas', 'sus',
                 'este', 'esta', 'ese', 'esa', 'del', 'los', 'las', 'les', 'del'}
    musical = {'flow', 'voz', 'beat', 'melodía', 'ritmo', 'mezcla', 'master',
               'producción', 'estilo', 'letra', 'canción', 'tema', 'remix', 'cover',
               'reggaeton', 'trap', 'perreo', 'guaracha'}
    appreciation = {'potente', 'suave', 'duro', 'crudo', 'limpio', 'oscuro', 'fresco',
                    'nuevo', 'original', 'único', 'diferente', 'pegajoso', 'bacán'}

    all_words = Counter()
    musical_found = Counter()
    appreciation_found = Counter()

    for d in data.values():
        for c in d.get('comments', []):
            words = re.findall(r'\b[a-záéíóúñ]{3,}\b', c['text'].lower())
            filtered = [w for w in words if w not in stopwords]
            all_words.update(filtered)
            for w in filtered:
                if w in musical:
                    musical_found[w] += 1
                if w in appreciation:
                    appreciation_found[w] += 1

    return {
        'top': all_words.most_common(15),
        'musical': musical_found.most_common(10),
        'appreciation': appreciation_found.most_common(10),
    }


def _categorize(data: Dict) -> Dict:
    patterns = {
        'flow_voz': [r'flow', r'voz', r'timbre', r'cantas', r'rappeas'],
        'estilo': [r'estilo', r'ritmo', r'beat', r'sonido', r'vibe', r'atmósfera'],
        'letra': [r'letra', r'mensaje', r'significado', r'storytelling'],
        'produccion': [r'producción', r'calidad', r'master', r'mezcla', r'profesional'],
        'originalidad': [r'original', r'único', r'diferente', r'nuevo', r'fresco'],
        'colaboracion': [r'collab', r'colaboración', r'trabajar juntos', r'tema juntos'],
    }

    categories = defaultdict(list)
    for d in data.values():
        for c in d.get('comments', []):
            text = c['text'].lower()
            for cat, pats in patterns.items():
                for p in pats:
                    if re.search(p, text):
                        categories[cat].append({
                            'comment': c['text'][:100],
                            'author': c['author'],
                            'likes': c.get('likes', 0),
                        })
                        break
    return dict(categories)


def _requests(data: Dict) -> List:
    patterns = {
        'beat_collaboration': [r'collab', r'colaboración', r'trabajar juntos', r'tema juntos'],
        'remix_version': [r'remix', r'otra versión', r'más largo'],
        'next_song': [r'próximo', r'siguiente', r'otra canción', r'nuevo tema', r'cuándo'],
        'lyrics': [r'letra', r'lyrics', r'qué dice'],
    }

    requests = []
    for d in data.values():
        for c in d.get('comments', []):
            text = c['text'].lower()
            for req_type, pats in patterns.items():
                for p in pats:
                    if re.search(p, text):
                        requests.append({
                            'type': req_type,
                            'comment': c['text'][:100],
                            'author': c['author'],
                            'likes': c.get('likes', 0),
                            'video_title': d.get('title', 'N/A'),
                        })
                        break
    return requests


def _top_comments(data: Dict) -> List:
    all_c = []
    for vid, d in data.items():
        for c in d.get('comments', []):
            all_c.append({
                'text': c['text'][:150],
                'author': c['author'],
                'likes': c.get('likes', 0),
                'video_title': d.get('title', 'N/A'),
                'video_id': vid,
            })
    return sorted(all_c, key=lambda x: x['likes'], reverse=True)[:15]


def _engagement(data: Dict) -> Dict:
    total_comments = sum(d.get('valid_comments', 0) for d in data.values())
    total_likes = sum(c.get('likes', 0) for d in data.values() for c in d.get('comments', []))
    total_views = sum(d.get('views', 0) for d in data.values())

    rate = ((total_comments + total_likes) / total_views * 100) if total_views > 0 else 0
    avg = (total_likes / total_comments) if total_comments > 0 else 0

    per_video = []
    for vid, d in data.items():
        v = d.get('views', 0)
        c = d.get('valid_comments', 0)
        l = sum(cm.get('likes', 0) for cm in d.get('comments', []))
        er = ((c + l) / v * 100) if v > 0 else 0
        per_video.append({
            'video_id': vid,
            'title': d.get('title', 'N/A'),
            'views': v,
            'comments': c,
            'comment_likes': l,
            'engagement_rate': round(er, 2),
        })

    return {
        'total_comments': total_comments,
        'total_comment_likes': total_likes,
        'total_views': total_views,
        'avg_likes_per_comment': round(avg, 2),
        'overall_engagement_rate': round(rate, 2),
        'per_video': per_video,
    }


def _loyal_fans(data: Dict) -> List:
    author_count = defaultdict(lambda: {'comments': 0, 'likes': 0, 'videos': set()})
    for d in data.values():
        for c in d.get('comments', []):
            a = c['author']
            author_count[a]['comments'] += 1
            author_count[a]['likes'] += c.get('likes', 0)
            author_count[a]['videos'].add(d.get('title', ''))

    fans = []
    for author, info in author_count.items():
        if info['comments'] >= 2:
            fans.append({
                'author': author,
                'comments': info['comments'],
                'likes': info['likes'],
                'videos': len(info['videos']),
            })
    return sorted(fans, key=lambda x: x['comments'], reverse=True)


def _save(result: Dict, quiet: bool = False):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    channel_slug = re.sub(r'[^\w]', '_', result.get('channel', 'unknown'))[:30]

    json_file = COMMENTS_DIR / f"{channel_slug}_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    if not quiet:
        print(f"Guardado: {json_file}")
