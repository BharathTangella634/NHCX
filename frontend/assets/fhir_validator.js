/**
 * FHIR Validator — Client-side FHIR R4 validation
 * Uses HL7's public FHIR validator API (validator.fhir.org)
 * and annotates a line-numbered JSON viewer with error tiles.
 */

// ─── Helpers ─────────────────────────────────────────────────────────────────

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ─── Line-Numbered JSON Viewer ────────────────────────────────────────────────

// Registry: textareaId → { renderLines }
const _lnvRegistry = {};

/**
 * Build a line-numbered JSON viewer for a given textarea element.
 */
function buildLineNumberedViewer(textareaEl) {
    textareaEl.style.display = 'none';

    const wrapper = document.createElement('div');
    wrapper.className = 'lnv-wrapper';
    wrapper.setAttribute('data-for', textareaEl.id);

    const gutterEl = document.createElement('div');
    gutterEl.className = 'lnv-gutter';

    const codeEl = document.createElement('div');
    codeEl.className = 'lnv-code';

    wrapper.appendChild(gutterEl);
    wrapper.appendChild(codeEl);

    textareaEl.insertAdjacentElement('afterend', wrapper);

    function renderLines(jsonText, errorMap) {
        const lines = jsonText.split('\n');
        gutterEl.innerHTML = '';
        codeEl.innerHTML = '';

        lines.forEach((line, i) => {
            const lineNum = i + 1;
            const errs = errorMap ? (errorMap[lineNum] || []) : [];
            const hasError = errs.some(e => e.severity === 'error' || e.severity === 'fatal');
            const hasWarn  = errs.some(e => e.severity === 'warning');
            const hasInfo  = errs.some(e => e.severity === 'information');

            // Gutter cell
            const gutterCell = document.createElement('div');
            gutterCell.className = 'lnv-line-gutter';
            if (hasError)      gutterCell.classList.add('lnv-gutter-error');
            else if (hasWarn)  gutterCell.classList.add('lnv-gutter-warn');
            else if (hasInfo)  gutterCell.classList.add('lnv-gutter-info');

            const numSpan = document.createElement('span');
            numSpan.className = 'lnv-linenum';
            numSpan.textContent = lineNum;
            gutterCell.appendChild(numSpan);

            if (errs.length > 0) {
                const badge = document.createElement('span');
                badge.className = 'lnv-badge';
                badge.textContent = errs.length;
                if (hasError)     badge.classList.add('lnv-badge-error');
                else if (hasWarn) badge.classList.add('lnv-badge-warn');
                else              badge.classList.add('lnv-badge-info');
                gutterCell.appendChild(badge);
            }

            gutterEl.appendChild(gutterCell);

            // Code cell
            const codeCell = document.createElement('div');
            codeCell.className = 'lnv-line-code';
            if (hasError)      codeCell.classList.add('lnv-line-error');
            else if (hasWarn)  codeCell.classList.add('lnv-line-warn');
            else if (hasInfo)  codeCell.classList.add('lnv-line-info');
            codeCell.id = `lnv-line-${textareaEl.id}-${lineNum}`;

            const codeSpan = document.createElement('span');
            codeSpan.className = 'lnv-code-text';
            codeSpan.textContent = line.length ? line : ' ';
            codeCell.appendChild(codeSpan);

            // Inline floating error tile on the line
            if (errs.length > 0) {
                const tile = document.createElement('span');
                tile.className = 'lnv-inline-tile';
                if (hasError)     tile.classList.add('lnv-tile-error');
                else if (hasWarn) tile.classList.add('lnv-tile-warn');
                else              tile.classList.add('lnv-tile-info');

                const icon   = hasError ? '✖' : hasWarn ? '⚠' : 'ℹ';
                const msg    = errs[0].message || '';
                const short  = msg.length > 90 ? msg.substring(0, 90) + '…' : msg;
                tile.innerHTML = `${icon} ${escapeHtml(short)}${errs.length > 1 ? ` <em>(+${errs.length - 1} more)</em>` : ''}`;
                codeCell.appendChild(tile);
            }

            codeEl.appendChild(codeCell);
        });
    }

    // Sync scroll
    codeEl.addEventListener('scroll', () => {
        gutterEl.scrollTop = codeEl.scrollTop;
    });

    return { wrapper, renderLines };
}

function initLineNumberedViewer(textareaId) {
    const ta = document.getElementById(textareaId);
    if (!ta || _lnvRegistry[textareaId]) return;
    const { renderLines } = buildLineNumberedViewer(ta);
    _lnvRegistry[textareaId] = { renderLines };
    if (ta.value) renderLines(ta.value, {});
}

function updateLineNumberedViewer(textareaId, errorMap) {
    const ta = document.getElementById(textareaId);
    if (!ta) return;
    if (!_lnvRegistry[textareaId]) initLineNumberedViewer(textareaId);
    const { renderLines } = _lnvRegistry[textareaId];
    renderLines(ta.value, errorMap || {});
}

// ─── FHIR Validation via HL7 Public API ──────────────────────────────────────

async function validateFhirJson(jsonString) {
    const VALIDATOR_URL = 'https://validator.fhir.org/validate';

    // Quick local JSON parse check
    try { JSON.parse(jsonString); }
    catch (e) {
        return { issues: [{ severity: 'fatal', message: `Invalid JSON: ${e.message}`, location: '$', line: 1 }] };
    }

    const encoded = btoa(unescape(encodeURIComponent(jsonString)));

    const payload = {
        cliContext: { sv: '4.0.1', profiles: [] },
        filesToValidate: [{ fileName: 'resource.json', fileContent: encoded, fileType: 'json' }]
    };

    const response = await fetch(VALIDATOR_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(60000)
    });

    if (!response.ok) {
        const text = await response.text();
        throw new Error(`Validator API ${response.status}: ${text.substring(0, 200)}`);
    }

    const result = await response.json();
    const issues = [];

    for (const outcome of (result.outcomes || [])) {
        for (const issue of (outcome?.issues?.issue || [])) {
            // Extract row from extensions
            let line = null;
            for (const ext of (issue.extension || [])) {
                if (ext.url && ext.url.toLowerCase().includes('row') && ext.valueInteger != null) {
                    line = ext.valueInteger;
                }
            }
            const loc = (issue.location || []).join(' > ');
            issues.push({
                severity: issue.severity || 'information',
                message: issue.diagnostics || issue.details?.text || 'Unknown issue',
                location: loc || '$',
                line
            });
        }
    }

    return { issues, raw: result };
}

function findLineByPath(lines, path) {
    if (!path) return null;
    const parts = path.split(/[.\[\]>]+/).filter(Boolean).reverse();
    for (const part of parts) {
        if (!part || /^\d+$/.test(part)) continue;
        const key = `"${part}"`;
        for (let i = 0; i < lines.length; i++) {
            if (lines[i].includes(key)) return i + 1;
        }
    }
    return null;
}

function buildErrorMap(issues, jsonString) {
    const errorMap = {};
    const lines = jsonString.split('\n');

    for (const issue of issues) {
        let lineNum = issue.line;
        if (!lineNum && issue.location && issue.location !== '$') {
            lineNum = findLineByPath(lines, issue.location);
        }
        const key = lineNum || 1;
        if (!errorMap[key]) errorMap[key] = [];
        errorMap[key].push(issue);
    }
    return errorMap;
}

// ─── UI: Validation Report Panel ─────────────────────────────────────────────

function renderFhirReport(issues, container, outputId) {
    if (issues.length === 0) {
        container.innerHTML = `
            <div class="val-success">
                <span class="val-success-icon">✔</span>
                <div>
                    <strong>FHIR Validation Passed</strong>
                    <p>No structural or conformance errors found. This resource is valid FHIR R4.</p>
                </div>
            </div>`;
        return;
    }

    const bySev = { fatal: [], error: [], warning: [], information: [] };
    for (const issue of issues) {
        (bySev[issue.severity] || bySev['information']).push(issue);
    }

    const totalErrors = bySev.fatal.length + bySev.error.length;
    const totalWarn   = bySev.warning.length;
    const totalInfo   = bySev.information.length;

    let html = `
        <div class="val-summary-bar">
            <span class="val-summary-title"><i class="fas fa-stethoscope"></i> FHIR R4 Validation Report</span>
            <div class="val-summary-counts">
                ${totalErrors > 0 ? `<span class="val-count-badge val-count-error">✖ ${totalErrors} Error${totalErrors !== 1 ? 's' : ''}</span>` : ''}
                ${totalWarn   > 0 ? `<span class="val-count-badge val-count-warn">⚠ ${totalWarn} Warning${totalWarn !== 1 ? 's' : ''}</span>` : ''}
                ${totalInfo   > 0 ? `<span class="val-count-badge val-count-info">ℹ ${totalInfo} Note${totalInfo !== 1 ? 's' : ''}</span>` : ''}
            </div>
        </div>
        <div class="val-issues-list">`;

    for (const sev of ['fatal', 'error', 'warning', 'information']) {
        for (const issue of bySev[sev]) {
            const cls  = (sev === 'fatal' || sev === 'error') ? 'val-tile-error' : sev === 'warning' ? 'val-tile-warn' : 'val-tile-info';
            const icon = (sev === 'fatal' || sev === 'error') ? '✖' : sev === 'warning' ? '⚠' : 'ℹ';
            const sevLabel = sev.charAt(0).toUpperCase() + sev.slice(1);
            const lineRef = issue.line
                ? `<a href="#" class="val-tile-lineref" onclick="scrollToViewerLine('${outputId}', ${issue.line}); return false;"><i class="fas fa-map-marker-alt"></i> Line ${issue.line}</a>`
                : '';

            html += `
                <div class="val-issue-tile ${cls}">
                    <div class="val-tile-header">
                        <span class="val-tile-icon">${icon}</span>
                        <span class="val-tile-sev">${sevLabel}</span>
                        ${lineRef}
                    </div>
                    <div class="val-tile-msg">${escapeHtml(issue.message)}</div>
                    ${issue.location && issue.location !== '$' ? `<div class="val-tile-loc"><i class="fas fa-code-branch"></i> <code>${escapeHtml(issue.location)}</code></div>` : ''}
                </div>`;
        }
    }

    html += `</div>`;
    container.innerHTML = html;
}

function scrollToViewerLine(textareaId, lineNum) {
    const lineEl = document.getElementById(`lnv-line-${textareaId}-${lineNum}`);
    if (lineEl) {
        lineEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        lineEl.classList.add('lnv-line-highlight-flash');
        setTimeout(() => lineEl.classList.remove('lnv-line-highlight-flash'), 2000);
    }
}

// ─── Main Entry Point ─────────────────────────────────────────────────────────

async function runFhirValidation(taskType) {
    console.log(`[FHIR Validator] Starting validation for ${taskType}...`);
    const outputId = taskType === 'PDF2FHIR' ? 'outputFHIR' : 'outputNHCX';
    const reportId = taskType === 'PDF2FHIR' ? 'validationReportFHIR' : 'validationReportNHCX';
    const btnId    = taskType === 'PDF2FHIR' ? 'valBtnFHIR' : 'valBtnNHCX';
    const loaderId = taskType === 'PDF2FHIR' ? 'loaderValFHIR' : 'loaderValNHCX';

    const ta       = document.getElementById(outputId);
    const reportEl = document.getElementById(reportId);
    const btn      = document.getElementById(btnId);
    const loader   = document.getElementById(loaderId);

    const jsonText = ta ? ta.value.trim() : '';
    console.log(`[FHIR Validator] Content length: ${jsonText.length}`);

    if (!jsonText || jsonText.startsWith('Processing') || jsonText.startsWith('Error')) {
        console.warn(`[FHIR Validator] No valid content found in ${outputId}`);
        reportEl.innerHTML = `<div class="val-report-empty"><i class="fas fa-info-circle"></i> No FHIR JSON output found. Please run the conversion first.</div>`;
        return;
    }

    // Ensure viewer is initialized before validation
    initLineNumberedViewer(outputId);

    reportEl.innerHTML = `
        <div class="val-loading">
            <div class="val-spinner"></div>
            <span>Validating against FHIR R4 specification<br><small>Using HL7 FHIR Validator API…</small></span>
        </div>`;
    if (loader) loader.style.display = 'inline-block';
    if (btn)    btn.disabled = true;

    try {
        const { issues } = await validateFhirJson(jsonText);
        console.log(`[FHIR Validator] Received ${issues.length} issues.`);
        const errorMap = buildErrorMap(issues, jsonText);

        updateLineNumberedViewer(outputId, errorMap);
        renderFhirReport(issues, reportEl, outputId);

        // Scroll report into view
        reportEl.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
        console.error(`[FHIR Validator] Error during validation:`, err);
        reportEl.innerHTML = `
            <div class="val-issue-tile val-tile-error">
                <div class="val-tile-header"><span class="val-tile-icon">✖</span><span class="val-tile-sev">Connection Error</span></div>
                <div class="val-tile-msg">${escapeHtml(err.message)}</div>
                <div class="val-tile-loc">Unable to reach the HL7 FHIR validator. Please check your network connection and try again.</div>
            </div>`;
    } finally {
        if (loader) loader.style.display = 'none';
        if (btn)    btn.disabled = false;
    }
}

// ─── Watch textarea updates from processFile() ───────────────────────────────

function watchTextareaForViewer(textareaId) {
    const ta = document.getElementById(textareaId);
    if (!ta) return;
    let lastValue = ta.value;

    console.log(`[FHIR Validator] Starting watcher for ${textareaId}...`);

    // Immediate check if content already exists
    if (ta.value.trim() && !ta.value.startsWith('Processing') && !ta.value.startsWith('Error')) {
        initLineNumberedViewer(textareaId);
    }

    setInterval(() => {
        if (ta.value !== lastValue) {
            console.log(`[FHIR Validator] Change detected in ${textareaId}`);
            lastValue = ta.value;
            const v = ta.value.trim();
            if (v && !v.startsWith('Processing') && !v.startsWith('Error')) {
                updateLineNumberedViewer(textareaId, {});
                // Clear old report on new data
                const suffix = textareaId === 'outputFHIR' ? 'FHIR' : 'NHCX';
                const rpt = document.getElementById(`validationReport${suffix}`);
                if (rpt) rpt.innerHTML = '';
            } else if (!v) {
                // If emptied, maybe revert to textarea or keep empty viewer?
                // For now, if empty, we just hide the viewer and show textarea
                const registry = _lnvRegistry[textareaId];
                if (registry) {
                    const wrapper = document.querySelector(`.lnv-wrapper[data-for="${textareaId}"]`);
                    if (wrapper) wrapper.style.display = 'none';
                    ta.style.display = 'block';
                    delete _lnvRegistry[textareaId];
                }
            }
        }
    }, 400);
}

window.addEventListener('load', () => {
    console.log("[FHIR Validator] Window loaded. Initializing watchers...");
    watchTextareaForViewer('outputFHIR');
    watchTextareaForViewer('outputNHCX');
});
