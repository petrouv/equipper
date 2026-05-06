"""Детекторы для определения типов файлов и их принадлежности приложениям.

Этот модуль содержит классы для:
- Группировки связанных файлов (Live Photos, RAW+JPEG пары и т.д.)
- Определения принадлежности файлов конкретным приложениям
- Извлечения метаданных устройств из EXIF
- Анализа файловых паттернов iOS приложений
"""

import json
import subprocess

from .constants import AppNames, FilePatterns, MediaExtensions


class FileGroup:
    """Класс для представления группы связанных файлов.

    Группа объединяет файлы с одинаковым базовым именем (например IMG_7256):
    - IMG_7256.HEIC (основное фото)
    - IMG_E7256.HEIC (обработанная версия)
    - IMG_E7256.MOV (видеочасть Live Photo)
    - IMG_7256.DNG (RAW версия)
    - IMG_7256.AAE (метаданные редактирования)
    """

    def __init__(self, base_name, app_type=None):
        """Инициализация группы файлов.

        Args:
            base_name (str): Базовое имя файла (например, '7256' для IMG_7256)
            app_type (str, optional): Тип приложения из AppNames
        """
        self.base_name = base_name  # IMG_7256, A001_08041410_C001, etc.
        self.files = []  # Список путей к файлам в группе
        self.app_type = app_type  # Photos, Halide, Blackmagic, etc.
        self.device_info = None  # Информация об устройстве из EXIF

    def add_file(self, file_path):
        """Добавляет файл в группу.

        Args:
            file_path (Path): Путь к файлу для добавления в группу
        """
        self.files.append(file_path)

    def get_primary_file(self):
        """Возвращает основной файл группы (для извлечения метаданных).

        Приоритет файлов по информативности EXIF данных:
        1. HEIC/HEIF - наиболее полные метаданные iOS
        2. RAW (DNG, RAF, ARW, CR2/CR3, NEF, ORF, RW2, ...) - полные EXIF от камер
        3. MOV/MP4 - видео файлы
        4. JPG/JPEG/PNG/TIFF - сжатые изображения
        5. AAE/XMP - только метаданные редактирования

        Returns:
            Path: Путь к файлу с наивысшим приоритетом
        """
        priorities = {
            ".HEIC": 1,
            ".HEIF": 1,
            **dict.fromkeys(MediaExtensions.RAW, 2),
            **dict.fromkeys(MediaExtensions.VIDEOS, 3),
            ".JPG": 4,
            ".JPEG": 4,
            ".PNG": 5,
            ".TIF": 5,
            ".TIFF": 5,
            **dict.fromkeys(MediaExtensions.METADATA, 6),
        }
        return min(self.files, key=lambda f: priorities.get(f.suffix.upper(), 7))

    def __repr__(self):
        return f"FileGroup({self.base_name}, {self.app_type}, {len(self.files)} files)"


class FileGrouper:
    """Класс для группировки файлов по связям.

    Анализирует файлы в директории и объединяет их в логические группы
    на основе базовых имен и типов файлов. Определяет принадлежность
    каждой группы к конкретному приложению через анализ EXIF и паттернов.
    """

    def __init__(self):
        self.detector = FileTypeDetector()
        self.blackmagic_detector = BlackmagicDetector()

    def scan_and_group_files(self, directory, recursive=True):
        """Сканирует директорию и группирует файлы по связям.

        Процесс группировки:
        1. Находит все медиафайлы в директории
        2. Извлекает базовые имена для группировки
        3. Определяет принадлежность к приложениям через EXIF
        4. Извлекает информацию об устройствах

        Args:
            directory (Path): Директория для сканирования
            recursive (bool): Если True — обходит вложенные папки (rglob).
                Если False — только файлы непосредственно в `directory`.
                Используется в смешанном режиме при финальной обработке
                корневой папки, чтобы не захватывать файлы из уже
                обработанных подпапок.

        Returns:
            List[FileGroup]: Список групп файлов
        """
        print("Этап 1: Сканирование и группировка файлов...")

        # Собираем все медиафайлы
        all_files = []
        iterator = directory.rglob("*") if recursive else directory.iterdir()
        for file_path in iterator:
            if file_path.is_file() and FileTypeDetector.is_media_file(file_path):
                all_files.append(file_path)

        print(f"  Найдено медиафайлов: {len(all_files)}")

        # Группируем файлы по базовым именам
        groups = {}

        for file_path in all_files:
            base_name = self._extract_base_name(file_path)

            if base_name not in groups:
                groups[base_name] = FileGroup(base_name)

            groups[base_name].add_file(file_path)

        # Определяем принадлежность каждой группы к приложению
        grouped_files = list(groups.values())
        for group in grouped_files:
            group.app_type = self._determine_group_app_type(group)
            group.device_info = self._extract_device_info(group.get_primary_file())

        print(f"  Создано групп файлов: {len(grouped_files)}")
        self._print_group_summary(grouped_files)

        return grouped_files

    def _extract_base_name(self, file_path):
        """Извлекает базовое имя файла для группировки.

        Логика извлечения базового имени:
        - IMG_E7256.* -> 7256 (отредактированные файлы)
        - IMG_7256.* -> 7256 (стандартные файлы)
        - Другие файлы -> полное имя без расширения

        Args:
            file_path (Path): Путь к файлу

        Returns:
            str: Базовое имя для группировки
        """
        file_name = file_path.name

        # Для IMG файлов используем номер
        if file_name.startswith("IMG_E"):
            return file_name[5:9]  # IMG_E7256 -> 7256
        elif file_name.startswith("IMG_"):
            return file_name[4:8]  # IMG_7256 -> 7256
        else:
            # Для остальных файлов используем имя без расширения
            return file_path.stem

    def _determine_group_app_type(self, group):
        """Определяет, какому приложению принадлежит группа файлов.

        Алгоритм определения:
        1. Проверка EXIF на специфичные приложения (Filmic, Moment, Blackmagic)
        2. Photos-дискриминаторы (приоритет над Halide):
           - AAE в группе → Photos (сайдкар правки из Photos.app)
           - любой MOV в группе → Photos (Live Photo: HEIC+MOV или HEIC+EHEIC+MOV+EMOV)
        3. Halide-сигнатуры (только без AAE и без MOV):
           - DNG+HEIC = Halide RAW
           - HEIC+IMG_E.HEIC = Halide Portrait

        Args:
            group (FileGroup): Группа файлов для анализа

        Returns:
            str: Название приложения из AppNames
        """
        # Собираем информацию о файлах в группе
        has_dng = any(f.suffix.upper() == ".DNG" for f in group.files)
        has_heic = any(
            f.suffix.upper() == ".HEIC" and f.name.startswith("IMG_") for f in group.files
        )
        has_e_heic = any(
            f.suffix.upper() == ".HEIC" and f.name.startswith("IMG_E") for f in group.files
        )
        has_aae = any(f.suffix.upper() == ".AAE" for f in group.files)
        has_mov = any(f.suffix.upper() == ".MOV" for f in group.files)

        # EXIF-основанное определение приложений
        # Проверяем каждый файл в группе на наличие метаданных от специфичных приложений
        for file_path in group.files:
            try:
                result = subprocess.run(
                    ["exiftool", "-Make", "-Software", "-json", str(file_path)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)[0]
                    make = data.get("Make", "").lower()
                    software = data.get("Software", "").lower()

                    # Filmic может записывать себя и в Make, и в Software
                    if "filmic" in make:
                        return AppNames.FILMIC
                    elif "moment" in software:
                        return AppNames.MOMENT
                    elif "filmic" in software:
                        return AppNames.FILMIC
            except Exception:
                # Ошибки EXIF игнорируем - продолжаем проверку других файлов
                pass

        # Blackmagic имеет высокий приоритет, т.к. оставляет четкую подпись в EXIF
        for file_path in group.files:
            if self.blackmagic_detector.is_blackmagic_file(file_path):
                return AppNames.BLACKMAGIC

        # Логика определения для IMG файлов (с числовым базовым именем)
        if group.base_name.isdigit():  # IMG_7256, IMG_E7256, и т.д.
            # AAE/MOV — однозначные сигнатуры Photos.app: AAE пишет только Photos
            # при правке, MOV (любой) — Live Photo. Halide ни AAE, ни MOV не создаёт.
            if has_aae or has_mov:
                return AppNames.PHOTOS
            # Признаки Halide (нет ни AAE, ни MOV):
            # 1. RAW режим: IMG_xxxx.DNG + IMG_xxxx.HEIC
            # 2. Portrait режим: IMG_xxxx.HEIC + IMG_Exxxx.HEIC
            if (has_dng and has_heic) or (has_heic and has_e_heic):
                return AppNames.HALIDE
            return AppNames.PHOTOS

        # Для остальных файлов - Photos по умолчанию
        return AppNames.PHOTOS

    def _extract_device_info(self, file_path):
        """Извлекает информацию об устройстве из EXIF.

        Фильтрует реальные устройства от приложений по полям Make/Model.
        Приложения часто записывают свои названия в поле Make, что не
        соответствует реальному устройству съемки.

        Args:
            file_path (Path): Путь к файлу для извлечения EXIF

        Returns:
            dict|None: Словарь с make/model или None если устройство не определено
        """
        try:
            result = subprocess.run(
                ["exiftool", "-Make", "-Model", "-json", str(file_path)],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)[0]
                make = data.get("Make", "")
                model = data.get("Model", "")

                # Фильтруем только реальные устройства (не приложения)
                app_makes = [
                    "Filmic",
                    "Filmic Pro",
                    "Blackmagic",
                    "Blackmagic Design",
                    "Moment",
                    "Halide",
                ]
                if (make == "Apple" and model and "iPhone" in model) or (
                    make
                    and model
                    and make not in app_makes
                    and not any(app in make for app in ["Filmic", "Blackmagic", "Moment", "Halide"])
                ):
                    return {"make": make, "model": model}
        except Exception:
            pass

        # Для файлов без EXIF или от приложений возвращаем None - они будут назначены основному устройству
        return None

    def _print_group_summary(self, groups):
        """Выводит сводку по группам файлов.

        Показывает статистику распределения файлов по приложениям
        для контроля корректности группировки.

        Args:
            groups (List[FileGroup]): Список групп файлов
        """
        app_counts = {}
        for group in groups:
            app_type = group.app_type
            if app_type not in app_counts:
                app_counts[app_type] = 0
            app_counts[app_type] += len(group.files)

        for app_type, count in app_counts.items():
            print(f"    {app_type}: {count} файлов")


class FileTypeDetector:
    """Базовый класс для определения типов файлов.

    Содержит статические методы для основных проверок:
    - Проверка медиафайлов по расширению
    - Анализ паттернов именования iOS файлов
    - Извлечение базовых номеров из имен файлов
    """

    @staticmethod
    def is_media_file(file_path):
        """Проверяет, является ли файл медиафайлом.

        Args:
            file_path (Path): Путь к файлу для проверки

        Returns:
            bool: True если файл является медиафайлом
        """
        return file_path.suffix.upper() in MediaExtensions.ALL

    @staticmethod
    def is_aae_file(file_path):
        """Проверяет, является ли файл AAE."""
        return file_path.suffix.upper() == ".AAE"

    @staticmethod
    def is_img_e_file(file_name):
        """Проверяет, является ли файл IMG_E*."""
        return file_name.startswith(FilePatterns.IMG_E)

    @staticmethod
    def is_base_img_file(file_name):
        """Проверяет, является ли файл базовым IMG_*."""
        return file_name.startswith(FilePatterns.IMG_BASE)

    @staticmethod
    def get_base_number(file_name):
        """Извлекает базовый номер из имени файла IMG_xxxx или IMG_Exxxx.

        Args:
            file_name (str): Имя файла для извлечения номера

        Returns:
            str|None: Базовый номер (например '7256') или None если не найден
        """
        if file_name.startswith(FilePatterns.IMG_E):
            return file_name[5:9]  # IMG_E7256 -> 7256
        elif file_name.startswith(FilePatterns.IMG_BASE):
            return file_name[4:8]  # IMG_7256 -> 7256
        return None


class PhotosAppFileDetector:
    """Класс для определения файлов из стандартного приложения Фото iOS.

    Основная логика определения:
    - Live Photos: IMG_xxxx.HEIC + IMG_Exxxx.HEIC + IMG_Exxxx.MOV
    - Обычные фото: одиночные IMG_xxxx.HEIC без парных файлов
    - Отличие от Halide: отсутствие DNG файлов и наличие MOV в парах
    """

    def __init__(self):
        self.detector = FileTypeDetector()

    def is_photos_app_file(self, file_path):
        """Главный метод определения принадлежности файла приложению Фото.

        Логика приоритетов:
        1. DNG файлы - обычно Halide, но могут быть скопированы в Фото
        2. IMG_E файлы - обработанные версии и Live Photos
        3. Базовые IMG_ файлы - стандартные фото
        4. MOV/PNG файлы - обычно из Фото

        Args:
            file_path (Path): Путь к файлу для анализа

        Returns:
            bool: True если файл относится к приложению Фото
        """
        if self.detector.is_aae_file(file_path):
            return False  # AAE обрабатываются отдельно

        file_name = file_path.name
        parent_folder = file_path.parent

        # Сначала проверяем расширение .DNG (приоритет выше)
        if file_path.suffix.upper() == ".DNG":
            return self._process_dng_file(file_path, parent_folder)
        elif self.detector.is_img_e_file(file_name):
            return self._process_img_e_file(file_path, parent_folder)
        elif self.detector.is_base_img_file(file_name):
            return self._process_base_img_file(file_path, parent_folder)
        elif file_path.suffix.upper() in {".MOV", ".PNG"}:
            return True

        return False

    def _process_img_e_file(self, file_path, parent_folder):
        """Обрабатывает файлы IMG_E*."""
        file_name = file_path.name
        base_num = self.detector.get_base_number(file_name)
        img_base = f"{FilePatterns.IMG_BASE}{base_num}"

        if file_path.suffix.upper() == ".HEIC":
            return self._process_img_e_heic(base_num, img_base, parent_folder)
        elif file_path.suffix.upper() == ".MOV":
            return True  # IMG_E*.MOV - часть Live Photo
        elif file_path.suffix.upper() == ".JPG":
            return self._process_img_e_jpg(img_base, parent_folder)

        return False

    def _process_img_e_heic(self, base_num, img_base, parent_folder):
        """Обрабатывает файлы IMG_E*.HEIC."""
        base_heic = parent_folder / f"{img_base}.HEIC"
        e_mov = parent_folder / f"{FilePatterns.IMG_E}{base_num}.MOV"
        base_mov = parent_folder / f"{img_base}.MOV"
        base_aae = parent_folder / f"{img_base}.AAE"

        if base_heic.exists():
            # AAE/любой MOV рядом — однозначно Photos.app:
            # - AAE пишет только Photos при правке
            # - MOV без E (HEIC+MOV) — Live Photo, MOV с E — отредактированный Live
            if base_aae.exists() or e_mov.exists() or base_mov.exists():
                return True
            # Иначе HEIC+EHEIC без сайдкаров — Halide Portrait
            return False

        return False  # Нет базового HEIC - не можем определить

    def _process_img_e_jpg(self, img_base, parent_folder):
        """Обрабатывает файлы IMG_E*.JPG."""
        base_heic = parent_folder / f"{img_base}.HEIC"
        # Если нет базового HEIC, то это точно не Halide Portrait
        return not base_heic.exists()

    def _process_base_img_file(self, file_path, parent_folder):
        """Обрабатывает базовые файлы IMG_*.HEIC."""
        if file_path.suffix.upper() != ".HEIC":
            return False

        file_name = file_path.name
        base_num = self.detector.get_base_number(file_name)
        e_heic = parent_folder / f"{FilePatterns.IMG_E}{base_num}.HEIC"
        e_mov = parent_folder / f"{FilePatterns.IMG_E}{base_num}.MOV"
        base_mov = parent_folder / f"{FilePatterns.IMG_BASE}{base_num}.MOV"
        base_aae = parent_folder / f"{FilePatterns.IMG_BASE}{base_num}.AAE"
        base_dng = parent_folder / f"{FilePatterns.IMG_BASE}{base_num}.DNG"

        # Приоритет 1: Halide RAW (DNG+HEIC, без AAE и без MOV)
        if base_dng.exists() and not base_aae.exists() and not base_mov.exists():
            return False  # Это Halide RAW

        # Приоритет 2: AAE или любой MOV — Photos
        # (Live Photo: HEIC+MOV; Live edited: +EHEIC+EMOV+AAE; Photo edited: +EHEIC+AAE)
        if base_aae.exists() or e_mov.exists() or base_mov.exists():
            return True

        # Приоритет 3: Halide Portrait (HEIC + EHEIC без сайдкаров)
        if e_heic.exists():
            return False

        # Приоритет 4: Обычное фото из Photos (одиночный HEIC)
        return True

    def _process_dng_file(self, file_path, parent_folder):
        """Обрабатывает DNG файлы."""
        file_name = file_path.name
        base_num = self.detector.get_base_number(file_name)

        # Если файл уже в папке Halide, проверяем есть ли соответствующий HEIC
        if parent_folder.name == AppNames.HALIDE:
            base_heic = parent_folder / f"{FilePatterns.IMG_BASE}{base_num}.HEIC"
            # DNG + HEIC в Halide - это пара из Halide (остается в Halide)
            if base_heic.exists():
                return False
            # Одиночный DNG в Halide - это файл из Photos (извлекается)
            return True

        # Если файл не в Halide, стандартная логика
        base_heic = parent_folder / f"{FilePatterns.IMG_BASE}{base_num}.HEIC"
        if base_heic.exists():
            return False
        return True


class BlackmagicDetector:
    """Класс для определения файлов Blackmagic Camera.

    Blackmagic Camera - профессиональное приложение для видеосъемки.
    Определение происходит через анализ EXIF поля Software,
    где приложение оставляет свою подпись.
    """

    @staticmethod
    def is_blackmagic_file(file_path):
        """Проверяет, является ли файл из Blackmagic Camera через ExifTool.

        Поиск ключевого слова 'blackmagic' в поле Software EXIF данных.
        Приложение Blackmagic Camera записывает свою сигнатуру
        в метаданные файла, что позволяет надежно его идентифицировать.

        Args:
            file_path (Path): Путь к файлу для проверки

        Returns:
            bool: True если файл создан Blackmagic Camera
        """
        try:
            result = subprocess.run(
                ["exiftool", "-Software", "-json", str(file_path)],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)[0]
                software = data.get("Software", "")
                return FilePatterns.BLACKMAGIC_SOFTWARE_KEYWORD in software.lower()
        except Exception:
            pass
        return False


class HalideDetector:
    """Класс для определения файлов из приложения Halide.

    Halide - профессиональное приложение камеры с поддержкой RAW.
    Основные признаки:
    - DNG файлы (часто в паре с HEIC)
    - Halide Portrait: IMG_xxxx.HEIC + IMG_Exxxx.HEIC без MOV файла
    """

    @staticmethod
    def has_halide_files(folder):
        """Проверяет, есть ли в папке файлы из Halide.

        Сигнатуры Halide (только без AAE и без MOV рядом — иначе Photos):
        1. DNG+HEIC пара (Halide RAW). Одиночный DNG — это ProRAW из Photos.
        2. IMG_xxxx.HEIC + IMG_Exxxx.HEIC без AAE/MOV (Halide Portrait).

        Args:
            folder (Path): Папка для проверки

        Returns:
            bool: True если в папке есть файлы Halide
        """
        for file_path in folder.rglob("*"):
            if not file_path.is_file():
                continue

            if file_path.name.startswith("IMG_") and not file_path.name.startswith("IMG_E"):
                base_num = file_path.name[4:8]
                parent = file_path.parent
                base_heic = parent / f"IMG_{base_num}.HEIC"
                base_dng = parent / f"IMG_{base_num}.DNG"
                base_mov = parent / f"IMG_{base_num}.MOV"
                base_aae = parent / f"IMG_{base_num}.AAE"
                e_heic = parent / f"IMG_E{base_num}.HEIC"
                e_mov = parent / f"IMG_E{base_num}.MOV"

                if base_aae.exists() or base_mov.exists() or e_mov.exists():
                    continue  # Photos-сигнатура, не Halide

                # Halide RAW: DNG+HEIC
                if base_dng.exists() and base_heic.exists():
                    return True
                # Halide Portrait: HEIC+EHEIC без сайдкаров
                if base_heic.exists() and e_heic.exists():
                    return True

        return False
