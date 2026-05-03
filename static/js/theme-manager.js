/**
 * Theme Manager - Local Home Agent
 * Shared theme toggle functionality for all templates
 * 
 * Neo-Brutalist + Swiss Design System
 * Supports: Dark mode (default), Light mode
 */

(function() {
    'use strict';

    // ============================================================
    // CONFIGURATION
    // ============================================================
    
    const THEME_KEY = 'local-home-agent-theme';
    const DEFAULT_THEME = 'dark';
    
    // ============================================================
    // THEME MANAGER CLASS
    // ============================================================

    class ThemeManager {
        constructor() {
            this.currentTheme = this.getStoredTheme() || this.getSystemTheme() || DEFAULT_THEME;
            this.toggleButton = null;
            this.init();
        }

        /**
         * Get theme from localStorage
         */
        getStoredTheme() {
            try {
                return localStorage.getItem(THEME_KEY);
            } catch (e) {
                console.warn('localStorage not available');
                return null;
            }
        }

        /**
         * Get system preference
         */
        getSystemTheme() {
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
                return 'light';
            }
            return 'dark';
        }

        /**
         * Apply theme to document
         */
        applyTheme(theme) {
            this.currentTheme = theme;
            document.documentElement.setAttribute('data-theme', theme);
            
            // Update meta theme-color for browser chrome
            const metaTheme = document.querySelector('meta[name="theme-color"]');
            if (metaTheme) {
                metaTheme.content = theme === 'light' ? '#f5f5f5' : '#ff3333';
            }
            
            // Store preference
            try {
                localStorage.setItem(THEME_KEY, theme);
            } catch (e) {
                // Ignore storage errors
            }

            // Update toggle button icon
            this.updateToggleIcon();

            // Dispatch event for other components
            window.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
        }

        /**
         * Toggle between themes
         */
        toggle() {
            const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
            this.applyTheme(newTheme);
            
            // Haptic feedback
            if (navigator.vibrate) {
                navigator.vibrate(15);
            }
        }

        /**
         * Update toggle button icon
         */
        updateToggleIcon() {
            const icon = document.getElementById('themeIcon');
            if (icon) {
                icon.textContent = this.currentTheme === 'light' ? '☀️' : '🌙';
            }
        }

        /**
         * Create and inject toggle button
         */
        createToggleButton() {
            // Check if toggle already exists
            if (document.getElementById('themeToggle')) {
                this.toggleButton = document.getElementById('themeToggle');
                return;
            }

            // Create button
            const button = document.createElement('button');
            button.id = 'themeToggle';
            button.className = 'theme-toggle';
            button.setAttribute('aria-label', 'Toggle theme');
            button.innerHTML = `<span id="themeIcon">${this.currentTheme === 'light' ? '☀️' : '🌙'}</span>`;
            
            // Add to document
            document.body.appendChild(button);
            this.toggleButton = button;
        }

        /**
         * Inject required CSS
         */
        injectStyles() {
            if (document.getElementById('theme-toggle-styles')) return;

            const css = `
                /* Theme Toggle Button */
                .theme-toggle {
                    position: fixed;
                    top: calc(16px + env(safe-area-inset-top, 0px));
                    right: 16px;
                    width: 44px;
                    height: 44px;
                    background: var(--color-surface, var(--bg-secondary, #1a1a1a));
                    border: 3px solid var(--color-border-strong, var(--border-color, #ffffff));
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    font-size: 1.3rem;
                    z-index: 9999;
                    transition: all 0.15s ease;
                    box-shadow: 3px 3px 0 var(--color-accent, #ff3333);
                }

                .theme-toggle:hover {
                    background: var(--color-surface-hover, var(--bg-tertiary, #2a2a2a));
                    transform: translate(2px, 2px);
                    box-shadow: 1px 1px 0 var(--color-accent, #ff3333);
                }

                .theme-toggle:active {
                    transform: translate(3px, 3px);
                    box-shadow: none;
                }

                /* Touch device adjustments */
                @media (hover: none) {
                    .theme-toggle:hover {
                        transform: none;
                        box-shadow: 3px 3px 0 var(--color-accent, #ff3333);
                    }
                    
                    .theme-toggle:active {
                        transform: scale(0.95);
                        opacity: 0.9;
                    }
                }

                /* Mobile positioning */
                @media (max-width: 480px) {
                    .theme-toggle {
                        top: calc(12px + env(safe-area-inset-top, 0px));
                        right: 12px;
                        width: 40px;
                        height: 40px;
                        font-size: 1.1rem;
                    }
                }

                /* When nav is present, adjust position */
                nav ~ .theme-toggle,
                .nav ~ .theme-toggle {
                    top: auto;
                    position: absolute;
                }

                /* Reduced motion */
                @media (prefers-reduced-motion: reduce) {
                    .theme-toggle {
                        transition: none;
                    }
                }
            `;

            const style = document.createElement('style');
            style.id = 'theme-toggle-styles';
            style.textContent = css;
            document.head.appendChild(style);
        }

        /**
         * Initialize theme manager
         */
        init() {
            // Apply initial theme immediately to prevent flash
            this.applyTheme(this.currentTheme);

            // Wait for DOM ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.setup());
            } else {
                this.setup();
            }
        }

        /**
         * Setup after DOM ready
         */
        setup() {
            this.injectStyles();
            this.createToggleButton();
            
            // Bind click handler
            if (this.toggleButton) {
                this.toggleButton.addEventListener('click', () => this.toggle());
            }

            // Listen for system theme changes
            if (window.matchMedia) {
                window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                    // Only auto-switch if user hasn't set a preference
                    if (!this.getStoredTheme()) {
                        this.applyTheme(e.matches ? 'dark' : 'light');
                    }
                });
            }

            console.log('🎨 Theme Manager initialized:', this.currentTheme);
        }
    }

    // ============================================================
    // AUTO-INITIALIZE
    // ============================================================

    // Create global instance
    window.ThemeManager = new ThemeManager();

})();
