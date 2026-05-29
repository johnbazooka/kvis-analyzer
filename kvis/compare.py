import re
import json
from datetime import datetime

from .constants import ANALYSIS_DIR, TRANSCRIPTS_DIR
from .utils import load_checkpoint

def _parse_spectral_overview(report_path):
    import numpy as np
    metrics = {}
    content = report_path.read_text(encoding='utf-8')
    for line in content.split('\n'):
        if not line.startswith('|') or '---' in line:
            continue
        if 'Metrica' in line or 'Tiempo' in line:
            continue
        parts = [p.strip() for p in line.split('|') if p.strip()]
        if len(parts) >= 2:
            key = parts[0]
            val = parts[1]
            metrics[key] = val
    # Parse energy bands
    energy = {}
    in_energy = False
    for line in content.split('\n'):
        if 'Distribucion de Energia' in line:
            in_energy = True
            continue
        if in_energy:
            if not line.startswith('|'):
                in_energy = False
                continue
            if '---' in line or 'Banda' in line:
                continue
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2:
                energy[parts[0]] = float(parts[1]) if parts[1].replace('.','').replace('-','').isdigit() else 0
    metrics['_energy'] = energy
    return metrics


def _parse_transcript_keywords(video_id):
    clean_path = TRANSCRIPTS_DIR / f"{video_id}_clean.txt"
    if not clean_path.exists():
        return [], []
    with open(clean_path, 'r', encoding='utf-8') as f:
        text = f.read()
    lines = text.split('\n')
    body = '\n'.join(lines[5:])
    body_lower = body.lower()

    technique_kw = {
        'dual-synth': ['dual-synth', 'dos sintetiz', 'synth coupling', 'paired'],
        'vocoder': ['vocoder', 'vocoderiz'],
        'scream': ['scream', 'grito', 'screaming'],
        'pad_distortion': ['pad distorsion', 'distorsionad'],
        'modulation': ['modulacion', 'modulaci', 'modulating', 'modulate', 'cambio de tono', 'cambio de clave'],
        'sus4': ['suspendid', 'sus4', 'cuarta', 'fourth'],
        'seventh': ['septima', 'sima', '7th', 'major 7'],
        'pedal_note': ['nota eje', 'pedal', 'nota unica', 'repetida', 'notas simples'],
        'bassline': ['bassline', 'bajo', 'bass', 'grave'],
        'intro_design': ['intro', 'introduccion'],
        'synth_phrase': ['synth phrase', 'frase de sinte', 'sintetizador'],
        'chorus': ['estribillo', 'chorus', 'refrain'],
        'verse': ['verso', 'verse'],
        'bridge': ['puente', 'bridge'],
        'chord_progression': ['progresion', 'acorde', 'chord'],
        'piano_test': ['piano', 'guitarra acustica', 'acustica'],
        'naming': ['titulo', 'nombre', 'naming', 'title'],
        'vibrato': ['vibrato'],
        'sample': ['sample', 'muestra'],
        'prophet': ['prophet'],
        'nordlead': ['nordlead', 'nord lead', 'clavia'],
        'jd800': ['jd-800', 'jd800'],
        'roland': ['roland'],
    }

    equipment_kw = {
        'NordLead': ['nordlead', 'nord lead', 'clavia'],
        'JD-800': ['jd-800', 'jd800'],
        'Roland': ['roland'],
        'Prophet': ['prophet'],
        'Vocoder': ['vocoder'],
    }

    found_techniques = []
    for tech, kws in technique_kw.items():
        if any(kw in body_lower for kw in kws):
            found_techniques.append(tech)

    found_equipment = []
    for equip, kws in equipment_kw.items():
        if any(kw in body_lower for kw in kws):
            found_equipment.append(equip)

    return found_techniques, found_equipment


def _extract_quotes(video_id, keywords=None):
    clean_path = TRANSCRIPTS_DIR / f"{video_id}_clean.txt"
    if not clean_path.exists():
        return []
    with open(clean_path, 'r', encoding='utf-8') as f:
        text = f.read()
    lines = text.split('\n')
    body = '\n'.join(lines[5:])

    quote_patterns = [
        r'"([^"]{20,150})"',
        r'"([^"]{20,150})"',
    ]
    quotes = []
    for pat in quote_patterns:
        for m in re.finditer(pat, body):
            quotes.append(m.group(1))
    if keywords:
        quotes = [q for q in quotes if any(kw in q.lower() for kw in keywords)]
    return quotes[:10]


def do_crosscompare(video_ids=None, group_by='channel', output_name=None, quiet=False):
    import numpy as np

    cp = load_checkpoint()
    all_videos = cp.get('videos', [])

    if video_ids:
        selected = [v for v in all_videos if v['video_id'] in video_ids]
    else:
        vids_with_spectral = set()
        for sp in ANALYSIS_DIR.glob('*_spectral_report.md'):
            vids_with_spectral.add(sp.stem.replace('_spectral_report', ''))
        selected = [v for v in all_videos
                    if v.get('spectral') or v.get('tempo') or v['video_id'] in vids_with_spectral]

    if not selected:
        print("  No videos con spectral data para comparar.")
        return None

    print(f"KVIS CROSS-COMPARE | {len(selected)} videos")
    print("=" * 60)

    video_data = []
    for v in selected:
        vid = v['video_id']
        sp_path = ANALYSIS_DIR / f"{vid}_spectral_report.md"
        if not sp_path.exists():
            continue
        metrics = _parse_spectral_overview(sp_path)
        techniques, equipment = _parse_transcript_keywords(vid)
        quotes = _extract_quotes(vid)

        # Extract tempo/centroid from spectral report if checkpoint missing
        tempo = v.get('tempo') or 0
        centroid = v.get('spectral_centroid') or 0
        bandwidth = v.get('spectral_bandwidth') or 0
        if not tempo and 'Tempo' in metrics:
            tempo_m = re.search(r'([\d.]+)\s*BPM', metrics['Tempo'])
            if tempo_m:
                tempo = float(tempo_m.group(1))
        if not centroid and 'Brillo (centroid)' in metrics:
            cent_m = re.search(r'([\d.]+)\s*Hz', metrics['Brillo (centroid)'])
            if cent_m:
                centroid = float(cent_m.group(1))
        if not bandwidth and 'Ancho espectral' in metrics:
            bw_m = re.search(r'([\d.]+)\s*Hz', metrics['Ancho espectral'])
            if bw_m:
                bandwidth = float(bw_m.group(1))

        entry = {
            'video_id': vid,
            'title': v.get('title', 'N/A'),
            'channel': v.get('channel', 'N/A'),
            'duration': v.get('duration', 0),
            'words': v.get('words', 0),
            'video_type': v.get('video_type', 'N/A'),
            'genres': v.get('genres', []),
            'tempo': tempo,
            'spectral_centroid': centroid,
            'spectral_bandwidth': bandwidth,
            'metrics': metrics,
            'techniques': techniques,
            'equipment': equipment,
            'quotes': quotes,
        }
        video_data.append(entry)

    if not video_data:
        print("  No se encontro data para comparar.")
        return None

    r = []
    r.append(f"# KVIS Cross-Compare: {len(video_data)} Videos")
    r.append(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M')} | **Videos:** {len(video_data)}")
    r.append("")

    # ── Section 1: Overview Table ──
    r.append("## Comparativo General")
    r.append("| # | Video | Canal | BPM | Brillo | Tipo | Generos |")
    r.append("|---|---|---|---|---|---|---|")
    for i, vd in enumerate(video_data, 1):
        genres = ','.join(vd['genres']) if vd['genres'] else '-'
        r.append(f"| {i} | [{vd['video_id']}] {vd['title'][:40]} | {vd['channel']} | {vd['tempo']:.0f} | {vd['spectral_centroid']:.0f}Hz | {vd['video_type']} | {genres} |")
    r.append("")

    # ── Section 2: Spectral Comparison ──
    tempos = [vd['tempo'] for vd in video_data if vd['tempo'] > 0]
    centroids = [vd['spectral_centroid'] for vd in video_data if vd['spectral_centroid'] > 0]

    if tempos:
        r.append("## Rango Spectral")
        r.append(f"- **Tempo:** {min(tempos):.0f}-{max(tempos):.0f} BPM (promedio: {np.mean(tempos):.0f})")
        r.append(f"- **Brillo:** {min(centroids):.0f}-{max(centroids):.0f} Hz (promedio: {np.mean(centroids):.0f})")
        r.append("")

    # ── Section 3: Technique Matrix ──
    all_techniques = sorted(set(t for vd in video_data for t in vd['techniques']))
    if all_techniques:
        r.append("## Matriz de Tecnicas")
        header = "| Tecnica | " + ' | '.join(vd['video_id'][:8] for vd in video_data) + " |"
        sep = "|---|" + '|'.join([':-:'] * len(video_data)) + "|"
        r.append(header)
        r.append(sep)
        for tech in all_techniques:
            row = f"| {tech} |"
            for vd in video_data:
                row += " X |" if tech in vd['techniques'] else " - |"
            r.append(row)
        r.append("")

        shared = [tech for tech in all_techniques
                  if sum(1 for vd in video_data if tech in vd['techniques']) >= max(2, len(video_data) // 2)]
        unique = {}
        for vd in video_data:
            for tech in vd['techniques']:
                if tech not in all_techniques:
                    continue
                count = sum(1 for vd2 in video_data if tech in vd2['techniques'])
                if count == 1:
                    unique.setdefault(vd['video_id'], []).append(tech)

        if shared:
            r.append("### Tecnicas Compartidas (aparecen en 2+ videos)")
            for tech in shared:
                vids_with = [vd['video_id'] for vd in video_data if tech in vd['techniques']]
                r.append(f"- **{tech}**: {', '.join(vids_with)}")
            r.append("")

        if unique:
            r.append("### Tecnicas Unicas (solo 1 video)")
            for vid, techs in unique.items():
                r.append(f"- **{vid}**: {', '.join(techs)}")
            r.append("")

    # ── Section 4: Equipment Matrix ──
    all_equipment = sorted(set(e for vd in video_data for e in vd['equipment']))
    if all_equipment:
        r.append("## Equipment Matrix")
        header = "| Equipment | " + ' | '.join(vd['video_id'][:8] for vd in video_data) + " |"
        sep = "|---|" + '|'.join([':-:'] * len(video_data)) + "|"
        r.append(header)
        r.append(sep)
        for eq in all_equipment:
            row = f"| {eq} |"
            for vd in video_data:
                row += " X |" if eq in vd['equipment'] else " - |"
            r.append(row)
        r.append("")

    # ── Section 5: Spectral Ranking ──
    r.append("## Ranking Spectral")
    by_tempo = sorted(video_data, key=lambda x: -x['tempo'])
    r.append("### Mas Rapido → Mas Lento")
    for vd in by_tempo:
        r.append(f"- **{vd['tempo']:.0f} BPM**: {vd['title'][:50]}")
    r.append("")

    by_bright = sorted(video_data, key=lambda x: -x['spectral_centroid'])
    r.append("### Mas Brillante → Mas Oscuro")
    for vd in by_bright:
        r.append(f"- **{vd['spectral_centroid']:.0f} Hz**: {vd['title'][:50]}")
    r.append("")

    # ── Section 6: Key Quotes ──
    all_quotes = []
    for vd in video_data:
        for q in vd['quotes'][:3]:
            all_quotes.append((vd['video_id'], q))
    if all_quotes:
        r.append("## Citas Destacadas")
        for vid, q in all_quotes[:15]:
            r.append(f"- *\"{q}\"* — {vid}")
        r.append("")

    # ── Section 7: Auto-Detected Groups ──
    groups = {}
    for vd in video_data:
        key = vd['channel'] if group_by == 'channel' else ','.join(vd['genres'])
        groups.setdefault(key, []).append(vd)

    if len(groups) > 1:
        r.append("## Grupos Detectados")
        for group_name, members in groups.items():
            r.append(f"### {group_name} ({len(members)} videos)")
            for vd in members:
                r.append(f"- {vd['title'][:50]} | {vd['tempo']:.0f} BPM | {vd['spectral_centroid']:.0f}Hz")
            r.append("")

    # ── Section 8: Pattern Summary ──
    r.append("## Patron Summary")
    if shared:
        r.append(f"**{len(shared)} patrones compartidos** en {len(video_data)} videos:")
        for tech in shared:
            r.append(f"- {tech}")
    r.append("")

    # Write output
    if output_name:
        out_path = ANALYSIS_DIR / f"crosscompare_{output_name}.md"
    else:
        out_path = ANALYSIS_DIR / f"crosscompare_{datetime.now().strftime('%Y%m%d_%H%M')}.md"

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(r))

    if quiet:
        print(f"KVIS CROSSCOMPARE → {len(video_data)} videos, {len(shared) if all_techniques else 0} tecnicas compartidas | {out_path}")
    else:
        print(f"  Videos comparados: {len(video_data)}")
        print(f"  Tecnicas compartidas: {len(shared) if all_techniques else 0}")
        print(f"  Equipment unicos: {len(all_equipment)}")
        print(f"  Output: {out_path}")
    return out_path


# ── DEEP: Full pipeline in 1 call ──────────────────────────────────


