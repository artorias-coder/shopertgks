import hmac
import hashlib
import urllib.parse
from app.config import settings


def validate_init_data(init_data: str) -> bool:
    """Validate Telegram Mini App initData using HMAC-SHA256."""
    if not init_data or not settings.BOT_TOKEN:
        return False

    try:
        parsed = urllib.parse.parse_qsl(init_data)
    except Exception:
        return False

    data_check = {}
    received_hash = ""
    for key, value in parsed:
        if key == "hash":
            received_hash = value
        else:
            data_check[key] = value

    if not received_hash:
        return False

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_check.items()))
    secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_hash, received_hash)
