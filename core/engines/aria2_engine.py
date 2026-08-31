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


def _is_valid_executable(path):
    """校验目标文件是否存在且具有可执行属性"""
    if not path or not os.path.isfile(path):
        return False
    if sys.platform.startswith("win"):
        return path.lower().endswith(".exe") or os.access(path, os.X_OK)
    return os.access(path, os.X_OK)


def detect_aria2_path(custom_path=""):
    """跨平台智能探测系统中可用的 aria2 可执行文件绝对路径"""
    # 1. 优先使用用户在设置中指定的自定义路径
    if custom_path and custom_path.strip():
        c_path = os.path.abspath(os.path.expanduser(custom_path.strip()))
        if _is_valid_executable(c_path):
            return c_path

    # 2. 检查系统全局 PATH 环境变量
    sys_aria = shutil.which("aria2c")
    if sys_aria and _is_valid_executable(sys_aria):
        return sys_aria

    # 3. 检查当前 Python / Conda 虚拟环境
    py_env_dirs = [
        sys.prefix,
        getattr(sys, "base_prefix", sys.prefix),
    ]
    for env_dir in py_env_dirs:
        candidates = [
            os.path.join(env_dir, "bin", "aria2c"),
            os.path.join(env_dir, "bin", "aria2c.exe"),
            os.path.join(env_dir, "Scripts", "aria2c.exe"),
            os.path.join(env_dir, "aria2c.exe"),
            os.path.join(env_dir, "aria2c"),
        ]
        for cand in candidates:
            if _is_valid_executable(cand):
                return cand

    # 4. 常见包管理器与桌面客户端路径扫描
    search_paths = []

    if sys.platform.startswith("win"):
        user_profile = os.environ.get("USERPROFILE", "")
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        app_data = os.environ.get("APPDATA", "")
        prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        prog_data = os.environ.get("ProgramData", r"C:\ProgramData")
        sys_drive = os.environ.get("SystemDrive", "C:")

        search_paths.extend(
            [
                os.path.join(
                    local_app_data, r"Programs\Motrix\resources\engine\aria2c.exe"
                ),
                os.path.join(
                    app_data, r"Local\Programs\Motrix\resources\engine\aria2c.exe"
                ),
                os.path.join(prog_files, r"Motrix\resources\engine\aria2c.exe"),
                os.path.join(prog_files_x86, r"Motrix\resources\engine\aria2c.exe"),
                os.path.join(prog_files, r"Persepolis Download Manager\aria2c.exe"),
                os.path.join(prog_files_x86, r"Persepolis Download Manager\aria2c.exe"),
                os.path.join(
                    local_app_data, r"Programs\Persepolis Download Manager\aria2c.exe"
                ),
                os.path.join(user_profile, r"scoop\apps\aria2\current\aria2c.exe"),
                os.path.join(user_profile, r"scoop\shims\aria2c.exe"),
                os.path.join(prog_data, r"chocolatey\bin\aria2c.exe"),
                os.path.join(prog_data, r"chocolatey\lib\aria2\tools\aria2c.exe"),
                os.path.join(sys_drive, r"\tools\aria2\aria2c.exe"),
                os.path.join(sys_drive, r"\aria2\aria2c.exe"),
                os.path.join(user_profile, r"aria2\aria2c.exe"),
                os.path.join(user_profile, r"Downloads\aria2\aria2c.exe"),
                os.path.join(user_profile, r".aria2\aria2c.exe"),
                r"D:\tools\aria2\aria2c.exe",
                r"D:\aria2\aria2c.exe",
                r"E:\aria2\aria2c.exe",
            ]
        )

    elif sys.platform.startswith("darwin"):
        home = os.path.expanduser("~")
        search_paths.extend(
            [
                "/opt/homebrew/bin/aria2c",
                "/usr/local/bin/aria2c",
                "/opt/local/bin/aria2c",
                "/Applications/Motrix.app/Contents/Resources/engine/aria2c",
                f"{home}/Applications/Motrix.app/Contents/Resources/engine/aria2c",
                "/Applications/Persepolis Download Manager.app/Contents/Resources/aria2c",
                f"{home}/.local/bin/aria2c",
            ]
        )

    else:
        home = os.path.expanduser("~")
        search_paths.extend(
            [
                "/usr/bin/aria2c",
                "/usr/local/bin/aria2c",
                "/opt/aria2/aria2c",
                "/opt/aria2c/bin/aria2c",
                "/opt/Motrix/resources/engine/aria2c",
                f"{home}/.local/bin/aria2c",
                f"{home}/.linuxbrew/bin/aria2c",
                "/home/linuxbrew/.linuxbrew/bin/aria2c",
                "/var/lib/snapd/snap/bin/aria2c",
                f"{home}/bin/aria2c",
            ]
        )

    for path in search_paths:
        if path and _is_valid_executable(path):
            return os.path.abspath(path)

    return None


def run_aria2_task(
    task,
    aria2_bin,
    final_url,
    target_dir,
    file_name,
    fake_ua,
    proxy=None,
    on_complete_callback=None,
):
    """跨平台启动 Aria2 命令行子进程下载 (支持断点续传、全局网络代理与日志解析)"""
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
    ]

    # 全局代理参数注入
    if proxy:
        cmd.append(f"--all-proxy={proxy}")

    cmd.append(final_url)

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
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
