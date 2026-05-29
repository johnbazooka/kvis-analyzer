import sys
import argparse

from .extract import do_extract
from .analyze import do_analyze
from .audio import do_audio
from .spectral import do_spectral
from .cross import do_crossanalyze
from .compare import do_crosscompare
from .classify import classify_video
from .teach import do_teach
from .reducer import do_reducer
from .integrate import do_integrate, do_map
from .pipeline import do_process, do_deep, do_batch
from .search import do_search
from .keyframes import do_keyframes, do_describe_keyframes
from .comments import do_comments
from .smart import do_smart
from .audience import do_audience
from .synthesize import do_synthesize
from .status import do_status
from .build_catalog import build_catalog
from .utils import extract_video_id


def _do_catalog(args):
    import json
    from pathlib import Path

    catalog_path = Path("CORE/data/kvis/kvis_catalog.json")

    if args.rebuild:
        print("Reconstruyendo catalogo...")
        from .build_catalog import inject_tags
        inject_tags()
        build_catalog()
        print("Catalogo reconstruido.")

    if not catalog_path.exists():
        print("No existe catalogo. Usa --rebuild para generarlo.")
        return None

    with open(catalog_path, encoding="utf-8") as f:
        catalog = json.load(f)

    videos = catalog["videos"]

    if args.category:
        videos = [v for v in videos if v["category"] == args.category]
    if args.tag:
        videos = [v for v in videos if args.tag in v.get("tags", [])]

    if not videos:
        print("No se encontraron videos con ese filtro.")
        return None

    cat_labels = catalog.get("categories", {})
    for v in videos:
        cat = v["category"]
        label = cat_labels.get(cat, cat)
        tags = ", ".join(v["tags"]) if v["tags"] else "-"
        print(f"[{v['video_id']}] {v['title']}")
        print(f"  {label} | {v['channel']} | {v['nutrients']} nutrientes | {tags}")

    print(f"\nTotal: {len(videos)} videos")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='KVIS v3.9 - KRGN Video Knowledge Infusion System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest='command')

    p_extract = sub.add_parser('extract', help='Extraer transcripcion de YouTube')
    p_extract.add_argument('url', help='URL o video ID')
    p_extract.add_argument('--lang', default='es', help='Idioma (default: es)')
    p_extract.add_argument('--force', action='store_true', help='Saltar transcript-api')

    p_analyze = sub.add_parser('analyze', help='Analizar transcripcion extraida')
    p_analyze.add_argument('video_id', help='Video ID')
    p_analyze.add_argument('--expected-steps', type=int, default=0)
    p_analyze.add_argument('--quiet', '-q', action='store_true', help='Solo resumen, sin output completo')

    p_map = sub.add_parser('map', help='Mapear insights a proyectos KRGN')
    p_map.add_argument('video_id', help='Video ID')
    p_map.add_argument('--keywords', nargs='+')
    p_map.add_argument('--add-project', metavar='TITLE')
    p_map.add_argument('--era', default='')
    p_map.add_argument('--priority', default='HIGH')

    p_audio = sub.add_parser('audio', help='Descargar audio MP3')
    p_audio.add_argument('url', help='URL o video ID')
    p_audio.add_argument('--output', help='Directorio de salida')

    p_process = sub.add_parser('process', help='Pipeline: extract + analyze')
    p_process.add_argument('url', help='URL o video ID')
    p_process.add_argument('--lang', default='es')
    p_process.add_argument('--expected-steps', type=int, default=0)
    p_process.add_argument('--quiet', '-q', action='store_true', help='Solo resumen')

    p_spectral = sub.add_parser('spectral', help='Analisis espectral de audio')
    p_spectral.add_argument('video_id', help='Video ID')

    p_cross = sub.add_parser('cross', help='Cross-analysis: subtitulos + spectral')
    p_cross.add_argument('video_id', help='Video ID')

    p_deep = sub.add_parser('deep', help='Pipeline completo: extract + audio + spectral + cross')
    p_deep.add_argument('url', help='URL o video ID')
    p_deep.add_argument('--lang', default='es')
    p_deep.add_argument('--auto-integrate', action='store_true', help='Integrar hallazgos automaticamente')
    p_deep.add_argument('--quiet', '-q', action='store_true', help='Solo resumen')

    p_batch = sub.add_parser('batch', help='Procesar multiples URLs (una por linea o archivo)')
    p_batch.add_argument('urls', nargs='*', help='URLs o path a archivo .txt')
    p_batch.add_argument('--file', '-f', help='Archivo con URLs (una por linea)')
    p_batch.add_argument('--lang', default='es')
    p_batch.add_argument('--auto-integrate', action='store_true', help='Integrar hallazgos automaticamente')

    p_integrate = sub.add_parser('integrate', help='Integrar hallazgos a KRGN knowledge stores')
    p_integrate.add_argument('video_id', help='Video ID')
    p_integrate.add_argument('--decision', help='Descripcion para decision_trail')
    p_integrate.add_argument('--pattern', action='append', help='nombre|desc para pattern_log (repetible)')
    p_integrate.add_argument('--project', help='Titulo de proyecto para music_production')
    p_integrate.add_argument('--project-genre', help='Genero del proyecto')

    p_teach = sub.add_parser('teach', help='Mostrar leccion aprendida del video')
    p_teach.add_argument('video_id', help='Video ID')
    p_teach.add_argument('--quiet', '-q', action='store_true', help='Solo resumen, sin output completo')

    p_reducer = sub.add_parser('reducer', help='Filtrar nutrients con BZK Lens: BZK-ALIGNED vs GENERICO')
    p_reducer.add_argument('video_id', help='Video ID')
    p_reducer.add_argument('--quiet', '-q', action='store_true', help='Solo resumen, sin output completo')

    p_crosscmp = sub.add_parser('crosscompare', help='Comparar multiples videos con spectral + tecnicas')
    p_crosscmp.add_argument('video_ids', nargs='*', help='Video IDs a comparar (vacio = todos)')
    p_crosscmp.add_argument('--group-by', default='channel', choices=['channel', 'genre'], help='Agrupar por canal o genero')
    p_crosscmp.add_argument('--name', help='Nombre para el archivo de salida')
    p_crosscmp.add_argument('--quiet', '-q', action='store_true', help='Solo resumen')

    p_status = sub.add_parser('status', help='Ver videos procesados')
    p_status.add_argument('--verbose', '-v', action='store_true')

    p_search = sub.add_parser('search', help='Busqueda semantica en transcripts, nutrientes y stores KRGN')
    p_search.add_argument('query', help='Query de busqueda')
    p_search.add_argument('--top', '-n', type=int, default=5, help='Resultados (default: 5)')
    p_search.add_argument('--scope', default='all', choices=['all', 'transcripts', 'nutrients', 'krgn'], help='Alcance de busqueda')
    p_search.add_argument('--no-connections', action='store_true', help='Desactivar boost por conexiones KRGN')
    p_search.add_argument('--engine', default='tfidf', choices=['tfidf', 'neural'], help='Motor de busqueda (default: tfidf, neural=sentence-transformers)')

    p_keyframes = sub.add_parser('keyframes', help='Extraer keyframes de video (scene detection o intervalo)')
    p_keyframes.add_argument('url', help='URL o video ID')
    p_keyframes.add_argument('--mode', default='scene', choices=['scene', 'interval'], help='scene=deteccion de cambios, interval=cada N fps (default: scene)')
    p_keyframes.add_argument('--fps', type=float, default=0.5, help='Frames por segundo (solo interval mode, default: 0.5)')
    p_keyframes.add_argument('--max', type=int, default=30, help='Maximo de frames (default: 30)')
    p_keyframes.add_argument('--threshold', type=float, default=0.3, help='Sensibilidad scene detection (default: 0.3)')

    p_comments = sub.add_parser('comments', help='Analizar comentarios de audiencia YouTube')
    p_comments.add_argument('url', help='URL de video, video ID, URL de canal (/channel/ID), o @handle')
    p_comments.add_argument('--videos', nargs='+', help='Video IDs adicionales para analisis multi-video')
    p_comments.add_argument('--quiet', '-q', action='store_true', help='Solo resumen')

    p_smart = sub.add_parser('smart', help='Auto-detectar tipo y ejecutar pipeline optimo')
    p_smart.add_argument('url', help='URL de video o canal')
    p_smart.add_argument('--lang', default='es', help='Idioma (default: es)')
    p_smart.add_argument('--quiet', '-q', action='store_true', help='Solo resumen')

    p_audience = sub.add_parser('audience', help='Cross-analisis de audiencias (2+ canales)')
    p_audience.add_argument('urls', nargs='+', help='URLs de canales a comparar')
    p_audience.add_argument('--quiet', '-q', action='store_true', help='Solo resumen')

    p_synthesize = sub.add_parser('synthesize', help='Sintetizar nutrientes de multiples videos')
    p_synthesize.add_argument('video_ids', nargs='*', help='Video IDs (vacio = todos los analizados)')
    p_synthesize.add_argument('--quiet', '-q', action='store_true', help='Solo resumen')

    p_describe = sub.add_parser('describe', help='Analisis visual de keyframes extraidos (color/brillo/complejidad)')
    p_describe.add_argument('video_id', help='Video ID con keyframes ya extraidos')

    p_catalog = sub.add_parser('catalog', help='Ver/actualizar catalogo de videos analizados')
    p_catalog.add_argument('--rebuild', '-r', action='store_true', help='Regenerar catalogo desde analysis files')
    p_catalog.add_argument('--category', '-c', help='Filtrar por categoria (industria, produccion, marketing, cultura, mindset, tecnologia, propio)')
    p_catalog.add_argument('--tag', '-t', help='Filtrar por tag')

    args = parser.parse_args()

    commands = {
        'extract': lambda: do_extract(args.url, args.lang, args.force),
        'analyze': lambda: do_analyze(args.video_id, args.expected_steps, getattr(args, 'quiet', False)),
        'map': lambda: do_map(args.video_id, args.keywords, args.add_project, args.era, args.priority),
        'audio': lambda: do_audio(args.url, args.output),
        'process': lambda: do_process(args.url, args.lang, args.expected_steps, getattr(args, 'quiet', False)),
        'spectral': lambda: do_spectral(args.video_id),
        'cross': lambda: do_crossanalyze(args.video_id),
        'deep': lambda: do_deep(args.url, args.lang, args.auto_integrate, getattr(args, 'quiet', False)),
        'batch': lambda: do_batch(args.urls, args.file, args.lang, args.auto_integrate),
        'integrate': lambda: do_integrate(args.video_id, args.decision, args.pattern, args.project, args.project_genre),
        'teach': lambda: do_teach(args.video_id, getattr(args, 'quiet', False)),
        'reducer': lambda: do_reducer(args.video_id, getattr(args, 'quiet', False)),
        'crosscompare': lambda: do_crosscompare(args.video_ids if args.video_ids else None, args.group_by, args.name, getattr(args, 'quiet', False)),
        'status': lambda: do_status(args.verbose),
        'search': lambda: do_search(args.query, args.top, args.scope, not args.no_connections, args.engine),
        'keyframes': lambda: do_keyframes(args.url, args.mode, args.fps, args.max, args.threshold),
        'comments': lambda: do_comments(args.url, getattr(args, 'videos', None), getattr(args, 'quiet', False)),
        'smart': lambda: do_smart(args.url, getattr(args, 'lang', 'es'), getattr(args, 'quiet', False)),
        'audience': lambda: do_audience(args.urls, getattr(args, 'quiet', False)),
        'synthesize': lambda: do_synthesize(args.video_ids if args.video_ids else None, getattr(args, 'quiet', False)),
        'describe': lambda: do_describe_keyframes(args.video_id),
        'catalog': lambda: _do_catalog(args),
    }

    if args.command in commands:
        result = commands[args.command]()
        sys.exit(0 if result is not None else 1)
    else:
        parser.print_help()
