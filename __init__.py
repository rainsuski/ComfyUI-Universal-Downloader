from server import PromptServer

from .api_routes import setup_routes
from .core.task_manager import DownloaderCore

downloader_core = DownloaderCore()

# 挂载 API 路由到 ComfyUI 服务端
setup_routes(PromptServer.instance.routes, downloader_core)

WEB_DIRECTORY = "./web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
