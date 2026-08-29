import json

import aiohttp.web


def setup_routes(routes, downloader_core):
    """注册所有下载相关的 HTTP API 路由"""

    # 0. 配置读取与保存 API
    @routes.get("/universal_downloader/api/config")
    async def handle_get_config(request):
        try:
            config = downloader_core.load_config()
            return aiohttp.web.json_response({"success": True, "config": config})
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            return aiohttp.web.json_response(
                {"success": False, "error": f"读取配置失败: {e}"}, status=500
            )

    @routes.post("/universal_downloader/api/config")
    async def handle_save_config(request):
        try:
            data = await request.json()
            success = downloader_core.save_config(data)
            return aiohttp.web.json_response({"success": success})
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            AttributeError,
            TypeError,
            OSError,
        ) as e:
            return aiohttp.web.json_response(
                {"success": False, "error": f"保存配置失败: {e}"}, status=500
            )

    # 1. 提交下载任务
    @routes.post("/universal_downloader/api/submit")
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

    # 2. 重试任务
    @routes.post("/universal_downloader/api/retry")
    async def handle_retry_task(request):
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

        success = downloader_core.retry_task(task_id)
        return aiohttp.web.json_response({"success": success, "task_id": task_id})

    # 3. 编辑并重新执行任务
    @routes.post("/universal_downloader/api/edit")
    async def handle_edit_task(request):
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

        success = downloader_core.edit_task(task_id, data)
        return aiohttp.web.json_response({"success": success, "task_id": task_id})

    # 4. 处理冲突决策 (覆盖 / 重命名 / 取消)
    @routes.post("/universal_downloader/api/resolve_conflict")
    async def handle_resolve_conflict(request):
        try:
            data = await request.json()
            task_id = data.get("task_id", "")
            action = data.get("action", "")
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
            return aiohttp.web.json_response(
                {"success": False, "error": f"参数错误: {e}"}, status=400
            )

        if not task_id or action not in ("overwrite", "rename", "cancel"):
            return aiohttp.web.json_response(
                {"success": False, "error": "无效的 task_id 或 action"},
                status=400,
            )

        success = downloader_core.resolve_conflict(task_id, action)
        return aiohttp.web.json_response({"success": success})

    # 5. 轮询任务列表
    @routes.get("/universal_downloader/api/tasks")
    async def handle_get_tasks(request):
        try:
            tasks = downloader_core.get_all_tasks()
            return aiohttp.web.json_response({"success": True, "tasks": tasks})
        except (TypeError, ValueError) as e:
            return aiohttp.web.json_response(
                {"success": False, "error": f"获取任务失败: {e}"}, status=500
            )

    # 6. 取消指定任务
    @routes.post("/universal_downloader/api/cancel")
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

    # 7. 清理历史记录
    @routes.post("/universal_downloader/api/clear_finished")
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
