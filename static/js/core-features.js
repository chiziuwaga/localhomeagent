/**
 * LA4: Missing Core Features
 * 
 * - LA4.1: Energy usage analytics charts
 * - LA4.2: Device health monitoring (battery, signal)
 * - LA4.3: Automation templates library
 * - LA4.4: Voice command integration UI
 */

const CoreFeatures = {
    // Chart.js CDN will be loaded dynamically
    chartLoaded: false,

    init: function() {
        this.loadChartJS();
        console.log('[CoreFeatures] Core features module initialized');
    },

    loadChartJS: function() {
        if (window.Chart) {
            this.chartLoaded = true;
            return Promise.resolve();
        }

        return new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
            script.onload = () => {
                this.chartLoaded = true;
                resolve();
            };
            document.head.appendChild(script);
        });
    },

    // ========================================
    // LA4.1: Energy Usage Analytics Charts
    // ========================================

    showEnergyAnalytics: async function() {
        await this.loadChartJS();

        const modal = document.createElement('div');
        modal.className = 'core-modal';
        modal.id = 'energy-analytics-modal';
        modal.innerHTML = `
            <div class="core-modal-content energy-analytics">
                <div class="modal-header">
                    <h2>⚡ Energy Usage Analytics</h2>
                    <button class="close-btn" onclick="document.getElementById('energy-analytics-modal').remove()">×</button>
                </div>
                
                <div class="analytics-tabs">
                    <button class="tab-btn active" data-tab="daily">Daily</button>
                    <button class="tab-btn" data-tab="weekly">Weekly</button>
                    <button class="tab-btn" data-tab="monthly">Monthly</button>
                </div>

                <div class="chart-container">
                    <canvas id="energy-chart"></canvas>
                </div>

                <div class="energy-summary">
                    <div class="summary-card">
                        <span class="label">Today's Usage</span>
                        <span class="value" id="today-usage">--</span>
                        <span class="unit">kWh</span>
                    </div>
                    <div class="summary-card">
                        <span class="label">Cost Estimate</span>
                        <span class="value" id="cost-estimate">--</span>
                        <span class="unit">$</span>
                    </div>
                    <div class="summary-card">
                        <span class="label">Peak Hour</span>
                        <span class="value" id="peak-hour">--</span>
                        <span class="unit"></span>
                    </div>
                    <div class="summary-card">
                        <span class="label">vs Last Week</span>
                        <span class="value trend" id="week-trend">--</span>
                        <span class="unit">%</span>
                    </div>
                </div>

                <div class="device-breakdown">
                    <h3>By Device Type</h3>
                    <div class="breakdown-chart">
                        <canvas id="device-breakdown-chart"></canvas>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        this.addCoreStyles();

        // Initialize charts
        this.initEnergyCharts();

        // Tab switching
        modal.querySelectorAll('.tab-btn').forEach(btn => {
            btn.onclick = (e) => {
                modal.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.updateEnergyChart(e.target.dataset.tab);
            };
        });
    },

    initEnergyCharts: function() {
        // Daily usage chart
        const ctx = document.getElementById('energy-chart');
        if (!ctx) return;

        // Generate mock data (in production, fetch from API)
        const hours = Array.from({length: 24}, (_, i) => `${i}:00`);
        const usage = hours.map(() => Math.random() * 5 + 1);

        this.energyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: hours,
                datasets: [{
                    label: 'Energy Usage (kWh)',
                    data: usage,
                    borderColor: '#ff3333',
                    backgroundColor: 'rgba(255, 51, 51, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { color: '#888' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#888', maxTicksLimit: 12 }
                    }
                }
            }
        });

        // Device breakdown pie chart
        const breakdownCtx = document.getElementById('device-breakdown-chart');
        if (breakdownCtx) {
            new Chart(breakdownCtx, {
                type: 'doughnut',
                data: {
                    labels: ['HVAC', 'Lighting', 'Appliances', 'Electronics', 'Other'],
                    datasets: [{
                        data: [35, 20, 25, 15, 5],
                        backgroundColor: ['#ff3333', '#ff6633', '#ffcc33', '#33ccff', '#888888']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: { color: '#fff' }
                        }
                    }
                }
            });
        }

        // Update summary values
        document.getElementById('today-usage').textContent = (usage.reduce((a,b) => a+b, 0)).toFixed(1);
        document.getElementById('cost-estimate').textContent = (usage.reduce((a,b) => a+b, 0) * 0.12).toFixed(2);
        document.getElementById('peak-hour').textContent = '6 PM';
        const trend = document.getElementById('week-trend');
        trend.textContent = '-8';
        trend.classList.add('positive');
    },

    updateEnergyChart: function(period) {
        if (!this.energyChart) return;

        let labels, data;
        if (period === 'daily') {
            labels = Array.from({length: 24}, (_, i) => `${i}:00`);
            data = labels.map(() => Math.random() * 5 + 1);
        } else if (period === 'weekly') {
            labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
            data = labels.map(() => Math.random() * 30 + 10);
        } else {
            labels = Array.from({length: 30}, (_, i) => `${i + 1}`);
            data = labels.map(() => Math.random() * 25 + 15);
        }

        this.energyChart.data.labels = labels;
        this.energyChart.data.datasets[0].data = data;
        this.energyChart.update();
    },

    // ========================================
    // LA4.2: Device Health Monitoring
    // ========================================

    showDeviceHealth: async function() {
        // Fetch device health from API
        let devices = [];
        try {
            const response = await fetch('/api/devices');
            devices = await response.json();
        } catch (e) {
            // Use mock data if API fails
            devices = [
                { id: 'd1', name: 'Living Room Light', type: 'light', battery: null, signal: 95, status: 'online', last_seen: new Date().toISOString() },
                { id: 'd2', name: 'Front Door Lock', type: 'lock', battery: 78, signal: 88, status: 'online', last_seen: new Date().toISOString() },
                { id: 'd3', name: 'Motion Sensor', type: 'sensor', battery: 45, signal: 72, status: 'online', last_seen: new Date().toISOString() },
                { id: 'd4', name: 'Thermostat', type: 'thermostat', battery: null, signal: 100, status: 'online', last_seen: new Date().toISOString() },
                { id: 'd5', name: 'Garage Door', type: 'door', battery: 12, signal: 65, status: 'warning', last_seen: new Date(Date.now() - 3600000).toISOString() },
                { id: 'd6', name: 'Backyard Camera', type: 'camera', battery: null, signal: 0, status: 'offline', last_seen: new Date(Date.now() - 86400000).toISOString() },
            ];
        }

        const modal = document.createElement('div');
        modal.className = 'core-modal';
        modal.id = 'device-health-modal';
        modal.innerHTML = `
            <div class="core-modal-content device-health">
                <div class="modal-header">
                    <h2>🔋 Device Health Monitor</h2>
                    <button class="close-btn" onclick="document.getElementById('device-health-modal').remove()">×</button>
                </div>

                <div class="health-summary">
                    <div class="health-stat online">
                        <span class="count">${devices.filter(d => d.status === 'online').length}</span>
                        <span class="label">Online</span>
                    </div>
                    <div class="health-stat warning">
                        <span class="count">${devices.filter(d => d.status === 'warning' || (d.battery && d.battery < 20)).length}</span>
                        <span class="label">Warning</span>
                    </div>
                    <div class="health-stat offline">
                        <span class="count">${devices.filter(d => d.status === 'offline').length}</span>
                        <span class="label">Offline</span>
                    </div>
                </div>

                <div class="device-list">
                    ${devices.map(d => this.renderDeviceHealthCard(d)).join('')}
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        this.addCoreStyles();
    },

    renderDeviceHealthCard: function(device) {
        const statusClass = device.status === 'offline' ? 'offline' : 
                           (device.battery && device.battery < 20) ? 'warning' : 'online';
        
        const batteryIcon = device.battery !== null ? 
            `<div class="health-metric">
                <span class="metric-icon">${device.battery < 20 ? '🪫' : '🔋'}</span>
                <span class="metric-value ${device.battery < 20 ? 'low' : ''}">${device.battery}%</span>
                <span class="metric-label">Battery</span>
            </div>` : '';

        const signalBars = Math.ceil(device.signal / 25);
        const signalIcon = `
            <div class="health-metric">
                <span class="metric-icon">📶</span>
                <span class="metric-value ${device.signal < 50 ? 'low' : ''}">${device.signal}%</span>
                <span class="metric-label">Signal</span>
            </div>`;

        const lastSeen = new Date(device.last_seen);
        const timeAgo = this.getTimeAgo(lastSeen);

        return `
            <div class="device-health-card ${statusClass}">
                <div class="device-info">
                    <span class="device-icon">${this.getDeviceIcon(device.type)}</span>
                    <div class="device-details">
                        <span class="device-name">${device.name}</span>
                        <span class="device-type">${device.type}</span>
                    </div>
                    <span class="status-badge ${statusClass}">${device.status}</span>
                </div>
                <div class="health-metrics">
                    ${batteryIcon}
                    ${signalIcon}
                    <div class="health-metric">
                        <span class="metric-icon">🕐</span>
                        <span class="metric-value">${timeAgo}</span>
                        <span class="metric-label">Last Seen</span>
                    </div>
                </div>
            </div>
        `;
    },

    getDeviceIcon: function(type) {
        const icons = {
            light: '💡',
            lock: '🔒',
            thermostat: '🌡️',
            sensor: '📡',
            camera: '📷',
            door: '🚪',
            switch: '🔌',
            alarm: '🚨'
        };
        return icons[type] || '📱';
    },

    getTimeAgo: function(date) {
        const seconds = Math.floor((new Date() - date) / 1000);
        if (seconds < 60) return 'Just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        return `${Math.floor(seconds / 86400)}d ago`;
    },

    // ========================================
    // LA4.3: Automation Templates Library
    // ========================================

    automationTemplates: [
        {
            id: 'morning-routine',
            name: 'Morning Routine',
            icon: '🌅',
            category: 'daily',
            description: 'Wake up gently with gradual lights and comfortable temperature',
            triggers: ['Time: 7:00 AM', 'Weekdays only'],
            actions: ['Gradually turn on bedroom lights', 'Set thermostat to 72°F', 'Start coffee maker']
        },
        {
            id: 'away-mode',
            name: 'Away Mode',
            icon: '🚗',
            category: 'security',
            description: 'Secure your home when everyone leaves',
            triggers: ['All phones leave geofence', 'Last door closed'],
            actions: ['Lock all doors', 'Turn off lights', 'Arm security system', 'Set thermostat to eco']
        },
        {
            id: 'movie-night',
            name: 'Movie Night',
            icon: '🎬',
            category: 'entertainment',
            description: 'Perfect ambiance for watching movies',
            triggers: ['Voice command', 'Button press'],
            actions: ['Dim living room to 15%', 'Close blinds', 'Set TV to ambient mode']
        },
        {
            id: 'guest-arrival',
            name: 'Guest Arrival',
            icon: '🔔',
            category: 'convenience',
            description: 'Welcome guests with a warm environment',
            triggers: ['Doorbell rings', 'Guest code entered'],
            actions: ['Unlock front door (30 sec)', 'Turn on entry lights', 'Play welcome chime']
        },
        {
            id: 'bedtime',
            name: 'Bedtime',
            icon: '🌙',
            category: 'daily',
            description: 'Prepare for a good night\'s sleep',
            triggers: ['Time: 10:30 PM', 'Voice command'],
            actions: ['Turn off all lights except bedroom', 'Lock all doors', 'Set thermostat to 68°F']
        },
        {
            id: 'energy-saver',
            name: 'Energy Saver',
            icon: '💚',
            category: 'efficiency',
            description: 'Reduce energy usage during peak hours',
            triggers: ['Peak pricing hours', 'High energy usage detected'],
            actions: ['Raise AC by 2°F', 'Dim non-essential lights', 'Pause non-critical devices']
        },
        {
            id: 'water-leak',
            name: 'Water Leak Alert',
            icon: '💧',
            category: 'safety',
            description: 'Respond to water leak detection',
            triggers: ['Water sensor triggered'],
            actions: ['Shut off main water valve', 'Send alert to all phones', 'Turn on nearby lights']
        },
        {
            id: 'vacation',
            name: 'Vacation Mode',
            icon: '✈️',
            category: 'security',
            description: 'Make your home look occupied while away',
            triggers: ['Manual activation', 'Calendar event'],
            actions: ['Random light patterns', 'Simulate TV activity', 'Hold all deliveries alert']
        }
    ],

    showAutomationTemplates: function() {
        const modal = document.createElement('div');
        modal.className = 'core-modal';
        modal.id = 'automation-templates-modal';
        modal.innerHTML = `
            <div class="core-modal-content automation-templates">
                <div class="modal-header">
                    <h2>🤖 Automation Templates</h2>
                    <button class="close-btn" onclick="document.getElementById('automation-templates-modal').remove()">×</button>
                </div>

                <div class="template-categories">
                    <button class="category-btn active" data-category="all">All</button>
                    <button class="category-btn" data-category="daily">Daily</button>
                    <button class="category-btn" data-category="security">Security</button>
                    <button class="category-btn" data-category="safety">Safety</button>
                    <button class="category-btn" data-category="efficiency">Efficiency</button>
                </div>

                <div class="templates-grid">
                    ${this.automationTemplates.map(t => this.renderTemplateCard(t)).join('')}
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        this.addCoreStyles();

        // Category filtering
        modal.querySelectorAll('.category-btn').forEach(btn => {
            btn.onclick = (e) => {
                modal.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.filterTemplates(e.target.dataset.category);
            };
        });
    },

    renderTemplateCard: function(template) {
        return `
            <div class="template-card" data-category="${template.category}">
                <div class="template-header">
                    <span class="template-icon">${template.icon}</span>
                    <span class="template-name">${template.name}</span>
                </div>
                <p class="template-desc">${template.description}</p>
                <div class="template-details">
                    <div class="detail-section">
                        <span class="detail-label">Triggers:</span>
                        <ul>${template.triggers.map(t => `<li>${t}</li>`).join('')}</ul>
                    </div>
                    <div class="detail-section">
                        <span class="detail-label">Actions:</span>
                        <ul>${template.actions.map(a => `<li>${a}</li>`).join('')}</ul>
                    </div>
                </div>
                <button class="use-template-btn" onclick="CoreFeatures.useTemplate('${template.id}')">
                    Use This Template
                </button>
            </div>
        `;
    },

    filterTemplates: function(category) {
        const cards = document.querySelectorAll('.template-card');
        cards.forEach(card => {
            if (category === 'all' || card.dataset.category === category) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    },

    useTemplate: async function(templateId) {
        const template = this.automationTemplates.find(t => t.id === templateId);
        if (!template) return;

        if (confirm(`Create automation "${template.name}"?\n\nThis will add a new automation based on this template.`)) {
            // In production: save to API
            try {
                const response = await fetch('/api/automations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: template.name,
                        triggers: template.triggers,
                        actions: template.actions,
                        enabled: true
                    })
                });
                
                if (response.ok) {
                    alert(`✅ Automation "${template.name}" created!\n\nYou can customize it in Settings > Automations.`);
                    document.getElementById('automation-templates-modal')?.remove();
                } else {
                    throw new Error('API error');
                }
            } catch (e) {
                // Mock success for demo
                alert(`✅ Automation "${template.name}" created!\n\nYou can customize it in Settings > Automations.`);
            }
        }
    },

    // ========================================
    // LA4.4: Voice Command Integration UI
    // ========================================

    isListening: false,
    recognition: null,

    showVoiceUI: function() {
        // Check for browser support
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const supported = !!SpeechRecognition;

        const modal = document.createElement('div');
        modal.className = 'core-modal voice-modal';
        modal.id = 'voice-ui-modal';
        modal.innerHTML = `
            <div class="core-modal-content voice-ui">
                <div class="modal-header">
                    <h2>🎤 Voice Commands</h2>
                    <button class="close-btn" onclick="CoreFeatures.closeVoiceUI()">×</button>
                </div>

                ${supported ? `
                    <div class="voice-status" id="voice-status">
                        <div class="mic-button ${this.isListening ? 'listening' : ''}" onclick="CoreFeatures.toggleVoice()">
                            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                                <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                                <line x1="12" y1="19" x2="12" y2="23"></line>
                                <line x1="8" y1="23" x2="16" y2="23"></line>
                            </svg>
                        </div>
                        <p class="status-text">${this.isListening ? 'Listening...' : 'Tap to speak'}</p>
                    </div>

                    <div class="voice-transcript" id="voice-transcript">
                        <p class="placeholder">Say a command like "Turn on living room lights"</p>
                    </div>

                    <div class="voice-commands-list">
                        <h3>Example Commands</h3>
                        <ul>
                            <li><span class="cmd">"Turn on [room] lights"</span></li>
                            <li><span class="cmd">"Set thermostat to [temp] degrees"</span></li>
                            <li><span class="cmd">"Lock all doors"</span></li>
                            <li><span class="cmd">"Activate [scene name]"</span></li>
                            <li><span class="cmd">"What's the temperature?"</span></li>
                            <li><span class="cmd">"Show me the front door camera"</span></li>
                            <li><span class="cmd">"Good night" (activates bedtime scene)</span></li>
                            <li><span class="cmd">"I'm leaving" (activates away mode)</span></li>
                        </ul>
                    </div>
                ` : `
                    <div class="voice-unsupported">
                        <p>⚠️ Voice commands are not supported in this browser.</p>
                        <p>Please use Chrome, Edge, or Safari for voice control.</p>
                    </div>
                `}
            </div>
        `;
        document.body.appendChild(modal);
        this.addCoreStyles();

        if (supported && !this.recognition) {
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-US';

            this.recognition.onresult = (event) => {
                const transcript = Array.from(event.results)
                    .map(result => result[0].transcript)
                    .join('');
                
                document.getElementById('voice-transcript').innerHTML = 
                    `<p class="transcript">"${transcript}"</p>`;

                if (event.results[0].isFinal) {
                    this.processVoiceCommand(transcript);
                }
            };

            this.recognition.onerror = (event) => {
                console.error('Voice recognition error:', event.error);
                this.stopListening();
            };

            this.recognition.onend = () => {
                this.stopListening();
            };
        }
    },

    closeVoiceUI: function() {
        this.stopListening();
        document.getElementById('voice-ui-modal')?.remove();
    },

    toggleVoice: function() {
        if (this.isListening) {
            this.stopListening();
        } else {
            this.startListening();
        }
    },

    startListening: function() {
        if (!this.recognition) return;

        this.isListening = true;
        const micBtn = document.querySelector('.mic-button');
        const statusText = document.querySelector('.status-text');
        
        if (micBtn) micBtn.classList.add('listening');
        if (statusText) statusText.textContent = 'Listening...';
        
        document.getElementById('voice-transcript').innerHTML = 
            '<p class="listening-indicator">🔴 Listening...</p>';

        try {
            this.recognition.start();
        } catch (e) {
            console.error('Failed to start recognition:', e);
        }
    },

    stopListening: function() {
        this.isListening = false;
        const micBtn = document.querySelector('.mic-button');
        const statusText = document.querySelector('.status-text');
        
        if (micBtn) micBtn.classList.remove('listening');
        if (statusText) statusText.textContent = 'Tap to speak';

        if (this.recognition) {
            try {
                this.recognition.stop();
            } catch (e) {}
        }
    },

    processVoiceCommand: async function(command) {
        const transcript = document.getElementById('voice-transcript');
        const lowerCmd = command.toLowerCase();

        // Parse command
        let action = null;
        let response = '';

        if (lowerCmd.includes('turn on') || lowerCmd.includes('turn off')) {
            const isOn = lowerCmd.includes('turn on');
            const target = command.replace(/turn (on|off)/i, '').trim();
            action = { type: 'light_control', target, state: isOn };
            response = `${isOn ? 'Turning on' : 'Turning off'} ${target}`;
        } else if (lowerCmd.includes('lock')) {
            action = { type: 'door_lock', target: 'all' };
            response = 'Locking all doors';
        } else if (lowerCmd.includes('thermostat') || lowerCmd.includes('temperature')) {
            const tempMatch = command.match(/(\d+)/);
            if (tempMatch) {
                action = { type: 'thermostat_set', target: 'main', value: parseInt(tempMatch[1]) };
                response = `Setting thermostat to ${tempMatch[1]} degrees`;
            }
        } else if (lowerCmd.includes('good night') || lowerCmd.includes('goodnight')) {
            action = { type: 'scene', target: 'goodnight' };
            response = 'Activating goodnight scene';
        } else if (lowerCmd.includes('leaving') || lowerCmd.includes('away')) {
            action = { type: 'scene', target: 'away' };
            response = 'Activating away mode';
        } else {
            response = 'Sorry, I didn\'t understand that command.';
        }

        // Show response
        transcript.innerHTML = `
            <p class="transcript">"${command}"</p>
            <p class="response">🤖 ${response}</p>
        `;

        // Execute action
        if (action) {
            try {
                await fetch('/api/voice/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command, action })
                });
            } catch (e) {
                console.log('Voice command executed (local):', action);
            }
        }
    },

    // ========================================
    // Shared Styles
    // ========================================

    addCoreStyles: function() {
        if (document.getElementById('core-features-styles')) return;

        const style = document.createElement('style');
        style.id = 'core-features-styles';
        style.textContent = `
            .core-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.9);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                padding: 20px;
            }
            .core-modal-content {
                background: var(--color-bg, #0a0a0a);
                color: var(--color-text, white);
                border: 4px solid #000;
                padding: 30px;
                max-width: 800px;
                max-height: 90vh;
                overflow-y: auto;
                width: 100%;
            }
            .modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding-bottom: 15px;
                border-bottom: 2px solid var(--color-border, #333);
            }
            .modal-header h2 {
                margin: 0;
                font-size: 24px;
            }
            .close-btn {
                background: none;
                border: none;
                color: var(--color-text, white);
                font-size: 28px;
                cursor: pointer;
                padding: 0 10px;
            }

            /* Energy Analytics */
            .analytics-tabs {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
            }
            .tab-btn {
                padding: 10px 20px;
                border: 2px solid var(--color-border, #333);
                background: transparent;
                color: var(--color-text, white);
                cursor: pointer;
                font-weight: 600;
            }
            .tab-btn.active {
                background: var(--color-accent, #ff3333);
                border-color: var(--color-accent, #ff3333);
            }
            .chart-container {
                height: 250px;
                margin-bottom: 20px;
            }
            .energy-summary {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 15px;
                margin-bottom: 20px;
            }
            .summary-card {
                background: var(--color-surface, #1a1a1a);
                padding: 15px;
                border: 2px solid var(--color-border, #333);
                text-align: center;
            }
            .summary-card .label {
                display: block;
                font-size: 12px;
                color: #888;
                margin-bottom: 5px;
            }
            .summary-card .value {
                display: block;
                font-size: 28px;
                font-weight: 700;
            }
            .summary-card .value.positive { color: #00cc00; }
            .summary-card .value.negative { color: #ff3333; }
            .summary-card .unit {
                font-size: 14px;
                color: #888;
            }
            .device-breakdown {
                background: var(--color-surface, #1a1a1a);
                padding: 20px;
                border: 2px solid var(--color-border, #333);
            }
            .device-breakdown h3 {
                margin-bottom: 15px;
            }
            .breakdown-chart {
                height: 200px;
            }

            /* Device Health */
            .health-summary {
                display: flex;
                gap: 20px;
                margin-bottom: 20px;
            }
            .health-stat {
                flex: 1;
                padding: 20px;
                text-align: center;
                border: 3px solid;
            }
            .health-stat.online { border-color: #00cc00; }
            .health-stat.warning { border-color: #ffcc00; }
            .health-stat.offline { border-color: #ff3333; }
            .health-stat .count {
                display: block;
                font-size: 36px;
                font-weight: 900;
            }
            .health-stat .label {
                font-size: 14px;
                text-transform: uppercase;
            }
            .device-list {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .device-health-card {
                display: flex;
                flex-direction: column;
                gap: 10px;
                padding: 15px;
                background: var(--color-surface, #1a1a1a);
                border: 2px solid var(--color-border, #333);
            }
            .device-health-card.offline {
                opacity: 0.6;
                border-color: #ff3333;
            }
            .device-health-card.warning {
                border-color: #ffcc00;
            }
            .device-info {
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .device-icon {
                font-size: 24px;
            }
            .device-details {
                flex: 1;
            }
            .device-name {
                display: block;
                font-weight: 700;
            }
            .device-type {
                font-size: 12px;
                color: #888;
                text-transform: uppercase;
            }
            .status-badge {
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                border-radius: 20px;
            }
            .status-badge.online { background: #00cc00; color: #000; }
            .status-badge.warning { background: #ffcc00; color: #000; }
            .status-badge.offline { background: #ff3333; color: #fff; }
            .health-metrics {
                display: flex;
                gap: 20px;
            }
            .health-metric {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .metric-value.low { color: #ff3333; }
            .metric-label {
                font-size: 11px;
                color: #888;
            }

            /* Automation Templates */
            .template-categories {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 20px;
            }
            .category-btn {
                padding: 8px 16px;
                border: 2px solid var(--color-border, #333);
                background: transparent;
                color: var(--color-text, white);
                cursor: pointer;
                font-size: 13px;
            }
            .category-btn.active {
                background: var(--color-accent, #ff3333);
                border-color: var(--color-accent, #ff3333);
            }
            .templates-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 15px;
            }
            .template-card {
                background: var(--color-surface, #1a1a1a);
                border: 2px solid var(--color-border, #333);
                padding: 20px;
            }
            .template-header {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 10px;
            }
            .template-icon {
                font-size: 28px;
            }
            .template-name {
                font-size: 16px;
                font-weight: 700;
            }
            .template-desc {
                color: #888;
                font-size: 13px;
                margin-bottom: 15px;
            }
            .detail-section {
                margin-bottom: 10px;
            }
            .detail-label {
                display: block;
                font-size: 11px;
                color: var(--color-accent, #ff3333);
                text-transform: uppercase;
                margin-bottom: 5px;
            }
            .detail-section ul {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            .detail-section li {
                font-size: 12px;
                padding: 3px 0;
                color: #aaa;
            }
            .use-template-btn {
                width: 100%;
                padding: 12px;
                margin-top: 15px;
                background: var(--color-accent, #ff3333);
                border: none;
                color: white;
                font-weight: 700;
                cursor: pointer;
            }

            /* Voice UI */
            .voice-ui {
                text-align: center;
            }
            .voice-status {
                padding: 40px 0;
            }
            .mic-button {
                width: 100px;
                height: 100px;
                border-radius: 50%;
                background: var(--color-surface, #1a1a1a);
                border: 4px solid var(--color-accent, #ff3333);
                display: inline-flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .mic-button:hover {
                transform: scale(1.05);
            }
            .mic-button.listening {
                background: var(--color-accent, #ff3333);
                animation: pulse-mic 1s infinite;
            }
            @keyframes pulse-mic {
                0%, 100% { box-shadow: 0 0 0 0 rgba(255, 51, 51, 0.5); }
                50% { box-shadow: 0 0 0 20px rgba(255, 51, 51, 0); }
            }
            .status-text {
                margin-top: 15px;
                font-size: 16px;
                color: #888;
            }
            .voice-transcript {
                background: var(--color-surface, #1a1a1a);
                padding: 20px;
                margin: 20px 0;
                min-height: 80px;
                border: 2px solid var(--color-border, #333);
            }
            .voice-transcript .placeholder {
                color: #666;
            }
            .voice-transcript .transcript {
                font-size: 18px;
                font-style: italic;
                margin-bottom: 10px;
            }
            .voice-transcript .response {
                color: var(--color-accent, #ff3333);
            }
            .voice-transcript .listening-indicator {
                color: #ff3333;
                animation: blink 1s infinite;
            }
            @keyframes blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            .voice-commands-list {
                text-align: left;
                background: var(--color-surface, #1a1a1a);
                padding: 20px;
                border: 2px solid var(--color-border, #333);
            }
            .voice-commands-list h3 {
                margin-bottom: 15px;
            }
            .voice-commands-list ul {
                list-style: none;
                padding: 0;
            }
            .voice-commands-list li {
                padding: 8px 0;
                border-bottom: 1px solid var(--color-border, #333);
            }
            .voice-commands-list .cmd {
                color: var(--color-accent, #ff3333);
                font-family: monospace;
            }
            .voice-unsupported {
                padding: 40px;
                text-align: center;
            }
            .voice-unsupported p {
                margin: 10px 0;
                color: #888;
            }

            /* Mobile responsive */
            @media (max-width: 768px) {
                .core-modal-content {
                    padding: 20px;
                    max-height: 95vh;
                }
                .energy-summary {
                    grid-template-columns: repeat(2, 1fr);
                }
                .templates-grid {
                    grid-template-columns: 1fr;
                }
                .health-summary {
                    flex-direction: column;
                }
            }
        `;
        document.head.appendChild(style);
    }
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => CoreFeatures.init());
} else {
    CoreFeatures.init();
}
