import { app } from "../../scripts/app.js";
import { ICONS } from "./js/icons.js";
import { DownloaderAPI } from "./js/api.js";
import { renderTaskList } from "./js/task_card.js";
import { openTaskModal } from "./js/modal_task.js";
import { openSettingsModal } from "./js/modal_settings.js";
import { showConflictDialog } from "./js/modal_conflict.js";

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

class UniversalDownloaderUI {
    constructor() {
        this.container = null;
        this.taskListEl = null;
        this.pollTimer = null;
        this.activeConflictTasks = new Set();
        this.cachedTasksMap = new Map();
        this.serverConfig = {
            civitai_token: "",
            aria2_path: "",
            hf_use_mirror: true,
            proxy_port: ""
        };
    }

    async loadServerConfig() {
        try {
            const data = await DownloaderAPI.getConfig();
            if (data.success && data.config) {
                this.serverConfig = { ...this.serverConfig, ...data.config };
            }
        } catch (e) {
            console.warn("[Downloader] 初始化拉取配置失败:", e);
        }
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
                    <button class="ud-btn ud-btn-secondary" id="ud-btn-settings" title="全局设置">
                        ${ICONS.settings}
                    </button>
                    <button class="ud-btn ud-btn-secondary" id="ud-btn-clear-task" title="清空已完成/失败任务">
                        ${ICONS.trash}
                    </button>
                </div>
            </div>
            <div class="ud-task-list" id="ud-task-list"></div>
        `;

        this.taskListEl = this.container.querySelector("#ud-task-list");
        this.container.querySelector("#ud-btn-new-task").onclick = () => this.openTaskModal();
        this.container.querySelector("#ud-btn-settings").onclick = () => this.openSettingsModal();
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
            const data = await DownloaderAPI.getTasks();
            if (data.success) {
                this.cachedTasksMap.clear();
                data.tasks.forEach(t => this.cachedTasksMap.set(t.id, t));
                renderTaskList(this.taskListEl, data.tasks);
                this.checkConflictPrompts(data.tasks);
            }
        } catch { }
    }

    checkConflictPrompts(tasks) {
        const currentConflictIds = new Set(
            tasks.filter(t => t.status === "CONFLICT").map(t => t.id)
        );
        for (const activeId of this.activeConflictTasks) {
            if (!currentConflictIds.has(activeId)) {
                this.activeConflictTasks.delete(activeId);
            }
        }

        tasks.forEach(task => {
            if (
                task.status === "CONFLICT" &&
                task.conflict_info &&
                task.conflict_info.file_name &&
                !this.activeConflictTasks.has(task.id)
            ) {
                this.activeConflictTasks.add(task.id);
                showConflictDialog(task.id, task.conflict_info, () => this.fetchTasks());
            }
        });
    }

    async openSettingsModal() {
        await this.loadServerConfig();
        openSettingsModal({
            serverConfig: this.serverConfig,
            onSaved: (newConfig) => {
                this.serverConfig = { ...this.serverConfig, ...newConfig };
            }
        });
    }

    async openTaskModal({ isEdit = false, taskId = null, taskData = null } = {}) {
        await this.loadServerConfig();
        openTaskModal({
            isEdit,
            taskId,
            taskData,
            serverConfig: this.serverConfig,
            onSubmitted: () => this.fetchTasks()
        });
    }

    async retryTask(taskId) {
        try {
            await DownloaderAPI.retryTask(taskId);
            this.fetchTasks();
        } catch (e) {
            console.error("重试任务失败:", e);
        }
    }

    editTask(taskId) {
        const task = this.cachedTasksMap.get(taskId);
        if (!task) return;
        this.openTaskModal({ isEdit: true, taskId, taskData: task });
    }

    async cancelTask(taskId) {
        try {
            await DownloaderAPI.cancelTask(taskId);
            this.activeConflictTasks.delete(taskId);
            this.fetchTasks();
        } catch (e) {
            console.error("取消任务失败:", e);
        }
    }

    async clearFinishedTasks() {
        try {
            await DownloaderAPI.clearFinishedTasks();
            this.fetchTasks();
        } catch (e) {
            console.error("清理任务失败:", e);
        }
    }
}

const downloaderUI = new UniversalDownloaderUI();
window.__ud_cancel = (id) => downloaderUI.cancelTask(id);
window.__ud_retry = (id) => downloaderUI.retryTask(id);
window.__ud_edit = (id) => downloaderUI.editTask(id);

app.registerExtension({
    name: "Comfy.UniversalDownloader",
    async setup() {
        await downloaderUI.loadServerConfig();

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
            btn.onclick = () => downloaderUI.openTaskModal();
            topbar.appendChild(btn);
        }
    }
});