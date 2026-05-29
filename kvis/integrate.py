import sys
import re
import json
import time
from datetime import datetime
from pathlib import Path

from .constants import DATA_DIR, ANALYSIS_DIR
from .utils import load_checkpoint, save_checkpoint

def _auto_integrate(video_id):
    cp = load_checkpoint()
    entry = None
    for v in cp.get('videos', []):
        if v['video_id'] == video_id:
            entry = v
            break
    if not entry:
        print(f"  No hay entry para {video_id}")
        return

    title = entry.get('title', 'N/A')
    vtype = entry.get('video_type', 'UNKNOWN')
    tempo = entry.get('tempo')
    genres = entry.get('genres', [])

    analysis_path = ANALYSIS_DIR / f"{video_id}_analysis.json"
    nutrients = []
    if analysis_path.exists():
        with open(analysis_path, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
        nutrients = analysis.get('nutrients', [])

    if not nutrients:
        print(f"  Sin nutrientes para integrar. Ejecuta analyze primero.")
        return

    today = datetime.now().strftime('%Y-%m-%d')
    updated = []

    # ── DECISION TRAIL: from SABIDURIA nutrients ──
    sabiduria = [n for n in nutrients if n['category'] == 'SABIDURIA' and n['relevance'] == 'ALTA']
    if sabiduria:
        # removed KRGN store
        if dt_file.exists():
            with open(dt_file, 'r', encoding='utf-8') as f:
                dt = json.load(f)
            dt_nums = []
            for t in dt.get('trails', []):
                m = re.match(r'DT_\d+_(\d+)', t.get('id', ''))
                if m:
                    dt_nums.append(int(m.group(1)))
            dt_num = max(dt_nums, default=0) + 1
            dt_id = f"DT_{today.replace('-','')}_{dt_num:03d}"
            wisdom_summaries = [f"- {n['nutrient']}" for n in sabiduria[:5]]
            new_dt = {
                "id": dt_id,
                "date": today,
                "type": "research",
                "title": f"KVIS: {title}",
                "description": f"Conocimiento extraido de KVIS {video_id}:\n" + "\n".join(wisdom_summaries),
                "sources": [f"KVIS {video_id}: {title}"],
                "status": "completed",
                "patterns_discovered": [n['nutrient'] for n in sabiduria],
                "files_affected": [],
                "reversible": False,
            }
            dt['trails'].append(new_dt)
            with open(dt_file, 'w', encoding='utf-8') as f:
                json.dump(dt, f, indent=2, ensure_ascii=False)
            print(f"  DT: {dt_id} — {len(sabiduria)} sabidurias → decision_trail.json")
            updated.append('decision_trail')

    # ── PATTERN LOG: from TECNICA ALTA + CREATIVO ALTA ──
    pattern_nutrients = [n for n in nutrients if n['category'] in ('TECNICA', 'CREATIVO') and n['relevance'] == 'ALTA']
    if pattern_nutrients:
        # removed KRGN store
        if pat_file.exists():
            with open(pat_file, 'r', encoding='utf-8') as f:
                pl = json.load(f)
            existing_names = {p.get('nombre', '').lower() for p in pl.get('patrones_activos', [])}
            existing_nums = []
            for p in pl.get('patrones_activos', []):
                m = re.match(r'PAT_(\d+)', p.get('id', ''))
                if m:
                    existing_nums.append(int(m.group(1)))
            pat_num = max(existing_nums, default=0) + 1
            added = 0
            for n in pattern_nutrients:
                nombre = re.sub(r':\s*\d+\s+menciones.*', '', n['nutrient']).strip()
                if nombre.lower() in existing_names:
                    for p in pl['patrones_activos']:
                        if p.get('nombre', '').lower() == nombre.lower():
                            p['ocurrencias'] = p.get('ocurrencias', 1) + 1
                            p['veces_confirmado'] = p.get('veces_confirmado', 1) + 1
                            p['ultima_vez'] = today
                            p['confianza'] = min(1.0, p.get('confianza', 0.7) + 0.05)
                            break
                    continue
                pat_id = f"PAT_{pat_num:03d}"
                pl['patrones_activos'].append({
                    "id": pat_id,
                    "nombre": nombre,
                    "descripcion": n['nutrient'],
                    "ocurrencias": 1,
                    "confianza": 0.7,
                    "veces_confirmado": 1,
                    "recomendacion": f"Extraido de KVIS: {title} ({video_id})",
                    "estado": "emergente",
                    "primera_vez": today,
                    "ultima_vez": today,
                })
                print(f"  PAT: {pat_id} '{nombre}' → pattern_log.json")
                pat_num += 1
                added += 1
            with open(pat_file, 'w', encoding='utf-8') as f:
                json.dump(pl, f, indent=2, ensure_ascii=False)
            if added:
                print(f"  + {len(pattern_nutrients) - added} patrones existentes actualizados")
            updated.append('pattern_log')

    # ── MEMORY BANK: from RELEVANCIA BZK + INDUSTRIA + REFERENCIAS ──
    memory_nutrients = [n for n in nutrients if n['category'] in ('RELEVANCIA BZK', 'INDUSTRIA', 'REFERENCIAS')]
    if memory_nutrients:

        if mb_file.exists():
            with open(mb_file, 'r', encoding='utf-8') as f:
                mb = json.load(f)
            for n in memory_nutrients:
                cat_map = {'RELEVANCIA BZK': 'musical', 'INDUSTRIA': 'negocio', 'REFERENCIAS': 'musical'}
                idea_id = str(int(time.time() * 1000))[-12:]
                mb['ideas'].append({
                    "id": idea_id,
                    "idea": f"[KVIS {video_id}] {n['nutrient']}",
                    "categoria": cat_map.get(n['category'], 'musical'),
                    "prioridad": "alta" if n['relevance'] == 'ALTA' else "media",
                    "contexto": "kvis_nutrient",
                    "tags": ["kvis", video_id, n['category'].lower().replace(' ', '_')],
                    "timestamp": datetime.now().isoformat(),
                })
            mb['stats']['total_ideas'] = len(mb['ideas'])
            mb['updated_at'] = datetime.now().isoformat()
            with open(mb_file, 'w', encoding='utf-8') as f:
                json.dump(mb, f, indent=2, ensure_ascii=False)
            print(f"  MEM: {len(memory_nutrients)} nutrientes → memory_bank.json")
            updated.append('memory_bank')

    # ── MUSIC PRODUCTION: add research entry ──
    genre_nutrients = [n for n in nutrients if n['category'] == 'GENERO']
    jb_nutrients = [n for n in nutrients if n['category'] == 'APLICACIÓN BZK']
    if genre_nutrients or jb_nutrients:
        # removed KRGN store
        if mp_file.exists():
            with open(mp_file, 'r', encoding='utf-8') as f:
                mp = json.load(f)
            genres_str = ', '.join(genres) if genres else 'varios'
            jb_str = '; '.join(n['nutrient'] for n in jb_nutrients) if jb_nutrients else ''
            new_proj = {
                "id": f"research_kvis_{video_id}_{int(time.time())}",
                "timestamp": datetime.now().isoformat(),
                "bpm": tempo,
                "duracion": "N/A",
                "estado": "investigacion",
                "genero": genres_str,
                "tags": ["kvis", "investigacion", video_id],
                "titulo": f"KVIS Research: {title}",
                "tonalidad": None,
                "created_at": datetime.now().isoformat(),
                "fuentes_investigacion": [f"KVIS {video_id}: {title}"],
                "aplicacion_jb": jb_str or "A evaluar",
            }
            mp['proyectos'].append(new_proj)
            mp['estadisticas']['total_proyectos'] = len(mp['proyectos'])
            with open(mp_file, 'w', encoding='utf-8') as f:
                json.dump(mp, f, indent=2, ensure_ascii=False)
            print(f"  PROJ: 'KVIS Research: {title}' → music_production.json")
            updated.append('music_production')

    if not updated:
        print("  Sin nutrientes de alta relevancia para integrar.")
    else:
        print(f"  Integrado en: {', '.join(updated)}")



def do_integrate(video_id, decision=None, patterns=None, project=None, project_genre=None):
    print(f"KVIS INTEGRATE | {video_id}")

    cp = load_checkpoint()
    vid_entry = None
    for v in cp['videos']:
        if v['video_id'] == video_id:
            vid_entry = v
            break
    if not vid_entry:
        print(f"  Video {video_id} no encontrado en checkpoint. Ejecuta extract primero.")
        return 1

    title = vid_entry.get('title', 'N/A')
    today = datetime.now().strftime('%Y-%m-%d')
    updated = []

    if decision:
        # removed KRGN store
        if dt_file.exists():
            with open(dt_file, 'r', encoding='utf-8') as f:
                dt = json.load(f)
            dt_nums = []
            for t in dt.get('trails', []):
                m = re.match(r'DT_\d+_(\d+)', t.get('id', ''))
                if m:
                    dt_nums.append(int(m.group(1)))
            dt_num = max(dt_nums, default=0) + 1
            dt_id = f"DT_{today.replace('-','')}_{dt_num:03d}"
            new_dt = {
                "id": dt_id,
                "date": today,
                "type": "research",
                "title": f"KVIS: {title}",
                "description": decision,
                "sources": [f"KVIS {video_id}: {title}"],
                "status": "completed",
                "patterns_discovered": patterns or [],
                "files_affected": [],
                "reversible": False,
            }
            dt['trails'].append(new_dt)
            with open(dt_file, 'w', encoding='utf-8') as f:
                json.dump(dt, f, indent=2, ensure_ascii=False)
            print(f"  DT: {dt_id} agregado a decision_trail.json")
            updated.append('decision_trail')

    if patterns:
        # removed KRGN store
        if pat_file.exists():
            with open(pat_file, 'r', encoding='utf-8') as f:
                pl = json.load(f)
            existing_ids = [p.get('id', '') for p in pl.get('patrones_activos', [])]
            existing_nums = []
            for pid in existing_ids:
                m = re.match(r'PAT_(\d+)', pid)
                if m:
                    existing_nums.append(int(m.group(1)))
            pat_num = max(existing_nums, default=0) + 1
            for p_str in patterns:
                parts = p_str.split('|', 1)
                nombre = parts[0].strip()
                desc = parts[1].strip() if len(parts) > 1 else nombre
                pat_id = f"PAT_{pat_num:03d}"
                new_pat = {
                    "id": pat_id,
                    "nombre": nombre,
                    "descripcion": desc,
                    "ocurrencias": 1,
                    "confianza": 0.7,
                    "veces_confirmado": 1,
                    "recomendacion": f"Extraido de KVIS: {title}",
                    "estado": "emergente",
                    "primera_vez": today,
                    "ultima_vez": today,
                }
                pl['patrones_activos'].append(new_pat)
                print(f"  PAT: {pat_id} '{nombre}' agregado a pattern_log.json")
                pat_num += 1
            with open(pat_file, 'w', encoding='utf-8') as f:
                json.dump(pl, f, indent=2, ensure_ascii=False)
            updated.append('pattern_log')

    if project:
        # removed KRGN store
        if mp_file.exists():
            with open(mp_file, 'r', encoding='utf-8') as f:
                mp = json.load(f)
            new_proj = {
                "id": f"proj_kvis_{video_id}_{int(time.time())}",
                "timestamp": datetime.now().isoformat(),
                "bpm": vid_entry.get('tempo'),
                "duracion": "N/A",
                "estado": "idea",
                "genero": project_genre or "KVIS Research",
                "tags": ["kvis", "investigacion", video_id],
                "titulo": project,
                "tonalidad": None,
                "created_at": datetime.now().isoformat(),
                "fuentes_investigacion": [f"KVIS {video_id}: {title}"],
            }
            mp['proyectos'].append(new_proj)
            mp['estadisticas']['total_proyectos'] = len(mp['proyectos'])
            with open(mp_file, 'w', encoding='utf-8') as f:
                json.dump(mp, f, indent=2, ensure_ascii=False)
            print(f"  PROJ: '{project}' agregado a music_production.json")
            updated.append('music_production')

    if not updated:
        print("  Nada que integrar. Usa --decision, --pattern, o --project.")

    print(f"  Integrado: {', '.join(updated) if updated else 'nada'}")
    return 0


# ── BATCH: Multiple URLs ──────────────────────────────────────────




def do_map(video_id, keywords=None, add_project=None, era='', priority='HIGH'):
    analysis_path = ANALYSIS_DIR / f"{video_id}_analysis.json"
    if not analysis_path.exists():
        print(f"  No hay analisis para {video_id}. Ejecuta analyze primero.")
        return

    with open(analysis_path, 'r', encoding='utf-8') as f:
        analysis = json.load(f)

    if mapper_path.exists():
        cmd = [sys.executable, str(mapper_path)]
        if add_project:
            cmd.extend(['--add-project', add_project, '--era', era, '--priority', priority])
        if keywords:
            cmd.extend(['--keywords'] + keywords)
        cmd.append(str(analysis_path))
        subprocess.run(cmd)
    else:
        print("  map_video_to_krgn.py no encontrado, mapeo manual requerido")
        print(f"  Generos detectados: {analysis.get('detected_genres', [])}")
        print(f"  Pasos: {analysis.get('steps_count', 0)}")

