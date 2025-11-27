import subprocess
from pathlib import Path


def extract_audio_from_video(input_path: Path) -> Path:
    """Конвертирует видео в mp3. Если аудио - возвращает путь как есть."""
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}

    if input_path.suffix.lower() not in video_extensions:
        return input_path

    output_path = input_path.with_suffix('.mp3')

    # Используем системный ffmpeg
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(input_path),
            "-vn", "-acodec", "libmp3lame", str(output_path)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path
    except subprocess.CalledProcessError:
        # Если ошибка (например, битый файл), возвращаем оригинал, пусть API разбирается
        return input_path