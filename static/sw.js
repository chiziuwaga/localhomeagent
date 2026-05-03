/**
 * Local Home Agent - Service Worker
 * Provides offline capability and caching for the PWA
 * 
 * Features:
 * - Offline fallback page
 * - Cache-first strategy for static assets
 * - Network-first strategy for API calls
 * - Background sync for pending actions
 */

const CACHE_NAME = 'home-agent-v1';
const OFFLINE_URL = '/offline';

// Static assets to cache on install
const STATIC_ASSETS = [
  '/',
  '/dashboard',
  '/chat',
  '/settings',
  '/offline',
  '/static/css/base.css',
  '/static/js/pwa.js',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

// API routes that should use network-first strategy
const API_ROUTES = ['/api/', '/ws'];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        console.log('[SW] Skip waiting');
        return self.skipWaiting();
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name !== CACHE_NAME)
            .map((name) => {
              console.log('[SW] Deleting old cache:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => {
        console.log('[SW] Claiming clients');
        return self.clients.claim();
      })
  );
});

// Fetch event - handle requests
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip cross-origin requests
  if (url.origin !== location.origin) {
    return;
  }
  
  // Handle API routes with network-first strategy
  if (API_ROUTES.some(route => url.pathname.startsWith(route))) {
    event.respondWith(networkFirst(request));
    return;
  }
  
  // Handle navigation requests
  if (request.mode === 'navigate') {
    event.respondWith(navigationHandler(request));
    return;
  }
  
  // Handle static assets with cache-first strategy
  event.respondWith(cacheFirst(request));
});

/**
 * Cache-first strategy - check cache, fallback to network
 */
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }
  
  try {
    const response = await fetch(request);
    
    // Cache successful responses
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    
    return response;
  } catch (error) {
    console.log('[SW] Fetch failed:', error);
    // Return offline page for HTML requests
    if (request.headers.get('Accept')?.includes('text/html')) {
      return caches.match(OFFLINE_URL);
    }
    throw error;
  }
}

/**
 * Network-first strategy - try network, fallback to cache
 */
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    
    // Cache successful GET responses
    if (response.ok && request.method === 'GET') {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    
    return response;
  } catch (error) {
    console.log('[SW] Network failed, trying cache:', error);
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    
    // Return error response for API calls
    return new Response(
      JSON.stringify({ 
        error: 'offline', 
        message: 'You are currently offline. This action will be synced when you reconnect.' 
      }),
      { 
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

/**
 * Navigation handler - special handling for page navigations
 */
async function navigationHandler(request) {
  try {
    // Try network first for navigation
    const preloadResponse = await event.preloadResponse;
    if (preloadResponse) {
      return preloadResponse;
    }
    
    const networkResponse = await fetch(request);
    return networkResponse;
  } catch (error) {
    console.log('[SW] Navigation failed, serving offline page');
    const cache = await caches.open(CACHE_NAME);
    const cachedPage = await cache.match(request);
    
    if (cachedPage) {
      return cachedPage;
    }
    
    return caches.match(OFFLINE_URL);
  }
}

// Background sync for pending device actions
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-device-actions') {
    event.waitUntil(syncPendingActions());
  }
});

/**
 * Sync pending device actions when back online
 */
async function syncPendingActions() {
  console.log('[SW] Syncing pending actions...');
  
  try {
    // Get pending actions from IndexedDB
    const db = await openDB();
    const tx = db.transaction('pendingActions', 'readonly');
    const store = tx.objectStore('pendingActions');
    const actions = await store.getAll();
    
    for (const action of actions) {
      try {
        await fetch(action.url, {
          method: action.method,
          headers: action.headers,
          body: action.body
        });
        
        // Remove synced action
        const deleteTx = db.transaction('pendingActions', 'readwrite');
        deleteTx.objectStore('pendingActions').delete(action.id);
        
        console.log('[SW] Synced action:', action.id);
      } catch (error) {
        console.log('[SW] Failed to sync action:', action.id, error);
      }
    }
  } catch (error) {
    console.log('[SW] Sync failed:', error);
  }
}

/**
 * Open IndexedDB for pending actions
 */
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('HomeAgentDB', 1);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('pendingActions')) {
        db.createObjectStore('pendingActions', { keyPath: 'id', autoIncrement: true });
      }
    };
  });
}

// Push notification handling
self.addEventListener('push', (event) => {
  if (!event.data) return;
  
  const data = event.data.json();
  const options = {
    body: data.body || 'Home Agent notification',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/badge-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      url: data.url || '/dashboard'
    },
    actions: data.actions || [
      { action: 'view', title: 'View' },
      { action: 'dismiss', title: 'Dismiss' }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title || 'Home Agent', options)
  );
});

// Notification click handling
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  
  if (event.action === 'dismiss') {
    return;
  }
  
  const url = event.notification.data?.url || '/dashboard';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Focus existing window if open
        for (const client of clientList) {
          if (client.url.includes(url) && 'focus' in client) {
            return client.focus();
          }
        }
        // Open new window
        if (clients.openWindow) {
          return clients.openWindow(url);
        }
      })
  );
});

console.log('[SW] Service worker loaded');
