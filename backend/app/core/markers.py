"""Text that retention writes in place of removed personal data.

Kept as plain text, never encrypted, so the database's own protections can
recognise it and anyone reading the table can see what retention did.
"""

REDACTED_TEXT = "[Removed after the retention period]"
REMOVED_NAME = "Removed account"

PLAIN_MARKERS = frozenset({REDACTED_TEXT, REMOVED_NAME})
