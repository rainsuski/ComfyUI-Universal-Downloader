import json

import aiohttp.web
from server import PromptServer

from .downloader_core import DownloaderCore

downloader_core = DownloaderCore()
routes = PromptServer.instance.app.router


# 1. 预检同名文件冲突
@PromptServer.instance.routes.post("/universal_downloader/api/precheck")
async def handle_precheck(request):
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return aiohttp.web.json_response(
            {"success": False, "error": f"JSON 解析失败: {e}"}, status=400
        )

    try:
        check_res = downloader_core.precheck_conflict(data)
        return aiohttp.web.json_response({"success": True, "result": check_res})
    except (ValueError, KeyError, OSError) as e:
        return aiohttp.web.json_response(
            {"success": False, "error": str(e)}, status=400
        )


# 2. 提交下载任务
@PromptServer.instance.routes.post("/universal_downloader/api/submit")
async def handle_submit_task(request):
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return aiohttp.web.json_response(
            {"success": False, "error": f"JSON 解析失败: {e}"}, status=400
        )

    url_or_air = data.get("url_or_air", "").strip()
    if not url_or_air:
        return aiohttp.web.json_response(
            {"success": False, "error": "资源地址不能为空！"}, status=400
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


# 3. 轮询任务列表
@PromptServer.instance.routes.get("/universal_downloader/api/tasks")
async def handle_get_tasks(request):
    try:
        tasks = downloader_core.get_all_tasks()
        return aiohttp.web.json_response({"success": True, "tasks": tasks})
    except (TypeError, ValueError) as e:
        return aiohttp.web.json_response(
            {"success": False, "error": f"获取任务失败: {e}"}, status=500
        )


# 4. 取消指定任务
@PromptServer.instance.routes.post("/universal_downloader/api/cancel")
async def handle_cancel_task(request):
    try:
        data = await request.json()
        task_id = data.get("task_id", "")
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
        return aiohttp.web.json_response(
            {"success": False, "error": f"参数错误: {e}"}, status=400
        )

    if not task_id:
        return aiohttp.web.json_response(
            {"success": False, "error": "缺少 task_id"}, status=400
        )

    success = downloader_core.cancel_task(task_id)
    return aiohttp.web.json_response({"success": success, "task_id": task_id})


# 5. 清理历史记录
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


WEB_DIRECTORY = "./web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
