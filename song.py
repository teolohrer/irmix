from pathlib import Path
from dl import download_youtube_audio
from tempfile import TemporaryDirectory
from extract import extract_stems
from log import get_logger

logger = get_logger(__name__)

ORIGINAL = 'original'

class Song:
    """
    a directory to song files
    """
    BASE_DIR = "songs"
    def __init__(self, title):
        self.title = title
        self.path = Path(self.BASE_DIR) / self.title
        self.files: dict[str, Path|None] = {
            ORIGINAL: None,
            'bass': None,
            'drums': None,
            'vocals': None,
            'other': None,
        }
        if not self.path.exists():
            logger.info(f"Creating song directory at {self.path}")
            self.path.mkdir(parents=True)

    def add_file(self, file_type: str, file_path: Path):
        if file_type not in self.files:
            raise ValueError(f"Invalid file type: {file_type}")
        # move and rename the file to the song directory
        ext = file_path.suffix
        new_file_path = self.path / f"{file_type}{ext}"
        logger.info(f"Moving {file_path} to {new_file_path}")
        file_path.rename(new_file_path)
        self.files[file_type] = new_file_path
    
    def extract_stems(self):
        if self.files[ORIGINAL] is None:
            raise ValueError("Original file not set.")
        with TemporaryDirectory() as tmpdir:
            logger.info(f"Extracting stems from {self.files[ORIGINAL]}")
            stems = extract_stems(self.files[ORIGINAL], Path(tmpdir)) # type: ignore
            logger.info(f"Extracted stems: {stems}")
            logger.info(f"Moving stems to {self.path}")
            for stem, path in stems.items():
                self.add_file(stem, path)
    
    @staticmethod
    def from_yt_url(youtube_url):
        with TemporaryDirectory() as tmpdir:
            logger.info(f"Downloading audio from YouTube URL: {youtube_url}")
            title, file_path = download_youtube_audio(youtube_url, tmpdir)
            # normalize title to be filesystem safe
            title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).rstrip()
            # remove multiple spaces
            title = ' '.join(title.split())
            # replace spaces with underscores
            title = title.replace(' ', '_')
            song = Song(title)
            song.add_file(ORIGINAL, Path(file_path))
        return song
    
    @staticmethod
    def from_path(path: Path):
        # from a directory with original.wav, bass.wav, drums.wav, vocals.wav, other.wav
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Path {path} does not exist or is not a directory.")
        title = path.name
        song = Song(title)
        for file_type in song.files.keys():
            file_path = path / f"{file_type}.wav"
            if file_path.exists():
                song.add_file(file_type, file_path)
        if song.files['original'] is None:
            raise ValueError(f"Original file not found in {path}.")
        return song


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        logger.error("Usage: python song.py <youtube_url>")
        sys.exit(1)
    youtube_url = sys.argv[1]
    song = Song.from_yt_url(youtube_url)
    song.extract_stems()
    for file_type, path in song.files.items():
        logger.info(f"{file_type}: {path}")