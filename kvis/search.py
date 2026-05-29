import re
import json
import math
from pathlib import Path

from .constants import (
    TRANSCRIPTS_DIR, ANALYSIS_DIR, CONNECTIONS_FILE,
    # removed KRGN store
)
from .utils import load_checkpoint
from .extract import _split_into_paragraphs

def _load_connection_scores():
    if not CONNECTIONS_FILE.exists():
        return {}
    try:
        data = json.loads(CONNECTIONS_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}
    scores = {}
    for conn in data.get('connections', []):
        strength = conn.get('strength', 1)
        for side in ('from', 'to'):
            sid = conn[side].get('id', '')
            store = conn[side].get('store', '')
            if not sid:
                continue
            key = f"{store}:{sid}"
            scores[key] = scores.get(key, 0) + strength
            if store == 'kvis_video':
                scores[f"video:{sid}"] = scores.get(f"video:{sid}", 0) + strength
    return scores


def do_search(query, top_n=5, scope='all', use_connections=True, engine='tfidf'):
    import numpy as np

    checkpoint = load_checkpoint()
    videos = checkpoint.get('videos', [])
    if not videos and scope != 'krgn':
        print("KVIS SEARCH | Sin videos procesados")
        return None

    documents = []
    meta = []

    for v in videos:
        vid = v['video_id']
        title = v.get('title', '')
        vtype = v.get('video_type', '')
        channel = v.get('channel', '')

        transcript_candidates = list(TRANSCRIPTS_DIR.glob(f"{vid}_clean.txt"))
        if not transcript_candidates:
            transcript_candidates = list(TRANSCRIPTS_DIR.glob(f"{vid}_timestamped.txt"))
        if not transcript_candidates:
            transcript_candidates = list(TRANSCRIPTS_DIR.glob(f"{vid}.txt"))
        transcript_text = ''
        if transcript_candidates:
            with open(transcript_candidates[0], 'r', encoding='utf-8') as f:
                transcript_text = f.read()

        if scope in ('all', 'transcripts') and transcript_text:
            docs = _split_into_paragraphs(transcript_text, max_para_chars=600)
            for i, doc in enumerate(docs):
                documents.append(doc)
                meta.append({
                    'video_id': vid, 'title': title, 'channel': channel,
                    'source': 'transcript', 'segment': i,
                    'total_segments': len(docs),
                })

        analysis_path = ANALYSIS_DIR / f"{vid}_analysis.json"
        if scope in ('all', 'nutrients') and analysis_path.exists():
            try:
                with open(analysis_path, 'r', encoding='utf-8') as f:
                    analysis = json.load(f)
                for n in analysis.get('nutrients', []):
                    nutrient_text = f"{n.get('nutrient', '')} {n.get('category', '')} {n.get('context', '')}"
                    if nutrient_text.strip():
                        documents.append(nutrient_text)
                        meta.append({
                            'video_id': vid, 'title': title, 'channel': channel,
                            'source': 'nutrient', 'category': n.get('category', ''),
                            'relevance': n.get('relevance', ''),
                            'bzk_tag': n.get('bzk_tag', ''),
                        })
                for ins in analysis.get('insights', []):
                    if ins.get('text', '').strip():
                        documents.append(ins['text'])
                        meta.append({
                            'video_id': vid, 'title': title, 'channel': channel,
                            'source': 'insight',
                        })
                for q in analysis.get('quotes', []):
                    if q.get('text', '').strip():
                        documents.append(q['text'])
                        meta.append({
                            'video_id': vid, 'title': title, 'channel': channel,
                            'source': 'quote',
                        })
            except Exception:
                pass

    if scope in ('all', 'krgn'):
        try:
            dt_data = None  # removed KRGN store)
            for trail in dt_data.get('trails', []):
                text_parts = [trail.get('title', ''), trail.get('description', '')]
                if trail.get('patterns_discovered'):
                    text_parts.extend(trail['patterns_discovered'][:3])
                doc_text = ' '.join(text_parts).strip()
                if doc_text:
                    documents.append(doc_text)
                    meta.append({
                        'source': 'decision_trail',
                        'store_id': trail.get('id', ''),
                        'title': trail.get('title', '')[:80],
                        'date': trail.get('date', ''),
                    })
        except Exception:
            pass

        try:
            pl_data = None  # removed KRGN store)
            for pat in pl_data.get('patrones_activos', []):
                text_parts = [pat.get('nombre', ''), pat.get('descripcion', ''), pat.get('recomendacion', '')]
                doc_text = ' '.join(text_parts).strip()
                if doc_text:
                    documents.append(doc_text)
                    meta.append({
                        'source': 'pattern_log',
                        'store_id': pat.get('id', ''),
                        'pattern_name': pat.get('nombre', ''),
                        'estado': pat.get('estado', ''),
                    })
        except Exception:
            pass

        try:
            mp_data = None  # removed KRGN store)
            for proj in mp_data.get('proyectos', []):
                text_parts = [proj.get('titulo', ''), proj.get('genero', '')]
                if proj.get('fuentes_investigacion'):
                    text_parts.extend(proj['fuentes_investigacion'][:3])
                if proj.get('aplicacion_jb'):
                    text_parts.append(proj['aplicacion_jb'])
                doc_text = ' '.join(str(p) for p in text_parts).strip()
                if doc_text:
                    documents.append(doc_text)
                    meta.append({
                        'source': 'music_production',
                        'store_id': proj.get('id', ''),
                        'titulo': proj.get('titulo', '')[:80],
                        'estado': proj.get('estado', ''),
                        'genero': proj.get('genero', ''),
                    })
        except Exception:
            pass

    if not documents:
        print("KVIS SEARCH | Sin documentos para buscar")
        return None

    conn_scores = _load_connection_scores() if use_connections else {}

    krgn_count = sum(1 for m in meta if m.get('source') in ('decision_trail', 'pattern_log', 'music_production'))
    video_count = sum(1 for m in meta if m.get('source') not in ('decision_trail', 'pattern_log', 'music_production'))
    print(f"KVIS SEARCH | Buscando: \"{query}\"")
    print(f"  Engine: {engine} | Index: {len(documents)} segmentos | {video_count} video | {krgn_count} KRGN stores{' | connections: ON' if conn_scores else ' | connections: OFF'}")
    print("=" * 60)

    if engine == 'neural':
        from sentence_transformers import SentenceTransformer
        print("  Cargando modelo neural (primera vez = descarga ~420MB)...")
        model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        print("  Generando embeddings...")
        doc_embeddings = model.encode(documents, show_progress_bar=False, batch_size=32, normalize_embeddings=True)
        query_embedding = model.encode([query], show_progress_bar=False, normalize_embeddings=True)
        scores = np.dot(query_embedding, doc_embeddings.T).flatten()
    else:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            stop_words=None,
            lowercase=True,
        )
        tfidf_matrix = vectorizer.fit_transform(documents)
        query_vec = vectorizer.transform([query])
        scores = cosine_similarity(query_vec, tfidf_matrix).flatten()

    if conn_scores:
        for idx in range(len(meta)):
            m = meta[idx]
            boost = 0.0
            vid = m.get('video_id', '')
            store_id = m.get('store_id', '')
            source = m.get('source', '')
            if vid:
                boost += conn_scores.get(f"video:{vid}", 0) * 0.005
            if store_id and source:
                store_map = {'decision_trail': 'decision_trail', 'pattern_log': 'pattern_log', 'music_production': 'music_production'}
                s = store_map.get(source, '')
                if s:
                    boost += conn_scores.get(f"{s}:{store_id}", 0) * 0.005
            scores[idx] = min(scores[idx] + boost, 1.0)

    top_indices = scores.argsort()[-top_n:][::-1]

    results = []
    for idx in top_indices:
        if scores[idx] < 0.01:
            continue
        m = meta[idx]
        doc = documents[idx]
        score = scores[idx]
        results.append({'meta': m, 'text': doc, 'score': score})

    if not results:
        print("  Sin resultados relevantes.")
        return results

    for i, r in enumerate(results, 1):
        m = r['meta']
        score_pct = r['score'] * 100
        source_tag = m.get('source', '?')
        vid = m.get('video_id', '')
        if source_tag == 'nutrient':
            source_tag = f"nutrient:{m.get('category', '?')} [{m.get('bzk_tag', '')}]"
        elif source_tag == 'transcript':
            source_tag = f"transcript [{m.get('segment', 0)+1}/{m.get('total_segments', '?')}]"
        elif source_tag == 'decision_trail':
            source_tag = f"decision_trail [{m.get('store_id', '')}]"
            vid = m.get('store_id', '')
        elif source_tag == 'pattern_log':
            source_tag = f"pattern_log [{m.get('pattern_name', '')}]"
            vid = m.get('store_id', '')
        elif source_tag == 'music_production':
            source_tag = f"music_prod [{m.get('genero', '')}]"
            vid = m.get('store_id', '')[:20]

        print(f"\n  [{i}] Score: {score_pct:.1f}% | {source_tag}")
        label = m.get('title', '') or m.get('pattern_name', '') or m.get('store_id', '')
        print(f"      {label[:70]}")
        print(f"      {r['text'][:150]}{'...' if len(r['text']) > 150 else ''}")

    return results


