import shutil
import os
from fastapi import APIRouter, Request, UploadFile, File, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.config import UPLOAD_DIR
from app.models.meeting import Meeting
from app.services import audio, gemini

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def index(request: Request, session: Session = Depends(get_session)):
    meetings = session.exec(select(Meeting).order_by(Meeting.id.desc())).all()
    return templates.TemplateResponse("index.html", {"request": request, "meetings": meetings})


@router.post("/upload")
async def upload_file(
        request: Request,
        file: UploadFile = File(...),
        session: Session = Depends(get_session)
):
    try:
        # 1. Сохраняем файл
        temp_path = UPLOAD_DIR / file.filename
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Обработка (Конвертация -> Транскрибация -> Саммари)
        # В реальном проекте это лучше делать в BackgroundTasks, но для UI результата ждем
        audio_path = audio.extract_audio_from_video(temp_path)
        transcription = await gemini.transcribe_audio(audio_path)
        summary = await gemini.generate_summary(transcription)

        # 3. Сохраняем в БД
        meeting = Meeting(
            filename=file.filename,
            transcription=transcription,
            summary=summary
        )
        session.add(meeting)
        session.commit()
        session.refresh(meeting)

        # 4. Чистка
        if temp_path.exists(): os.remove(temp_path)
        if audio_path != temp_path and audio_path.exists(): os.remove(audio_path)

        # 5. Возвращаем частичный HTML (строку таблицы)
        return templates.TemplateResponse("components/meeting_row.html", {"request": request, "meeting": meeting})

    except Exception as e:
        print(f"Error: {e}")
        # Возвращаем HTML с ошибкой, который HTMX вставит в UI
        return templates.TemplateResponse(
            "components/error.html",
            {"request": request, "message": str(e)},
            status_code=500
        )