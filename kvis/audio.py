from pathlib import Path

from .constants import AUDIO_DIR
from .utils import load_checkpoint, save_checkpoint, extract_video_id

def do_audio(url, output_dir=None):
    video_id = extract_video_id(url)
    url = url if 'http' in url else f"https://youtu.be/{video_id}"
    output = output_dir or str(AUDIO_DIR)

    print(f"KVIS AUDIO | {video_id}")
    try:
        import yt_dlp
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{output}/{video_id}.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'quiet': False,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        audio_file = f"{video_id}.mp3"
        audio_path = Path(output) / audio_file
        if audio_path.exists():
            checkpoint = load_checkpoint()
            for v in checkpoint['videos']:
                if v['video_id'] == video_id:
                    v['audio_file'] = audio_file
            if not any(v['video_id'] == video_id for v in checkpoint['videos']):
                checkpoint['videos'].append({
                    'video_id': video_id, 'audio_file': audio_file,
                    'title': 'N/A', 'channel': 'N/A', 'duration': 0,
                    'url': url, 'method': 'audio-only',
                    'extracted_at': datetime.now().isoformat(),
                    'chars': 0, 'words': 0, 'transcript_file': '', 'analyzed': False,
                })
            save_checkpoint(checkpoint)
            print(f"  OK: {audio_file}")
        else:
            print(f"  OK: Audio descargado en {output}")
    except ImportError:
        print("  yt-dlp no instalado. pip install yt-dlp")
    except Exception as e:
        print(f"  Error: {e}")

