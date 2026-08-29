# core/engines/stream_engine.py
import os
import re
import time
import urllib.error
import urllib.request


def run_python_stream_task(
    task,
    final_url,
    target_dir,
    file_name,
    fake_ua,
    on_complete_callback=None,
):
    """Python 原生流式分块下载引擎 (支持 HTTP Range 断点续传与自动降级)"""
    os.makedirs(target_dir, exist_ok=True)
    temp_file_path = os.path.join(target_dir, f"{file_name}.downloading")
    final_file_path = os.path.join(target_dir, file_name)

    downloaded = 0
    # 检查是否存在已下载的临时分块
    if os.path.isfile(temp_file_path):
        downloaded = os.path.getsize(temp_file_path)

    headers = {"User-Agent": fake_ua}
    if downloaded > 0:
        headers["Range"] = f"bytes={downloaded}-"

    try:
        req = urllib.request.Request(final_url, headers=headers)

        try:
            resp = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            # 416 表示所请求的范围无法满足（通常表示之前已全部下载完毕或范围溢出）
            if e.code == 416 and downloaded > 0:
                if os.path.isfile(final_file_path):
                    try:
                        os.remove(final_file_path)
                    except OSError:
                        pass
                os.replace(temp_file_path, final_file_path)
                task["status"] = "COMPLETED"
                task["progress"] = 100.0
                task["speed"] = "0 B/s"
                if callable(on_complete_callback):
                    on_complete_callback()
                return
            raise

        with resp:
            status_code = resp.getcode()
            total_bytes = 0
            file_mode = "wb"

            # 服务器支持断点续传 (HTTP 206 Partial Content)
            if status_code == 206:
                content_range = resp.headers.get("Content-Range", "")
                if content_range:
                    match = re.search(r"/(\d+)$", content_range)
                    if match:
                        total_bytes = int(match.group(1))
                if total_bytes == 0:
                    content_length = int(resp.headers.get("Content-Length", 0))
                    total_bytes = downloaded + content_length if content_length else 0
                file_mode = "ab"
            else:
                # 服务器不支持续传或重新请求 (HTTP 200)
                downloaded = 0
                total_bytes = int(resp.headers.get("Content-Length", 0))
                file_mode = "wb"

            task["total"] = (
                f"{round(total_bytes / (1024 * 1024), 2)} MB" if total_bytes else "未知"
            )
            task["downloaded"] = f"{round(downloaded / (1024 * 1024), 2)} MB"
            if total_bytes > 0:
                task["progress"] = round((downloaded / total_bytes) * 100, 1)
            task["status"] = "DOWNLOADING"

            chunk_size = 1024 * 1024  # 1MB 缓冲区
            last_time = time.time()
            last_downloaded = downloaded

            with open(temp_file_path, file_mode) as f:
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
                        task["speed"] = f"{round(speed_bps / (1024 * 1024), 2)} MB/s"
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
            # 取消时保留 temp_file_path，支持后续重试断点续传
        else:
            if os.path.isfile(final_file_path):
                try:
                    os.remove(final_file_path)
                except OSError:
                    pass
            os.replace(temp_file_path, final_file_path)

            task["status"] = "COMPLETED"
            task["progress"] = 100.0
            task["speed"] = "0 B/s"
            if callable(on_complete_callback):
                on_complete_callback()

    except urllib.error.HTTPError as e:
        task["status"] = "FAILED"
        task["error_msg"] = f"HTTP 错误 {e.code}: {e.reason}"
        task["speed"] = "0 B/s"
    except urllib.error.URLError as e:
        task["status"] = "FAILED"
        task["error_msg"] = f"网络连接失败: {e.reason}"
        task["speed"] = "0 B/s"
    except (TimeoutError, OSError) as e:
        task["status"] = "FAILED"
        task["error_msg"] = f"流式下载异常: {e}"
        task["speed"] = "0 B/s"
