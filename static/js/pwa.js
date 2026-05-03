/**
 * Local Home Agent - PWA Handler
 * Handles service worker registration, install prompts, and offline detection
 */

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        swPath: '/static/sw.js',
        installPromptDelay: 3000, // Show install prompt after 3 seconds
        offlineToastDuration: 5000
    };

    // State
    let deferredInstallPrompt = null;
    let isOnline = navigator.onLine;
    let swRegistration = null;

    /**
     * Initialize PWA features
     */
    async function initPWA() {
        // Register service worker
        await registerServiceWorker();

        // Setup install prompt handler
        setupInstallPrompt();

        // Setup online/offline detection
        setupNetworkDetection();

        // Check for updates
        checkForUpdates();

        console.log('[PWA] Initialized');
    }

    /**
     * Register service worker
     */
    async function registerServiceWorker() {
        if (!('serviceWorker' in navigator)) {
            console.log('[PWA] Service workers not supported');
            return;
        }

        try {
            swRegistration = await navigator.serviceWorker.register(CONFIG.swPath, {
                scope: '/'
            });

            console.log('[PWA] Service worker registered:', swRegistration.scope);

            // Handle updates
            swRegistration.addEventListener('updatefound', () => {
                const newWorker = swRegistration.installing;
                
                newWorker.addEventListener('statechange', () => {
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        // New version available
                        showUpdateNotification();
                    }
                });
            });

        } catch (error) {
            console.error('[PWA] Service worker registration failed:', error);
        }
    }

    /**
     * Setup install prompt handler
     */
    function setupInstallPrompt() {
        // Capture the install prompt event
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredInstallPrompt = e;
            
            // Show custom install UI after delay
            setTimeout(() => {
                if (deferredInstallPrompt && !isAppInstalled()) {
                    showInstallPrompt();
                }
            }, CONFIG.installPromptDelay);
        });

        // Track successful installs
        window.addEventListener('appinstalled', () => {
            deferredInstallPrompt = null;
            console.log('[PWA] App installed');
            hideInstallPrompt();
            
            // Track installation
            trackEvent('pwa_installed');
        });
    }

    /**
     * Check if app is already installed
     */
    function isAppInstalled() {
        // Check display mode
        if (window.matchMedia('(display-mode: standalone)').matches) {
            return true;
        }
        
        // Check iOS
        if (navigator.standalone === true) {
            return true;
        }
        
        return false;
    }

    /**
     * Show custom install prompt
     */
    function showInstallPrompt() {
        // Check if prompt already exists
        if (document.getElementById('pwa-install-prompt')) {
            return;
        }

        const prompt = document.createElement('div');
        prompt.id = 'pwa-install-prompt';
        prompt.innerHTML = `
            <div class="pwa-install-content">
                <div class="pwa-install-icon">🏠</div>
                <div class="pwa-install-text">
                    <strong>Install Home Agent</strong>
                    <span>Add to home screen for quick access</span>
                </div>
                <button class="pwa-install-btn" onclick="window.HomeAgentPWA.install()">
                    INSTALL
                </button>
                <button class="pwa-install-close" onclick="window.HomeAgentPWA.dismissInstall()">
                    ✕
                </button>
            </div>
        `;

        // Add styles if not already present
        if (!document.getElementById('pwa-install-styles')) {
            const styles = document.createElement('style');
            styles.id = 'pwa-install-styles';
            styles.textContent = `
                #pwa-install-prompt {
                    position: fixed;
                    bottom: 24px;
                    left: 24px;
                    right: 24px;
                    z-index: 10000;
                    animation: slideUp 0.3s ease-out;
                }
                
                @keyframes slideUp {
                    from {
                        opacity: 0;
                        transform: translateY(20px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                
                .pwa-install-content {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    padding: 16px;
                    background: white;
                    border: 4px solid black;
                    box-shadow: 8px 8px 0 black;
                    max-width: 500px;
                    margin: 0 auto;
                }
                
                .pwa-install-icon {
                    font-size: 2rem;
                    flex-shrink: 0;
                }
                
                .pwa-install-text {
                    flex: 1;
                    display: flex;
                    flex-direction: column;
                    gap: 4px;
                }
                
                .pwa-install-text strong {
                    font-size: 1rem;
                }
                
                .pwa-install-text span {
                    font-size: 0.85rem;
                    color: #666;
                }
                
                .pwa-install-btn {
                    padding: 10px 20px;
                    background: #ff3333;
                    color: white;
                    border: 3px solid black;
                    font-family: 'Courier New', monospace;
                    font-weight: bold;
                    cursor: pointer;
                    white-space: nowrap;
                    transition: all 0.2s;
                }
                
                .pwa-install-btn:hover {
                    transform: translate(2px, 2px);
                    box-shadow: none;
                }
                
                .pwa-install-close {
                    padding: 8px;
                    background: transparent;
                    border: none;
                    font-size: 1.25rem;
                    cursor: pointer;
                    opacity: 0.5;
                    transition: opacity 0.2s;
                }
                
                .pwa-install-close:hover {
                    opacity: 1;
                }
                
                @media (max-width: 480px) {
                    #pwa-install-prompt {
                        bottom: 16px;
                        left: 16px;
                        right: 16px;
                    }
                    
                    .pwa-install-content {
                        padding: 12px;
                        box-shadow: 4px 4px 0 black;
                    }
                    
                    .pwa-install-icon {
                        font-size: 1.5rem;
                    }
                }
            `;
            document.head.appendChild(styles);
        }

        document.body.appendChild(prompt);

        // iOS-specific instructions
        if (isIOS() && !isAppInstalled()) {
            showIOSInstallInstructions();
        }
    }

    /**
     * Hide install prompt
     */
    function hideInstallPrompt() {
        const prompt = document.getElementById('pwa-install-prompt');
        if (prompt) {
            prompt.remove();
        }
    }

    /**
     * Trigger the install prompt
     */
    async function install() {
        if (!deferredInstallPrompt) {
            console.log('[PWA] No install prompt available');
            return;
        }

        // Show the browser's install prompt
        deferredInstallPrompt.prompt();

        // Wait for user choice
        const { outcome } = await deferredInstallPrompt.userChoice;
        console.log('[PWA] Install prompt outcome:', outcome);

        // Clear the saved prompt
        deferredInstallPrompt = null;
        hideInstallPrompt();
    }

    /**
     * Dismiss install prompt
     */
    function dismissInstall() {
        hideInstallPrompt();
        
        // Don't show again for this session
        sessionStorage.setItem('pwa-install-dismissed', 'true');
    }

    /**
     * Show iOS-specific install instructions
     */
    function showIOSInstallInstructions() {
        const prompt = document.getElementById('pwa-install-prompt');
        if (!prompt) return;

        prompt.querySelector('.pwa-install-content').innerHTML = `
            <div class="pwa-install-icon">📱</div>
            <div class="pwa-install-text">
                <strong>Install Home Agent</strong>
                <span>Tap <strong>Share</strong> then <strong>Add to Home Screen</strong></span>
            </div>
            <button class="pwa-install-close" onclick="window.HomeAgentPWA.dismissInstall()">
                ✕
            </button>
        `;
    }

    /**
     * Check if device is iOS
     */
    function isIOS() {
        return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    }

    /**
     * Setup network detection
     */
    function setupNetworkDetection() {
        window.addEventListener('online', () => {
            isOnline = true;
            showNetworkToast('online');
            
            // Trigger background sync
            if (swRegistration && 'sync' in swRegistration) {
                swRegistration.sync.register('sync-device-actions');
            }
        });

        window.addEventListener('offline', () => {
            isOnline = false;
            showNetworkToast('offline');
        });

        // Initial state
        if (!navigator.onLine) {
            showNetworkToast('offline');
        }
    }

    /**
     * Show network status toast
     */
    function showNetworkToast(status) {
        // Remove existing toast
        const existing = document.getElementById('network-toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.id = 'network-toast';
        toast.className = `network-toast ${status}`;
        toast.innerHTML = status === 'online' 
            ? '✓ Back online' 
            : '⚠ You are offline';

        // Add styles if not present
        if (!document.getElementById('network-toast-styles')) {
            const styles = document.createElement('style');
            styles.id = 'network-toast-styles';
            styles.textContent = `
                .network-toast {
                    position: fixed;
                    top: env(safe-area-inset-top, 16px);
                    left: 50%;
                    transform: translateX(-50%);
                    padding: 12px 24px;
                    font-family: 'Courier New', monospace;
                    font-weight: bold;
                    font-size: 0.9rem;
                    border: 3px solid black;
                    z-index: 10001;
                    animation: toastIn 0.3s ease-out;
                }
                
                @keyframes toastIn {
                    from {
                        opacity: 0;
                        transform: translateX(-50%) translateY(-20px);
                    }
                    to {
                        opacity: 1;
                        transform: translateX(-50%) translateY(0);
                    }
                }
                
                .network-toast.online {
                    background: #00cc00;
                    color: white;
                }
                
                .network-toast.offline {
                    background: #ff3333;
                    color: white;
                }
            `;
            document.head.appendChild(styles);
        }

        document.body.appendChild(toast);

        // Auto-hide for online status
        if (status === 'online') {
            setTimeout(() => {
                toast.style.animation = 'toastIn 0.3s ease-out reverse';
                setTimeout(() => toast.remove(), 300);
            }, CONFIG.offlineToastDuration);
        }
    }

    /**
     * Check for service worker updates
     */
    async function checkForUpdates() {
        if (!swRegistration) return;

        try {
            await swRegistration.update();
        } catch (error) {
            console.log('[PWA] Update check failed:', error);
        }
    }

    /**
     * Show update notification
     */
    function showUpdateNotification() {
        const notification = document.createElement('div');
        notification.id = 'update-notification';
        notification.innerHTML = `
            <div class="update-content">
                <span>🔄 Update available</span>
                <button onclick="window.HomeAgentPWA.applyUpdate()">UPDATE NOW</button>
            </div>
        `;

        // Add styles
        if (!document.getElementById('update-notification-styles')) {
            const styles = document.createElement('style');
            styles.id = 'update-notification-styles';
            styles.textContent = `
                #update-notification {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    background: #1a1a1a;
                    color: white;
                    padding: 12px 16px;
                    z-index: 10002;
                    animation: slideDown 0.3s ease-out;
                }
                
                @keyframes slideDown {
                    from { transform: translateY(-100%); }
                    to { transform: translateY(0); }
                }
                
                .update-content {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    gap: 16px;
                    max-width: 600px;
                    margin: 0 auto;
                    font-family: 'Courier New', monospace;
                }
                
                #update-notification button {
                    padding: 8px 16px;
                    background: #ff3333;
                    color: white;
                    border: 2px solid white;
                    font-family: 'Courier New', monospace;
                    font-weight: bold;
                    cursor: pointer;
                }
            `;
            document.head.appendChild(styles);
        }

        document.body.appendChild(notification);
    }

    /**
     * Apply the update and reload
     */
    function applyUpdate() {
        if (swRegistration && swRegistration.waiting) {
            swRegistration.waiting.postMessage({ type: 'SKIP_WAITING' });
        }
        window.location.reload();
    }

    /**
     * Track analytics event
     */
    function trackEvent(eventName, data = {}) {
        console.log('[PWA] Event:', eventName, data);
        // Add your analytics tracking here
    }

    // Expose public API
    window.HomeAgentPWA = {
        init: initPWA,
        install: install,
        dismissInstall: dismissInstall,
        applyUpdate: applyUpdate,
        isOnline: () => isOnline,
        isInstalled: isAppInstalled
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPWA);
    } else {
        initPWA();
    }

})();
