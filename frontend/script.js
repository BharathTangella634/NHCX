console.log("Page loaded. Script initialized.");

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

    const loaderElement = document.getElementById(loaderId);
    const btnElement = document.getElementById(btnId);

    if (loaderElement) loaderElement.style.display = "inline-block";
    if (btnElement) btnElement.disabled = true;

    const baseUrl = window.location.hostname === "localhost" ? "http://localhost:8000" : window.location.origin;
    const apiUrl = taskType === 'PDF2FHIR' ? `${baseUrl}/pdf2fhir` : `${baseUrl}/pdf2nhcx`;

    console.log(`API triggered: POST to ${apiUrl}`);

    try {
        const response = await fetch(apiUrl, { method: 'POST', body: formData });
        if (!response.ok) throw new Error(`Server Error: ${response.status}`);
        const data = await response.json();
        console.log(`API response received for ${taskType}. Status: ${response.status}`);
        outputElement.value = JSON.stringify(data, null, 2);
        
        if (taskType === 'PDF2FHIR') {
            const infoElement = document.getElementById('infoFHIR');
            const docTypeSpan = document.getElementById('docTypeFHIR');
            const procTimeSpan = document.getElementById('procTimeFHIR');
            if (infoElement && docTypeSpan && procTimeSpan) {
                if (data.document_type || data.processing_time) {
                    infoElement.style.display = 'block';
                    docTypeSpan.textContent = data.document_type || 'Unknown';
                    procTimeSpan.textContent = data.processing_time || 'N/A';
                } else {
                    infoElement.style.display = 'none';
                }
            }
        }
    } catch (error) {
        outputElement.value = "Error: " + error.message;
    } finally {
        if (loaderElement) loaderElement.style.display = "none";
        if (btnElement) btnElement.disabled = false;
    }
}

/**
 * Handle Validation call to Python backend
 */
async function handleValidation(taskType) {
    const outputId = taskType === 'PDF2FHIR' ? 'outputFHIR' : 'outputNHCX';
    const reportId = taskType === 'PDF2FHIR' ? 'validationReportFHIR' : 'validationReportNHCX';
    const btnId = taskType === 'PDF2FHIR' ? 'valBtnFHIR' : 'valBtnNHCX';
    const loaderId = taskType === 'PDF2FHIR' ? 'loaderValFHIR' : 'loaderValNHCX';
    
    const jsonContent = document.getElementById(outputId).value;
    const reportArea = document.getElementById(reportId);
    const btn = document.getElementById(btnId);
    const loader = document.getElementById(loaderId);

    if (!jsonContent || jsonContent.startsWith("Processing") || jsonContent.startsWith("Error")) {
        alert("No valid JSON content to validate.");
        return;
    }

    // Reset UI
    reportArea.innerHTML = "";
    loader.style.display = "inline-block";
    btn.disabled = true;

    const baseUrl = window.location.hostname === "localhost" ? "http://localhost:8000" : window.location.origin;
    
    try {
        const response = await fetch(`${baseUrl}/validate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                json_data: jsonContent,
                type: taskType // To help backend know if it's ABDM or NHCX
            })
        });

        if (!response.ok) throw new Error("Validation service unavailable");

        const result = await response.json();
        // Assuming backend returns { report: "string_of_errors" }
        displayValidationReport(result.report, reportArea);

    } catch (error) {
        reportArea.innerHTML = `<div class="error-card"><strong>Connection Error</strong>${error.message}</div>`;
    } finally {
        loader.style.display = "none";
        btn.disabled = false;
    }
}

function displayValidationReport(reportText, container) {
    if (!reportText || reportText.trim() === "") {
        container.innerHTML = `<div class="success-msg"><i class="fas fa-check-circle"></i> No validation errors found. Document is compliant.</div>`;
        return;
    }

    const lines = reportText.split('\n');
    lines.forEach(line => {
        if (line.trim()) {
            const card = document.createElement('div');
            card.className = 'error-card';
            
            // Extract the 'Error @ Path' part for bolding if available
            const match = line.match(/(Error @ .*?): (.*)/);
            if (match) {
                card.innerHTML = `<strong>${match[1]}</strong><span>${match[2]}</span>`;
            } else {
                card.textContent = line;
            }
            container.appendChild(card);
        }
    });
}

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