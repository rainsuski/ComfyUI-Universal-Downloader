import os
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
    """Python 原生流式分块下载引擎 (无需外部二进制依赖，带自动速率计算)"""
    temp_file_path = os.path.join(target_dir, f"{file_name}.downloading")
    final_file_path = os.path.join(target_dir, file_name)

    try:
        req = urllib.request.Request(final_url, headers={"User-Agent": fake_ua})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_bytes = int(resp.headers.get("Content-Length", 0))
            task["total"] = (
                f"{round(total_bytes / (1024 * 1024), 2)} MB" if total_bytes else "未知"
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
            if os.path.isfile(temp_file_path):
                os.remove(temp_file_path)
        else:
            if os.path.isfile(final_file_path):
                os.remove(final_file_path)
            os.replace(temp_file_path, final_file_path)

            task["status"] = "COMPLETED"
            task["progress"] = 100.0
            task["speed"] = "0 B/s"
            if callable(on_complete_callback):
                on_complete_callback()

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
