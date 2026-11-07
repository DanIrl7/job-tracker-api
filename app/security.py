import datetime as dt
import hashlib
import hmac
import os

import jwt

PBKDF2_ITERATIONS = 310_000
TOKEN_ALGORITHM = "HS256"
TOKEN_LIFETIME = dt.timedelta(hours=24)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _scheme, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_token(user_id: int, secret: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + TOKEN_LIFETIME}
    return jwt.encode(payload, secret, algorithm=TOKEN_ALGORITHM)


def decode_token(token: str, secret: str) -> int | None:
    try:
        data = jwt.decode(token, secret, algorithms=[TOKEN_ALGORITHM])
        return int(data["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
