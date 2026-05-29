#!/usr/bin/env python3
"""
KVIS Auto-Categorize v1.0 — Clasifica automaticamente videos por categoria y tags.
Usa titulo, canal, generos, nutrientes y keywords para determinar categoria.
"""

import re
import unicodedata
from typing import Dict, List, Tuple
from collections import Counter


def _normalize(text: str) -> str:
    """Remove accents for matching."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()


CATEGORY_RULES = [
    ("industria", {
        "channels": [
            "creadores de hits", "hablemos de hits", "soycepa"
        ],
        "title_keywords": [
            "disquera", "discografica", "sello", "contrato", "royalty", "royalties",
            "industria", "plataforma", "spotify", "streaming", "dinero", "millones",
            "ventas", "carrera", "artista emergente", "lanzamiento", "album",
            "sencillo", "independiente", "independencia"
        ],
        "nutrient_categories": ["INDUSTRIA"],
        "genre_boost": [],
    }),
    ("produccion", {
        "channels": [
            "alegria maxima", "dimelosmooth", "servando roofing",
            "holly", "saski"
        ],
        "title_keywords": [
            "produccion", "produccion musical", "ingeniero", "mezcla", "master",
            "mastering", "mixing", "grabacion", "daw", "fl studio", "ableton",
            "pro tools", "plugin", "plugin", "sintetizador", "bajo", "bateria",
            "composicion", "arreglo", "beat", "instrumental", "tracking",
            "microfono", "ecualizador", "compresor", "reverb", "delay",
            "ingeniero de sonido", "sonido", "studio", "estudio"
        ],
        "nutrient_categories": ["TECNICA"],
        "genre_boost": [],
    }),
    ("marketing", {
        "channels": [
            "bext postgraduate", "riversal", "mi disquera"
        ],
        "title_keywords": [
            "marketing", "estrategia", "branding", "lanzamiento", "promocion",
            "redes sociales", "instagram", "tiktok", "youtube", "contenido",
            "portada", "portadas", "cover", "imagen", "posicionamiento", "audiencia",
            "fans", "comunidad", "viral", "ascenso", "exito", "formula",
            "secreto", "como triunfar", "como crecer"
        ],
        "nutrient_categories": [],
        "genre_boost": [],
    }),
    ("cultura", {
        "channels": [
            "aj one", "el movimiento podcast", "kason",
            "beno espinosa"
        ],
        "title_keywords": [
            "reggaeton", "regueton", "genero", "historia", "movimiento",
            "residente", "odio", "critica", "conformista", "vendio",
            "vendo", "politica", "chile", "kidd voodoo", "artista",
            "musica urbana", "trap", "analisis", "realidad"
        ],
        "nutrient_categories": ["GENERO", "REFERENCIAS"],
        "genre_boost": ["reggaeton", "trap", "rock", "pop"],
    }),
    ("mindset", {
        "channels": [
            "obac", "roberto cosmico", "proyecto progresivo", "trending tony"
        ],
        "title_keywords": [
            "bloqueado", "creatividad", "motivacion", "por amor",
            "resultado", "filosofia", "manipulacion", "psicologia",
            "pensar", "piensa", "opinion", "valentia", "autenticidad",
            "superacion", "mente", "mentalidad", "habito", "disciplina",
            "miedo", "fracaso", "exito personal", "nadie dice"
        ],
        "nutrient_categories": ["SABIDURIA", "CREATIVO"],
        "genre_boost": [],
    }),
    ("tecnologia", {
        "channels": [
            "gustavo entrala"
        ],
        "title_keywords": [
            "inteligencia artificial", "ia ", "ai ", "tecnologia", "futuro",
            "automatizacion", "machine learning", "robot", "digital",
            "herramienta", "software", "app", "algoritmo"
        ],
        "nutrient_categories": [],
        "genre_boost": [],
    }),
    ("propio", {
        "channels": [
            "a.k.a. john bazooka", "john bazooka", "a.k.a. john bazooka official",
            "bazooka"
        ],
        "title_keywords": [],
        "nutrient_categories": [],
        "genre_boost": [],
    }),
]

TAG_EXTRACTORS = {
    "disquera": ["disquera", "discografica", "sello discografico", "warner", "universal", "sony"],
    "warner": ["warner"],
    "produccion": ["produccion", "produccion musical", "producir"],
    "A&R": ["a&r", "artist and repertoire"],
    "proceso": ["proceso", "workflow", "flujo de trabajo"],
    "tainy": ["tainy"],
    "productor": ["productor", "produccion"],
    "reggaeton": ["reggaeton", "regueton", "perreo"],
    "industria": ["industria", "negocio"],
    "colaboracion": ["colaboracion", "feat", "featuring", "feature"],
    "podcast": ["podcast", "episodio", "ep ", "cap "],
    "standly": ["standly"],
    "dinero": ["dinero", "dolares", "millones", "plata", "ganar"],
    "industria_chilena": ["chile", "chilena", "chileno"],
    "crisis": ["crisis", "quiebra", "deuda"],
    "recuperacion": ["recuper", "reinvent"],
    "independiente": ["independiente", "indie", "solo"],
    "tyto_kush": ["tyto kush"],
    "martinwhite": ["martinwhite", "martin white"],
    "estrategia": ["estrategia", "plan", "formula"],
    "exito": ["exito", "exitoso", "triunfar"],
    "marketing": ["marketing", "promocion", "publicidad"],
    "artista emergente": ["artista emergente", "emergente", "nuevo"],
    "rosalia": ["rosalia"],
    "branding": ["branding", "marca", "identidad"],
    "carrera": ["carrera", "trayectoria"],
    "posicionamiento": ["posicionamiento", "posicionar"],
    "album": ["album", "disco", "ep ", "lp "],
    "lanzamiento": ["lanzamiento", "release", "estreno"],
    "portadas": ["portada", "cover", "arte de tapa"],
    "visual": ["visual", "imagen", "estetica"],
    "arte": ["arte", "artistico"],
    "tutorial": ["tutorial", "como hacer", "paso a paso"],
    "workflow": ["workflow", "rutina", "proceso"],
    "tecnica": ["tecnica", "metodo", "tecnico"],
    "ingeniero": ["ingeniero", "sonido", "mezcla", "master"],
    "mezcla": ["mezcla", "mixing", "mix"],
    "mastering": ["mastering", "masterizar", "master"],
    "grabacion": ["grabacion", "grabar", "recording"],
    "residente": ["residente", "rene"],
    "historia": ["historia", "origen"],
    "odio": ["odio", "odiar"],
    "movimiento": ["movimiento", "escena"],
    "artistas": ["artista", "musicos"],
    "conformismo": ["conformista", "conformismo", "comodo"],
    "critica": ["critica", "criticar", "opinion"],
    "kidd_voodoo": ["kidd voodoo", "kid voodoo"],
    "venta": ["vender", "vendio", "venta", "vendido"],
    "genero": ["genero", "estilo"],
    "analisis": ["analisis", "analizar"],
    "politica": ["politica", "kast", "gobierno"],
    "chile": ["chile"],
    "kast": ["kast"],
    "peter_thiel": ["peter thiel", "thiel"],
    "actualidad": ["actualidad", "noticia"],
    "autenticidad": ["autentico", "autenticidad", "auténtico"],
    "opinion": ["opinion", "pensar", "piensa"],
    "filosofia": ["filosofia", "filosofico"],
    "valentia": ["valentia", "valiente", "coraje"],
    "manipulacion": ["manipulacion", "manipular"],
    "psicologia": ["psicologia", "psicologico"],
    "persuasion": ["persuasion", "persuadir", "convencer"],
    "amor": ["amor", "pasión"],
    "resultado": ["resultado", "exito", "fruto"],
    "bloqueo": ["bloqueado", "bloqueo", "block"],
    "creatividad": ["creatividad", "creativo", "crear"],
    "superacion": ["superacion", "superar", "mejorar"],
    "motivacion": ["motivacion", "motivar", "inspirar"],
    "IA": ["inteligencia artificial", "ia ", "ai ", "gpt", "chatgpt"],
    "futuro": ["futuro", "futurologo"],
    "costo": ["costo", "caro", "pagar", "precio"],
    "tecnologia": ["tecnologia", "tech", "digital"],
    "remix": ["remix", "remix"],
    "kpop": ["kpop", "k-pop", "loona", "triple"],
    "guaracha": ["guaracha"],
    "aleteo": ["aleteo"],
    "identidad": ["identidad", "identificar"],
    "minimalismo": ["minimalista", "minimalismo", "simple"],
    "nostalgia": ["nostalgia", "nostalgico"],
    "emocion": ["emocion", "sentimiento"],
    "transformacion": ["transform", "cambio", "evolucion"],
}


def auto_categorize(analysis: Dict) -> Tuple[str, List[str]]:
    """
    Dado un dict de analysis, retorna (category, tags).
    Prioridad: canal propio > scores por reglas.
    """
    title = _normalize(analysis.get("title") or "")
    channel = _normalize(analysis.get("channel") or "")
    genres = [_normalize(g) for g in (analysis.get("detected_genres") or [])]
    nutrient_cats = [n.get("category", "").upper() for n in (analysis.get("nutrients") or [])]
    nutrient_words = []
    for n in (analysis.get("nutrients") or []):
        nutrient_words.extend(_normalize(n.get("nutrient", "") or "").split())

    text = f"{title} {channel} {' '.join(genres)} {' '.join(nutrient_words[:100])}"

    scores = {}
    channel_matched = None
    for cat, rules in CATEGORY_RULES:
        score = 0.0

        # Channel match (strongest signal)
        for ch in rules["channels"]:
            if ch in channel:
                score += 10.0
                if channel_matched is None:
                    channel_matched = cat

        # Title keywords
        for kw in rules["title_keywords"]:
            if kw in title:
                score += 2.0

        # Nutrient categories
        nc_counter = Counter(nutrient_cats)
        for nc in rules["nutrient_categories"]:
            score += nc_counter.get(nc, 0) * 0.3

        # Genre boost
        for g in rules["genre_boost"]:
            if g in genres:
                score += 1.0

        scores[cat] = score

    # If channel matched, use that category (channel is definitive)
    if channel_matched:
        best_cat = channel_matched
    else:
        best_cat = max(scores, key=scores.get)
        if scores[best_cat] == 0:
            best_cat = "cultura"

    # Extract tags
    tags = []
    for tag, keywords in TAG_EXTRACTORS.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)

    # Remove duplicates while preserving order, limit to 8
    seen = set()
    unique_tags = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique_tags.append(t)
            if len(unique_tags) >= 8:
                break

    return best_cat, unique_tags


def auto_categorize_file(video_id: str) -> Tuple[str, List[str]]:
    """Read analysis file, auto-categorize, write back category + tags."""
    import json
    from .constants import ANALYSIS_DIR

    fp = ANALYSIS_DIR / f"{video_id}_analysis.json"
    if not fp.exists():
        return "sin_procesar", []

    with open(fp, encoding="utf-8") as f:
        data = json.load(f)

    # Skip if already categorized and has nutrients
    if data.get("category") and data.get("tags") and len(data.get("nutrients", [])) > 0:
        return data["category"], data["tags"]

    category, tags = auto_categorize(data)
    data["category"] = category
    data["tags"] = tags

    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return category, tags
