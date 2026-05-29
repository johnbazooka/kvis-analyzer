import re
import json
from datetime import datetime

from .constants import ANALYSIS_DIR
from .utils import (
    find_audio, load_spectral_cache, load_checkpoint, save_checkpoint,
    fix_encoding, freq_to_note, save_spectral_cache,
)


def do_spectral(video_id):
    import librosa
    import numpy as np

    audio = find_audio(video_id)
    if not audio:
        print(f"No audio para {video_id}. Descarga primero con: python scripts/kvis.py audio URL")
        return None

    print(f"  Cargando audio...")
    y, sr = librosa.load(str(audio), sr=None)
    dur = len(y) / sr
    N = 10
    seg = dur / N
    print(f"  Duracion: {dur:.1f}s | SR: {sr}Hz")

    MAX_CHUNK = 600
    if dur > MAX_CHUNK:
        chunk_dur = MAX_CHUNK
        n_chunks = int(np.ceil(dur / chunk_dur))
        print(f"  Audio largo, procesando en {n_chunks} chunks de {chunk_dur}s...")
        tempos, onset_counts = [], []
        all_onset_times = []
        for ci in range(n_chunks):
            print(f"    Chunk {ci+1}/{n_chunks}...", end="\r")
            s = int(ci * chunk_dur * sr)
            e = min(int((ci + 1) * chunk_dur * sr), len(y))
            yc = y[s:e]
            if len(yc) < sr * 5:
                continue
            try:
                t_c, _ = librosa.beat.beat_track(y=yc, sr=sr)
                if hasattr(t_c, '__len__'):
                    t_c = float(t_c[0])
                tempos.append(float(t_c))
            except Exception:
                pass
            oe = librosa.onset.onset_strength(y=yc, sr=sr)
            of = librosa.onset.onset_detect(onset_envelope=oe, sr=sr)
            ot = librosa.frames_to_time(of, sr=sr) + ci * chunk_dur
            all_onset_times.extend(ot.tolist())
            onset_counts.append(len(of))
            del yc, oe
        print(f"    Chunks completados                ")
        tempo = float(np.median(tempos)) if tempos else 0.0
        onset_frames_idx = np.arange(len(all_onset_times))
        onset_times = np.array(sorted(all_onset_times))
        del y

        print(f"  Calculando features espectrales (primeros {MAX_CHUNK}s)...")
        y_full, _ = librosa.load(str(audio), sr=sr, duration=MAX_CHUNK)
        rms = librosa.feature.rms(y=y_full, frame_length=2048, hop_length=512)[0]
        rms_db = librosa.amplitude_to_db(rms, ref=np.max)
        cent = librosa.feature.spectral_centroid(y=y_full, sr=sr)[0]
        bw = librosa.feature.spectral_bandwidth(y=y_full, sr=sr)[0]
        flat = librosa.feature.spectral_flatness(y=y_full)[0]
        rolloff = librosa.feature.spectral_rolloff(y=y_full, sr=sr, roll_percent=0.85)[0]
        contrast = librosa.feature.spectral_contrast(y=y_full, sr=sr)
        chroma = librosa.feature.chroma_cqt(y=y_full, sr=sr)
        S = np.abs(librosa.stft(y_full, n_fft=2048))
        del y_full
    else:
        print(f"  Calculando features espectrales...")
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        if hasattr(tempo, '__len__'):
            tempo = float(tempo[0])
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        rms_db = librosa.amplitude_to_db(rms, ref=np.max)
        cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        bw = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
        flat = librosa.feature.spectral_flatness(y=y)[0]
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]
        contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onset_frames_idx = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
        onset_times = librosa.frames_to_time(onset_frames_idx, sr=sr)
        S = np.abs(librosa.stft(y, n_fft=2048))
        del y

    seg_size = len(rms) // N
    segments = []
    for i in range(N):
        s, e = i * seg_size, min((i+1) * seg_size, len(rms))
        seg_rms = np.mean(rms_db[s:e])
        seg_cent = np.mean(cent[s:e])
        seg_flat = np.mean(flat[s:e])
        segments.append({
            't0': round(i * seg, 1), 't1': round((i+1) * seg, 1),
            'rms': round(float(seg_rms), 1),
            'centroid': round(float(seg_cent), 0),
            'flatness': round(float(seg_flat), 5),
            'brightness': 'BRIGHT' if seg_cent > 3000 else 'MID' if seg_cent > 1500 else 'DARK',
            'type': 'MUSIC/SFX' if seg_flat < 0.02 and seg_rms > -18 else
                    'VOICE' if seg_flat < 0.03 and -18 <= seg_rms <= -12 else
                    'QUIET/SILENCE' if seg_rms < -20 else 'MIXED',
        })

    onset_density = len(onset_times) / dur

    halftime_fix = False
    if tempo < 100 and onset_density > 3.0:
        tempo = tempo * 2
        halftime_fix = True

    chroma_avg = np.mean(chroma, axis=1)
    notes = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    ranked = sorted(zip(notes, chroma_avg), key=lambda x: -x[1])
    key_guess = ranked[0][0]

    drops = []
    for i in range(1, len(segments)):
        diff = segments[i]['rms'] - segments[i-1]['rms']
        if diff < -4:
            drops.append(f"{segments[i]['t0']}s (cae {abs(diff):.1f}dB)")
        elif diff > 4:
            drops.append(f"{segments[i]['t0']}s (sube +{diff:.1f}dB)")

    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    bands = {'Sub <60Hz': 60, 'Low 60-250Hz': 250, 'MidLow 250-500Hz': 500,
             'Mid 500-2kHz': 2000, 'MidHigh 2-4kHz': 4000, 'High 4-8kHz': 8000, 'Air >8kHz': sr/2}
    band_energy = {}
    prev = 0
    for name, f_hi in bands.items():
        mask = (freqs >= prev) & (freqs < f_hi)
        if mask.any():
            band_energy[name] = round(float(np.mean(S[mask])), 2)
        prev = f_hi

    r = []
    r.append(f"# KVIS Spectral Report: {video_id}")

    save_spectral_cache(video_id, {
        'sr': sr, 'dur': dur, 'hop': 512,
        'rms_db': rms_db, 'cent': cent, 'bw': bw, 'flat': flat,
        'rolloff': rolloff, 'contrast': contrast, 'chroma': chroma,
        'onset_times': onset_times, 'S': S,
        'tempo': tempo, 'onset_density': onset_density,
    })
    r.append(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M')} | **Duracion:** {dur:.1f}s | **SR:** {sr}Hz")
    r.append("")

    r.append("## Overview")
    r.append(f"| Metrica | Valor | Nota |")
    r.append(f"|---|---|---|")
    r.append(f"| Tempo | {tempo:.1f} BPM | {'Eurobeat range' if 150 < tempo < 175 else 'Out of eurobeat range'}{' (half-time corrected)' if halftime_fix else ''} |")
    r.append(f"| Brillo (centroid) | {np.mean(cent):.0f} Hz ({freq_to_note(np.mean(cent))}) | {'Brillante' if np.mean(cent) > 3000 else 'Medio' if np.mean(cent) > 1500 else 'Oscuro'} |")
    r.append(f"| Ancho espectral | {np.mean(bw):.0f} Hz | {'Muy ancho (complejo)' if np.mean(bw) > 3000 else 'Normal'} |")
    r.append(f"| Flatness | {np.mean(flat):.4f} | {'Tonal/musical' if np.mean(flat) < 0.02 else 'Texturizado/ruido' if np.mean(flat) < 0.05 else 'Ruidoso'} |")
    r.append(f"| Rolloff 85% | {np.mean(rolloff):.0f} Hz ({freq_to_note(np.mean(rolloff))}) | Limite superior de contenido |")
    r.append(f"| Contraste spectral | {np.mean(contrast):.1f} | {'Alta dinamica frecuencial' if np.mean(contrast) > 20 else 'Medio'} |")
    r.append(f"| Onset density | {onset_density:.1f}/s ({len(onset_times)} total) | {'Denso/percusivo' if onset_density > 3 else 'Moderado' if onset_density > 1.5 else 'Sparse'} |")
    r.append(f"| Tonalidad estimada | {key_guess} (cromatico: {', '.join(n for n,v in ranked[:4])}) | Eurobeat tipicamente cromatico |")
    r.append("")

    r.append("## Distribucion de Energia por Banda")
    r.append("| Banda | Energia | Barra |")
    r.append("|---|---|---|")
    max_e = max(band_energy.values()) if band_energy else 1
    for name, val in band_energy.items():
        bar = '#' * int(val / max_e * 30)
        r.append(f"| {name} | {val:.2f} | {bar} |")
    r.append("")

    r.append("## Timeline por Segmentos")
    r.append("| Tiempo | RMS dB | Brillo | Flatness | Tipo | Contenido probable |")
    r.append("|---|---|---|---|---|---|")
    for s in segments:
        r.append(f"| {s['t0']:.0f}s-{s['t1']:.0f}s | {s['rms']} | {s['brightness']} ({s['centroid']:.0f}Hz) | {s['flatness']:.4f} | {s['type']} | |")
    r.append("")

    if drops:
        r.append("## Transiciones Detectadas")
        for d in drops:
            r.append(f"- **{d}**")
        r.append("")

    r.append("## Onsets Principales (transientes)")
    prev_t = 0
    shown = 0
    for t in onset_times:
        if t - prev_t > 5.0 and shown < 30:
            r.append(f"- {t:.1f}s")
            prev_t = t
            shown += 1
    r.append("")

    r.append("## Interpretacion Musical")
    bright_segs = [s for s in segments if s['brightness'] == 'BRIGHT']
    dark_segs = [s for s in segments if s['brightness'] == 'DARK']
    music_segs = [s for s in segments if s['type'] in ('MUSIC/SFX', 'MIXED')]

    r.append(f"- Segmentos musicales: {len(music_segs)}/{N}")
    r.append(f"- Segmentos brillantes: {len(bright_segs)} | Oscuros: {len(dark_segs)}")
    if music_segs:
        avg_bright = np.mean([s['centroid'] for s in music_segs])
        r.append(f"- Brillo promedio en secciones musicales: {avg_bright:.0f} Hz")
        r.append(f"- Esto indica {'presencia fuerte de synths agudos y hi-hats' if avg_bright > 3500 else 'synths medios con presencia vocal' if avg_bright > 2000 else 'bajo/sub-grave dominante'}")

    if onset_density > 3:
        r.append(f"- Onset density {onset_density:.1f}/s = percusion densa, tipico de {'eurobeat/happy hardcore' if tempo > 150 else 'drum and bass' if tempo > 160 else 'EDM'}")
    elif onset_density > 1.5:
        r.append(f"- Onset density moderada ({onset_density:.1f}/s) = balance entre percusion y melodia")
    r.append("")

    out = ANALYSIS_DIR / f"{video_id}_spectral_report.md"
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(r))

    checkpoint = load_checkpoint()
    for v in checkpoint['videos']:
        if v['video_id'] == video_id:
            v['spectral'] = True
            v['tempo'] = round(float(tempo), 1)
            v['spectral_centroid'] = round(float(np.mean(cent)), 0)
    save_checkpoint(checkpoint)

    print(f"  OK: {out}")
    return out
