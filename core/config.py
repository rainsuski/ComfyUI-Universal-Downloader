import json
import os
import logging

logger = logging.getLogger("Universal-Downloader")


class ConfigManager:
    """服务端配置文件管理类 (负责持久化存储 API Token / 镜像设置 / 自定义路径等)"""

    def __init__(self, config_dir=None):
        if config_dir is None:
            # 默认保存在插件根目录下
            config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.config_path = os.path.join(config_dir, "downloader_config.json")
        self.load_config()

    def load_config(self):
        default_cfg = {
            "civitai_token": "",
            "aria2_path": "",
            "hf_use_mirror": True,
        }
        try:
            if not os.path.isfile(self.config_path):
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(default_cfg, f, indent=4, ensure_ascii=False)
                return default_cfg

            with open(self.config_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    default_cfg.update(saved)
                return default_cfg
        except (
            OSError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            ValueError,
            TypeError,
        ) as e:
            logger.error(f"[Universal-Downloader] 读取配置文件异常: {e}")
            return default_cfg

    def save_config(self, new_cfg):
        if not isinstance(new_cfg, dict):
            return False
        current_cfg = self.load_config()
        current_cfg.update(new_cfg)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(current_cfg, f, indent=4, ensure_ascii=False)
            return True
        except (OSError, TypeError, ValueError) as e:
            logger.error(f"[Universal-Downloader] 保存配置失败: {e}")
            return False
