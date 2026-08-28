<div align="center">

# ⚡ ComfyUI Universal Downloader

**现代化侧边栏模型资产极速下载管理扩展 | A Modern, Native Download Manager Extension for ComfyUI**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-Extension-orange.svg)](https://github.com/comfyanonymous/ComfyUI)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

[简体中文](./README.md) | [English](./README_EN.md)

</div>
---

## 核心特性

### 1. 全来源格式解析

* **Civitai (C 站)**：
  * 支持 **AIR 编码**（如 `urn:air:anima:lora:civitai:2736763@3077360`，该格式无法获取准确的变体ID，仅推荐在没有多个变体的情况下使用）；
  * 支持 **模型页面 URL**、**API 下载直链**；
* **Hugging Face**：
  * 自动将浏览器复制的 `/blob/` 页面链接转换为 `/resolve/` 下载直链；
  * 内置 **国内镜像加速 (`hf-mirror.com`)** 一键开关。
* **GitHub Releases / 通用直链**：支持任意软件、插件压缩包及第三方直链高速下载。

### 2. 下载引擎

* **主力引擎：`aria2 (CLI)`**
* **路径**：
  $$
  \text{用户手动指定路径} \longrightarrow \text{系统全局环境变量 PATH} \longrightarrow \text{自动嗅探 Windows 下 Motrix 内置引擎} \longrightarrow \text{自动优雅降级}
  $$
* **`Python 原生流式`**
  * 零前置依赖，开箱即用；
  * 采用 `.downloading` 临时后缀的**原子写入机制（Atomic Write）**，下载未完成或异常中断绝不产生损坏假模型。

### 3. 模型自动归类

* 自动识别模型类型并分流存入对应目录：`checkpoints`、`loras`、`vae`、`text_encoders`、`diffusion_models`、`controlnet`、`upscale_models`（亦支持自定义绝对/相对路径）；

---

## 安装方法

### 方法一：Git Clone (推荐)

进入 ComfyUI 的 `custom_nodes` 目录并拉取仓库：

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/rainsuski/ComfyUI-Universal-Downloader.git
```

### 方法二：手动安装

1. 点击 GitHub 仓库右上角 `Code` $\to$ `Download ZIP`；
2. 解压并将文件夹重命名为 `ComfyUI-Universal-Downloader`；
3. 将该文件夹放置在 `ComfyUI/custom_nodes/` 下；
4. 重启 ComfyUI。

---

## 使用示范

1. 重启 ComfyUI 后，在浏览器按 `Ctrl + F5` 刷新页面；
2. 点击屏幕最左侧导航栏的 **`📥 下载`** 选项卡展开抽屉；
3. 点击顶部的 **`【+ 新建】`** 按钮打开弹窗，在资源地址框贴入以下任意格式即可：

| 来源类型                | 支持的输入格式示例                                                                                     | 自动归类目标                |
| :---------------------- | :----------------------------------------------------------------------------------------------------- | :-------------------------- |
| **C站 AIR 编码**  | `urn:air:anima:lora:civitai:2736763@3077360`                                                         | `models/loras`            |
| **C站网页 URL**   | `https://civitai.com/models/2736763?modelVersionId=3077360`                                          | 自动识别                    |
| **Hugging Face**  | `https://huggingface.co/circlestone-labs/Anima/blob/main/split_files/vae/qwen_image_vae.safetensors` | `models/vae`              |
| **GitHub / 直链** | `https://github.com/comfyanonymous/ComfyUI/releases/download/.../file.zip`                           | `models/custom_downloads` |

---

## 常见问题

#### Q1: 提示 `⚠️ 未探测到有效 aria2c，已自动无缝降级为 Python 原生流式下载`？

* **说明**：系统未检测到 `aria2c` 执行程序，但依然可以通过 Python 原生下载完成任务。
* **提升下载速度建议**：
  * **如果你装了 Motrix**：在弹窗的 `aria2_path` 里填入 Motrix 自带的 `aria2c.exe` 路径（通常在 `C:\Users\你的用户名\AppData\Local\Programs\Motrix\resources\engine\aria2c.exe`）；
  * **全局安装**：
    * Windows: 在 PowerShell 运行 `winget install aria2.aria2`
    * Linux: `apt update && apt install -y aria2`
    * macOS: `brew install aria2`

#### Q2: 下载 Civitai 提示 401 Unauthorized 或下载失败？

* **解决办法**：在新建弹窗的 `civitai_token` 输入框中填入你在 Civitai 个人设置里生成的 **API Token**（只需填一次，浏览器会自动记住）。

---

## 📄 开源协议 (License)

MIT License
