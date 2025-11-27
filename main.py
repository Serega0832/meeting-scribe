import os
import shutil
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Field, Session, SQLModel, create_engine, select
import httpx
from dotenv import load_dotenv

# --- 1. КОНФИГУРАЦИЯ ---

# Загружаем переменные из файла .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Папки
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATABASE_URL = f"sqlite:///{BASE_DIR}/database.db"

# Настройки из .env (с дефолтными значениями для подстраховки)
EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL", "http://localhost:8000")
SERVICE_NAME = os.getenv("SERVICE_NAME", "meeting_scribe_public")
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 5))
CHUNK_DURATION = 600  # 10 минут

UPLOAD_DIR.mkdir(exist_ok=True)


# --- 2. БАЗА ДАННЫХ ---

class Meeting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    transcription: str = Field(default="")
    summary: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)


engine = create_engine(DATABASE_URL)
SQLModel.metadata.create_all(engine)

# --- 3. FASTAPI ---

app = FastAPI(title="Meeting Scribe")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# --- 4. БИЗНЕС-ЛОГИКА ---

def compress_audio(input_path: Path) -> Path:
    """Сжимает аудио в легкий mono mp3 32k для быстрой отправки."""
    output_path = input_path.with_suffix('.mp3')
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(input_path),
            "-vn", "-map", "a", "-ac", "1", "-ar", "16000", "-b:a", "32k",
            str(output_path)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path
    except Exception:
        # Если ffmpeg не справился, возвращаем оригинал
        return input_path


def split_audio(file_path: Path, chunk_duration: int = CHUNK_DURATION) -> List[Path]:
    """Нарезает аудио на куски по chunk_duration секунд."""
    output_pattern = file_path.parent / f"{file_path.stem}_part_%03d.mp3"

    subprocess.run([
        "ffmpeg", "-y", "-i", str(file_path),
        "-f", "segment", "-segment_time", str(chunk_duration),
        "-c", "copy", str(output_pattern)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    chunks = sorted(file_path.parent.glob(f"{file_path.stem}_part_*.mp3"))
    return chunks


async def transcribe_chunk(client: httpx.AsyncClient, chunk_path: Path, index: int, semaphore: asyncio.Semaphore) -> Tuple[int, str]:
    """Отправляет один кусок на транскрибацию."""
    async with semaphore:
        try:
            file_size = os.path.getsize(chunk_path) / 1024 / 1024
            print(f"--> [Часть {index}] Отправка ({file_size:.2f} MB)...")

            with open(chunk_path, "rb") as f:
                files = {'file': (chunk_path.name, f, "audio/mpeg")}
                data = {'service_name': SERVICE_NAME, 'model': 'gemini-flash-lite-latest'}

                response = await client.post(
                    f"{EXTERNAL_API_URL}/transcribe",
                    data=data,
                    files=files,
                    timeout=300.0
                )
                response.raise_for_status()
                text = response.json().get("text", "")
                print(f"<-- [Часть {index}] Готово!")
                return index, text
        except Exception as e:
            print(f"XXX [Часть {index}] Ошибка: {e}")
            return index, f"\n[Ошибка распознавания части {index}]\n"


async def process_parallel(file_path: Path) -> tuple[str, str]:
    """Оркестратор: Нарезка -> Параллельная транскрибация -> Склейка -> Саммари"""

    # 1. Нарезка
    print("Нарезка аудио на части...")
    chunks = split_audio(file_path)
    print(f"Получено {len(chunks)} частей.")

    # 2. Параллельная транскрибация
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    async with httpx.AsyncClient(timeout=600.0) as client:
        tasks = [
            transcribe_chunk(client, chunk, i, semaphore)
            for i, chunk in enumerate(chunks)
        ]

        results = await asyncio.gather(*tasks)

        # Сортируем и склеиваем
        results.sort(key=lambda x: x[0])
        full_transcription = "\n".join([r[1] for r in results])

        # Удаляем куски
        for chunk in chunks:
            if chunk.exists(): os.remove(chunk)

        # 3. Саммари
        summary_text = ""
        if full_transcription:
            print("Генерация общего саммари...")
            prompt = (
                f"Ты — профессиональный секретарь. Ниже полная расшифровка длинной встречи. "
                f"Твоя задача — составить структурированный протокол (Markdown).\n"
                f"1. Основная тема.\n"
                f"2. Ключевые тезисы (списком).\n"
                f"3. Задачи и договоренности (кто, что, когда).\n"
                f"4. Сроки.\n\n"
                f"Текст встречи:\n{full_transcription}"
            )

            try:
                json_payload = {
                    "service_name": SERVICE_NAME,
                    "model": "gemini-flash-lite-latest",
                    "prompt": prompt
                }
                resp_gen = await client.post(f"{EXTERNAL_API_URL}/generate", json=json_payload)
                if resp_gen.status_code == 200:
                    summary_text = resp_gen.json().get("text", "")
                else:
                    summary_text = f"Ошибка саммари: {resp_gen.text}"
            except Exception as e:
                summary_text = f"Ошибка соединения при саммари: {e}"

    return full_transcription, summary_text


# --- 5. ЭНДПОИНТЫ ---

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with Session(engine) as session:
        meetings = session.exec(select(Meeting).order_by(Meeting.id.desc())).all()
    return templates.TemplateResponse("index.html", {"request": request, "meetings": meetings})


@app.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    temp_path = UPLOAD_DIR / file.filename
    processed_audio_path = None

    try:
        # 1. Сохраняем оригинал
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Сжимаем (мастер-файл)
        processed_audio_path = compress_audio(temp_path)

        # 3. Запускаем обработку
        transcription, summary = await process_parallel(processed_audio_path)

        # 4. Сохраняем в БД
        with Session(engine) as session:
            meeting = Meeting(
                filename=file.filename,
                transcription=transcription,
                summary=summary
            )
            session.add(meeting)
            session.commit()
            session.refresh(meeting)

        # 5. Чистка
        if temp_path.exists(): os.remove(temp_path)
        if processed_audio_path and processed_audio_path != temp_path and processed_audio_path.exists():
            os.remove(processed_audio_path)

        return templates.TemplateResponse("components/meeting_row.html", {"request": request, "meeting": meeting})

    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        if temp_path.exists(): os.remove(temp_path)
        if processed_audio_path and processed_audio_path.exists(): os.remove(processed_audio_path)

        return HTMLResponse(
            f"<div class='bg-red-100 p-4 rounded text-red-700 font-bold'>Ошибка: {str(e)}</div>",
            status_code=500
        )