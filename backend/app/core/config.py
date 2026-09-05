"""
Core configuration and environment settings for TarkaRaksha.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


class Settings:
    """
    Application runtime configuration loaded from environment.
    Strictly forbids printing or leaking secret keys.
    """
    def __init__(self):
        self.groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")
        self.groq_model: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        self.groq_timeout_seconds: float = float(os.getenv("GROQ_TIMEOUT_SECONDS", "30.0"))
        self.groq_max_retries: int = int(os.getenv("GROQ_MAX_RETRIES", "2"))

        # Payment integration config (T09+)
        self.razorpay_key_id: Optional[str] = os.getenv("RAZORPAY_KEY_ID")
        self.razorpay_key_secret: Optional[str] = os.getenv("RAZORPAY_KEY_SECRET")

    @property
    def has_groq_credentials(self) -> bool:
        return bool(self.groq_api_key and self.groq_api_key.strip())

    def __repr__(self) -> str:
        # Prevent accidental secret leakage
        return (
            f"Settings(groq_model='{self.groq_model}', "
            f"has_groq_credentials={self.has_groq_credentials}, "
            f"groq_timeout={self.groq_timeout_seconds}s, "
            f"groq_max_retries={self.groq_max_retries})"
        )


settings = Settings()
