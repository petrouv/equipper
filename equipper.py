#!/usr/bin/env python3
"""
Скрипт для организации фото и видео по папкам с учетом устройства и софта.

Поддерживает два режима работы:
- Режим 1: Обработка файлов в одной папке
- Режим 2: Обработка множественных подпапок (каждая папка обрабатывается отдельно)

Алгоритм работы:
1. Автоматически определяет структуру входной директории
2. Использует ExifTool для первичной организации по устройствам/софту
3. Нормализует названия устройств (iPhone14,3 -> iPhone 13 Pro Max)
4. Удаляет версии приложений из путей (Moment, Blackmagic Cam)
5. Переименовывает папки версий iOS в Halide (если есть фото из Halide)
6. Извлекает фото из приложения Фото из папок Halide по умным правилам
7. Размещает системные файлы в корне устройства, приложения - в подпапках

Примеры использования:
    python equipper.py /path/to/photos              # одна папка с файлами
    python equipper.py /path/to/multiple_folders    # папка с подпапками
    equipper /path/to/photos  # после установки

Требования:
    - Python 3.6+
    - ExifTool должен быть установлен в системе
"""

import sys
from pathlib import Path

try:
    from .organizer import FileOrganizer
except ImportError:
    # Fallback for direct script execution
    from organizer import FileOrganizer


def main():
    """Главная функция командного скрипта.

    Обрабатывает аргументы командной строки, создает экземпляр
    FileOrganizer и запускает процесс организации файлов.

    Логика валидации:
    1. Проверяет наличие ровно одного аргумента
    2. Проверяет существование и тип указанного пути
    3. Запускает организацию с обработкой ошибок

    Exit codes:
        0: Успешное завершение
        1: Ошибка в аргументах или критическая ошибка
    """
    # Проверяем правильность использования
    if len(sys.argv) != 2:
        print("Использование: equipper <путь_к_исходной_папке>")
        print("Пример: equipper /Users/user/Photos/Camera_Roll")
        sys.exit(1)

    # Получаем и проверяем исходную папку
    src_path = Path(sys.argv[1])

    if not src_path.exists() or not src_path.is_dir():
        print(f"Ошибка: {src_path} не существует или не является папкой")
        sys.exit(1)

    try:
        # Создаем организатор и запускаем обработку
        organizer = FileOrganizer(src_path)
        organizer.organize()

        print("\n🎉 Обработка завершена успешно!")

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
