export const DownloaderAPI = {
    async getConfig() {
        const res = await fetch("/universal_downloader/api/config");
        return await res.json();
    },

    async saveConfig(cfg) {
        const res = await fetch("/universal_downloader/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(cfg)
        });
        return await res.json();
    },

    async getTasks() {
        const res = await fetch("/universal_downloader/api/tasks");
        return await res.json();
    },

    async submitTask(payload) {
        const res = await fetch("/universal_downloader/api/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        return await res.json();
    },

    async editTask(payload) {
        const res = await fetch("/universal_downloader/api/edit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        return await res.json();
    },

    async retryTask(taskId) {
        const res = await fetch("/universal_downloader/api/retry", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ task_id: taskId })
        });
        return await res.json();
    },

    async cancelTask(taskId) {
        const res = await fetch("/universal_downloader/api/cancel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ task_id: taskId })
        });
        return await res.json();
    },

    async clearFinishedTasks() {
        const res = await fetch("/universal_downloader/api/clear_finished", {
            method: "POST"
        });
        return await res.json();
    },

    async resolveConflict(taskId, action) {
        const res = await fetch("/universal_downloader/api/resolve_conflict", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ task_id: taskId, action })
        });
        return await res.json();
    }
};