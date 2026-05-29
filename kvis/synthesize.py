#!/usr/bin/env python3
"""
KVIS Synthesize v1.0 — Cross-video nutrient synthesis.
Lee multiples analisis y genera matriz cruzada de nutrientes, patrones comunes, divergencias.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter, defaultdict
from datetime import datetime

from .constants import ANALYSIS_DIR, DATA_DIR

SYNTH_DIR = DATA_DIR / "synthesis"
SYNTH_DIR.mkdir(parents=True, exist_ok=True)


def do_synthesize(video_ids: List[str] = None, quiet: bool = False) -> Optional[Dict]:
    """Sintetizar nutrientes de multiples videos en matriz cruzada."""
    analyses = _load_analyses(video_ids)
    if not analyses:
        print("ERROR: No hay analisis disponibles. Ejecutar kvis process primero.")
        return None

    if not quiet:
        print(f"\nKVIS SYNTHESIZE | {len(analyses)} video(s)")
        print("=" * 60)

    synthesis = {
        'common_axes': _common_axes(analyses),
        'divergent': _divergent(analyses),
        'matrix': _build_matrix(analyses),
        'patterns': _detect_patterns(analyses),
        'principles': _extract_principles(analyses),
        'bzk_application': _bzk_application(analyses),
    }

    if not quiet:
        _print_synthesis(synthesis, analyses)

    result = {
        'videos': [{'id': a['video_id'], 'title': a.get('title', 'N/A'), 'channel': a.get('channel', 'N/A')} for a in analyses],
        'synthesis': synthesis,
    }

    _save(result, quiet)
    return result


def _load_analyses(video_ids: List[str] = None) -> List[Dict]:
    analyses = []
    if video_ids:
        for vid in video_ids:
            path = ANALYSIS_DIR / f"{vid}_analysis.json"
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['video_id'] = vid
                    analyses.append(data)
    else:
        for path in sorted(ANALYSIS_DIR.glob("*_analysis.json")):
            if '_spectral' in path.name or '_comments' in path.name or '_audience' in path.name:
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    vid = path.stem.replace('_analysis', '')
                    data['video_id'] = vid
                    analyses.append(data)
            except Exception:
                pass

    return analyses


def _common_axes(analyses: List[Dict]) -> List[Dict]:
    """Find axes mentioned in multiple videos."""
    axis_counts = defaultdict(list)
    for a in analyses:
        nutrients = a.get('nutrients', [])
        if isinstance(nutrients, list):
            for item in nutrients:
                if isinstance(item, dict):
                    cat = item.get('category', 'OTRO')
                    text = item.get('nutrient', '')[:80]
                    axis_counts[text].append({
                        'video': a.get('video_id', '?'),
                        'channel': a.get('channel', '?'),
                        'category': cat,
                    })
        elif isinstance(nutrients, dict):
            for cat, items in nutrients.items():
                if isinstance(items, list):
                    for item in items:
                        text = item if isinstance(item, str) else item.get('text', str(item))
                        axis_counts[text[:80]].append({
                            'video': a.get('video_id', '?'),
                            'channel': a.get('channel', '?'),
                            'category': cat,
                        })

    common = []
    for text, sources in axis_counts.items():
        if len(sources) >= 2:
            common.append({
                'axis': text,
                'count': len(sources),
                'sources': sources,
            })

    return sorted(common, key=lambda x: x['count'], reverse=True)[:20]


def _divergent(analyses: List[Dict]) -> List[Dict]:
    """Find insights unique to single videos."""
    divergent = []
    for a in analyses:
        insights = a.get('insights', [])
        for ins in insights:
            if isinstance(ins, dict):
                text = ins.get('text', '')
            else:
                text = str(ins)
            if text and len(text) > 20:
                divergent.append({
                    'insight': text[:150],
                    'video': a.get('video_id', '?'),
                    'channel': a.get('channel', '?'),
                    'type': 'unique',
                })

    return divergent[:15]


def _build_matrix(analyses: List[Dict]) -> Dict:
    """Build nutrient matrix: category x video."""
    categories = defaultdict(lambda: defaultdict(int))
    for a in analyses:
        vid = a.get('video_id', '?')
        nutrients = a.get('nutrients', [])
        if isinstance(nutrients, list):
            for item in nutrients:
                if isinstance(item, dict):
                    cat = item.get('category', 'OTRO')
                    categories[cat][vid] += 1
        elif isinstance(nutrients, dict):
            for cat, items in nutrients.items():
                if isinstance(items, list):
                    categories[cat][vid] = len(items)

    return dict(categories)


def _detect_patterns(analyses: List[Dict]) -> List[Dict]:
    """Detect repeated patterns across videos."""
    all_techniques = Counter()
    all_creative = Counter()
    all_wisdom = Counter()

    for a in analyses:
        nutrients = a.get('nutrients', [])
        items = nutrients if isinstance(nutrients, list) else []
        if isinstance(nutrients, dict):
            items = [item for sublist in nutrients.values() for item in (sublist if isinstance(sublist, list) else [])]

        for item in items:
            text = item.get('nutrient', '') if isinstance(item, dict) else str(item)
            cat = item.get('category', '') if isinstance(item, dict) else ''
            lower = text.lower()

            technique_kw = ['produccion', 'grabacion', 'mezcla', 'master', 'composicion',
                            'autotune', 'producción', 'grabación', 'composición', 'sampling',
                            'diseño gráfico', 'marketing', 'distribución']
            creative_kw = ['identidad', 'simbolismo', 'nostalgia', 'experimentacion',
                           'colaboracion', 'transformacion', 'minimalismo', 'emocion',
                           'experimentación', 'colaboración', 'transformación']

            if cat == 'TECNNICA' or cat == 'TECNICA':
                for kw in technique_kw:
                    if kw in lower:
                        all_techniques[kw] += 1
            if cat == 'CREATIVO':
                for kw in creative_kw:
                    if kw in lower:
                        all_creative[kw] += 1
            if cat == 'SABIDURIA':
                all_wisdom[text[:50]] += 1

    patterns = []
    for technique, count in all_techniques.most_common(10):
        if count >= 2:
            patterns.append({'type': 'tecnica', 'pattern': technique, 'videos': count, 'confirmed': True})
    for creative, count in all_creative.most_common(10):
        if count >= 2:
            patterns.append({'type': 'creativo', 'pattern': creative, 'videos': count, 'confirmed': True})
    for wisdom, count in all_wisdom.most_common(10):
        if count >= 2:
            patterns.append({'type': 'sabiduria', 'pattern': wisdom, 'videos': count, 'confirmed': True})

    return patterns


def _extract_principles(analyses: List[Dict]) -> List[str]:
    """Extract core principles repeated across videos."""
    principle_markers = [
        r'se trata de', r'lo mas importante', r'la diferencia', r'la clave',
        r'lo esencial', r'nunca', r'siempre', r'el secreto',
    ]

    principles = []
    for a in analyses:
        nutrients = a.get('nutrients', [])
        items = nutrients if isinstance(nutrients, list) else []
        if isinstance(nutrients, dict):
            wisdom = nutrients.get('SABIDURIA', [])
            items = wisdom if isinstance(wisdom, list) else []
        else:
            items = [i for i in nutrients if isinstance(i, dict) and i.get('category') == 'SABIDURIA']

        for w in items:
            text = w.get('nutrient', '') if isinstance(w, dict) else str(w)
            for marker in principle_markers:
                if re.search(marker, text.lower()):
                    principles.append(text[:150])
                    break

    return list(set(principles))[:10]


def _bzk_application(analyses: List[Dict]) -> List[Dict]:
    """Extract BZK-relevant items."""
    bzk_items = []
    for a in analyses:
        nutrients = a.get('nutrients', [])
        items = nutrients if isinstance(nutrients, list) else []
        if isinstance(nutrients, dict):
            relevance = nutrients.get('RELEVANCIA BZK', [])
            items = relevance if isinstance(relevance, list) else []
        else:
            items = [i for i in nutrients if isinstance(i, dict) and 'BZK' in i.get('category', '')]

        for item in items:
            text = item.get('nutrient', '') if isinstance(item, dict) else str(item)
            bzk_items.append({
                'text': text[:150],
                'video': a.get('video_id', '?'),
                'channel': a.get('channel', '?'),
            })

    return bzk_items


def _print_synthesis(synthesis: Dict, analyses: List[Dict]):
    print(f"\nVideos analizados:")
    for a in analyses:
        title = a.get('title', a.get('video_id', '?'))
        print(f"  {a.get('video_id', '?')} | {title[:50]}")

    if synthesis['common_axes']:
        print(f"\nEjes comunes ({len(synthesis['common_axes'])}):")
        for ax in synthesis['common_axes'][:8]:
            print(f"  [{ax['count']}x] {ax['axis'][:70]}")

    if synthesis['patterns']:
        print(f"\nPatrones confirmados:")
        for p in synthesis['patterns'][:10]:
            print(f"  [{p['type']}] {p['pattern']} ({p['videos']} videos)")

    if synthesis['principles']:
        print(f"\nPrincipios extraidos:")
        for p in synthesis['principles'][:5]:
            print(f"  \"{p[:80]}\"")

    if synthesis['divergent']:
        print(f"\nInsights unicos:")
        for d in synthesis['divergent'][:5]:
            print(f"  [{d['channel'][:20]}] {d['insight'][:70]}")

    if synthesis['bzk_application']:
        print(f"\nAplicacion BZK ({len(synthesis['bzk_application'])} items):")
        for b in synthesis['bzk_application'][:5]:
            print(f"  [{b['channel'][:20]}] {b['text'][:70]}")

    print(f"\n{'─' * 60}")


def _save(result: Dict, quiet: bool = False):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_file = SYNTH_DIR / f"synthesis_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    if not quiet:
        print(f"Guardado: {json_file}")
