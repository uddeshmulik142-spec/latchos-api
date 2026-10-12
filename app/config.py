import os


# --- Database ---
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

# --- Gemini AI ---
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

# --- CORS ---
ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
] or [
    "https://latchos.online",
    "https://www.latchos.online",
    "https://latchos-api.onrender.com",
    "http://localhost:3000",
]

# --- Auth ---
API_KEY: str = os.environ.get("API_KEY", "")

# --- Rate Limiting ---
RATE_LIMIT_PER_MINUTE: int = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30"))

# --- Gate Dispatch ---
DISPATCH_WEBHOOK_URL: str = os.environ.get("DISPATCH_WEBHOOK_URL", "")

# --- Mock Mode ---
MOCK_OCR: bool = os.environ.get("MOCK_OCR", "true").lower() == "true"

# --- File Upload ---
MAX_FILE_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB

SUPPORTED_MEDIA_TYPES: set[str] = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}
