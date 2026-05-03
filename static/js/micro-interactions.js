/**
 * Micro-Interactions Module for Local Home Agent
 * P5: MI1 - Local Agent Animations
 * 
 * Features:
 * - MI1.1: Device toggle flip animation
 * - MI1.2: Energy meter pulse effect
 * - MI1.3: Processing orb animation
 * - MI1.4: Voice waveform visualization
 * - MI1.5: Proximity indicator ripples
 * - MI1.6: Status glow transitions
 * - MI1.7: Connection beam animation
 * - MI1.8: Error shake effect
 * - MI1.9: Success checkmark morph
 * - MI1.10: Loading skeleton shimmer
 * - MI1.11: Tooltip slide-in
 * - MI1.12: Card hover 3D tilt
 * - MI1.13: Button press haptic feedback
 */

// ============================================================================
// ANIMATION CONFIGURATION
// ============================================================================

const AnimationConfig = {
    // Timing functions
    easing: {
        bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
        smooth: 'cubic-bezier(0.4, 0, 0.2, 1)',
        snappy: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
        elastic: 'cubic-bezier(0.68, -0.6, 0.32, 1.6)'
    },
    
    // Duration presets (ms)
    duration: {
        instant: 50,
        fast: 150,
        normal: 300,
        slow: 500,
        glacial: 1000
    },
    
    // Feature flags
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    hapticEnabled: 'vibrate' in navigator
};

// ============================================================================
// MI1.1: DEVICE TOGGLE FLIP ANIMATION
// ============================================================================

class DeviceToggle {
    constructor(element) {
        this.element = element;
        this.isOn = element.classList.contains('active');
        this.init();
    }
    
    init() {
        this.element.addEventListener('click', () => this.toggle());
        this.element.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.toggle();
            }
        });
    }
    
    toggle() {
        if (AnimationConfig.reducedMotion) {
            this.isOn = !this.isOn;
            this.element.classList.toggle('active', this.isOn);
            return;
        }
        
        // 3D flip animation
        this.element.style.transform = 'rotateX(90deg) scale(0.9)';
        this.element.style.opacity = '0.5';
        
        setTimeout(() => {
            this.isOn = !this.isOn;
            this.element.classList.toggle('active', this.isOn);
            this.element.style.transform = 'rotateX(0deg) scale(1)';
            this.element.style.opacity = '1';
            
            // Haptic feedback on mobile
            if (AnimationConfig.hapticEnabled) {
                navigator.vibrate(this.isOn ? [15, 5, 25] : [25]);
            }
        }, AnimationConfig.duration.fast);
        
        this.element.dispatchEvent(new CustomEvent('device-toggle', { 
            detail: { isOn: !this.isOn } 
        }));
    }
    
    setOn(value) {
        if (this.isOn !== value) {
            this.toggle();
        }
    }
}

// ============================================================================
// MI1.2: ENERGY METER PULSE EFFECT
// ============================================================================

class EnergyMeter {
    constructor(element, options = {}) {
        this.element = element;
        this.value = options.initialValue || 100;
        this.maxValue = options.maxValue || 100;
        this.warningThreshold = options.warningThreshold || 30;
        this.criticalThreshold = options.criticalThreshold || 15;
        this.pulseInterval = null;
        this.init();
    }
    
    init() {
        this.element.innerHTML = `
            <div class="energy-meter-container">
                <div class="energy-meter-fill"></div>
                <div class="energy-meter-pulse"></div>
                <div class="energy-meter-glow"></div>
                <span class="energy-meter-label">${this.value}%</span>
            </div>
        `;
        
        this.fill = this.element.querySelector('.energy-meter-fill');
        this.pulse = this.element.querySelector('.energy-meter-pulse');
        this.glow = this.element.querySelector('.energy-meter-glow');
        this.label = this.element.querySelector('.energy-meter-label');
        
        this.update(this.value);
    }
    
    update(newValue) {
        const oldValue = this.value;
        this.value = Math.max(0, Math.min(this.maxValue, newValue));
        const percentage = (this.value / this.maxValue) * 100;
        
        // Animate fill
        this.fill.style.width = `${percentage}%`;
        
        // Update color based on level
        const color = this.getColor(this.value);
        this.fill.style.background = color.gradient;
        this.glow.style.boxShadow = `0 0 20px ${color.primary}`;
        
        // Animate label with counting effect
        this.animateValue(oldValue, this.value);
        
        // Pulse effect for critical levels
        if (this.value <= this.criticalThreshold) {
            this.startCriticalPulse();
        } else if (this.value <= this.warningThreshold) {
            this.startWarningPulse();
        } else {
            this.stopPulse();
        }
    }
    
    getColor(value) {
        if (value <= this.criticalThreshold) {
            return {
                primary: '#ef4444',
                gradient: 'linear-gradient(90deg, #dc2626, #ef4444)'
            };
        } else if (value <= this.warningThreshold) {
            return {
                primary: '#f59e0b',
                gradient: 'linear-gradient(90deg, #d97706, #f59e0b)'
            };
        }
        return {
            primary: '#22c55e',
            gradient: 'linear-gradient(90deg, #16a34a, #22c55e)'
        };
    }
    
    animateValue(from, to) {
        if (AnimationConfig.reducedMotion) {
            this.label.textContent = `${Math.round(to)}%`;
            return;
        }
        
        const duration = AnimationConfig.duration.normal;
        const startTime = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
            
            const current = from + (to - from) * eased;
            this.label.textContent = `${Math.round(current)}%`;
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }
    
    startCriticalPulse() {
        if (this.pulseInterval) return;
        
        this.pulse.style.animation = 'energy-critical-pulse 0.5s ease-in-out infinite';
        this.element.classList.add('critical');
        
        // Flash effect
        this.pulseInterval = setInterval(() => {
            this.glow.style.opacity = this.glow.style.opacity === '1' ? '0.3' : '1';
        }, 500);
    }
    
    startWarningPulse() {
        if (this.pulseInterval) return;
        
        this.pulse.style.animation = 'energy-warning-pulse 1s ease-in-out infinite';
        this.element.classList.add('warning');
    }
    
    stopPulse() {
        if (this.pulseInterval) {
            clearInterval(this.pulseInterval);
            this.pulseInterval = null;
        }
        this.pulse.style.animation = 'none';
        this.glow.style.opacity = '0.5';
        this.element.classList.remove('critical', 'warning');
    }
    
    destroy() {
        this.stopPulse();
    }
}

// ============================================================================
// MI1.3: PROCESSING ORB ANIMATION
// ============================================================================

class ProcessingOrb {
    constructor(element) {
        this.element = element;
        this.isProcessing = false;
        this.thinkingMode = 'standard';
        this.init();
    }
    
    init() {
        this.element.innerHTML = `
            <div class="orb-container">
                <div class="orb-core"></div>
                <div class="orb-ring orb-ring-1"></div>
                <div class="orb-ring orb-ring-2"></div>
                <div class="orb-ring orb-ring-3"></div>
                <div class="orb-particles"></div>
            </div>
        `;
        
        this.core = this.element.querySelector('.orb-core');
        this.rings = this.element.querySelectorAll('.orb-ring');
        this.particles = this.element.querySelector('.orb-particles');
        
        // Create particles
        for (let i = 0; i < 12; i++) {
            const particle = document.createElement('div');
            particle.className = 'orb-particle';
            particle.style.setProperty('--delay', `${i * 0.1}s`);
            particle.style.setProperty('--angle', `${i * 30}deg`);
            this.particles.appendChild(particle);
        }
    }
    
    setMode(mode) {
        this.thinkingMode = mode;
        this.element.dataset.mode = mode;
        
        // Adjust animation speed based on mode
        const speeds = {
            quick: '0.5s',
            standard: '1s',
            deep: '2s',
            recursive: '3s'
        };
        
        this.element.style.setProperty('--orb-speed', speeds[mode] || '1s');
    }
    
    startProcessing() {
        if (this.isProcessing) return;
        this.isProcessing = true;
        
        this.element.classList.add('processing');
        
        if (!AnimationConfig.reducedMotion) {
            // Rotate rings in opposite directions
            this.rings[0].style.animation = 'orb-rotate 2s linear infinite';
            this.rings[1].style.animation = 'orb-rotate 3s linear infinite reverse';
            this.rings[2].style.animation = 'orb-rotate 4s linear infinite';
            
            // Core pulsing
            this.core.style.animation = 'orb-pulse 1.5s ease-in-out infinite';
            
            // Particles orbiting
            this.particles.style.animation = 'particles-orbit 4s linear infinite';
        }
    }
    
    stopProcessing(success = true) {
        if (!this.isProcessing) return;
        this.isProcessing = false;
        
        // Flash effect on completion
        if (!AnimationConfig.reducedMotion) {
            this.core.style.animation = success 
                ? 'orb-success-flash 0.5s ease-out' 
                : 'orb-error-flash 0.5s ease-out';
            
            this.core.style.backgroundColor = success ? '#22c55e' : '#ef4444';
        }
        
        setTimeout(() => {
            this.element.classList.remove('processing');
            this.rings.forEach(ring => ring.style.animation = 'none');
            this.particles.style.animation = 'none';
            this.core.style.animation = 'none';
            this.core.style.backgroundColor = '';
        }, 500);
    }
    
    setProgress(percent) {
        // Visualize progress through ring expansion
        const scale = 0.8 + (percent / 100) * 0.4;
        this.rings.forEach((ring, i) => {
            ring.style.transform = `scale(${scale - i * 0.1})`;
        });
    }
}

// ============================================================================
// MI1.4: VOICE WAVEFORM VISUALIZATION
// ============================================================================

class VoiceWaveform {
    constructor(canvas, options = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.bars = options.bars || 24;
        this.barWidth = options.barWidth || 4;
        this.barGap = options.barGap || 2;
        this.barColor = options.barColor || '#3b82f6';
        this.activeColor = options.activeColor || '#60a5fa';
        this.isActive = false;
        this.animationFrame = null;
        this.audioData = new Array(this.bars).fill(0);
        
        this.resize();
        window.addEventListener('resize', () => this.resize());
    }
    
    resize() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.ctx.scale(dpr, dpr);
    }
    
    start(audioContext, source) {
        if (this.isActive) return;
        this.isActive = true;
        
        // Create analyser for real audio
        if (audioContext && source) {
            this.analyser = audioContext.createAnalyser();
            this.analyser.fftSize = 64;
            source.connect(this.analyser);
            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        }
        
        this.animate();
    }
    
    simulate() {
        // Simulated waveform when no audio input
        this.isActive = true;
        this.simulateData();
        this.animate();
    }
    
    simulateData() {
        if (!this.isActive) return;
        
        // Generate smooth wave-like data
        const time = performance.now() / 1000;
        this.audioData = this.audioData.map((_, i) => {
            const wave1 = Math.sin(time * 3 + i * 0.5) * 0.3;
            const wave2 = Math.sin(time * 5 + i * 0.3) * 0.2;
            const wave3 = Math.sin(time * 7 + i * 0.7) * 0.15;
            const noise = (Math.random() - 0.5) * 0.1;
            return Math.abs(wave1 + wave2 + wave3 + noise);
        });
        
        requestAnimationFrame(() => this.simulateData());
    }
    
    animate() {
        if (!this.isActive) return;
        
        const rect = this.canvas.getBoundingClientRect();
        this.ctx.clearRect(0, 0, rect.width, rect.height);
        
        // Get audio data
        if (this.analyser) {
            this.analyser.getByteFrequencyData(this.dataArray);
            this.audioData = Array.from(this.dataArray)
                .slice(0, this.bars)
                .map(v => v / 255);
        }
        
        const totalWidth = (this.barWidth + this.barGap) * this.bars - this.barGap;
        const startX = (rect.width - totalWidth) / 2;
        const centerY = rect.height / 2;
        const maxHeight = rect.height * 0.8;
        
        this.audioData.forEach((value, i) => {
            const x = startX + i * (this.barWidth + this.barGap);
            const height = Math.max(4, value * maxHeight);
            
            // Gradient for active bars
            const gradient = this.ctx.createLinearGradient(x, centerY - height/2, x, centerY + height/2);
            gradient.addColorStop(0, this.activeColor);
            gradient.addColorStop(0.5, this.barColor);
            gradient.addColorStop(1, this.activeColor);
            
            this.ctx.fillStyle = gradient;
            this.ctx.beginPath();
            this.ctx.roundRect(
                x, 
                centerY - height/2, 
                this.barWidth, 
                height, 
                this.barWidth / 2
            );
            this.ctx.fill();
        });
        
        this.animationFrame = requestAnimationFrame(() => this.animate());
    }
    
    stop() {
        this.isActive = false;
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
        
        // Fade out animation
        const fadeOut = () => {
            this.audioData = this.audioData.map(v => v * 0.9);
            const rect = this.canvas.getBoundingClientRect();
            this.ctx.clearRect(0, 0, rect.width, rect.height);
            
            if (this.audioData.some(v => v > 0.01)) {
                this.drawBars();
                requestAnimationFrame(fadeOut);
            }
        };
        fadeOut();
    }
}

// ============================================================================
// MI1.5: PROXIMITY INDICATOR RIPPLES
// ============================================================================

class ProximityIndicator {
    constructor(element) {
        this.element = element;
        this.level = 'unknown';
        this.rippleCount = 0;
        this.init();
    }
    
    init() {
        this.element.innerHTML = `
            <div class="proximity-container">
                <div class="proximity-center"></div>
                <div class="proximity-ripples"></div>
                <div class="proximity-label">Scanning...</div>
            </div>
        `;
        
        this.center = this.element.querySelector('.proximity-center');
        this.ripples = this.element.querySelector('.proximity-ripples');
        this.label = this.element.querySelector('.proximity-label');
    }
    
    setLevel(level) {
        const levels = {
            near: { color: '#22c55e', rippleSpeed: '1s', label: 'Admin Nearby' },
            medium: { color: '#f59e0b', rippleSpeed: '2s', label: 'In Range' },
            far: { color: '#ef4444', rippleSpeed: '3s', label: 'Out of Range' },
            unknown: { color: '#6b7280', rippleSpeed: '4s', label: 'Scanning...' }
        };
        
        const config = levels[level] || levels.unknown;
        this.level = level;
        
        this.center.style.backgroundColor = config.color;
        this.element.dataset.level = level;
        this.label.textContent = config.label;
        
        // Trigger ripple effect
        this.createRipple(config.color, config.rippleSpeed);
    }
    
    createRipple(color, speed) {
        if (AnimationConfig.reducedMotion) return;
        
        const ripple = document.createElement('div');
        ripple.className = 'proximity-ripple';
        ripple.style.borderColor = color;
        ripple.style.animationDuration = speed;
        
        this.ripples.appendChild(ripple);
        
        // Clean up after animation
        ripple.addEventListener('animationend', () => {
            ripple.remove();
        });
        
        // Continuous ripples while level is active
        this.rippleCount++;
        if (this.rippleCount < 5) {
            setTimeout(() => {
                if (this.element.dataset.level === this.level) {
                    this.createRipple(color, speed);
                }
            }, parseFloat(speed) * 500);
        }
    }
    
    pulse() {
        this.center.style.animation = 'proximity-pulse 0.5s ease-out';
        setTimeout(() => {
            this.center.style.animation = '';
        }, 500);
    }
}

// ============================================================================
// MI1.6: STATUS GLOW TRANSITIONS
// ============================================================================

class StatusGlow {
    constructor(element) {
        this.element = element;
        this.status = 'idle';
        this.init();
    }
    
    init() {
        this.element.style.transition = `
            box-shadow ${AnimationConfig.duration.normal}ms ${AnimationConfig.easing.smooth},
            border-color ${AnimationConfig.duration.normal}ms ${AnimationConfig.easing.smooth}
        `;
    }
    
    setStatus(status) {
        const statusStyles = {
            idle: {
                glow: '0 0 0 0 transparent',
                border: '#374151'
            },
            active: {
                glow: '0 0 20px 0 rgba(59, 130, 246, 0.5), 0 0 40px 0 rgba(59, 130, 246, 0.3)',
                border: '#3b82f6'
            },
            success: {
                glow: '0 0 20px 0 rgba(34, 197, 94, 0.5), 0 0 40px 0 rgba(34, 197, 94, 0.3)',
                border: '#22c55e'
            },
            warning: {
                glow: '0 0 20px 0 rgba(245, 158, 11, 0.5), 0 0 40px 0 rgba(245, 158, 11, 0.3)',
                border: '#f59e0b'
            },
            error: {
                glow: '0 0 20px 0 rgba(239, 68, 68, 0.5), 0 0 40px 0 rgba(239, 68, 68, 0.3)',
                border: '#ef4444'
            },
            processing: {
                glow: '0 0 30px 0 rgba(139, 92, 246, 0.6), 0 0 60px 0 rgba(139, 92, 246, 0.3)',
                border: '#8b5cf6'
            }
        };
        
        const style = statusStyles[status] || statusStyles.idle;
        this.status = status;
        
        this.element.style.boxShadow = style.glow;
        this.element.style.borderColor = style.border;
        this.element.dataset.status = status;
        
        // Pulse animation for attention-grabbing states
        if (['warning', 'error'].includes(status) && !AnimationConfig.reducedMotion) {
            this.startPulse(style.glow);
        } else {
            this.stopPulse();
        }
    }
    
    startPulse(glowStyle) {
        if (this.pulseAnimation) return;
        
        let intensity = 1;
        let direction = -1;
        
        this.pulseAnimation = setInterval(() => {
            intensity += direction * 0.1;
            if (intensity <= 0.3 || intensity >= 1) direction *= -1;
            
            this.element.style.filter = `brightness(${0.9 + intensity * 0.1})`;
        }, 50);
    }
    
    stopPulse() {
        if (this.pulseAnimation) {
            clearInterval(this.pulseAnimation);
            this.pulseAnimation = null;
            this.element.style.filter = '';
        }
    }
}

// ============================================================================
// MI1.7: CONNECTION BEAM ANIMATION
// ============================================================================

class ConnectionBeam {
    constructor(svg, sourceElement, targetElement) {
        this.svg = svg;
        this.source = sourceElement;
        this.target = targetElement;
        this.isConnected = false;
        this.init();
    }
    
    init() {
        // Create path element
        this.path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        this.path.setAttribute('fill', 'none');
        this.path.setAttribute('stroke', 'url(#beam-gradient)');
        this.path.setAttribute('stroke-width', '2');
        this.path.setAttribute('stroke-linecap', 'round');
        
        // Create gradient
        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        defs.innerHTML = `
            <linearGradient id="beam-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color:#3b82f6;stop-opacity:0" />
                <stop offset="50%" style="stop-color:#3b82f6;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#22c55e;stop-opacity:0" />
            </linearGradient>
        `;
        
        this.svg.appendChild(defs);
        this.svg.appendChild(this.path);
        
        // Animated dots along path
        this.dots = [];
        for (let i = 0; i < 3; i++) {
            const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            dot.setAttribute('r', '4');
            dot.setAttribute('fill', '#60a5fa');
            dot.style.opacity = '0';
            this.svg.appendChild(dot);
            this.dots.push(dot);
        }
    }
    
    connect() {
        if (this.isConnected) return;
        this.isConnected = true;
        
        this.updatePath();
        this.animateConnection();
        
        // Keep updating path if elements move
        this.updateInterval = setInterval(() => this.updatePath(), 100);
    }
    
    disconnect() {
        this.isConnected = false;
        
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        // Fade out animation
        this.path.style.transition = 'opacity 0.3s';
        this.path.style.opacity = '0';
        this.dots.forEach(dot => dot.style.opacity = '0');
    }
    
    updatePath() {
        const sourceRect = this.source.getBoundingClientRect();
        const targetRect = this.target.getBoundingClientRect();
        const svgRect = this.svg.getBoundingClientRect();
        
        const x1 = sourceRect.left + sourceRect.width / 2 - svgRect.left;
        const y1 = sourceRect.top + sourceRect.height / 2 - svgRect.top;
        const x2 = targetRect.left + targetRect.width / 2 - svgRect.left;
        const y2 = targetRect.top + targetRect.height / 2 - svgRect.top;
        
        // Curved path
        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2 - 50;
        
        this.path.setAttribute('d', `M ${x1} ${y1} Q ${midX} ${midY} ${x2} ${y2}`);
    }
    
    animateConnection() {
        if (!this.isConnected || AnimationConfig.reducedMotion) return;
        
        const pathLength = this.path.getTotalLength();
        
        this.dots.forEach((dot, i) => {
            const delay = i * 0.3;
            const animate = () => {
                if (!this.isConnected) return;
                
                let progress = ((performance.now() / 1000 + delay) % 2) / 2;
                const point = this.path.getPointAtLength(progress * pathLength);
                
                dot.setAttribute('cx', point.x);
                dot.setAttribute('cy', point.y);
                dot.style.opacity = Math.sin(progress * Math.PI);
                
                requestAnimationFrame(animate);
            };
            requestAnimationFrame(animate);
        });
    }
}

// ============================================================================
// MI1.8: ERROR SHAKE EFFECT
// ============================================================================

function shakeElement(element, intensity = 'normal') {
    if (AnimationConfig.reducedMotion) {
        element.classList.add('error-highlight');
        setTimeout(() => element.classList.remove('error-highlight'), 1000);
        return;
    }
    
    const intensities = {
        light: { distance: 3, duration: 300 },
        normal: { distance: 6, duration: 400 },
        heavy: { distance: 10, duration: 500 }
    };
    
    const config = intensities[intensity] || intensities.normal;
    const keyframes = [
        { transform: 'translateX(0)' },
        { transform: `translateX(-${config.distance}px)` },
        { transform: `translateX(${config.distance}px)` },
        { transform: `translateX(-${config.distance}px)` },
        { transform: `translateX(${config.distance}px)` },
        { transform: `translateX(-${config.distance / 2}px)` },
        { transform: `translateX(${config.distance / 2}px)` },
        { transform: 'translateX(0)' }
    ];
    
    element.animate(keyframes, {
        duration: config.duration,
        easing: AnimationConfig.easing.snappy
    });
    
    // Haptic feedback
    if (AnimationConfig.hapticEnabled) {
        navigator.vibrate([50, 30, 50, 30, 50]);
    }
}

// ============================================================================
// MI1.9: SUCCESS CHECKMARK MORPH
// ============================================================================

class SuccessCheckmark {
    constructor(element) {
        this.element = element;
        this.init();
    }
    
    init() {
        this.element.innerHTML = `
            <svg class="success-checkmark" viewBox="0 0 52 52">
                <circle class="checkmark-circle" cx="26" cy="26" r="25" fill="none"/>
                <path class="checkmark-check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
            </svg>
        `;
        
        this.circle = this.element.querySelector('.checkmark-circle');
        this.check = this.element.querySelector('.checkmark-check');
    }
    
    animate() {
        if (AnimationConfig.reducedMotion) {
            this.element.classList.add('success-visible');
            return;
        }
        
        // Circle draw animation
        const circleLength = 2 * Math.PI * 25;
        this.circle.style.strokeDasharray = circleLength;
        this.circle.style.strokeDashoffset = circleLength;
        
        this.circle.animate([
            { strokeDashoffset: circleLength },
            { strokeDashoffset: 0 }
        ], {
            duration: 400,
            easing: AnimationConfig.easing.smooth,
            fill: 'forwards'
        });
        
        // Checkmark draw animation (delayed)
        const checkLength = this.check.getTotalLength ? this.check.getTotalLength() : 50;
        this.check.style.strokeDasharray = checkLength;
        this.check.style.strokeDashoffset = checkLength;
        
        setTimeout(() => {
            this.check.animate([
                { strokeDashoffset: checkLength },
                { strokeDashoffset: 0 }
            ], {
                duration: 300,
                easing: AnimationConfig.easing.snappy,
                fill: 'forwards'
            });
        }, 300);
        
        // Scale bounce
        this.element.animate([
            { transform: 'scale(0.8)', opacity: 0 },
            { transform: 'scale(1.1)', opacity: 1 },
            { transform: 'scale(1)' }
        ], {
            duration: 500,
            easing: AnimationConfig.easing.bounce
        });
        
        // Haptic
        if (AnimationConfig.hapticEnabled) {
            navigator.vibrate([10, 50, 10]);
        }
    }
    
    reset() {
        this.init();
    }
}

// ============================================================================
// MI1.10: LOADING SKELETON SHIMMER
// ============================================================================

class SkeletonLoader {
    static create(element, options = {}) {
        const { rows = 3, type = 'text', avatar = false } = options;
        
        let html = '<div class="skeleton-container">';
        
        if (avatar) {
            html += '<div class="skeleton skeleton-avatar"></div>';
        }
        
        html += '<div class="skeleton-content">';
        
        if (type === 'text') {
            for (let i = 0; i < rows; i++) {
                const width = i === rows - 1 ? '60%' : `${80 + Math.random() * 20}%`;
                html += `<div class="skeleton skeleton-text" style="width: ${width}"></div>`;
            }
        } else if (type === 'card') {
            html += `
                <div class="skeleton skeleton-image"></div>
                <div class="skeleton skeleton-title"></div>
                <div class="skeleton skeleton-text"></div>
                <div class="skeleton skeleton-text" style="width: 70%"></div>
            `;
        } else if (type === 'list') {
            for (let i = 0; i < rows; i++) {
                html += `
                    <div class="skeleton-list-item">
                        <div class="skeleton skeleton-icon"></div>
                        <div class="skeleton skeleton-text"></div>
                    </div>
                `;
            }
        }
        
        html += '</div></div>';
        
        element.innerHTML = html;
        element.classList.add('loading');
        
        return {
            remove: () => {
                element.classList.remove('loading');
                element.innerHTML = '';
            }
        };
    }
}

// ============================================================================
// MI1.11: TOOLTIP SLIDE-IN
// ============================================================================

class Tooltip {
    constructor(options = {}) {
        this.offset = options.offset || 8;
        this.delay = options.delay || 500;
        this.tooltipElement = null;
        this.timeout = null;
        
        this.init();
    }
    
    init() {
        // Create tooltip container
        this.tooltipElement = document.createElement('div');
        this.tooltipElement.className = 'micro-tooltip';
        this.tooltipElement.style.cssText = `
            position: fixed;
            z-index: 9999;
            padding: 8px 12px;
            background: #1f2937;
            color: white;
            font-size: 13px;
            border-radius: 6px;
            pointer-events: none;
            opacity: 0;
            transform: translateY(4px);
            transition: opacity 0.2s, transform 0.2s;
            max-width: 300px;
        `;
        document.body.appendChild(this.tooltipElement);
        
        // Event delegation
        document.addEventListener('mouseenter', (e) => this.handleMouseEnter(e), true);
        document.addEventListener('mouseleave', (e) => this.handleMouseLeave(e), true);
    }
    
    handleMouseEnter(e) {
        const target = e.target.closest('[data-tooltip]');
        if (!target) return;
        
        this.timeout = setTimeout(() => {
            this.show(target, target.dataset.tooltip);
        }, this.delay);
    }
    
    handleMouseLeave(e) {
        const target = e.target.closest('[data-tooltip]');
        if (!target) return;
        
        clearTimeout(this.timeout);
        this.hide();
    }
    
    show(anchor, text) {
        const rect = anchor.getBoundingClientRect();
        
        this.tooltipElement.textContent = text;
        this.tooltipElement.style.opacity = '1';
        this.tooltipElement.style.transform = 'translateY(0)';
        
        // Position above element by default
        const tooltipRect = this.tooltipElement.getBoundingClientRect();
        let top = rect.top - tooltipRect.height - this.offset;
        let left = rect.left + (rect.width - tooltipRect.width) / 2;
        
        // Flip if not enough space above
        if (top < 8) {
            top = rect.bottom + this.offset;
        }
        
        // Keep within viewport
        left = Math.max(8, Math.min(left, window.innerWidth - tooltipRect.width - 8));
        
        this.tooltipElement.style.top = `${top}px`;
        this.tooltipElement.style.left = `${left}px`;
    }
    
    hide() {
        this.tooltipElement.style.opacity = '0';
        this.tooltipElement.style.transform = 'translateY(4px)';
    }
}

// ============================================================================
// MI1.12: CARD HOVER 3D TILT
// ============================================================================

class Card3DTilt {
    constructor(element, options = {}) {
        this.element = element;
        this.maxTilt = options.maxTilt || 10;
        this.perspective = options.perspective || 1000;
        this.scale = options.scale || 1.02;
        this.speed = options.speed || 400;
        this.glare = options.glare !== false;
        
        if (AnimationConfig.reducedMotion) return;
        
        this.init();
    }
    
    init() {
        this.element.style.transformStyle = 'preserve-3d';
        this.element.style.transition = `transform ${this.speed}ms ease-out`;
        
        if (this.glare) {
            this.glareElement = document.createElement('div');
            this.glareElement.className = 'tilt-glare';
            this.glareElement.style.cssText = `
                position: absolute;
                inset: 0;
                border-radius: inherit;
                pointer-events: none;
                background: linear-gradient(
                    135deg,
                    rgba(255,255,255,0.3) 0%,
                    transparent 50%,
                    transparent 100%
                );
                opacity: 0;
                transition: opacity 0.3s;
            `;
            this.element.style.position = 'relative';
            this.element.appendChild(this.glareElement);
        }
        
        this.element.addEventListener('mouseenter', () => this.onEnter());
        this.element.addEventListener('mousemove', (e) => this.onMove(e));
        this.element.addEventListener('mouseleave', () => this.onLeave());
    }
    
    onEnter() {
        this.element.style.transition = 'none';
        if (this.glareElement) {
            this.glareElement.style.opacity = '1';
        }
    }
    
    onMove(e) {
        const rect = this.element.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        const mouseX = e.clientX - centerX;
        const mouseY = e.clientY - centerY;
        
        const rotateX = (mouseY / (rect.height / 2)) * -this.maxTilt;
        const rotateY = (mouseX / (rect.width / 2)) * this.maxTilt;
        
        this.element.style.transform = `
            perspective(${this.perspective}px)
            rotateX(${rotateX}deg)
            rotateY(${rotateY}deg)
            scale(${this.scale})
        `;
        
        if (this.glareElement) {
            const glareX = ((mouseX / rect.width) + 0.5) * 100;
            const glareY = ((mouseY / rect.height) + 0.5) * 100;
            this.glareElement.style.background = `
                radial-gradient(
                    circle at ${glareX}% ${glareY}%,
                    rgba(255,255,255,0.2) 0%,
                    transparent 50%
                )
            `;
        }
    }
    
    onLeave() {
        this.element.style.transition = `transform ${this.speed}ms ease-out`;
        this.element.style.transform = '';
        
        if (this.glareElement) {
            this.glareElement.style.opacity = '0';
        }
    }
}

// ============================================================================
// MI1.13: BUTTON PRESS HAPTIC FEEDBACK
// ============================================================================

class HapticButton {
    static patterns = {
        light: [10],
        medium: [20],
        heavy: [30],
        double: [15, 50, 15],
        success: [10, 30, 10],
        error: [50, 30, 50, 30, 50],
        warning: [30, 50, 30]
    };
    
    constructor(element, pattern = 'medium') {
        this.element = element;
        this.pattern = HapticButton.patterns[pattern] || HapticButton.patterns.medium;
        
        if (!AnimationConfig.hapticEnabled) return;
        
        this.init();
    }
    
    init() {
        this.element.addEventListener('click', () => this.trigger());
        this.element.addEventListener('touchstart', () => this.trigger());
    }
    
    trigger() {
        if (AnimationConfig.hapticEnabled) {
            navigator.vibrate(this.pattern);
        }
        
        // Visual feedback
        if (!AnimationConfig.reducedMotion) {
            this.element.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.element.style.transform = '';
            }, 100);
        }
    }
    
    static triggerPattern(pattern) {
        const p = HapticButton.patterns[pattern] || pattern;
        if (AnimationConfig.hapticEnabled) {
            navigator.vibrate(p);
        }
    }
}

// ============================================================================
// CSS KEYFRAMES INJECTION
// ============================================================================

const styleSheet = document.createElement('style');
styleSheet.textContent = `
    /* Energy Meter Animations */
    @keyframes energy-critical-pulse {
        0%, 100% { opacity: 0.3; transform: scale(1); }
        50% { opacity: 1; transform: scale(1.05); }
    }
    
    @keyframes energy-warning-pulse {
        0%, 100% { opacity: 0.5; transform: scale(1); }
        50% { opacity: 1; transform: scale(1.02); }
    }
    
    /* Orb Animations */
    @keyframes orb-rotate {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    @keyframes orb-pulse {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.1); opacity: 0.8; }
    }
    
    @keyframes orb-success-flash {
        0% { transform: scale(1); filter: brightness(1); }
        50% { transform: scale(1.3); filter: brightness(1.5); }
        100% { transform: scale(1); filter: brightness(1); }
    }
    
    @keyframes orb-error-flash {
        0%, 100% { transform: scale(1); }
        25%, 75% { transform: scale(0.9); }
        50% { transform: scale(1.1); }
    }
    
    @keyframes particles-orbit {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    /* Proximity Animations */
    @keyframes proximity-ripple {
        0% {
            transform: scale(0.5);
            opacity: 1;
        }
        100% {
            transform: scale(2.5);
            opacity: 0;
        }
    }
    
    @keyframes proximity-pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.2); }
    }
    
    .proximity-ripple {
        position: absolute;
        inset: 0;
        border-radius: 50%;
        border: 2px solid;
        animation: proximity-ripple linear forwards;
    }
    
    /* Skeleton Loading */
    @keyframes skeleton-shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    
    .skeleton {
        background: linear-gradient(
            90deg,
            #1f2937 0%,
            #374151 50%,
            #1f2937 100%
        );
        background-size: 200% 100%;
        animation: skeleton-shimmer 1.5s infinite;
        border-radius: 4px;
    }
    
    .skeleton-text {
        height: 16px;
        margin-bottom: 8px;
    }
    
    .skeleton-title {
        height: 24px;
        width: 60%;
        margin-bottom: 12px;
    }
    
    .skeleton-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
    }
    
    .skeleton-icon {
        width: 24px;
        height: 24px;
        border-radius: 4px;
    }
    
    .skeleton-image {
        height: 150px;
        margin-bottom: 12px;
    }
    
    /* Success Checkmark */
    .success-checkmark {
        width: 52px;
        height: 52px;
    }
    
    .checkmark-circle {
        stroke: #22c55e;
        stroke-width: 2;
    }
    
    .checkmark-check {
        stroke: #22c55e;
        stroke-width: 3;
    }
    
    /* Reduced Motion */
    @media (prefers-reduced-motion: reduce) {
        .skeleton,
        .proximity-ripple,
        .orb-ring,
        .orb-core {
            animation: none !important;
        }
    }
`;
document.head.appendChild(styleSheet);

// ============================================================================
// GLOBAL INITIALIZATION
// ============================================================================

const MicroInteractions = {
    DeviceToggle,
    EnergyMeter,
    ProcessingOrb,
    VoiceWaveform,
    ProximityIndicator,
    StatusGlow,
    ConnectionBeam,
    SuccessCheckmark,
    SkeletonLoader,
    Tooltip,
    Card3DTilt,
    HapticButton,
    
    // Utility functions
    shake: shakeElement,
    
    // Configuration
    config: AnimationConfig,
    
    // Auto-initialize common elements
    init() {
        // Initialize tooltips globally
        new Tooltip();
        
        // Auto-initialize elements with data attributes
        document.querySelectorAll('[data-toggle]').forEach(el => new DeviceToggle(el));
        document.querySelectorAll('[data-energy-meter]').forEach(el => new EnergyMeter(el));
        document.querySelectorAll('[data-processing-orb]').forEach(el => new ProcessingOrb(el));
        document.querySelectorAll('[data-proximity]').forEach(el => new ProximityIndicator(el));
        document.querySelectorAll('[data-status-glow]').forEach(el => new StatusGlow(el));
        document.querySelectorAll('[data-tilt]').forEach(el => new Card3DTilt(el));
        document.querySelectorAll('[data-haptic]').forEach(el => {
            new HapticButton(el, el.dataset.haptic);
        });
        
        console.log('🎨 Micro-interactions initialized');
    }
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MicroInteractions;
}

// Auto-init on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => MicroInteractions.init());
} else {
    MicroInteractions.init();
}
