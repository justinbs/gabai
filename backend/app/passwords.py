"""Password rules and temporary passwords.

`problem()` is the only place the rules live. Registration, admin account
creation and password change all go through `UserManager.validate_password`,
which calls it, so the three can't drift apart.

Length over composition, plus a short list of passwords people actually pick.
No "one uppercase, one symbol" rules: they push people to `Password1!` and to
writing it on a sticky note by the shared laptop.
"""

import secrets

MIN_LENGTH = 8
MAX_LENGTH = 128

# Kept short and in the file on purpose. Covers the obvious picks, including the
# local ones, without shipping a wordlist.
COMMON = {
    "password",
    "password1",
    "password123",
    "passw0rd",
    "12345678",
    "123456789",
    "1234567890",
    "87654321",
    "qwertyui",
    "qwerty123",
    "qwertyuiop",
    "asdfghjkl",
    "abcd1234",
    "abc12345",
    "iloveyou",
    "iloveyou1",
    "letmein1",
    "welcome1",
    "mahalkita",
    "barangay",
    "barangay5",
    "barangayv",
    "singko123",
    "tanza123",
    "gabai123",
}

# No 0/O, 1/l/I. Someone reads this out loud at a shared desk.
TEMPORARY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
TEMPORARY_LENGTH = 10


def problem(password: str, email: str | None = None) -> str | None:
    """What's wrong with this password, or None if it's fine."""
    if len(password) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters"
    if len(password) > MAX_LENGTH:
        return f"Use {MAX_LENGTH} characters or fewer"

    lowered = password.lower()
    if lowered in COMMON or len(set(lowered)) == 1:
        return "That one's too common, pick another"

    if email:
        local = email.split("@")[0].lower()
        if lowered == email.lower() or (len(local) >= 3 and local in lowered):
            return "Don't put your email in your password"

    return None


def generate_temporary() -> str:
    return "".join(secrets.choice(TEMPORARY_ALPHABET) for _ in range(TEMPORARY_LENGTH))
