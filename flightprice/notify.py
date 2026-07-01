"""Alert delivery: e-mail when SMTP is configured, else console."""

from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional


class Notifier:
    """Sends alert messages. Falls back to stdout when SMTP is unset."""

    def __init__(self) -> None:
        self.host = os.getenv("SMTP_HOST", "")
        self.port = int(os.getenv("SMTP_PORT", "587") or 587)
        self.user = os.getenv("SMTP_USER", "")
        self.password = os.getenv("SMTP_PASSWORD", "")
        self.sender = os.getenv("ALERT_FROM", "") or self.user
        self.recipient = os.getenv("ALERT_TO", "")

    @property
    def email_enabled(self) -> bool:
        return bool(self.host and self.sender and self.recipient)

    def send(self, subject: str, body: str) -> None:
        if not self.email_enabled:
            print(f"\n🔔 ALERT: {subject}\n{body}\n")
            return
        try:
            self._send_email(subject, body)
            print(f"📧 Alert e-mailed to {self.recipient}: {subject}")
        except Exception as exc:  # never let notification failure crash monitor
            print(f"⚠️  E-mail alert failed ({exc}); printing instead:")
            print(f"\n🔔 ALERT: {subject}\n{body}\n")

    def _send_email(self, subject: str, body: str) -> None:
        msg = MIMEText(body, _charset="utf-8")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = self.recipient
        with smtplib.SMTP(self.host, self.port, timeout=20) as server:
            server.starttls()
            if self.user and self.password:
                server.login(self.user, self.password)
            server.send_message(msg)
