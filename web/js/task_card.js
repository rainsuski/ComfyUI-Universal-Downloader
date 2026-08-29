import { ICONS } from "./icons.js";

export function renderTaskList(taskListEl, tasks) {
    if (!taskListEl) return;

    if (!tasks || tasks.length === 0) {
        taskListEl.innerHTML = `
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
            case "CONFLICT": statusBadge = `<span class="ud-badge ud-badge-warn">同名冲突(待确认)</span>`; break;
            case "DOWNLOADING": statusBadge = `<span class="ud-badge ud-badge-info">下载中</span>`; break;
            case "COMPLETED": statusBadge = `<span class="ud-badge ud-badge-success">已完成</span>`; break;
            case "FAILED": statusBadge = `<span class="ud-badge ud-badge-danger">失败</span>`; break;
            case "CANCELLED": statusBadge = `<span class="ud-badge ud-badge-muted">已取消</span>`; break;
        }

        let engineBadge = "";
        const engineStr = (task.engine || "").toLowerCase();
        if (engineStr.includes("降级") || engineStr.includes("degrade")) {
            engineBadge = `<span class="ud-badge ud-badge-engine-degrade" title="${task.engine || '未找到有效 aria2，已自动降级为 Python 原生流式'}">⚠️ 降级: Python</span>`;
        } else if (engineStr.includes("aria2")) {
            engineBadge = `<span class="ud-badge ud-badge-engine-aria" title="${task.engine || 'aria2 多线程'}">aria2</span>`;
        } else if (engineStr.includes("python")) {
            engineBadge = `<span class="ud-badge ud-badge-engine-py" title="${task.engine || 'Python 原生流式'}">Python</span>`;
        }

        let actionsHtml = "";
        if (isRunning || task.status === "CONFLICT") {
            actionsHtml = `<button class="ud-btn-cancel" onclick="window.__ud_cancel('${task.id}')">取消下载</button>`;
        } else if (task.status === "FAILED" || task.status === "CANCELLED") {
            actionsHtml = `
                <button class="ud-btn-card-action ud-btn-retry" onclick="window.__ud_retry('${task.id}')">
                    ${ICONS.retry} <span>重试</span>
                </button>
                <button class="ud-btn-card-action ud-btn-edit-card" onclick="window.__ud_edit('${task.id}')">
                    ${ICONS.edit} <span>编辑</span>
                </button>
            `;
        }

        return `
            <div class="ud-task-card" data-id="${task.id}">
                <div class="ud-card-top">
                    <div class="ud-file-name" title="${task.file_name}">${task.file_name}</div>
                    <div class="ud-badges">
                        <span class="ud-badge ud-badge-type">${task.category || 'auto'}</span>
                        ${engineBadge}
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

                ${actionsHtml ? `<div class="ud-card-actions">${actionsHtml}</div>` : ''}
            </div>
        `;
    }).join("");

    taskListEl.innerHTML = html;
}