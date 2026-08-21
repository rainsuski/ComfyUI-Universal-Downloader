import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

# 兼容独立运行与 ComfyUI 环境
try:
    import folder_paths
except ImportError:
    folder_paths = None


class DownloaderCore:
    """Universal Downloader 核心调度器单例类 管理多引擎任务调度、进度解析与文件生命周期"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                # 优化: 采用现代 Python 3 无参 super()
                cls._instance = super().__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.tasks = {}  # 保存所有任务: { task_id: task_dict }
        self.fake_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    # ==================== 1.1 多平台 aria2 路径智能探测器 ====================
    def detect_aria2_path(self, custom_path=""):
        """探测优先级: 1. 用户自定义手动指定 2. 系统全局环境变量 PATH 3. 自动嗅探 Motrix 常见默认安装路径 4. 未找到 (返回 None)"""
        # 1. 用户手动指定
        if custom_path and custom_path.strip():
            c_path = os.path.expanduser(custom_path.strip())
            if os.path.isfile(c_path):
                if sys.platform.startswith("win") and c_path.lower().endswith(".exe"):
                    return c_path
                if os.access(c_path, os.X_OK):
                    return c_path

        # 2. 系统全局环境变量 PATH
        sys_aria = shutil.which("aria2c")
        if sys_aria:
            return sys_aria

        # 3. 自动嗅探 Windows 下 Motrix 常见安装路径
        if sys.platform.startswith("win"):
            possible_motrix_paths = [
                os.path.expandvars(
                    r"%LOCALAPPDATA%\Programs\Motrix\resources\engine\aria2c.exe"
                ),
                r"C:\Program Files\Motrix\resources\engine\aria2c.exe",
                r"C:\Program Files (x86)\Motrix\resources\engine\aria2c.exe",
                os.path.expandvars(
                    r"%APPDATA%\Local\Programs\Motrix\resources\engine\aria2c.exe"
                ),
            ]
            for m_path in possible_motrix_paths:
                if os.path.isfile(m_path):
                    print(
                        f"[Universal-Downloader] ⚡ 自动探测到 Motrix 内置 aria2 引擎: {m_path}"
                    )
                    return m_path

        # 4. 未找到
        return None

    # ==================== 1.2 资源链接与元数据解析内核 ====================
    def parse_resource_info(
        self,
        url_or_air,
        target_type="auto",
        custom_path="",
        custom_filename="",
        civitai_token="",
        hf_use_mirror=True,
    ):
        """解析输入资源，返回: (final_url, final_filename, target_dir, model_category)"""
        input_str = url_or_air.strip()
        final_url = ""
        file_name = custom_filename.strip()
        model_category = target_type

        # ---------- A. Hugging Face 链接解析 ----------
        if "huggingface.co" in input_str or "hf-mirror.com" in input_str:
            clean_url = input_str.split("?")[0]
            if not file_name:
                file_name = clean_url.split("/")[-1]

            if "/blob/" in input_str:
                input_str = input_str.replace("/blob/", "/resolve/")

            if hf_use_mirror and "huggingface.co" in input_str:
                input_str = input_str.replace("huggingface.co", "hf-mirror.com")

            final_url = input_str

            if model_category == "auto":
                low = input_str.lower()
                if any(k in low for k in ["text_encoder", "qwen_3", "clip"]):
                    model_category = "text_encoders"
                elif "vae" in low:
                    model_category = "vae"
                elif any(k in low for k in ["diffusion_models", "unet", "anima"]):
                    model_category = "diffusion_models"
                elif "lora" in low:
                    model_category = "loras"
                elif "controlnet" in low:
                    model_category = "controlnet"
                elif "checkpoint" in low:
                    model_category = "checkpoints"
                elif "upscale" in low:
                    model_category = "upscale_models"
                else:
                    model_category = "checkpoints"

        # ---------- B. Civitai (C站) 链接 / AIR / 纯 ID 解析 ----------
        elif (
            "civitai" in input_str
            or input_str.isdigit()
            or input_str.startswith("urn:air:")
        ):
            version_id = None
            air_match = re.search(
                r"urn:air:([^:]+):([^:]+):civitai:([0-9]+)(@([0-9]+))?",
                input_str,
            )
            if air_match:
                m_type = air_match.group(2).lower()
                version_id = (
                    air_match.group(5) if air_match.group(5) else air_match.group(3)
                )
                if model_category == "auto":
                    if m_type == "checkpoint":
                        model_category = "checkpoints"
                    elif m_type in ("lora", "locon"):
                        model_category = "loras"
                    elif m_type == "vae":
                        model_category = "vae"
                    elif m_type == "controlnet":
                        model_category = "controlnet"
                    elif m_type == "upscaler":
                        model_category = "upscale_models"
            elif "modelVersionId=" in input_str:
                m = re.search(r"modelVersionId=(\d+)", input_str)
                if m:
                    version_id = m.group(1)
            elif input_str.isdigit():
                version_id = input_str
            elif "civitai.com/api/download/models/" in input_str:
                m = re.search(r"models/(\d+)", input_str)
                if m:
                    version_id = m.group(1)

            # 调用 C 站官方 API 获取真实文件名与 downloadUrl
            if version_id:
                api_meta_url = f"https://civitai.com/api/v1/model-versions/{version_id}"
                try:
                    headers = {"User-Agent": self.fake_ua}
                    if civitai_token.strip():
                        headers["Authorization"] = f"Bearer {civitai_token.strip()}"
                    req = urllib.request.Request(api_meta_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=6) as response:
                        meta = json.loads(response.read().decode())
                        if not file_name and "files" in meta and len(meta["files"]) > 0:
                            file_name = meta["files"][0]["name"]
                            final_url = meta["files"][0].get(
                                "downloadUrl",
                                f"https://civitai.com/api/download/models/{version_id}",
                            )
                        else:
                            final_url = meta.get(
                                "downloadUrl",
                                f"https://civitai.com/api/download/models/{version_id}",
                            )
                except (
                    urllib.error.URLError,
                    urllib.error.HTTPError,
                    json.JSONDecodeError,
                    TimeoutError,
                    KeyError,
                ):
                    final_url = f"https://civitai.com/api/download/models/{version_id}"
            else:
                final_url = input_str

            if "token=" not in final_url and civitai_token.strip():
                sep = "&" if "?" in final_url else "?"
                final_url = f"{final_url}{sep}token={civitai_token.strip()}"

            # 提前发起 HEAD 请求预解析 307 重定向，抓取 Cloudflare R2 直链
            try:
                head_req = urllib.request.Request(
                    final_url,
                    headers={"User-Agent": self.fake_ua},
                    method="HEAD",
                )
                with urllib.request.urlopen(head_req, timeout=6) as head_resp:
                    final_url = head_resp.geturl()
            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                TimeoutError,
                OSError,
            ):
                pass

        # ---------- C. 通用直链 / GitHub Releases 解析 ----------
        else:
            final_url = input_str
            clean_name = input_str.split("?")[0].rstrip("/").split("/")[-1]
            if not file_name:
                file_name = clean_name or "downloaded_file.bin"
            if model_category == "auto":
                model_category = "custom_path"

        # ---------- D. 最终保存路径计算 ----------
        comfy_root = (
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            if "__file__" in locals()
            else os.getcwd()
        )

        if model_category == "custom_path" or target_type == "custom_path":
            if custom_path.strip():
                target_dir = (
                    os.path.abspath(custom_path.strip())
                    if os.path.isabs(custom_path.strip())
                    else os.path.abspath(os.path.join(comfy_root, custom_path.strip()))
                )
            else:
                target_dir = (
                    os.path.join(folder_paths.models_dir, "custom_downloads")
                    if folder_paths
                    else os.path.join(comfy_root, "models", "custom_downloads")
                )
        else:
            if model_category == "auto":
                model_category = "loras"
            if folder_paths:
                try:
                    target_dir = folder_paths.get_folder_paths(model_category)[0]
                except (KeyError, IndexError, AttributeError):
                    target_dir = os.path.join(folder_paths.models_dir, model_category)
            else:
                target_dir = os.path.join(comfy_root, "models", model_category)

        os.makedirs(target_dir, exist_ok=True)
        return final_url, file_name, target_dir, model_category

    # ==================== 1.3 双引擎执行逻辑 ====================
    def _run_aria2_task(self, task_id, aria2_bin, final_url, target_dir, file_name):
        """引擎 A: aria2c (CLI) 执行与标准输出实时解析"""
        task = self.tasks[task_id]
        cmd = [
            aria2_bin,
            "-c",
            "-x",
            "16",
            "-s",
            "16",
            "-k",
            "1M",
            "--summary-interval=1",
            "--console-log-level=notice",
            f"--header=User-Agent: {self.fake_ua}",
            "-d",
            target_dir,
            "-o",
            file_name,
            final_url,
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )
            task["process_ref"] = process
            task["status"] = "DOWNLOADING"

            progress_regex = re.compile(
                r"\[#\w+\s+([\d\.]+\w+)/([\d\.]+\w+)\((\d+)%\).*?DL:([\d\.]+\w+)"
            )

            for line in iter(process.stdout.readline, ""):
                if task["cancel_flag"]:
                    process.terminate()
                    break

                match = progress_regex.search(line)
                if match:
                    task["downloaded"] = match.group(1)
                    task["total"] = match.group(2)
                    task["progress"] = float(match.group(3))
                    task["speed"] = f"{match.group(4)}/s"

            process.stdout.close()
            return_code = process.wait()

            if task["cancel_flag"]:
                task["status"] = "CANCELLED"
                task["speed"] = "0 B/s"
            elif return_code == 0:
                task["status"] = "COMPLETED"
                task["progress"] = 100.0
                task["speed"] = "0 B/s"
                self._trigger_comfy_refresh()
            else:
                task["status"] = "FAILED"
                task["error_msg"] = f"aria2 进程非正常退出，代码: {return_code}"

        except (OSError, subprocess.SubprocessError) as e:
            task["status"] = "FAILED"
            task["error_msg"] = f"启动或执行 aria2 失败: {e}"

    def _run_python_stream_task(self, task_id, final_url, target_dir, file_name):
        """引擎 B: Python 原生流式切片下载 (带原子写入与取消保护)"""
        task = self.tasks[task_id]
        temp_file_path = os.path.join(target_dir, f"{file_name}.downloading")
        final_file_path = os.path.join(target_dir, file_name)

        try:
            req = urllib.request.Request(
                final_url, headers={"User-Agent": self.fake_ua}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                total_bytes = int(resp.headers.get("Content-Length", 0))
                task["total"] = (
                    f"{round(total_bytes / (1024 * 1024), 2)} MB"
                    if total_bytes
                    else "未知"
                )
                task["status"] = "DOWNLOADING"

                downloaded = 0
                chunk_size = 1024 * 1024  # 1MB 块
                last_time = time.time()
                last_downloaded = 0

                with open(temp_file_path, "wb") as f:
                    while True:
                        if task["cancel_flag"]:
                            break

                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)

                        now = time.time()
                        dt = now - last_time
                        if dt >= 0.5:
                            speed_bps = (downloaded - last_downloaded) / dt
                            task["speed"] = (
                                f"{round(speed_bps / (1024 * 1024), 2)} MB/s"
                            )
                            task["downloaded"] = (
                                f"{round(downloaded / (1024 * 1024), 2)} MB"
                            )
                            if total_bytes > 0:
                                task["progress"] = round(
                                    (downloaded / total_bytes) * 100, 1
                                )
                            last_time = now
                            last_downloaded = downloaded

            if task["cancel_flag"]:
                task["status"] = "CANCELLED"
                task["speed"] = "0 B/s"
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            else:
                if os.path.exists(final_file_path):
                    os.remove(final_file_path)
                os.replace(temp_file_path, final_file_path)

                task["status"] = "COMPLETED"
                task["progress"] = 100.0
                task["speed"] = "0 B/s"
                self._trigger_comfy_refresh()

        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            OSError,
        ) as e:
            task["status"] = "FAILED"
            task["error_msg"] = f"流式下载失败: {e}"
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    # ==================== 1.4 状态机与任务调度接口 ====================
    def _trigger_comfy_refresh(self):
        """通知 ComfyUI 后端内存重新扫描模型文件 (非刷新网页)"""
        if folder_paths and hasattr(folder_paths, "cache"):
            try:
                folder_paths.cache.clear()
            except (AttributeError, TypeError) as e:
                print(f"[Universal-Downloader] 刷新模型缓存提示: {e}")

    def create_task(self, params):
        """创建并启动一个异步下载任务"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        url_or_air = params.get("url_or_air", "")
        target_type = params.get("target_type", "auto")
        custom_path = params.get("custom_path", "")
        custom_filename = params.get("custom_filename", "")
        civitai_token = params.get("civitai_token", "")
        hf_use_mirror = params.get("hf_use_mirror", True)
        aria2_path_input = params.get("aria2_path", "")
        download_engine = params.get("download_engine", "aria2 (CLI)")

        task = {
            "id": task_id,
            "url_or_air": url_or_air,
            "file_name": "解析中...",
            "save_dir": "",
            "category": target_type,
            "engine": download_engine,
            "status": "PARSING",
            "progress": 0.0,
            "speed": "0 B/s",
            "downloaded": "0 MB",
            "total": "0 MB",
            "error_msg": "",
            "cancel_flag": False,
            "process_ref": None,
            "created_at": time.time(),
        }
        self.tasks[task_id] = task

        def _worker():
            try:
                # 1. 深度解析直链与文件名
                final_url, file_name, target_dir, model_category = (
                    self.parse_resource_info(
                        url_or_air=url_or_air,
                        target_type=target_type,
                        custom_path=custom_path,
                        custom_filename=custom_filename,
                        civitai_token=civitai_token,
                        hf_use_mirror=hf_use_mirror,
                    )
                )

                task["file_name"] = file_name
                task["save_dir"] = target_dir
                task["category"] = model_category

                # 2. 检查 aria2 路径并决定执行引擎
                detected_aria2 = self.detect_aria2_path(aria2_path_input)

                if "aria2" in download_engine and detected_aria2:
                    task["engine"] = f"aria2 ({detected_aria2})"
                    self._run_aria2_task(
                        task_id,
                        detected_aria2,
                        final_url,
                        target_dir,
                        file_name,
                    )
                else:
                    if "aria2" in download_engine and not detected_aria2:
                        print(
                            "[Universal-Downloader] ⚠️ 未探测到有效 aria2c，已自动无缝降级为 Python 原生流式下载！"
                        )
                        task["engine"] = "Python (自动降级流式)"
                    else:
                        task["engine"] = "Python (原生流式)"

                    self._run_python_stream_task(
                        task_id, final_url, target_dir, file_name
                    )

            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                TimeoutError,
                OSError,
                KeyError,
                ValueError,
            ) as e:
                task["status"] = "FAILED"
                task["error_msg"] = f"解析异常: {e}"

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        return task_id

    def cancel_task(self, task_id):
        """取消指定任务"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task["cancel_flag"] = True
            if task.get("process_ref"):
                try:
                    task["process_ref"].terminate()
                except (ProcessLookupError, OSError):
                    pass
            task["status"] = "CANCELLED"
            task["speed"] = "0 B/s"
            return True
        return False

    def get_all_tasks(self):
        """获取所有任务清单（已清理不可序列化对象）"""
        clean_tasks = []
        for t in self.tasks.values():
            t_copy = t.copy()
            t_copy.pop("process_ref", None)
            clean_tasks.append(t_copy)
        clean_tasks.sort(key=lambda x: x["created_at"], reverse=True)
        return clean_tasks

    def clear_finished(self):
        """清理已完成、已失败或已取消的历史任务"""
        to_delete = [
            tid
            for tid, t in self.tasks.items()
            if t["status"] in ("COMPLETED", "FAILED", "CANCELLED")
        ]
        for tid in to_delete:
            del self.tasks[tid]
        return len(to_delete)
