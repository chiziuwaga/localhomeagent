/**
 * Security Features for Local Home Agent
 * LA3: Safety & Security Implementation
 * 
 * Features:
 * - LA3.1: Emergency mode / panic button
 * - LA3.3: Backup/restore functionality
 * - LA3.4: Security audit log viewer
 * - LA3.5: Session timeout with warning
 * - LA3.6: Two-factor auth for admin actions
 */

const SecurityManager = {
    // Session timeout settings (30 minutes default)
    SESSION_TIMEOUT: 30 * 60 * 1000,
    WARNING_BEFORE: 5 * 60 * 1000, // 5 minutes warning
    
    lastActivity: Date.now(),
    timeoutWarningShown: false,
    sessionTimer: null,
    warningTimer: null,

    /**
     * Initialize all security features
     */
    init: function() {
        this.initSessionTimeout();
        this.initPanicButton();
        this.init2FAModal();
        console.log('[Security] Security manager initialized');
    },

    // ========================================
    // LA3.1: Emergency Mode / Panic Button
    // ========================================

    emergencyMode: false,

    initPanicButton: function() {
        // Add panic button to all pages
        const panicBtn = document.createElement('button');
        panicBtn.id = 'panic-button';
        panicBtn.className = 'panic-button';
        panicBtn.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>EMERGENCY</span>
        `;
        panicBtn.onclick = () => this.activateEmergencyMode();
        document.body.appendChild(panicBtn);

        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .panic-button {
                position: fixed;
                bottom: 80px;
                right: 20px;
                background: #ff3333;
                color: white;
                border: 3px solid #000;
                border-radius: 50px;
                padding: 12px 20px;
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 900;
                text-transform: uppercase;
                font-size: 12px;
                cursor: pointer;
                z-index: 9998;
                box-shadow: 4px 4px 0 #000;
                transition: all 0.1s ease;
            }
            .panic-button:hover {
                transform: translate(-2px, -2px);
                box-shadow: 6px 6px 0 #000;
            }
            .panic-button:active {
                transform: translate(2px, 2px);
                box-shadow: 2px 2px 0 #000;
            }
            .panic-button.active {
                animation: pulse-emergency 0.5s infinite;
                background: #cc0000;
            }
            @keyframes pulse-emergency {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.05); }
            }
            
            .emergency-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(255, 0, 0, 0.9);
                z-index: 10000;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                color: white;
            }
            .emergency-overlay h1 {
                font-size: 48px;
                font-weight: 900;
                margin-bottom: 20px;
                text-transform: uppercase;
            }
            .emergency-overlay p {
                font-size: 18px;
                margin-bottom: 30px;
                max-width: 400px;
                text-align: center;
            }
            .emergency-actions {
                display: flex;
                gap: 20px;
            }
            .emergency-actions button {
                padding: 15px 30px;
                font-size: 16px;
                font-weight: 700;
                border: 3px solid #000;
                cursor: pointer;
            }
            .deactivate-btn {
                background: white;
                color: #000;
            }
            .call-btn {
                background: #000;
                color: white;
            }
        `;
        document.head.appendChild(style);
    },

    activateEmergencyMode: async function() {
        if (this.emergencyMode) return;
        
        // Confirm activation
        if (!confirm('⚠️ ACTIVATE EMERGENCY MODE?\n\nThis will:\n• Stop all automations\n• Lock all doors\n• Turn on all lights\n• Alert property manager')) {
            return;
        }

        this.emergencyMode = true;
        document.getElementById('panic-button').classList.add('active');

        // Call emergency API
        try {
            const response = await fetch('/api/emergency/activate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            console.log('[Security] Emergency mode activated:', data);
        } catch (error) {
            console.error('[Security] Emergency activation failed:', error);
        }

        // Show emergency overlay
        this.showEmergencyOverlay();
    },

    showEmergencyOverlay: function() {
        const overlay = document.createElement('div');
        overlay.id = 'emergency-overlay';
        overlay.className = 'emergency-overlay';
        overlay.innerHTML = `
            <h1>🚨 Emergency Mode Active</h1>
            <p>All automations have been stopped. Doors are locked and lights are on. The property manager has been notified.</p>
            <div class="emergency-actions">
                <button class="deactivate-btn" onclick="SecurityManager.deactivateEmergency()">
                    Deactivate (Admin PIN Required)
                </button>
                <button class="call-btn" onclick="SecurityManager.callEmergency()">
                    📞 Call Emergency Services
                </button>
            </div>
            <p style="margin-top: 40px; font-size: 14px; opacity: 0.8;">
                Activated at: ${new Date().toLocaleTimeString()}
            </p>
        `;
        document.body.appendChild(overlay);
    },

    deactivateEmergency: async function() {
        // Require 2FA to deactivate
        const pin = await this.request2FA('Deactivate Emergency Mode');
        if (!pin) return;

        try {
            const response = await fetch('/api/emergency/deactivate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin })
            });
            const data = await response.json();
            
            if (data.success) {
                this.emergencyMode = false;
                document.getElementById('panic-button').classList.remove('active');
                document.getElementById('emergency-overlay')?.remove();
                alert('Emergency mode deactivated');
            } else {
                alert('Invalid PIN. Emergency mode remains active.');
            }
        } catch (error) {
            console.error('[Security] Deactivation failed:', error);
            alert('Deactivation failed. Please try again.');
        }
    },

    callEmergency: function() {
        if (confirm('Call emergency services (911)?')) {
            window.location.href = 'tel:911';
        }
    },

    // ========================================
    // LA3.3: Backup/Restore Functionality
    // ========================================

    exportBackup: async function() {
        try {
            const response = await fetch('/api/backup/export');
            const data = await response.json();
            
            // Create downloadable file
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `local-home-agent-backup-${new Date().toISOString().split('T')[0]}.json`;
            a.click();
            URL.revokeObjectURL(url);
            
            console.log('[Security] Backup exported successfully');
            return true;
        } catch (error) {
            console.error('[Security] Backup export failed:', error);
            alert('Backup export failed: ' + error.message);
            return false;
        }
    },

    importBackup: async function(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = async (e) => {
                try {
                    const data = JSON.parse(e.target.result);
                    
                    // Require 2FA for restore
                    const pin = await this.request2FA('Restore Backup');
                    if (!pin) {
                        reject(new Error('2FA required'));
                        return;
                    }

                    const response = await fetch('/api/backup/import', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ backup: data, pin })
                    });
                    
                    const result = await response.json();
                    if (result.success) {
                        alert('Backup restored successfully! The page will reload.');
                        window.location.reload();
                        resolve(true);
                    } else {
                        reject(new Error(result.error || 'Restore failed'));
                    }
                } catch (error) {
                    reject(error);
                }
            };
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.readAsText(file);
        });
    },

    showBackupModal: function() {
        const modal = document.createElement('div');
        modal.className = 'security-modal';
        modal.id = 'backup-modal';
        modal.innerHTML = `
            <div class="security-modal-content">
                <h2>💾 Backup & Restore</h2>
                <p>Export your settings, devices, and configurations to a JSON file.</p>
                
                <div class="backup-actions">
                    <button class="export-btn" onclick="SecurityManager.exportBackup()">
                        📤 Export Backup
                    </button>
                    
                    <div class="import-section">
                        <label for="import-file" class="import-btn">
                            📥 Import Backup
                        </label>
                        <input type="file" id="import-file" accept=".json" 
                            onchange="SecurityManager.handleImportFile(this.files[0])" hidden>
                    </div>
                </div>
                
                <div class="backup-info">
                    <h3>What's included:</h3>
                    <ul>
                        <li>✅ Home settings</li>
                        <li>✅ Device configurations</li>
                        <li>✅ User list</li>
                        <li>✅ Automation rules</li>
                        <li>✅ Scene definitions</li>
                    </ul>
                </div>
                
                <button class="close-modal-btn" onclick="document.getElementById('backup-modal').remove()">
                    Close
                </button>
            </div>
        `;
        document.body.appendChild(modal);
        this.addModalStyles();
    },

    handleImportFile: async function(file) {
        if (!file) return;
        
        if (!confirm('⚠️ This will overwrite your current settings. Continue?')) {
            return;
        }

        try {
            await this.importBackup(file);
        } catch (error) {
            alert('Import failed: ' + error.message);
        }
    },

    // ========================================
    // LA3.4: Security Audit Log Viewer
    // ========================================

    showAuditLog: async function() {
        const modal = document.createElement('div');
        modal.className = 'security-modal';
        modal.id = 'audit-log-modal';
        modal.innerHTML = `
            <div class="security-modal-content audit-log-content">
                <h2>📋 Security Audit Log</h2>
                <div class="audit-filters">
                    <select id="audit-filter-level">
                        <option value="">All Levels</option>
                        <option value="low">Low Risk</option>
                        <option value="medium">Medium Risk</option>
                        <option value="high">High Risk</option>
                        <option value="critical">Critical</option>
                    </select>
                    <select id="audit-filter-allowed">
                        <option value="">All Actions</option>
                        <option value="true">Allowed</option>
                        <option value="false">Denied</option>
                    </select>
                    <button onclick="SecurityManager.refreshAuditLog()">🔄 Refresh</button>
                </div>
                <div id="audit-log-entries" class="audit-log-entries">
                    <p>Loading...</p>
                </div>
                <button class="close-modal-btn" onclick="document.getElementById('audit-log-modal').remove()">
                    Close
                </button>
            </div>
        `;
        document.body.appendChild(modal);
        this.addModalStyles();
        this.refreshAuditLog();
    },

    refreshAuditLog: async function() {
        const container = document.getElementById('audit-log-entries');
        if (!container) return;

        try {
            const response = await fetch('/api/energy/audit-log?limit=50');
            const data = await response.json();
            
            if (!data.entries || data.entries.length === 0) {
                container.innerHTML = '<p class="no-entries">No audit log entries yet.</p>';
                return;
            }

            container.innerHTML = data.entries.map(entry => `
                <div class="audit-entry ${entry.energy_level} ${entry.was_allowed ? 'allowed' : 'denied'}">
                    <div class="audit-time">${new Date(entry.timestamp).toLocaleString()}</div>
                    <div class="audit-action">
                        <span class="audit-type">${entry.action_type}</span>
                        <span class="audit-target">${entry.target || 'N/A'}</span>
                    </div>
                    <div class="audit-user">
                        <span class="audit-user-id">${entry.user_id}</span>
                        <span class="audit-role">${entry.user_role}</span>
                    </div>
                    <div class="audit-result">
                        <span class="energy-score">${entry.energy_score.toFixed(1)}</span>
                        <span class="audit-status ${entry.was_allowed ? 'allowed' : 'denied'}">
                            ${entry.was_allowed ? '✅' : '❌'}
                        </span>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            container.innerHTML = `<p class="error">Failed to load audit log: ${error.message}</p>`;
        }
    },

    // ========================================
    // LA3.5: Session Timeout with Warning
    // ========================================

    initSessionTimeout: function() {
        // Track activity
        ['click', 'keypress', 'scroll', 'mousemove', 'touchstart'].forEach(event => {
            document.addEventListener(event, () => this.resetSessionTimer(), { passive: true });
        });

        // Start timeout timer
        this.startSessionTimer();
    },

    resetSessionTimer: function() {
        this.lastActivity = Date.now();
        this.timeoutWarningShown = false;
        
        // Hide warning if shown
        const warning = document.getElementById('session-warning');
        if (warning) warning.remove();
    },

    startSessionTimer: function() {
        // Clear existing timers
        if (this.sessionTimer) clearInterval(this.sessionTimer);
        
        this.sessionTimer = setInterval(() => {
            const elapsed = Date.now() - this.lastActivity;
            const remaining = this.SESSION_TIMEOUT - elapsed;

            // Show warning 5 minutes before timeout
            if (remaining <= this.WARNING_BEFORE && !this.timeoutWarningShown) {
                this.showSessionWarning(remaining);
                this.timeoutWarningShown = true;
            }

            // Timeout reached
            if (remaining <= 0) {
                this.handleSessionTimeout();
            }
        }, 10000); // Check every 10 seconds
    },

    showSessionWarning: function(remaining) {
        const minutes = Math.ceil(remaining / 60000);
        
        const warning = document.createElement('div');
        warning.id = 'session-warning';
        warning.className = 'session-warning';
        warning.innerHTML = `
            <div class="session-warning-content">
                <span>⏱️ Session expires in ${minutes} minute${minutes > 1 ? 's' : ''}</span>
                <button onclick="SecurityManager.extendSession()">Extend Session</button>
                <button class="dismiss" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;
        document.body.appendChild(warning);

        // Add warning styles
        const style = document.createElement('style');
        style.textContent = `
            .session-warning {
                position: fixed;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: #ffcc00;
                color: #000;
                border: 3px solid #000;
                padding: 12px 20px;
                z-index: 9999;
                box-shadow: 4px 4px 0 #000;
            }
            .session-warning-content {
                display: flex;
                align-items: center;
                gap: 15px;
            }
            .session-warning button {
                padding: 5px 12px;
                border: 2px solid #000;
                background: white;
                cursor: pointer;
                font-weight: 600;
            }
            .session-warning button.dismiss {
                padding: 2px 8px;
                background: transparent;
                border: none;
                font-size: 18px;
            }
        `;
        document.head.appendChild(style);
    },

    extendSession: function() {
        this.resetSessionTimer();
        alert('Session extended for 30 more minutes.');
    },

    handleSessionTimeout: function() {
        clearInterval(this.sessionTimer);
        
        // Show timeout modal
        const modal = document.createElement('div');
        modal.className = 'security-modal timeout-modal';
        modal.innerHTML = `
            <div class="security-modal-content">
                <h2>⏰ Session Expired</h2>
                <p>Your session has expired due to inactivity.</p>
                <button onclick="window.location.reload()">Continue Working</button>
            </div>
        `;
        document.body.appendChild(modal);
        this.addModalStyles();
    },

    // ========================================
    // LA3.6: Two-Factor Auth for Admin Actions
    // ========================================

    init2FAModal: function() {
        // Add 2FA modal styles
        const style = document.createElement('style');
        style.textContent = `
            .twofa-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10001;
            }
            .twofa-content {
                background: var(--color-bg, #0a0a0a);
                border: 4px solid #000;
                padding: 30px;
                max-width: 400px;
                text-align: center;
            }
            .twofa-content h3 {
                margin-bottom: 10px;
                color: var(--color-text, white);
            }
            .twofa-content p {
                margin-bottom: 20px;
                color: var(--color-text-muted, #888);
            }
            .pin-input {
                display: flex;
                justify-content: center;
                gap: 10px;
                margin-bottom: 20px;
            }
            .pin-input input {
                width: 50px;
                height: 60px;
                text-align: center;
                font-size: 24px;
                font-weight: 700;
                border: 3px solid #000;
                background: var(--color-surface, #1a1a1a);
                color: var(--color-text, white);
            }
            .pin-input input:focus {
                border-color: var(--color-accent, #ff3333);
                outline: none;
            }
            .twofa-actions {
                display: flex;
                gap: 10px;
                justify-content: center;
            }
            .twofa-actions button {
                padding: 12px 24px;
                border: 3px solid #000;
                font-weight: 700;
                cursor: pointer;
            }
            .twofa-confirm {
                background: var(--color-accent, #ff3333);
                color: white;
            }
            .twofa-cancel {
                background: transparent;
                color: var(--color-text, white);
            }
        `;
        document.head.appendChild(style);
    },

    request2FA: function(action) {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'twofa-modal';
            modal.id = 'twofa-modal';
            modal.innerHTML = `
                <div class="twofa-content">
                    <h3>🔐 Admin Verification Required</h3>
                    <p>${action}</p>
                    <div class="pin-input">
                        <input type="password" maxlength="1" data-index="0" autofocus>
                        <input type="password" maxlength="1" data-index="1">
                        <input type="password" maxlength="1" data-index="2">
                        <input type="password" maxlength="1" data-index="3">
                    </div>
                    <div class="twofa-actions">
                        <button class="twofa-cancel" onclick="SecurityManager.cancel2FA()">Cancel</button>
                        <button class="twofa-confirm" onclick="SecurityManager.confirm2FA()">Verify</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);

            // Store resolver for later
            this._2faResolver = resolve;

            // Setup PIN input navigation
            const inputs = modal.querySelectorAll('.pin-input input');
            inputs.forEach((input, i) => {
                input.addEventListener('input', (e) => {
                    if (e.target.value && i < inputs.length - 1) {
                        inputs[i + 1].focus();
                    }
                });
                input.addEventListener('keydown', (e) => {
                    if (e.key === 'Backspace' && !e.target.value && i > 0) {
                        inputs[i - 1].focus();
                    }
                    if (e.key === 'Enter') {
                        this.confirm2FA();
                    }
                    if (e.key === 'Escape') {
                        this.cancel2FA();
                    }
                });
            });
            
            // Focus first input
            inputs[0].focus();
        });
    },

    confirm2FA: function() {
        const inputs = document.querySelectorAll('.pin-input input');
        const pin = Array.from(inputs).map(i => i.value).join('');
        
        if (pin.length !== 4) {
            alert('Please enter a 4-digit PIN');
            return;
        }

        document.getElementById('twofa-modal')?.remove();
        this._2faResolver(pin);
    },

    cancel2FA: function() {
        document.getElementById('twofa-modal')?.remove();
        this._2faResolver(null);
    },

    // ========================================
    // Shared Modal Styles
    // ========================================

    addModalStyles: function() {
        if (document.getElementById('security-modal-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'security-modal-styles';
        style.textContent = `
            .security-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
            }
            .security-modal-content {
                background: var(--color-bg, #0a0a0a);
                color: var(--color-text, white);
                border: 4px solid #000;
                padding: 30px;
                max-width: 600px;
                max-height: 80vh;
                overflow-y: auto;
            }
            .security-modal-content h2 {
                margin-bottom: 15px;
            }
            .security-modal-content p {
                margin-bottom: 20px;
                color: var(--color-text-muted, #888);
            }
            .close-modal-btn {
                display: block;
                width: 100%;
                padding: 12px;
                margin-top: 20px;
                background: transparent;
                border: 2px solid var(--color-text, white);
                color: var(--color-text, white);
                font-weight: 600;
                cursor: pointer;
            }
            .backup-actions {
                display: flex;
                gap: 15px;
                margin-bottom: 20px;
            }
            .export-btn, .import-btn {
                flex: 1;
                padding: 15px;
                border: 3px solid #000;
                font-weight: 700;
                cursor: pointer;
                text-align: center;
            }
            .export-btn {
                background: var(--color-accent, #ff3333);
                color: white;
            }
            .import-btn {
                background: var(--color-surface, #1a1a1a);
                color: var(--color-text, white);
                display: block;
            }
            .backup-info {
                background: var(--color-surface, #1a1a1a);
                padding: 15px;
                border: 2px solid var(--color-border, #333);
            }
            .backup-info h3 {
                margin-bottom: 10px;
                font-size: 14px;
            }
            .backup-info ul {
                list-style: none;
                padding: 0;
            }
            .backup-info li {
                padding: 5px 0;
                font-size: 14px;
            }
            
            /* Audit log styles */
            .audit-log-content {
                min-width: 500px;
            }
            .audit-filters {
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
            }
            .audit-filters select, .audit-filters button {
                padding: 8px 12px;
                border: 2px solid #000;
                background: var(--color-surface, #1a1a1a);
                color: var(--color-text, white);
            }
            .audit-log-entries {
                max-height: 400px;
                overflow-y: auto;
            }
            .audit-entry {
                display: grid;
                grid-template-columns: 150px 1fr 120px 80px;
                gap: 10px;
                padding: 10px;
                border-bottom: 1px solid var(--color-border, #333);
                font-size: 13px;
            }
            .audit-entry.denied {
                background: rgba(255, 0, 0, 0.1);
            }
            .audit-entry.critical {
                border-left: 4px solid #ff0000;
            }
            .audit-entry.high {
                border-left: 4px solid #ff6600;
            }
            .audit-entry.medium {
                border-left: 4px solid #ffcc00;
            }
            .audit-time {
                color: var(--color-text-muted, #888);
                font-size: 11px;
            }
            .audit-type {
                font-weight: 600;
                text-transform: uppercase;
                font-size: 11px;
            }
            .audit-target {
                color: var(--color-text-muted, #888);
            }
            .audit-role {
                font-size: 11px;
                padding: 2px 6px;
                background: var(--color-surface, #1a1a1a);
                border-radius: 4px;
            }
            .energy-score {
                font-weight: 700;
            }
            .audit-status.allowed { color: #00cc00; }
            .audit-status.denied { color: #ff3333; }
            
            .no-entries, .error {
                text-align: center;
                padding: 40px;
                color: var(--color-text-muted, #888);
            }
            .error { color: #ff3333; }
        `;
        document.head.appendChild(style);
    }
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => SecurityManager.init());
} else {
    SecurityManager.init();
}
