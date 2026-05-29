from .constants import TRANSCRIPTS_DIR, ANALYSIS_DIR, AUDIO_DIR, KEYFRAMES_DIR, CHECKPOINT_FILE
from .utils import load_checkpoint

def do_status(verbose=False):
    checkpoint = load_checkpoint()
    videos = checkpoint.get('videos', [])
    if not videos:
        print("KVIS STATUS | Sin videos procesados")
        return True

    print(f"KVIS v3.4 STATUS | {len(videos)} videos")
    print("-" * 70)
    for v in reversed(videos):
        status_flags = []
        if v.get('analyzed'):
            status_flags.append('analyzed')
        if v.get('audio_file'):
            status_flags.append('audio')
        if v.get('spectral'):
            status_flags.append('spectral')
        if v.get('cross_analyzed'):
            status_flags.append('cross')
        genres = v.get('genres', [])
        if genres:
            status_flags.append(f"generos: {','.join(genres)}")
        steps = v.get('steps_found', 0)
        if steps:
            status_flags.append(f"{steps} pasos")
        vtype = v.get('video_type', '')
        if vtype:
            status_flags.append(vtype)

        title = v.get('title', 'N/A')[:50]
        print(f"  {v['video_id']} | {title}")
        print(f"    {v.get('extracted_at', '?')[:10]} | {v.get('words', '?')} palabras | {' '.join(status_flags)}")
        if verbose:
            print(f"    Metodo: {v.get('method', '?')} | Archivo: {v.get('transcript_file', '?')}")
            if v.get('audio_file'):
                print(f"    Audio: {v['audio_file']}")
    print("-" * 70)
    return True

