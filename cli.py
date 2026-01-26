import os
import re
import asyncio
import subprocess
import sys
import hashlib
import time
import json
import shutil
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from googletrans import Translator

# Глобальные настройки
ROOT_DIR = r"C:\Apps\Extreme\tweaks"
BACKUP_DIR = None

# Инициализация переводчика
translator = Translator()

# Слова, которые не нужно переводить (регистронезависимо)
PROTECTED_WORDS = {'ram', 'bios', 'nvidia', 'amd', 'hdcp', 'khz', 'cpu', 'gpu', 'ssd', 'hdd', 'cop',
                  'usb', 'lan', 'wifi', 'bluetooth', 'dns', 'ip', 'tcp', 'udp', 'vpn', 'kbdqs', 'mpo',
                  'windows', 'microsoft', 'directx', 'opengl', 'dx', 'vulkan', 'hz', 'sense', 'uvm'}

# ============================================================================
# 1. Функции для конвертации .reg файлов в .bat
# ============================================================================

def convert_reg_to_bat(root_dir, reg_convert_exe_path):
    """Рекурсивно конвертирует все .reg файлы в .bat во всех папках и подпапках"""
    
    if not os.path.exists(reg_convert_exe_path):
        print(f"❌ Ошибка: Файл {reg_convert_exe_path} не найден!")
        return 0, 0
    
    if not os.path.exists(root_dir):
        print(f"❌ Ошибка: Директория {root_dir} не существует!")
        return 0, 0
    
    converted_count = 0
    error_count = 0
    
    print(f"🔍 Начинаем поиск .reg файлов в: {root_dir}")
    print("=" * 50)
    
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith('.reg'):
                reg_file_path = os.path.join(root, file)
                bat_file_path = os.path.splitext(reg_file_path)[0] + '.bat'
                
                print(f"📄 Найден .reg файл: {reg_file_path}")
                
                try:
                    cmd = [
                        reg_convert_exe_path,
                        f"/S={reg_file_path}",
                        "/O=BAT",
                        f"/T={bat_file_path}"
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
                    
                    if result.returncode == 0:
                        print(f"✓ Успешно сконвертирован: {bat_file_path}")
                        converted_count += 1
                    else:
                        print(f"✗ Ошибка при конвертации {reg_file_path}:")
                        if result.stdout:
                            print(f"  stdout: {result.stdout}")
                        if result.stderr:
                            print(f"  stderr: {result.stderr}")
                        error_count += 1
                        
                except Exception as e:
                    print(f"✗ Исключение при конвертации {reg_file_path}: {e}")
                    error_count += 1
    
    return converted_count, error_count

# ============================================================================
# 2. Функции для переименования файлов и папок
# ============================================================================

def remove_numbers_and_points_from_start(name):
    """Удаляет цифры и точки в начале имени файла/папки"""
    base_name, ext = os.path.splitext(name)
    new_base_name = re.sub(r'^[.\d]+', '', base_name)
    return new_base_name + ext

def clean_filename(name):
    """Удаляет лишние пробелы и скобки в начале имени файла/папки"""
    base_name, ext = os.path.splitext(name)
    new_base_name = re.sub(r'^[\s\)]+', '', base_name)
    new_base_name = re.sub(r'^\)\s+', '', new_base_name)
    return new_base_name + ext

def process_rename_folder(folder, mode='both'):
    """
    Рекурсивно обрабатывает папку, переименовывая файлы и папки
    mode: 'numbers' - удаляет цифры и точки, 'spaces' - удаляет пробелы и скобки, 'both' - оба режима
    """
    processed_files = 0
    processed_dirs = 0
    removed_empty_dirs = 0
    
    for root, dirs, files in os.walk(folder, topdown=False):
        # Обработка файлов
        for filename in files:
            old_path = os.path.join(root, filename)
            
            if mode in ['numbers', 'both']:
                new_filename = remove_numbers_and_points_from_start(filename)
            elif mode == 'spaces':
                new_filename = clean_filename(filename)
            else:
                new_filename = filename
            
            if mode == 'both':
                new_filename = clean_filename(new_filename)
            
            if new_filename != filename:
                new_path = os.path.join(root, new_filename)
                try:
                    os.rename(old_path, new_path)
                    print(f"✅ Переименован файл: {filename} → {new_filename}")
                    processed_files += 1
                except Exception as e:
                    print(f"❌ Не удалось переименовать файл {filename}: {e}")

        # Обработка папок
        for dirname in dirs:
            old_dir_path = os.path.join(root, dirname)
            
            if mode in ['numbers', 'both']:
                new_dir_name = remove_numbers_and_points_from_start(dirname)
            elif mode == 'spaces':
                new_dir_name = clean_filename(dirname)
            else:
                new_dir_name = dirname
            
            if mode == 'both':
                new_dir_name = clean_filename(new_dir_name)
            
            if new_dir_name != dirname:
                new_dir_path = os.path.join(root, new_dir_name)
                try:
                    os.rename(old_dir_path, new_dir_path)
                    print(f"✅ Переименована папка: {dirname} → {new_dir_name}")
                    processed_dirs += 1
                except Exception as e:
                    print(f"❌ Не удалось переименовать папку {dirname}: {e}")

        # Проверка и удаление пустых папок
        current_dir = root
        if current_dir != folder:
            try:
                if not os.listdir(current_dir):
                    os.rmdir(current_dir)
                    print(f"🗑️  Удалена пустая папка: {os.path.basename(current_dir)}")
                    removed_empty_dirs += 1
            except Exception as e:
                print(f"⚠️  Не удалось удалить папку {os.path.basename(current_dir)}: {e}")
    
    return processed_files, processed_dirs, removed_empty_dirs

# ============================================================================
# 3. Функции для быстрой очистки файлов
# ============================================================================

def quick_clean(root_dir):
    """Быстрая очистка файлов с неразрешенными расширениями"""
    allowed_extensions = ['.bat', '.cmd', '.reg', '.pow', '.py', '.nip', '.ps1']
    
    deleted_count = 0
    error_count = 0
    
    print(f"🧹 Начинаю быструю очистку в: {root_dir}")
    print("=" * 50)
    
    for root, dirs, files in os.walk(root_dir):
        for filename in files:
            filepath = os.path.join(root, filename)
            _, ext = os.path.splitext(filename)
            ext = ext.lower()
            
            if ext not in allowed_extensions:
                try:
                    os.remove(filepath)
                    print(f"🗑️  Удален: {filename}")
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ Ошибка удаления {filename}: {e}")
                    error_count += 1
    
    return deleted_count, error_count

# ============================================================================
# 4. Функции для удаления команд из .bat и .cmd файлов
# ============================================================================

def remove_commands_from_batch_files(root_dir):
    """Удаляет команды pause, exit, shutdown из всех .bat и .cmd файлов"""
    
    commands_to_remove = ['pause', 'exit', 'shutdown']
    pattern = re.compile(r'^\s*(pause|exit|shutdown)\b', re.IGNORECASE | re.MULTILINE)
    
    processed_count = 0
    modified_count = 0
    error_count = 0
    
    print(f"🔍 Ищу .bat и .cmd файлы в: {root_dir}")
    print("=" * 50)
    
    for root, dirs, files in os.walk(root_dir):
        for filename in files:
            if filename.lower().endswith(('.bat', '.cmd')):
                filepath = os.path.join(root, filename)
                processed_count += 1
                
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    original_content = content
                    
                    # Удаляем команды
                    content = pattern.sub('', content)
                    
                    # Удаляем пустые строки, которые могли образоваться
                    lines = content.splitlines()
                    cleaned_lines = []
                    for line in lines:
                        stripped_line = line.strip()
                        if stripped_line:  # Не пустая строка
                            cleaned_lines.append(line)
                    
                    content = '\n'.join(cleaned_lines)
                    
                    if content != original_content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"✂️  Очищен: {filename}")
                        modified_count += 1
                        
                except Exception as e:
                    print(f"❌ Ошибка обработки {filename}: {e}")
                    error_count += 1
    
    print("=" * 50)
    print(f"📊 Обработано файлов: {processed_count}")
    print(f"✂️  Изменено файлов: {modified_count}")
    print(f"❌ Ошибок: {error_count}")
    
    return processed_count, modified_count, error_count

# ============================================================================
# 5. Функции для перевода имен файлов
# ============================================================================

def should_translate(name):
    """Проверяет, нужно ли переводить имя"""
    # Если имя уже содержит русские буквы, не переводим
    if re.search(r'[а-яА-Я]', name):
        return False
    
    # Если имя полностью в верхнем регистре (аббревиатура), не переводим
    if name.isupper():
        return False
    
    # Разделяем имя и расширение
    name_without_ext, ext = os.path.splitext(name)
    
    # Разбиваем на слова для проверки
    words = re.split(r'[_\-\s\.]', name_without_ext)
    
    # Если все слова капсом, не переводим
    if all(word.isupper() for word in words if word):
        return False
    
    # Если все слова в защищенном списке, не переводим
    if all(word.lower() in PROTECTED_WORDS for word in words if word and not word.isupper()):
        return False
    
    return True

async def translate_name_async(name):
    """Переводит название файла целиком (асинхронная версия)"""
    try:
        # Разделяем имя и расширение
        name_without_ext, ext = os.path.splitext(name)
        
        # Переводим название целиком
        translation = await translator.translate(name_without_ext, dest='ru')
        
        # Получаем переведенный текст
        translated_text = translation.text
        
        # Заменяем проблемные символы
        translated_text = translated_text.replace('_', ' ')
        
        # Обработка кавычек и других символов
        translated_text = translated_text.replace('"', '').replace("'", "")
        
        # Удаляем лишние пробелы
        translated_text = ' '.join(translated_text.split())
        
        # Возвращаем с оригинальным расширением
        return translated_text + ext
        
    except Exception as e:
        print(f"Ошибка перевода '{name}': {e}")
        return name

async def process_translation():
    """Асинхронно обрабатывает все файлы для перевода"""
    tasks = []
    
    # Собираем все задачи для перевода
    for root, dirs, files in os.walk(ROOT_DIR):
        for file in files:
            # Пропускаем .pow и .nip файлы
            if file.lower().endswith('.pow'):
                continue

            if file.lower().endswith('.nip'):
                continue
            
            # Проверяем, нужно ли переводить
            if not should_translate(file):
                continue
            
            tasks.append((root, file))
    
    # Обрабатываем задачи группами для избежания перегрузки API
    batch_size = 10
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i+batch_size]
        
        for root, file in batch:
            try:
                new_file_name = await translate_name_async(file)
                if new_file_name != file:
                    old_path = os.path.join(root, file)
                    new_path = os.path.join(root, new_file_name)
                    
                    # Проверяем, существует ли уже файл с таким именем
                    if os.path.exists(new_path):
                        base, ext = os.path.splitext(new_file_name)
                        counter = 1
                        while os.path.exists(new_path):
                            new_file_name = f"{base}_{counter}{ext}"
                            new_path = os.path.join(root, new_file_name)
                            counter += 1
                    
                    os.rename(old_path, new_path)
                    print(f"Переименовано: {file} -> {new_file_name}")
                    
            except Exception as e:
                print(f"Ошибка при обработке файла {file}: {e}")

# ============================================================================
# 6. Функции для удаления дубликатов
# ============================================================================

class DuplicateFileRemover:
    def __init__(self, root_paths, output_dir=None, hash_method='md5'):
        """Инициализация класса для поиска и удаления дубликатов"""
        self.root_paths = [Path(p) for p in root_paths]
        self.output_dir = Path(output_dir) if output_dir else None
        self.hash_method = hash_method
        
        # Статистика
        self.stats = {
            'total_files': 0,
            'duplicate_files': 0,
            'duplicate_size': 0,
            'deleted_files': 0,
            'moved_files': 0,
            'errors': 0,
            'processing_time': 0
        }
        
        # Словарь для хранения хэшей
        self.hash_dict = defaultdict(list)
        
        # Расширения, которые нужно проверять (если None - все файлы)
        self.extensions_to_check = None
        
        # Минимальный размер файла для проверки (в байтах)
        self.min_file_size = 0
        
        # Максимальный размер файла для проверки (в байтах)
        self.max_file_size = 1024 * 1024 * 1024  # 1 ГБ
        
        # Папки для исключения
        self.exclude_dirs = {'.git', '.svn', '.idea', '__pycache__', 'node_modules'}
        
        # Создаем папку для логов
        self.log_dir = Path('duplicate_cleanup_logs')
        self.log_dir.mkdir(exist_ok=True)
        
        # Имя лог-файла с временной меткой
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = self.log_dir / f'duplicate_cleanup_{timestamp}.log'
    
    def log_message(self, message, level='INFO'):
        """Запись сообщения в лог-файл и вывод в консоль"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
        
        # Выводим в консоль
        if level == 'ERROR':
            print(f"❌ {message}")
        elif level == 'WARNING':
            print(f"⚠️  {message}")
        elif level == 'INFO':
            print(f"ℹ️  {message}")
        elif level == 'SUCCESS':
            print(f"✅ {message}")
    
    def calculate_file_hash(self, filepath, chunk_size=8192):
        """Вычисляет хэш файла"""
        try:
            if self.hash_method == 'md5':
                hash_func = hashlib.md5()
            elif self.hash_method == 'sha1':
                hash_func = hashlib.sha1()
            elif self.hash_method == 'sha256':
                hash_func = hashlib.sha256()
            else:
                raise ValueError(f"Неподдерживаемый метод хэширования: {self.hash_method}")
            
            with open(filepath, 'rb') as f:
                while chunk := f.read(chunk_size):
                    hash_func.update(chunk)
            
            return hash_func.hexdigest()
        except Exception as e:
            self.log_message(f"Ошибка при вычислении хэша файла {filepath}: {e}", 'ERROR')
            return None
    
    def get_file_info(self, filepath):
        """Получает информацию о файле"""
        try:
            stat = filepath.stat()
            return {
                'path': str(filepath),
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'created': stat.st_ctime
            }
        except Exception as e:
            self.log_message(f"Ошибка при получении информации о файле {filepath}: {e}", 'ERROR')
            return None
    
    def find_duplicates(self):
        """Находит все дубликаты файлов"""
        self.log_message("🔍 Начинаю поиск дубликатов файлов...")
        
        start_time = time.time()
        
        # Сначала собираем информацию о всех файлах
        all_files = []
        for root_path in self.root_paths:
            if not root_path.exists():
                self.log_message(f"Папка не существует: {root_path}", 'WARNING')
                continue
            
            for item in root_path.rglob('*'):
                if item.is_file():
                    # Проверяем исключения
                    if any(exclude in str(item) for exclude in self.exclude_dirs):
                        continue
                    
                    # Проверяем расширение
                    if self.extensions_to_check and item.suffix.lower() not in self.extensions_to_check:
                        continue
                    
                    # Получаем информацию о файле
                    file_info = self.get_file_info(item)
                    if file_info:
                        all_files.append((item, file_info))
        
        self.stats['total_files'] = len(all_files)
        self.log_message(f"Найдено файлов для проверки: {self.stats['total_files']}")
        
        # Группируем файлы по размеру (быстрая предварительная проверка)
        size_dict = defaultdict(list)
        for filepath, file_info in all_files:
            # Пропускаем файлы, не соответствующие ограничениям по размеру
            if file_info['size'] < self.min_file_size or file_info['size'] > self.max_file_size:
                continue
            
            size_dict[file_info['size']].append((filepath, file_info))
        
        # Проверяем файлы с одинаковым размером
        duplicate_groups = []
        
        for size, files in size_dict.items():
            if len(files) > 1:
                # Группируем по хэшу
                hash_groups = defaultdict(list)
                
                for filepath, file_info in files:
                    file_hash = self.calculate_file_hash(filepath)
                    if file_hash:
                        hash_groups[file_hash].append((filepath, file_info))
                
                # Добавляем группы с дубликатами
                for file_hash, file_list in hash_groups.items():
                    if len(file_list) > 1:
                        duplicate_groups.append({
                            'hash': file_hash,
                            'size': size,
                            'files': file_list
                        })
        
        # Сортируем группы по размеру (начиная с самых больших файлов)
        duplicate_groups.sort(key=lambda x: x['size'], reverse=True)
        
        end_time = time.time()
        self.stats['processing_time'] = end_time - start_time
        
        self.stats['duplicate_files'] = sum(len(group['files']) - 1 for group in duplicate_groups)
        self.stats['duplicate_size'] = sum(group['size'] * (len(group['files']) - 1) for group in duplicate_groups)
        
        self.log_message(f"Найдено групп дубликатов: {len(duplicate_groups)}")
        self.log_message(f"Обнаружено дубликатов: {self.stats['duplicate_files']} файлов")
        self.log_message(f"Дублирующий объем: {self.format_size(self.stats['duplicate_size'])}")
        self.log_message(f"Время поиска: {self.stats['processing_time']:.2f} секунд")
        
        return duplicate_groups
    
    def format_size(self, size_bytes):
        """Форматирует размер в читаемом виде"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def save_backup(self, filepath):
        """Сохраняет резервную копию файла"""
        if not self.output_dir:
            return None
        
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            # Создаем относительный путь для сохранения структуры
            backup_path = self.output_dir / filepath.relative_to(self.root_paths[0])
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(filepath, backup_path)
            self.stats['moved_files'] += 1
            
            return backup_path
        except Exception as e:
            self.log_message(f"Ошибка при создании резервной копии {filepath}: {e}", 'ERROR')
            return None
    
    def delete_duplicates(self, duplicate_groups, keep_strategy='oldest'):
        """Удаляет дубликаты файлов"""
        self.log_message(f"\n🗑️  Начинаю удаление дубликатов (стратегия: {keep_strategy})...")
        
        deleted_files = []
        
        for i, group in enumerate(duplicate_groups, 1):
            self.log_message(f"\nГруппа {i}/{len(duplicate_groups)}: {len(group['files'])} файлов, "
                           f"размер: {self.format_size(group['size'])}")
            
            # Определяем, какой файл оставить
            if keep_strategy == 'oldest':
                sorted_files = sorted(group['files'], key=lambda x: x[1]['created'])
            elif keep_strategy == 'newest':
                sorted_files = sorted(group['files'], key=lambda x: x[1]['modified'], reverse=True)
            elif keep_strategy == 'shortest_path':
                sorted_files = sorted(group['files'], key=lambda x: len(str(x[0])))
            elif keep_strategy == 'longest_path':
                sorted_files = sorted(group['files'], key=lambda x: len(str(x[0])), reverse=True)
            else:
                sorted_files = sorted(group['files'], key=lambda x: x[1]['created'])
            
            # Первый файл в отсортированном списке оставляем
            keep_file = sorted_files[0]
            files_to_delete = sorted_files[1:]
            
            self.log_message(f"Сохраняю файл: {keep_file[0]}")
            
            # Удаляем дубликаты
            for filepath, file_info in files_to_delete:
                try:
                    backup_path = self.save_backup(filepath)
                    
                    os.remove(filepath)
                    
                    deleted_files.append({
                        'original_path': str(filepath),
                        'backup_path': str(backup_path) if backup_path else None,
                        'size': file_info['size'],
                        'hash': group['hash']
                    })
                    
                    self.stats['deleted_files'] += 1
                    self.log_message(f"Удален: {filepath}")
                    
                except Exception as e:
                    self.stats['errors'] += 1
                    self.log_message(f"Ошибка при удалении {filepath}: {e}", 'ERROR')
        
        self.save_deletion_report(deleted_files)
        
        return deleted_files
    
    def save_deletion_report(self, deleted_files):
        """Сохраняет отчет об удаленных файлах"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats,
            'settings': {
                'root_paths': [str(p) for p in self.root_paths],
                'hash_method': self.hash_method,
                'output_dir': str(self.output_dir) if self.output_dir else None
            },
            'deleted_files': deleted_files
        }
        
        report_file = self.log_dir / f'deletion_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.log_message(f"Отчет сохранен: {report_file}")
    
    def print_stats(self):
        """Выводит статистику"""
        print("\n" + "="*70)
        print("📊 СТАТИСТИКА ОБРАБОТКИ ДУБЛИКАТОВ")
        print("="*70)
        print(f"📁 Всего файлов проверено: {self.stats['total_files']}")
        print(f"🔍 Найдено дубликатов: {self.stats['duplicate_files']} файлов")
        print(f"💾 Дублирующий объем: {self.format_size(self.stats['duplicate_size'])}")
        print(f"🗑️  Удалено файлов: {self.stats['deleted_files']}")
        print(f"📦 Файлов в резервной копии: {self.stats['moved_files']}")
        print(f"❌ Ошибок: {self.stats['errors']}")
        print(f"⏱️  Время обработки: {self.stats['processing_time']:.2f} сек")
        print(f"📝 Лог файл: {self.log_file}")

# ============================================================================
# 7. Главная функция с меню выбора
# ============================================================================

def main():
    """Основная функция с меню выбора"""
    
    global ROOT_DIR, BACKUP_DIR
    
    print("=" * 70)
    print("🛠️  КОМПЛЕКСНЫЙ ОБРАБОТЧИК ФАЙЛОВ")
    print("=" * 70)
    print(f"📁 Текущая рабочая папка: {ROOT_DIR}")
    print()
    
    # Проверка существования папки
    if not os.path.exists(ROOT_DIR):
        print(f"❌ Папка {ROOT_DIR} не существует!")
        print("Введите корректный путь:")
        new_path = input("> ").strip()
        if os.path.exists(new_path):
            ROOT_DIR = new_path
        else:
            print("❌ Папка не существует. Завершение программы.")
            return
    
    while True:
        print("\n" + "="*70)
        print("📋 ГЛАВНОЕ МЕНЮ")
        print("="*70)
        print("1. 🚀 ПОЛНАЯ ОБРАБОТКА (все операции последовательно)")
        print("2. 🔄 Конвертация .reg файлов в .bat")
        print("3. 📝 Переименование файлов и папок")
        print("4. 🧹 Быстрая очистка файлов")
        print("5. ✂️  Удаление pause/exit/shutdown из .bat/.cmd файлов")
        print("6. 🌐 Перевод имен файлов")
        print("7. 🔍 Поиск и удаление дубликатов")
        print("8. ⚙️  Настройки")
        print("0. ❌ Выход")
        print("="*70)
        
        try:
            choice = input("\nВыберите операцию (0-8): ").strip()
            
            if choice == '0':
                print("Выход из программы.")
                break
            
            elif choice == '1':
                print("\n" + "="*70)
                print("🚀 ЗАПУСК ПОЛНОЙ ОБРАБОТКИ")
                print("="*70)
                print("Будет выполнено:")
                print("1. 🔄 Конвертация .reg → .bat")
                print("2. 📝 Переименование файлов и папок")
                print("3. 🧹 Быстрая очистка файлов")
                print("4. ✂️  Удаление pause/exit/shutdown из .bat/.cmd")
                print("5. 🌐 Перевод имен файлов")
                print("="*70)
                
                confirm = input("\nВы уверены? Это может занять время! (y/n): ").strip().lower()
                if confirm not in ['y', 'yes', 'д', 'да']:
                    print("Отменено.")
                    continue
                
                # Шаг 1: Конвертация
                print("\n" + "="*60)
                print("ШАГ 1: 🔄 КОНВЕРТАЦИЯ .REG ФАЙЛОВ В .BAT")
                print("="*60)
                reg_convert_path = "RegConvert.exe"
                if os.path.exists(reg_convert_path):
                    converted, reg_errors = convert_reg_to_bat(ROOT_DIR, reg_convert_path)
                    print(f"✓ Сконвертировано: {converted}, ошибок: {reg_errors}")
                else:
                    print("⚠️  RegConvert.exe не найден, пропускаем этот шаг")
                    converted, reg_errors = 0, 0
                
                # Шаг 2: Переименование
                print("\n" + "="*60)
                print("ШАГ 2: 📝 ПЕРЕИМЕНОВАНИЕ ФАЙЛОВ И ПАПОК")
                print("="*60)
                files, dirs, empty = process_rename_folder(ROOT_DIR, 'both')
                print(f"✓ Файлов: {files}, папок: {dirs}, пустых папок: {empty}")
                
                # Шаг 3: Быстрая очистка
                print("\n" + "="*60)
                print("ШАГ 3: 🧹 БЫСТРАЯ ОЧИСТКА ФАЙЛОВ")
                print("="*60)
                deleted, clean_errors = quick_clean(ROOT_DIR)
                print(f"✓ Удалено: {deleted}, ошибок: {clean_errors}")
                
                # Шаг 4: Удаление команд
                print("\n" + "="*60)
                print("ШАГ 4: ✂️  УДАЛЕНИЕ PAUSE/EXIT/SHUTDOWN")
                print("="*60)
                processed, modified, cmd_errors = remove_commands_from_batch_files(ROOT_DIR)
                print(f"✓ Обработано: {processed}, изменено: {modified}, ошибок: {cmd_errors}")
                
                # Шаг 5: Перевод
                print("\n" + "="*60)
                print("ШАГ 5: 🌐 ПЕРЕВОД ИМЕН ФАЙЛОВ")
                print("="*60)
                print("Запуск перевода...")
                asyncio.run(process_translation())
                
                print("\n" + "="*70)
                print("✅ ПОЛНАЯ ОБРАБОТКА ЗАВЕРШЕНА!")
                print("="*70)
                print("📊 ИТОГОВАЯ СТАТИСТИКА:")
                print(f"   🔄 Сконвертировано .reg файлов: {converted}")
                print(f"   📝 Переименовано файлов: {files}, папок: {dirs}")
                print(f"   🗑️  Удалено пустых папок: {empty}")
                print(f"   🧹 Удалено лишних файлов: {deleted}")
                print(f"   ✂️  Очищено .bat/.cmd файлов: {modified}")
                print(f"   ⚠️  Всего ошибок: {reg_errors + clean_errors + cmd_errors}")
                print("="*70)
            
            elif choice == '2':
                print("\n🔄 КОНВЕРТАЦИЯ .REG В .BAT")
                print("-" * 40)
                reg_convert_path = input("Введите путь к RegConvert.exe (Enter для поиска в текущей папке): ").strip()
                if not reg_convert_path:
                    reg_convert_path = "RegConvert.exe"
                    print(f"Используется: {reg_convert_path}")
                
                confirm = input("Вы уверены, что хотите начать конвертацию? (y/n): ").strip().lower()
                if confirm in ['y', 'yes', 'д', 'да']:
                    converted, errors = convert_reg_to_bat(ROOT_DIR, reg_convert_path)
                    print("=" * 50)
                    print(f"✅ Конвертация завершена!")
                    print(f"📊 Статистика:")
                    print(f"   ✓ Успешно сконвертировано: {converted}")
                    print(f"   ✗ Ошибок: {errors}")
                else:
                    print("Конвертация отменена.")
            
            elif choice == '3':
                print("\n📝 ПЕРЕИМЕНОВАНИЕ ФАЙЛОВ И ПАПОК")
                print("-" * 40)
                print("1. Удалить цифры и точки в начале")
                print("2. Удалить пробелы и скобки в начале")
                print("3. Оба режима (цифры+пробелы)")
                
                rename_choice = input("Выберите режим (1-3): ").strip()
                
                if rename_choice == '1':
                    mode = 'numbers'
                elif rename_choice == '2':
                    mode = 'spaces'
                elif rename_choice == '3':
                    mode = 'both'
                else:
                    print("❌ Неверный выбор, отмена.")
                    continue
                
                confirm = input(f"Вы уверены, что хотите начать переименование ({mode})? (y/n): ").strip().lower()
                if confirm in ['y', 'yes', 'д', 'да']:
                    print(f"\n🔄 Начинаю переименование в режиме '{mode}'...")
                    print("=" * 50)
                    files, dirs, empty = process_rename_folder(ROOT_DIR, mode)
                    print("=" * 50)
                    print(f"✅ Переименование завершено!")
                    print(f"📊 Статистика:")
                    print(f"   📄 Файлов переименовано: {files}")
                    print(f"   📁 Папок переименовано: {dirs}")
                    print(f"   🗑️  Пустых папок удалено: {empty}")
                else:
                    print("Переименование отменено.")
            
            elif choice == '4':
                print("\n🧹 БЫСТРАЯ ОЧИСТКА")
                print("-" * 40)
                print("Будут удалены все файлы кроме:")
                print("  .bat, .cmd, .reg, .pow, .py, .nip, .ps1")
                print()
                
                confirm = input("Вы уверены? Это действие необратимо! (y/n): ").strip().lower()
                if confirm in ['y', 'yes', 'д', 'да']:
                    deleted, errors = quick_clean(ROOT_DIR)
                    print("=" * 50)
                    print(f"✅ Очистка завершена!")
                    print(f"📊 Статистика:")
                    print(f"   🗑️  Файлов удалено: {deleted}")
                    print(f"   ❌ Ошибок: {errors}")
                else:
                    print("Очистка отменена.")
            
            elif choice == '5':
                print("\n✂️  УДАЛЕНИЕ PAUSE/EXIT/SHUTDOWN")
                print("-" * 40)
                print("Будут удалены команды из всех .bat и .cmd файлов:")
                print("  pause, exit, shutdown")
                print()
                
                confirm = input("Вы уверены? (y/n): ").strip().lower()
                if confirm in ['y', 'yes', 'д', 'да']:
                    processed, modified, errors = remove_commands_from_batch_files(ROOT_DIR)
                    print("=" * 50)
                    print(f"✅ Очистка завершена!")
                    print(f"📊 Статистика:")
                    print(f"   📄 Обработано файлов: {processed}")
                    print(f"   ✂️  Изменено файлов: {modified}")
                    print(f"   ❌ Ошибок: {errors}")
                else:
                    print("Очистка отменена.")
            
            elif choice == '6':
                print("\n🌐 ПЕРЕВОД ИМЕН ФАЙЛОВ")
                print("-" * 40)
                print("Будут переведены имена файлов с английского на русский")
                print("Пропускаются файлы:")
                print("  • Уже содержащие русские буквы")
                print("  • Аббревиатуры (все буквы заглавные)")
                print("  • Файлы с защищенными словами (RAM, BIOS и т.д.)")
                print()
                
                confirm = input("Начать перевод? (y/n): ").strip().lower()
                if confirm in ['y', 'yes', 'д', 'да']:
                    print("🔄 Запуск перевода...")
                    asyncio.run(process_translation())
                    print("✅ Перевод завершен!")
                else:
                    print("Перевод отменен.")
            
            elif choice == '7':
                print("\n🔍 ПОИСК И УДАЛЕНИЕ ДУБЛИКАТОВ")
                print("-" * 40)
                
                # Создаем объект для удаления дубликатов
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_dir = Path(f"backup_duplicates_{timestamp}")
                
                remover = DuplicateFileRemover(
                    root_paths=[ROOT_DIR],
                    output_dir=backup_dir,
                    hash_method='md5'
                )
                
                # Находим дубликаты
                duplicates = remover.find_duplicates()
                
                if not duplicates:
                    print("✅ Дубликаты не найдены!")
                    continue
                
                print(f"\n🎯 Найдено {len(duplicates)} групп дубликатов")
                print(f"📊 Всего дубликатов для удаления: {remover.stats['duplicate_files']} файлов")
                print(f"💾 Будет освобождено: {remover.format_size(remover.stats['duplicate_size'])}")
                
                # Выбор стратегии
                print("\n📋 СТРАТЕГИИ СОХРАНЕНИЯ:")
                print("  1. oldest - оставить самый старый файл")
                print("  2. newest - оставить самый новый файл")
                print("  3. shortest_path - оставить файл с самым коротким путем")
                print("  4. longest_path - оставить файл с самым длинным путем")
                
                strategy_choice = input("Выберите стратегию (1-4, по умолчанию 1): ").strip()
                
                strategies = {
                    '1': 'oldest',
                    '2': 'newest',
                    '3': 'shortest_path',
                    '4': 'longest_path'
                }
                
                strategy = strategies.get(strategy_choice, 'oldest')
                
                # Подтверждение
                confirm = input(f"\n⚠️  Вы уверены, что хотите удалить {remover.stats['duplicate_files']} "
                              f"файлов? (y/n): ").strip().lower()
                
                if confirm in ['y', 'yes', 'д', 'да']:
                    deleted = remover.delete_duplicates(duplicates, strategy)
                    remover.print_stats()
                else:
                    print("Удаление отменено.")
            
            elif choice == '8':
                print("\n⚙️  НАСТРОЙКИ")
                print("-" * 40)
                print(f"1. 📁 Текущая рабочая папка: {ROOT_DIR}")
                print("2. ⬅️  Вернуться в главное меню")
                
                setting_choice = input("Выберите опцию (1-2): ").strip()
                
                if setting_choice == '1':
                    new_path = input(f"Введите новый путь (Enter для отмены): ").strip()
                    if new_path and os.path.exists(new_path):
                        ROOT_DIR = new_path
                        print(f"✅ Новый путь установлен: {ROOT_DIR}")
                    else:
                        print("❌ Папка не существует или ввод отменен.")
            
            else:
                print("❌ Неверный выбор. Попробуйте снова.")
        
        except KeyboardInterrupt:
            print("\n\nПрограмма прервана пользователем.")
            break
        except Exception as e:
            print(f"❌ Произошла ошибка: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nПрограмма завершена.")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        input("Нажмите Enter для выхода...")