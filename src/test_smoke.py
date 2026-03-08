from ticket_alarm.models import ShowEvent


def test_fingerprint_changes_with_open_time():
    a = ShowEvent("x", "title", "http://x", None)
    b = ShowEvent("x", "title", "http://x", None)
    assert a.fingerprint == b.fingerprint

