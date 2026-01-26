import os
import re
import asyncio
import subprocess
import sys
import hashlib
import time
import json
import shutil
import threading
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from googletrans import Translator

import customtkinter as ctk
from tkinter import messagebox, filedialog
from CTkMessagebox import CTkMessagebox
from PIL import Image, ImageTk
import tkinter as tk

# Настройка темы
ctk.set_appearance_mode("dark")  # Режимы: "dark", "light", "system"
ctk.set_default_color_theme("blue")  # Темы: "blue", "green", "dark-blue"

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

def convert_reg_to_bat(root_dir, reg_convert_exe_path, progress_callback=None):
    """Рекурсивно конвертирует все .reg файлы в .bat во всех папках и подпапках"""
    
    if not os.path.exists(reg_convert_exe_path):
        return 0, 0, f"❌ Файл {reg_convert_exe_path} не найден!"
    
    if not os.path.exists(root_dir):
        return 0, 0, f"❌ Директория {root_dir} не существует!"
    
    converted_count = 0
    error_count = 0
    messages = []
    
    messages.append(f"🔍 Поиск .reg файлов в: {root_dir}")
    
    reg_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith('.reg'):
                reg_files.append(os.path.join(root, file))
    
    total_files = len(reg_files)
    if progress_callback:
        progress_callback(0, total_files, "Начинаю конвертацию...")
    
    for i, reg_file_path in enumerate(reg_files, 1):
        bat_file_path = os.path.splitext(reg_file_path)[0] + '.bat'
        
        try:
            cmd = [
                reg_convert_exe_path,
                f"/S={reg_file_path}",
                "/O=BAT",
                f"/T={bat_file_path}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                messages.append(f"✓ {os.path.basename(reg_file_path)} → {os.path.basename(bat_file_path)}")
                converted_count += 1
            else:
                messages.append(f"✗ Ошибка: {os.path.basename(reg_file_path)}")
                error_count += 1
                
        except Exception as e:
            messages.append(f"✗ Исключение: {os.path.basename(reg_file_path)} - {str(e)}")
            error_count += 1
        
        if progress_callback:
            progress_callback(i, total_files, f"Обработано: {i}/{total_files}")
    
    return converted_count, error_count, "\n".join(messages)

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

def process_rename_folder(folder, mode='both', progress_callback=None):
    """Рекурсивно обрабатывает папку, переименовывая файлы и папки"""
    processed_files = 0
    processed_dirs = 0
    removed_empty_dirs = 0
    messages = []
    
    all_files = []
    all_dirs = []
    
    for root, dirs, files in os.walk(folder):
        all_files.extend([(root, f) for f in files])
        all_dirs.extend([(root, d) for d in dirs])
    
    total_items = len(all_files) + len(all_dirs)
    if progress_callback:
        progress_callback(0, total_items, "Начинаю переименование...")
    
    current_item = 0
    
    # Сначала собираем все переименования для файлов
    rename_list = []
    for root, filename in all_files:
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
            rename_list.append((old_path, new_path, filename, new_filename))
        
        current_item += 1
        if progress_callback:
            progress_callback(current_item, total_items, f"Файлы: {current_item}/{total_items}")
    
    # Выполняем переименование файлов
    for old_path, new_path, old_name, new_name in rename_list:
        try:
            os.rename(old_path, new_path)
            messages.append(f"📄 {old_name} → {new_name}")
            processed_files += 1
        except Exception as e:
            messages.append(f"❌ {old_name}: {str(e)}")
    
    # Переименование папок (снизу вверх)
    for root, dirs, files in os.walk(folder, topdown=False):
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
                    messages.append(f"📁 {dirname} → {new_dir_name}")
                    processed_dirs += 1
                except Exception as e:
                    messages.append(f"❌ Папка {dirname}: {str(e)}")
    
    return processed_files, processed_dirs, removed_empty_dirs, "\n".join(messages)

# ============================================================================
# 3. Функции для быстрой очистки файлов
# ============================================================================

def quick_clean(root_dir, progress_callback=None):
    """Быстрая очистка файлов с неразрешенными расширениями"""
    allowed_extensions = ['.bat', '.cmd', '.reg', '.pow', '.py', '.nip', '.ps1']
    
    deleted_count = 0
    error_count = 0
    messages = []
    
    files_to_check = []
    for root, dirs, files in os.walk(root_dir):
        for filename in files:
            files_to_check.append((root, filename))
    
    total_files = len(files_to_check)
    if progress_callback:
        progress_callback(0, total_files, "Начинаю очистку...")
    
    for i, (root, filename) in enumerate(files_to_check, 1):
        filepath = os.path.join(root, filename)
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        if ext not in allowed_extensions:
            try:
                os.remove(filepath)
                messages.append(f"🗑️  {filename}")
                deleted_count += 1
            except Exception as e:
                messages.append(f"❌ {filename}: {str(e)}")
                error_count += 1
        
        if progress_callback:
            progress_callback(i, total_files, f"Проверено: {i}/{total_files}")
    
    return deleted_count, error_count, "\n".join(messages)

# ============================================================================
# 4. Функции для удаления команд из .bat и .cmd файлов
# ============================================================================

def remove_commands_from_batch_files(root_dir, progress_callback=None):
    """Удаляет команды pause, exit, shutdown из всех .bat и .cmd файлов"""
    
    commands_to_remove = ['pause', 'exit', 'shutdown']
    pattern = re.compile(r'^\s*(pause|exit|shutdown)\b', re.IGNORECASE | re.MULTILINE)
    
    processed_count = 0
    modified_count = 0
    error_count = 0
    messages = []
    
    batch_files = []
    for root, dirs, files in os.walk(root_dir):
        for filename in files:
            if filename.lower().endswith(('.bat', '.cmd')):
                batch_files.append(os.path.join(root, filename))
    
    total_files = len(batch_files)
    if progress_callback:
        progress_callback(0, total_files, "Начинаю очистку команд...")
    
    for i, filepath in enumerate(batch_files, 1):
        filename = os.path.basename(filepath)
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
                messages.append(f"✂️  {filename}")
                modified_count += 1
                
        except Exception as e:
            messages.append(f"❌ {filename}: {str(e)}")
            error_count += 1
        
        if progress_callback:
            progress_callback(i, total_files, f"Обработано: {i}/{total_files}")
    
    return processed_count, modified_count, error_count, "\n".join(messages)

# ============================================================================
# 5. Функции для перевода имен файлов
# ============================================================================

def should_translate(name):
    """Проверяет, нужно ли переводить имя"""
    if re.search(r'[а-яА-Я]', name):
        return False
    
    if name.isupper():
        return False
    
    name_without_ext, ext = os.path.splitext(name)
    
    words = re.split(r'[_\-\s\.]', name_without_ext)
    
    if all(word.isupper() for word in words if word):
        return False
    
    if all(word.lower() in PROTECTED_WORDS for word in words if word and not word.isupper()):
        return False
    
    return True

async def translate_name_async(name):
    """Переводит название файла целиком (асинхронная версия)"""
    try:
        name_without_ext, ext = os.path.splitext(name)
        translation = await translator.translate(name_without_ext, dest='ru')
        translated_text = translation.text
        translated_text = translated_text.replace('_', ' ')
        translated_text = translated_text.replace('"', '').replace("'", "")
        translated_text = ' '.join(translated_text.split())
        return translated_text + ext
    except Exception as e:
        return name

async def process_translation_async(root_dir, progress_callback=None):
    """Асинхронно обрабатывает все файлы для перевода"""
    tasks = []
    
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(('.pow', '.nip')):
                continue
            if not should_translate(file):
                continue
            tasks.append((root, file))
    
    total_tasks = len(tasks)
    if progress_callback:
        progress_callback(0, total_tasks, "Начинаю перевод...")
    
    messages = []
    batch_size = 5  # Меньший batch size для GUI
    
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i+batch_size]
        
        for root, file in batch:
            try:
                new_file_name = await translate_name_async(file)
                if new_file_name != file:
                    old_path = os.path.join(root, file)
                    new_path = os.path.join(root, new_file_name)
                    
                    if os.path.exists(new_path):
                        base, ext = os.path.splitext(new_file_name)
                        counter = 1
                        while os.path.exists(new_path):
                            new_file_name = f"{base}_{counter}{ext}"
                            new_path = os.path.join(root, new_file_name)
                            counter += 1
                    
                    os.rename(old_path, new_path)
                    messages.append(f"🌐 {file} → {new_file_name}")
                    
            except Exception as e:
                messages.append(f"❌ {file}: {str(e)}")
        
        if progress_callback:
            progress_callback(min(i + batch_size, total_tasks), total_tasks, 
                            f"Переведено: {min(i + batch_size, total_tasks)}/{total_tasks}")
        await asyncio.sleep(0.1)  # Небольшая задержка для обновления GUI
    
    return "\n".join(messages)

# ============================================================================
# 6. Класс для удаления дубликатов
# ============================================================================

class DuplicateFileRemoverGUI:
    def __init__(self, root_paths, output_dir=None):
        self.root_paths = [Path(p) for p in root_paths]
        self.output_dir = Path(output_dir) if output_dir else None
        self.hash_method = 'md5'
        self.stats = {
            'total_files': 0,
            'duplicate_files': 0,
            'duplicate_size': 0,
            'deleted_files': 0,
            'moved_files': 0,
            'errors': 0,
            'processing_time': 0
        }
        self.hash_dict = defaultdict(list)
        self.extensions_to_check = None
        self.min_file_size = 0
        self.max_file_size = 1024 * 1024 * 1024
        self.exclude_dirs = {'.git', '.svn', '.idea', '__pycache__', 'node_modules'}
        self.log_dir = Path('duplicate_cleanup_logs')
        self.log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = self.log_dir / f'duplicate_cleanup_{timestamp}.log'
    
    def log_message(self, message, level='INFO'):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
        return log_entry
    
    def calculate_file_hash(self, filepath):
        try:
            if self.hash_method == 'md5':
                hash_func = hashlib.md5()
            elif self.hash_method == 'sha1':
                hash_func = hashlib.sha1()
            elif self.hash_method == 'sha256':
                hash_func = hashlib.sha256()
            
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192):
                    hash_func.update(chunk)
            
            return hash_func.hexdigest()
        except Exception as e:
            return None
    
    def find_duplicates(self, progress_callback=None):
        start_time = time.time()
        
        all_files = []
        for root_path in self.root_paths:
            if not root_path.exists():
                continue
            
            items = list(root_path.rglob('*'))
            total_items = len(items)
            for i, item in enumerate(items):
                if item.is_file():
                    if any(exclude in str(item) for exclude in self.exclude_dirs):
                        continue
                    if self.extensions_to_check and item.suffix.lower() not in self.extensions_to_check:
                        continue
                    try:
                        stat = item.stat()
                        all_files.append((item, stat.st_size, stat.st_ctime, stat.st_mtime))
                    except:
                        pass
                
                if progress_callback and i % 100 == 0:
                    progress_callback(i, total_items, f"Сканирование: {i}/{total_items}")
        
        self.stats['total_files'] = len(all_files)
        
        size_dict = defaultdict(list)
        for filepath, size, created, modified in all_files:
            if self.min_file_size <= size <= self.max_file_size:
                size_dict[size].append((filepath, size, created, modified))
        
        duplicate_groups = []
        total_size_groups = len([s for s in size_dict if len(size_dict[s]) > 1])
        current_group = 0
        
        for size, files in size_dict.items():
            if len(files) > 1:
                hash_groups = defaultdict(list)
                for filepath, size, created, modified in files:
                    file_hash = self.calculate_file_hash(filepath)
                    if file_hash:
                        hash_groups[file_hash].append((filepath, size, created, modified))
                
                for file_hash, file_list in hash_groups.items():
                    if len(file_list) > 1:
                        duplicate_groups.append({
                            'hash': file_hash,
                            'size': size,
                            'files': file_list
                        })
                
                current_group += 1
                if progress_callback:
                    progress_callback(current_group, total_size_groups, 
                                    f"Проверка хэшей: {current_group}/{total_size_groups}")
        
        duplicate_groups.sort(key=lambda x: x['size'], reverse=True)
        
        end_time = time.time()
        self.stats['processing_time'] = end_time - start_time
        self.stats['duplicate_files'] = sum(len(group['files']) - 1 for group in duplicate_groups)
        self.stats['duplicate_size'] = sum(group['size'] * (len(group['files']) - 1) for group in duplicate_groups)
        
        return duplicate_groups
    
    def format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

# ============================================================================
# 7. Основной класс GUI
# ============================================================================

class FileProcessorApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("🛠️ Комплексный обработчик файлов")
        self.root.geometry("1200x700")
        
        # Центрирование окна
        self.center_window(1200, 700)
        
        self.current_dir = ROOT_DIR
        self.is_processing = False
        self.current_task = None
        
        # Настройка сетки
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        self.create_widgets()
        self.update_dir_label()
        
    def center_window(self, width, height):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
    
    def create_widgets(self):
        # Основной фрейм
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        # Заголовок
        self.title_label = ctk.CTkLabel(
            self.main_frame,
            text="🛠️ КОМПЛЕКСНЫЙ ОБРАБОТЧИК ФАЙЛОВ",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        # Фрейм для информации о папке
        self.dir_frame = ctk.CTkFrame(self.main_frame)
        self.dir_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.dir_frame.grid_columnconfigure(1, weight=1)
        
        self.dir_label = ctk.CTkLabel(self.dir_frame, text="📁 Рабочая папка:", font=ctk.CTkFont(size=14))
        self.dir_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.dir_path_label = ctk.CTkLabel(
            self.dir_frame, 
            text="",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.dir_path_label.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        self.change_dir_btn = ctk.CTkButton(
            self.dir_frame,
            text="Изменить",
            width=100,
            command=self.change_directory
        )
        self.change_dir_btn.grid(row=0, column=2, padx=10, pady=10)
        
        # Фрейм для кнопок операций
        self.operations_frame = ctk.CTkFrame(self.main_frame)
        self.operations_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.operations_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # Кнопки операций
        operations = [
            ("🚀 ПОЛНАЯ ОБРАБОТКА", self.full_process, 0, 0),
            ("🔄 Конвертация REG→BAT", self.convert_reg_to_bat_gui, 0, 1),
            ("📝 Переименование", self.rename_gui, 0, 2),
            ("🧹 Быстрая очистка", self.quick_clean_gui, 0, 3),
            ("✂️ Удаление команд", self.remove_commands_gui, 1, 0),
            ("🌐 Перевод имен", self.translate_gui, 1, 1),
            ("🔍 Поиск дубликатов", self.find_duplicates_gui, 1, 2),
            ("⚙️ Настройки", self.settings_gui, 1, 3)
        ]
        
        for text, command, row, col in operations:
            btn = ctk.CTkButton(
                self.operations_frame,
                text=text,
                command=command,
                height=40,
                font=ctk.CTkFont(size=13)
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
        
        # Фрейм для прогресса
        self.progress_frame = ctk.CTkFrame(self.main_frame)
        self.progress_frame.grid(row=3, column=0, padx=20, pady=(10, 5), sticky="ew")
        self.progress_frame.grid_columnconfigure(0, weight=1)
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Готов к работе", font=ctk.CTkFont(size=12))
        self.progress_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.progress_bar.set(0)
        
        # Фрейм для вывода
        self.output_frame = ctk.CTkFrame(self.main_frame)
        self.output_frame.grid(row=4, column=0, padx=20, pady=10, sticky="nsew")
        self.output_frame.grid_columnconfigure(0, weight=1)
        self.output_frame.grid_rowconfigure(0, weight=1)
        
        self.output_text = ctk.CTkTextbox(
            self.output_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="none"
        )
        self.output_text.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Scrollbar для вывода
        self.output_scrollbar = ctk.CTkScrollbar(self.output_frame, command=self.output_text.yview)
        self.output_scrollbar.grid(row=0, column=1, sticky="ns")
        self.output_text.configure(yscrollcommand=self.output_scrollbar.set)
        
        # Кнопка остановки
        self.stop_btn = ctk.CTkButton(
            self.main_frame,
            text="⏹️ Остановить",
            command=self.stop_processing,
            fg_color="red",
            hover_color="dark red",
            state="disabled"
        )
        self.stop_btn.grid(row=5, column=0, padx=20, pady=(5, 20), sticky="e")
    
    def update_dir_label(self):
        self.dir_path_label.configure(text=self.current_dir)
    
    def change_directory(self):
        if self.is_processing:
            self.show_warning("Дождитесь завершения текущей операции")
            return
        
        dir_path = filedialog.askdirectory(initialdir=self.current_dir)
        if dir_path:
            self.current_dir = dir_path
            self.update_dir_label()
            self.log_output(f"📁 Изменена рабочая папка: {dir_path}")
    
    def log_output(self, message, clear=False):
        if clear:
            self.output_text.delete("1.0", "end")
        
        self.output_text.insert("end", message + "\n")
        self.output_text.see("end")
        self.root.update()
    
    def update_progress(self, value, max_value, message):
        if max_value > 0:
            progress = value / max_value
            self.progress_bar.set(progress)
        self.progress_label.configure(text=message)
        self.root.update()
    
    def set_processing_state(self, processing):
        self.is_processing = processing
        state = "disabled" if processing else "normal"
        
        for child in self.operations_frame.winfo_children():
            if isinstance(child, ctk.CTkButton):
                child.configure(state=state)
        
        self.change_dir_btn.configure(state=state)
        self.stop_btn.configure(state="normal" if processing else "disabled")
    
    def stop_processing(self):
        if self.current_task and self.current_task.is_alive():
            self.current_task.do_run = False
            self.log_output("🛑 Запрошена остановка операции...")
    
    def show_warning(self, message):
        CTkMessagebox(title="Внимание", message=message, icon="warning")
    
    def show_error(self, message):
        CTkMessagebox(title="Ошибка", message=message, icon="cancel")
    
    def show_info(self, message):
        CTkMessagebox(title="Информация", message=message, icon="info")
    
    # ============================================================================
    # Методы для операций
    # ============================================================================
    
    def full_process(self):
        if not os.path.exists(self.current_dir):
            self.show_error(f"Папка не существует: {self.current_dir}")
            return
        
        if self.is_processing:
            self.show_warning("Дождитесь завершения текущей операции")
            return
        
        self.set_processing_state(True)
        self.log_output("="*60, clear=True)
        self.log_output("🚀 ЗАПУСК ПОЛНОЙ ОБРАБОТКИ")
        self.log_output("="*60)
        
        self.current_task = threading.Thread(target=self.run_full_process)
        self.current_task.start()
    
    def run_full_process(self):
        try:
            # Шаг 1: Конвертация
            self.log_output("\n" + "="*60)
            self.log_output("ШАГ 1: 🔄 КОНВЕРТАЦИЯ .REG ФАЙЛОВ В .BAT")
            self.log_output("="*60)
            
            reg_convert_path = "RegConvert.exe"
            if os.path.exists(reg_convert_path):
                def progress_callback(value, max_value, message):
                    self.update_progress(value, max_value, message)
                
                converted, errors, messages = convert_reg_to_bat(
                    self.current_dir, 
                    reg_convert_path,
                    progress_callback
                )
                self.log_output(messages)
                self.log_output(f"\n✓ Сконвертировано: {converted}, ошибок: {errors}")
            else:
                self.log_output("⚠️  RegConvert.exe не найден, пропускаем этот шаг")
            
            # Шаг 2: Переименование
            self.log_output("\n" + "="*60)
            self.log_output("ШАГ 2: 📝 ПЕРЕИМЕНОВАНИЕ ФАЙЛОВ И ПАПОК")
            self.log_output("="*60)
            
            def rename_progress(value, max_value, message):
                self.update_progress(value, max_value, message)
            
            files, dirs, empty, messages = process_rename_folder(
                self.current_dir, 
                'both',
                rename_progress
            )
            self.log_output(messages)
            self.log_output(f"\n✓ Файлов: {files}, папок: {dirs}, пустых папок: {empty}")
            
            # Шаг 3: Быстрая очистка
            self.log_output("\n" + "="*60)
            self.log_output("ШАГ 3: 🧹 БЫСТРАЯ ОЧИСТКА ФАЙЛОВ")
            self.log_output("="*60)
            
            def clean_progress(value, max_value, message):
                self.update_progress(value, max_value, message)
            
            deleted, errors, messages = quick_clean(
                self.current_dir,
                clean_progress
            )
            self.log_output(messages)
            self.log_output(f"\n✓ Удалено: {deleted}, ошибок: {errors}")
            
            # Шаг 4: Удаление команд
            self.log_output("\n" + "="*60)
            self.log_output("ШАГ 4: ✂️  УДАЛЕНИЕ PAUSE/EXIT/SHUTDOWN")
            self.log_output("="*60)
            
            def cmd_progress(value, max_value, message):
                self.update_progress(value, max_value, message)
            
            processed, modified, cmd_errors, messages = remove_commands_from_batch_files(
                self.current_dir,
                cmd_progress
            )
            self.log_output(messages)
            self.log_output(f"\n✓ Обработано: {processed}, изменено: {modified}, ошибок: {cmd_errors}")
            
            # Шаг 5: Перевод
            self.log_output("\n" + "="*60)
            self.log_output("ШАГ 5: 🌐 ПЕРЕВОД ИМЕН ФАЙЛОВ")
            self.log_output("="*60)
            self.log_output("Запуск перевода...")
            
            # Запуск асинхронного перевода в отдельном потоке
            asyncio.run(self.run_translation_async())
            
            self.log_output("\n" + "="*70)
            self.log_output("✅ ПОЛНАЯ ОБРАБОТКА ЗАВЕРШЕНА!")
            self.log_output("="*70)
            self.log_output("📊 ИТОГОВАЯ СТАТИСТИКА:")
            self.log_output(f"   🔄 Сконвертировано .reg файлов: {converted if 'converted' in locals() else 0}")
            self.log_output(f"   📝 Переименовано файлов: {files}, папок: {dirs}")
            self.log_output(f"   🗑️  Удалено пустых папок: {empty}")
            self.log_output(f"   🧹 Удалено лишних файлов: {deleted}")
            self.log_output(f"   ✂️  Очищено .bat/.cmd файлов: {modified}")
            
        except Exception as e:
            self.log_output(f"❌ Ошибка при полной обработке: {str(e)}")
        finally:
            self.set_processing_state(False)
            self.update_progress(0, 1, "Готов к работе")
    
    async def run_translation_async(self):
        def progress_callback(value, max_value, message):
            self.update_progress(value, max_value, message)
        
        messages = await process_translation_async(self.current_dir, progress_callback)
        self.log_output(messages)
    
    def convert_reg_to_bat_gui(self):
        if not os.path.exists(self.current_dir):
            self.show_error(f"Папка не существует: {self.current_dir}")
            return
        
        if self.is_processing:
            self.show_warning("Дождитесь завершения текущей операции")
            return
        
        # Диалог выбора RegConvert.exe
        file_path = filedialog.askopenfilename(
            title="Выберите RegConvert.exe",
            filetypes=[("EXE files", "*.exe"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        self.set_processing_state(True)
        self.log_output("="*60, clear=True)
        self.log_output("🔄 КОНВЕРТАЦИЯ .REG ФАЙЛОВ В .BAT")
        self.log_output("="*60)
        
        self.current_task = threading.Thread(
            target=self.run_convert_reg_to_bat,
            args=(file_path,)
        )
        self.current_task.start()
    
    def run_convert_reg_to_bat(self, reg_convert_path):
        try:
            def progress_callback(value, max_value, message):
                self.update_progress(value, max_value, message)
            
            converted, errors, messages = convert_reg_to_bat(
                self.current_dir, 
                reg_convert_path,
                progress_callback
            )
            
            self.log_output(messages)
            self.log_output("\n" + "="*60)
            self.log_output(f"✅ КОНВЕРТАЦИЯ ЗАВЕРШЕНА!")
            self.log_output(f"📊 Статистика:")
            self.log_output(f"   ✓ Успешно сконвертировано: {converted}")
            self.log_output(f"   ✗ Ошибок: {errors}")
            
        except Exception as e:
            self.log_output(f"❌ Ошибка при конвертации: {str(e)}")
        finally:
            self.set_processing_state(False)
            self.update_progress(0, 1, "Готов к работе")
    
    def rename_gui(self):
        if not os.path.exists(self.current_dir):
            self.show_error(f"Папка не существует: {self.current_dir}")
            return
        
        if self.is_processing:
            self.show_warning("Дождитесь завершения текущей операции")
            return
        
        # Диалог выбора режима
        dialog = ctk.CTkInputDialog(
            text="Выберите режим переименования:\n1. Удалить цифры и точки\n2. Удалить пробелы и скобки\n3. Оба режима",
            title="Режим переименования"
        )
        
        choice = dialog.get_input()
        if not choice:
            return
        
        if choice == '1':
            mode = 'numbers'
        elif choice == '2':
            mode = 'spaces'
        elif choice == '3':
            mode = 'both'
        else:
            self.show_warning("Неверный выбор")
            return
        
        self.set_processing_state(True)
        self.log_output("="*60, clear=True)
        self.log_output(f"📝 ПЕРЕИМЕНОВАНИЕ ФАЙЛОВ И ПАПОК ({mode})")
        self.log_output("="*60)
        
        self.current_task = threading.Thread(
            target=self.run_rename,
            args=(mode,)
        )
        self.current_task.start()
    
    def run_rename(self, mode):
        try:
            def progress_callback(value, max_value, message):
                self.update_progress(value, max_value, message)
            
            files, dirs, empty, messages = process_rename_folder(
                self.current_dir, 
                mode,
                progress_callback
            )
            
            self.log_output(messages)
            self.log_output("\n" + "="*60)
            self.log_output(f"✅ ПЕРЕИМЕНОВАНИЕ ЗАВЕРШЕНО!")
            self.log_output(f"📊 Статистика:")
            self.log_output(f"   📄 Файлов переименовано: {files}")
            self.log_output(f"   📁 Папок переименовано: {dirs}")
            self.log_output(f"   🗑️  Пустых папок удалено: {empty}")
            
        except Exception as e:
            self.log_output(f"❌ Ошибка при переименовании: {str(e)}")
        finally:
            self.set_processing_state(False)
            self.update_progress(0, 1, "Готов к работе")
    
    def quick_clean_gui(self):
        if not os.path.exists(self.current_dir):
            self.show_error(f"Папка не существует: {self.current_dir}")
            return
        
        if self.is_processing:
            self.show_warning("Дождитесь завершения текущей операции")
            return
        
        # Подтверждение
        msg = CTkMessagebox(
            title="Подтверждение",
            message="Будут удалены все файлы кроме:\n.bat, .cmd, .reg, .pow, .py, .nip, .ps1\n\nВы уверены?",
            icon="question",
            option_1="Отмена",
            option_2="Продолжить"
        )
        
        if msg.get() != "Продолжить":
            return
        
        self.set_processing_state(True)
        self.log_output("="*60, clear=True)
        self.log_output("🧹 БЫСТРАЯ ОЧИСТКА ФАЙЛОВ")
        self.log_output("="*60)
        
        self.current_task = threading.Thread(target=self.run_quick_clean)
        self.current_task.start()
    
    def run_quick_clean(self):
        try:
            def progress_callback(value, max_value, message):
                self.update_progress(value, max_value, message)
            
            deleted, errors, messages = quick_clean(
                self.current_dir,
                progress_callback
            )
            
            self.log_output(messages)
            self.log_output("\n" + "="*60)
            self.log_output(f"✅ ОЧИСТКА ЗАВЕРШЕНА!")
            self.log_output(f"📊 Статистика:")
            self.log_output(f"   🗑️  Файлов удалено: {deleted}")
            self.log_output(f"   ❌ Ошибок: {errors}")
            
        except Exception as e:
            self.log_output(f"❌ Ошибка при очистке: {str(e)}")
        finally:
            self.set_processing_state(False)
            self.update_progress(0, 1, "Готов к работе")
    
    def remove_commands_gui(self):
        if not os.path.exists(self.current_dir):
            self.show_error(f"Папка не существует: {self.current_dir}")
            return
        
        if self.is_processing:
            self.show_warning("Дождитесь завершения текущей операции")
            return
        
        # Подтверждение
        msg = CTkMessagebox(
            title="Подтверждение",
            message="Будут удалены команды pause, exit, shutdown\nиз всех .bat и .cmd файлов\n\nВы уверены?",
            icon="question",
            option_1="Отмена",
            option_2="Продолжить"
        )
        
        if msg.get() != "Продолжить":
            return
        
        self.set_processing_state(True)
        self.log_output("="*60, clear=True)
        self.log_output("✂️  УДАЛЕНИЕ PAUSE/EXIT/SHUTDOWN ИЗ .BAT/.CMD ФАЙЛОВ")
        self.log_output("="*60)
        
        self.current_task = threading.Thread(target=self.run_remove_commands)
        self.current_task.start()
    
    def run_remove_commands(self):
        try:
            def progress_callback(value, max_value, message):
                self.update_progress(value, max_value, message)
            
            processed, modified, errors, messages = remove_commands_from_batch_files(
                self.current_dir,
                progress_callback
            )
            
            self.log_output(messages)
            self.log_output("\n" + "="*60)
            self.log_output(f"✅ ОЧИСТКА КОМАНД ЗАВЕРШЕНА!")
            self.log_output(f"📊 Статистика:")
            self.log_output(f"   📄 Обработано файлов: {processed}")
            self.log_output(f"   ✂️  Изменено файлов: {modified}")
            self.log_output(f"   ❌ Ошибок: {errors}")
            
        except Exception as e:
            self.log_output(f"❌ Ошибка при очистке команд: {str(e)}")
        finally:
            self.set_processing_state(False)
            self.update_progress(0, 1, "Готов к работе")
    
    def translate_gui(self):
        if not os.path.exists(self.current_dir):
            self.show_error(f"Папка не существует: {self.current_dir}")
            return
        
        if self.is_processing:
            self.show_warning("Дождитесь завершения текущей операции")
            return
        
        # Подтверждение
        msg = CTkMessagebox(
            title="Подтверждение",
            message="Будут переведены имена файлов с английского на русский\n\nВы уверены?",
            icon="question",
            option_1="Отмена",
            option_2="Продолжить"
        )
        
        if msg.get() != "Продолжить":
            return
        
        self.set_processing_state(True)
        self.log_output("="*60, clear=True)
        self.log_output("🌐 ПЕРЕВОД ИМЕН ФАЙЛОВ")
        self.log_output("="*60)
        
        self.current_task = threading.Thread(target=self.run_translation)
        self.current_task.start()
    
    def run_translation(self):
        try:
            async def translate_wrapper():
                def progress_callback(value, max_value, message):
                    self.update_progress(value, max_value, message)
                
                messages = await process_translation_async(
                    self.current_dir,
                    progress_callback
                )
                self.log_output(messages)
                self.log_output("\n" + "="*60)
                self.log_output(f"✅ ПЕРЕВОД ЗАВЕРШЕН!")
            
            asyncio.run(translate_wrapper())
            
        except Exception as e:
            self.log_output(f"❌ Ошибка при переводе: {str(e)}")
        finally:
            self.set_processing_state(False)
            self.update_progress(0, 1, "Готов к работе")
    
    def find_duplicates_gui(self):
        if not os.path.exists(self.current_dir):
            self.show_error(f"Папка не существует: {self.current_dir}")
            return
        
        if self.is_processing:
            self.show_warning("Дождитесь завершения текущей операции")
            return
        
        self.set_processing_state(True)
        self.log_output("="*60, clear=True)
        self.log_output("🔍 ПОИСК ДУБЛИКАТОВ ФАЙЛОВ")
        self.log_output("="*60)
        
        self.current_task = threading.Thread(target=self.run_find_duplicates)
        self.current_task.start()
    
    def run_find_duplicates(self):
        try:
            remover = DuplicateFileRemoverGUI([self.current_dir])
            
            def progress_callback(value, max_value, message):
                self.update_progress(value, max_value, message)
            
            duplicates = remover.find_duplicates(progress_callback)
            
            self.log_output(f"\n📊 РЕЗУЛЬТАТЫ ПОИСКА:")
            self.log_output(f"   📁 Всего файлов проверено: {remover.stats['total_files']}")
            self.log_output(f"   🔍 Найдено групп дубликатов: {len(duplicates)}")
            self.log_output(f"   💾 Дублирующий объем: {remover.format_size(remover.stats['duplicate_size'])}")
            self.log_output(f"   ⏱️  Время обработки: {remover.stats['processing_time']:.2f} сек")
            
            if duplicates:
                self.log_output("\n🎯 НАЙДЕННЫЕ ДУБЛИКАТЫ:")
                for i, group in enumerate(duplicates[:10], 1):  # Показываем первые 10 групп
                    self.log_output(f"\nГруппа {i}: {len(group['files'])} файлов, "
                                  f"размер: {remover.format_size(group['size'])}")
                    for filepath, size, created, modified in group['files'][:3]:  # Показываем первые 3 файла
                        self.log_output(f"  • {os.path.basename(filepath)}")
                    if len(group['files']) > 3:
                        self.log_output(f"  • ... и еще {len(group['files']) - 3} файлов")
            
            # Предложение удалить
            if duplicates:
                self.log_output("\n" + "="*60)
                msg = CTkMessagebox(
                    title="Найдены дубликаты",
                    message=f"Найдено {len(duplicates)} групп дубликатов\nУдалить дубликаты?",
                    icon="question",
                    option_1="Отмена",
                    option_2="Удалить"
                )
                
                if msg.get() == "Удалить":
                    self.delete_duplicates_gui(remover, duplicates)
            
        except Exception as e:
            self.log_output(f"❌ Ошибка при поиске дубликатов: {str(e)}")
        finally:
            self.set_processing_state(False)
            self.update_progress(0, 1, "Готов к работе")
    
    def delete_duplicates_gui(self, remover, duplicates):
        # Диалог выбора стратегии
        dialog = ctk.CTkInputDialog(
            text="Выберите стратегию удаления:\n1. Оставить самый старый файл\n2. Оставить самый новый файл\n3. Оставить файл с самым коротким путем\n4. Оставить файл с самым длинным путем",
            title="Стратегия удаления дубликатов"
        )
        
        choice = dialog.get_input()
        if not choice:
            return
        
        strategies = {
            '1': 'oldest',
            '2': 'newest',
            '3': 'shortest_path',
            '4': 'longest_path'
        }
        
        strategy = strategies.get(choice, 'oldest')
        
        self.log_output(f"\n🗑️  УДАЛЕНИЕ ДУБЛИКАТОВ (стратегия: {strategy})...")
        
        try:
            deleted_files = []
            
            for i, group in enumerate(duplicates, 1):
                if strategy == 'oldest':
                    sorted_files = sorted(group['files'], key=lambda x: x[2])  # created
                elif strategy == 'newest':
                    sorted_files = sorted(group['files'], key=lambda x: x[3], reverse=True)  # modified
                elif strategy == 'shortest_path':
                    sorted_files = sorted(group['files'], key=lambda x: len(str(x[0])))
                elif strategy == 'longest_path':
                    sorted_files = sorted(group['files'], key=lambda x: len(str(x[0])), reverse=True)
                else:
                    sorted_files = sorted(group['files'], key=lambda x: x[2])
                
                keep_file = sorted_files[0]
                files_to_delete = sorted_files[1:]
                
                for filepath, size, created, modified in files_to_delete:
                    try:
                        os.remove(filepath)
                        deleted_files.append(str(filepath))
                        self.log_output(f"  Удален: {os.path.basename(filepath)}")
                    except Exception as e:
                        self.log_output(f"  ❌ Ошибка: {os.path.basename(filepath)} - {str(e)}")
            
            self.log_output(f"\n✅ УДАЛЕНО {len(deleted_files)} ДУБЛИКАТОВ")
            
        except Exception as e:
            self.log_output(f"❌ Ошибка при удалении дубликатов: {str(e)}")
    
    def settings_gui(self):
        # Диалог изменения папки
        dir_path = filedialog.askdirectory(initialdir=self.current_dir)
        if dir_path:
            self.current_dir = dir_path
            self.update_dir_label()
            self.log_output(f"⚙️  Изменена рабочая папка: {dir_path}")
    
    def run(self):
        self.root.mainloop()

# ============================================================================
# Запуск приложения
# ============================================================================

if __name__ == "__main__":
    try:
        app = FileProcessorApp()
        app.run()
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        input("Нажмите Enter для выхода...")