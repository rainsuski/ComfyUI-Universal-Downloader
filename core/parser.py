# core/parser.py
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

try:
    import folder_paths
except ImportError:
    folder_paths = None


class ResourceParser:
    """资源地址与分类解析器 (支持 Civitai AIR、HF Mirror 加速、DiT/Diffusion 智能归类与普适直链解析)"""

    def __init__(self, fake_ua):
        self.fake_ua = fake_ua

    def parse_resource_info(
        self,
        url_or_air,
        target_type="auto",
        custom_path="",
        custom_filename="",
        effective_civitai_token="",
        hf_use_mirror=True,
    ):
        input_str = url_or_air.strip()
        if not input_str:
            raise ValueError("资源地址不能为空！")

        if not input_str.startswith(("http://", "https://", "urn:air:")):
            raise ValueError(
                "无效的资源地址！请输入以 http:// 或 https:// 开头的下载链接，或 Civitai AIR 标签"
            )

        final_url = ""
        file_name = custom_filename.strip()
        model_category = target_type

        # A. Hugging Face 解析
        if "huggingface.co" in input_str or "hf-mirror.com" in input_str:
            clean_url = input_str.split("?")[0].rstrip("/")
            if not file_name:
                file_name = clean_url.split("/")[-1]

            if "/blob/" in input_str:
                input_str = input_str.replace("/blob/", "/resolve/")

            if hf_use_mirror and "huggingface.co" in input_str:
                input_str = input_str.replace("huggingface.co", "hf-mirror.com")

            final_url = input_str

            if model_category == "auto":
                low = input_str.lower()
                if any(
                    k in low
                    for k in ["text_encoder", "text_encoders", "qwen_3", "clip", "t5"]
                ):
                    model_category = "text_encoders"
                elif "vae" in low:
                    model_category = "vae"
                elif any(
                    k in low
                    for k in [
                        "diffusion_models",
                        "diffusion_model",
                        "unet",
                        "dit",
                        "flux",
                        "anima",
                    ]
                ):
                    model_category = "diffusion_models"
                elif any(k in low for k in ["lora", "locon", "dora"]):
                    model_category = "loras"
                elif "controlnet" in low:
                    model_category = "controlnet"
                elif "upscale" in low:
                    model_category = "upscale_models"
                elif any(k in low for k in ["embedding", "textual"]):
                    model_category = "embeddings"
                elif "checkpoint" in low:
                    model_category = "checkpoints"
                else:
                    model_category = "checkpoints"

        # B. Civitai (C站) 解析
        elif "civitai." in input_str or input_str.startswith("urn:air:"):
            version_id = None
            target_file_id = None

            m_file = re.search(r"fileId=(\d+)", input_str)
            if m_file:
                target_file_id = m_file.group(1)

            air_match = re.search(
                r"urn:air:([^:]+):([^:]+):civitai:([0-9]+)(@([0-9]+))?",
                input_str,
            )
            if air_match:
                m_type = air_match.group(2).lower()
                version_id = (
                    air_match.group(5) if air_match.group(5) else air_match.group(3)
                )
                if model_category == "auto":
                    if m_type == "checkpoint":
                        model_category = "checkpoints"
                    elif m_type in ("lora", "locon", "dora"):
                        model_category = "loras"
                    elif m_type == "vae":
                        model_category = "vae"
                    elif m_type in (
                        "diffusionmodel",
                        "diffusion_models",
                        "diffusion_model",
                        "unet",
                        "dit",
                    ):
                        model_category = "diffusion_models"
                    elif m_type in ("textencoder", "text_encoders", "clip", "t5"):
                        model_category = "text_encoders"
                    elif m_type == "controlnet":
                        model_category = "controlnet"
                    elif m_type in ("upscaler", "upscale_models"):
                        model_category = "upscale_models"
                    elif m_type in ("embedding", "textualinversion", "embeddings"):
                        model_category = "embeddings"
            elif "modelVersionId=" in input_str:
                m = re.search(r"modelVersionId=(\d+)", input_str)
                if m:
                    version_id = m.group(1)
            elif "/models/" in input_str:
                m = re.search(r"/models/(\d+)", input_str)
                if m:
                    version_id = m.group(1)

            if version_id:
                api_meta_url = f"https://civitai.com/api/v1/model-versions/{version_id}"
                headers = {"User-Agent": self.fake_ua}
                if effective_civitai_token:
                    headers["Authorization"] = f"Bearer {effective_civitai_token}"

                req = urllib.request.Request(api_meta_url, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=8) as response:
                        meta = json.loads(response.read().decode())
                        files_list = meta.get("files", [])

                        matched_file = None
                        if target_file_id and files_list:
                            for f in files_list:
                                if str(f.get("id")) == str(target_file_id):
                                    matched_file = f
                                    break

                        if not matched_file and files_list:
                            matched_file = next(
                                (f for f in files_list if f.get("primary")),
                                files_list[0],
                            )

                        if not file_name and matched_file:
                            file_name = matched_file.get("name", "").strip()

                        base_download_url = meta.get(
                            "downloadUrl",
                            f"https://civitai.com/api/download/models/{version_id}",
                        )
                        if target_file_id:
                            sep = "&" if "?" in base_download_url else "?"
                            final_url = (
                                f"{base_download_url}{sep}fileId={target_file_id}"
                            )
                        else:
                            final_url = base_download_url

                        if not file_name and "name" in meta:
                            file_name = f"{meta['name']}.safetensors"

                        if model_category == "auto":
                            m_type = (
                                meta.get("model", {}).get("type")
                                or meta.get("type")
                                or ""
                            ).lower()
                            if "checkpoint" in m_type:
                                model_category = "checkpoints"
                            elif any(k in m_type for k in ["lora", "locon", "dora"]):
                                model_category = "loras"
                            elif "vae" in m_type:
                                model_category = "vae"
                            elif any(k in m_type for k in ["diffusion", "unet", "dit"]):
                                model_category = "diffusion_models"
                            elif any(
                                k in m_type
                                for k in ["text_encoder", "textencoder", "clip", "t5"]
                            ):
                                model_category = "text_encoders"
                            elif "controlnet" in m_type:
                                model_category = "controlnet"
                            elif "upscale" in m_type:
                                model_category = "upscale_models"
                            elif "embedding" in m_type or "textual" in m_type:
                                model_category = "embeddings"
                            else:
                                model_category = "checkpoints"

                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        raise ValueError(
                            f"C 站不存在 Version ID 为 [{version_id}] 的模型版本！"
                        )
                    if e.code in (401, 403):
                        raise ValueError(
                            f"C 站拒绝访问 (HTTP {e.code})，该模型可能需要设置 Civitai API Token！"
                        )
                    raise ValueError(f"请求 C 站 API 失败 (HTTP {e.code}): {e.reason}")
                except (urllib.error.URLError, TimeoutError) as e:
                    raise ValueError(f"连接 C 站 API 超时或网络异常: {e}")
                except json.JSONDecodeError:
                    raise ValueError("C 站 API 返回了非法的响应数据！")
            else:
                final_url = input_str

            if "token=" not in final_url and effective_civitai_token:
                sep = "&" if "?" in final_url else "?"
                final_url = f"{final_url}{sep}token={effective_civitai_token}"

        # C. 通用直链
        else:
            final_url = input_str
            clean_name = input_str.split("?")[0].rstrip("/").split("/")[-1]
            if not file_name:
                file_name = clean_name
            if model_category == "auto":
                model_category = "custom_path"

        # 文件名有效性检测
        file_name = file_name.strip()
        final_url = final_url.strip()

        if not file_name or file_name in (".", "/", "\\"):
            raise ValueError(
                "未能从该地址解析出合法的文件名，请在【自定义文件名】中手动指定！"
            )
        if not final_url.startswith(("http://", "https://")):
            raise ValueError("解析生成的下载直链非法，无法启动下载！")

        # D. 保存路径推导
        comfy_root = (
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            if "__file__" in globals()
            else os.getcwd()
        )

        user_path_input = custom_path.strip()

        # 模式一：明确指定为完整自定义路径
        if model_category == "custom_path" or target_type == "custom_path":
            if user_path_input:
                target_dir = (
                    os.path.abspath(user_path_input)
                    if os.path.isabs(user_path_input)
                    else os.path.abspath(os.path.join(comfy_root, user_path_input))
                )
            else:
                target_dir = (
                    os.path.join(folder_paths.models_dir, "custom_downloads")
                    if folder_paths
                    else os.path.join(comfy_root, "models", "custom_downloads")
                )
        # 模式二：分类目录模式 (checkpoints, loras, vae, diffusion_models, etc.)
        else:
            if model_category == "auto":
                model_category = "checkpoints"

            # unet 规范化为 diffusion_models
            effective_category = (
                "diffusion_models" if model_category == "unet" else model_category
            )
            base_target_dir = None

            if folder_paths:
                try:
                    possible_paths = folder_paths.get_folder_paths(effective_category)
                    if possible_paths:
                        # 优先查找真正的 diffusion_models 目录，避免被旧版兼容的 unet 别名带偏
                        for p in possible_paths:
                            if (
                                "diffusion_models"
                                in os.path.basename(os.path.normpath(p)).lower()
                            ):
                                base_target_dir = p
                                break
                        if not base_target_dir:
                            base_target_dir = possible_paths[0]
                except (KeyError, IndexError, AttributeError):
                    pass

                if not base_target_dir:
                    base_target_dir = os.path.join(
                        folder_paths.models_dir, effective_category
                    )
            else:
                base_target_dir = os.path.join(comfy_root, "models", effective_category)

            # 在分类模式下，无论用户是否输入了前导斜杠（如 /anima），均视为相对子目录拼接
            if user_path_input:
                clean_sub_path = user_path_input.strip("/\\")
                target_dir = os.path.abspath(
                    os.path.join(base_target_dir, clean_sub_path)
                )
            else:
                target_dir = base_target_dir

        os.makedirs(target_dir, exist_ok=True)
        return final_url, file_name, target_dir, model_category

    @staticmethod
    def generate_unique_filename(target_dir, file_name):
        base, ext = os.path.splitext(file_name)
        counter = 1
        new_name = f"{base} ({counter}){ext}"
        while os.path.isfile(os.path.join(target_dir, new_name)):
            counter += 1
            new_name = f"{base} ({counter}){ext}"
        return new_name
