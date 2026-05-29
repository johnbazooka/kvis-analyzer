#!/usr/bin/env python3
"""
KVIS Catalog Builder v1.0 — Genera catalogo indexado de videos KVIS.
Usa autocat para clasificar automaticamente videos nuevos.
"""

import json
from pathlib import Path
from datetime import datetime

from .constants import ANALYSIS_DIR, DATA_DIR
from .autocat import auto_categorize

CATALOG_JSON = DATA_DIR / "kvis_catalog.json"
CATALOG_MD = DATA_DIR / "kvis_catalog.md"

CATEGORIES = {
    "industria": {
        "label": "Industria Musical",
        "icon": "🏭",
        "description": "Negocio, disqueras, contratos, dinero, industria chilena/global"
    },
    "produccion": {
        "label": "Producción Musical",
        "icon": "🎹",
        "description": "Técnicas de producción, mixing, mastering, DAW, workflow"
    },
    "marketing": {
        "label": "Marketing & Estrategia",
        "icon": "📊",
        "description": "Branding, lanzamientos, estrategia de carrera, posicionamiento"
    },
    "cultura": {
        "label": "Cultura & Análisis Musical",
        "icon": "🎧",
        "description": "Análisis de géneros, artistas, movimientos, crítica musical"
    },
    "mindset": {
        "label": "Mindset & Creatividad",
        "icon": "🧠",
        "description": "Motivación, creatividad, bloqueos, filosofía artística"
    },
    "tecnologia": {
        "label": "Tecnología & IA",
        "icon": "🤖",
        "description": "IA en música, herramientas tech, futuro de la industria"
    },
    "propio": {
        "label": "BZK (Propio)",
        "icon": "🔥",
        "description": "Videos propios de John Bazooka"
    },
    "sin_procesar": {
        "label": "Sin Procesar",
        "icon": "⏳",
        "description": "Videos con pipeline parcial (sin nutrientes)"
    }
}


def ensure_categorized():
    """Ensure all analysis files have category + tags, auto-categorize if missing."""
    updated = 0
    for fp in sorted(ANALYSIS_DIR.glob("*_analysis.json")):
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)

        has_cat = data.get("category")
        has_tags = data.get("tags")
        has_nutrients = len(data.get("nutrients", [])) > 0

        if has_cat and has_tags and has_nutrients:
            continue

        if not has_nutrients and not data.get("title"):
            data["category"] = "sin_procesar"
            data["tags"] = []
        elif has_nutrients and (not has_cat or not has_tags):
            category, tags = auto_categorize(data)
            data["category"] = category
            data["tags"] = tags
        else:
            continue

        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        updated += 1

    return updated


def build_catalog():
    """Generar kvis_catalog.json y kvis_catalog.md."""
    entries = []
    for fp in sorted(ANALYSIS_DIR.glob("*_analysis.json")):
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)

        vid = data.get("video_id", "?")
        title = data.get("title") or "Sin título"
        channel = data.get("channel") or "?"
        n_nutrients = len(data.get("nutrients", []))
        category = data.get("category", "sin_procesar")
        tags = data.get("tags", [])
        analyzed_at = data.get("analyzed_at", "?")

        entries.append({
            "video_id": vid,
            "title": title,
            "channel": channel,
            "nutrients": n_nutrients,
            "category": category,
            "tags": tags,
            "analyzed_at": analyzed_at
        })

    # JSON catalog
    catalog = {
        "version": "1.1",
        "generated_at": datetime.now().isoformat(),
        "total_videos": len(entries),
        "categories": {k: v["label"] for k, v in CATEGORIES.items()},
        "videos": entries
    }

    with open(CATALOG_JSON, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    # MD catalog
    md_lines = [
        "# KVIS Catalog — Videos Analizados\n",
        f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M')} | **Total:** {len(entries)} videos\n",
        "---\n"
    ]

    by_cat = {}
    for e in entries:
        by_cat.setdefault(e["category"], []).append(e)

    for cat_key, cat_info in CATEGORIES.items():
        vids = by_cat.get(cat_key, [])
        if not vids:
            continue

        md_lines.append(f"## {cat_info['icon']} {cat_info['label']}")
        md_lines.append(f"*{cat_info['description']}* ({len(vids)} videos)\n")

        for e in vids:
            tag_str = ", ".join(f"`{t}`" for t in e["tags"]) if e["tags"] else "*sin tags*"
            md_lines.append(
                f"- **[{e['video_id']}]** {e['title']}  "
                f"*({e['channel']})* — {e['nutrients']} nutrientes | {tag_str}"
            )

        md_lines.append("")

    md_lines.append("---\n")
    md_lines.append("## Estadísticas\n")
    md_lines.append("| Categoría | Videos | Nutrientes |")
    md_lines.append("|-----------|:------:|:----------:|")
    for cat_key, cat_info in CATEGORIES.items():
        vids = by_cat.get(cat_key, [])
        if not vids:
            continue
        total_n = sum(v["nutrients"] for v in vids)
        md_lines.append(f"| {cat_info['icon']} {cat_info['label']} | {len(vids)} | {total_n} |")

    total_nutrients = sum(e["nutrients"] for e in entries)
    md_lines.append(f"| **Total** | **{len(entries)}** | **{total_nutrients}** |")

    with open(CATALOG_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return len(entries)


if __name__ == "__main__":
    print("Ensuring all videos categorized...")
    n = ensure_categorized()
    print(f"  -> {n} files auto-categorized")

    print("Building catalog...")
    total = build_catalog()
    print(f"  -> {total} videos cataloged")
    print(f"  -> {CATALOG_JSON}")
    print(f"  -> {CATALOG_MD}")
