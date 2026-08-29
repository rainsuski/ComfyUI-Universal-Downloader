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
  * 支持 **AIR 编码**（如 `urn:air:anima:lora:civitai:2736763@3077360`）；
  * 支持 **模型页面 URL**、**API 下载直链**（支持携带 Token 自动匹配精准版本文件）。
* **Hugging Face**：
  * 自动将浏览器复制的 `/blob/` 页面预览链接转换为 `/resolve/` 下载直链；
* **GitHub Releases / 通用直链**：支持任意软件、节点压缩包及第三方直链高速下载。

### 2. 双下载引擎与智能调度

* **主力引擎：`aria2 (CLI)`**（多线程极速并发）
  * **智能跨平台探测链路**：
    $$
    \text{自定义路径} \longrightarrow \text{系统 PATH} \longrightarrow \text{Conda/Python 虚拟环境} \longrightarrow \text{常见客户端/包管理器内核 (Motrix等)} \longrightarrow \text{优雅降级}
    $$
* **兜底引擎：`Python 原生流式`**
  * 零前置依赖，开箱即用；
  * 采用 `.downloading` 临时后缀的**原子写入机制（Atomic Write）**，下载未完成绝不产生损坏假模型。

### 3. 断点续传

* **全链路断点续传**：支持 HTTP Range 协议与 aria2 进度控制，无论是手动中止、网络波动还是下载失败，均可随时重试并继续下载；

### 4. 模型智能归类与缓存刷新

* 自动识别模型类别并分流存入对应目录：`checkpoints`、`loras`、`vae`、`text_encoders`、`diffusion_models`、`controlnet`、`upscale_models`（亦支持自定义绝对/相对子路径）；
* 下载完成后**自动触发 ComfyUI 模型缓存刷新**，无需重启服务即可在节点加载器中立刻选到新模型。

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

* **说明**：插件会自动扫描系统环境变量、Conda 虚拟环境及常用客户端（如 Motrix 等），若均未安装则会自动降级为 Python 原生下载（依然支持断点续传）。
* **如需获得多线程极限下载速度**，可通过以下任意方式安装 aria2：
  * **Windows**：在终端运行 `winget install aria2.aria2` 或安装 [Motrix](https://motrix.app/)（插件会自动探测其内置内核）；
  * **Linux**：`apt update && apt install -y aria2` 或 `conda install -c conda-forge aria2`；
  * **macOS**：`brew install aria2`。

#### Q2: 下载 Civitai 提示 401 Unauthorized 或下载失败？

* **解决办法**：在新建任务弹窗的 `civitai_token` 输入框中填入你在 Civitai 个人设置里生成的 **API Token**（输入一次即可，服务端会自动持久化记住）。

---

## 📄 开源协议 (License)

[MIT License](./LICENSE)