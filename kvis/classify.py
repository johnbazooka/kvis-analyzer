import re

from .constants import TRANSCRIPTS_DIR, ANALYSIS_DIR
from .utils import load_checkpoint


def classify_video(video_id):
    words_per_sec = 0
    word_diversity = 0
    music_pct = 0
    duration = 0

    cp = load_checkpoint()
    entry = None
    for v in cp.get('videos', []):
        if v['video_id'] == video_id:
            entry = v
            break

    title = (entry.get('title', '') if entry else '').lower()
    channel = (entry.get('channel', '') if entry else '').lower()

    if entry:
        duration = entry.get('duration', 0)
        words = entry.get('words', 0)
        if duration > 0:
            words_per_sec = words / duration

    clean_path = TRANSCRIPTS_DIR / f"{video_id}_clean.txt"
    meaningful_words = 0
    if clean_path.exists():
        with open(clean_path, 'r', encoding='utf-8') as f:
            text = f.read()
        real_text = re.sub(r'\[.*?\]', '', text)
        real_text = re.sub(r'=+', '', real_text)
        real_text = re.sub(r'Titulo:.*?URL:.*?\n', '', real_text)
        word_list = real_text.lower().split()
        word_list = [w for w in word_list if len(w) > 2 and w not in ('the', 'and', 'for', 'this', 'that', 'with')]
        meaningful_words = len(word_list)
        word_diversity = len(set(word_list)) / max(len(word_list), 1)

    spectral_path = ANALYSIS_DIR / f"{video_id}_spectral_report.md"
    if spectral_path.exists():
        with open(spectral_path, 'r', encoding='utf-8') as f:
            sr_text = f.read()
        music_lines = [l for l in sr_text.split('\n') if l.startswith('|') and ('MUSIC/SFX' in l or 'MIXED' in l)]
        total_lines = [l for l in sr_text.split('\n') if l.startswith('|') and 'Hz)' in l and 'RMS' not in l and 'Tiempo' not in l and '---' not in l]
        if total_lines:
            music_pct = len(music_lines) / len(total_lines)
        dur_match = re.search(r'\*\*Duracion:\*\* (\d+\.?\d*)s', sr_text)
        if dur_match and duration == 0:
            duration = float(dur_match.group(1))
            if duration > 0:
                words = entry.get('words', 0) if entry else 0
                words_per_sec = words / duration

    if meaningful_words < 50 and music_pct > 0.5:
        return 'MUSIC'
    if meaningful_words < 50 and words_per_sec < 0.5 and word_diversity < 0.15:
        return 'MUSIC'
    if music_pct > 0.7 and words_per_sec < 0.8 and meaningful_words < 100:
        return 'MUSIC'

    tutorial_kw = ['tutorial', 'como hacer', 'how to make', 'how to', 'fl studio', 'ableton',
                   'produccion', 'producing', 'how i produced', 'how i created', 'studio secrets',
                   'guide', 'guia']
    if any(kw in title for kw in tutorial_kw):
        return 'TUTORIAL'

    doc_kw = ['history', 'documental', 'evolution', 'origen', 'cultura', 'cultural', 'story',
              'what is', 'history of']
    if any(kw in title for kw in doc_kw):
        return 'DOCUMENTARY'

    podcast_kw = ['podcast', 'episodio', 'entrevista', 'charla', 'conversación',
                  'invitado', 'desayun', 'talk show']
    podcast_channels = ['beno espinosa', 'profesor rayado', 'dímelo smooth', 'dimelo smooth',
                        'matías parkman', 'matias parkman']
    if any(kw in title for kw in podcast_kw) or any(ch in channel for ch in podcast_channels):
        return 'PODCAST'
    ep_match = re.search(r'\bep\.?\s*\d+', title)
    if ep_match and duration > 600:
        return 'PODCAST'

    if words_per_sec > 2.0 and duration > 300:
        return 'PODCAST'

    return 'TUTORIAL'
