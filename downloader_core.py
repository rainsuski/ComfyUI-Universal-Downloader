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

try:
    import folder_paths
except ImportError:
    folder_paths = None

# aria2 退出代码人性化中文化字典 [2]
ARIA2_ERROR_CODES = {
    1: "发生未知错误",
    2: "连接超时，目标服务器未响应",
    3: "资源未找到 (HTTP 404 / 链接失效)",
    4: "资源未找到且重试次数已达上限",
    5: "下载速度过慢导致连接中断",
    6: "网络连接异常中断",
    7: "存在未完成的下载任务",
    8: "远程服务器不支持断点续传",
    9: "磁盘剩余空间不足",
    10: "分片哈希校验失败",
    11: "正在进行相同文件的下载",
    12: "正在下载相同的种子信息",
    13: "目标文件已存在",
    14: "文件重命名失败",
    15: "无法打开已存在的文件",
    16: "无法创建新文件或磁盘权限受限",
    17: "本地磁盘文件 I/O 读写错误",
    18: "无法创建保存目录",
    19: "DNS 域名解析失败，请检查网址主机名是否有效",
    20: "无法解析 Metalink 文件",
    21: "FTP 协议命令执行失败",
    22: "HTTP 响应标头格式错误或异常",
    23: "发生过多重定向循环",
    24: "HTTP 身份验证失败 (需有效 Token 或登录权限)",
    25: "无法解析种子 (Torrent) 文件",
    26: "种子文件损坏或缺少关键信息",
    27: "Magnet 磁力链接解析失败",
    28: "aria2 命令参数错误",
    29: "目标服务器拒绝响应或服务不可用 (HTTP 503/地址不可达)",
    30: "RPC 响应数据解析失败",
    31: "校验和 (Checksum) 不匹配",
    32: "校验和计算过程异常",
}


class DownloaderCore:
    """Universal Downloader 核心调度器单例类
    具备精准的错误转义、流式日志捕获与物理文件冲突隔离机制
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.tasks = {}
        self.fake_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )

    # ==================== 路径探测器 ====================
    def detect_aria2_path(self, custom_path=""):
        if custom_path and custom_path.strip():
            c_path = os.path.expanduser(custom_path.strip())
            if os.path.isfile(c_path):
                if sys.platform.startswith("win") and c_path.lower().endswith(".exe"):
                    return c_path
                if os.access(c_path, os.X_OK):
                    return c_path

        sys_aria = shutil.which("aria2c")
        if sys_aria:
            return sys_aria

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
                    return m_path

        return None

    # ==================== 资源解析内核 ====================
    def parse_resource_info(
        self,
        url_or_air,
        target_type="auto",
        custom_path="",
        custom_filename="",
        civitai_token="",
        hf_use_mirror=True,
    ):
        input_str = url_or_air.strip()
        if not input_str:
            raise ValueError("资源地址不能为空！")

        if not input_str.startswith(("http://", "https://", "urn:air:")):
            raise ValueError(
                "无效的资源地址！请输入以 http:// 或 https:// 开头的下载链接，或 Civitai AIR 标签"
            )

        final_url = ""
        file_name = custom_filename.strip()
        model_category = target_type

        # A. Hugging Face 解析
        if "huggingface.co" in input_str or "hf-mirror.com" in input_str:
            clean_url = input_str.split("?")[0].rstrip("/")
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

        # B. Civitai (C站) 解析
        elif "civitai.com" in input_str or input_str.startswith("urn:air:"):
            version_id = None
            air_match = re.search(
                r"urn:air:([^:]+):([^:]+):civitai:([0-9]+)(@([0-9]+))?", input_str
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
            elif "civitai.com/api/download/models/" in input_str:
                m = re.search(r"models/(\d+)", input_str)
                if m:
                    version_id = m.group(1)

            if version_id:
                api_meta_url = f"https://civitai.com/api/v1/model-versions/{version_id}"
                headers = {"User-Agent": self.fake_ua}
                if civitai_token.strip():
                    headers["Authorization"] = f"Bearer {civitai_token.strip()}"

                req = urllib.request.Request(api_meta_url, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=8) as response:
                        meta = json.loads(response.read().decode())
                        if not file_name and "files" in meta and len(meta["files"]) > 0:
                            file_name = meta["files"][0].get("name", "").strip()

                        final_url = meta.get(
                            "downloadUrl",
                            f"https://civitai.com/api/download/models/{version_id}",
                        )
                        if not file_name and "name" in meta:
                            file_name = f"{meta['name']}.safetensors"
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        raise ValueError(
                            f"C 站不存在 Version ID 为 [{version_id}] 的模型版本！"
                        )
                    if e.code in (401, 403):
                        raise ValueError(
                            f"C 站拒绝访问 (HTTP {e.code})，该模型可能需要设置 Civitai API Token！"
                        )
                    raise ValueError(f"请求 C 站 API 失败 (HTTP {e.code}): {e.reason}")
                except (urllib.error.URLError, TimeoutError) as e:
                    raise ValueError(f"连接 C 站 API 超时或网络异常: {e}")
                except json.JSONDecodeError:
                    raise ValueError("C 站 API 返回了非法的响应数据！")
            else:
                final_url = input_str

            if "token=" not in final_url and civitai_token.strip():
                sep = "&" if "?" in final_url else "?"
                final_url = f"{final_url}{sep}token={civitai_token.strip()}"

        # C. 通用直链 (支持任意合法网络地址，包括内网/自定义端口)
        else:
            final_url = input_str
            clean_name = input_str.split("?")[0].rstrip("/").split("/")[-1]
            if not file_name:
                file_name = clean_name
            if model_category == "auto":
                model_category = "custom_path"

        # 【关卡 2】文件名门禁
        file_name = file_name.strip()
        final_url = final_url.strip()

        if not file_name or file_name in (".", "/", "\\"):
            raise ValueError(
                "未能从该地址解析出合法的文件名，请在【自定义文件名】中手动指定！"
            )
        if not final_url.startswith(("http://", "https://")):
            raise ValueError("解析生成的下载直链非法，无法启动下载！")

        # D. 保存路径推导
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

    def _generate_unique_filename(self, target_dir, file_name):
        base, ext = os.path.splitext(file_name)
        counter = 1
        new_name = f"{base} ({counter}){ext}"
        while os.path.isfile(os.path.join(target_dir, new_name)):
            counter += 1
            new_name = f"{base} ({counter}){ext}"
        return new_name

    # ==================== 执行引擎 ====================
    def _run_aria2_task(self, task_id, aria2_bin, final_url, target_dir, file_name):
        task = self.tasks[task_id]
        final_file_path = os.path.join(target_dir, file_name)
        aria_control_file = f"{final_file_path}.aria2"

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
            "--allow-overwrite=true",
            "--auto-file-renaming=false",
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
            last_raw_line = ""

            for line in iter(process.stdout.readline, ""):
                line_str = line.strip()
                if line_str:
                    last_raw_line = line_str

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
                if os.path.isfile(final_file_path):
                    os.remove(final_file_path)
                if os.path.isfile(aria_control_file):
                    os.remove(aria_control_file)
            elif return_code == 0:
                task["status"] = "COMPLETED"
                task["progress"] = 100.0
                task["speed"] = "0 B/s"
                self._trigger_comfy_refresh()
            else:
                task["status"] = "FAILED"
                # 人性化中文化错误翻译
                reason = ARIA2_ERROR_CODES.get(
                    return_code, f"进程退出代码 {return_code}"
                )
                task["error_msg"] = f"下载失败: {reason}"

        except (OSError, subprocess.SubprocessError) as e:
            task["status"] = "FAILED"
            task["error_msg"] = f"执行 aria2 失败: {e}"

    def _run_python_stream_task(self, task_id, final_url, target_dir, file_name):
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
                chunk_size = 1024 * 1024
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
                if os.path.isfile(temp_file_path):
                    os.remove(temp_file_path)
            else:
                if os.path.isfile(final_file_path):
                    os.remove(final_file_path)
                os.replace(temp_file_path, final_file_path)

                task["status"] = "COMPLETED"
                task["progress"] = 100.0
                task["speed"] = "0 B/s"
                self._trigger_comfy_refresh()

        except urllib.error.HTTPError as e:
            task["status"] = "FAILED"
            task["error_msg"] = f"HTTP 错误 {e.code}: {e.reason}"
            if os.path.isfile(temp_file_path):
                os.remove(temp_file_path)
        except urllib.error.URLError as e:
            task["status"] = "FAILED"
            task["error_msg"] = f"网络连接失败: {e.reason}"
            if os.path.isfile(temp_file_path):
                os.remove(temp_file_path)
        except (TimeoutError, OSError) as e:
            task["status"] = "FAILED"
            task["error_msg"] = f"流式下载异常: {e}"
            if os.path.isfile(temp_file_path):
                os.remove(temp_file_path)

    # ==================== 状态机与调度 ====================
    def _trigger_comfy_refresh(self):
        if folder_paths and hasattr(folder_paths, "cache"):
            try:
                folder_paths.cache.clear()
            except (AttributeError, TypeError) as e:
                print(f"[Universal-Downloader] 刷新模型缓存提示: {e}")

    def create_task(self, params):
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
            "file_name": "正在解析资源...",
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
            "conflict_info": None,
            "conflict_event": threading.Event(),
            "conflict_action": None,
            "created_at": time.time(),
        }
        self.tasks[task_id] = task

        def _worker():
            try:
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
                target_file_path = os.path.join(target_dir, file_name)

                if not file_name or not file_name.strip():
                    raise ValueError("未能获取到有效的文件名，无法启动下载！")

                if os.path.isdir(target_file_path):
                    raise ValueError(
                        f"目标路径是一个已存在的目录，无法作为文件写入：{target_file_path}"
                    )

                if os.path.isfile(target_file_path):
                    size_bytes = os.path.getsize(target_file_path)
                    size_str = (
                        f"{round(size_bytes / (1024 * 1024 * 1024), 2)} GB"
                        if size_bytes >= 1024 * 1024 * 1024
                        else f"{round(size_bytes / (1024 * 1024), 2)} MB"
                    )

                    task["status"] = "CONFLICT"
                    task["conflict_info"] = {
                        "file_name": file_name,
                        "file_size": size_str,
                        "full_path": target_file_path,
                    }

                    resolved = task["conflict_event"].wait(timeout=600)

                    if (
                        not resolved
                        or task["conflict_action"] == "cancel"
                        or task["cancel_flag"]
                    ):
                        task["status"] = "CANCELLED"
                        task["speed"] = "0 B/s"
                        return

                    if task["conflict_action"] == "rename":
                        file_name = self._generate_unique_filename(
                            target_dir, file_name
                        )
                        task["file_name"] = file_name
                        target_file_path = os.path.join(target_dir, file_name)
                    elif task["conflict_action"] == "overwrite":
                        try:
                            if os.path.isfile(target_file_path):
                                os.remove(target_file_path)
                            if os.path.isfile(f"{target_file_path}.aria2"):
                                os.remove(f"{target_file_path}.aria2")
                        except OSError as err:
                            print(f"[Universal-Downloader] 覆盖预清理提示: {err}")

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
                    task["engine"] = (
                        "Python (自动降级流式)"
                        if "aria2" in download_engine
                        else "Python (原生流式)"
                    )
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
                task["error_msg"] = str(e)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        return task_id

    def resolve_conflict(self, task_id, action):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task["conflict_action"] = action
            task["conflict_event"].set()
            return True
        return False

    def cancel_task(self, task_id):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task["cancel_flag"] = True
            task["conflict_action"] = "cancel"
            task["conflict_event"].set()

            if task.get("process_ref"):
                try:
                    task["process_ref"].terminate()
                except (ProcessLookupError, OSError):
                    pass
            task["status"] = "CANCELLED"
            task["speed"] = "0 B/s"

            if task.get("save_dir") and task.get("file_name"):
                target_file = os.path.join(task["save_dir"], task["file_name"])
                for f_path in (
                    target_file,
                    f"{target_file}.aria2",
                    f"{target_file}.downloading",
                ):
                    if os.path.isfile(f_path):
                        try:
                            os.remove(f_path)
                        except OSError:
                            pass
            return True
        return False

    def get_all_tasks(self):
        clean_tasks = []
        for t in self.tasks.values():
            t_copy = t.copy()
            t_copy.pop("process_ref", None)
            t_copy.pop("conflict_event", None)
            clean_tasks.append(t_copy)
        clean_tasks.sort(key=lambda x: x["created_at"], reverse=True)
        return clean_tasks

    def clear_finished(self):
        to_delete = [
            tid
            for tid, t in self.tasks.items()
            if t["status"] in ("COMPLETED", "FAILED", "CANCELLED")
        ]
        for tid in to_delete:
            del self.tasks[tid]
        return len(to_delete)
