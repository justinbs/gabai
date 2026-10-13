"""Column types shared by the models."""

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core import crypto
from app.core.markers import PLAIN_MARKERS


class EncryptedText(TypeDecorator):
    """Text stored encrypted, read back as plain text.

    The rest of the code, the classifier included, only ever sees plain text.
    Retention markers are stored as they are so the database's protections can
    recognise them. Everything else is encrypted, even text that already looks
    encrypted, so a resident can't plant a value that fails to decrypt.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or value in PLAIN_MARKERS:
            return value
        return crypto.encrypt_text(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return crypto.decrypt_text(value)
