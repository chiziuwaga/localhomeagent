# PWA Icons

This folder should contain the following icon files for the PWA manifest:

## Required Icons

| File | Size | Purpose |
|------|------|---------|
| `icon-72x72.png` | 72x72 | Small icon |
| `icon-96x96.png` | 96x96 | Android shortcut |
| `icon-128x128.png` | 128x128 | Medium icon |
| `icon-144x144.png` | 144x144 | Medium icon |
| `icon-152x152.png` | 152x152 | iOS icon |
| `icon-192x192.png` | 192x192 | Android icon |
| `icon-384x384.png` | 384x384 | Large icon |
| `icon-512x512.png` | 512x512 | Splash screen |

## Additional Icons

| File | Size | Purpose |
|------|------|---------|
| `chat-96x96.png` | 96x96 | Chat shortcut |
| `dashboard-96x96.png` | 96x96 | Dashboard shortcut |
| `badge-72x72.png` | 72x72 | Notification badge |

## Icon Design Guidelines

1. **Style**: Neo-brutalist with thick black border (2-4px)
2. **Colors**: 
   - Primary: `#ff3333` (red accent)
   - Background: `#ffffff` (white)
   - Border: `#000000` (black)
3. **Symbol**: House icon (🏠) or similar home automation symbol
4. **Maskable Area**: Keep important content within 80% safe zone

## Generate Icons

You can generate all icon sizes from a single 512x512 source using:

```bash
# Using ImageMagick
for size in 72 96 128 144 152 192 384 512; do
  convert icon-source.png -resize ${size}x${size} icon-${size}x${size}.png
done
```

Or use online PWA icon generators:
- https://realfavicongenerator.net/
- https://www.pwabuilder.com/
