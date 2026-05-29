import re
import json

from .constants import ANALYSIS_DIR
from .utils import fix_encoding

def _cross_reference(video_id):
    analysis_path = ANALYSIS_DIR / f"{video_id}_analysis.json"
    if not analysis_path.exists():
        return []
    with open(analysis_path, 'r', encoding='utf-8') as f:
        current = json.load(f)
    current_topics = set(current.get('topics_detected', []))
    current_insights = [ins['text'][:60].lower() for ins in current.get('insights', [])]
    current_nutrients = set()
    for n in current.get('nutrients', []):
        if n['relevance'] == 'ALTA' and n['category'] in ('TECNICA', 'CREATIVO', 'SABIDURIA'):
            name = re.sub(r':\s*\d+\s+menciones.*', '', n['nutrient']).strip().lower()
            current_nutrients.add(name)

    validations = []
    for other_path in ANALYSIS_DIR.glob('*_analysis.json'):
        if other_path == analysis_path:
            continue
        try:
            with open(other_path, 'r', encoding='utf-8') as f:
                other = json.load(f)
        except Exception:
            continue
        other_vid = other.get('video_id', '')
        other_channel = other.get('channel', '?')
        other_topics = set(other.get('topics_detected', []))
        shared = current_topics & other_topics
        if not shared:
            continue
        other_nutrients = set()
        for n in other.get('nutrients', []):
            if n['relevance'] == 'ALTA' and n['category'] in ('TECNICA', 'CREATIVO', 'SABIDURIA'):
                name = re.sub(r':\s*\d+\s*menciones.*', '', n['nutrient']).strip().lower()
                other_nutrients.add(name)
        shared_nutrients = current_nutrients & other_nutrients
        if shared or shared_nutrients:
            validations.append({
                'video_id': other_vid,
                'channel': other_channel,
                'title': other.get('title', '?')[:50],
                'shared_topics': sorted(shared),
                'shared_nutrients': sorted(shared_nutrients),
            })
    return validations




def do_teach(video_id, quiet=False):
    analysis_path = ANALYSIS_DIR / f"{video_id}_analysis.json"
    if not analysis_path.exists():
        print(f"  No hay analisis para {video_id}. Ejecuta analyze primero.")
        return None

    with open(analysis_path, 'r', encoding='utf-8') as f:
        a = json.load(f)

    title = a.get('title', video_id)
    channel = a.get('channel', 'N/A')
    steps = a.get('steps_found', [])
    insights = a.get('insights', [])
    quotes = a.get('quotes', [])
    nutrients = a.get('nutrients', [])
    genres = a.get('detected_genres', [])
    topics = a.get('topics_detected', [])
    creator = channel.split()[0] if channel not in ('N/A', '') else 'el creador'

    r = []
    r.append(f"# KVIS TEACH: {video_id}")
    r.append(f"## {title}")
    r.append(f"**Por:** {channel}")
    r.append("")

    r.append("### De que trata")
    if topics:
        r.append(f"{creator} cubre: **{', '.join(topics)}**.")
    if genres:
        r.append(f"Generos mencionados: {', '.join(genres)}.")
    r.append(f"*Todo el conocimiento y experiencias son de {channel}, no de John Bazooka. Lo que sigue es lo que BZK puede aprender de este video.*")
    r.append("")

    if steps:
        r.append(f"### Lo que {creator} ensena")
        r.append("")
        for i, s in enumerate(steps, 1):
            text = s['text']
            text = re.sub(r'\[MUSICA\]\s*', '', text)
            text = re.sub(r'\[CANTO\]\s*', '', text)
            text = re.sub(r'\[RISAS\]\s*', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > 180:
                text = text[:177] + '...'
            r.append(f"**{i}.** {text}")
        r.append("")

    if insights:
        r.append(f"### Lo que quizas no sabias (segun {channel})")
        r.append("")
        seen = set()
        for ins in insights:
            text = ins['text']
            text = re.sub(r'\s+', ' ', text).strip()
            key = text[:40]
            if key in seen:
                continue
            seen.add(key)
            label_map = {
                'Confirma practica universal': 'Estudio confirma',
                'Confirma practica estandar': 'Es estandar en la industria',
                'Desmitificacion': 'Mito derribado',
                'Comparacion clave': 'Dato clave',
                'Punto de impacto': 'Impacto real',
            }
            label = label_map.get(ins['type'], ins['type'])
            r.append(f"- **{label}:** {text}")
        r.append("")

    wisdom = [n for n in nutrients if n['category'] == 'SABIDURIA']
    if wisdom:
        r.append(f"### Sabiduria de {channel}")
        r.append("")
        for w in wisdom:
            r.append(f"> {w['source']}")
        r.append("")

    bzk_app = [n for n in nutrients if n['category'] == 'APLICACION BZK']
    bzk_rel = [n for n in nutrients if n['category'] == 'RELEVANCIA BZK']
    if bzk_app or bzk_rel:
        r.append("### Como aplica a John Bazooka")
        r.append("")
        for n in bzk_rel:
            r.append(f"- {n['nutrient']}")
        for n in bzk_app:
            r.append(f"- {n['nutrient']}")
        r.append("")

    tech_high = [n for n in nutrients if n['category'] == 'TECNICA' and n['relevance'] == 'ALTA']
    if tech_high:
        r.append("### Conocimiento tecnico disponible")
        r.append("")
        for n in tech_high:
            r.append(f"- {n['nutrient']}")
        r.append("")

    creative_high = [n for n in nutrients if n['category'] == 'CREATIVO' and n['relevance'] == 'ALTA']
    if creative_high:
        r.append("### Principios creativos detectados")
        r.append("")
        for n in creative_high:
            r.append(f"- {n['nutrient']}")
        r.append("")

    refs = [n for n in nutrients if n['category'] == 'REFERENCIAS']
    if refs:
        r.append("### Referencias para profundizar")
        r.append("")
        for n in refs:
            r.append(f"- {n['nutrient']}")
        r.append("")

    if quotes:
        r.append(f"### Citas de {channel}")
        r.append("")
        for q in quotes:
            r.append(f'> "{q}"')
        r.append("")

    cross_refs = _cross_reference(video_id)
    if cross_refs:
        r.append("### Validacion cruzada (conocimiento confirmado por otros videos)")
        r.append("")
        for ref in cross_refs:
            parts = []
            if ref['shared_topics']:
                parts.append(f"topicos: {', '.join(ref['shared_topics'])}")
            if ref['shared_nutrients']:
                parts.append(f"nutrientes: {', '.join(ref['shared_nutrients'][:5])}")
            r.append(f"- **{ref['channel']}** ({ref['video_id']}): {' | '.join(parts)}")
        r.append("")

    teach_path = ANALYSIS_DIR / f"{video_id}_teach.md"
    with open(teach_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(r))

    if quiet:
        print(f"KVIS TEACH {video_id} → {len(r)} lineas, {len(nutrients)} nutrients | {teach_path}")
    else:
        print('\n'.join(r))
        print(f"\n  Guardado: {teach_path}")
    return teach_path

