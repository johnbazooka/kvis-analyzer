import re
import json
from datetime import datetime

from .constants import TRANSCRIPTS_DIR, ANALYSIS_DIR
from .utils import load_checkpoint, save_checkpoint, fix_encoding


def _bzk_classify_nutrient(nutrient):
    cat = nutrient.get('category', '')
    nut = nutrient.get('nutrient', '').lower()
    src = nutrient.get('source', '').lower()
    combined = f"{cat} {nut} {src}"

    anti_bzk_kw = [
        'minimalismo dogmatico', 'menos es mas', 'menos es más', 'reduce capas',
        'reduce layers', 'quita todo lo que', 'simplify everything',
        'copia lo que funciona', 'copia fórmulas', 'sigue la tendencia',
        'follow the trend', 'compite por precio', 'sacrifica arte',
        'sacrifica artistry', 'hacer lo comercial', 'vende tu alma',
        'compromiso creativo', 'fórmula ganadora', 'copia a los',
        'formula exito', 'fórmula éxito', 'copy what works',
        'elige un genero', 'elige un género', 'stick to one genre',
    ]
    for kw in anti_bzk_kw:
        if kw in combined:
            return 'ANTI-BZK'

    jb_aligned_kw = [
        'densidad', 'capas', 'textura', 'densidad con proposito',
        'tierno y potente', 'tension', 'eurobeat', 'reggaeton', 'reggaetón',
        'dembow', 'perreo', 'guaracha', 'aleteo', 'tribal', 'cumbiaton',
        'genero crossing', 'cruce de generos',
        'dj thinking', 'pista de baile', 'dancefloor', 'extended',
        'liberación', 'liberacion', 'escape', 'revolución', 'revolucion',
        'artisticidad', 'sintetizador', 'synth', 'mezcla', 'mezclar',
        'producción musical', 'produccion musical', 'para para',
        'initial d', 'avex', 'sinclairestyle', 'italo disco',
        'rebel', 'rebeld', 'autenticidad', 'autentico',
        'identidad', 'sello personal', 'distintivo',
        'no compet', 'no copio', 'no sacrific',
        'emocion', 'emoción', 'sentir', 'transmit',
        'contra el sistema', 'anti-sistema', 'fascismo', 'facha',
        'dictadura', 'vigilancia', 'hipervigilancia', 'libertad',
        'derechos', 'autoritarismo', 'resistencia', 'lucha',
        'monopolio creativo', 'de 0 a 1', 'crear algo nuevo',
        'kast', 'ultraderecha', 'extrema derecha', 'palantir',
        'thiel', 'billionaire', 'magnate', 'desigualdad',
    ]
    for kw in jb_aligned_kw:
        if kw in combined:
            return 'BZK-ALIGNED'

    if cat in ('APLICACION BZK', 'RELEVANCIA BZK'):
        return 'BZK-ALIGNED'

    generic_cats = {'INDUSTRIA'}
    generic_kw = [
        'spotify', 'playlist', 'streaming', 'redes sociales', 'instagram',
        'tiktok', 'facebook', 'youtube ads', 'facebook ads', 'presupuesto',
        'roi', 'engagement', 'reach', 'click', 'conversion',
        'contrato', 'derechos', 'royalt', 'regalías', 'publishing',
    ]
    if cat in generic_cats:
        return 'GENERICO'
    for kw in generic_kw:
        if kw in combined:
            return 'GENERICO'

    return 'GENERICO'


def _extract_steps_semantic(text, title=''):
    text_lower = text.lower()
    steps = []

    topic_labels = {
        'brainstorm': ['brainstorm', 'top line', 'topline', 'primeras ideas', 'improvisar melod'],
        'composicion': ['composici', 'escribir', 'letra', 'melod', 'acorde', 'armon', 'progresi'],
        'grabacion': ['grabar', 'grabaci', 'voz', 'vocal', 'cabina', 'micro'],
        'comping': ['comping', 'tomas', 'mejor parte', 'take'],
        'produccion': ['producci', 'instrument', 'arreglo', 'timbre', 'beat'],
        'mixing': ['mezcla', 'mixing', 'ecualiz', 'compresi', 'balance'],
        'mastering': ['master', 'masteriz', 'loudness'],
        'autotune': ['autotun', 'auto-tun'],
        'marketing': ['spotify', 'playlist', 'lanzamiento', 'promoci'],
        'industria': ['discogr', 'warner', 'sello', 'contrato', 'label', 'industria'],
        'identidad': ['identidad', 'quien eres', 'sonido unico', 'diferente'],
        'negocio': ['negocio', 'vivir de la musica', 'marketing', 'visible', 'sistema'],
        'minimalismo': ['minimalista', 'menos es mas', 'omitir', 'quitar', 'reducir', 'defines tu sonido', 'sobra'],
        'emocion': ['emocion', 'sentimiento', 'sentir', 'resuene', 'reson', 'conectar', 'mover a'],
        'diferenciacion': ['diferente', 'unico', 'distint', 'genuino', 'original', 'competitiv'],
        'audiencia': ['audiencia', 'para quien', 'publico', 'oyente', 'escuchar', 'gente', 'consumidor'],
    }

    def _topic_for(frag):
        fl = frag.lower()
        scores = {}
        for t, kws in topic_labels.items():
            score = sum(1 for kw in kws if kw in fl)
            if score > 0:
                scores[t] = score
        if scores:
            return max(scores, key=scores.get)
        return 'general'

    confidence_map = {
        'Ley': 0.95,
        'Regla': 0.90,
        'Paso': 0.85,
        'Clave': 0.80,
        'Tip': 0.75,
        'Transicion': 0.60,
        'Siguiente paso': 0.55,
        'Paso final': 0.70,
        'Enumeracion': 0.65,
    }

    law_pat = re.compile(
        r'((?:ley|Ley)\s+n[uú]mero\s+(?:uno|1|dos|2|tres|3|cuatro|4|cinco|5|seis|6|siete|7|ocho|8|nueve|9|diez|10)[^.!?\n]{10,250})',
        re.IGNORECASE
    )
    for m in law_pat.finditer(text):
        frag = m.group(1).strip()
        if len(frag) > 15:
            nm = re.search(r'n[uú]mero\s+(\w+)', frag, re.IGNORECASE)
            steps.append({'label': f"Ley {nm.group(1) if nm else '?'}", 'topic': _topic_for(frag), 'text': frag[:250], 'confidence': 0.95})

    rule_pat = re.compile(r'((?:regla|principio|pilar|clave|factor)\s+n[uú]mero\s+\d+[^.!?\n]{10,250})', re.IGNORECASE)
    for m in rule_pat.finditer(text):
        frag = m.group(1).strip()
        if len(frag) > 15:
            steps.append({'label': 'Regla', 'topic': _topic_for(frag), 'text': frag[:250], 'confidence': 0.90})

    ordinal_map = {
        'primer': 1, '1er': 1,
        'segund': 2, '2do': 2,
        'tercer': 3, '3er': 3,
        'cuart': 4, '4to': 4,
        'quint': 5, '5to': 5,
        'sext': 6, '6to': 6,
        'septim': 7, 'séptim': 7,
        'octav': 8,
        'noven': 9,
        'decim': 10, 'décim': 10,
    }
    ordinal_words = '|'.join(sorted(ordinal_map.keys(), key=len, reverse=True))
    step_words = '(?:paso|lugar|punto|fase|etapa|ley|regla|principio|pilar|cosa|elemento)'
    ord_pat = re.compile(rf'((?:el\s+)?(?:{ordinal_words})(?:[oa])?\s+{step_words}[^.!?\n]{{10,250}})', re.IGNORECASE)
    for m in ord_pat.finditer(text):
        frag = m.group(1).strip()
        if len(frag) > 15:
            for prefix, num in ordinal_map.items():
                if re.search(prefix, frag, re.IGNORECASE):
                    steps.append({'label': f'Paso {num}', 'topic': _topic_for(frag), 'text': frag[:250], 'confidence': confidence_map.get('Paso', 0.85)})
                    break

    trans_pats = [
        (r'(?:una\s+vez\s+(?:que|ya))\s+.*?(?:toca|viene|vamos|pasamos|siguiente)[^.!?\n]{10,200}', 'Transicion'),
        (r'(?:ahora\s+(?:ya|bien|pues|vamos|toca))\s+.*?(?:paso|fase|grab|producc|mix|master|compos)[^.!?\n]{10,200}', 'Transicion'),
        (r'(?:toca\s+(?:el|la))\s+.*?(?:paso|fase|grab|producc|mix|master|compos)[^.!?\n]{10,200}', 'Transicion'),
        (r'(?:vamos\s+(?:a|con)\s+.*?(?:paso|fase|grab|producc|mix|master|compos|estudio))[^.!?\n]{10,200}', 'Transicion'),
        (r'(?:[uú]ltimo)\s+(?:paso|fase|etapa|cosa)[^.!?\n]{10,200}', 'Paso final'),
        (r'(?:siguiente|pr[oó]ximo)\s+(?:paso|cosa|fase|etapa)[^.!?\n]{10,200}', 'Siguiente paso'),
    ]
    for pat, label in trans_pats:
        for m in re.finditer(pat, text, re.IGNORECASE):
            frag = m.group(0).strip()
            if len(frag) > 15:
                steps.append({'label': label, 'topic': _topic_for(frag), 'text': frag[:250], 'confidence': confidence_map.get(label, 0.60)})

    key_pats = [
        (r'(?:lo\s+(?:m[aá]s\s+)?importante|clave|esencial|fundamental|cr[ií]tico)\s+(?:es|ser|que)[^.!?\n]{15,200}', 'Clave'),
        (r'(?:tip|consejo|regla|principio)\s*:?\s+\d+[^.!?\n]{10,200}', 'Tip'),
        (r'\d+\.\s+[A-ZÁÉÍÓÚÑ][^.!?\n]{10,200}', 'Enumeracion'),
    ]
    for pat, label in key_pats:
        for m in re.finditer(pat, text, re.IGNORECASE):
            frag = m.group(0).strip()
            if len(frag) > 15:
                steps.append({'label': label, 'topic': _topic_for(frag), 'text': frag[:250], 'confidence': confidence_map.get(label, 0.60)})

    if not steps:
        for t, kws in topic_labels.items():
            relevant = [s for s in text.split('.') if any(kw in s.lower() for kw in kws)]
            if relevant:
                best = max(relevant, key=lambda x: sum(1 for kw in kws if kw in x.lower()))
                steps.append({'label': t.capitalize(), 'topic': t, 'text': best.strip()[:250], 'confidence': 0.40})

    seen = set()
    unique = []
    for s in steps:
        key = f"{s['label']}:{s['text'][:40]}"
        if key not in seen:
            unique.append(s)
            seen.add(key)
    return unique


def _extract_key_insights(text, steps):
    insights = []
    insight_patterns = [
        (r'(?:todo[s]?\s+(?:el\s+)?mundo\s+(?:lo\s+)?hace[sn]?)', 'Confirma practica universal'),
        (r'(?:es\s+est[a\u00e1]ndar|es\s+normal|se\s+hace\s+as[i\u00ed]|pr[a\u00e1]ctica\s+com[u\u00fa]n)', 'Confirma practica estandar'),
        (r'(?:no\s+tienes?\s+por\s+qu[e\u00e9]\s+avergonzarte|no\s+est[a\u00e1]\s+mal|no\s+es\s+trampa)', 'Desmitificacion'),
        (r'(?:mucho\s+m[a\u00e1]s\s+(?:dif[i\u00ed]cil|complicado|f[a\u00e1]cil|importante|mejor))', 'Comparacion clave'),
        (r'(?:va\s+a\s+cambiar\s+por\s+completo|totalmente\s+diferente|radicalmente)', 'Punto de impacto'),
    ]
    for pat, label in insight_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            start = max(0, m.start() - 60)
            end = min(len(text), m.end() + 80)
            context = text[start:end].strip()
            context = re.sub(r'\s+', ' ', context)
            context = re.sub(r'^\S+\s', '', context) if start > 0 else context
            if end < len(text):
                last_space = context.rfind(' ')
                if last_space > len(context) - 20:
                    context = context[:last_space]
            if context and context[0].islower() and start > 0:
                first_space = context.find(' ')
                if first_space > 0:
                    context = context[first_space+1:]
            context = context.strip().rstrip('.,;:)').strip()
            if len(context) > 30:
                insights.append({'type': label, 'text': context[:300]})

    seen_signatures = {}
    unique = []
    for ins in insights:
        sig_words = [w for w in ins['text'].lower().split() if len(w) > 3]
        sig = ' '.join(sorted(set(sig_words))[:8])
        t = ins['type']
        key = f"{t}:{sig}"
        if key not in seen_signatures:
            seen_signatures[key] = True
            unique.append(ins)
    return unique[:10]


def _extract_notable_quotes(text):
    quotes = []
    patterns = [
        r'"([^"]{25,180})"',
        r'\u00ab([^"]{25,180})\u00bb',
        r'\u201c([^"]{25,180})\u201d',
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            quotes.append(m.group(1))
    if not quotes:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        quote_starts = [
            'es mucho m', 'todo el mundo', 'lo m\u00e1s importante',
            'la clave', 'el truco', 'nunca', 'siempre', 'es imposible',
        ]
        for s in sentences:
            if any(s.lower().startswith(qs) for qs in quote_starts) and len(s) > 40:
                quotes.append(s.strip()[:200])
    seen = set()
    unique = []
    for q in quotes:
        key = q[:50]
        if key not in seen:
            unique.append(q)
            seen.add(key)
    return unique[:8]


def _extract_nutrients(text, title='', genres=None):
    nutrients = []
    text_lower = text.lower()

    def _add(category, nutrient, relevance='MEDIA', source=''):
        nutrients.append({
            'category': category,
            'nutrient': nutrient,
            'relevance': relevance,
            'source': source[:150],
        })

    artist_patterns = [
        r'(?:de|del|by|por)\s+([A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+){0,3})',
        r'([A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+){0,2})\s+(?:es|fue|sería|se convirtió|creó|diseñó|produjo|compuso|grabó)',
    ]
    noise_words = {
        'el','la','los','las','de','del','en','por','que','se','su','un','una','es','fue',
        'con','para','como','más','pero','este','esta','sin','sobre','entre','hay','muy',
        'también','cuando','donde','puede','todo','tiene','hacer','cada','después','otros',
        'otra','otro','estas','estos','esa','ese','eso','ella','nos','les','das','dar',
    }
    stop_names = {
        'el álbum', 'la portada', 'el disco', 'la banda', 'el artista', 'la canción',
        'la música', 'el video', 'la primera', 'you tube', 'music spring', 'warner music',
        'big mac', 'stone throw', 'natural snow', 'velvet underground', 'red hot',
        'aerosmith', 'un album', 'la obra', 'la foto', 'la imagen', 'la persona',
        'la historia', 'el mundo', 'la industria', 'el productor', 'la producción',
        'el proceso', 'la primera', 'el director', 'el concepto', 'el diseño',
        'la creación', 'la composición', 'la grabación', 'el trabajo',
    }
    artists_found = set()
    for pat in artist_patterns:
        for m in re.finditer(pat, text):
            name = m.group(1).strip()
            words = name.split()
            if not (1 < len(words) <= 4):
                continue
            if all(w.lower() in noise_words for w in words):
                continue
            if any(w.lower() in noise_words for w in words[:1]):
                continue
            if name.lower() in stop_names:
                continue
            if re.search(r'(brew|pitches|kill|father|hosted|bonnie|elder|springstein|acrilas|biton|naville)', name, re.IGNORECASE):
                continue
            artists_found.add(name)
    if artists_found:
        notable = sorted(artists_found, key=lambda x: len(x), reverse=True)[:10]
        _add('REFERENCIAS', f'Artistas/mencionados: {", ".join(notable)}', 'ALTA')

    album_pattern = r'(?:álbum|album)\s+(?:de\s+)?["\u00ab\u201c]([^"\u00ab\u201d\u00bb\n]{3,50})["\u201d\u00bb]'
    albums_found = set()
    for m in re.finditer(album_pattern, text, re.IGNORECASE):
        album = m.group(1).strip().rstrip('.,;:)')
        if album and album.lower() not in ('la portada', 'el álbum', 'la primera', 'los vinilos', 'el disco'):
            albums_found.add(album)
    if albums_found:
        _add('REFERENCIAS', f'Álbumes mencionados: {", ".join(list(albums_found)[:10])}', 'ALTA')

    genre_keywords = {
        'eurobeat': ['eurobeat', 'initial d', 'avex', 'sinclairestyle', 'super eurobeat'],
        'guaracha': ['guaracha', 'aleteo', 'tribal', 'sonido de disco'],
        'trap': ['trap', 'drill', '808', 'beat maker'],
        'reggaeton': ['reggaeton', 'reggaetón', 'dembow', 'perreo'],
        'techno': ['techno', 'rave', 'sintetizador'],
        'house': ['house', 'tech house', 'deep house'],
        'hip-hop': ['hip hop', 'hiphop', 'rap', 'mc', 'dj', 'sample', 'vinilo'],
        'pop': ['pop music', 'pop español', 'k-pop', 'pop rock', 'pop urbano'],
        'rock': ['rock', 'banda', 'guitarra'],
        'lo-fi': ['lo-fi', 'lofi', 'chillhop'],
    }
    mentioned_genres = []
    for genre, kws in genre_keywords.items():
        count = sum(text_lower.count(kw) for kw in kws)
        if count > 0:
            mentioned_genres.append((genre, count))
    eurobeat_para = len(re.findall(r'para\s+para', text_lower))
    if eurobeat_para >= 3:
        mentioned_genres.append(('eurobeat', eurobeat_para))
    if mentioned_genres:
        mentioned_genres.sort(key=lambda x: -x[1])
        _add('GENERO', f'Géneros musicales mencionados: {", ".join(g for g,c in mentioned_genres)}', 'ALTA')

    technique_kw = {
        'sampling': ['sample', 'samplar', 'muestreo', 'vinilo'],
        'producción': ['producci', 'productor', 'mezcla', 'mixing', 'master'],
        'composición': ['composici', 'melod', 'acorde', 'armon', 'progresi'],
        'grabación': ['grabar', 'grabaci', 'estudio', 'cabina', 'micro'],
        'diseño gráfico': ['dise', 'portada', 'cover', 'artwork', 'visual', 'ilustrac'],
        'marketing': ['spotify', 'playlist', 'lanzamiento', 'promoci', 'branding', 'identidad'],
        'distribución': ['distribuci', 'vinilo', 'físico', 'digital', 'streaming', 'plataforma'],
        'autotune': ['autotun', 'auto-tun', 'pitch correction'],
    }
    for tech, kws in technique_kw.items():
        count = sum(text_lower.count(kw) for kw in kws)
        if count >= 3:
            _add('TECNICA', f'{tech}: {count} menciones — conocimiento técnico presente', 'ALTA')
        elif count >= 1:
            _add('TECNICA', f'{tech}: {count} menciones', 'MEDIA')

    creative_kw = {
        'minimalismo': ['minimalista', 'minimalismo', 'simple', 'esencial', 'menos es más'],
        'simbolismo': ['símbolo', 'simbol', 'metáfora', 'representa', 'significa'],
        'nostalgia': ['nostalgia', 'melancol', 'recuerdo', 'pasado', 'memoria'],
        'experimentación': ['experiment', 'innovar', 'vanguardia', 'romper', 'desafiar'],
        'colaboración': ['colaboraci', 'trabajó con', 'junto a', 'mano de', 'creó con'],
        'identidad': ['identidad', 'marca', 'sello', 'distintivo', 'personal', 'único'],
        'emoción': ['emocion', 'sentir', 'transmit', 'sensación', 'impacto'],
        'contraste': ['contraste', 'dualidad', 'opuesto', 'paradoja'],
        'transformación': ['transform', 'evoluci', 'crecimiento', 'cambio'],
    }
    for concept, kws in creative_kw.items():
        count = sum(text_lower.count(kw) for kw in kws)
        if count >= 2:
            _add('CREATIVO', f'{concept}: {count} menciones — principio creativo detectado', 'ALTA')
        elif count >= 1:
            _add('CREATIVO', f'{concept}: presente', 'MEDIA')

    industry_kw = {
        'disquera': ['discogr', 'sello', 'warner', 'sony', 'universal', 'label', 'indie'],
        'streaming': ['spotify', 'apple music', 'streaming', 'plataforma', 'digital'],
        'físico': ['vinilo', 'cassette', 'cd', 'físico', 'tienda de discos'],
        'contrato': ['contrato', 'derechos', 'royalty', 'regalías', 'publishing'],
        'mercado': ['mercado', 'audiencia', 'oyentes', 'fans', 'público'],
    }
    for topic, kws in industry_kw.items():
        count = sum(text_lower.count(kw) for kw in kws)
        if count >= 2:
            _add('INDUSTRIA', f'{topic}: {count} menciones', 'MEDIA')

    sentences = re.split(r'(?<=[.!?])\s+', text)
    wisdom_patterns = [
        (r'la\s+clave\s+(?:es|está|radica)', 'CLAVE'),
        (r'lo\s+(?:más\s+)?importante\s+(?:es|de)', 'CLAVE'),
        (r'(?:nunca|siempre)\s+(?:hay\s+que|se\s+debe|es)', 'REGLA'),
        (r'(?:el\s+error|el\s+problema|la\s+trampa|el\s+mito)', 'WARNING'),
        (r'(?:nadie|ninguno|jamás|nunca)\s+(?:te\s+)?(?:dice|contó|explicó|mencionó)', 'OCULTO'),
        (r'(?:todo\s+el\s+mundo|todos)\s+(?:lo\s+hacen|hacen|usan|saben)', 'UNIVERSAL'),
        (r'(?:depende\s+de|se\s+trata\s+de|se\s+reduce\s+a)', 'INSIGHT'),
        (r'(?:el\s+arte|el\s+secreto|la\s+diferencia)\s+(?:es|está|radica)', 'SABIDURIA'),
        (r'(?:puede\s+ser|podría\s+ser|vale\s+la\s+pena)\s+.*?(?:intentar|probar|explorar|considerar)', 'OPORTUNIDAD'),
    ]
    for pat, label in wisdom_patterns:
        for s in sentences:
            if re.search(pat, s, re.IGNORECASE) and len(s.strip()) > 25:
                clean_s = re.sub(r'\s+', ' ', s.strip())[:200]
                _add('SABIDURIA', f'{label}: {clean_s}', 'ALTA', clean_s)

    jb_keywords = {
        'eurobeat': ['eurobeat', 'initial d', 'sinclairestyle', 'para para', 'avex', 'j-pop', 'italo disco'],
        'producción BZK': ['producción musical', 'productor', 'daw', 'fl studio', 'ableton', 'sintetizador', 'synth', 'mezcla', 'master'],
        'marketing BZK': ['spotify', 'playlist', 'lanzamiento', 'cover art', 'artwork', 'branding', 'identidad visual'],
        'creatividad BZK': ['composición', 'melodía', 'inspiración', 'creatividad', 'proceso creativo'],
    }
    jb_hits = {}
    for area, kws in jb_keywords.items():
        count = sum(text_lower.count(kw) for kw in kws)
        if count > 0:
            jb_hits[area] = count
    if jb_hits:
        top_area = max(jb_hits, key=jb_hits.get)
        _add('RELEVANCIA BZK', f'Área más relevante: {top_area} ({jb_hits[top_area]} menciones). Total: {", ".join(f"{k}({v})" for k,v in sorted(jb_hits.items(), key=lambda x:-x[1]))}', 'ALTA')

    sentences = re.split(r'(?<=[.!?])\s+', text)
    for s in sentences:
        s_lower = s.lower()
        if any(kw in s_lower for kw in ['portada', 'cover', 'artwork', 'diseño']):
            if any(kw in s_lower for kw in ['importante', 'esencial', 'clave', 'define', 'representa', 'transmite', 'impacto']):
                clean_s = re.sub(r'\s+', ' ', s.strip())[:250]
                _add('APLICACIÓN BZK', f'Diseño de portadas: {clean_s}', 'ALTA', clean_s)
                break

    category_priority = {'ALTA': 0, 'MEDIA': 1, 'BAJA': 2}
    nutrients.sort(key=lambda x: category_priority.get(x['relevance'], 1))
    seen_keys = set()
    unique = []
    for n in nutrients:
        key = f"{n['category']}:{n['nutrient'][:50]}"
        if key not in seen_keys:
            n['bzk_alignment'] = _bzk_classify_nutrient(n)
            unique.append(n)
            seen_keys.add(key)
    return unique


def do_analyze(video_id, expected_steps=0, quiet=False):
    clean_path = TRANSCRIPTS_DIR / f"{video_id}_clean.txt"
    if not clean_path.exists():
        print(f"  No hay transcripcion para {video_id}. Ejecuta extract primero.")
        return None

    with open(clean_path, 'r', encoding='utf-8') as f:
        text = f.read()

    lines = text.split('\n')
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith('=' * 10):
            body_start = i + 2
            break
    transcript = '\n'.join(lines[body_start:])

    title = 'N/A'
    channel = 'N/A'
    for line in lines:
        if line.startswith('Titulo:'):
            title = line.replace('Titulo:', '').strip()
        elif line.startswith('Canal:'):
            channel = line.replace('Canal:', '').strip()

    steps = _extract_steps_semantic(transcript, title)
    clean_transcript = re.sub(r'^##\s+\S+\s*$', '', transcript, flags=re.MULTILINE)
    clean_transcript = re.sub(r'\n{3,}', '\n\n', clean_transcript)
    insights = _extract_key_insights(clean_transcript, steps)
    quotes = _extract_notable_quotes(transcript)
    nutrients = _extract_nutrients(clean_transcript, title)

    genres = {
        'reggaeton': ['reggaeton', 'reggaet\u00f3n', 'dembow', 'perreo'],
        'techno': ['techno', 'techpara', 'rave'],
        'eurobeat': ['eurobeat', 'super eurobeat'],
        'house': ['house', 'deep house', 'tech house'],
        'trap': ['trap', 'drill', '808'],
        'lo-fi': ['lo-fi', 'lofi', 'chillhop'],
        'rkt': ['rkt', 'rossini', 'bizet'],
        'pop': ['pop music', 'pop espa\u00f1ol', 'k-pop', 'pop rock'],
        'rock': ['rock', 'guitarra el\u00e9ctrica'],
        ' edm': ['edm', 'electronic dance'],
    }
    transcript_lower = transcript.lower()
    detected_genres = [g for g, kws in genres.items() if any(kw in transcript_lower for kw in kws)]
    if len(re.findall(r'para\s+para', transcript_lower)) >= 3:
        if 'eurobeat' not in detected_genres:
            detected_genres.append('eurobeat')

    topics = sorted(set(s['topic'] for s in steps if s['topic'] != 'general'))

    analysis = {
        'video_id': video_id,
        'title': title,
        'channel': channel,
        'analyzed_at': datetime.now().isoformat(),
        'expected_steps': expected_steps,
        'steps_found': [{'label': s['label'], 'topic': s['topic'], 'text': s['text'][:200]} for s in steps],
        'steps_count': len(steps),
        'topics_detected': topics,
        'insights': insights,
        'quotes': quotes,
        'nutrients': nutrients,
        'nutrients_count': len(nutrients),
        'detected_genres': detected_genres,
        'word_count': len(transcript.split()),
        'char_count': len(transcript),
    }

    analysis_path = ANALYSIS_DIR / f"{video_id}_analysis.json"
    with open(analysis_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    analysis_md = ANALYSIS_DIR / f"{video_id}_analysis.md"
    with open(analysis_md, 'w', encoding='utf-8') as f:
        f.write(f"# KVIS Analysis: {video_id}\n\n")
        f.write(f"**Titulo:** {title}\n")
        f.write(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Pasos detectados:** {len(steps)}")
        if expected_steps:
            f.write(f" (esperados: {expected_steps})")
        f.write("\n")
        if detected_genres:
            f.write(f"**Generos:** {', '.join(detected_genres)}\n")
        if topics:
            f.write(f"**Topicos:** {', '.join(topics)}\n")
        f.write(f"**Insights:** {len(insights)} | **Citas:** {len(quotes)} | **Nutrientes:** {len(nutrients)}\n")

        if steps:
            f.write(f"\n## Pasos/Secciones Detectados ({len(steps)})\n\n")
            for i, step in enumerate(steps, 1):
                f.write(f"### {i}. {step['label']}")
                if step['topic'] != 'general':
                    f.write(f" [{step['topic']}]")
                f.write("\n\n")
                f.write(f"> {step['text']}\n\n")

        if insights:
            f.write(f"## Insights Clave ({len(insights)})\n\n")
            for ins in insights:
                f.write(f"- **{ins['type']}:** {ins['text']}\n")
            f.write("\n")

        if quotes:
            f.write("## Citas Notables\n\n")
            for q in quotes:
                f.write(f"> \"{q}\"\n\n")

        if nutrients:
            by_cat = {}
            for n in nutrients:
                by_cat.setdefault(n['category'], []).append(n)
            f.write(f"## Nutrientes KRGN ({len(nutrients)})\n\n")
            f.write(f"> *¿Qué puede extraer KRGN de este video?*\n\n")
            for cat, items in by_cat.items():
                f.write(f"### {cat} ({len(items)})\n\n")
                for item in items:
                    rel_marker = '**' if item['relevance'] == 'ALTA' else ''
                    f.write(f"- {rel_marker}{item['nutrient']}{rel_marker}\n")
                f.write("\n")

        f.write("## Transcripcion Completa\n\n")
        f.write(transcript)

    checkpoint = load_checkpoint()
    for v in checkpoint['videos']:
        if v['video_id'] == video_id:
            v['analyzed'] = True
            v['steps_found'] = len(steps)
            v['genres'] = detected_genres
            v['topics'] = topics
            if 'title' not in v or v.get('title') == 'N/A':
                v['title'] = title
    save_checkpoint(checkpoint)

    if quiet:
        print(f"KVIS ANALYZE {video_id} → {len(steps)} pasos, {len(insights)} insights, {len(nutrients)} nutrients | {analysis_md}")
    else:
        print(f"  Pasos detectados: {len(steps)}")
        if topics:
            print(f"  Topicos: {', '.join(topics)}")
        print(f"  Insights: {len(insights)} | Citas: {len(quotes)} | Nutrientes: {len(nutrients)}")
        if detected_genres:
            print(f"  Generos: {', '.join(detected_genres)}")
        if nutrients:
            cats = sorted(set(n['category'] for n in nutrients))
            print(f"  Categorias nutrientes: {', '.join(cats)}")
        print(f"  Analisis: {analysis_md}")
    return analysis_path
