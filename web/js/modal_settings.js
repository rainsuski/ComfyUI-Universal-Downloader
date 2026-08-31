import { ICONS } from "./icons.js";
import { DownloaderAPI } from "./api.js";

export function openSettingsModal({ serverConfig = {}, onSaved = null } = {}) {
    const initialProxyPort = serverConfig.proxy_port || "";
    const initialCivitaiToken = serverConfig.civitai_token || "";
    const initialAria2Path = serverConfig.aria2_path || "";
    const initialHfMirror = serverConfig.hf_use_mirror !== undefined ? serverConfig.hf_use_mirror : true;

    const modalBackdrop = document.createElement("div");
    modalBackdrop.className = "ud-modal-backdrop";

    modalBackdrop.innerHTML = `
        <div class="ud-modal-card ud-settings-card">
            <div class="ud-modal-header">
                <div class="ud-modal-title">
                    <span style="color: #ff9900;">⚙️</span> 全局设置
                </div>
                <button class="ud-modal-close" id="ud-settings-close-btn">${ICONS.close}</button>
            </div>
            
            <div class="ud-modal-body">
                <div class="ud-form-group">
                    <label class="ud-label">代理端口 / 地址 (Proxy Port / URL)</label>
                    <input type="text" class="ud-input" id="ud-in-proxy-port" value="${initialProxyPort}" placeholder="如: 7890 或 http://127.0.0.1:7890 (留空则不开启代理)" />
                    <span class="ud-form-tip">支持配置本地代理端口（如 Clash 7890、v2ray 10809）或完整代理地址，留空则直连。</span>
                </div>

                <div class="ud-form-group">
                    <label class="ud-label">Civitai API Token (全局默认)</label>
                    <div class="ud-input-with-icon">
                        <input type="password" class="ud-input" id="ud-settings-token" value="${initialCivitaiToken}" placeholder="Civitai API Token" autocomplete="off" />
                        <button type="button" class="ud-btn-eye" id="ud-settings-toggle-token" title="显示/隐藏 Token">${ICONS.eye}</button>
                    </div>
                </div>

                <div class="ud-form-group">
                    <label class="ud-label">Aria2 可执行文件路径 (全局默认)</label>
                    <input type="text" class="ud-input" id="ud-settings-aria2-path" value="${initialAria2Path}" placeholder="留空自动探测系统 PATH 或 Motrix 路径" />
                </div>

                <div class="ud-form-group">
                    <label class="ud-label">HuggingFace 镜像加速</label>
                    <div class="ud-switch-group">
                        <label class="ud-switch-label">
                            <input type="checkbox" id="ud-settings-hf-mirror" ${initialHfMirror ? 'checked' : ''} />
                            <span>默认启用国内镜像加速 (hf-mirror.com)</span>
                        </label>
                    </div>
                </div>
            </div>

            <div class="ud-modal-footer">
                <button class="ud-btn ud-btn-secondary" id="ud-settings-cancel-btn">取消</button>
                <button class="ud-btn ud-btn-primary" id="ud-settings-save-btn">💾 保存设置</button>
            </div>
        </div>
    `;

    document.body.appendChild(modalBackdrop);

    const closeModal = () => {
        modalBackdrop.remove();
    };

    modalBackdrop.querySelector("#ud-settings-close-btn").onclick = closeModal;
    modalBackdrop.querySelector("#ud-settings-cancel-btn").onclick = closeModal;
    modalBackdrop.onclick = (e) => {
        if (e.target === modalBackdrop) closeModal();
    };

    const tokenInput = modalBackdrop.querySelector("#ud-settings-token");
    const toggleTokenBtn = modalBackdrop.querySelector("#ud-settings-toggle-token");
    toggleTokenBtn.onclick = () => {
        const isPassword = tokenInput.type === "password";
        tokenInput.type = isPassword ? "text" : "password";
        toggleTokenBtn.innerHTML = isPassword ? ICONS.eyeOff : ICONS.eye;
    };

    modalBackdrop.querySelector("#ud-settings-save-btn").onclick = async () => {
        const saveBtn = modalBackdrop.querySelector("#ud-settings-save-btn");
        saveBtn.disabled = true;
        saveBtn.innerText = "保存中...";

        const newConfig = {
            proxy_port: modalBackdrop.querySelector("#ud-in-proxy-port").value.trim(),
            civitai_token: modalBackdrop.querySelector("#ud-settings-token").value.trim(),
            aria2_path: modalBackdrop.querySelector("#ud-settings-aria2-path").value.trim(),
            hf_use_mirror: modalBackdrop.querySelector("#ud-settings-hf-mirror").checked
        };

        try {
            const res = await DownloaderAPI.saveConfig(newConfig);
            if (res && res.success) {
                if (typeof onSaved === "function") {
                    onSaved(newConfig);
                }
                closeModal();
            } else {
                alert("保存设置失败: " + (res?.error || "未知错误"));
                saveBtn.disabled = false;
                saveBtn.innerText = "💾 保存设置";
            }
        } catch (err) {
            console.error("保存设置异常:", err);
            alert("保存设置异常，请查看控制台日志");
            saveBtn.disabled = false;
            saveBtn.innerText = "💾 保存设置";
        }
    };
}