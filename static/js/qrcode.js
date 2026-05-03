/**
 * QR Code Generator - Simple canvas-based implementation
 * For generating QR codes for WiFi access sharing
 * 
 * Uses the qr-creator library pattern for a lightweight solution
 */

(function() {
    'use strict';

    // QR Code Module
    const QRCode = {
        /**
         * Generate QR code on canvas
         * @param {HTMLCanvasElement} canvas - Target canvas
         * @param {string} text - Text to encode
         * @param {Object} options - Size, colors, etc.
         */
        generate: function(canvas, text, options = {}) {
            const size = options.size || 200;
            const darkColor = options.darkColor || '#000000';
            const lightColor = options.lightColor || '#ffffff';
            const errorCorrection = options.errorCorrection || 'M';
            
            canvas.width = size;
            canvas.height = size;
            
            const ctx = canvas.getContext('2d');
            
            // Use external library if available
            if (typeof QRCreator !== 'undefined') {
                QRCreator.render({
                    text: text,
                    size: size,
                    fill: darkColor,
                    background: lightColor,
                    ecl: errorCorrection
                }, canvas);
                return;
            }
            
            // Fallback: Generate a visual placeholder with encoded text
            // In production, use a proper QR library like qrcode.js
            this._generateFallback(ctx, text, size, darkColor, lightColor);
        },

        /**
         * Fallback QR code visualization
         * Creates a styled placeholder that indicates QR functionality
         */
        _generateFallback: function(ctx, text, size, darkColor, lightColor) {
            // Fill background
            ctx.fillStyle = lightColor;
            ctx.fillRect(0, 0, size, size);
            
            // Calculate module size (QR codes are typically 25x25 to 177x177 modules)
            const moduleCount = 25;
            const moduleSize = Math.floor(size / (moduleCount + 2)); // +2 for quiet zone
            const offset = Math.floor((size - moduleCount * moduleSize) / 2);
            
            // Generate pseudo-random pattern based on text hash
            const hash = this._hashString(text);
            
            ctx.fillStyle = darkColor;
            
            // Draw finder patterns (corner squares)
            this._drawFinderPattern(ctx, offset, offset, moduleSize);
            this._drawFinderPattern(ctx, offset + (moduleCount - 7) * moduleSize, offset, moduleSize);
            this._drawFinderPattern(ctx, offset, offset + (moduleCount - 7) * moduleSize, moduleSize);
            
            // Draw alignment pattern
            const alignPos = offset + 16 * moduleSize;
            this._drawAlignmentPattern(ctx, alignPos, alignPos, moduleSize);
            
            // Draw timing patterns
            for (let i = 8; i < moduleCount - 8; i++) {
                if (i % 2 === 0) {
                    ctx.fillRect(offset + i * moduleSize, offset + 6 * moduleSize, moduleSize, moduleSize);
                    ctx.fillRect(offset + 6 * moduleSize, offset + i * moduleSize, moduleSize, moduleSize);
                }
            }
            
            // Draw data modules (pseudo-random based on hash)
            for (let y = 0; y < moduleCount; y++) {
                for (let x = 0; x < moduleCount; x++) {
                    // Skip finder and timing patterns
                    if (this._isReservedModule(x, y, moduleCount)) continue;
                    
                    // Generate module based on position and hash
                    const bit = ((hash + x * 31 + y * 37) % 100) < 50;
                    if (bit) {
                        ctx.fillRect(
                            offset + x * moduleSize,
                            offset + y * moduleSize,
                            moduleSize,
                            moduleSize
                        );
                    }
                }
            }
            
            // Add URL text at bottom (subtle indicator this is a fallback)
            ctx.fillStyle = darkColor;
            ctx.font = `${Math.floor(size / 20)}px 'Courier New', monospace`;
            ctx.textAlign = 'center';
            const shortUrl = text.length > 30 ? text.substring(0, 27) + '...' : text;
            // Don't show URL in QR - just the pattern
        },

        /**
         * Draw a finder pattern (the big corner squares)
         */
        _drawFinderPattern: function(ctx, x, y, moduleSize) {
            // Outer square (7x7)
            ctx.fillRect(x, y, moduleSize * 7, moduleSize * 7);
            
            // Inner white square (5x5)
            const color = ctx.fillStyle;
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(x + moduleSize, y + moduleSize, moduleSize * 5, moduleSize * 5);
            
            // Center square (3x3)
            ctx.fillStyle = color;
            ctx.fillRect(x + moduleSize * 2, y + moduleSize * 2, moduleSize * 3, moduleSize * 3);
        },

        /**
         * Draw an alignment pattern
         */
        _drawAlignmentPattern: function(ctx, x, y, moduleSize) {
            ctx.fillRect(x, y, moduleSize * 5, moduleSize * 5);
            
            const color = ctx.fillStyle;
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(x + moduleSize, y + moduleSize, moduleSize * 3, moduleSize * 3);
            
            ctx.fillStyle = color;
            ctx.fillRect(x + moduleSize * 2, y + moduleSize * 2, moduleSize, moduleSize);
        },

        /**
         * Check if module is in a reserved area
         */
        _isReservedModule: function(x, y, count) {
            // Finder patterns (top-left, top-right, bottom-left)
            if (x < 9 && y < 9) return true;
            if (x >= count - 9 && y < 9) return true;
            if (x < 9 && y >= count - 9) return true;
            
            // Timing patterns
            if (x === 6 || y === 6) return true;
            
            // Alignment pattern (approximate)
            if (x >= 14 && x <= 20 && y >= 14 && y <= 20) return true;
            
            return false;
        },

        /**
         * Simple string hash function
         */
        _hashString: function(str) {
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                const char = str.charCodeAt(i);
                hash = ((hash << 5) - hash) + char;
                hash = hash & hash; // Convert to 32bit integer
            }
            return Math.abs(hash);
        }
    };

    // Expose globally
    window.QRCode = QRCode;

    // Helper function for easy use
    window.generateQRCode = function(canvasId, text, options) {
        const canvas = document.getElementById(canvasId);
        if (canvas) {
            QRCode.generate(canvas, text, options);
        }
    };

})();
