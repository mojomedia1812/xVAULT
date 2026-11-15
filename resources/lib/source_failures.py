"""Classify resolver failures without persisting URLs, tokens or error text."""
import re
import threading


HEALTH_LOCK = threading.RLock()


class SourceFailure(Exception):
    def __init__(self, reason, ttl):
        super(SourceFailure, self).__init__(reason)
        self.reason = reason
        self.ttl = ttl


def classify(error):
    if isinstance(error, SourceFailure):
        return error
    text = str(error).lower()
    if re.search(r'\b(?:video|file) (?:was |has been )?(?:deleted|removed)\b|\b(?:video|file) (?:has been )?not found\b', text):
        return SourceFailure('deleted', 24 * 60 * 60)
    status = getattr(error, 'code', None)
    if status in (404, 410) or re.search(r'http error (?:404|410)\b', text):
        return SourceFailure('not_found', 30 * 60)
    if 'certificate_verify_failed' in text or 'certificate verify failed' in text:
        return SourceFailure('tls', 5 * 60)
    if status in (401, 403, 429) or re.search(r'http error (?:401|403|429)\b', text):
        return SourceFailure('access', 5 * 60)
    if (isinstance(status, int) and status >= 500) or re.search(r'http error 5\d\d\b', text):
        return SourceFailure('server', 5 * 60)
    if any(value in text for value in ('timed out', 'timeout', 'getaddrinfo failed',
                                       'name or service not known', 'temporary failure in name resolution',
                                       'connection reset', 'connection refused')):
        return SourceFailure('network', 5 * 60)
    return None
