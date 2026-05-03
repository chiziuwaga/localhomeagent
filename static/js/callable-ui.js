/**
 * Local Home Agent - Callable UI Library
 * 
 * Renders interactive UI components inline within chat messages.
 * Matches the Co-Living web platform's callable UI pattern.
 * 
 * Supported callable UIs:
 * - DeviceCard: Show device with toggle control
 * - EnergyMeter: Display thermodynamic energy level
 * - ActionConfirmation: Inline approve/deny dialogs
 * - SceneSelector: Quick scene activation buttons
 * - VerificationChallenge: PIN/code entry for high-risk actions
 * - DeviceList: Grid of multiple devices
 * - StatusCard: Show system status metrics
 * - AlertBanner: Warning/info banners
 */

(function() {
    'use strict';

    // Callable UI Registry
    const CallableUI = {
        
        /**
         * Parse message content for callable UI JSON blocks
         * Format: ```callable:TYPE {...json...} ```
         */
        parseMessage: function(content) {
            const regex = /```callable:(\w+)\s*(\{[\s\S]*?\})\s*```/g;
            let match;
            const callables = [];
            
            while ((match = regex.exec(content)) !== null) {
                try {
                    const type = match[1];
                    const data = JSON.parse(match[2]);
                    callables.push({ type, data, raw: match[0] });
                } catch (e) {
                    console.error('[CallableUI] Failed to parse:', e);
                }
            }
            
            return callables;
        },

        /**
         * Render callable UI and return HTML
         */
        render: function(type, data) {
            const renderer = this.renderers[type];
            if (!renderer) {
                console.warn('[CallableUI] Unknown type:', type);
                return `<div class="callable-unknown">[Unknown UI: ${type}]</div>`;
            }
            return renderer(data);
        },

        /**
         * Process message content, replacing callable blocks with rendered HTML
         */
        processMessage: function(content) {
            const callables = this.parseMessage(content);
            let processed = content;
            
            for (const callable of callables) {
                const html = this.render(callable.type, callable.data);
                processed = processed.replace(callable.raw, html);
            }
            
            return processed;
        },

        // UI Renderers
        renderers: {
            
            /**
             * DeviceCard - Single device with toggle
             */
            DeviceCard: function(data) {
                const { id, name, icon, state, type, entityId } = data;
                const isOn = state === 'on' || state === true;
                
                return `
                    <div class="callable-device-card" data-entity-id="${entityId || id}">
                        <div class="callable-device-info">
                            <span class="callable-device-icon">${icon || '💡'}</span>
                            <div class="callable-device-text">
                                <strong>${name}</strong>
                                <span class="callable-device-type">${type || 'Device'}</span>
                            </div>
                        </div>
                        <button class="callable-device-toggle ${isOn ? 'on' : ''}" 
                                onclick="CallableUI.toggleDevice('${entityId || id}', this)">
                            <span class="toggle-label">${isOn ? 'ON' : 'OFF'}</span>
                        </button>
                    </div>
                `;
            },

            /**
             * DeviceList - Grid of devices
             */
            DeviceList: function(data) {
                const { devices, title } = data;
                const cards = devices.map(d => CallableUI.renderers.DeviceCard(d)).join('');
                
                return `
                    <div class="callable-device-list">
                        ${title ? `<h4 class="callable-section-title">${title}</h4>` : ''}
                        <div class="callable-device-grid">
                            ${cards}
                        </div>
                    </div>
                `;
            },

            /**
             * EnergyMeter - Thermodynamic energy level display
             */
            EnergyMeter: function(data) {
                const { level, max, label, thresholds } = data;
                const percentage = Math.min((level / (max || 100)) * 100, 100);
                
                let energyClass = 'energy-low';
                if (percentage > 80) energyClass = 'energy-critical';
                else if (percentage > 50) energyClass = 'energy-high';
                else if (percentage > 20) energyClass = 'energy-medium';
                
                return `
                    <div class="callable-energy-meter">
                        <div class="callable-energy-header">
                            <span class="callable-energy-icon">⚡</span>
                            <span class="callable-energy-label">${label || 'System Energy'}</span>
                            <span class="callable-energy-value">${level.toFixed(1)}</span>
                        </div>
                        <div class="callable-energy-bar">
                            <div class="callable-energy-fill ${energyClass}" style="width: ${percentage}%"></div>
                        </div>
                        <div class="callable-energy-thresholds">
                            <span>SAFE</span>
                            <span>MEDIUM</span>
                            <span>HIGH</span>
                            <span>CRITICAL</span>
                        </div>
                    </div>
                `;
            },

            /**
             * ActionConfirmation - Approve/Deny dialog for actions
             */
            ActionConfirmation: function(data) {
                const { action, target, message, actionId, energyLevel } = data;
                
                return `
                    <div class="callable-action-confirm" data-action-id="${actionId}">
                        <div class="callable-confirm-header">
                            <span class="callable-confirm-icon">⚠️</span>
                            <span class="callable-confirm-title">Action Required</span>
                        </div>
                        <div class="callable-confirm-body">
                            <p class="callable-confirm-message">${message}</p>
                            <div class="callable-confirm-details">
                                <span><strong>Action:</strong> ${action}</span>
                                <span><strong>Target:</strong> ${target}</span>
                                ${energyLevel ? `<span><strong>Energy:</strong> ${energyLevel}</span>` : ''}
                            </div>
                        </div>
                        <div class="callable-confirm-actions">
                            <button class="callable-btn callable-btn-danger" onclick="CallableUI.denyAction('${actionId}')">
                                ✕ DENY
                            </button>
                            <button class="callable-btn callable-btn-success" onclick="CallableUI.approveAction('${actionId}')">
                                ✓ APPROVE
                            </button>
                        </div>
                    </div>
                `;
            },

            /**
             * SceneSelector - Quick scene buttons
             */
            SceneSelector: function(data) {
                const { scenes, title } = data;
                const buttons = scenes.map(s => `
                    <button class="callable-scene-btn" onclick="CallableUI.activateScene('${s.id}')">
                        <span class="callable-scene-icon">${s.icon || '🎬'}</span>
                        <span class="callable-scene-name">${s.name}</span>
                    </button>
                `).join('');
                
                return `
                    <div class="callable-scene-selector">
                        ${title ? `<h4 class="callable-section-title">${title}</h4>` : ''}
                        <div class="callable-scene-grid">
                            ${buttons}
                        </div>
                    </div>
                `;
            },

            /**
             * VerificationChallenge - PIN/code entry
             */
            VerificationChallenge: function(data) {
                const { challengeId, type, message, timeout } = data;
                
                const inputType = type === 'pin' ? 'password' : 'text';
                const placeholder = type === 'pin' ? 'Enter PIN' : 'Enter code';
                
                return `
                    <div class="callable-verification" data-challenge-id="${challengeId}">
                        <div class="callable-verify-header">
                            <span class="callable-verify-icon">🔐</span>
                            <span class="callable-verify-title">Verification Required</span>
                        </div>
                        <p class="callable-verify-message">${message}</p>
                        <div class="callable-verify-input">
                            <input type="${inputType}" 
                                   id="verify-input-${challengeId}" 
                                   placeholder="${placeholder}"
                                   class="callable-input"
                                   maxlength="6"
                                   autocomplete="off"
                                   onkeypress="if(event.key==='Enter') CallableUI.submitVerification('${challengeId}')">
                            <button class="callable-btn callable-btn-accent" onclick="CallableUI.submitVerification('${challengeId}')">
                                VERIFY
                            </button>
                        </div>
                        ${timeout ? `<div class="callable-verify-timeout">Expires in <span id="timeout-${challengeId}">${timeout}</span>s</div>` : ''}
                    </div>
                `;
            },

            /**
             * StatusCard - System status metric
             */
            StatusCard: function(data) {
                const { title, value, icon, status, subtitle } = data;
                const statusClass = status || 'normal';
                
                return `
                    <div class="callable-status-card status-${statusClass}">
                        <span class="callable-status-icon">${icon || '📊'}</span>
                        <div class="callable-status-content">
                            <div class="callable-status-value">${value}</div>
                            <div class="callable-status-title">${title}</div>
                            ${subtitle ? `<div class="callable-status-subtitle">${subtitle}</div>` : ''}
                        </div>
                    </div>
                `;
            },

            /**
             * AlertBanner - Warning/info/error banner
             */
            AlertBanner: function(data) {
                const { type, title, message, dismissible } = data;
                const icons = { warning: '⚠️', error: '❌', success: '✅', info: 'ℹ️' };
                
                return `
                    <div class="callable-alert callable-alert-${type || 'info'}">
                        <span class="callable-alert-icon">${icons[type] || icons.info}</span>
                        <div class="callable-alert-content">
                            ${title ? `<strong class="callable-alert-title">${title}</strong>` : ''}
                            <span class="callable-alert-message">${message}</span>
                        </div>
                        ${dismissible ? '<button class="callable-alert-dismiss" onclick="this.parentElement.remove()">✕</button>' : ''}
                    </div>
                `;
            }
        },

        // Action handlers
        toggleDevice: async function(entityId, button) {
            const isOn = button.classList.contains('on');
            const newState = !isOn;
            
            button.disabled = true;
            button.innerHTML = '<span class="toggle-label">...</span>';
            
            try {
                const response = await fetch(`/api/devices/${entityId}/control`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ state: newState ? 'on' : 'off' })
                });
                
                if (response.ok) {
                    button.classList.toggle('on', newState);
                    button.innerHTML = `<span class="toggle-label">${newState ? 'ON' : 'OFF'}</span>`;
                } else {
                    throw new Error('Failed to toggle device');
                }
            } catch (error) {
                console.error('[CallableUI] Toggle error:', error);
                button.innerHTML = `<span class="toggle-label">${isOn ? 'ON' : 'OFF'}</span>`;
                alert('Failed to control device. Please try again.');
            }
            
            button.disabled = false;
        },

        approveAction: async function(actionId) {
            await this.respondToAction(actionId, 'approve');
        },

        denyAction: async function(actionId) {
            await this.respondToAction(actionId, 'deny');
        },

        respondToAction: async function(actionId, response) {
            const card = document.querySelector(`[data-action-id="${actionId}"]`);
            if (!card) return;
            
            card.classList.add('processing');
            
            try {
                const res = await fetch(`/api/actions/${actionId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ response })
                });
                
                if (res.ok) {
                    card.innerHTML = `
                        <div class="callable-confirm-result ${response}">
                            ${response === 'approve' ? '✓ Action approved' : '✕ Action denied'}
                        </div>
                    `;
                }
            } catch (error) {
                console.error('[CallableUI] Action response error:', error);
            }
        },

        activateScene: async function(sceneId) {
            try {
                const response = await fetch(`/api/scenes/${sceneId}`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    // Visual feedback
                    const btn = event.target.closest('.callable-scene-btn');
                    if (btn) {
                        btn.classList.add('activated');
                        setTimeout(() => btn.classList.remove('activated'), 2000);
                    }
                }
            } catch (error) {
                console.error('[CallableUI] Scene activation error:', error);
            }
        },

        submitVerification: async function(challengeId) {
            const input = document.getElementById(`verify-input-${challengeId}`);
            const card = document.querySelector(`[data-challenge-id="${challengeId}"]`);
            if (!input || !card) return;
            
            const code = input.value.trim();
            if (!code) {
                input.focus();
                return;
            }
            
            card.classList.add('processing');
            
            try {
                const response = await fetch(`/api/verify/${challengeId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code })
                });
                
                const result = await response.json();
                
                if (result.verified) {
                    card.innerHTML = `
                        <div class="callable-verify-result success">
                            ✓ Verification successful
                        </div>
                    `;
                } else {
                    card.classList.remove('processing');
                    input.value = '';
                    input.placeholder = 'Invalid code - try again';
                    input.focus();
                }
            } catch (error) {
                console.error('[CallableUI] Verification error:', error);
                card.classList.remove('processing');
            }
        }
    };

    // Alias for backwards compatibility with chat.html integration
    CallableUI.parseCallableUI = CallableUI.processMessage;
    
    // Initialize any interactive components after DOM insertion
    CallableUI.initializeComponents = function(container) {
        // Start countdown timers for verification challenges
        container.querySelectorAll('.callable-verify-timeout span[id^="timeout-"]').forEach(el => {
            const challengeId = el.id.replace('timeout-', '');
            let remaining = parseInt(el.textContent, 10);
            
            const timer = setInterval(() => {
                remaining--;
                el.textContent = remaining;
                
                if (remaining <= 0) {
                    clearInterval(timer);
                    const card = container.querySelector(`[data-challenge-id="${challengeId}"]`);
                    if (card) {
                        card.innerHTML = `
                            <div class="callable-verify-result expired">
                                ⏱ Verification expired
                            </div>
                        `;
                    }
                }
            }, 1000);
        });
        
        // Add animation classes to newly rendered components
        container.querySelectorAll('.callable-device-card, .callable-action-confirm, .callable-verification').forEach(el => {
            el.classList.add('callable-animate-in');
        });
    };

    // Expose globally
    window.CallableUI = CallableUI;

})();
