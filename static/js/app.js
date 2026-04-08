/**
 * Squash Manager - Main JavaScript
 */

// CSRF Token helper for fetch requests
function getCsrfToken() {
    const tokenEl = document.querySelector('[name=csrfmiddlewaretoken]');
    if (tokenEl) return tokenEl.value;

    // Fallback: get from cookie
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') return value;
    }
    return '';
}

// API helper with automatic token modal handling
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
        },
    };

    const response = await fetch(url, { ...defaultOptions, ...options });
    const data = await response.json();

    // Handle token required response
    if (response.status === 401 && data.show_modal) {
        showTokenModal();
        throw new Error('Squash token required');
    }

    if (!response.ok) {
        throw new Error(data.error || data.message || 'Request failed');
    }

    return data;
}

// Token Modal
function showTokenModal() {
    const modal = document.getElementById('token-modal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function closeTokenModal() {
    const modal = document.getElementById('token-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Close modal on outside click
document.addEventListener('click', (e) => {
    const modal = document.getElementById('token-modal');
    if (modal && e.target === modal) {
        closeTokenModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeTokenModal();
    }
});

// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.3s';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

// Confirmation helper
function confirmAction(message) {
    return confirm(message);
}

// Show loading spinner
function showLoading(element) {
    const originalContent = element.innerHTML;
    element.dataset.originalContent = originalContent;
    element.innerHTML = '<span class="spinner"></span>';
    element.disabled = true;
}

// Hide loading spinner
function hideLoading(element) {
    const originalContent = element.dataset.originalContent;
    if (originalContent) {
        element.innerHTML = originalContent;
    }
    element.disabled = false;
}

// Execute test suite
async function executeSuite(suiteId) {
    const btn = event.target;
    if (!confirmAction('Are you sure you want to execute this test suite?')) {
        return;
    }

    showLoading(btn);

    try {
        const data = await apiRequest(`/suites/${suiteId}/execute/`, {
            method: 'POST',
        });

        if (data.redirect) {
            window.location.href = data.redirect;
        } else {
            window.location.reload();
        }
    } catch (error) {
        alert('Error: ' + error.message);
        hideLoading(btn);
    }
}

// Sync results to Squash
async function syncToSquash(suiteId) {
    const btn = event.target;
    showLoading(btn);

    try {
        const data = await apiRequest(`/api/suites/${suiteId}/sync/`, {
            method: 'POST',
        });

        alert(data.message || 'Results synced to Squash successfully!');
        window.location.reload();
    } catch (error) {
        alert('Error: ' + error.message);
        hideLoading(btn);
    }
}

// Scan directory for robot tests
async function scanDirectory(suiteId) {
    const btn = event.target;
    showLoading(btn);

    try {
        const data = await apiRequest(`/suites/${suiteId}/scan/`, {
            method: 'POST',
        });

        window.location.reload();
    } catch (error) {
        alert('Error: ' + error.message);
        hideLoading(btn);
    }
}

// Save mappings
async function saveMappings(suiteId) {
    const btn = event.target;
    const mappingInputs = document.querySelectorAll('.mapping-input');
    const mappings = [];

    mappingInputs.forEach(input => {
        const testName = input.dataset.testName;
        const squashId = input.value.trim();
        if (squashId) {
            mappings.push({
                robot_test_name: testName,
                squash_test_case_id: parseInt(squashId, 10),
            });
        }
    });

    showLoading(btn);

    try {
        await apiRequest(`/suites/${suiteId}/mappings/`, {
            method: 'POST',
            body: JSON.stringify({ mappings }),
        });

        alert('Mappings saved successfully!');
        window.location.reload();
    } catch (error) {
        alert('Error: ' + error.message);
        hideLoading(btn);
    }
}
