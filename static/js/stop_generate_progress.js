(function () {
    'use strict';

    function resolveTaskId() {
        const fromUrl = new URLSearchParams(window.location.search).get('task_id');
        if (fromUrl) {
            return fromUrl;
        }

        const scripts = Array.from(document.scripts || []);
        for (const script of scripts) {
            const content = script.textContent || '';
            const match = content.match(/const\s+taskId\s*=\s*['"]([^'"]+)['"]/);
            if (match && match[1] && !match[1].includes('{{')) {
                return match[1];
            }
        }

        return null;
    }

    const taskId = resolveTaskId();
    const backButton = document.getElementById('backButton');
    let stopButton = document.getElementById('stopButton');

    if (!taskId) {
        return;
    }

    if (!stopButton && backButton) {
        const backColumn = backButton.closest('[class*="col-md-"]');
        const actionRow = backButton.closest('.row');

        if (!backColumn || !actionRow) {
            return;
        }

        const resultColumn = backColumn.nextElementSibling;
        backColumn.classList.remove('col-md-6');
        backColumn.classList.add('col-md-4');

        if (resultColumn) {
            resultColumn.classList.remove('col-md-6');
            resultColumn.classList.add('col-md-4');
        }

        const stopColumn = document.createElement('div');
        stopColumn.className = 'col-md-4 mb-2';
        stopColumn.innerHTML = [
            '<button type="button" class="btn btn-danger w-100" id="stopButton" style="display: none;">',
            '<i class="fas fa-stop-circle me-2"></i>Hentikan Generate',
            '</button>'
        ].join('');
        backColumn.insertAdjacentElement('afterend', stopColumn);
        stopButton = document.getElementById('stopButton');
    }

    if (!stopButton) {
        return;
    }

    stopButton.setAttribute('type', 'button');
    let stopRequested = false;

    function addLog(message, type) {
        const logMessages = document.getElementById('logMessages');
        if (!logMessages) {
            return;
        }

        const alertClass = type === 'error' ? 'alert-danger' :
            type === 'warning' ? 'alert-warning' :
            type === 'success' ? 'alert-success' : 'alert-info';
        const icon = type === 'error' ? 'fa-exclamation-circle' :
            type === 'warning' ? 'fa-exclamation-triangle' :
            type === 'success' ? 'fa-check-circle' : 'fa-info-circle';

        const logItem = document.createElement('div');
        logItem.className = `alert ${alertClass} mb-2`;
        logItem.innerHTML = `<small><i class="fas ${icon} me-2"></i>${message}</small>`;
        logMessages.prepend(logItem);

        while (logMessages.children.length > 20) {
            logMessages.lastElementChild.remove();
        }
    }

    function setStoppingState() {
        stopButton.style.display = '';
        stopButton.disabled = true;
        stopButton.innerHTML = '<i class="fas fa-hourglass-half me-2"></i>Menghentikan...';
    }

    function setRunningState() {
        stopButton.style.display = '';
        stopButton.disabled = false;
        stopButton.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Hentikan Generate';
    }

    function setHiddenState() {
        stopButton.style.display = 'none';
        stopButton.disabled = false;
    }

    async function refreshStopState() {
        try {
            const response = await fetch(`/api/generate_progress_status?task_id=${encodeURIComponent(taskId)}`, {
                cache: 'no-store',
                credentials: 'same-origin'
            });

            if (!response.ok) {
                return;
            }

            const data = await response.json();

            if (data.is_complete || data.error) {
                setHiddenState();
                return;
            }

            if (data.is_stopped || stopRequested) {
                setStoppingState();
                return;
            }

            if (data.is_processing) {
                setRunningState();
            } else {
                setHiddenState();
            }
        } catch (error) {
            // Polling utama halaman sudah menampilkan error koneksi; script ini cukup diam.
        }
    }

    async function stopGenerateProcess() {
        if (!confirm('Hentikan proses generate QR Code massal sekarang?')) {
            return;
        }

        stopRequested = true;
        setStoppingState();
        addLog('Permintaan stop dikirim...', 'warning');

        try {
            const response = await fetch(`/api/stop_generate_process?task_id=${encodeURIComponent(taskId)}`, {
                cache: 'no-store',
                credentials: 'same-origin'
            });
            const data = await response.json();

            if (data.error) {
                stopRequested = false;
                setRunningState();
                addLog(`Error menghentikan proses: ${data.error}`, 'error');
                return;
            }

            addLog(data.status || 'Proses sedang dihentikan...', 'warning');
            refreshStopState();
        } catch (error) {
            stopRequested = false;
            setRunningState();
            addLog(`Error menghentikan proses: ${error.message}`, 'error');
        }
    }

    if (stopButton.dataset.stopGenerateHandler !== 'ready') {
        stopButton.addEventListener('click', stopGenerateProcess);
        stopButton.dataset.stopGenerateHandler = 'ready';
    }
    refreshStopState();
    window.setInterval(refreshStopState, 3000);
}());
