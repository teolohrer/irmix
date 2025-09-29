#!/usr/bin/env python3
"""
IRMix - YouTube Audio Stem Extractor and Live Mixer
A simple tool to extract stems from YouTube videos and mix them live.
"""

import argparse
import sys
import select
import termios
import tty
import time
import logging
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.align import Align
from rich.text import Text
from rich import box

from song import Song
from mixer import TrackMixer


class KeyboardInput:
    """Simplified keyboard input handler for Rich Live"""
    
    def __init__(self):
        self.old_settings = None
        
    def __enter__(self):
        if not sys.stdin.isatty():
            return self
        try:
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except (termios.error, AttributeError):
            self.old_settings = None
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.old_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            except termios.error:
                pass
    
    def get_char(self) -> Optional[str]:
        """Get a single character if available (non-blocking with faster polling)"""
        if not sys.stdin.isatty():
            return None
        try:
            if select.select([sys.stdin], [], [], 0.01) == ([sys.stdin], [], []):
                char = sys.stdin.read(1)
                if char.lower() in 'qsr ' or char.isdigit() or char == '\x03':
                    return char
        except (OSError, IOError):
            pass
        return None


class LiveMixer:
    """Rich-based live mixing interface with simple table display"""
    
    def __init__(self, mixer: TrackMixer):
        self.mixer = mixer
        self.running = False
        self.stems = [track for track in mixer.list_tracks() if track != 'original']
        self.console = Console()
        
    def create_display(self) -> Panel:
        """Create the main display table"""
        # Create stems table
        table = Table(box=box.ROUNDED, title="🎵 IRMix Live Stems", title_style="bold cyan")
        table.add_column("Key", justify="center", style="bright_blue", width=5)
        table.add_column("Stem", justify="left", style="white", min_width=15)
        table.add_column("Status", justify="center", style="bold", width=10)
        table.add_column("Volume", justify="center", style="dim", width=8)
        
        # Add stem rows
        for i, stem in enumerate(self.stems, 1):
            muted = self.mixer.is_muted(stem)
            volume = self.mixer.get_volume(stem)
            
            status = "[red]MUTED[/]" if muted else "[green]ACTIVE[/]"
            volume_text = f"{volume:.1f}" if not muted else "[dim]0.0[/]"
            
            table.add_row(
                f"[cyan]{i}[/]",
                stem.replace("_", " ").title(),
                status,
                volume_text
            )
        
        # Add controls info
        controls = Text.from_markup(
            "\n[bold]Controls:[/] "
            "[cyan]SPACE[/]=Play/Pause • "
            "[cyan]S[/]=Stop • "
            "[cyan]R[/]=Rewind • "
            "[cyan]1-9[/]=Toggle Stems • "
            "[cyan]Q[/]=Quit"
        )
        
        # Status info
        status = self.mixer.status.value.upper()
        status_color = "green" if status == "PLAYING" else "yellow" if status == "PAUSED" else "red"
        status_text = Text(f"Status: {status}", style=f"bold {status_color}")
        
        # Combine everything in a panel
        content = Align.center(table)
        panel = Panel(
            content,
            subtitle=controls,
            subtitle_align="center",
            title=status_text,
            title_align="center",
            border_style="bright_blue",
            padding=(1, 2)
        )
        
        return panel
        
    def handle_key(self, char: str) -> bool:
        """Handle keyboard input. Returns True if should quit."""
        if char.lower() == 'q' or char == '\x03':  # q or Ctrl+C
            return True
        elif char == ' ':  # Space bar
            if self.mixer.status.value == 'playing':
                self.mixer.pause()
            elif self.mixer.status.value == 'paused':
                self.mixer.resume()
            else:
                self.mixer.play()
        elif char.lower() == 's':
            self.mixer.stop()
        elif char.lower() == 'r':
            self.mixer.rewind_all()
        elif char.isdigit():
            stem_num = int(char)
            if 1 <= stem_num <= len(self.stems):
                stem_name = self.stems[stem_num - 1]
                self.mixer.toggle_mute(stem_name)
        
        return False
        
    def run(self):
        """Run the live mixer interface"""
        self.running = True
        
        # Disable logging during live interface to keep display clean
        logging.disable(logging.CRITICAL)
        
        try:
            self.console.print("\n[bold green]🎵 IRMix Live Mixer Starting...[/]\n")
            self.mixer.play()
            
            with Live(
                self.create_display(),
                refresh_per_second=10,
                auto_refresh=False,
                console=self.console,
                screen=True
            ) as live:
                with KeyboardInput() as kb:
                    while self.running:
                        try:
                            # Clear and update display
                            live.update(self.create_display(), refresh=True)
                            
                            # Check for keyboard input with faster polling
                            char = kb.get_char()
                            if char and self.handle_key(char):
                                break
                                    
                            time.sleep(0.01)  # Faster polling for more responsive input
                            
                        except KeyboardInterrupt:
                            break
                            
        finally:
            self.running = False
            self.mixer.stop()
            # Re-enable logging after live interface
            logging.disable(logging.NOTSET)
            self.console.clear()
            self.console.print("\n[bold blue]🎵 Mixer stopped. Goodbye![/]\n")


def extract_and_mix(youtube_url: str, extract_stems: bool = True):
    """Extract stems from YouTube URL and start live mixer"""
    console = Console()
    
    try:
        console.print(f"\n[bold blue]🔗 Processing YouTube URL:[/] {youtube_url}")
        
        # Download audio
        with console.status("[bold green]📥 Downloading audio...", spinner="dots"):
            song = Song.from_yt_url(youtube_url)
        console.print(f"[green]✓[/] Downloaded: [bold]{song.title}[/]")
        
        # Extract stems if requested
        if extract_stems:
            with console.status("[bold yellow]🎵 Extracting stems (this may take a few minutes)...", spinner="bouncingBar"):
                song.extract_stems()
            console.print("[green]✓[/] Stems extracted successfully!")
        
        # Initialize mixer
        with console.status("[bold cyan]🎛️ Loading mixer...", spinner="dots"):
            mixer = TrackMixer.from_song(song)
        
        if not mixer.list_tracks():
            console.print("[red]✗[/] Error: No tracks loaded!")
            return
            
        console.print(f"[green]✓[/] Loaded tracks: [bold]{', '.join(mixer.list_tracks())}[/]")
        
        # Start live mixer
        live_mixer = LiveMixer(mixer)
        live_mixer.run()
        
    except Exception as e:
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
            
        with console.status(f"[bold cyan]📁 Loading song from: {song_path}...", spinner="dots"):
            song = Song.from_path(path)
        
        # Initialize mixer
        with console.status("[bold cyan]🎛️ Initializing mixer...", spinner="dots"):
            mixer = TrackMixer.from_song(song)
        
        if not mixer.list_tracks():
            console.print("[red]✗[/] Error: No tracks loaded!")
            return
            
        console.print(f"[green]✓[/] Loaded tracks: [bold]{', '.join(mixer.list_tracks())}[/]")
        
        # Start live mixer
        live_mixer = LiveMixer(mixer)
        live_mixer.run()
        
    except Exception as e:
        console.print(f"[red]✗ Error:[/] {e}")
        sys.exit(1)


def list_available_songs():
    """List available songs in the songs directory"""
    console = Console()
    songs_dir = Path("songs")
    
    if not songs_dir.exists():
        console.print("[red]📁 Songs directory does not exist[/]")
        return
        
    songs = [d.name for d in songs_dir.iterdir() if d.is_dir()]
    if not songs:
        console.print("[yellow]📁 No songs found in songs directory[/]")
        return
        
    console.print("\n[bold blue]🎵 Available songs:[/]")
    for song in sorted(songs):
        console.print(f"  [green]•[/] {song}")
    console.print()


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="🎵 IRMix - YouTube Audio Stem Extractor and Live Mixer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract stems from YouTube URL and start mixer
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
        help="YouTube URL (for --extract) or path to song directory (for --mix)"
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
    
    # Handle list songs option
    if args.list_songs:
        list_available_songs()
        return
    
    # Require URL or path for other operations
    if not args.url_or_path:
        parser.print_help()
        sys.exit(1)
    
    # Check that exactly one operation is specified
    if args.extract and args.mix:
        print("❌ Error: Cannot use both --extract and --mix at the same time")
        sys.exit(1)
    
    if not args.extract and not args.mix:
        print("❌ Error: Must specify either --extract or --mix")
        parser.print_help()
        sys.exit(1)
    
    # Execute the requested operation
    if args.extract:
        extract_and_mix(args.url_or_path, extract_stems=True)
    elif args.mix:
        mix_existing(args.url_or_path)


if __name__ == "__main__":
    main()