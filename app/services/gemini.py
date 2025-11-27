import httpx
from pathlib import Path
from app.core.config import EXTERNAL_API_URL, SERVICE_NAME


async def transcribe_audio(file_path: Path) -> str:
    """Отправляет файл на транскрибацию"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        with open(file_path, "rb") as f:
            files = {'file': (file_path.name, f, "audio/mpeg")}
            data = {'service_name': SERVICE_NAME, 'model': 'gemini-flash-lite-latest'}

            resp = await client.post(f"{EXTERNAL_API_URL}/transcribe", data=data, files=files)
            resp.raise_for_status()
            return resp.json().get("text", "")


async def generate_summary(text: str) -> str:
    """Генерирует саммари по тексту"""
    if not text:
        return "Не удалось получить текст для саммари."

    prompt = (
        f"Ты — опытный бизнес-ассистент. Ниже приведена расшифровка разговора. "
        f"Сделай краткое саммари (итоги): о чем договорились, какие задачи поставлены. "
        f"Текст:\n\n{text}"
    )

    payload = {
        "service_name": SERVICE_NAME,
        "model": "gemini-flash-lite-latest",
        "prompt": prompt
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{EXTERNAL_API_URL}/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("text", "")