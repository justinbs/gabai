"""Outgoing email, through Resend's HTTP API.

An HTTP call rather than SMTP: DigitalOcean blocks outbound mail ports on new
droplets, and one POST needs nothing installed. It's the standard library, so no
new dependency either.

Without RESEND_API_KEY nothing is sent. In development the email is written to
the log so the link can be clicked locally. Anywhere else only a warning is
logged, because a reset link sitting in a log is a working credential.
"""

import asyncio
import json
import logging
import time
import urllib.error
import urllib.request

from app.core.config import get_settings

settings = get_settings()
log = logging.getLogger(__name__)

# One email per address per kind in this window. Stops the forms being used to
# flood someone's inbox. Held in memory, which is enough for the single worker
# this runs on, and it resets on restart.
COOLDOWN_SECONDS = 120
_last_sent: dict[str, float] = {}
_in_flight: set[asyncio.Task] = set()

PLACE = "GABAI, Barangay V (Singko), Amaya, Tanza, Cavite"


def allowed(kind: str, address: str) -> bool:
    now = time.monotonic()
    for key, at in list(_last_sent.items()):
        if now - at > COOLDOWN_SECONDS:
            del _last_sent[key]
    key = f"{kind}:{address.lower()}"
    if key in _last_sent:
        return False
    _last_sent[key] = now
    return True


def sender() -> str:
    """The From header Resend accepts, whatever shape MAIL_FROM arrives in.

    `GABAI <no-reply@gabai.help>` in .env reached the app once with its angle
    brackets gone, and Resend refused every email with a 422. So accept that, a
    bare address, or the proper form, and always send the proper form.
    """
    value = settings.mail_from.strip().strip('"').strip("'")
    if "<" in value and value.endswith(">"):
        return value
    parts = value.split()
    address = next((p for p in reversed(parts) if "@" in p), value)
    name = " ".join(p for p in parts if p != address) or "GABAI"
    return f"{name} <{address}>"


def link(path: str, token: str) -> str:
    # After the #, so the token never reaches Caddy's access log.
    return f"{settings.public_url.rstrip('/')}/{path}#token={token}"


def verify_email(name: str, url: str) -> tuple[str, str]:
    return (
        "Confirm your email for GABAI",
        f"Hi {name},\n\n"
        "Open this link to confirm your email · Buksan ang link para makumpirma ang email ninyo\n"
        f"{url}\n\n"
        "It works for 24 hours · Gagana ito sa loob ng 24 oras\n\n"
        "If you didn't sign up for GABAI, you can ignore this · "
        "Kung hindi kayo nag-sign up, balewalain lang ito\n\n"
        f"{PLACE}\n",
    )


def reset_email(name: str, url: str) -> tuple[str, str]:
    return (
        "Reset your GABAI password",
        f"Hi {name},\n\n"
        "Open this link to set a new password · Buksan ang link para magtakda ng bagong password\n"
        f"{url}\n\n"
        "It works for 1 hour, and only once · Gagana ito sa loob ng 1 oras, isang beses lang\n\n"
        "If you didn't ask for this, ignore it and your password stays the same · "
        "Kung hindi kayo ang humiling nito, balewalain lang, hindi magbabago ang password ninyo\n\n"
        f"{PLACE}\n",
    )


def _send(to: str, subject: str, text: str) -> None:
    if not settings.resend_api_key:
        if settings.environment == "development":
            log.warning("No RESEND_API_KEY, not sent. Development copy to %s:\n%s\n\n%s", to, subject, text)
        else:
            log.warning("No RESEND_API_KEY, an email was not sent")
        return

    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(
            {"from": sender(), "to": [to], "subject": subject, "text": text}
        ).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            # Resend's API sits behind Cloudflare, which blocks Python's
            # default User-Agent as a bot (error 1010) before Resend sees it.
            "User-Agent": "gabai/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        # Resend says why in the body, e.g. the domain isn't verified yet.
        # No address in the log, personal data doesn't belong there.
        reason = exc.read().decode(errors="replace")[:300]
        log.error("Resend refused an email: %s %s", exc.code, reason)
    except (urllib.error.URLError, TimeoutError) as exc:
        log.error("Sending an email failed: %s", exc)


def send_later(to: str, subject: str, text: str) -> None:
    # Off the request path. The response shouldn't wait on the mail provider,
    # or reveal through its timing whether an address has an account.
    task = asyncio.get_running_loop().create_task(asyncio.to_thread(_send, to, subject, text))
    _in_flight.add(task)
    task.add_done_callback(_in_flight.discard)
