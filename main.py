#!/usr/bin/env python3
"""
IRMix - YouTube Audio Stem Extractor and Live Mixer
A simple tool to extract stems from YouTube videos and mix them live.
"""

import argparse
import sys
import threading
import time
import select
import termios
import tty
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box

from song import Song
from mixer import TrackMixer
from log import get_logger

logger = get_logger(__name__)

class KeyboardInput:
    """Non-blocking keyboard input handler for macOS/Linux"""
    
    def __init__(self):
        self.old_settings = None
        
    def __enter__(self):
        self.old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
        return self
        
    def __exit__(self, type, value, traceback):
        if self.old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
    
    def get_char(self, timeout=0.1):
        """Get a single character with timeout"""
        if select.select([sys.stdin], [], [], timeout) == ([sys.stdin], [], []):
            return sys.stdin.read(1)
        return None

class LiveMixer:
    """Rich console live mixing interface"""
    
    def __init__(self, mixer: TrackMixer):
        self.mixer = mixer
        self.running = False
        self.tracks = [track for track in mixer.list_tracks() if track != 'original']
        self.console = Console()
        self.last_command = ""
        
    def create_interface(self):
        """Create the rich interface layout"""
        # Status panel
        status_color = "green" if self.mixer.status.value == 'playing' else "yellow" if self.mixer.status.value == 'paused' else "red"
        status_text = Text(f"Status: {self.mixer.status.value.upper()}", style=f"bold {status_color}")
        
        # Stems table
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold blue")
        table.add_column("Key", style="cyan", width=5)
        table.add_column("Stem", style="white", width=12)
        table.add_column("Status", width=10)
        
        for i, track in enumerate(self.tracks, 1):
            muted = self.mixer.is_muted(track)
            status_style = "red" if muted else "green"
            status_text_val = "MUTED" if muted else "PLAYING"
            table.add_row(
                str(i),
                track.capitalize(),
                Text(status_text_val, style=f"bold {status_style}")
            )
        
        # Controls panel
        controls = Text()
        controls.append("Controls: ", style="bold white")
        controls.append("SPACE", style="bold cyan")
        controls.append(" Play/Pause  ", style="white")
        controls.append("s", style="bold cyan")
        controls.append(" Stop  ", style="white")
        controls.append("r", style="bold cyan")
        controls.append(" Rewind  ", style="white")
        controls.append("q", style="bold cyan")
        controls.append(" Quit  ", style="white")
        controls.append("1-4", style="bold cyan")
        controls.append(" Toggle stems", style="white")
        
        # Create panels
        status_panel = Panel(status_text, title="Playback", border_style="blue")
        stems_panel = Panel(table, title="Stems", border_style="green")
        controls_panel = Panel(controls, title="Controls", border_style="yellow")
        
        # Feedback panel
        feedback_text = Text(self.last_command if self.last_command else " ", style="dim")
        feedback_panel = Panel(feedback_text, title="Last Action", border_style="dim", height=3)
        
        # Layout
        layout = Layout()
        layout.split_column(
            Layout(status_panel, size=3),
            Layout(stems_panel, size=len(self.tracks) + 4),
            Layout(controls_panel, size=3),
            Layout(feedback_panel, size=3)
        )
        
        return layout
        
    def run(self):
        """Run the rich console mixing interface"""
        self.running = True
        
        # Suppress mixer logs during interface
        import logging
        mixer_logger = logging.getLogger('mixer')
        original_level = mixer_logger.level
        mixer_logger.setLevel(logging.WARNING)
        
        try:
            self.console.clear()
            self.console.print(Panel.fit("🎵 IRMix Live Mixer", style="bold magenta"))
            self.console.print("Starting playback... Press keys for real-time control!", style="green")
            
            self.mixer.play()
            
            with KeyboardInput() as kb:
                with Live(self.create_interface(), console=self.console, refresh_per_second=10) as live:
                    while self.running:
                        try:
                            # Update the interface
                            live.update(self.create_interface())
                            
                            # Get keyboard input (non-blocking)
                            char = kb.get_char(timeout=0.1)
                            
                            if char:
                                if char.lower() == 'q':
                                    break
                                elif char == ' ':  # Space bar
                                    if self.mixer.status.value == 'playing':
                                        self.mixer.pause()
                                        self.last_command = "⏸️  Paused"
                                    else:
                                        if self.mixer.status.value == 'paused':
                                            self.mixer.resume()
                                        else:
                                            self.mixer.play()
                                        self.last_command = "▶️  Playing"
                                elif char.lower() == 's':
                                    self.mixer.stop()
                                    self.last_command = "⏹️  Stopped"
                                elif char.lower() == 'r':
                                    self.mixer.rewind_all()
                                    self.last_command = "⏪ Rewound"
                                elif char.isdigit():
                                    track_num = int(char)
                                    if 1 <= track_num <= len(self.tracks):
                                        track_name = self.tracks[track_num - 1]
                                        self.mixer.toggle_mute(track_name)
                                        muted = self.mixer.is_muted(track_name)
                                        status = "🔇 muted" if muted else "🔊 unmuted"
                                        self.last_command = f"{track_name.capitalize()} {status}"
                                    else:
                                        self.last_command = f"❌ Invalid track number. Use 1-{len(self.tracks)}"
                                elif char == '\x03':  # Ctrl+C
                                    break
                            
                            # Clear last command after a few seconds
                            if hasattr(self, '_last_command_time'):
                                if time.time() - self._last_command_time > 2:
                                    self.last_command = ""
                            
                            if self.last_command and not hasattr(self, '_last_command_time'):
                                self._last_command_time = time.time()
                            elif not self.last_command:
                                if hasattr(self, '_last_command_time'):
                                    delattr(self, '_last_command_time')
                            
                        except KeyboardInterrupt:
                            break
                        
        finally:
            # Restore logger level
            mixer_logger.setLevel(original_level)
            self.running = False
            self.mixer.stop()
            self.console.clear()
            self.console.print(Panel.fit("🎵 Mixer stopped. Goodbye!", style="bold red"))

def extract_and_mix(youtube_url: str, extract_stems: bool = True):
    """Extract stems from YouTube URL and start live mixer"""
    console = Console()
    
    try:
        console.print(f"[bold blue]Processing YouTube URL:[/] {youtube_url}")
        
        # Create song from YouTube URL
        with console.status("[bold green]Downloading audio...", spinner="dots"):
            song = Song.from_yt_url(youtube_url)
        console.print(f"[green]✓[/] Downloaded: [bold]{song.title}[/]")
        
        if extract_stems:
            with console.status("[bold yellow]Extracting stems (this may take a few minutes)...", spinner="bouncingBar"):
                song.extract_stems()
            console.print("[green]✓[/] Stems extracted successfully!")
        
        # Create mixer from song
        with console.status("[bold cyan]Loading mixer...", spinner="dots"):
            mixer = TrackMixer.from_song(song)
        
        if not mixer.list_tracks():
            console.print("[red]✗[/] Error: No tracks loaded!")
            return
            
        console.print(f"[green]✓[/] Loaded tracks: [bold]{', '.join(mixer.list_tracks())}[/]")
        
        # Start live mixer
        live_mixer = LiveMixer(mixer)
        live_mixer.run()
        
    except Exception as e:
        logger.error(f"Error processing YouTube URL: {e}")
        console.print(f"[red]✗ Error:[/] {e}")
        sys.exit(1)

def mix_existing(song_path: str):
    """Mix existing song directory"""
    console = Console()
    
    try:
        path = Path(song_path)
        if not path.exists():
            console.print(f"[red]✗ Error:[/] Path {song_path} does not exist")
            sys.exit(1)
            
        with console.status(f"[bold cyan]Loading song from: {song_path}...", spinner="dots"):
            song = Song.from_path(path)
        
        # Create mixer from song
        with console.status("[bold cyan]Initializing mixer...", spinner="dots"):
            mixer = TrackMixer.from_song(song)
        
        if not mixer.list_tracks():
            console.print("[red]✗[/] Error: No tracks loaded!")
            return
            
        console.print(f"[green]✓[/] Loaded tracks: [bold]{', '.join(mixer.list_tracks())}[/]")
        
        # Start live mixer
        live_mixer = LiveMixer(mixer)
        live_mixer.run()
        
    except Exception as e:
        logger.error(f"Error loading song: {e}")
        console.print(f"[red]✗ Error:[/] {e}")
        sys.exit(1)

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="IRMix - YouTube Audio Stem Extractor and Live Mixer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract stems from YouTube URL (download + separate stems)
  python main.py --extract https://www.youtube.com/watch?v=VIDEO_ID
  
  # Mix existing stem folder
  python main.py --mix songs/SONG_NAME
  
  # List available songs
  python main.py --list-songs
        """
    )
    
    parser.add_argument(
        "url_or_path",
        nargs="?",
        help="YouTube URL (for --extract) or path to existing song directory (for --mix)"
    )
    
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Download YouTube audio and extract stems"
    )
    
    parser.add_argument(
        "--mix",
        action="store_true",
        help="Mix existing stem folder"
    )
    
    parser.add_argument(
        "--list-songs",
        action="store_true",
        help="List available songs in the songs directory"
    )
    
    args = parser.parse_args()
    
    # List songs option
    if args.list_songs:
        console = Console()
        songs_dir = Path("songs")
        if songs_dir.exists():
            songs = [d.name for d in songs_dir.iterdir() if d.is_dir()]
            if songs:
                console.print("[bold blue]Available songs:[/]")
                for song in sorted(songs):
                    console.print(f"  [green]•[/] {song}")
            else:
                console.print("[yellow]No songs found in songs directory[/]")
        else:
            console.print("[red]Songs directory does not exist[/]")
        return
    
    # Require URL or path for other operations
    if not args.url_or_path:
        parser.print_help()
        sys.exit(1)
    
    # Check that exactly one operation is specified
    if args.extract and args.mix:
        print("Error: Cannot use both --extract and --mix at the same time")
        sys.exit(1)
    
    if not args.extract and not args.mix:
        print("Error: Must specify either --extract or --mix")
        parser.print_help()
        sys.exit(1)
    
    if args.extract:
        # Extract stems from YouTube URL
        extract_and_mix(args.url_or_path, extract_stems=True)
    elif args.mix:
        # Mix existing song directory
        mix_existing(args.url_or_path)

if __name__ == "__main__":
    main()