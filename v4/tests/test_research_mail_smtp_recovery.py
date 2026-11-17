"""No-network regression tests for Gmail SMTP partial failure handling."""
import ssl
import smtplib
import unittest

from email.message import EmailMessage
from v4.research_mail import _send_review_smtp


def message():
    msg = EmailMessage()
    msg["From"] = "sender@gmail.com"
    msg["To"] = "recipient@gmail.com"
    msg["Subject"] = "V4 test fixture, never sent"
    msg.set_content("static fixture")
    return msg


class FakeSMTP:
    def __init__(self, events, *, fail_at=None):
        self.events = events
        self.fail_at = fail_at

    def __enter__(self):
        self.events.append("open")
        if self.fail_at == "open":
            raise ssl.SSLEOFError(8, "TLS EOF before SMTP")
        return self

    def login(self, sender, password):
        self.events.append("login")
        if self.fail_at == "login":
            raise ssl.SSLEOFError(8, "TLS EOF before DATA")

    def send_message(self, msg):
        self.events.append("send")
        if self.fail_at == "data":
            raise ssl.SSLEOFError(8, "ambiguous SMTP DATA")
        if self.fail_at == "refused":
            return {"recipient@gmail.com": (550, "denied")}
        return {}

    def __exit__(self, *_):
        self.events.append("quit")
        if self.fail_at == "quit":
            raise ssl.SSLEOFError(8, "TLS EOF after DATA")


class SMTPRecoveryTests(unittest.TestCase):
    def test_eof_during_quit_is_accepted_not_resubmitted(self):
        calls = []
        def factory(*args, **kwargs):
            return FakeSMTP(calls, fail_at="quit")
        _send_review_smtp(message(), "sender@gmail.com", "secret",
                          smtp_factory=factory)
        self.assertEqual(calls.count("send"), 1)

    def test_pre_data_login_failure_can_reconnect_once(self):
        calls = []
        attempts = [0]
        def factory(*args, **kwargs):
            attempts[0] += 1
            return FakeSMTP(calls,
                            fail_at="login" if attempts[0] == 1 else None)
        _send_review_smtp(message(), "sender@gmail.com", "secret",
                          smtp_factory=factory)
        self.assertEqual(attempts[0], 2)
        self.assertEqual(calls.count("send"), 1)

    def test_data_eof_never_resends_ambiguous_mail(self):
        calls = []
        attempts = [0]
        def factory(*args, **kwargs):
            attempts[0] += 1
            return FakeSMTP(calls, fail_at="data")
        with self.assertRaises(ssl.SSLEOFError):
            _send_review_smtp(message(), "sender@gmail.com", "secret",
                              smtp_factory=factory)
        self.assertEqual(attempts[0], 1)
        self.assertEqual(calls.count("send"), 1)

    def test_recipients_refused_does_not_write_a_success(self):
        calls = []
        with self.assertRaisesRegex(RuntimeError,
                                    "REVIEW_GMAIL_RECIPIENT_REFUSED"):
            _send_review_smtp(message(), "sender@gmail.com", "secret",
                              smtp_factory=lambda *a,**k:
                              FakeSMTP(calls, fail_at="refused"))
        self.assertEqual(calls.count("send"), 1)

    def test_second_pre_data_failure_is_not_silenced(self):
        attempts = [0]
        def factory(*args, **kwargs):
            attempts[0] += 1
            return FakeSMTP([], fail_at="open")
        with self.assertRaises(ssl.SSLEOFError):
            _send_review_smtp(message(), "sender@gmail.com", "secret",
                              smtp_factory=factory)
        self.assertEqual(attempts[0], 2)


if __name__ == "__main__":
    unittest.main()
