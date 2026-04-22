console.log("Page loaded. Script initialized.");

// ── Mixpanel Initialization ─────────────────────────────────────────────────
mixpanel.init("b175723126491e0011d3d2b4c1afea9b", {
    debug: true,
    track_pageview: true,
    persistence: "localStorage",
    autocapture: true,
    record_sessions_percent: 100,
});

// Identify anonymous user with a stable ID stored in localStorage
(function () {
    var uid = localStorage.getItem('mp_anon_id');
    if (!uid) {
        uid = crypto.randomUUID ? crypto.randomUUID() : 'anon-' + Date.now();
        localStorage.setItem('mp_anon_id', uid);
    }
    mixpanel.identify(uid);
})();
// ────────────────────────────────────────────────────────────────────────────

// ── AI Status Badge ─────────────────────────────────────────────────────────
async function checkAiStatus() {
    const badge  = document.getElementById('aiBadge');
    const textEl = document.getElementById('aiBadgeText');

    // On localhost dev: hit FastAPI ports directly
    // On production: use the reverse-proxied paths routed by nginx
    const isLocal = window.location.hostname === 'localhost';
    const base1 = isLocal ? 'http://localhost:8000' : `${window.location.origin}/pdf2abdm`;
    const base2 = isLocal ? 'http://localhost:8001' : `${window.location.origin}/pdf2nhcx`;

    // Check Gemma4 model-health on both services — this is the authoritative AI signal
    const url1 = `${base1}/model-health?model=gemma4`;
    const url2 = `${base2}/model-health?model=gemma4`;

    try {
        const [r1, r2] = await Promise.all([
            fetch(url1, { method: 'GET', signal: AbortSignal.timeout(8000) }),
            fetch(url2, { method: 'GET', signal: AbortSignal.timeout(8000) })
        ]);

        if (r1.ok && r2.ok) {
            badge.classList.remove('ai-badge-off');
            textEl.textContent = 'AI ON';
            badge.title = 'Gemma 4 is available on both services';
        } else {
            let reason = 'Gemma4 unavailable on one or more services';
            try {
                const body = !r1.ok ? await r1.json() : await r2.json();
                if (body.reason === 'auth_failed') reason = 'Vertex AI authentication failed';
                else if (body.detail)               reason = body.detail;
            } catch(e) {}
            throw new Error(reason);
        }
    } catch (err) {
        badge.classList.add('ai-badge-off');
        textEl.textContent = 'AI OFF';
        badge.title = err.message;
        console.warn('AI Status Check failed:', err.message);
    }
}

// Run on page load, then re-check every 60 s
window.addEventListener('DOMContentLoaded', () => {
    checkAiStatus();
    setInterval(checkAiStatus, 60000);
});
// ────────────────────────────────────────────────────────────────────────────

// ── Helper: build base URLs for each service ─────────────────────────────────
function getServiceBase(service) {
    // service: 'abdm' | 'nhcx'
    const isLocal = window.location.hostname === 'localhost';
    if (service === 'abdm') return isLocal ? 'http://localhost:8000' : `${window.location.origin}/pdf2abdm`;
    return isLocal ? 'http://localhost:8001' : `${window.location.origin}/pdf2nhcx`;
}


// ── Model & OCR Selection (Hidden but kept as constants for backend) ─────────
const selectedModel = 'gemma4';
const selectedOcr = { FHIR: 'auto', NHCX: 'auto' };
// ────────────────────────────────────────────────────────────────────────────


function openTab(evt, tabName) {
    var i, tabcontent, tablinks;
    tabcontent = document.getElementsByClassName("tabcontent");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    tablinks = document.getElementsByClassName("tablinks");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
    }
    document.getElementById(tabName).style.display = "block";
    evt.currentTarget.className += " active";

    // Mixpanel: track tab navigation
    mixpanel.track('Page View', {
        'page_url': window.location.href + '#' + tabName,
        'page_title': tabName,
    });
}

function updateFileName(inputId) {
    const input = document.getElementById(inputId);
    const labelId = inputId === 'fileFHIR' ? 'labelFHIR' : 'labelNHCX';
    const label = document.getElementById(labelId);
    if (input.files.length > 0) {
        label.querySelector('.file-text').textContent = input.files[0].name;
    }
}

// ── Toast Notification System ─────────────────────────────────────────────
function showToast(title, message, type = 'error', duration = 6000) {
    const container = document.getElementById('toast-container');
    const icons = { error: 'fa-circle-xmark', warn: 'fa-triangle-exclamation', info: 'fa-circle-info' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="fas ${icons[type] || icons.error} toast-icon"></i>
        <div class="toast-body">
            <div class="toast-title">${title}</div>
            <div class="toast-msg">${message}</div>
        </div>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('toast-hide');
        toast.addEventListener('animationend', () => toast.remove());
    }, duration);
}

async function processFile(taskType) {
    const fileInputId = taskType === 'PDF2FHIR' ? 'fileFHIR' : 'fileNHCX';
    const outputId = taskType === 'PDF2FHIR' ? 'outputFHIR' : 'outputNHCX';
    const loaderId = taskType === 'PDF2FHIR' ? 'loaderFHIR' : 'loaderNHCX';
    const btnId = taskType === 'PDF2FHIR' ? 'btnFHIR' : 'btnNHCX';
    const fileInput = document.getElementById(fileInputId);
    
    if (!fileInput.files.length) {
        showToast('No File Selected', 'Please select a PDF file before processing.', 'warn');
        return;
    }

    // ── Client-side file-size guard (25 MB) ───────────────────────────────
    const MAX_SIZE_MB = 25;
    const fileSizeMB = fileInput.files[0].size / (1024 * 1024);
    if (fileSizeMB > MAX_SIZE_MB) {
        showToast(
            'File Too Large',
            `"${fileInput.files[0].name}" is ${fileSizeMB.toFixed(1)} MB. Maximum allowed size is ${MAX_SIZE_MB} MB.`,
            'error'
        );
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    // Attach currently selected model and OCR engine for backend routing
    formData.append("model", selectedModel);
    formData.append("ocr_engine", selectedOcr[taskType === 'PDF2FHIR' ? 'FHIR' : 'NHCX']);

    const outputElement = document.getElementById(outputId);
    outputElement.textContent = "Processing conversion... this may take a moment.";
    if (window.Prism) Prism.highlightElement(outputElement);

    const processingLogoId = taskType === 'PDF2FHIR' ? 'processingLogoFHIR' : 'processingLogoNHCX';
    const processingLogo = document.getElementById(processingLogoId);
    if (processingLogo) processingLogo.style.display = "block";
    if (outputElement && outputElement.parentElement) outputElement.parentElement.style.display = "none";

    const loaderElement = document.getElementById(loaderId);
    const btnElement = document.getElementById(btnId);

    if (loaderElement) loaderElement.style.display = "inline-block";
    if (btnElement) btnElement.disabled = true;

    let baseUrl;
    if (window.location.hostname === "localhost") {
        baseUrl = taskType === 'PDF2FHIR' ? "http://localhost:8000" : "http://localhost:8001";
    } else {
        // If not localhost, assume an ingress routes /pdf2fhir to port 8000 and /pdf2nhcx to port 8001,
        // or we just use origin and the backend routes them properly.
        baseUrl = window.location.origin;
    }
    const apiUrl = taskType === 'PDF2FHIR' ? `${baseUrl}/pdf2abdm` : `${baseUrl}/pdf2nhcx`;

    console.log(`API triggered: POST to ${apiUrl}`);

    try {
        const response = await fetch(apiUrl, { method: 'POST', body: formData });
        if (!response.ok) {
            let errTitle = 'Processing Failed';
            let errMsg = `Server responded with status ${response.status}.`;
            try {
                const errData = await response.json();
                if (errData.detail) {
                    errTitle = errData.detail.title || errTitle;
                    errMsg = errData.detail.message || errMsg;
                } else if (errData.message) {
                    errMsg = errData.message;
                }
            } catch(_) {}
            const err = new Error(errMsg);
            err._detail = { title: errTitle, message: errMsg };
            throw err;
        }
        const data = await response.json();
        console.log(`API response received for ${taskType}. Status: ${response.status}`);
        outputElement.textContent = JSON.stringify(data, null, 2);
        if (window.Prism) Prism.highlightElement(outputElement);

        // Mixpanel: track successful conversion (the core value event)
        mixpanel.track('Conversion', {
            'Conversion Type': taskType === 'PDF2FHIR' ? 'PDF to ABDM' : 'PDF to NHCX',
            'Conversion Value': data.processing_time || 'N/A',
            'file_name': fileInput.files[0].name,
            'document_type': data.document_type || 'Unknown',
            'bundle_count': (data.bundles ? data.bundles.length : (data.bundle ? 1 : 0)),
        });
        
        const suffix = taskType === 'PDF2FHIR' ? 'FHIR' : 'NHCX';
        const infoElement = document.getElementById(`info${suffix}`);
        const docTypeSpan = document.getElementById(`docType${suffix}`); // NHCX doesn't have docType in HTML but it's fine if null
        const procTimeSpan = document.getElementById(`procTime${suffix}`);
        const bundleContainer = document.getElementById(`bundleSelectorContainer${suffix}`);
        const bundleSelect = document.getElementById(`bundleSelect${suffix}`);

        if (infoElement && procTimeSpan) {
            if (data.document_type || data.processing_time) {
                infoElement.style.display = 'block';
                if (docTypeSpan) docTypeSpan.textContent = data.document_type || 'Unknown';
                procTimeSpan.textContent = data.processing_time || 'N/A';
            } else {
                infoElement.style.display = 'none';
            }
        }

        if (bundleContainer && bundleSelect) {
            let bundles = data.bundles;
            let bundle_names = data.bundle_names;
            
            // Normalize NHCX bundle data
            if (taskType === 'PDF2NHCX' && data.bundle) {
                bundles = [data.bundle];
                bundle_names = data.bundle_names || ["NHCX Bundle"];
            }

            if (bundles && bundles.length > 0) {
                bundleContainer.style.display = 'block';
                bundleSelect.innerHTML = '';
                
                bundles.forEach((bundle, index) => {
                    const option = document.createElement('option');
                    option.value = index;
                    option.textContent = bundle_names && bundle_names[index] ? bundle_names[index] : `Bundle ${index + 1}`;
                    bundleSelect.appendChild(option);
                });

                // Set initial output to first bundle
                outputElement.textContent = JSON.stringify(bundles[0], null, 2);
                if (window.Prism) Prism.highlightElement(outputElement);

                bundleSelect.onchange = (e) => {
                    const idx = e.target.value;
                    outputElement.textContent = JSON.stringify(bundles[idx], null, 2);
                    if (window.Prism) Prism.highlightElement(outputElement);
                };
            } else {
                bundleContainer.style.display = 'none';
                bundleSelect.innerHTML = '';
            }
        }
    } catch (error) {
        let title = 'Processing Failed';
        let msg = error.message;

        // Parse structured error details from backend
        try {
            const detail = error._detail;
            if (detail) { title = detail.title || title; msg = detail.message || msg; }
        } catch(_) {}

        showToast(title, msg, 'error');
        outputElement.textContent = `Error: ${msg}`;
        if (window.Prism) Prism.highlightElement(outputElement);

        // Mixpanel: track conversion error
        mixpanel.track('Error', {
            'error_type': 'server',
            'error_message': msg,
            'page_url': window.location.href,
        });
    } finally {
        if (processingLogo) processingLogo.style.display = "none";
        if (outputElement && outputElement.parentElement) outputElement.parentElement.style.display = "block";
        if (loaderElement) loaderElement.style.display = "none";
        if (btnElement) btnElement.disabled = false;
    }
}

// Old validation functions removed in favor of fhir_validator.js


function copyToClipboard(id) {
    const textarea = document.getElementById(id);
    if (!textarea || !textarea.textContent) return;

    // Use modern Clipboard API for better compatibility and to work even if textarea is hidden
    navigator.clipboard.writeText(textarea.textContent).then(() => {
        const btn = event.target;
        const oldText = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => btn.textContent = oldText, 2000);
    }).catch(err => {
        console.error('Failed to copy: ', err);
        // Fallback for older browsers
        textarea.select();
        document.execCommand('copy');
    });
}

function downloadJSON(id) {
    const textarea = document.getElementById(id);
    if (!textarea.textContent) return;
    
    const blob = new Blob([textarea.textContent], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    
    const filename = id === 'outputFHIR' ? 'abdm_output.json' : 'nhcx_output.json';
    a.download = filename;
    
    document.body.appendChild(a);
    a.click();

    // Mixpanel: track file download
    mixpanel.track('Conversion', {
        'Conversion Type': id === 'outputFHIR' ? 'Download ABDM JSON' : 'Download NHCX JSON',
    });

    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Modal functionality
async function openModal(fileUrl) {
    const modal = document.getElementById("docModal");
    const modalBody = document.getElementById("modalBody");
    modalBody.innerHTML = '<div style="text-align:center; padding:40px;"><div class="loader" style="display:inline-block; border-top-color:var(--primary);"></div><p>Loading document...</p></div>';
    modal.style.display = "block";

    try {
        if (fileUrl.endsWith('.pdf')) {
            // For PDF, we can use an iframe
            modalBody.innerHTML = `<iframe src="${fileUrl}" width="100%" height="700px" style="border:none;"></iframe>`;
        } else if (fileUrl.endsWith('.md')) {
            // Fetch and parse Markdown
            const response = await fetch(fileUrl);
            if (!response.ok) throw new Error(`Failed to load ${fileUrl}`);
            let markdownText = await response.text();
            
            // Fix image paths for markdown loaded from assets
            if (fileUrl.startsWith('assets/')) {
                markdownText = markdownText.replace(/\!\[([^\]]*)\]\((?:\.\/)?([^)]+\.(png|jpg|jpeg|gif))\)/gi, '![$1](assets/$2)');
            }

            // Assuming marked.js is included in index.html
            if (typeof marked !== 'undefined') {
                modalBody.innerHTML = marked.parse(markdownText);
            } else {
                modalBody.innerHTML = `<pre style="white-space: pre-wrap;">${markdownText}</pre>`;
            }
        } else if (fileUrl.endsWith('.png') || fileUrl.endsWith('.jpg') || fileUrl.endsWith('.jpeg')) {
            modalBody.innerHTML = `<div style="text-align:center;"><img src="${fileUrl}" style="max-width:100%; max-height:80vh; border-radius:8px; box-shadow:0 4px 12px rgba(0,0,0,0.1);"></div>`;
        } else {
            modalBody.innerHTML = `<p style="color:red;">Unsupported file type.</p>`;
        }
    } catch (error) {
        modalBody.innerHTML = `<div class="error-card"><strong>Error Loading Document</strong><p>${error.message}</p></div>`;
    }
}

function closeModal() {
    const modal = document.getElementById("docModal");
    modal.style.display = "none";
    document.getElementById("modalBody").innerHTML = ''; // Clear content
}

// Close modal if user clicks outside of it
window.onclick = function(event) {
    const modal = document.getElementById("docModal");
    if (event.target === modal) {
        closeModal();
    }
}