import { ICONS } from "./icons.js";
import { DownloaderAPI } from "./api.js";

export function showConflictDialog(taskId, conflictInfo, onResolved) {
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

    const sendDecision = async (action) => {
        dialog.remove();
        try {
            await DownloaderAPI.resolveConflict(taskId, action);
            if (typeof onResolved === "function") {
                onResolved();
            }
        } catch (e) {
            console.error("冲突决策提交失败:", e);
        }
    };

    dialog.querySelector("#ud-btn-conflict-cancel").onclick = () => sendDecision("cancel");
    dialog.querySelector("#ud-btn-conflict-rename").onclick = () => sendDecision("rename");
    dialog.querySelector("#ud-btn-conflict-overwrite").onclick = () => sendDecision("overwrite");
}