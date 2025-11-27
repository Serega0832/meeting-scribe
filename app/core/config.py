import os
from pathlib import Path

# Настройки путей
BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
DATABASE_URL = "sqlite:///database.db"

# Настройки внешнего API
EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL", "http://localhost:8000")
SERVICE_NAME = os.getenv("SERVICE_NAME", "meeting_scribe_public")

# Создаем папку загрузок
UPLOAD_DIR.mkdir(exist_ok=True)