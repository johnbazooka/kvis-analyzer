import sys
import re
from pathlib import Path

from .utils import extract_video_id, load_checkpoint, save_checkpoint
from .extract import do_extract
from .analyze import do_analyze
from .audio import do_audio
from .spectral import do_spectral
from .classify import classify_video
from .cross import do_crossanalyze
from .teach import do_teach
from .comments import do_comments
from .integrate import _auto_integrate
from .autocat import auto_categorize_file
from .build_catalog import build_catalog

def do_process(url, lang='es', expected_steps=0, quiet=False):
    print(f"KVIS PROCESS | Pipeline completo")
    print("=" * 60)

    result = do_extract(url, lang=lang)
    if not result:
        return 1

    video_id = extract_video_id(url)
    do_analyze(video_id, expected_steps=expected_steps, quiet=quiet)

    cat, tags = auto_categorize_file(video_id)
    print(f"\n  CATEGORIA: {cat} | Tags: {', '.join(tags)}")

    cat, tags = auto_categorize_file(video_id)
    print(f"\n  CATEGORIA: {cat} | Tags: {', '.join(tags)}")

    print("\n[TEACH] Leccion del video:")
    print("-" * 40)
    do_teach(video_id, quiet=quiet)

    print("\n[INTEGRATE] Nutrientes → KRGN:")
    print("-" * 40)
    _auto_integrate(video_id)

    return 0



def do_deep(url, lang='es', auto_integrate=False, quiet=False):
    video_id = extract_video_id(url)
    url = url if 'http' in url else f"https://youtu.be/{video_id}"

    print(f"KVIS DEEP | {video_id} | Pipeline inteligente")
    print("=" * 60)

    # Phase 1: Extract + Audio (always)
    print("\n[1/4] EXTRACT transcripcion...")
    result = do_extract(url, lang=lang)
    if not result:
        print("  FALLA en extract. Abortando deep.")
        return 1

    print("\n[2/4] AUDIO descarga...")
    do_audio(url)

    print("\n[3/4] SPECTRAL analisis...")
    spectral_result = do_spectral(video_id)
    if not spectral_result:
        print("  Spectral falla (sin audio?). Continuando sin spectral.")

    # Phase 2: Classify
    vtype = classify_video(video_id)
    print(f"\n  CLASIFICADO: {vtype}")

    checkpoint = load_checkpoint()
    for v in checkpoint['videos']:
        if v['video_id'] == video_id:
            v['video_type'] = vtype
    save_checkpoint(checkpoint)

    if vtype == 'MUSIC':
        print("  Pipeline MUSIC: spectral + comments (sin transcript analysis)")
        print("  Razon: transcripcion vacia/basura, video es musica pura")
        print(f"\n  NOTA: spectral report es el deliverable principal")
        print(f"  BPM puede tener half-time correction (x2 si <100 y onset>3/s)")
        print("\n[4/5] COMMENTS analisis de audiencia...")
        do_comments(url, quiet=quiet)
    else:
        print("\n[4/5] CROSS-ANALYSIS...")
        cross_result = do_crossanalyze(video_id)
        if not cross_result:
            print("  Cross-analysis falla (sin SRT o audio?).")
        do_analyze(video_id, quiet=quiet)

    print("\n[5/5] TEACH + INTEGRATE...")
    print("-" * 40)
    if vtype != 'MUSIC':
        do_teach(video_id, quiet=quiet)
    _auto_integrate(video_id)

    cat, tags = auto_categorize_file(video_id)
    print(f"\n  CATEGORIA: {cat} | Tags: {', '.join(tags)}")

    build_catalog()

    return 0


# ── INTEGRATE: Auto-update KRGN knowledge stores ───────────────────




def do_batch(urls, file_path=None, lang='es', auto_integrate=False):
    all_urls = list(urls)
    if file_path:
        fp = Path(file_path)
        if fp.exists():
            with open(fp, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        all_urls.append(line)
        else:
            print(f"  Archivo no encontrado: {file_path}")
            return 1

    if not all_urls:
        print("  No hay URLs para procesar. Pasar URLs o usar --file")
        return 1

    print(f"KVIS BATCH | {len(all_urls)} videos")
    print("=" * 60)

    results = {'ok': [], 'fail': []}
    for i, url in enumerate(all_urls, 1):
        vid = extract_video_id(url)
        print(f"\n[{i}/{len(all_urls)}] {vid}")
        try:
            rc = do_deep(url, lang=lang, auto_integrate=auto_integrate)
            if rc == 0:
                results['ok'].append(vid)
            else:
                results['fail'].append(vid)
        except Exception as e:
            print(f"  ERROR: {e}")
            results['fail'].append(vid)

    print("\n" + "=" * 60)
    print(f"BATCH COMPLETADO | OK: {len(results['ok'])} | FAIL: {len(results['fail'])}")
    if results['ok']:
        print(f"  OK: {', '.join(results['ok'])}")
    if results['fail']:
        print(f"  FAIL: {', '.join(results['fail'])}")
    return 0 if not results['fail'] else 1


# ── MAIN ────────────────────────────────────────────────────────────

