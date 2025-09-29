import threading
import time
import logging
import sys
import select
import tty
import termios
from pathlib import Path
from typing import Optional
from collections import deque

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.align import Align
from rich.columns import Columns

from song import Song
from mixer import TrackMixer, PlaybackStatus
from log import get_logger

logger = get_logger(__name__)

class LogCapture(logging.Handler):
    """Custom logging handler to capture logs for display"""
    def __init__(self, max_logs=10):
        super().__init__()
        self.logs = deque(maxlen=max_logs)
        
    def emit(self, record):
        log_entry = self.format(record)
        self.logs.append(log_entry)

class MixerApp:
    def __init__(self):
        self.console = Console()
        self.mixer: Optional[TrackMixer] = None
        self.current_song: Optional[Song] = None
        self.running = True
        self.layout = Layout()
        
        # Setup log capture
        self.log_capture = LogCapture(max_logs=8)
        self.log_capture.setFormatter(logging.Formatter('%(name)s - %(message)s'))
        logging.getLogger().addHandler(self.log_capture)
        
        self.setup_layout()
        
    def setup_layout(self):
        """Setup the Rich layout structure"""
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        self.layout["main"].split_row(
            Layout(name="controls", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        self.layout["right"].split_column(
            Layout(name="status", ratio=1),
            Layout(name="logs", ratio=1)
        )

    def create_header(self) -> Panel:
        """Create the header panel"""
        title = Text("🎵 IRMIX - Interactive Music Mixer", style="bold magenta")
        return Panel(Align.center(title), style="bright_blue")

    def create_footer(self) -> Panel:
        """Create the footer with controls"""
        controls = Text()
        controls.append("Press: ", style="bold")
        controls.append("P", style="green")
        controls.append("=Play/Pause  ", style="white")
        controls.append("S", style="red")
        controls.append("=Stop  ", style="white")
        controls.append("R", style="yellow")
        controls.append("=Rewind  ", style="white")
        controls.append("1-4", style="cyan")
        controls.append("=Toggle Stems  ", style="white")
        controls.append("Q", style="magenta")
        controls.append("=Quit", style="white")
        
        return Panel(Align.center(controls), style="dim")

    def create_mixer_controls(self) -> Panel:
        """Create the mixer controls panel"""
        if not self.mixer:
            return Panel("No song loaded", title="Mixer Controls", style="dim")
            
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("Stem", style="cyan", width=10)
        table.add_column("Status", width=12)
        table.add_column("Key", width=5)
        
        stems = ["vocals", "drums", "bass", "other"]
        keys = ["1", "2", "3", "4"]
        
        for i, (stem, key) in enumerate(zip(stems, keys)):
            if stem in self.mixer.tracks:
                is_muted = self.mixer.is_muted(stem)
                status = "🔇 MUTED" if is_muted else "🔊 ACTIVE"
                status_style = "red" if is_muted else "green"
                
                table.add_row(
                    stem.capitalize(),
                    Text(status, style=status_style),
                    f"[{key}]"
                )
        
        return Panel(table, title="🎛️ Mixer Controls", style="bright_blue")

    def create_status_panel(self) -> Panel:
        """Create the status panel"""
        if not self.mixer or not self.current_song:
            return Panel("No song loaded", title="Status", style="dim")
            
        # Playback status
        status_color = {
            PlaybackStatus.PLAYING: "green",
            PlaybackStatus.PAUSED: "yellow", 
            PlaybackStatus.STOPPED: "red"
        }
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="bold", width=8)
        table.add_column("Value", width=15)
        
        table.add_row("Song:", self.current_song.title[:15] + "..." if len(self.current_song.title) > 15 else self.current_song.title)
        table.add_row("Status:", Text(
            self.mixer.status.value.upper(), 
            style=status_color.get(self.mixer.status, "white")
        ))
        table.add_row("Tracks:", str(len(self.mixer.tracks)))
        
        return Panel(table, title="📊 Status", style="bright_green")

    def create_logs_panel(self) -> Panel:
        """Create the logs panel"""
        if not self.log_capture.logs:
            return Panel("No logs yet", title="📝 Logs", style="dim")
        
        log_text = Text()
        for log_entry in list(self.log_capture.logs)[-6:]:  # Show last 6 logs
            # Truncate long log entries
            if len(log_entry) > 40:
                log_entry = log_entry[:37] + "..."
            log_text.append(log_entry + "\n", style="dim")
        
        return Panel(log_text, title="📝 Logs", style="yellow")

    def update_display(self):
        """Update the display layout"""
        self.layout["header"].update(self.create_header())
        self.layout["controls"].update(self.create_mixer_controls())
        self.layout["status"].update(self.create_status_panel())
        self.layout["logs"].update(self.create_logs_panel())
        self.layout["footer"].update(self.create_footer())

    def list_songs(self) -> list[Path]:
        """List available songs in the songs directory"""
        songs_dir = Path("songs")
        if not songs_dir.exists():
            songs_dir.mkdir(parents=True)
            return []
        return [p for p in songs_dir.iterdir() if p.is_dir()]

    def select_existing_song(self) -> Optional[Song]:
        """Let user select from existing songs"""
        songs = self.list_songs()
        
        if not songs:
            self.console.print("❌ No existing songs found in the songs directory.", style="red")
            return None
            
        self.console.print("\n📁 Available Songs:", style="bold cyan")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Index", style="cyan", width=8)
        table.add_column("Song Title", style="green")
        
        for i, song_path in enumerate(songs, 1):
            table.add_row(str(i), song_path.name)
            
        self.console.print(table)
        
        while True:
            try:
                choice = Prompt.ask(
                    "\nSelect a song by number (or 'q' to go back)",
                    default="q"
                )
                
                if choice.lower() == 'q':
                    return None
                    
                index = int(choice) - 1
                if 0 <= index < len(songs):
                    selected_path = songs[index]
                    self.console.print(f"✅ Loading song: {selected_path.name}", style="green")
                    return Song.from_path(selected_path)
                else:
                    self.console.print("❌ Invalid selection. Please try again.", style="red")
                    
            except ValueError:
                self.console.print("❌ Please enter a valid number.", style="red")

    def load_song_from_youtube(self) -> Optional[Song]:
        """Load a new song from YouTube URL"""
        self.console.print("\n🎬 Load Song from YouTube", style="bold cyan")
        
        url = Prompt.ask("Enter YouTube URL (or 'q' to go back)")
        
        if url.lower() == 'q':
            return None
            
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Downloading and processing...", total=None)
                
                # Download and create song
                song = Song.from_yt_url(url)
                progress.update(task, description="Extracting stems...")
                song.extract_stems()
                
            self.console.print(f"✅ Successfully loaded: {song.title}", style="green")
            return song
            
        except Exception as e:
            self.console.print(f"❌ Error loading song: {str(e)}", style="red")
            logger.error(f"Error loading song from YouTube: {e}")
            return None

    def song_selection_menu(self) -> Optional[Song]:
        """Show song selection menu"""
        while True:
            self.console.clear()
            self.console.print(Panel.fit("🎵 Song Selection", style="bold magenta"))
            
            choices = [
                "1. Select existing song",
                "2. Load new song from YouTube",
                "3. Back to main menu"
            ]
            
            for choice in choices:
                self.console.print(f"  {choice}")
                
            selection = Prompt.ask("\nChoose an option", choices=["1", "2", "3"], default="3")
            
            if selection == "1":
                song = self.select_existing_song()
                if song:
                    return song
            elif selection == "2":
                song = self.load_song_from_youtube()
                if song:
                    return song
            elif selection == "3":
                return None

    def handle_mixer_command(self, command: str):
        """Handle mixer commands"""
        if not self.mixer:
            return
            
        command = command.lower().strip()
        
        if command in ['p', 'play', 'pause']:
            if self.mixer.status == PlaybackStatus.PLAYING:
                self.mixer.pause()
            elif self.mixer.status == PlaybackStatus.PAUSED:
                self.mixer.resume()
            else:
                self.mixer.play()
        elif command in ['s', 'stop']:
            self.mixer.stop()
        elif command in ['r', 'rewind']:
            self.mixer.rewind_all()
        elif command in ['1', '2', '3', '4']:
            stems = ["vocals", "drums", "bass", "other"]
            stem_index = int(command) - 1
            if stem_index < len(stems):
                stem = stems[stem_index]
                if stem in self.mixer.tracks:
                    self.mixer.toggle_mute(stem)
        elif command in ['q', 'quit']:
            self.running = False

    def handle_keyboard_input(self):
        """Handle direct keyboard input in a separate thread"""
        # Save terminal settings
        old_settings = termios.tcgetattr(sys.stdin)
        
        try:
            tty.setraw(sys.stdin.fileno())
            
            while self.running:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1).lower()
                    
                    if not self.mixer:
                        continue
                        
                    if key == 'p':
                        if self.mixer.status == PlaybackStatus.PLAYING:
                            self.mixer.pause()
                        elif self.mixer.status == PlaybackStatus.PAUSED:
                            self.mixer.resume()
                        else:
                            self.mixer.play()
                    elif key == 's':
                        self.mixer.stop()
                    elif key == 'r':
                        self.mixer.rewind_all()
                    elif key in '1234':
                        stems = ["vocals", "drums", "bass", "other"]
                        stem_index = int(key) - 1
                        if stem_index < len(stems):
                            stem = stems[stem_index]
                            if stem in self.mixer.tracks:
                                self.mixer.toggle_mute(stem)
                    elif key == 'q':
                        self.running = False
                        break
                        
        except Exception:
            # Fallback if keyboard handling fails
            pass
        finally:
            # Restore terminal settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    def run_mixer(self):
        """Run the interactive mixer"""
        if not self.mixer or not self.current_song:
            self.console.print("❌ No song loaded!", style="red")
            return
            
        self.console.clear()
        self.running = True
        
        # Start playback
        self.mixer.play()
        
        # Start keyboard input handler in separate thread
        input_thread = threading.Thread(target=self.handle_keyboard_input, daemon=True)
        input_thread.start()
        
        try:
            with Live(self.layout, console=self.console, refresh_per_second=4) as live:
                while self.running:
                    self.update_display()
                    time.sleep(0.25)
                    
        except KeyboardInterrupt:
            self.running = False
            
        finally:
            if self.mixer:
                self.mixer.stop()

    def main_menu(self):
        """Show the main menu"""
        while True:
            self.console.clear()
            
            # Title
            title = Panel.fit("🎵 IRMIX - Interactive Music Mixer", style="bold magenta")
            self.console.print(title)
            self.console.print()
            
            # Current song status
            if self.current_song:
                status = f"✅ Current song: {self.current_song.title}"
                self.console.print(Panel(status, style="green"))
            else:
                self.console.print(Panel("❌ No song loaded", style="red"))
            
            self.console.print()
            
            # Menu options
            options = [
                "1. Select/Load Song",
                "2. Start Mixer" + (" (song loaded)" if self.current_song else " (no song)"),
                "3. Quit"
            ]
            
            for option in options:
                style = "green" if "song loaded" in option else "white"
                if "no song" in option:
                    style = "dim"
                self.console.print(f"  {option}", style=style)
            
            choice = Prompt.ask("\nChoose an option", choices=["1", "2", "3"], default="3")
            
            if choice == "1":
                song = self.song_selection_menu()
                if song:
                    self.current_song = song
                    self.mixer = TrackMixer.from_song(song)
                    self.console.print(f"✅ Song loaded: {song.title}", style="green")
                    time.sleep(1)
                    
            elif choice == "2":
                if self.current_song and self.mixer:
                    self.run_mixer()
                else:
                    self.console.print("❌ Please load a song first!", style="red")
                    time.sleep(2)
                    
            elif choice == "3":
                if Confirm.ask("Are you sure you want to quit?"):
                    break

    def run(self):
        """Run the application"""
        try:
            self.console.print("🎵 Welcome to IRMIX!", style="bold magenta")
            self.main_menu()
        except KeyboardInterrupt:
            pass
        finally:
            if self.mixer:
                self.mixer.stop()
            # Remove log handler
            logging.getLogger().removeHandler(self.log_capture)
            self.console.print("\n👋 Thanks for using IRMIX!", style="bold cyan")


def main():
    """Main entry point"""
    app = MixerApp()
    app.run()


if __name__ == "__main__":
    main()
