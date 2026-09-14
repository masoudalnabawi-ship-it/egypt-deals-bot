import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_channel_id: str = os.getenv("TELEGRAM_CHANNEL_ID", "")
    admin_chat_id: int = int(os.getenv("ADMIN_CHAT_ID", "0") or "0")
    check_interval_minutes: int = int(os.getenv("CHECK_INTERVAL_MINUTES", "20"))
    min_discount_percent: float = float(os.getenv("MIN_DISCOUNT_PERCENT", "15"))
    min_saving_egp: float = float(os.getenv("MIN_SAVING_EGP", "100"))
    max_posts_per_cycle: int = int(os.getenv("MAX_POSTS_PER_CYCLE", "2"))
    max_verify_candidates: int = int(os.getenv("MAX_VERIFY_CANDIDATES", "10"))
    strict_verification: bool = env_bool("STRICT_VERIFICATION", True)
    min_match_confidence: float = float(os.getenv("MIN_MATCH_CONFIDENCE", "90"))
    min_market_advantage_percent: float = float(os.getenv("MIN_MARKET_ADVANTAGE_PERCENT", "0"))
    timeout: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))
    user_agent: str = os.getenv("USER_AGENT", "Mozilla/5.0")
    enabled_stores: tuple[str, ...] = tuple(
        x.strip().lower()
        for x in os.getenv("ENABLED_STORES", "jumia,2b").split(",")
        if x.strip()
    )

settings = Settings()
