"""Provider media restrictions shared by collection, cache and playback."""


def allowed(provider, mediatype=None, season=None, episode=None):
    if provider != 'movie2k2':
        return True
    if str(mediatype or '').lower() in ('tv', 'tvshow', 'season', 'episode'):
        return False
    # Season zero is also used by films; an episode number identifies specials.
    # Reject malformed non-empty coordinates rather than searching a film title.
    return all(value in (None, '', 0, '0', '0.0') for value in (season, episode))
