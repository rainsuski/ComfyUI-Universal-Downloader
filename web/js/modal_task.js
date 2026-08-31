import { ICONS } from "./icons.js";
import { DownloaderAPI } from "./api.js";

export function openTaskModal({ isEdit = false, taskId = null, taskData = null, onSubmitted = null } = {}) {
    const params = (isEdit && taskData && taskData.params) ? taskData.params : {};

    const initialUrl = params.url_or_air || (taskData ? taskData.url_or_air : "") || "";
    const initialTargetType = params.target_type || (taskData ? taskData.category : "auto") || "auto";
    const initialEngine = params.download_engine || (taskData ? taskData.engine : "aria2 (CLI)") || "aria2 (CLI)";
    const initialCustomPath = params.custom_path || "";
    const initialCustomFilename = params.custom_filename || (taskData && taskData.file_name !== "正在解析资源..." ? taskData.file_name : "") || "";

    const modalBackdrop = document.createElement("div");
    modalBackdrop.className = "ud-modal-backdrop";

    modalBackdrop.innerHTML = `
        <div class="ud-modal-card">
            <div class="ud-modal-header">
                <div class="ud-modal-title">
                    <span style="color: #ff9900;">${isEdit ? '✏️' : '⚡'}</span> 
                    ${isEdit ? '编辑下载任务 (将直接更新当前卡片)' : 'Universal Asset Downloader (全能下载器)'}
                </div>
                <button class="ud-modal-close" id="ud-modal-close-btn">${ICONS.close}</button>
            </div>
            
            <div class="ud-modal-body">
                <div class="ud-form-group">
                    <label class="ud-label"><span class="ud-req">*</span> url_or_air (资源地址)</label>
                    <input type="text" class="ud-input" id="ud-in-url" value="${initialUrl}" placeholder="支持: C站链接/AIR标签、HF链接、GitHub Release或文件直链" autofocus />
                </div>

                <div class="ud-form-row">
                    <div class="ud-form-group flex-1">
                        <label class="ud-label"><span class="ud-req">*</span> target_type (保存类型)</label>
                        <select class="ud-select" id="ud-in-target-type">
                            <option value="auto" ${initialTargetType === 'auto' ? 'selected' : ''}>auto (智能自动分类)</option>
                            <option value="loras" ${initialTargetType === 'loras' ? 'selected' : ''}>loras</option>
                            <option value="checkpoints" ${initialTargetType === 'checkpoints' ? 'selected' : ''}>checkpoints</option>
                            <option value="diffusion_models" ${initialTargetType === 'diffusion_models' ? 'selected' : ''}>diffusion_models</option>
                            <option value="vae" ${initialTargetType === 'vae' ? 'selected' : ''}>vae</option>
                            <option value="text_encoders" ${initialTargetType === 'text_encoders' ? 'selected' : ''}>text_encoders</option>
                            <option value="controlnet" ${initialTargetType === 'controlnet' ? 'selected' : ''}>controlnet</option>
                            <option value="upscale_models" ${initialTargetType === 'upscale_models' ? 'selected' : ''}>upscale_models</option>
                            <option value="custom_path" ${initialTargetType === 'custom_path' ? 'selected' : ''}>custom_path (自定义路径)</option>
                        </select>
                    </div>

                    <div class="ud-form-group flex-1">
                        <label class="ud-label"><span class="ud-req">*</span> download_engine (下载引擎)</label>
                        <select class="ud-select" id="ud-in-engine">
                            <option value="aria2 (CLI)" ${initialEngine.startsWith('aria2') ? 'selected' : ''}>aria2 (CLI Command 极速多线程)</option>
                            <option value="Python (原生流式)" ${initialEngine.startsWith('Python') ? 'selected' : ''}>Python (原生流式 无前置依赖)</option>
                        </select>
                    </div>
                </div>

                <div class="ud-form-group">
                    <label class="ud-label">custom_path (子目录 / 自定义保存路径)</label>
                    <input type="text" class="ud-input" id="ud-in-custom-path" value="${initialCustomPath}" placeholder="auto/分类模式下作为追加子目录(如: anima)；custom_path模式下为完整路径" />
                </div>

                <div class="ud-form-group">
                    <label class="ud-label">custom_filename (自定义文件名)</label>
                    <input type="text" class="ud-input" id="ud-in-custom-filename" value="${initialCustomFilename}" placeholder="留空则自动从网络/API解析真实文件名，如: my_model.safetensors" />
                </div>
            </div>

            <div class="ud-modal-footer">
                <button class="ud-btn ud-btn-secondary" id="ud-modal-cancel-btn">取消</button>
                <button class="ud-btn ud-btn-primary" id="ud-modal-submit-btn">
                    ${isEdit ? '💾 保存并重新下载' : '🚀 立即开始下载'}
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modalBackdrop);

    const closeModal = () => {
        modalBackdrop.remove();
    };

    modalBackdrop.querySelector("#ud-modal-close-btn").onclick = closeModal;
    modalBackdrop.querySelector("#ud-modal-cancel-btn").onclick = closeModal;
    modalBackdrop.onclick = (e) => {
        if (e.target === modalBackdrop) closeModal();
    };

    modalBackdrop.querySelector("#ud-modal-submit-btn").onclick = async () => {
        const url_or_air = modalBackdrop.querySelector("#ud-in-url").value.trim();
        if (!url_or_air) {
            alert("请输入资源地址 (url_or_air)!");
            return;
        }

        if (!url_or_air.startsWith("http://") && !url_or_air.startsWith("https://") && !url_or_air.startsWith("urn:air:")) {
            alert("资源地址格式不正确！请输入以 http:// 或 https:// 开头的链接，或 Civitai AIR 标签");
            return;
        }

        const payload = {
            url_or_air,
            target_type: modalBackdrop.querySelector("#ud-in-target-type").value,
            download_engine: modalBackdrop.querySelector("#ud-in-engine").value,
            custom_path: modalBackdrop.querySelector("#ud-in-custom-path").value.trim(),
            custom_filename: modalBackdrop.querySelector("#ud-in-custom-filename").value.trim()
        };

        closeModal();

        try {
            if (isEdit) {
                await DownloaderAPI.editTask({ ...payload, task_id: taskId });
            } else {
                await DownloaderAPI.submitTask(payload);
            }
            if (typeof onSubmitted === "function") {
                onSubmitted();
            }
        } catch (err) {
            console.error("提交任务异常:", err);
        }
    };
}