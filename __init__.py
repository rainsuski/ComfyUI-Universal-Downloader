import json

import aiohttp.web
from server import PromptServer

from .downloader_core import DownloaderCore

# 实例化核心调度器单例
downloader_core = DownloaderCore()
routes = PromptServer.instance.app.router

# ==================== 2.1 注册 REST API 路由 ====================


# 1. 提交下载任务
@PromptServer.instance.routes.post("/universal_downloader/api/submit")
async def handle_submit_task(request):
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return aiohttp.web.json_response(
            {"success": False, "error": f"JSON 请求体解析失败: {e}"},
            status=400,
        )

    url_or_air = data.get("url_or_air", "").strip()
    if not url_or_air:
        return aiohttp.web.json_response(
            {"success": False, "error": "资源地址 (url_or_air) 不能为空！"},
            status=400,
        )

    try:
        task_id = downloader_core.create_task(data)
        return aiohttp.web.json_response(
            {"success": True, "task_id": task_id, "status": "created"}
        )
    except (ValueError, KeyError, OSError) as e:
        return aiohttp.web.json_response(
            {"success": False, "error": f"创建任务失败: {e}"}, status=500
        )


# 2. 轮询获取任务列表与实时进度
@PromptServer.instance.routes.get("/universal_downloader/api/tasks")
async def handle_get_tasks(request):
    try:
        tasks = downloader_core.get_all_tasks()
        return aiohttp.web.json_response({"success": True, "tasks": tasks})
    except (TypeError, ValueError) as e:
        return aiohttp.web.json_response(
            {"success": False, "error": f"获取任务列表失败: {e}"}, status=500
        )


# 3. 取消指定任务
@PromptServer.instance.routes.post("/universal_downloader/api/cancel")
async def handle_cancel_task(request):
    try:
        data = await request.json()
        task_id = data.get("task_id", "")
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
        return aiohttp.web.json_response(
            {"success": False, "error": f"参数解析失败: {e}"}, status=400
        )

    if not task_id:
        return aiohttp.web.json_response(
            {"success": False, "error": "缺少 task_id 参数"}, status=400
        )

    success = downloader_core.cancel_task(task_id)
    return aiohttp.web.json_response({"success": success, "task_id": task_id})


# 4. 清除已完成/失败/已取消的任务记录
@PromptServer.instance.routes.post("/universal_downloader/api/clear_finished")
async def handle_clear_finished(request):
    try:
        cleared_count = downloader_core.clear_finished()
        return aiohttp.web.json_response(
            {"success": True, "cleared_count": cleared_count}
        )
    except (KeyError, RuntimeError) as e:
        return aiohttp.web.json_response(
            {"success": False, "error": f"清理失败: {e}"}, status=500
        )


# ==================== 2.2 前端静态资源目录声明 ====================

# 声明前端扩展目录（ComfyUI 会自动加载此目录下的 JS/CSS 脚本）
WEB_DIRECTORY = "./web"

# 导出空映射（标准 Web 扩展无需占用画布节点命名空间）
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print("[Universal-Downloader] 🚀 Web API 服务与路由已成功挂载至 ComfyUI PromptServer！")
