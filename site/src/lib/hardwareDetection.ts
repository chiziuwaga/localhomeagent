/**
 * Hardware Detection Module
 * P5: DW2.2 - Add hardware detection (GPU/VRAM) to model recommendations
 *
 * Detects client hardware capabilities via browser APIs to recommend
 * the optimal AI model for Local Home Agent installation.
 *
 * Features:
 * - GPU detection via WebGL
 * - Estimated VRAM via WebGL limits
 * - Device memory via navigator.deviceMemory
 * - CPU core count via navigator.hardwareConcurrency
 * - Platform detection
 * - Model recommendation based on detected specs
 */

// ============================================================================
// TYPES
// ============================================================================

export interface GPUInfo {
  vendor: string;
  renderer: string;
  estimatedVRAM: number; // MB
  webglVersion: number;
  unmaskedVendor?: string;
  unmaskedRenderer?: string;
  tier: "integrated" | "mid-range" | "high-end" | "unknown";
}

export interface CPUInfo {
  cores: number;
  estimatedSpeed: "slow" | "medium" | "fast";
}

export interface MemoryInfo {
  deviceMemoryGB: number | null; // navigator.deviceMemory (Chrome only)
  jsHeapSizeLimit: number | null; // MB
  estimatedTotalRAM: number; // GB, best estimate
}

export interface HardwareProfile {
  gpu: GPUInfo;
  cpu: CPUInfo;
  memory: MemoryInfo;
  platform: {
    os: "windows" | "macos" | "linux" | "ios" | "android" | "unknown";
    browser: string;
    isMobile: boolean;
    isAppleSilicon: boolean;
  };
  timestamp: string;
}

export interface ModelRecommendation {
  id: string;
  name: string;
  size: string;
  ram: string;
  contextWindow: string;
  quality: "basic" | "good" | "excellent";
  speed: "fast" | "medium" | "slow";
  reason: string;
  confidence: "high" | "medium" | "low";
}

// ============================================================================
// GPU DETECTION
// ============================================================================

/**
 * Detect GPU capabilities via WebGL
 */
export function detectGPU(): GPUInfo {
  const defaultGPU: GPUInfo = {
    vendor: "Unknown",
    renderer: "Unknown",
    estimatedVRAM: 0,
    webglVersion: 0,
    tier: "unknown",
  };

  try {
    // Try WebGL2 first, fall back to WebGL1
    const canvas = document.createElement("canvas");
    let gl: WebGLRenderingContext | WebGL2RenderingContext | null = null;
    let webglVersion = 0;

    gl = canvas.getContext("webgl2") as WebGL2RenderingContext | null;
    if (gl) {
      webglVersion = 2;
    } else {
      gl = canvas.getContext("webgl") as WebGLRenderingContext | null;
      if (gl) {
        webglVersion = 1;
      }
    }

    if (!gl) {
      return defaultGPU;
    }

    // Get basic vendor/renderer
    const vendor = gl.getParameter(gl.VENDOR) || "Unknown";
    const renderer = gl.getParameter(gl.RENDERER) || "Unknown";

    // Try to get unmasked (real) vendor/renderer
    const debugInfo = gl.getExtension("WEBGL_debug_renderer_info");
    let unmaskedVendor: string | undefined;
    let unmaskedRenderer: string | undefined;

    if (debugInfo) {
      unmaskedVendor =
        gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) || undefined;
      unmaskedRenderer =
        gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) || undefined;
    }

    // Estimate VRAM based on WebGL limits
    const estimatedVRAM = estimateVRAM(gl, unmaskedRenderer || renderer);

    // Determine GPU tier
    const tier = classifyGPUTier(unmaskedRenderer || renderer, estimatedVRAM);

    return {
      vendor,
      renderer,
      estimatedVRAM,
      webglVersion,
      unmaskedVendor,
      unmaskedRenderer,
      tier,
    };
  } catch (error) {
    console.warn("GPU detection failed:", error);
    return defaultGPU;
  }
}

/**
 * Estimate VRAM based on WebGL limits and renderer string
 */
function estimateVRAM(
  gl: WebGLRenderingContext | WebGL2RenderingContext,
  renderer: string
): number {
  // Check for known GPU patterns
  const rendererLower = renderer.toLowerCase();

  // High-end NVIDIA (RTX 30/40 series, Tesla, etc.)
  if (
    rendererLower.includes("rtx 40") ||
    rendererLower.includes("a100") ||
    rendererLower.includes("h100")
  ) {
    return 16000; // 16GB+
  }
  if (rendererLower.includes("rtx 30") || rendererLower.includes("rtx 20")) {
    return 8000; // 8GB typical
  }
  if (rendererLower.includes("gtx 16") || rendererLower.includes("gtx 10")) {
    return 6000; // 6GB typical
  }

  // AMD high-end
  if (rendererLower.includes("rx 7") || rendererLower.includes("rx 6")) {
    return 8000;
  }

  // Apple Silicon
  if (
    rendererLower.includes("apple m1") ||
    rendererLower.includes("apple m2") ||
    rendererLower.includes("apple m3")
  ) {
    return 8000; // Unified memory
  }

  // Intel integrated
  if (
    rendererLower.includes("intel") &&
    (rendererLower.includes("uhd") || rendererLower.includes("iris"))
  ) {
    return 2000; // Shared memory
  }

  // Fallback: estimate based on max texture size
  const maxTextureSize = gl.getParameter(gl.MAX_TEXTURE_SIZE) || 4096;
  if (maxTextureSize >= 16384) {
    return 8000;
  } else if (maxTextureSize >= 8192) {
    return 4000;
  } else {
    return 2000;
  }
}

/**
 * Classify GPU into performance tiers
 */
function classifyGPUTier(
  renderer: string,
  estimatedVRAM: number
): GPUInfo["tier"] {
  const rendererLower = renderer.toLowerCase();

  // High-end
  if (
    rendererLower.includes("rtx") ||
    rendererLower.includes("rx 7") ||
    rendererLower.includes("rx 6") ||
    rendererLower.includes("apple m2") ||
    rendererLower.includes("apple m3") ||
    estimatedVRAM >= 8000
  ) {
    return "high-end";
  }

  // Mid-range
  if (
    rendererLower.includes("gtx") ||
    rendererLower.includes("apple m1") ||
    rendererLower.includes("radeon") ||
    estimatedVRAM >= 4000
  ) {
    return "mid-range";
  }

  // Integrated
  if (
    rendererLower.includes("intel") ||
    rendererLower.includes("integrated") ||
    estimatedVRAM < 2000
  ) {
    return "integrated";
  }

  return "unknown";
}

// ============================================================================
// CPU DETECTION
// ============================================================================

/**
 * Detect CPU capabilities
 */
export function detectCPU(): CPUInfo {
  const cores = navigator.hardwareConcurrency || 4;

  // Estimate speed based on core count (rough heuristic)
  let estimatedSpeed: CPUInfo["estimatedSpeed"] = "medium";
  if (cores >= 12) {
    estimatedSpeed = "fast";
  } else if (cores <= 4) {
    estimatedSpeed = "slow";
  }

  return {
    cores,
    estimatedSpeed,
  };
}

// ============================================================================
// MEMORY DETECTION
// ============================================================================

/**
 * Detect memory capabilities
 */
export function detectMemory(): MemoryInfo {
  // navigator.deviceMemory is Chrome-only
  const deviceMemoryGB = (navigator as any).deviceMemory || null;

  // JS heap size limit (Chrome only)
  let jsHeapSizeLimit: number | null = null;
  if ((performance as any).memory) {
    jsHeapSizeLimit = Math.round(
      (performance as any).memory.jsHeapSizeLimit / (1024 * 1024)
    );
  }

  // Estimate total RAM
  let estimatedTotalRAM = 8; // Default assumption

  if (deviceMemoryGB) {
    // Device memory is capped at 8 for privacy, but we can use it as a minimum
    estimatedTotalRAM = Math.max(deviceMemoryGB, 4);
    // If device memory is 8, actual RAM is likely 8-32GB
    if (deviceMemoryGB === 8) {
      estimatedTotalRAM = 16; // Assume 16GB for systems reporting max
    }
  } else if (jsHeapSizeLimit) {
    // Rough estimate: JS heap is typically 50-70% of available RAM
    estimatedTotalRAM = Math.round(jsHeapSizeLimit / 500); // Very rough
  }

  return {
    deviceMemoryGB,
    jsHeapSizeLimit,
    estimatedTotalRAM,
  };
}

// ============================================================================
// PLATFORM DETECTION
// ============================================================================

/**
 * Detect platform and browser
 */
export function detectPlatform(): HardwareProfile["platform"] {
  const ua = navigator.userAgent.toLowerCase();
  const platform = navigator.platform?.toLowerCase() || "";

  // Detect OS
  let os: HardwareProfile["platform"]["os"] = "unknown";
  if (ua.includes("win")) {
    os = "windows";
  } else if (ua.includes("mac")) {
    os = "macos";
  } else if (ua.includes("linux")) {
    os = "linux";
  } else if (ua.includes("iphone") || ua.includes("ipad")) {
    os = "ios";
  } else if (ua.includes("android")) {
    os = "android";
  }

  // Detect browser
  let browser = "unknown";
  if (ua.includes("chrome") && !ua.includes("edg")) {
    browser = "Chrome";
  } else if (ua.includes("firefox")) {
    browser = "Firefox";
  } else if (ua.includes("safari") && !ua.includes("chrome")) {
    browser = "Safari";
  } else if (ua.includes("edg")) {
    browser = "Edge";
  }

  // Detect mobile
  const isMobile = /android|iphone|ipad|ipod|mobile/i.test(ua);

  // Detect Apple Silicon (heuristic)
  const isAppleSilicon =
    os === "macos" &&
    (platform.includes("arm") ||
      // Modern Safari on Apple Silicon often has specific WebGL renderer
      (browser === "Safari" && navigator.maxTouchPoints > 0));

  return {
    os,
    browser,
    isMobile,
    isAppleSilicon,
  };
}

// ============================================================================
// FULL HARDWARE PROFILE
// ============================================================================

/**
 * Detect complete hardware profile
 */
export function detectHardware(): HardwareProfile {
  return {
    gpu: detectGPU(),
    cpu: detectCPU(),
    memory: detectMemory(),
    platform: detectPlatform(),
    timestamp: new Date().toISOString(),
  };
}

// ============================================================================
// MODEL RECOMMENDATION
// ============================================================================

/**
 * Model specifications for recommendations
 */
const MODEL_SPECS = [
  {
    id: "llama3.2:1b",
    name: "Llama 3.2 1B",
    size: "1.3GB",
    minRAM: 4,
    contextWindow: "8K",
    quality: "basic" as const,
    speed: "fast" as const,
  },
  {
    id: "phi3:mini",
    name: "Phi-3 Mini",
    size: "2.3GB",
    minRAM: 6,
    contextWindow: "128K",
    quality: "basic" as const,
    speed: "fast" as const,
  },
  {
    id: "llama3.2:3b",
    name: "Llama 3.2 3B",
    size: "2.0GB",
    minRAM: 8,
    contextWindow: "128K",
    quality: "good" as const,
    speed: "medium" as const,
  },
  {
    id: "mistral:7b-instruct",
    name: "Mistral 7B Instruct",
    size: "4.1GB",
    minRAM: 10,
    contextWindow: "32K",
    quality: "good" as const,
    speed: "medium" as const,
  },
  {
    id: "llama3.1:8b",
    name: "Llama 3.1 8B",
    size: "4.7GB",
    minRAM: 12,
    contextWindow: "128K",
    quality: "excellent" as const,
    speed: "slow" as const,
  },
  {
    id: "qwen2.5-coder:7b",
    name: "Qwen 2.5 Coder 7B",
    size: "4.4GB",
    minRAM: 12,
    contextWindow: "128K",
    quality: "excellent" as const,
    speed: "slow" as const,
  },
];

/**
 * Recommend optimal model based on hardware profile
 */
export function recommendModel(profile: HardwareProfile): ModelRecommendation {
  const { gpu, cpu, memory, platform } = profile;

  // Calculate effective RAM (consider Apple Silicon unified memory bonus)
  let effectiveRAM = memory.estimatedTotalRAM;
  if (platform.isAppleSilicon) {
    effectiveRAM *= 1.3; // Apple Silicon uses RAM more efficiently for ML
  }
  if (gpu.tier === "high-end") {
    effectiveRAM *= 1.2; // Good GPU can help with larger models
  }

  // Find best fitting model
  let selectedModel = MODEL_SPECS[0]; // Default to smallest
  let confidence: ModelRecommendation["confidence"] = "medium";

  for (const model of MODEL_SPECS) {
    if (effectiveRAM >= model.minRAM) {
      selectedModel = model;
    }
  }

  // Determine confidence based on detection quality
  if (memory.deviceMemoryGB !== null && gpu.unmaskedRenderer) {
    confidence = "high";
  } else if (memory.deviceMemoryGB !== null || gpu.unmaskedRenderer) {
    confidence = "medium";
  } else {
    confidence = "low";
  }

  // Generate reason
  let reason = `Based on ~${memory.estimatedTotalRAM}GB RAM`;
  if (gpu.tier !== "unknown") {
    reason += ` and ${gpu.tier} GPU`;
  }
  if (platform.isAppleSilicon) {
    reason += " (Apple Silicon optimized)";
  }

  return {
    id: selectedModel.id,
    name: selectedModel.name,
    size: selectedModel.size,
    ram: `${selectedModel.minRAM}GB+`,
    contextWindow: selectedModel.contextWindow,
    quality: selectedModel.quality,
    speed: selectedModel.speed,
    reason,
    confidence,
  };
}

/**
 * Get all compatible models for the hardware
 */
export function getCompatibleModels(
  profile: HardwareProfile
): ModelRecommendation[] {
  const { memory, platform, gpu } = profile;

  let effectiveRAM = memory.estimatedTotalRAM;
  if (platform.isAppleSilicon) {
    effectiveRAM *= 1.3;
  }
  if (gpu.tier === "high-end") {
    effectiveRAM *= 1.2;
  }

  return MODEL_SPECS.filter(model => effectiveRAM >= model.minRAM).map(
    model => ({
      id: model.id,
      name: model.name,
      size: model.size,
      ram: `${model.minRAM}GB+`,
      contextWindow: model.contextWindow,
      quality: model.quality,
      speed: model.speed,
      reason: `Compatible with your ~${memory.estimatedTotalRAM}GB RAM`,
      confidence: "medium" as const,
    })
  );
}

// ============================================================================
// REACT HOOK (Optional)
// ============================================================================

import { useState, useEffect } from "react";

/**
 * React hook for hardware detection
 */
export function useHardwareDetection() {
  const [profile, setProfile] = useState<HardwareProfile | null>(null);
  const [recommendation, setRecommendation] =
    useState<ModelRecommendation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    try {
      const detectedProfile = detectHardware();
      setProfile(detectedProfile);
      setRecommendation(recommendModel(detectedProfile));
      setLoading(false);
    } catch (err) {
      setError(
        err instanceof Error ? err : new Error("Hardware detection failed")
      );
      setLoading(false);
    }
  }, []);

  return {
    profile,
    recommendation,
    compatibleModels: profile ? getCompatibleModels(profile) : [],
    loading,
    error,
    refresh: () => {
      setLoading(true);
      try {
        const detectedProfile = detectHardware();
        setProfile(detectedProfile);
        setRecommendation(recommendModel(detectedProfile));
        setLoading(false);
      } catch (err) {
        setError(
          err instanceof Error ? err : new Error("Hardware detection failed")
        );
        setLoading(false);
      }
    },
  };
}

// ============================================================================
// STORAGE
// ============================================================================

const STORAGE_KEY = "local-home-agent-hardware-profile";

/**
 * Save hardware profile to localStorage
 */
export function saveHardwareProfile(profile: HardwareProfile): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  } catch (error) {
    console.warn("Failed to save hardware profile:", error);
  }
}

/**
 * Load hardware profile from localStorage
 */
export function loadHardwareProfile(): HardwareProfile | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (error) {
    console.warn("Failed to load hardware profile:", error);
  }
  return null;
}

/**
 * Detect and save hardware profile
 */
export function detectAndSaveHardware(): HardwareProfile {
  const profile = detectHardware();
  saveHardwareProfile(profile);
  return profile;
}
