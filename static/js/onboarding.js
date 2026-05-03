/**
 * Local Home Agent - Onboarding & Tutorial System
 * 
 * LA2.1: Interactive setup wizard with progress
 * LA2.2: First-time user guided tour
 * LA2.3: Feature tooltips for dashboard
 * LA2.4: Keyboard shortcut guide modal
 * LA2.5: Video tutorial placeholders
 * LA2.6: "What's New" changelog modal
 * LA2.7: Help bubble on each page
 */

const Onboarding = {
    STORAGE_KEYS: {
        ONBOARDING_COMPLETE: 'lha-onboarding-complete',
        TOUR_COMPLETE: 'lha-tour-complete',
        SEEN_WHATS_NEW: 'lha-whats-new-v1.0',
        SEEN_TOOLTIPS: 'lha-tooltips-shown'
    },
    
    VERSION: '1.0.0',
    
    // LA2.6: What's New changelog
    CHANGELOG: [
        {
            version: '1.0.0',
            date: 'December 2025',
            title: 'Initial Release',
            changes: [
                '🏠 AI-powered home assistant',
                '💡 Smart device control',
                '🔒 Thermodynamic security model',
                '📱 Mobile PWA support',
                '🌙 Dark/Light mode toggle',
                '🔗 Home Assistant integration'
            ]
        }
    ],
    
    // LA2.4: Keyboard shortcuts
    SHORTCUTS: [
        { key: 'Ctrl/⌘ + K', action: 'Open quick command' },
        { key: 'Ctrl/⌘ + /', action: 'Toggle help' },
        { key: 'Ctrl/⌘ + D', action: 'Go to Dashboard' },
        { key: 'Ctrl/⌘ + C', action: 'Open Chat' },
        { key: 'Ctrl/⌘ + S', action: 'Open Settings' },
        { key: 'Esc', action: 'Close modal/menu' },
        { key: 'T', action: 'Toggle theme' },
        { key: '?', action: 'Show this help' }
    ],
    
    // LA2.2: Tour steps
    TOUR_STEPS: [
        {
            target: 'nav, .mobile-nav',
            title: 'Navigation',
            content: 'Use the navigation to switch between Dashboard, Chat, and Settings.',
            position: 'bottom'
        },
        {
            target: '.device-grid, .devices-section, #devices',
            title: 'Device Control',
            content: 'Control all your smart home devices from one place. Tap to toggle!',
            position: 'top'
        },
        {
            target: '#theme-toggle-btn, .theme-toggle-btn',
            title: 'Theme Toggle',
            content: 'Switch between dark and light mode anytime.',
            position: 'left'
        },
        {
            target: '.help-bubble',
            title: 'Need Help?',
            content: 'Click this button anytime for help and tips!',
            position: 'top'
        }
    ],
    
    // LA2.3: Feature tooltips
    TOOLTIPS: {
        'device-toggle': 'Tap to turn this device on/off',
        'energy-meter': 'Shows your home\'s current energy usage',
        'chat-input': 'Ask your AI assistant anything about your home',
        'scene-button': 'Activate a preset scene for multiple devices',
        'automation-card': 'Automated actions that run on schedule or triggers'
    },
    
    /**
     * Initialize onboarding system
     */
    init: function() {
        // Inject styles
        this.injectStyles();
        
        // Check if first time user
        if (!this.isOnboardingComplete()) {
            setTimeout(() => this.showWelcomeModal(), 500);
        } else if (!this.hasSeenWhatsNew()) {
            setTimeout(() => this.showWhatsNewModal(), 500);
        }
        
        // Always add help bubble
        this.addHelpBubble();
        
        // Setup keyboard shortcuts
        this.setupKeyboardShortcuts();
    },
    
    /**
     * Check if onboarding is complete
     */
    isOnboardingComplete: function() {
        return localStorage.getItem(this.STORAGE_KEYS.ONBOARDING_COMPLETE) === 'true';
    },
    
    /**
     * Check if user has seen latest what's new
     */
    hasSeenWhatsNew: function() {
        return localStorage.getItem(this.STORAGE_KEYS.SEEN_WHATS_NEW) === 'true';
    },
    
    /**
     * LA2.1: Show welcome modal with setup wizard
     */
    showWelcomeModal: function() {
        const modal = this.createModal('welcome-modal', `
            <div class="onboarding-wizard">
                <div class="wizard-header">
                    <h2>👋 Welcome to Local Home Agent</h2>
                    <p>Your AI-powered smart home assistant</p>
                </div>
                
                <div class="wizard-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" id="wizard-progress-fill" style="width: 25%"></div>
                    </div>
                    <span class="progress-text">Step <span id="current-step">1</span> of 4</span>
                </div>
                
                <div class="wizard-steps">
                    <div class="wizard-step active" data-step="1">
                        <div class="step-icon">🏠</div>
                        <h3>What is Local Home Agent?</h3>
                        <p>A privacy-first AI assistant that runs entirely on your local network. 
                        Your data never leaves your home!</p>
                        <ul class="feature-list">
                            <li>✅ Control smart devices with voice or text</li>
                            <li>✅ No cloud dependency - works offline</li>
                            <li>✅ Secure by design with thermodynamic AI</li>
                        </ul>
                    </div>
                    
                    <div class="wizard-step" data-step="2">
                        <div class="step-icon">🔌</div>
                        <h3>Connect Your Devices</h3>
                        <p>Link your smart home devices through Home Assistant or add them manually.</p>
                        <div class="quick-actions">
                            <button class="action-btn" onclick="window.location.href='/settings#devices'">
                                ⚙️ Setup Home Assistant
                            </button>
                            <button class="action-btn secondary" onclick="Onboarding.skipToStep(3)">
                                Skip for now →
                            </button>
                        </div>
                    </div>
                    
                    <div class="wizard-step" data-step="3">
                        <div class="step-icon">🤖</div>
                        <h3>Choose Your AI Model</h3>
                        <p>Select a local AI model for natural conversations.</p>
                        <div class="model-options">
                            <div class="model-option">
                                <strong>Llama 3.2 1B</strong>
                                <span class="badge">Fast</span>
                                <p>Best for older hardware (4GB RAM)</p>
                            </div>
                            <div class="model-option recommended">
                                <strong>Llama 3.2 3B</strong>
                                <span class="badge">Recommended</span>
                                <p>Good balance (8GB RAM)</p>
                            </div>
                            <div class="model-option">
                                <strong>Llama 3.2 8B</strong>
                                <span class="badge">Best</span>
                                <p>Most capable (16GB RAM)</p>
                            </div>
                        </div>
                        <button class="action-btn" onclick="window.location.href='/settings#models'">
                            ⚙️ Configure AI Model
                        </button>
                    </div>
                    
                    <div class="wizard-step" data-step="4">
                        <div class="step-icon">🎉</div>
                        <h3>You're All Set!</h3>
                        <p>Your Local Home Agent is ready to use.</p>
                        <div class="completion-actions">
                            <button class="action-btn primary" onclick="Onboarding.completeOnboarding()">
                                🚀 Start Using
                            </button>
                            <button class="action-btn secondary" onclick="Onboarding.startTour()">
                                📖 Take a Quick Tour
                            </button>
                        </div>
                    </div>
                </div>
                
                <div class="wizard-nav">
                    <button class="nav-btn prev" id="wizard-prev" onclick="Onboarding.prevStep()" disabled>
                        ← Previous
                    </button>
                    <button class="nav-btn next" id="wizard-next" onclick="Onboarding.nextStep()">
                        Next →
                    </button>
                </div>
            </div>
        `);
        
        this.currentStep = 1;
        document.body.appendChild(modal);
    },
    
    /**
     * Navigate wizard steps
     */
    nextStep: function() {
        if (this.currentStep < 4) {
            this.currentStep++;
            this.updateWizardUI();
        }
    },
    
    prevStep: function() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.updateWizardUI();
        }
    },
    
    skipToStep: function(step) {
        this.currentStep = step;
        this.updateWizardUI();
    },
    
    updateWizardUI: function() {
        // Update progress
        const progressFill = document.getElementById('wizard-progress-fill');
        const currentStepEl = document.getElementById('current-step');
        if (progressFill) progressFill.style.width = (this.currentStep * 25) + '%';
        if (currentStepEl) currentStepEl.textContent = this.currentStep;
        
        // Update steps visibility
        document.querySelectorAll('.wizard-step').forEach(step => {
            step.classList.remove('active');
            if (parseInt(step.dataset.step) === this.currentStep) {
                step.classList.add('active');
            }
        });
        
        // Update nav buttons
        const prevBtn = document.getElementById('wizard-prev');
        const nextBtn = document.getElementById('wizard-next');
        if (prevBtn) prevBtn.disabled = this.currentStep === 1;
        if (nextBtn) {
            nextBtn.style.display = this.currentStep === 4 ? 'none' : 'block';
        }
    },
    
    /**
     * Complete onboarding
     */
    completeOnboarding: function() {
        localStorage.setItem(this.STORAGE_KEYS.ONBOARDING_COMPLETE, 'true');
        this.closeModal('welcome-modal');
    },
    
    /**
     * LA2.2: Start guided tour
     */
    startTour: function() {
        this.closeModal('welcome-modal');
        this.currentTourStep = 0;
        this.showTourStep();
    },
    
    showTourStep: function() {
        const step = this.TOUR_STEPS[this.currentTourStep];
        if (!step) {
            this.completeTour();
            return;
        }
        
        // Find target element
        const target = document.querySelector(step.target);
        if (!target) {
            // Skip if element not found
            this.currentTourStep++;
            this.showTourStep();
            return;
        }
        
        // Create spotlight
        this.createSpotlight(target, step);
    },
    
    createSpotlight: function(target, step) {
        // Remove existing spotlight
        this.removeSpotlight();
        
        const rect = target.getBoundingClientRect();
        
        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'tour-overlay';
        overlay.id = 'tour-overlay';
        
        // Create spotlight hole
        const spotlight = document.createElement('div');
        spotlight.className = 'tour-spotlight';
        spotlight.style.cssText = `
            left: ${rect.left - 10}px;
            top: ${rect.top - 10}px;
            width: ${rect.width + 20}px;
            height: ${rect.height + 20}px;
        `;
        
        // Create tooltip
        const tooltip = document.createElement('div');
        tooltip.className = 'tour-tooltip ' + step.position;
        tooltip.innerHTML = `
            <div class="tour-tooltip-content">
                <h4>${step.title}</h4>
                <p>${step.content}</p>
                <div class="tour-nav">
                    <span class="tour-progress">${this.currentTourStep + 1} / ${this.TOUR_STEPS.length}</span>
                    <div class="tour-buttons">
                        <button onclick="Onboarding.skipTour()">Skip</button>
                        <button class="primary" onclick="Onboarding.nextTourStep()">
                            ${this.currentTourStep < this.TOUR_STEPS.length - 1 ? 'Next' : 'Done'}
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // Position tooltip
        this.positionTooltip(tooltip, rect, step.position);
        
        overlay.appendChild(spotlight);
        overlay.appendChild(tooltip);
        document.body.appendChild(overlay);
    },
    
    positionTooltip: function(tooltip, rect, position) {
        const margin = 20;
        switch (position) {
            case 'bottom':
                tooltip.style.top = (rect.bottom + margin) + 'px';
                tooltip.style.left = (rect.left + rect.width / 2) + 'px';
                break;
            case 'top':
                tooltip.style.bottom = (window.innerHeight - rect.top + margin) + 'px';
                tooltip.style.left = (rect.left + rect.width / 2) + 'px';
                break;
            case 'left':
                tooltip.style.top = (rect.top + rect.height / 2) + 'px';
                tooltip.style.right = (window.innerWidth - rect.left + margin) + 'px';
                break;
            case 'right':
                tooltip.style.top = (rect.top + rect.height / 2) + 'px';
                tooltip.style.left = (rect.right + margin) + 'px';
                break;
        }
    },
    
    nextTourStep: function() {
        this.currentTourStep++;
        if (this.currentTourStep >= this.TOUR_STEPS.length) {
            this.completeTour();
        } else {
            this.showTourStep();
        }
    },
    
    skipTour: function() {
        this.completeTour();
    },
    
    completeTour: function() {
        this.removeSpotlight();
        localStorage.setItem(this.STORAGE_KEYS.TOUR_COMPLETE, 'true');
        localStorage.setItem(this.STORAGE_KEYS.ONBOARDING_COMPLETE, 'true');
    },
    
    removeSpotlight: function() {
        const overlay = document.getElementById('tour-overlay');
        if (overlay) overlay.remove();
    },
    
    /**
     * LA2.4: Show keyboard shortcuts modal
     */
    showKeyboardShortcuts: function() {
        const modal = this.createModal('shortcuts-modal', `
            <div class="shortcuts-modal">
                <div class="modal-header">
                    <h2>⌨️ Keyboard Shortcuts</h2>
                    <button class="close-btn" onclick="Onboarding.closeModal('shortcuts-modal')">×</button>
                </div>
                <div class="shortcuts-list">
                    ${this.SHORTCUTS.map(s => `
                        <div class="shortcut-item">
                            <kbd>${s.key}</kbd>
                            <span>${s.action}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `);
        document.body.appendChild(modal);
    },
    
    /**
     * LA2.6: Show What's New modal
     */
    showWhatsNewModal: function() {
        const latest = this.CHANGELOG[0];
        const modal = this.createModal('whats-new-modal', `
            <div class="whats-new-modal">
                <div class="modal-header">
                    <h2>🎉 What's New in v${latest.version}</h2>
                    <button class="close-btn" onclick="Onboarding.closeWhatsNew()">×</button>
                </div>
                <p class="release-date">${latest.date}</p>
                <h3>${latest.title}</h3>
                <ul class="changes-list">
                    ${latest.changes.map(c => `<li>${c}</li>`).join('')}
                </ul>
                <button class="action-btn primary" onclick="Onboarding.closeWhatsNew()">
                    Got it!
                </button>
            </div>
        `);
        document.body.appendChild(modal);
    },
    
    closeWhatsNew: function() {
        localStorage.setItem(this.STORAGE_KEYS.SEEN_WHATS_NEW, 'true');
        this.closeModal('whats-new-modal');
    },
    
    /**
     * LA2.7: Add help bubble to page
     */
    addHelpBubble: function() {
        const bubble = document.createElement('button');
        bubble.className = 'help-bubble';
        bubble.innerHTML = '?';
        bubble.setAttribute('aria-label', 'Help');
        bubble.title = 'Need help?';
        bubble.onclick = () => this.showHelpMenu();
        document.body.appendChild(bubble);
    },
    
    showHelpMenu: function() {
        const existing = document.getElementById('help-menu');
        if (existing) {
            existing.remove();
            return;
        }
        
        const menu = document.createElement('div');
        menu.id = 'help-menu';
        menu.className = 'help-menu';
        menu.innerHTML = `
            <div class="help-menu-content">
                <button onclick="Onboarding.startTour(); this.parentElement.parentElement.remove();">
                    📖 Take a Tour
                </button>
                <button onclick="Onboarding.showKeyboardShortcuts(); this.parentElement.parentElement.remove();">
                    ⌨️ Keyboard Shortcuts
                </button>
                <button onclick="Onboarding.showVideoTutorials(); this.parentElement.parentElement.remove();">
                    🎬 Video Tutorials
                </button>
                <button onclick="Onboarding.showWhatsNewModal(); this.parentElement.parentElement.remove();">
                    🆕 What's New
                </button>
                <button onclick="window.location.href='/admin-guide'">
                    📡 WiFi Setup Guide
                </button>
            </div>
        `;
        document.body.appendChild(menu);
        
        // Close when clicking outside
        setTimeout(() => {
            document.addEventListener('click', function closeMenu(e) {
                if (!menu.contains(e.target) && !e.target.classList.contains('help-bubble')) {
                    menu.remove();
                    document.removeEventListener('click', closeMenu);
                }
            });
        }, 100);
    },
    
    /**
     * LA2.5: Show video tutorials modal
     */
    showVideoTutorials: function() {
        const modal = this.createModal('videos-modal', `
            <div class="videos-modal">
                <div class="modal-header">
                    <h2>🎬 Video Tutorials</h2>
                    <button class="close-btn" onclick="Onboarding.closeModal('videos-modal')">×</button>
                </div>
                <div class="video-grid">
                    <div class="video-card">
                        <div class="video-placeholder">
                            <span>▶️</span>
                        </div>
                        <h4>Getting Started</h4>
                        <p>5 min • Basics</p>
                    </div>
                    <div class="video-card">
                        <div class="video-placeholder">
                            <span>▶️</span>
                        </div>
                        <h4>Device Setup</h4>
                        <p>8 min • Devices</p>
                    </div>
                    <div class="video-card">
                        <div class="video-placeholder">
                            <span>▶️</span>
                        </div>
                        <h4>AI Chat Features</h4>
                        <p>6 min • Chat</p>
                    </div>
                    <div class="video-card">
                        <div class="video-placeholder">
                            <span>▶️</span>
                        </div>
                        <h4>Automations</h4>
                        <p>10 min • Advanced</p>
                    </div>
                </div>
                <p class="coming-soon">🚧 Video tutorials coming soon!</p>
            </div>
        `);
        document.body.appendChild(modal);
    },
    
    /**
     * LA2.3: Show feature tooltip
     */
    showFeatureTooltip: function(element, key) {
        const text = this.TOOLTIPS[key];
        if (!text) return;
        
        const tooltip = document.createElement('div');
        tooltip.className = 'feature-tooltip';
        tooltip.textContent = text;
        
        const rect = element.getBoundingClientRect();
        tooltip.style.top = (rect.bottom + 8) + 'px';
        tooltip.style.left = (rect.left + rect.width / 2) + 'px';
        
        document.body.appendChild(tooltip);
        
        element.addEventListener('mouseleave', () => tooltip.remove(), { once: true });
    },
    
    /**
     * Setup keyboard shortcuts
     */
    setupKeyboardShortcuts: function() {
        document.addEventListener('keydown', (e) => {
            // Ignore if typing in input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            
            const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
            const cmdOrCtrl = isMac ? e.metaKey : e.ctrlKey;
            
            if (e.key === '?') {
                e.preventDefault();
                this.showKeyboardShortcuts();
            } else if (e.key === 't' || e.key === 'T') {
                if (window.ThemeManager) ThemeManager.toggle();
            } else if (cmdOrCtrl && e.key === '/') {
                e.preventDefault();
                this.showHelpMenu();
            } else if (cmdOrCtrl && e.key === 'd') {
                e.preventDefault();
                window.location.href = '/dashboard';
            } else if (cmdOrCtrl && e.key === 'c' && !window.getSelection().toString()) {
                e.preventDefault();
                window.location.href = '/chat';
            } else if (e.key === 'Escape') {
                this.closeAllModals();
            }
        });
    },
    
    /**
     * Modal helpers
     */
    createModal: function(id, content) {
        const modal = document.createElement('div');
        modal.id = id;
        modal.className = 'onboarding-modal';
        modal.innerHTML = `<div class="modal-backdrop" onclick="Onboarding.closeModal('${id}')"></div>
            <div class="modal-content">${content}</div>`;
        return modal;
    },
    
    closeModal: function(id) {
        const modal = document.getElementById(id);
        if (modal) modal.remove();
    },
    
    closeAllModals: function() {
        document.querySelectorAll('.onboarding-modal').forEach(m => m.remove());
        this.removeSpotlight();
        const helpMenu = document.getElementById('help-menu');
        if (helpMenu) helpMenu.remove();
    },
    
    /**
     * Inject styles
     */
    injectStyles: function() {
        const style = document.createElement('style');
        style.textContent = `
            /* Onboarding Modal Base */
            .onboarding-modal {
                position: fixed;
                inset: 0;
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 16px;
            }
            
            .modal-backdrop {
                position: absolute;
                inset: 0;
                background: rgba(0, 0, 0, 0.8);
            }
            
            .modal-content {
                position: relative;
                background: var(--color-surface, #1a1a1a);
                border: 4px solid var(--color-border-strong, #fff);
                box-shadow: 12px 12px 0 var(--color-accent, #ff3333);
                max-width: 600px;
                width: 100%;
                max-height: 90vh;
                overflow-y: auto;
                padding: 32px;
                font-family: 'Courier New', monospace;
                color: var(--color-text, #fff);
            }
            
            .modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 24px;
                padding-bottom: 16px;
                border-bottom: 2px solid var(--color-border, #333);
            }
            
            .modal-header h2 {
                margin: 0;
                font-size: 1.5rem;
            }
            
            .close-btn {
                width: 40px;
                height: 40px;
                border: 2px solid var(--color-border-strong, #fff);
                background: transparent;
                color: var(--color-text, #fff);
                font-size: 1.5rem;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .close-btn:hover {
                background: var(--color-accent, #ff3333);
                color: #000;
            }
            
            /* Wizard Styles */
            .wizard-header {
                text-align: center;
                margin-bottom: 24px;
            }
            
            .wizard-header h2 {
                margin: 0 0 8px 0;
            }
            
            .wizard-progress {
                margin-bottom: 24px;
            }
            
            .progress-bar {
                height: 8px;
                background: var(--color-border, #333);
                border: 2px solid var(--color-border-strong, #fff);
                margin-bottom: 8px;
            }
            
            .progress-fill {
                height: 100%;
                background: var(--color-accent, #ff3333);
                transition: width 0.3s ease;
            }
            
            .progress-text {
                font-size: 0.875rem;
                color: var(--color-text-muted, #888);
            }
            
            .wizard-step {
                display: none;
            }
            
            .wizard-step.active {
                display: block;
            }
            
            .step-icon {
                font-size: 3rem;
                text-align: center;
                margin-bottom: 16px;
            }
            
            .wizard-step h3 {
                text-align: center;
                margin-bottom: 16px;
            }
            
            .wizard-step p {
                text-align: center;
                color: var(--color-text-muted, #888);
                margin-bottom: 16px;
            }
            
            .feature-list {
                list-style: none;
                padding: 0;
                margin: 24px 0;
            }
            
            .feature-list li {
                padding: 8px 0;
                border-bottom: 1px solid var(--color-border, #333);
            }
            
            .quick-actions, .completion-actions {
                display: flex;
                flex-direction: column;
                gap: 12px;
                margin-top: 24px;
            }
            
            .action-btn {
                padding: 16px 24px;
                border: 3px solid var(--color-border-strong, #fff);
                background: var(--color-surface, #1a1a1a);
                color: var(--color-text, #fff);
                font-family: 'Courier New', monospace;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.2s;
                text-align: center;
                text-decoration: none;
            }
            
            .action-btn:hover {
                transform: translate(2px, 2px);
            }
            
            .action-btn.primary {
                background: var(--color-accent, #ff3333);
                color: #000;
            }
            
            .action-btn.secondary {
                background: transparent;
                border-style: dashed;
            }
            
            /* Model options */
            .model-options {
                display: flex;
                flex-direction: column;
                gap: 12px;
                margin: 24px 0;
            }
            
            .model-option {
                padding: 12px 16px;
                border: 2px solid var(--color-border, #333);
                cursor: pointer;
            }
            
            .model-option:hover, .model-option.recommended {
                border-color: var(--color-accent, #ff3333);
            }
            
            .model-option .badge {
                background: var(--color-accent, #ff3333);
                color: #000;
                font-size: 0.75rem;
                padding: 2px 8px;
                margin-left: 8px;
            }
            
            .model-option p {
                margin: 4px 0 0 0;
                font-size: 0.875rem;
                text-align: left;
            }
            
            /* Wizard nav */
            .wizard-nav {
                display: flex;
                justify-content: space-between;
                margin-top: 32px;
                padding-top: 24px;
                border-top: 2px solid var(--color-border, #333);
            }
            
            .nav-btn {
                padding: 12px 24px;
                border: 2px solid var(--color-border-strong, #fff);
                background: var(--color-surface, #1a1a1a);
                color: var(--color-text, #fff);
                font-family: 'Courier New', monospace;
                cursor: pointer;
            }
            
            .nav-btn:disabled {
                opacity: 0.3;
                cursor: not-allowed;
            }
            
            .nav-btn.next {
                background: var(--color-accent, #ff3333);
                color: #000;
            }
            
            /* Tour overlay */
            .tour-overlay {
                position: fixed;
                inset: 0;
                background: rgba(0, 0, 0, 0.8);
                z-index: 9999;
            }
            
            .tour-spotlight {
                position: absolute;
                border: 3px solid var(--color-accent, #ff3333);
                box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.8);
                border-radius: 4px;
            }
            
            .tour-tooltip {
                position: fixed;
                background: var(--color-surface, #1a1a1a);
                border: 3px solid var(--color-border-strong, #fff);
                padding: 20px;
                max-width: 300px;
                z-index: 10000;
                box-shadow: 8px 8px 0 var(--color-accent, #ff3333);
                transform: translateX(-50%);
            }
            
            .tour-tooltip h4 {
                margin: 0 0 8px 0;
            }
            
            .tour-tooltip p {
                margin: 0 0 16px 0;
                color: var(--color-text-muted, #888);
            }
            
            .tour-nav {
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .tour-progress {
                font-size: 0.875rem;
                color: var(--color-text-muted, #888);
            }
            
            .tour-buttons button {
                padding: 8px 16px;
                border: 2px solid var(--color-border-strong, #fff);
                background: transparent;
                color: var(--color-text, #fff);
                font-family: 'Courier New', monospace;
                cursor: pointer;
                margin-left: 8px;
            }
            
            .tour-buttons button.primary {
                background: var(--color-accent, #ff3333);
                color: #000;
            }
            
            /* Shortcuts modal */
            .shortcuts-list {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            
            .shortcut-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px;
                border: 1px solid var(--color-border, #333);
            }
            
            .shortcut-item kbd {
                background: var(--color-bg, #0a0a0a);
                border: 2px solid var(--color-border, #333);
                padding: 4px 12px;
                font-family: 'Courier New', monospace;
                font-size: 0.875rem;
            }
            
            /* Videos modal */
            .video-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 16px;
                margin-bottom: 24px;
            }
            
            .video-card {
                border: 2px solid var(--color-border, #333);
                padding: 16px;
                cursor: pointer;
            }
            
            .video-card:hover {
                border-color: var(--color-accent, #ff3333);
            }
            
            .video-placeholder {
                height: 80px;
                background: var(--color-bg, #0a0a0a);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 2rem;
                margin-bottom: 12px;
            }
            
            .video-card h4 {
                margin: 0 0 4px 0;
            }
            
            .video-card p {
                margin: 0;
                font-size: 0.875rem;
                color: var(--color-text-muted, #888);
            }
            
            .coming-soon {
                text-align: center;
                color: var(--color-text-muted, #888);
                font-style: italic;
            }
            
            /* What's New modal */
            .release-date {
                color: var(--color-text-muted, #888);
                margin-bottom: 16px;
            }
            
            .changes-list {
                list-style: none;
                padding: 0;
                margin: 16px 0 24px 0;
            }
            
            .changes-list li {
                padding: 8px 0;
                border-bottom: 1px solid var(--color-border, #333);
            }
            
            /* Help bubble */
            .help-bubble {
                position: fixed;
                bottom: 80px;
                right: 16px;
                width: 48px;
                height: 48px;
                border-radius: 50%;
                border: 3px solid var(--color-border-strong, #fff);
                background: var(--color-accent, #ff3333);
                color: #000;
                font-size: 1.5rem;
                font-weight: bold;
                cursor: pointer;
                z-index: 900;
                box-shadow: 4px 4px 0 var(--color-border, #333);
                transition: all 0.2s;
            }
            
            .help-bubble:hover {
                transform: scale(1.1);
            }
            
            /* Help menu */
            .help-menu {
                position: fixed;
                bottom: 140px;
                right: 16px;
                z-index: 901;
            }
            
            .help-menu-content {
                background: var(--color-surface, #1a1a1a);
                border: 3px solid var(--color-border-strong, #fff);
                box-shadow: 8px 8px 0 var(--color-accent, #ff3333);
                display: flex;
                flex-direction: column;
            }
            
            .help-menu-content button {
                padding: 16px 24px;
                border: none;
                border-bottom: 1px solid var(--color-border, #333);
                background: transparent;
                color: var(--color-text, #fff);
                font-family: 'Courier New', monospace;
                text-align: left;
                cursor: pointer;
            }
            
            .help-menu-content button:last-child {
                border-bottom: none;
            }
            
            .help-menu-content button:hover {
                background: var(--color-surface-hover, #2a2a2a);
            }
            
            /* Feature tooltip */
            .feature-tooltip {
                position: fixed;
                background: var(--color-accent, #ff3333);
                color: #000;
                padding: 8px 16px;
                font-size: 0.875rem;
                font-family: 'Courier New', monospace;
                transform: translateX(-50%);
                z-index: 1000;
                white-space: nowrap;
            }
            
            .feature-tooltip::before {
                content: '';
                position: absolute;
                top: -8px;
                left: 50%;
                transform: translateX(-50%);
                border-left: 8px solid transparent;
                border-right: 8px solid transparent;
                border-bottom: 8px solid var(--color-accent, #ff3333);
            }
            
            @media (max-width: 600px) {
                .video-grid {
                    grid-template-columns: 1fr;
                }
                
                .modal-content {
                    padding: 20px;
                }
                
                .help-bubble {
                    bottom: 100px;
                }
                
                .help-menu {
                    bottom: 160px;
                    left: 16px;
                    right: 16px;
                }
            }
        `;
        document.head.appendChild(style);
    }
};

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => Onboarding.init());
} else {
    Onboarding.init();
}

// Export for use in other scripts
window.Onboarding = Onboarding;
