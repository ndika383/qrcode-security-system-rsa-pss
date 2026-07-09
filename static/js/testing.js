 // Testing System JavaScript
class TestingSystem {
    constructor() {
        this.activeTests = new Map();
        this.initEventListeners();
        this.loadActiveTests();
        this.startPolling();
    }
    
    initEventListeners() {
        // Konfigurasi test
        document.querySelectorAll('.configure-test').forEach(button => {
            button.addEventListener('click', (e) => {
                const card = e.target.closest('.test-card');
                const testType = card.dataset.testType;
                this.openConfigModal(testType);
            });
        });
    }
    
    openConfigModal(testType) {
        // Load config template via AJAX
        fetch(`/testing/config/${testType}`)
            .then(response => response.text())
            .then(html => {
                document.getElementById('configModalBody').innerHTML = html;
                const modal = new bootstrap.Modal(document.getElementById('configModal'));
                modal.show();
                
                // Setup form submission
                document.getElementById('testConfigForm')?.addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.startTest(testType);
                    modal.hide();
                });
            });
    }
    
    startTest(testType) {
        const form = document.getElementById('testConfigForm');
        const formData = new FormData(form);
        const params = Object.fromEntries(formData);
        
        fetch('/testing/start_test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ test_type: testType, params: params })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.showNotification('Test berhasil dimulai!', 'success');
                this.loadActiveTests();
            }
        });
    }
    
    loadActiveTests() {
        fetch('/testing/active_tests')
            .then(response => response.json())
            .then(tests => {
                this.updateActiveTestsUI(tests);
            });
    }
    
    updateActiveTestsUI(tests) {
        const container = document.getElementById('activeTestsContainer');
        if (tests.length === 0) {
            container.innerHTML = `
                <div class="text-center py-5">
                    <i class="bi bi-inbox" style="font-size: 3rem; color: #ccc;"></i>
                    <p class="mt-2 text-muted">Tidak ada test yang aktif</p>
                </div>`;
            return;
        }
        
        let html = '<div class="row">';
        tests.forEach(test => {
            html += `
                <div class="col-md-6 mb-3">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h6 class="mb-0">${test.test_type}</h6>
                            <span class="badge ${test.status === 'running' ? 'bg-warning' : 'bg-success'}">
                                ${test.status}
                            </span>
                        </div>
                        <div class="card-body">
                            <div class="progress mb-2">
                                <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                     style="width: ${test.progress}%">
                                    ${test.progress}%
                                </div>
                            </div>
                            <div class="small text-muted">
                                Session: ${test.session_id}<br>
                                Started: ${new Date(test.start_time).toLocaleString()}
                            </div>
                        </div>
                    </div>
                </div>`;
        });
        html += '</div>';
        container.innerHTML = html;
    }
    
    startPolling() {
        // Poll setiap 5 detik untuk update progress
        setInterval(() => {
            this.loadActiveTests();
        }, 5000);
    }
    
    showNotification(message, type = 'info') {
        // Implement notification system
        console.log(`${type.toUpperCase()}: ${message}`);
    }
}

// Initialize ketika DOM siap
document.addEventListener('DOMContentLoaded', () => {
    window.testingSystem = new TestingSystem();
});
