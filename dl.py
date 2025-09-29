import os
import yt_dlp
from log import get_logger

logger = get_logger(__name__)

def download_youtube_audio(youtube_url, output_path) -> tuple[str, str]:
    """Download audio from a YouTube URL and convert it to WAV format.
    Returns the title of the video and the path to the WAV file.
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        # 'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
        'outtmpl': os.path.join(output_path, '%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl: # type: ignore
        logger.info(f"Downloading audio from YouTube URL: {youtube_url}")
        
        info_dict = ydl.extract_info(youtube_url, download=True)
            
        video_title = info_dict.get("title", None)
        video_id = info_dict.get("id", None)
        if not video_title:
            raise ValueError("Could not retrieve video title.")
        wav_file_path = os.path.join(output_path, f"{video_id}.wav")
        logger.info(f"Downloaded video title: {video_title} at {wav_file_path}")
        return video_title, wav_file_path

if __name__ == "__main__":
    import sys
    # dl to current directory
    output_dir = "."
    if len(sys.argv) != 2:
        print("Usage: python dl.py <youtube_url>")
        sys.exit(1)
    youtube_url = sys.argv[1]
    wav_path = download_youtube_audio(youtube_url, output_dir)
    print(f"Downloaded and extracted audio to: {wav_path}")