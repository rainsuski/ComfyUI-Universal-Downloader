# core/engines/aria2_engine.py
import os
import re
import shutil
import subprocess
import sys

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


def detect_aria2_path(custom_path=""):
    """探测系统中可用的 aria2 可执行文件绝对路径"""
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


def run_aria2_task(
    task,
    aria2_bin,
    final_url,
    target_dir,
    file_name,
    fake_ua,
    on_complete_callback=None,
):
    """启动 Aria2 命令行子进程下载并实时解析日志输出 (支持断点续传)"""
    os.makedirs(target_dir, exist_ok=True)

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
        f"--header=User-Agent: {fake_ua}",
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
            # 取消时保留进度文件与分块文件，支持重试续传
        elif return_code == 0:
            task["status"] = "COMPLETED"
            task["progress"] = 100.0
            task["speed"] = "0 B/s"
            if callable(on_complete_callback):
                on_complete_callback()
        else:
            task["status"] = "FAILED"
            task["speed"] = "0 B/s"
            reason = ARIA2_ERROR_CODES.get(return_code, f"进程退出代码 {return_code}")
            task["error_msg"] = f"下载失败: {reason}"

    except (OSError, subprocess.SubprocessError) as e:
        task["status"] = "FAILED"
        task["speed"] = "0 B/s"
        task["error_msg"] = f"执行 aria2 失败: {e}"
