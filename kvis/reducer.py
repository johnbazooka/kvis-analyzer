import re
import json

from .constants import ANALYSIS_DIR
from .analyze import _bzk_classify_nutrient

def do_reducer(video_id, quiet=False):
    if not quiet:
        print(f"KVIS REDUCER | {video_id}")
        print("  Modo: Filtrando ruido del sistema. No reduce la musica — reduce lo GENERICO.\n")

    analysis_path = ANALYSIS_DIR / f"{video_id}_analysis.json"
    if not analysis_path.exists():
        print(f"  No hay analisis para {video_id}. Ejecuta analyze primero.")
        return None

    with open(analysis_path, 'r', encoding='utf-8') as f:
        a = json.load(f)

    title = a.get('title', video_id)
    channel = a.get('channel', 'N/A')
    nutrients = a.get('nutrients', [])
    insights = a.get('insights', [])
    steps = a.get('steps_found', [])
    creator = channel.split()[0] if channel not in ('N/A', '') else 'el creador'

    for n in nutrients:
        if 'bzk_alignment' not in n:
            n['bzk_alignment'] = _bzk_classify_nutrient(n)

    r = []
    r.append(f"# KVIS REDUCER: {video_id}")
    r.append(f"## {title}")
    r.append(f"**Por:** {channel}")
    r.append(f"**Modo:** Filtrado BZK — lo que NO necesitas, lo que TE DEFINE, lo que CUIDAR.")
    r.append("")

    jb_aligned = [n for n in nutrients if n.get('bzk_alignment') == 'BZK-ALIGNED']
    generic = [n for n in nutrients if n.get('bzk_alignment') == 'GENERICO']
    anti_bzk = [n for n in nutrients if n.get('bzk_alignment') == 'ANTI-BZK']

    r.append("### Resumen BZK Lens")
    r.append("")
    r.append(f"| Clasificacion | Cantidad |")
    r.append(f"|---|---|")
    r.append(f"| BZK-ALIGNED (unico para BZK) | {len(jb_aligned)} |")
    r.append(f"| GENERICO (conocimiento comun) | {len(generic)} |")
    if anti_bzk:
        r.append(f"| ANTI-BZK (contradice manifiesto) | {len(anti_bzk)} |")
    total = len(nutrients) or 1
    ratio = len(jb_aligned) / total * 100
    r.append("")
    if ratio >= 60:
        verdict = "Video altamente relevante para BZK."
    elif ratio >= 30:
        verdict = "Video mixto — filtra lo generico, absorbe lo alineado."
    else:
        verdict = "Video mayormente generico — extrae solo las gemas."
    r.append(f"**Ratio BZK:** {ratio:.0f}% alineado con tu identidad. {verdict}")
    r.append("")

    if anti_bzk:
        r.append("### ALERTAS ANTI-BZK (contradicen tu manifiesto)")
        r.append("")
        r.append("> *Estas ideas chocan con lo que DEFINE a Bazooka Revolution. No las adoptes.*")
        r.append("")
        for n in anti_bzk:
            r.append(f"- **[{n['category']}]** {n['nutrient']}")
        r.append("")

    if jb_aligned:
        r.append("### LO QUE TE DEFINE (BZK-ALIGNED)")
        r.append("")
        r.append("> *Estos nutrients resuenan con tu identidad. Absorbelos, integrarlos te hace MAS BZK.*")
        r.append("")
        for n in jb_aligned:
            r.append(f"- **[{n['category']}]** {n['nutrient']}")
        r.append("")

    if generic:
        r.append("### RUIDO FILTRADO (GENERICO)")
        r.append("")
        r.append("> *Conocimiento comun. Cualquier productor lo sabe. No define a NADIE.*")
        r.append("")
        for n in generic:
            r.append(f"- ~~[{n['category']}] {n['nutrient']}~~")
        r.append("")

    if insights:
        r.append("### Insights bajo BZK Lens")
        r.append("")
        for ins in insights:
            text = ins['text']
            text = re.sub(r'\s+', ' ', text).strip()
            ins_lower = text.lower()
            jb_signal = any(kw in ins_lower for kw in [
                'eurobeat', 'sintetizador', 'synth', 'densidad', 'capas',
                'textura', 'artisticidad', 'libre', 'liberación', 'escape',
                'revolución', 'autentico', 'identidad', 'dj', 'baile',
                'dembow', 'perreo', 'genero', 'gnero', 'rebel',
            ])
            marker = "**[BZK]**" if jb_signal else "[GEN]"
            r.append(f"- {marker} {ins['type']}: {text}")
        r.append("")

    bzk_principles = {
        'densidad con proposito': 0,
        'tierno + potente': 0,
        'dj thinking': 0,
        'cruce de generos': 0,
    }
    full_text = f"{title} {' '.join(s.get('text', '') for s in steps)} {' '.join(n.get('nutrient', '') for n in nutrients)}".lower()
    if any(kw in full_text for kw in ['capas', 'layers', 'densidad', 'textura', 'agregar', 'construir']):
        bzk_principles['densidad con proposito'] += 1
    if any(kw in full_text for kw in ['tierno', 'tender', 'potente', 'powerful', 'tension', 'contraste']):
        bzk_principles['tierno + potente'] += 1
    if any(kw in full_text for kw in ['dj', 'pista', 'dancefloor', 'mezcla', 'transicion', 'extended']):
        bzk_principles['dj thinking'] += 1
    if any(kw in full_text for kw in ['genero', 'género', 'cruce', 'cross', 'eurobeat', 'reggaeton', 'electrónica', 'hibrido']):
        bzk_principles['cruce de generos'] += 1

    r.append("### Huella BZK en este video")
    r.append("")
    r.append("| Principio BZK | Presencia |")
    r.append("|---|---|")
    for principle, score in bzk_principles.items():
        status = "Detectado" if score > 0 else "Ausente"
        r.append(f"| {principle} | {status} |")
    r.append("")

    reducer_path = ANALYSIS_DIR / f"{video_id}_reducer.md"
    with open(reducer_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(r))

    if quiet:
        total = len(nutrients) or 1
        ratio = len(jb_aligned) / total * 100
        print(f"KVIS REDUCER {video_id} → BZK {ratio:.0f}% ({len(jb_aligned)}JB/{len(generic)}GEN/{len(anti_bzk)}ANTI) | {reducer_path}")
    else:
        print('\n'.join(r))
        print(f"\n  Guardado: {reducer_path}")
    return reducer_path


