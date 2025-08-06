"""Основной класс для организации медиафайлов.

Этот модуль содержит главную логику организации медиафайлов:
- Сканирование и группировка связанных файлов
- Создание структуры папок по устройствам и приложениям
- Перемещение файлов в соответствующие папки
- Нормализация названий устройств Apple
- Очистка пустых папок после обработки

Поддерживает два режима работы:
- Обработка файлов в одной папке
- Обработка множественных подпапок
"""

import shutil
import subprocess
import sys
from pathlib import Path

try:
    from .constants import AppNames, FilePatterns
    from .detectors import (
        BlackmagicDetector,
        FileGrouper,
        FileTypeDetector,
        HalideDetector,
        PhotosAppFileDetector,
    )
except ImportError:
    # Fallback for direct script execution
    from constants import AppNames, FilePatterns
    from detectors import (
        BlackmagicDetector,
        FileGrouper,
        FileTypeDetector,
        HalideDetector,
        PhotosAppFileDetector,
    )


class OrganizationPipeline:
    """Класс для выполнения цепочки операций по организации файлов.

    Реализует паттерн "Цепочка обязанностей" для последовательного
    выполнения всех этапов организации файлов:
    1. Сканирование и группировка файлов
    2. Создание структуры устройств и папок
    3. Перемещение файлов по назначениям
    """

    @staticmethod
    def run_full_pipeline(organizer):
        """Выполняет полный цикл организации файлов.

        Координирует выполнение всех этапов обработки в правильном порядке.
        Каждый этап зависит от результатов предыдущего.

        Args:
            organizer (FileOrganizer): Экземпляр организатора файлов
        """
        file_groups = organizer.scan_and_group_files()
        devices, primary_device = organizer.create_device_structure(file_groups)
        organizer.move_groups_to_destinations(file_groups, devices, primary_device)


class FileOrganizer:
    """Основной класс для организации медиафайлов по устройствам и программам.

    Главный координатор всего процесса организации файлов.
    Объединяет функциональность всех детекторов и группировщиков
    для создания структурированной файловой системы.

    Особенности:
    - Автоматическое определение структуры входной директории
    - Нормализация названий устройств Apple (iPhone14,3 -> iPhone 13 Pro Max)
    - Интеллектуальная группировка связанных файлов (Live Photos, RAW+JPEG)
    - Поддержка множественных режимов обработки
    """

    def __init__(self, src_dir):
        """Инициализация организатора файлов.

        Args:
            src_dir (str | Path): Исходная директория с файлами
        """
        self.src_dir = Path(src_dir)
        self.grouper = FileGrouper()
        self.pipeline = OrganizationPipeline()

        # Инициализируем детекторы с обработкой ошибок
        try:
            self.photos_detector = PhotosAppFileDetector()
        except Exception as e:
            print(f"⚠️ Ошибка инициализации PhotosAppFileDetector: {e}")
            self.photos_detector = None

        try:
            self.halide_detector = HalideDetector()
        except Exception as e:
            print(f"⚠️ Ошибка инициализации HalideDetector: {e}")
            self.halide_detector = None

        try:
            self.blackmagic_detector = BlackmagicDetector()
        except Exception as e:
            print(f"⚠️ Ошибка инициализации BlackmagicDetector: {e}")
            self.blackmagic_detector = None

        # Словарь для нормализации технических названий iPhone в читаемые
        # Содержит только реально существующие модели с их техническими идентификаторами
        # Источник: официальная документация Apple Developer
        self.iphone_models = {
            # iPhone 15 Series (2023) - РЕАЛЬНЫЕ
            "iPhone16,1": "iPhone 15 Pro",
            "iPhone16,2": "iPhone 15 Pro Max",
            "iPhone15,4": "iPhone 15",
            "iPhone15,5": "iPhone 15 Plus",
            # iPhone 14 Series (2022) - РЕАЛЬНЫЕ
            "iPhone15,2": "iPhone 14 Pro",
            "iPhone15,3": "iPhone 14 Pro Max",
            "iPhone14,7": "iPhone 14",
            "iPhone14,8": "iPhone 14 Plus",
            # iPhone 13 Series (2021) - РЕАЛЬНЫЕ
            "iPhone14,2": "iPhone 13 Pro",
            "iPhone14,3": "iPhone 13 Pro Max",
            "iPhone14,5": "iPhone 13",
            "iPhone14,4": "iPhone 13 mini",
            # iPhone 12 Series (2020) - РЕАЛЬНЫЕ
            "iPhone13,3": "iPhone 12 Pro",
            "iPhone13,4": "iPhone 12 Pro Max",
            "iPhone13,2": "iPhone 12",
            "iPhone13,1": "iPhone 12 mini",
            # iPhone SE 3rd Gen (2022) - РЕАЛЬНЫЕ
            "iPhone14,6": "iPhone SE (3rd generation)",
            # iPhone 11 Series (2019) - РЕАЛЬНЫЕ
            "iPhone12,3": "iPhone 11 Pro",
            "iPhone12,5": "iPhone 11 Pro Max",
            "iPhone12,1": "iPhone 11",
            # iPhone XS/XR Series (2018) - РЕАЛЬНЫЕ
            "iPhone11,2": "iPhone XS",
            "iPhone11,4": "iPhone XS Max",
            "iPhone11,6": "iPhone XS Max",
            "iPhone11,8": "iPhone XR",
            # iPhone X (2017) - РЕАЛЬНЫЕ
            "iPhone10,3": "iPhone X",
            "iPhone10,6": "iPhone X",
            # iPhone 8 Series (2017) - РЕАЛЬНЫЕ
            "iPhone10,1": "iPhone 8",
            "iPhone10,4": "iPhone 8",
            "iPhone10,2": "iPhone 8 Plus",
            "iPhone10,5": "iPhone 8 Plus",
            # iPhone 7 Series (2016) - РЕАЛЬНЫЕ
            "iPhone9,1": "iPhone 7",
            "iPhone9,3": "iPhone 7",
            "iPhone9,2": "iPhone 7 Plus",
            "iPhone9,4": "iPhone 7 Plus",
            # iPhone SE 1st Gen (2016) - РЕАЛЬНЫЕ
            "iPhone8,4": "iPhone SE (1st generation)",
            # iPhone 6s Series (2015) - РЕАЛЬНЫЕ
            "iPhone8,1": "iPhone 6s",
            "iPhone8,2": "iPhone 6s Plus",
            # iPhone 6 Series (2014) - РЕАЛЬНЫЕ
            "iPhone7,2": "iPhone 6",
            "iPhone7,1": "iPhone 6 Plus",
            # iPhone SE 2nd Gen (2020) - РЕАЛЬНЫЕ
            "iPhone12,8": "iPhone SE (2nd generation)",
        }

        # Счетчики для статистики
        self.processed_files = []
        self.created_folders = []
        self.moved_folders = []

    def scan_and_group_files(self):
        """Этап 1: Сканирование и группировка всех файлов.

        Делегирует работу FileGrouper для поиска и объединения
        связанных файлов в логические группы.

        Returns:
            List[FileGroup]: Список групп связанных файлов
        """
        return self.grouper.scan_and_group_files(self.src_dir)

    def create_device_structure(self, file_groups):
        """Этап 2: Создание структуры устройств.

        Анализирует группы файлов для определения уникальных устройств
        и создает только папки устройств. Папки приложений создаются
        по мере необходимости в процессе перемещения файлов.

        Args:
            file_groups (List[FileGroup]): Группы файлов для анализа

        Returns:
            tuple: (devices_dict, primary_device_name)
        """
        print("Этап 2: Создание структуры устройств...")

        # Собираем информацию об устройствах (только с валидными EXIF данными)
        devices = {}
        primary_device = None

        for group in file_groups:
            if group.device_info:
                make = group.device_info["make"]
                model = group.device_info["model"]

                # Нормализуем название устройства
                device_name = self._normalize_device_name(make, model)

                if device_name not in devices:
                    devices[device_name] = self.src_dir / device_name
                    devices[device_name].mkdir(exist_ok=True)
                    print(f"  ✅ Создано устройство: {device_name}")

                    # Запоминаем первое (основное) устройство
                    if primary_device is None:
                        primary_device = device_name

        # Если не найдено ни одного устройства, создаем дефолтное
        if not devices:
            primary_device = "Apple iPhone 13 Pro Max"  # Дефолтное устройство
            devices[primary_device] = self.src_dir / primary_device
            devices[primary_device].mkdir(exist_ok=True)
            print(f"  ✅ Создано дефолтное устройство: {primary_device}")

        return devices, primary_device

    def move_groups_to_destinations(self, file_groups, devices, primary_device):
        """Этап 3: Перемещение файлов группами по назначениям.

        Перемещает каждую группу файлов целиком в соответствующую папку.
        Файлы без информации об устройстве назначаются основному устройству.
        Папки приложений создаются автоматически по мере необходимости.

        Логика размещения:
        - Photos (устройство) → корень папки устройства
        - Halide → подпапка Halide/
        - Blackmagic → подпапка Blackmagic Camera/
        - Moment → подпапка Moment/
        - Filmic → подпапка Filmic/

        Args:
            file_groups (List[FileGroup]): Группы файлов для перемещения
            devices (dict): Словарь устройство → путь к папке
            primary_device (str): Основное устройство для файлов без EXIF
        """
        print("Этап 3: Перемещение файлов по назначениям...")

        total_moved = 0

        for group in file_groups:
            # Определяем папку устройства
            if group.device_info:
                make = group.device_info["make"]
                model = group.device_info["model"]
                device_name = self._normalize_device_name(make, model)
            else:
                # Файлы без EXIF идут в основное устройство
                device_name = primary_device

            device_path = devices[device_name]

            # Определяем папку назначения и создаем ее при необходимости
            if group.app_type == AppNames.PHOTOS:
                dest_folder = device_path
            else:
                dest_folder = device_path / group.app_type
                # Создаем папку приложения только если она нужна
                self._ensure_folder_exists(dest_folder)

            # Перемещаем все файлы группы
            for file_path in group.files:
                # Проверяем, нужно ли перемещать
                if file_path.parent == dest_folder:
                    continue

                dest_path = dest_folder / file_path.name
                if self._move_file(file_path, dest_path):
                    total_moved += 1
                    self.processed_files.append(f"{file_path.name} -> {group.app_type}")

        if total_moved > 0:
            print(f"  ✅ Всего перемещено файлов: {total_moved}")

        # Удаляем пустые папки
        self._cleanup_empty_folders()

    def _normalize_device_name(self, make, model):
        """Нормализует техническое название устройства в читаемое.

        Преобразует технические идентификаторы Apple в понятные названия:
        iPhone14,3 → iPhone 13 Pro Max
        iPhone15,2 → iPhone 14 Pro

        Для других производителей возвращает комбинацию Make + Model.

        Args:
            make (str): Производитель устройства (из EXIF)
            model (str): Модель устройства (из EXIF)

        Returns:
            str: Нормализованное название устройства
        """
        if make == "Apple" and model.startswith("iPhone"):
            # Проверяем, есть ли это в словаре нормализации
            if model in self.iphone_models:
                return f"Apple {self.iphone_models[model]}"
            else:
                return f"Apple {model}"
        else:
            return f"{make} {model}"

    def _cleanup_empty_folders(self):
        """Удаляет пустые папки после перемещения файлов.

        Рекурсивно ищет и удаляет пустые директории в исходной папке.
        Полезно для очистки структуры после реорганизации файлов.
        Сохраняет корневую папку даже если она пустая.
        """
        print("  Очистка пустых папок...")

        removed_count = 0
        # Ищем пустые папки рекурсивно
        for folder_path in list(self.src_dir.rglob("*")):
            if (
                folder_path.is_dir()
                and folder_path != self.src_dir
                and not any(folder_path.iterdir())
            ):  # папка пустая
                try:
                    folder_path.rmdir()
                    print(f"    🗑️ Удалена пустая папка: {folder_path.name}")
                    removed_count += 1
                except Exception as e:
                    print(f"    ❌ Ошибка удаления {folder_path.name}: {e}")

        if removed_count > 0:
            print(f"  ✅ Удалено пустых папок: {removed_count}")

    def _ensure_folder_exists(self, folder_path):
        """Безопасно создает папку если она не существует.

        Использует mkdir с exist_ok=True для избежания ошибок
        при попытке создать уже существующую папку.

        Args:
            folder_path (Path): Путь к папке для создания
        """
        try:
            folder_path.mkdir(exist_ok=True)
            print(f"    ✅ Создана папка приложения: {folder_path.name}")
        except Exception as e:
            print(f"    ❌ Ошибка создания папки {folder_path.name}: {e}")

    def _move_file(self, source_path, dest_path):
        """Безопасно перемещает файл с обработкой ошибок.

        Использует shutil.move для атомарного перемещения файла.
        Автоматически создает промежуточные папки если нужно.

        Args:
            source_path (Path): Исходный путь к файлу
            dest_path (Path): Путь назначения

        Returns:
            bool: True если перемещение успешно, False при ошибке
        """
        try:
            shutil.move(str(source_path), str(dest_path))
            return True
        except Exception as e:
            print(f"    ❌ Ошибка перемещения {source_path.name}: {e}")
            return False

    def check_exiftool(self):
        """Проверяет наличие ExifTool в системе.

        ExifTool - необходимая зависимость для извлечения метаданных
        из медиафайлов. Без него невозможно определить устройство съемки
        и приложение, создавшее файл.

        Returns:
            bool: True если ExifTool доступен, False если не найден
        """
        try:
            subprocess.run(["exiftool", "-ver"], capture_output=True, check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def _process_root_files(self):
        """Обрабатывает файлы, оставшиеся в корне исходной папки."""
        device_folders = self._find_device_folders()
        if not device_folders:
            return

        root_files = []
        for file_path in self.src_dir.iterdir():
            if file_path.is_file() and FileTypeDetector.is_media_file(file_path):
                root_files.append(file_path)

        if root_files:
            print(f"  Обрабатываю файлы в корне: {len(root_files)} файлов")
            target_device = device_folders[0]  # Берем первое устройство

            files_moved = 0
            for file_path in root_files:
                dest_folder, app_name = self._determine_correct_destination(
                    file_path, target_device
                )
                dest_path = dest_folder / file_path.name

                if self._move_file(file_path, dest_path):
                    files_moved += 1
                    self.processed_files.append(f"{file_path.name} -> {app_name}")
                    print(f"    ✅ {file_path.name} -> {target_device.name}/{app_name}")

            if files_moved > 0:
                print(f"    ✅ Перемещено из корня: {files_moved} файлов")

    def _determine_correct_destination(self, file_path, device_folder):
        """Определяет правильное назначение для файла."""
        try:
            if self.blackmagic_detector and self.blackmagic_detector.is_blackmagic_file(file_path):
                return device_folder / AppNames.BLACKMAGIC, AppNames.BLACKMAGIC
        except Exception as e:
            print(f"    ⚠️ Ошибка Blackmagic детектора для {file_path.name}: {e}")

        try:
            if self._is_halide_file(file_path):
                return device_folder / AppNames.HALIDE, AppNames.HALIDE
        except Exception as e:
            print(f"    ⚠️ Ошибка Halide детектора для {file_path.name}: {e}")

        try:
            if self._is_moment_file(file_path):
                return device_folder / AppNames.MOMENT, AppNames.MOMENT
        except Exception as e:
            print(f"    ⚠️ Ошибка Moment детектора для {file_path.name}: {e}")

        try:
            if self._is_filmic_file(file_path):
                return device_folder / AppNames.FILMIC, AppNames.FILMIC
        except Exception as e:
            print(f"    ⚠️ Ошибка Filmic детектора для {file_path.name}: {e}")

        # Все остальное - в приложение Фото (корень устройства)
        return device_folder, AppNames.PHOTOS

    def _is_halide_file(self, file_path):
        """Определяет, является ли файл из Halide."""
        # Используем обратную логику - если НЕ из Photos, то может быть из Halide
        try:
            if self.photos_detector:
                is_photos_file = self.photos_detector.is_photos_app_file(file_path)
            else:
                is_photos_file = False
        except Exception as e:
            print(f"    ⚠️ Ошибка Photos детектора для {file_path.name}: {e}")
            # В случае ошибки предполагаем, что это НЕ файл Photos
            is_photos_file = False

        if not is_photos_file:
            # Дополнительные проверки для Halide
            if file_path.suffix.upper() == ".DNG":
                # DNG файлы из Halide обычно имеют парные HEIC
                base_num = FileTypeDetector.get_base_number(file_path.name)
                if base_num:
                    # Проверяем наличие парного HEIC файла в той же папке или соседних
                    parent_folder = file_path.parent
                    base_heic = parent_folder / f"{FilePatterns.IMG_BASE}{base_num}.HEIC"
                    if base_heic.exists():
                        return True
            elif file_path.suffix.upper() == ".HEIC" and FileTypeDetector.is_img_e_file(
                file_path.name
            ):
                # IMG_E*.HEIC без MOV - из Halide
                base_num = FileTypeDetector.get_base_number(file_path.name)
                if base_num:
                    e_mov = file_path.parent / f"{FilePatterns.IMG_E}{base_num}.MOV"
                    if not e_mov.exists():
                        return True
        return False

    def _is_moment_file(self, file_path):
        """Определяет, является ли файл из Moment через EXIF."""
        return False  # Теперь определяется только через EXIF в FileGrouper

    def _is_filmic_file(self, file_path):
        """Определяет, является ли файл из Filmic через EXIF."""
        return False  # Теперь определяется только через EXIF в FileGrouper

    def detect_structure_type(self):
        """Определяет тип структуры входной директории.

        Определяет стратегию обработки на основе содержимого:
        - Режим 1: файлы находятся прямо в корне
        - Режим 2: файлы организованы по подпапкам
        - Смешанный режим: есть и файлы, и подпапки

        Returns:
            tuple: (files_in_root, folders_with_media)
                files_in_root (list): Медиафайлы в корне
                folders_with_media (list): Подпапки с медиафайлами
        """
        files_in_root = []
        folders_with_media = []

        for item in self.src_dir.iterdir():
            if item.is_file():
                if FileTypeDetector.is_media_file(item):
                    files_in_root.append(item)
            elif item.is_dir():
                if self._folder_has_media_files(item):
                    folders_with_media.append(item)

        return files_in_root, folders_with_media

    def organize_single_folder(self, folder_path):
        """Организует файлы в одной конкретной папке.

        Временно переключает рабочую директорию на указанную папку,
        выполняет полный цикл организации, затем восстанавливает
        исходную рабочую директорию.

        Полезно для режима множественных подпапок, когда каждая
        папка обрабатывается отдельно.

        Args:
            folder_path (Path): Папка для организации
        """
        print(f"\n📁 Обрабатываю папку: {folder_path.name}")

        original_src = self.src_dir
        self.src_dir = folder_path

        try:
            self.pipeline.run_full_pipeline(self)
        finally:
            self.src_dir = original_src

    def organize(self):
        """Основной публичный метод для запуска организации файлов.

        Выполняет полный цикл организации:
        1. Проверяет наличие ExifTool
        2. Определяет тип структуры директории
        3. Выбирает соответствующую стратегию обработки
        4. Выполняет организацию с отображением прогресса
        5. Показывает итоговую статистику

        Поддерживаемые режимы:
        - Одна папка с файлами
        - Множество подпапок с файлами
        - Смешанный режим

        Raises:
            SystemExit: Если ExifTool не доступен
        """
        print(f"🔍 Анализирую структуру директории: {self.src_dir}")

        # Проверяем ExifTool
        if not self.check_exiftool():
            print("❌ ExifTool не найден. Установите ExifTool для корректной работы.")
            sys.exit(1)

        # Определяем тип структуры
        files_in_root, folders_with_media = self.detect_structure_type()

        if files_in_root and not folders_with_media:
            # Режим 1: Файлы находятся прямо в целевой папке
            print(f"📋 Режим: Обработка файлов в корневой папке ({len(files_in_root)} файлов)")

            # Стандартная обработка одной папки
            self.pipeline.run_full_pipeline(self)

        elif folders_with_media:
            # Режим 2: Папка содержит подпапки с медиафайлами
            print(f"📂 Режим: Обработка множественных подпапок ({len(folders_with_media)} папок)")

            if files_in_root:
                print(
                    f"⚠️  Найдены файлы в корне ({len(files_in_root)}), "
                    f"они будут обработаны вместе с корневой папкой"
                )

            # Обрабатываем каждую подпапку отдельно
            for folder in folders_with_media:
                self.organize_single_folder(folder)

            # Если есть файлы в корне, обрабатываем и их
            if files_in_root:
                print(f"\n📁 Обрабатываю корневую папку: {self.src_dir.name}")
                self.pipeline.run_full_pipeline(self)

        else:
            print("⚠️  В указанной директории не найдено медиафайлов для обработки")
            return

        # Выводим статистику
        self.print_summary()

    def _find_folders_by_keyword(self, keyword):
        """Находит папки по ключевому слову."""
        return [
            item
            for item in self.src_dir.iterdir()
            if item.is_dir() and keyword.lower() in item.name.lower()
        ]

    def _find_device_folders(self):
        """Находит папки устройств Apple."""
        return [
            item
            for item in self.src_dir.iterdir()
            if item.is_dir() and item.name.startswith(FilePatterns.APPLE_PREFIX)
        ]

    def _rename_folder(self, folder, new_name):
        """Переименовывает папку."""
        new_path = folder.parent / new_name
        try:
            folder.rename(new_path)
            print(f"  ✅ {folder.name} -> {new_name}")
            self.moved_folders.append(f"{folder.name} -> {new_name}")
        except Exception as e:
            print(f"  ❌ Ошибка переименования {folder.name}: {e}")

    def _folder_has_media_files(self, folder):
        """Проверяет, содержит ли папка медиафайлы.

        Рекурсивно просматривает папку и все ее подпапки
        в поисках любых файлов с поддерживаемыми расширениями.

        Args:
            folder (Path): Папка для проверки

        Returns:
            bool: True если найден хотя бы один медиафайл
        """
        for file_path in folder.rglob("*"):
            if file_path.is_file() and FileTypeDetector.is_media_file(file_path):
                return True
        return False

    def print_summary(self):
        """Отображает детальную сводку по выполненной организации.

        Выводит статистику по:
        - Переименованным папкам
        - Перемещенным файлам с указанием назначения
        - Общем результате работы

        Полезно для контроля результатов и отладки.
        """
        print("\n" + "=" * 50)
        print("СВОДКА ОРГАНИЗАЦИИ")
        print("=" * 50)

        if self.moved_folders:
            print("Переименованные папки:")
            for move in self.moved_folders:
                print(f"  📁 {move}")

        if self.processed_files:
            print(f"\nПеремещенные файлы ({len(self.processed_files)}):")
            for file_info in self.processed_files:
                print(f"  📄 {file_info}")

        print("\n🎉 Организация завершена успешно!")
        print("Структура файлов оптимизирована по устройствам и приложениям.")
