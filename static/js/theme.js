/**
 * Theme Manager - Dark/Light Mode Toggle
 * Neo-Brutalist Swiss Design System
 * 
 * LA2: Tutorial & Onboarding - Theme toggle visible across platform
 */

const ThemeManager = {
    STORAGE_KEY: 'local-home-agent-theme',
    
    /**
     * Initialize theme from storage or system preference
     */
    init: function() {
        const saved = localStorage.getItem(this.STORAGE_KEY);
        if (saved) {
            this.setTheme(saved);
        } else {
            // Check system preference
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            this.setTheme(prefersDark ? 'dark' : 'light');
        }
        
        // Listen for system preference changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!localStorage.getItem(this.STORAGE_KEY)) {
                this.setTheme(e.matches ? 'dark' : 'light');
            }
        });
        
        // Create and inject toggle button
        this.injectToggleButton();
    },
    
    /**
     * Set theme
     */
    setTheme: function(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(this.STORAGE_KEY, theme);
        
        // Update meta theme-color
        const metaTheme = document.querySelector('meta[name="theme-color"]');
        if (metaTheme) {
            metaTheme.content = theme === 'dark' ? '#ff3333' : '#ff3333';
        }
        
        // Update toggle button icon if exists
        this.updateToggleIcon(theme);
    },
    
    /**
     * Toggle between dark and light
     */
    toggle: function() {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        this.setTheme(current === 'dark' ? 'light' : 'dark');
    },
    
    /**
     * Get current theme
     */
    getTheme: function() {
        return document.documentElement.getAttribute('data-theme') || 'dark';
    },
    
    /**
     * Update toggle button icon
     */
    updateToggleIcon: function(theme) {
        const btn = document.getElementById('theme-toggle-btn');
        if (btn) {
            btn.innerHTML = theme === 'dark' ? this.getSunIcon() : this.getMoonIcon();
            btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
            btn.title = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
        }
    },
    
    /**
     * Inject toggle button into navigation
     */
    injectToggleButton: function() {
        // Find nav or create floating button
        const nav = document.querySelector('nav') || document.querySelector('.mobile-nav');
        const currentTheme = this.getTheme();
        
        const btn = document.createElement('button');
        btn.id = 'theme-toggle-btn';
        btn.className = 'theme-toggle-btn';
        btn.innerHTML = currentTheme === 'dark' ? this.getSunIcon() : this.getMoonIcon();
        btn.setAttribute('aria-label', currentTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
        btn.title = currentTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
        btn.onclick = () => this.toggle();
        
        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .theme-toggle-btn {
                position: fixed;
                top: 16px;
                right: 16px;
                width: 44px;
                height: 44px;
                border: 3px solid var(--color-border-strong, #ffffff);
                background: var(--color-surface, #1a1a1a);
                color: var(--color-text, #ffffff);
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 1000;
                transition: all 0.2s ease;
                box-shadow: 4px 4px 0 var(--color-accent, #ff3333);
            }
            
            .theme-toggle-btn:hover {
                transform: translate(2px, 2px);
                box-shadow: 2px 2px 0 var(--color-accent, #ff3333);
            }
            
            .theme-toggle-btn:active {
                transform: translate(4px, 4px);
                box-shadow: none;
            }
            
            .theme-toggle-btn svg {
                width: 24px;
                height: 24px;
            }
            
            /* Adjust position when nav is present */
            nav ~ .theme-toggle-btn,
            .mobile-nav ~ .theme-toggle-btn {
                top: auto;
                bottom: 80px;
            }
            
            @media (min-width: 768px) {
                .theme-toggle-btn {
                    top: 20px;
                    right: 24px;
                }
            }
        `;
        document.head.appendChild(style);
        document.body.appendChild(btn);
    },
    
    /**
     * Sun icon (for switching to light mode)
     */
    getSunIcon: function() {
        return `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>`;
    },
    
    /**
     * Moon icon (for switching to dark mode)
     */
    getMoonIcon: function() {
        return `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
        </svg>`;
    }
};

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => ThemeManager.init());
} else {
    ThemeManager.init();
}

// Export for use in other scripts
window.ThemeManager = ThemeManager;
