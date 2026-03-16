import os
import base64
from typing import Optional, Union

# 支持的文件类型
SUPPORTED_FILE_TYPES = {
    'text': ['.txt', '.md', '.json', '.csv', '.log', '.xml', '.yaml', '.yml'],
    'image': ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'],
    'audio': ['.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac'],
    'video': ['.mp4', '.webm', '.mov', '.avi', '.mkv'],
    'document': ['.pdf']
}

def read_file_content(file_path: str) -> str:
    """读取文件内容
    
    Args:
        file_path: 文件路径
    
    Returns:
        文件内容
    """
    try:
        # 获取文件扩展名
        ext = os.path.splitext(file_path)[1].lower()
        
        # 文本文件
        if ext in SUPPORTED_FILE_TYPES['text']:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        
        # 图片文件
        elif ext in SUPPORTED_FILE_TYPES['image']:
            with open(file_path, 'rb') as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
            return f"[Image: {os.path.basename(file_path)}]\nBase64: {encoded}"
        
        # 音频文件
        elif ext in SUPPORTED_FILE_TYPES['audio']:
            return f"[Audio: {os.path.basename(file_path)}]\nFile path: {file_path}"
        
        # 视频文件
        elif ext in SUPPORTED_FILE_TYPES['video']:
            return f"[Video: {os.path.basename(file_path)}]\nFile path: {file_path}"
        
        # PDF文件
        elif ext in SUPPORTED_FILE_TYPES['document']:
            try:
                import PyPDF2
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ''
                    for page_num in range(len(reader.pages)):
                        page = reader.pages[page_num]
                        text += page.extract_text()
                return f"[PDF: {os.path.basename(file_path)}]\n{text}"
            except ImportError:
                return f"[PDF: {os.path.basename(file_path)}]\nPyPDF2 not installed, cannot extract text"
            except Exception as e:
                return f"[PDF: {os.path.basename(file_path)}]\nError reading PDF: {str(e)}"
        
        # 其他文件类型
        else:
            return f"[File: {os.path.basename(file_path)}]\nFile path: {file_path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

def get_file_type(file_path: str) -> str:
    """获取文件类型
    
    Args:
        file_path: 文件路径
    
    Returns:
        文件类型
    """
    ext = os.path.splitext(file_path)[1].lower()
    for file_type, extensions in SUPPORTED_FILE_TYPES.items():
        if ext in extensions:
            return file_type
    return 'unknown'

def ensure_directory(directory: str) -> None:
    """确保目录存在
    
    Args:
        directory: 目录路径
    """
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import os
import uuid
import requests
import base64
import hashlib

PROJECT_BASE = os.getenv("RAG_PROJECT_BASE") or os.getenv("RAG_DEPLOY_BASE")

IMG_FORMAT=["png","jpg","jpeg","gif","bmp","webp","svg","tiff","tif"]
VIDEO_FORMAT=["mp4","avi","mov","wmv","flv","mkv","webm","m4v","3gp"]
AUDIO_FORMAT=["mp3","wav","ogg","flac","m4a","aac","wma","amr"]


def get_project_base_directory(*args):
    global PROJECT_BASE
    if PROJECT_BASE is None:
        PROJECT_BASE = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                os.pardir,
            )
        )

    if args:
        return os.path.join(PROJECT_BASE, *args)
    return PROJECT_BASE

def get_filepaths(base,has_suffix=[]):
    for root, ds, fs in os.walk(base):
        for f in fs:
            if has_suffix and os.path.splitext(f)[-1] not in has_suffix:
                continue
            fullname = os.path.join(root, f)
            yield fullname



def get_uuid():
    return uuid.uuid1().hex


def download_img(url):
    if not url:
        return ""
    response = requests.get(url)
    return "data:" + \
        response.headers.get('Content-Type', 'image/jpg') + ";" + \
        "base64," + base64.b64encode(response.content).decode("utf-8")


def hash_str2int(line: str, mod: int = 10 ** 8) -> int:
    return int(hashlib.sha1(line.encode("utf-8")).hexdigest(), 16) % mod

def convert_bytes(size_in_bytes: int) -> str:
    """
    Format size in bytes.
    """
    if size_in_bytes == 0:
        return "0 B"

    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    size = float(size_in_bytes)

    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1

    if i == 0 or size >= 100:
        return f"{size:.0f} {units[i]}"
    elif size >= 10:
        return f"{size:.1f} {units[i]}"
    else:
        return f"{size:.2f} {units[i]}"