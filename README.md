# IRMix

YouTube audio stem extractor and live mixer. Download any YouTube video, separate it into individual stems (vocals, drums, bass, other), and mix them live with keyboard controls.

## Features

- **YouTube Integration**: Download audio directly from YouTube URLs
- **AI Stem Separation**: Extract vocals, drums, bass, and other instruments using Demucs
- **Live Mixing**: Real-time stem toggling with keyboard controls
- **Rich Interface**: Clean terminal UI with status indicators and controls

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- FFmpeg (for audio processing)

### macOS (Homebrew)
```bash
# Install uv and FFmpeg
brew install uv ffmpeg

# Install project dependencies
uv sync
```

### Ubuntu
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install FFmpeg
sudo apt update
sudo apt install ffmpeg

# Install project dependencies
uv sync
```

## Usage

### Download and mix YouTube video
```bash
uv run main.py https://www.youtube.com/watch?v=VIDEO_ID
```

### Extract stems only (no mixer)
```bash
uv run main.py https://www.youtube.com/watch?v=VIDEO_ID --extract
```

### Mix existing stems
```bash
uv run main.py songs/SONG_NAME
```

### List available songs
```bash
uv run main.py --list-songs
```

## Mixer Controls

| Key | Action |
|-----|--------|
| `SPACE` | Play/Pause |
| `S` | Stop |
| `R` | Rewind |
| `1-9` | Toggle stems |
| `Q` | Quit |

## How It Works

1. **Download**: YouTube audio is downloaded as WAV using yt-dlp
2. **Separation**: Demucs AI model separates audio into 4 stems
3. **Mixing**: pygame handles real-time audio playback and stem toggling

## Dependencies

- [demucs](https://github.com/adefossez/demucs) - AI audio source separation
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube audio downloading  
- [pygame](https://www.pygame.org/) - Audio playback and mixing
- [rich](https://github.com/Textualize/rich) - Terminal UI