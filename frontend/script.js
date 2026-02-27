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

async function processFile(taskType) {
    const fileInputId = taskType === 'PDF2FHIR' ? 'fileFHIR' : 'fileNHCX';
    const outputId = taskType === 'PDF2FHIR' ? 'outputFHIR' : 'outputNHCX';
    const fileInput = document.getElementById(fileInputId);
    
    if (!fileInput.files.length) {
        alert("Please select a file first.");
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append("file", file);

    const outputElement = document.getElementById(outputId);
    outputElement.value = "Processing...";

    // Determine API endpoint based on task. We assume these are available.
    const host = window.location.hostname || "127.0.0.1";
    let apiUrl = '';
    if (taskType === 'PDF2FHIR') {
        apiUrl = `http://${host}:8000/pdf2fhir`; // replace with actual backend API if different
    } else {
        apiUrl = `http://${host}:8000/process/nhcx`; // replace with actual backend API if different
    }

    try {
        const response = await fetch(apiUrl, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        outputElement.value = JSON.stringify(data, null, 2);
    } catch (error) {
        outputElement.value = "Error processing file: " + error.message + "\n\n(Note: Ensure API endpoints are properly configured and CORS is enabled if needed)";
        console.error("Error:", error);
    }
}

function validateJson(outputId) {
    const outputElement = document.getElementById(outputId);
    const resultElementId = outputId === 'outputFHIR' ? 'validationResultFHIR' : 'validationResultNHCX';
    const resultElement = document.getElementById(resultElementId);
    
    const text = outputElement.value;
    
    if (!text.trim()) {
        resultElement.textContent = "Nothing to validate.";
        resultElement.className = "validation-result error";
        return;
    }

    try {
        JSON.parse(text);
        resultElement.textContent = "Valid JSON format.";
        resultElement.className = "validation-result success";
    } catch (e) {
        resultElement.textContent = "Invalid JSON: " + e.message;
        resultElement.className = "validation-result error";
    }
}