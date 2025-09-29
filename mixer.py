from enum import Enum
from pathlib import Path
import pygame
import os
from log import get_logger

from song import Song, ORIGINAL

logger = get_logger(__name__)

class PlaybackStatus(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"

class Track:
    def __init__(self, name: str, sound: pygame.mixer.Sound, channel: pygame.mixer.Channel):
        self.name = name
        self.sound = sound
        self.channel = channel

class TrackMixer:
    def __init__(self, frequency=44100, channels=2, buffer=512):
        pygame.mixer.init(frequency=frequency, channels=channels, buffer=buffer)
        self.tracks: dict[str, Track] = {}   # name -> Track
        self.volumes: dict[str, float] = {}  # name -> volume (0.0 to 1.0)
        self.status = PlaybackStatus.STOPPED

    def add_track(self, path, name=None):
        """
        Add an audio track.
        - path: path to audio file
        - name: optional name (defaults to filename)
        """
        if name is None:
            name = os.path.basename(path)

        sound = pygame.mixer.Sound(path)
        channel = pygame.mixer.Channel(len(self.tracks))  # unique channel per track
        self.tracks[name] = Track(name, sound, channel)
        self.volumes[name] = 1.0  # default volume
        logger.info(f"Added track: {name}")

    def play(self):
        """Play all tracks from their current state (if stopped, start)."""
        # only play 'original' if it exists, others are muted but still play in sync
        if self.status != PlaybackStatus.PLAYING:
            for name, track in self.tracks.items():
                volume = 1.0 if name == ORIGINAL else 0.0
                track.channel.set_volume(volume)
                if not track.channel.get_busy():
                    track.channel.play(track.sound, loops=0)
            self.status = PlaybackStatus.PLAYING
            logger.info("Playback started")

    def pause(self):
        """Pause all tracks."""
        for track in self.tracks.values():
            track.channel.pause()
        self.status = PlaybackStatus.PAUSED
        logger.info("Playback paused")
    
    def resume(self):
        """Resume all paused tracks."""
        for track in self.tracks.values():
            track.channel.unpause()
        self.status = PlaybackStatus.PLAYING
        logger.info("Playback resumed")

    def stop(self):
        """Stop (pause) all tracks."""
        for track in self.tracks.values():
            track.channel.stop()
        self.status = PlaybackStatus.STOPPED
        logger.info("Playback stopped")
    
    def is_muted(self, name):
        # since the original track contains all stems, a track is muted if both it and the original are muted
        assert name in self.tracks, f"Track not found: {name}"
        assert ORIGINAL in self.tracks, "Original track not found"
        track_muted = self.tracks[name].channel.get_volume() == 0.0
        original_muted = self.tracks[ORIGINAL].channel.get_volume() == 0.0
        return track_muted and original_muted
    
    def mute_stem(self, name):
        if self.is_muted(name):
            logger.warning(f"Track {name} is already muted")
            self.log_volumes()
            return
        logger.info(f"Muting stem: {name}")
        if not self.is_muted(ORIGINAL):
            # if original is unmuted, mute original and unmute all others
            for n in self.tracks:
                self._set_muted(n, n == ORIGINAL)
        # then mute the requested stem
        self._set_muted(name, True)
        self.log_volumes()
    
    def unmute_stem(self, name):
        if not self.is_muted(name):
            logger.warning(f"Track {name} is already unmuted")
            self.log_volumes()
            return
        logger.info(f"Unmuting stem: {name}")
        # first unmute the requested stem
        self._set_muted(name, False)
        if all(not self.is_muted(n) for n in self.tracks if n != ORIGINAL):
            # if all stems are now unmuted, unmute original and mute all others
            for n in self.tracks:
                self._set_muted(n, n != ORIGINAL)
        self.log_volumes()
    
    def toggle_mute(self, name):
        if self.is_muted(name):
            self.unmute_stem(name)
        else:
            self.mute_stem(name)

    def _set_muted(self, name, muted):
        assert name in self.tracks, f"Track not found: {name}"
        if muted:
            self.tracks[name].channel.set_volume(0.0)
        else:
            self.tracks[name].channel.set_volume(self.volumes[name])
    
    def set_volume(self, name: str, volume: float):
        """Set volume for a track (0.0 to 1.0)"""
        assert name in self.tracks, f"Track not found: {name}"
        volume = max(0.0, min(1.0, volume))  # clamp between 0 and 1
        self.volumes[name] = volume
        
        # Only apply volume if track is not muted
        if not self.is_muted(name):
            self.tracks[name].channel.set_volume(volume)
        
        logger.info(f"Set volume for {name}: {volume}")
    
    def get_volume(self, name: str) -> float:
        """Get volume for a track"""
        assert name in self.tracks, f"Track not found: {name}"
        return self.volumes[name]
    
    def adjust_volume(self, name: str, delta: float):
        """Adjust volume by delta amount"""
        current = self.get_volume(name)
        new_volume = current + delta
        self.set_volume(name, new_volume)

    def log_volumes(self):
        for name, track in self.tracks.items():
            volume = track.channel.get_volume()
            logger.info(f"Volume for {name}: {volume}")

    def rewind_all(self):
        """Rewind all tracks (restart everything in sync)."""
        for track in self.tracks.values():
            track.channel.stop()
        for track in self.tracks.values():
            track.channel.play(track.sound, loops=0)
        logger.info("Rewound all tracks")

    def list_tracks(self):
        """List all loaded tracks."""
        return list(self.tracks.keys())
    
    @staticmethod
    def from_song(song: Song):
        mixer = TrackMixer()
        for part, path in song.files.items():
            if path is not None:
                mixer.add_track(path, name=part)
        return mixer

if __name__ == "__main__":
    song = Song.from_path(Path("songs") / "VULFPECK_1612")
    mixer = TrackMixer.from_song(song)
    logger.info(f"Loaded tracks: {mixer.list_tracks()}")
    mixer.play()
    while True:
        toggle = input("Enter stem to toggle mute (or 'q' to quit): ")
        if toggle == 'q':
            break
        if toggle in mixer.list_tracks():
            mixer.toggle_mute(toggle)
    mixer.stop()

