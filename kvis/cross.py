import re
import json
from datetime import datetime

from .constants import ANALYSIS_DIR, TRANSCRIPTS_DIR
from .utils import (
    find_audio, find_subs, load_spectral_cache, fix_encoding,
    load_checkpoint, save_checkpoint,
)


def do_crossanalyze(video_id):
    import librosa
    import numpy as np

    audio_path = find_audio(video_id)
    if not audio_path:
        print(f"No audio para {video_id}. Descarga primero con: python scripts/kvis.py audio URL")
        return None

    subs, subs_source = find_subs(video_id)
    if not subs:
        print(f"No hay subtitulos para {video_id}. Ejecuta extract primero.")
        return None

    print(f"  Subtitulos: {len(subs)} segmentos | Fuente: {subs_source}")

    cached = load_spectral_cache(video_id)
    if cached:
        print(f"  Usando cache espectral (salto calculo librosa)")
        sr = cached['sr']
        dur = cached['dur']
        hop = cached.get('hop', 512)
        rms_db = cached['rms_db']
        cent = cached['cent']
        bw = cached['bw']
        flat = cached['flat']
        rolloff = cached['rolloff']
        contrast = cached['contrast']
        onset_times = cached['onset_times']
    else:
        print(f"  Sin cache, calculando features desde audio...")
        y, sr = librosa.load(str(audio_path), sr=None)
        dur = len(y) / sr
        hop = 512
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
        rms_db = librosa.amplitude_to_db(rms, ref=np.max)
        cent = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]
        bw = librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=hop)[0]
        flat = librosa.feature.spectral_flatness(y=y, hop_length=hop)[0]
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85, hop_length=hop)[0]
        contrast = librosa.feature.spectral_contrast(y=y, sr=sr, hop_length=hop)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
        onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop)
        del y

    print(f"  Audio: {dur:.1f}s")

    def spectral_at(t_start, t_end):
        f_start = max(0, int(t_start * sr / hop))
        f_end = min(len(rms_db), int(t_end * sr / hop))
        if f_end <= f_start:
            f_end = f_start + 1
        return {
            'rms': round(float(np.mean(rms_db[f_start:f_end])), 1),
            'centroid': round(float(np.mean(cent[f_start:f_end])), 0),
            'bandwidth': round(float(np.mean(bw[f_start:f_end])), 0),
            'flatness': round(float(np.mean(flat[f_start:f_end])), 5),
            'rolloff': round(float(np.mean(rolloff[f_start:f_end])), 0),
            'contrast': round(float(np.mean(contrast[:, f_start:f_end])), 1),
            'onsets': int(np.sum((onset_times >= t_start) & (onset_times <= t_end))),
        }

    cross = []
    for s in subs:
        sp = spectral_at(s['start'], s['end'])
        cross.append({**s, **sp})

    sub_times = [(s['start'], s['end']) for s in subs]
    gaps = []
    prev_end = 0
    for st, en in sorted(sub_times):
        if st - prev_end > 2.0:
            sp = spectral_at(prev_end, st)
            gaps.append({'start': round(prev_end,2), 'end': round(st,2), 'dur': round(st - prev_end,1), **sp})
        prev_end = max(prev_end, en)
    if dur - prev_end > 2.0:
        sp = spectral_at(prev_end, dur)
        gaps.append({'start': round(prev_end,2), 'end': round(dur,2), 'dur': round(dur - prev_end,1), **sp})

    r = []
    r.append(f"# KVIS Cross-Analysis: {video_id}")
    r.append(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M')} | **Duracion:** {dur:.1f}s | **Subtitulos:** {len(subs)}")
    r.append("")

    r.append("## Secciones SIN voz (musica/SFX puros)")
    if gaps:
        r.append("| Tiempo | Duracion | RMS | Brillo | Flatness | Onsets | Interpretacion |")
        r.append("|---|---|---|---|---|---|---|")
        for g in gaps:
            interp = []
            if g['centroid'] > 4000: interp.append('synths agudos')
            elif g['centroid'] > 2500: interp.append('synths medios')
            elif g['centroid'] > 1000: interp.append('cuerpo mid-range')
            else: interp.append('grave/sub')
            if g['onsets'] > g['dur'] * 4: interp.append('percusion densa')
            elif g['onsets'] > g['dur'] * 2: interp.append('beat presente')
            if g['rms'] > -12: interp.append('LOUD')
            elif g['rms'] > -16: interp.append('moderado')
            else: interp.append('quiet')
            if g['flatness'] > 0.05: interp.append('textura/ruido')
            elif g['flatness'] < 0.005: interp.append('tonal puro')
            r.append(f"| {g['start']:.0f}s-{g['end']:.0f}s | {g['dur']:.1f}s | {g['rms']} | {g['centroid']:.0f}Hz | {g['flatness']:.4f} | {g['onsets']} | {', '.join(interp)} |")
    else:
        r.append("No se detectaron gaps musicales significativos")
    r.append("")

    r.append("## Timeline Completo: Subtitulos + Spectral")
    r.append("| Tiempo | Texto (resumen) | RMS | Brillo | Flatness | Onsets | Lectura |")
    r.append("|---|---|---|---|---|---|---|")

    for c in cross:
        text = c['text'][:80] + ('...' if len(c['text']) > 80 else '')
        lectura = []
        if c['rms'] > -12: lectura.append('LOUD')
        elif c['rms'] < -20: lectura.append('quiet')
        if c['centroid'] > 4000: lectura.append('agudo')
        elif c['centroid'] < 1500: lectura.append('grave')
        if c['flatness'] > 0.02: lectura.append('textura')
        if c['onsets'] > 5: lectura.append(f'{c["onsets"]} hits')
        r.append(f"| {c['start']:.0f}s-{c['end']:.0f}s | {fix_encoding(text)} | {c['rms']} | {c['centroid']:.0f}Hz | {c['flatness']:.4f} | {c['onsets']} | {' / '.join(lectura) or '-'} |")
    r.append("")

    r.append("## Momentos Clave (cruce voz+espectro)")
    r.append("")

    loud_speech = sorted([c for c in cross if c['rms'] > -16], key=lambda x: -x['rms'])
    if loud_speech:
        r.append("### Voz + Alta Energia")
        for c in loud_speech[:8]:
            r.append(f"- **{c['start']:.0f}s**: RMS={c['rms']} | Brillo={c['centroid']:.0f}Hz | \"{fix_encoding(c['text'][:100])}\"")
        r.append("")

    bright_moments = sorted(cross, key=lambda x: -x['centroid'])
    if bright_moments:
        r.append("### Momentos Mas Brillantes")
        for c in bright_moments[:5]:
            r.append(f"- **{c['start']:.0f}s**: Centroid={c['centroid']:.0f}Hz | \"{fix_encoding(c['text'][:100])}\"")
        r.append("")

    dense_moments = sorted(cross, key=lambda x: -x['onsets'])
    if dense_moments:
        r.append("### Momentos Mas Percusivos")
        for c in dense_moments[:5]:
            r.append(f"- **{c['start']:.0f}s**: {c['onsets']} onsets | \"{fix_encoding(c['text'][:100])}\"")
        r.append("")

    topics = {
        'intro': ['intro', 'introduccion', 'comienzo'],
        'synth': ['sintetizador', 'synth', 'prophet', 'secuencia'],
        'voz': ['voz', 'vocal', 'grito', 'scream', 'efecto'],
        'bajo': ['bajo', 'bass', 'grave'],
        'guitarra': ['guitarra', 'guitar'],
        'beat': ['beat', 'ritmo', 'percusion', 'kick', 'bombo'],
        'mezcla': ['mezcla', 'mix', 'master', 'produccion'],
    }

    r.append("## Temas de Produccion vs Spectral Data")
    r.append("| Tema | Segmentos | RMS promedio | Brillo promedio | Flatness promedio |")
    r.append("|---|---|---|---|---|")
    for topic, keywords in topics.items():
        matches = [c for c in cross if any(kw in c['text'].lower() for kw in keywords)]
        if matches:
            avg_rms = round(np.mean([m['rms'] for m in matches]), 1)
            avg_cent = round(np.mean([m['centroid'] for m in matches]), 0)
            avg_flat = round(np.mean([m['flatness'] for m in matches]), 5)
            r.append(f"| {topic} | {len(matches)} | {avg_rms} dB | {avg_cent} Hz | {avg_flat} |")
    r.append("")

    r.append("## Evolucion Narrativa-Espectral")
    n_parts = 5
    part_dur = dur / n_parts
    for i in range(n_parts):
        t0, t1 = i * part_dur, (i+1) * part_dur
        part_subs = [c for c in cross if c['start'] >= t0 and c['start'] < t1]
        part_gaps = [g for g in gaps if g['start'] >= t0 and g['end'] <= t1]
        part_text = ' '.join([s['text'][:60] for s in part_subs[:3]]) + ('...' if len(part_subs) > 3 else '')
        avg_rms = round(np.mean([s['rms'] for s in part_subs]), 1) if part_subs else 'N/A'
        avg_cent = round(np.mean([s['centroid'] for s in part_subs]), 0) if part_subs else 'N/A'
        music_pct = round(sum(g['dur'] for g in part_gaps) / part_dur * 100, 0) if part_gaps else 0
        r.append(f"### Parte {i+1} ({t0:.0f}s-{t1:.0f}s): RMS={avg_rms}dB | Brillo={avg_cent}Hz | Musica={music_pct}%")
        r.append(f"> {fix_encoding(part_text)}")
        r.append("")

    out = ANALYSIS_DIR / f"{video_id}_cross_analysis.md"
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(r))

    checkpoint = load_checkpoint()
    for v in checkpoint['videos']:
        if v['video_id'] == video_id:
            v['cross_analyzed'] = True
            v['sub_segments'] = len(subs)
            v['music_gaps'] = len(gaps)
    save_checkpoint(checkpoint)

    print(f"  OK: {out}")
    return out
