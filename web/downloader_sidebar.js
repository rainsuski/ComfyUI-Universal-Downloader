import { app } from "../../scripts/app.js";

// 动态载入 CSS
(function loadStyles() {
    const linkId = "ud-downloader-style";
    if (!document.getElementById(linkId)) {
        const link = document.createElement("link");
        link.id = linkId;
        link.rel = "stylesheet";
        link.type = "text/css";
        link.href = new URL("./downloader_style.css", import.meta.url).href;
        document.head.appendChild(link);
    }
})();

const ICONS = {
    download: `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>`,
    plus: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>`,
    trash: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`,
    close: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`,
    empty: `<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.3"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>`,
    warn: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#eab308" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`
};

const STORAGE_KEY = "comfy_universal_downloader_config";

function loadUserConfig() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : {};
    } catch {
        return {};
    }
}

function saveUserConfig(cfg) {
    try {
        const prev = loadUserConfig();
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...prev, ...cfg }));
    } catch (e) {
        console.warn("[Downloader] 保存配置失败:", e);
    }
}

class UniversalDownloaderUI {
    constructor() {
        this.container = null;
        this.taskListEl = null;
        this.pollTimer = null;
        this.isModalOpen = false;
    }

    renderSidebar(container) {
        this.container = container;
        this.container.classList.add("ud-sidebar-panel");

        this.container.innerHTML = `
            <div class="ud-sidebar-header">
                <div class="ud-header-title">
                    <span class="ud-title-icon">${ICONS.download}</span>
                    <span class="ud-title-text">下载管理</span>
                </div>
                <div class="ud-header-actions">
                    <button class="ud-btn ud-btn-primary" id="ud-btn-new-task" title="新建下载任务">
                        ${ICONS.plus} <span>新建</span>
                    </button>
                    <button class="ud-btn ud-btn-secondary" id="ud-btn-clear-task" title="清空已完成/失败任务">
                        ${ICONS.trash}
                    </button>
                </div>
            </div>
            <div class="ud-task-list" id="ud-task-list"></div>
        `;

        this.taskListEl = this.container.querySelector("#ud-task-list");
        this.container.querySelector("#ud-btn-new-task").onclick = () => this.openNewTaskModal();
        this.container.querySelector("#ud-btn-clear-task").onclick = () => this.clearFinishedTasks();

        this.startPolling();
    }

    startPolling() {
        if (this.pollTimer) clearInterval(this.pollTimer);
        this.fetchTasks();
        this.pollTimer = setInterval(() => this.fetchTasks(), 1000);
    }

    async fetchTasks() {
        if (!this.taskListEl) return;
        try {
            const res = await fetch("/universal_downloader/api/tasks");
            const data = await res.json();
            if (data.success) {
                this.renderTaskList(data.tasks);
            }
        } catch { }
    }

    renderTaskList(tasks) {
        if (!tasks || tasks.length === 0) {
            this.taskListEl.innerHTML = `
                <div class="ud-empty-state">
                    <div class="ud-empty-icon">${ICONS.empty}</div>
                    <div class="ud-empty-title">暂无下载任务</div>
                    <div class="ud-empty-desc">点击上方【+ 新建】按钮添加模型或资产下载任务。</div>
                </div>
            `;
            return;
        }

        const html = tasks.map(task => {
            const isRunning = task.status === "DOWNLOADING" || task.status === "PARSING";
            const progress = Number(task.progress || 0).toFixed(1);

            let statusBadge = "";
            switch (task.status) {
                case "PARSING": statusBadge = `<span class="ud-badge ud-badge-warn">解析中...</span>`; break;
                case "DOWNLOADING": statusBadge = `<span class="ud-badge ud-badge-info">下载中</span>`; break;
                case "COMPLETED": statusBadge = `<span class="ud-badge ud-badge-success">已完成</span>`; break;
                case "FAILED": statusBadge = `<span class="ud-badge ud-badge-danger">失败</span>`; break;
                case "CANCELLED": statusBadge = `<span class="ud-badge ud-badge-muted">已取消</span>`; break;
            }

            return `
                <div class="ud-task-card" data-id="${task.id}">
                    <div class="ud-card-top">
                        <div class="ud-file-name" title="${task.file_name}">${task.file_name}</div>
                        <div class="ud-badges">
                            <span class="ud-badge ud-badge-type">${task.category || 'auto'}</span>
                            ${statusBadge}
                        </div>
                    </div>
                    
                    <div class="ud-progress-bar-bg">
                        <div class="ud-progress-bar-fill ${task.status.toLowerCase()}" style="width: ${progress}%"></div>
                    </div>
                    
                    <div class="ud-card-meta">
                        <span class="ud-meta-speed">${isRunning ? task.speed : (task.status === 'COMPLETED' ? '100%' : '0 B/s')}</span>
                        <span class="ud-meta-size">${task.downloaded || '0 MB'} / ${task.total || '未知'}</span>
                    </div>

                    ${task.error_msg ? `<div class="ud-card-error" title="${task.error_msg}">⚠️ ${task.error_msg}</div>` : ''}

                    ${isRunning ? `
                        <div class="ud-card-actions">
                            <button class="ud-btn-cancel" onclick="window.__ud_cancel('${task.id}')">取消下载</button>
                        </div>
                    ` : ''}
                </div>
            `;
        }).join("");

        this.taskListEl.innerHTML = html;
    }

    async cancelTask(taskId) {
        try {
            await fetch("/universal_downloader/api/cancel", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ task_id: taskId })
            });
            this.fetchTasks();
        } catch (e) {
            console.error("取消任务失败:", e);
        }
    }

    async clearFinishedTasks() {
        try {
            await fetch("/universal_downloader/api/clear_finished", { method: "POST" });
            this.fetchTasks();
        } catch (e) {
            console.error("清理任务失败:", e);
        }
    }

    // 真正执行提交
    async executeSubmit(payload) {
        try {
            const res = await fetch("/universal_downloader/api/submit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                this.fetchTasks();
                return true;
            } else {
                alert(`提交失败: ${data.error}`);
                return false;
            }
        } catch (err) {
            alert(`请求网络异常: ${err}`);
            return false;
        }
    }

    // 弹出同名文件冲突确认框
    showConflictDialog(conflictInfo, onConfirm) {
        const dialog = document.createElement("div");
        dialog.className = "ud-modal-backdrop ud-conflict-backdrop";

        dialog.innerHTML = `
            <div class="ud-modal-card ud-conflict-card">
                <div class="ud-conflict-header">
                    ${ICONS.warn}
                    <div class="ud-conflict-title">检测到本地同名文件！</div>
                </div>
                <div class="ud-conflict-body">
                    <p>目标路径已存在同名文件：</p>
                    <div class="ud-conflict-filepath" title="${conflictInfo.full_path}">${conflictInfo.file_name}</div>
                    <div class="ud-conflict-meta">本地大小: <strong>${conflictInfo.file_size}</strong></div>
                    <p style="margin-top: 10px; color: #a1a1aa; font-size: 12px;">请选择处理方式：</p>
                </div>
                <div class="ud-conflict-footer">
                    <button class="ud-btn ud-btn-secondary" id="ud-btn-conflict-cancel">取消</button>
                    <button class="ud-btn ud-btn-rename" id="ud-btn-conflict-rename">自动重命名 (1)</button>
                    <button class="ud-btn ud-btn-danger" id="ud-btn-conflict-overwrite">覆盖原文件</button>
                </div>
            </div>
        `;

        document.body.appendChild(dialog);

        const closeDialog = () => dialog.remove();

        dialog.querySelector("#ud-btn-conflict-cancel").onclick = closeDialog;
        dialog.querySelector("#ud-btn-conflict-rename").onclick = () => {
            closeDialog();
            onConfirm("rename");
        };
        dialog.querySelector("#ud-btn-conflict-overwrite").onclick = () => {
            closeDialog();
            onConfirm("overwrite");
        };
    }

    // 弹出新建任务弹窗
    openNewTaskModal() {
        if (this.isModalOpen) return;
        this.isModalOpen = true;

        const config = loadUserConfig();
        const modalBackdrop = document.createElement("div");
        modalBackdrop.className = "ud-modal-backdrop";

        modalBackdrop.innerHTML = `
            <div class="ud-modal-card">
                <div class="ud-modal-header">
                    <div class="ud-modal-title">
                        <span style="color: #ff9900;">⚡</span> Universal Asset Downloader (全能下载器)
                    </div>
                    <button class="ud-modal-close" id="ud-modal-close-btn">${ICONS.close}</button>
                </div>
                
                <div class="ud-modal-body">
                    <div class="ud-form-group">
                        <label class="ud-label"><span class="ud-req">*</span> url_or_air (资源地址)</label>
                        <input type="text" class="ud-input" id="ud-in-url" placeholder="支持: C站AIR/URL/ID、HF链接、GitHub Release或文件直链" autofocus />
                    </div>

                    <div class="ud-form-row">
                        <div class="ud-form-group flex-1">
                            <label class="ud-label"><span class="ud-req">*</span> target_type (保存类型)</label>
                            <select class="ud-select" id="ud-in-target-type">
                                <option value="auto">auto (智能自动分类)</option>
                                <option value="loras">loras</option>
                                <option value="checkpoints">checkpoints</option>
                                <option value="diffusion_models">diffusion_models</option>
                                <option value="vae">vae</option>
                                <option value="text_encoders">text_encoders</option>
                                <option value="controlnet">controlnet</option>
                                <option value="upscale_models">upscale_models</option>
                                <option value="custom_path">custom_path (自定义路径)</option>
                            </select>
                        </div>

                        <div class="ud-form-group flex-1">
                            <label class="ud-label"><span class="ud-req">*</span> download_engine (下载引擎)</label>
                            <select class="ud-select" id="ud-in-engine">
                                <option value="aria2 (CLI)">aria2 (CLI Command 极速多线程)</option>
                                <option value="Python (原生流式)">Python (原生流式 无前置依赖)</option>
                            </select>
                        </div>
                    </div>

                    <div class="ud-form-group">
                        <label class="ud-label">custom_path (自定义保存路径)</label>
                        <input type="text" class="ud-input" id="ud-in-custom-path" placeholder="custom_path 时生效，支持相对路径(如: custom_nodes/xxx)或绝对路径" />
                    </div>

                    <div class="ud-form-group">
                        <label class="ud-label">custom_filename (自定义文件名)</label>
                        <input type="text" class="ud-input" id="ud-in-custom-filename" placeholder="留空则自动从网络/API解析真实文件名，如: my_model.safetensors" />
                    </div>

                    <div class="ud-form-group">
                        <label class="ud-label">aria2_path (自定义 aria2 可执行文件路径)</label>
                        <input type="text" class="ud-input" id="ud-in-aria2-path" value="${config.aria2_path || ''}" placeholder="留空自动探测系统PATH或Motrix路径，亦可手动指定" />
                    </div>

                    <div class="ud-form-group">
                        <label class="ud-label">civitai_token (Civitai API Token)</label>
                        <input type="text" class="ud-input" id="ud-in-token" value="${config.civitai_token || ''}" placeholder="Civitai API Token (civitai下载必填)" />
                    </div>

                    <div class="ud-form-group">
                        <label class="ud-label">hf_use_mirror (HF 镜像加速)</label>
                        <div class="ud-switch-group">
                            <label class="ud-switch-label">
                                <input type="checkbox" id="ud-in-hf-mirror" ${config.hf_use_mirror !== false ? 'checked' : ''} />
                                <span>启用国内镜像加速 (hf-mirror.com)</span>
                            </label>
                        </div>
                    </div>
                </div>

                <div class="ud-modal-footer">
                    <button class="ud-btn ud-btn-secondary" id="ud-modal-cancel-btn">取消</button>
                    <button class="ud-btn ud-btn-primary" id="ud-modal-submit-btn">🚀 立即开始下载</button>
                </div>
            </div>
        `;

        document.body.appendChild(modalBackdrop);

        const closeModal = () => {
            modalBackdrop.remove();
            this.isModalOpen = false;
        };

        modalBackdrop.querySelector("#ud-modal-close-btn").onclick = closeModal;
        modalBackdrop.querySelector("#ud-modal-cancel-btn").onclick = closeModal;
        modalBackdrop.onclick = (e) => {
            if (e.target === modalBackdrop) closeModal();
        };

        modalBackdrop.querySelector("#ud-modal-submit-btn").onclick = async () => {
            const url_or_air = modalBackdrop.querySelector("#ud-in-url").value.trim();
            const civitai_token = modalBackdrop.querySelector("#ud-in-token").value.trim();

            if (!url_or_air) {
                alert("请输入资源地址 (url_or_air)!");
                return;
            }

            const payload = {
                url_or_air,
                target_type: modalBackdrop.querySelector("#ud-in-target-type").value,
                download_engine: modalBackdrop.querySelector("#ud-in-engine").value,
                custom_path: modalBackdrop.querySelector("#ud-in-custom-path").value.trim(),
                custom_filename: modalBackdrop.querySelector("#ud-in-custom-filename").value.trim(),
                aria2_path: modalBackdrop.querySelector("#ud-in-aria2-path").value.trim(),
                civitai_token: civitai_token,
                hf_use_mirror: modalBackdrop.querySelector("#ud-in-hf-mirror").checked,
                conflict_action: "overwrite"
            };

            saveUserConfig({
                civitai_token: payload.civitai_token,
                aria2_path: payload.aria2_path,
                hf_use_mirror: payload.hf_use_mirror
            });

            // 1. 发起预检
            try {
                const preRes = await fetch("/universal_downloader/api/precheck", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const preData = await preRes.json();

                if (!preData.success) {
                    alert(`解析失败: ${preData.error}`);
                    return;
                }

                // 2. 如果存在同名文件，弹出确认对话框
                if (preData.result && preData.result.exists) {
                    this.showConflictDialog(preData.result, async (action) => {
                        payload.conflict_action = action;
                        const ok = await this.executeSubmit(payload);
                        if (ok) closeModal();
                    });
                } else {
                    // 3. 不存在冲突，直接提交下载
                    const ok = await this.executeSubmit(payload);
                    if (ok) closeModal();
                }
            } catch (err) {
                alert(`预检网络异常: ${err}`);
            }
        };
    }
}

const downloaderUI = new UniversalDownloaderUI();
window.__ud_cancel = (id) => downloaderUI.cancelTask(id);

app.registerExtension({
    name: "Comfy.UniversalDownloader",
    async setup() {
        if (app.extensionManager && typeof app.extensionManager.registerSidebarTab === "function") {
            app.extensionManager.registerSidebarTab({
                id: "universal-downloader-tab",
                icon: "pi pi-download",
                title: "下载",
                tooltip: "Universal Downloader (模型资产下载器)",
                type: "custom",
                render: (el) => downloaderUI.renderSidebar(el)
            });
        }
        const topbar = document.querySelector(".comfy-menu") || document.querySelector("#comfy-topbar");
        if (topbar && !document.querySelector("#ud-topbar-btn")) {
            const btn = document.createElement("button");
            btn.id = "ud-topbar-btn";
            btn.innerHTML = `⚡ 下载`;
            btn.className = "comfy-btn";
            btn.style.cssText = "font-weight: bold; color: #ff9900;";
            btn.onclick = () => downloaderUI.openNewTaskModal();
            topbar.appendChild(btn);
        }
    }
});