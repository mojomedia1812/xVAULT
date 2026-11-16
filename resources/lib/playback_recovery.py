"""Bounded VOD recovery policy; no source URLs or playback side effects."""
import math


class RecoveryState:
    MAX_ATTEMPTS = 2
    RESOLVE_TIMEOUT = 20

    def __init__(self):
        self.position = 0.0
        self.duration = 0.0
        self.attempts = 0

    def observe(self, position, duration):
        try:
            position, duration = float(position), float(duration)
            if math.isfinite(position) and position >= 0:
                self.position = position
            if math.isfinite(duration) and duration > 0:
                self.duration = duration
        except (ValueError, TypeError):
            pass

    def interrupted(self, reason, media_type, user_stopped=False):
        return (not user_stopped and media_type in ('movie', 'tvshow', 'episode')
                and reason in ('error', 'stall', 'eof')
                and self.duration > 0 and self.position >= 1
                and self.position < self.duration - max(10, self.duration * .02))

    def begin(self):
        if self.attempts >= self.MAX_ATTEMPTS:
            return False
        self.attempts += 1
        return True
