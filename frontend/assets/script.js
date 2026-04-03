console.log("Page loaded. Script initialized.");

// ── AI Status Badge ─────────────────────────────────────────────────────────
async function checkAiStatus() {
    const badge  = document.getElementById('aiBadge');
    const textEl = document.getElementById('aiBadgeText');

    // On localhost dev: hit FastAPI ports directly
    // On production: use the reverse-proxied paths (/pdf2fhir & /pdf2nhcx)
    //   which are routed by nginx to the backend containers
    const isLocal = window.location.hostname === 'localhost';
    const health1 = isLocal ? 'http://localhost:8000/health' : `${window.location.origin}/pdf2fhir/health`;
    const health2 = isLocal ? 'http://localhost:8001/health' : `${window.location.origin}/pdf2nhcx/health`;

    try {
        const [r1, r2] = await Promise.all([
            fetch(health1, { method: 'GET', signal: AbortSignal.timeout(5000) }),
            fetch(health2, { method: 'GET', signal: AbortSignal.timeout(5000) })
        ]);
        if (r1.ok && r2.ok) {
            badge.classList.remove('ai-badge-off');
            textEl.textContent = 'AI ON';
        } else {
            throw new Error('one or more services down');
        }
    } catch {
        badge.classList.add('ai-badge-off');
        textEl.textContent = 'AI OFF';
    }
}

// Run health check on load
window.addEventListener('DOMContentLoaded', checkAiStatus);
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
}

function updateFileName(inputId) {
    const input = document.getElementById(inputId);
    const labelId = inputId === 'fileFHIR' ? 'labelFHIR' : 'labelNHCX';
    const label = document.getElementById(labelId);
    if (input.files.length > 0) {
        label.querySelector('.file-text').textContent = input.files[0].name;
    }
}

async function processFile(taskType) {
    const fileInputId = taskType === 'PDF2FHIR' ? 'fileFHIR' : 'fileNHCX';
    const outputId = taskType === 'PDF2FHIR' ? 'outputFHIR' : 'outputNHCX';
    const loaderId = taskType === 'PDF2FHIR' ? 'loaderFHIR' : 'loaderNHCX';
    const btnId = taskType === 'PDF2FHIR' ? 'btnFHIR' : 'btnNHCX';
    const fileInput = document.getElementById(fileInputId);
    
    if (!fileInput.files.length) {
        alert("Please select a PDF file first.");
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    const outputElement = document.getElementById(outputId);
    outputElement.value = "Processing conversion... this may take a moment.";

    const processingLogoId = taskType === 'PDF2FHIR' ? 'processingLogoFHIR' : 'processingLogoNHCX';
    const processingLogo = document.getElementById(processingLogoId);
    if (processingLogo) processingLogo.style.display = "block";
    if (outputElement) outputElement.style.display = "none";

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
    const apiUrl = taskType === 'PDF2FHIR' ? `${baseUrl}/pdf2fhir` : `${baseUrl}/pdf2nhcx`;

    console.log(`API triggered: POST to ${apiUrl}`);

    try {
        const response = await fetch(apiUrl, { method: 'POST', body: formData });
        if (!response.ok) throw new Error(`Server Error: ${response.status}`);
        const data = await response.json();
        console.log(`API response received for ${taskType}. Status: ${response.status}`);
        outputElement.value = JSON.stringify(data, null, 2);
        
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
                outputElement.value = JSON.stringify(bundles[0], null, 2);

                bundleSelect.onchange = (e) => {
                    const idx = e.target.value;
                    outputElement.value = JSON.stringify(bundles[idx], null, 2);
                };
            } else {
                bundleContainer.style.display = 'none';
                bundleSelect.innerHTML = '';
            }
        }
    } catch (error) {
        outputElement.value = "Error: " + error.message;
    } finally {
        if (processingLogo) processingLogo.style.display = "none";
        if (outputElement) outputElement.style.display = "block";
        if (loaderElement) loaderElement.style.display = "none";
        if (btnElement) btnElement.disabled = false;
    }
}

// Old validation functions removed in favor of fhir_validator.js


function copyToClipboard(id) {
    const textarea = document.getElementById(id);
    if (!textarea.value) return;
    textarea.select();
    document.execCommand('copy');
    const btn = event.target;
    const oldText = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => btn.textContent = oldText, 2000);
}

function downloadJSON(id) {
    const textarea = document.getElementById(id);
    if (!textarea.value) return;
    
    const blob = new Blob([textarea.value], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    
    const filename = id === 'outputFHIR' ? 'abdm_output.json' : 'nhcx_output.json';
    a.download = filename;
    
    document.body.appendChild(a);
    a.click();
    
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