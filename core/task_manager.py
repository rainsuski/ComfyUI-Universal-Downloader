import logging
import os
import threading
import time
import urllib.error
import uuid

logger = logging.getLogger("Universal-Downloader")

from .config import ConfigManager
from .engines.aria2_engine import detect_aria2_path, run_aria2_task
from .engines.stream_engine import run_python_stream_task
from .parser import ResourceParser

try:
    import folder_paths
except ImportError:
    folder_paths = None


class DownloaderCore:
    """Universal Downloader 核心调度器单例类
    具备多源解析、进行中任务排他互斥锁、物理文件冲突隔离与即时状态断流
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
        self.config_mgr = ConfigManager()
        self.parser = ResourceParser(self.fake_ua)

    def load_config(self):
        return self.config_mgr.load_config()

    def save_config(self, new_cfg):
        return self.config_mgr.save_config(new_cfg)

    def detect_aria2_path(self, custom_path=""):
        return detect_aria2_path(custom_path)

    def parse_resource_info(
        self,
        url_or_air,
        target_type="auto",
        custom_path="",
        custom_filename="",
        civitai_token="",
        hf_use_mirror=True,
    ):
        saved_cfg = self.load_config()
        effective_civitai_token = (
            civitai_token.strip() or saved_cfg.get("civitai_token", "").strip()
        )
        return self.parser.parse_resource_info(
            url_or_air=url_or_air,
            target_type=target_type,
            custom_path=custom_path,
            custom_filename=custom_filename,
            effective_civitai_token=effective_civitai_token,
            hf_use_mirror=hf_use_mirror,
        )

    def _trigger_comfy_refresh(self):
        if folder_paths and hasattr(folder_paths, "cache"):
            try:
                folder_paths.cache.clear()
            except (AttributeError, TypeError) as e:
                logger.warning(f"[Universal-Downloader] 刷新模型缓存提示: {e}")

    def _start_task_thread(self, task_id):
        task = self.tasks[task_id]
        params = task.get("params", {})

        url_or_air = params.get("url_or_air", "")
        target_type = params.get("target_type", "auto")
        custom_path = params.get("custom_path", "")
        custom_filename = params.get("custom_filename", "")
        civitai_token = params.get("civitai_token", "")
        hf_use_mirror = params.get("hf_use_mirror", True)
        aria2_path_input = params.get("aria2_path", "")
        download_engine = params.get("download_engine", "aria2 (CLI)")

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

                # 关卡 2: 内存进行中任务排他锁（同名并发直接报错熔断）
                for tid, t in self.tasks.items():
                    if tid != task_id and t.get("status") in (
                        "DOWNLOADING",
                        "PARSING",
                        "CONFLICT",
                    ):
                        other_dir = t.get("save_dir", "")
                        other_name = t.get("file_name", "")
                        if other_dir and other_name and other_name != "正在解析资源...":
                            other_path = os.path.join(other_dir, other_name)
                            if os.path.abspath(other_path) == os.path.abspath(
                                target_file_path
                            ):
                                raise ValueError(
                                    f"目标文件正在下载中，请勿重复添加！(冲突任务ID: {tid})"
                                )

                # 关卡 3: 本地已有物理文件冲突检测
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
                        file_name = self.parser.generate_unique_filename(
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
                            logger.warning(
                                f"[Universal-Downloader] 覆盖预清理提示: {err}"
                            )

                saved_cfg = self.load_config()
                effective_aria2_path = (
                    aria2_path_input.strip() or saved_cfg.get("aria2_path", "").strip()
                )
                detected_aria2 = self.detect_aria2_path(effective_aria2_path)

                if "aria2" in download_engine and detected_aria2:
                    task["engine"] = f"aria2 ({detected_aria2})"
                    run_aria2_task(
                        task=task,
                        aria2_bin=detected_aria2,
                        final_url=final_url,
                        target_dir=target_dir,
                        file_name=file_name,
                        fake_ua=self.fake_ua,
                        on_complete_callback=self._trigger_comfy_refresh,
                    )
                else:
                    task["engine"] = (
                        "Python (自动降级流式)"
                        if "aria2" in download_engine
                        else "Python (原生流式)"
                    )
                    run_python_stream_task(
                        task=task,
                        final_url=final_url,
                        target_dir=target_dir,
                        file_name=file_name,
                        fake_ua=self.fake_ua,
                        on_complete_callback=self._trigger_comfy_refresh,
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

    def create_task(self, params):
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        cfg_update = {}
        if params.get("civitai_token", "").strip():
            cfg_update["civitai_token"] = params.get("civitai_token", "").strip()
        if params.get("aria2_path", "").strip():
            cfg_update["aria2_path"] = params.get("aria2_path", "").strip()
        if "hf_use_mirror" in params:
            cfg_update["hf_use_mirror"] = bool(params.get("hf_use_mirror"))
        if cfg_update:
            self.save_config(cfg_update)

        task = {
            "id": task_id,
            "params": dict(params),
            "url_or_air": params.get("url_or_air", ""),
            "file_name": "正在解析资源...",
            "save_dir": "",
            "category": params.get("target_type", "auto"),
            "engine": params.get("download_engine", "aria2 (CLI)"),
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
        self._start_task_thread(task_id)
        return task_id

    def retry_task(self, task_id):
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task["status"] = "PARSING"
        task["file_name"] = "正在解析资源..."
        task["progress"] = 0.0
        task["speed"] = "0 B/s"
        task["downloaded"] = "0 MB"
        task["total"] = "0 MB"
        task["error_msg"] = ""
        task["cancel_flag"] = False
        task["process_ref"] = None
        task["conflict_info"] = None
        task["conflict_action"] = None
        task["conflict_event"] = threading.Event()

        self._start_task_thread(task_id)
        return True

    def edit_task(self, task_id, new_params):
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task["params"] = dict(new_params)
        task["url_or_air"] = new_params.get("url_or_air", "")
        task["category"] = new_params.get("target_type", "auto")
        task["engine"] = new_params.get("download_engine", "aria2 (CLI)")
        task["status"] = "PARSING"
        task["file_name"] = "正在重新解析..."
        task["progress"] = 0.0
        task["speed"] = "0 B/s"
        task["downloaded"] = "0 MB"
        task["total"] = "0 MB"
        task["error_msg"] = ""
        task["cancel_flag"] = False
        task["process_ref"] = None
        task["conflict_info"] = None
        task["conflict_action"] = None
        task["conflict_event"] = threading.Event()

        self._start_task_thread(task_id)
        return True

    def resolve_conflict(self, task_id, action):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task["conflict_action"] = action
            if action == "cancel":
                task["status"] = "CANCELLED"
            else:
                task["status"] = "DOWNLOADING"
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
