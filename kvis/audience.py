#!/usr/bin/env python3
"""
KVIS Audience v1.0 — Cross-artist audience analysis.
Compara comentarios de multiples canales: fans compartidos, ER, sentimiento, oportunidades.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter, defaultdict
from datetime import datetime

from .constants import DATA_DIR
from .comments import do_comments

COMMENTS_DIR = DATA_DIR / "comments"


def do_audience(urls: List[str], quiet: bool = False) -> Optional[Dict]:
    """Analizar y comparar audiencias de multiples canales/videos."""
    if not urls:
        print("ERROR: Pasar al menos 2 URLs de canales")
        return None

    if not quiet:
        print(f"\nKVIS AUDIENCE | {len(urls)} canal(es)")
        print("=" * 60)

    channels = []
    for url in urls:
        if not quiet:
            print(f"\nProcesando: {url[:60]}")
        result = do_comments(url, quiet=True)
        if result:
            channels.append(result)
        else:
            if not quiet:
                print(f"  SKIP: sin datos")

    if len(channels) < 2:
        print("ERROR: Necesito al menos 2 canales con datos")
        return None

    analysis = _cross_analyze(channels, quiet)
    result = {
        'channels': len(channels),
        'channel_names': [c.get('channel', 'N/A') for c in channels],
        'analysis': analysis,
        'raw': channels,
    }

    _save(result, quiet)
    return result


def _cross_analyze(channels: List[Dict], quiet: bool = False) -> Dict:
    fans_per_channel = []
    for ch in channels:
        fans = _get_fans(ch)
        fans_per_channel.append({'name': ch.get('channel', 'N/A'), 'fans': fans})

    shared = _shared_fans(fans_per_channel)
    comparative = _comparative(channels)
    opportunities = _opportunities(channels, shared, fans_per_channel)

    if not quiet:
        names = [c.get('channel', '?') for c in channels]
        print(f"\n{'─' * 60}")
        print(f"CROSS-AUDIENCE: {' vs '.join(names)}")
        print(f"{'─' * 60}")

        print(f"\nComparativa:")
        for c in comparative:
            print(f"  {c['name']:30s} | {c['views']:>6} views | {c['comments']:>4} comms | ER {c['engagement_rate']:.1f}% | +{c['positive_pct']:.0f}%")

        if shared:
            print(f"\nFans compartidos ({len(shared)}):")
            for f in shared[:10]:
                print(f"  {f['author']:25s} | " + " | ".join(f"{ch}: {f['channels'][ch]}c" for ch in f['channels']))
        else:
            print(f"\nFans compartidos: 0 — audiencias no se cruzan")

        if opportunities:
            print(f"\nOportunidades:")
            for o in opportunities:
                print(f"  {o}")

        print(f"{'─' * 60}")

    return {
        'comparative': comparative,
        'shared_fans': shared,
        'fans_per_channel': [{'name': f['name'], 'total_fans': len(f['fans'])} for f in fans_per_channel],
        'opportunities': opportunities,
    }


def _get_fans(data: Dict) -> Dict:
    fans = defaultdict(lambda: {'comments': 0, 'likes': 0})
    owner = data.get('channel', '').lower()
    for vid, v in data.get('comments_data', {}).items():
        for c in v.get('comments', []):
            author = c['author']
            if author.lower().replace(' ', '') in owner.replace(' ', '').lower():
                continue
            fans[author]['comments'] += 1
            fans[author]['likes'] += c.get('likes', 0)
    return dict(fans)


def _shared_fans(fans_per_channel: List[Dict]) -> List[Dict]:
    if len(fans_per_channel) < 2:
        return []

    author_sets = []
    for fp in fans_per_channel:
        author_sets.append(set(fp['fans'].keys()))

    shared_authors = author_sets[0]
    for s in author_sets[1:]:
        shared_authors = shared_authors & s

    if not shared_authors:
        # Also check pairwise
        all_shared = []
        for i in range(len(fans_per_channel)):
            for j in range(i + 1, len(fans_per_channel)):
                pair = author_sets[i] & author_sets[j]
                for author in pair:
                    entry = {
                        'author': author,
                        'channels': {
                            fans_per_channel[i]['name']: fans_per_channel[i]['fans'][author]['comments'],
                            fans_per_channel[j]['name']: fans_per_channel[j]['fans'][author]['comments'],
                        }
                    }
                    all_shared.append(entry)
        return all_shared

    result = []
    for author in shared_authors:
        entry = {'author': author, 'channels': {}}
        for fp in fans_per_channel:
            if author in fp['fans']:
                entry['channels'][fp['name']] = fp['fans'][author]['comments']
        result.append(entry)
    return result


def _comparative(channels: List[Dict]) -> List[Dict]:
    result = []
    for ch in channels:
        eng = ch.get('analysis', {}).get('engagement', {})
        sent = ch.get('analysis', {}).get('sentiment', {})
        loyal = ch.get('analysis', {}).get('loyal_fans', [])
        cats = ch.get('analysis', {}).get('categories', {})
        reqs = ch.get('analysis', {}).get('requests', [])

        result.append({
            'name': ch.get('channel', 'N/A'),
            'views': eng.get('total_views', 0),
            'comments': eng.get('total_comments', 0),
            'engagement_rate': eng.get('overall_engagement_rate', 0),
            'positive_pct': sent.get('positive_pct', 0),
            'negative_pct': sent.get('negative_pct', 0),
            'loyal_fans': len(loyal),
            'categories': {k: len(v) for k, v in cats.items()} if cats else {},
            'requests_count': len(reqs),
            'requests_types': dict(Counter(r['type'] for r in reqs)) if reqs else {},
        })
    return result


def _opportunities(channels: List[Dict], shared: List[Dict], fans_per_channel: List[Dict]) -> List[str]:
    opps = []
    names = [c.get('channel', '?') for c in channels]

    if not shared:
        opps.append(f"Audiencias de {' y '.join(names)} NO se cruzan — collab importaria audiencia nueva")
    elif len(shared) < 3:
        opps.append(f"Solo {len(shared)} fans compartidos — poco cross-pollination natural")
    else:
        opps.append(f"{len(shared)} fans compartidos — base comun detectada")

    for ch in channels:
        eng = ch.get('analysis', {}).get('engagement', {})
        sent = ch.get('analysis', {}).get('sentiment', {})
        reqs = ch.get('analysis', {}).get('requests', [])
        name = ch.get('channel', '?')

        er = eng.get('overall_engagement_rate', 0)
        if er > 5:
            opps.append(f"{name}: ER alto ({er:.1f}%) — audiencia super fiel")
        if sent.get('negative_pct', 0) > 10:
            opps.append(f"{name}: sentimiento negativo alto ({sent['negative_pct']:.0f}%) — revisar contenido")
        if len(reqs) > 10:
            opps.append(f"{name}: {len(reqs)} solicitudes — audiencia hambrienta de contenido")

    biggest = max(channels, key=lambda c: c.get('analysis', {}).get('engagement', {}).get('total_views', 0))
    opps.append(f"{biggest.get('channel', '?')} es el hub con mas views — ideal para subir collabs")

    return opps


def _save(result: Dict, quiet: bool = False):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    slug = re.sub(r'[^\w]', '_', '_'.join(result.get('channel_names', ['unknown'])))[:50]
    json_file = COMMENTS_DIR / f"audience_{slug}_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    if not quiet:
        print(f"Guardado: {json_file}")
