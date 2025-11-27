document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    // Элементы UI
    const actionSection = document.getElementById('action-section');
    const fileNameDisplay = document.getElementById('file-name');
    const dropText = document.getElementById('drop-text');

    // --- Drag & Drop Events ---

    // Предотвращаем стандартное поведение
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Подсветка зоны
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('border-blue-500', 'bg-blue-50');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('border-blue-500', 'bg-blue-50');
        });
    });

    // --- Обработка Файлов ---

    // 1. Если перетащили файл
    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    });

    // 2. Если выбрали через клик
    fileInput.addEventListener('change', () => {
        handleFiles(fileInput.files);
    });

    function handleFiles(files) {
        if (files.length > 0) {
            // Присваиваем файлы инпуту (важно для отправки формы!)
            fileInput.files = files;

            // Обновляем UI
            const name = files[0].name;

            // Скрываем "Нажмите сюда"
            dropText.classList.add('hidden');

            // Показываем имя файла
            fileNameDisplay.textContent = "📄 " + name;
            fileNameDisplay.classList.remove('hidden');

            // ПОКАЗЫВАЕМ КНОПКУ
            actionSection.classList.remove('hidden');
        }
    }
});