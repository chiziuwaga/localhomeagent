/**
 * Local Agent Download & Installation Page
 * Sprint 6: DW1.1-DW1.10
 *
 * Features:
 * - OS auto-detection
 * - Download progress tracking
 * - System requirements check
 * - Installation wizard UI
 * - First-run setup guide
 * - Model download wizard
 */

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { AnimatedBackground } from "@/components/AnimatedBackground";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Download,
  Monitor,
  Apple,
  Terminal,
  CheckCircle2,
  AlertCircle,
  Cpu,
  HardDrive,
  MemoryStick,
  Wifi,
  ArrowRight,
  ArrowLeft,
  Play,
  Settings,
  Shield,
  Home,
  Sparkles,
  Zap,
  Brain,
  Lock,
  Users,
  Gauge,
  ExternalLink,
  Copy,
  Check,
  RefreshCw,
} from "lucide-react";
import { Link } from "wouter";

// ============================================================================
// TYPES
// ============================================================================

type OperatingSystem = "windows" | "macos" | "linux" | "unknown";
type DownloadState = "idle" | "downloading" | "complete" | "error";
type WizardStep =
  | "welcome"
  | "requirements"
  | "components"
  | "network"
  | "admin"
  | "model"
  | "complete";

interface SystemRequirements {
  ram: { minimum: number; recommended: number; unit: string };
  cpu: { minimum: string; recommended: string };
  disk: { minimum: number; recommended: number; unit: string };
  network: string;
}

interface DownloadOption {
  os: OperatingSystem;
  label: string;
  icon: typeof Monitor;
  filename: string;
  size: string;
  url: string;
  arch?: string[];
}

interface ModelRecommendation {
  id: string;
  name: string;
  size: string;
  ram: string;
  context: string; // Context window size (e.g., "8K", "32K", "128K")
  quality: "basic" | "good" | "excellent";
  speed: "fast" | "medium" | "slow";
  description: string;
  command: string;
  recommended?: boolean;
}

// ============================================================================
// CONSTANTS
// ============================================================================

const SYSTEM_REQUIREMENTS: SystemRequirements = {
  ram: { minimum: 8, recommended: 16, unit: "GB" },
  cpu: {
    minimum: "4 cores @ 2.0GHz",
    recommended: "8 cores @ 3.0GHz+ or Apple M1+",
  },
  disk: { minimum: 5, recommended: 20, unit: "GB" },
  network: "WiFi or Ethernet (local network access)",
};

// GitHub Releases base URL - update this to your actual releases
const GITHUB_RELEASES_BASE =
  "https://github.com/Fix-It-For-Me-AI/local-home-agent/releases/latest/download";

const DOWNLOAD_OPTIONS: DownloadOption[] = [
  {
    os: "windows",
    label: "Windows",
    icon: Monitor,
    filename: "CoLiving-Home-Agent-Windows.exe",
    size: "85 MB",
    url: `${GITHUB_RELEASES_BASE}/CoLiving-Home-Agent-Windows.exe`,
    arch: ["x64", "x86"],
  },
  {
    os: "macos",
    label: "macOS",
    icon: Apple,
    filename: "CoLiving-Home-Agent-macOS",
    size: "92 MB",
    url: `${GITHUB_RELEASES_BASE}/CoLiving-Home-Agent-macOS`,
    arch: ["Intel", "Apple Silicon"],
  },
  {
    os: "linux",
    label: "Linux",
    icon: Terminal,
    filename: "CoLiving-Home-Agent-Linux",
    size: "78 MB",
    url: `${GITHUB_RELEASES_BASE}/CoLiving-Home-Agent-Linux`,
    arch: ["x64", "ARM64"],
  },
];

const MODEL_RECOMMENDATIONS: ModelRecommendation[] = [
  {
    id: "llama3.2:1b",
    name: "Llama 3.2 1B",
    size: "1.3 GB",
    ram: "4 GB",
    context: "128K",
    quality: "basic",
    speed: "fast",
    description:
      "Fastest response times, good for simple tasks and low-spec hardware",
    command: "ollama pull llama3.2:1b",
  },
  {
    id: "phi3:mini",
    name: "Phi-3 Mini",
    size: "2.3 GB",
    ram: "6 GB",
    context: "128K",
    quality: "good",
    speed: "fast",
    description:
      "Microsoft's efficient model with huge context, great for long conversations",
    command: "ollama pull phi3:mini",
  },
  {
    id: "llama3.2:3b",
    name: "Llama 3.2 3B",
    size: "2.0 GB",
    ram: "8 GB",
    context: "128K",
    quality: "good",
    speed: "medium",
    description: "Good balance of speed, quality, and massive context window",
    command: "ollama pull llama3.2:3b",
    recommended: true,
  },
  {
    id: "mistral:7b-instruct",
    name: "Mistral 7B Instruct",
    size: "4.1 GB",
    ram: "10 GB",
    context: "32K",
    quality: "excellent",
    speed: "medium",
    description:
      "Excellent instruction following, great for complex automations",
    command: "ollama pull mistral:7b-instruct",
  },
  {
    id: "llama3.1:8b",
    name: "Llama 3.1 8B",
    size: "4.7 GB",
    ram: "12 GB",
    context: "128K",
    quality: "excellent",
    speed: "slow",
    description:
      "Best quality with massive context, ideal for high-spec hardware with GPU",
    command: "ollama pull llama3.1:8b",
  },
  {
    id: "qwen2.5-coder:7b",
    name: "Qwen 2.5 Coder",
    size: "4.4 GB",
    ram: "12 GB",
    context: "128K",
    quality: "excellent",
    speed: "medium",
    description:
      "Optimized for code and automation scripts with huge context window",
    command: "ollama pull qwen2.5-coder:7b",
  },
];

const WIZARD_STEPS: { id: WizardStep; label: string; icon: typeof Home }[] = [
  { id: "welcome", label: "Welcome", icon: Home },
  { id: "requirements", label: "Requirements", icon: Gauge },
  { id: "components", label: "Components", icon: Settings },
  { id: "network", label: "Network", icon: Wifi },
  { id: "admin", label: "Admin Setup", icon: Shield },
  { id: "model", label: "AI Model", icon: Brain },
  { id: "complete", label: "Complete", icon: CheckCircle2 },
];

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function detectOS(): OperatingSystem {
  if (typeof window === "undefined") return "unknown";

  const userAgent = navigator.userAgent.toLowerCase();
  const platform = navigator.platform?.toLowerCase() || "";

  if (platform.includes("win") || userAgent.includes("windows")) {
    return "windows";
  }
  if (platform.includes("mac") || userAgent.includes("macintosh")) {
    return "macos";
  }
  if (platform.includes("linux") || userAgent.includes("linux")) {
    return "linux";
  }

  return "unknown";
}

/**
 * DW2.2: Hardware Detection
 * Detects GPU type, VRAM estimate, RAM, and CPU cores
 */
interface HardwareInfo {
  gpu: {
    name: string;
    type: "nvidia" | "amd" | "intel" | "apple" | "unknown";
    vramEstimate: string;
  };
  ram: { total: number | null; unit: string };
  cpu: { cores: number; threads: number };
  recommendedModel: string;
}

async function detectHardware(): Promise<HardwareInfo> {
  const hardware: HardwareInfo = {
    gpu: { name: "Unknown", type: "unknown", vramEstimate: "Unknown" },
    ram: { total: null, unit: "GB" },
    cpu: {
      cores: navigator.hardwareConcurrency || 4,
      threads: navigator.hardwareConcurrency || 4,
    },
    recommendedModel: "llama3.2:3b",
  };

  // Try to detect GPU using WebGL
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
    if (gl) {
      const debugInfo = gl.getExtension("WEBGL_debug_renderer_info");
      if (debugInfo) {
        const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
        hardware.gpu.name = renderer;

        // Detect GPU type
        const rendererLower = renderer.toLowerCase();
        if (
          rendererLower.includes("nvidia") ||
          rendererLower.includes("geforce") ||
          rendererLower.includes("quadro") ||
          rendererLower.includes("rtx") ||
          rendererLower.includes("gtx")
        ) {
          hardware.gpu.type = "nvidia";
          // Estimate VRAM based on common cards
          if (rendererLower.includes("rtx 40"))
            hardware.gpu.vramEstimate = "8-24 GB";
          else if (rendererLower.includes("rtx 30"))
            hardware.gpu.vramEstimate = "8-24 GB";
          else if (rendererLower.includes("rtx 20"))
            hardware.gpu.vramEstimate = "6-11 GB";
          else if (rendererLower.includes("gtx 16"))
            hardware.gpu.vramEstimate = "4-6 GB";
          else if (rendererLower.includes("gtx 10"))
            hardware.gpu.vramEstimate = "3-8 GB";
          else hardware.gpu.vramEstimate = "4-8 GB";
        } else if (
          rendererLower.includes("amd") ||
          rendererLower.includes("radeon")
        ) {
          hardware.gpu.type = "amd";
          hardware.gpu.vramEstimate = "4-16 GB";
        } else if (rendererLower.includes("intel")) {
          hardware.gpu.type = "intel";
          hardware.gpu.vramEstimate = "Shared (2-4 GB)";
        } else if (
          rendererLower.includes("apple") ||
          rendererLower.includes("m1") ||
          rendererLower.includes("m2") ||
          rendererLower.includes("m3") ||
          rendererLower.includes("m4")
        ) {
          hardware.gpu.type = "apple";
          hardware.gpu.vramEstimate = "Unified (8-128 GB)";
        }
      }
    }
  } catch (e) {
    console.warn("GPU detection failed:", e);
  }

  // Estimate RAM using performance.memory (Chrome only) or navigator.deviceMemory
  try {
    if ("deviceMemory" in navigator) {
      // deviceMemory returns a conservative estimate (2, 4, 8, etc.)
      hardware.ram.total = (navigator as any).deviceMemory;
    }
    // Try Chrome-specific memory API
    if ((performance as any).memory) {
      const memMB = (performance as any).memory.jsHeapSizeLimit / (1024 * 1024);
      // This is heap limit, actual RAM is usually 4-8x higher
      hardware.ram.total = Math.max(
        hardware.ram.total || 0,
        Math.round(memMB / 256)
      );
    }
  } catch (e) {
    console.warn("RAM detection failed:", e);
  }

  // Recommend model based on detected hardware
  const cores = hardware.cpu.cores;
  const hasGpu =
    hardware.gpu.type === "nvidia" ||
    hardware.gpu.type === "amd" ||
    hardware.gpu.type === "apple";
  const ram = hardware.ram.total || 8;

  if (hasGpu && ram >= 16) {
    hardware.recommendedModel = "llama3.1:8b";
  } else if (hasGpu && ram >= 12) {
    hardware.recommendedModel = "mistral:7b-instruct";
  } else if (ram >= 8 || (hasGpu && ram >= 6)) {
    hardware.recommendedModel = "llama3.2:3b";
  } else if (cores >= 4) {
    hardware.recommendedModel = "phi3:mini";
  } else {
    hardware.recommendedModel = "llama3.2:1b";
  }

  return hardware;
}

function getQualityColor(quality: ModelRecommendation["quality"]): string {
  switch (quality) {
    case "basic":
      return "bg-yellow-100 text-yellow-800 border-yellow-300";
    case "good":
      return "bg-blue-100 text-blue-800 border-blue-300";
    case "excellent":
      return "bg-green-100 text-green-800 border-green-300";
  }
}

function getSpeedColor(speed: ModelRecommendation["speed"]): string {
  switch (speed) {
    case "fast":
      return "bg-green-100 text-green-800";
    case "medium":
      return "bg-yellow-100 text-yellow-800";
    case "slow":
      return "bg-orange-100 text-orange-800";
  }
}

// ============================================================================
// COMPONENTS
// ============================================================================

function OSDetectionBanner({ detectedOS }: { detectedOS: OperatingSystem }) {
  const option = DOWNLOAD_OPTIONS.find(o => o.os === detectedOS);

  if (!option) return null;

  return (
    <div className="bg-accent-yellow/20 border-2 border-black px-4 py-2 rounded-lg inline-flex items-center gap-2 font-mono text-sm">
      <option.icon className="w-4 h-4" />
      <span>
        We detected you're using <strong>{option.label}</strong>
      </span>
    </div>
  );
}

function SystemRequirementsCheck() {
  const [checking, setChecking] = useState(true);
  const [results, setResults] = useState<
    { label: string; status: "pass" | "warn" | "unknown"; value: string }[]
  >([]);
  const [hardware, setHardware] = useState<HardwareInfo | null>(null);

  useEffect(() => {
    // Enhanced hardware detection (DW2.2)
    async function runDetection() {
      const hw = await detectHardware();
      setHardware(hw);

      const ramStatus = hw.ram.total
        ? hw.ram.total >= 8
          ? "pass"
          : "warn"
        : "unknown";
      const gpuStatus = hw.gpu.type !== "unknown" ? "pass" : "unknown";

      setResults([
        {
          label: "Operating System",
          status: "pass",
          value:
            detectOS() === "unknown"
              ? "Unknown"
              : DOWNLOAD_OPTIONS.find(o => o.os === detectOS())?.label ||
                "Unknown",
        },
        {
          label: "CPU Cores",
          status: hw.cpu.cores >= 4 ? "pass" : "warn",
          value: `${hw.cpu.cores} cores`,
        },
        {
          label: "GPU",
          status: gpuStatus,
          value:
            hw.gpu.name.length > 40
              ? hw.gpu.name.substring(0, 40) + "..."
              : hw.gpu.name,
        },
        {
          label: "GPU Type",
          status:
            hw.gpu.type === "nvidia" || hw.gpu.type === "apple"
              ? "pass"
              : gpuStatus,
          value: `${hw.gpu.type.toUpperCase()} (VRAM: ${hw.gpu.vramEstimate})`,
        },
        {
          label: "RAM",
          status: ramStatus,
          value: hw.ram.total
            ? `${hw.ram.total}+ GB detected`
            : "Check manually (8GB+ recommended)",
        },
        {
          label: "Disk Space",
          status: "unknown",
          value: "5GB+ required",
        },
        {
          label: "Network",
          status: navigator.onLine ? "pass" : "warn",
          value: navigator.onLine ? "Connected" : "Offline",
        },
      ]);
      setChecking(false);
    }

    runDetection();
  }, []);

  return (
    <Card className="border-4 border-black shadow-brutal">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gauge className="w-5 h-5" />
          System Requirements Check
        </CardTitle>
      </CardHeader>
      <CardContent>
        {checking ? (
          <div className="flex items-center gap-3 text-muted-foreground">
            <RefreshCw className="w-4 h-4 animate-spin" />
            Detecting hardware capabilities...
          </div>
        ) : (
          <>
            <div className="space-y-3">
              {results.map((result, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between py-2 border-b border-gray-200 last:border-0"
                >
                  <span className="font-mono text-sm">{result.label}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground max-w-[200px] truncate">
                      {result.value}
                    </span>
                    {result.status === "pass" && (
                      <CheckCircle2 className="w-4 h-4 text-green-600" />
                    )}
                    {result.status === "warn" && (
                      <AlertCircle className="w-4 h-4 text-yellow-600" />
                    )}
                    {result.status === "unknown" && (
                      <AlertCircle className="w-4 h-4 text-gray-400" />
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Recommended Model (DW2.2) */}
            {hardware && (
              <div className="mt-4 p-4 bg-green-50 border-2 border-green-300 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Brain className="w-5 h-5 text-green-700" />
                  <h4 className="font-bold text-green-800">
                    Recommended Model for Your Hardware
                  </h4>
                </div>
                <p className="text-green-700 font-mono text-lg">
                  {hardware.recommendedModel}
                </p>
                <p className="text-sm text-green-600 mt-1">
                  Based on your{" "}
                  {hardware.gpu.type !== "unknown"
                    ? hardware.gpu.type.toUpperCase() + " GPU and "
                    : ""}
                  {hardware.ram.total || "estimated"} GB RAM
                </p>
              </div>
            )}
          </>
        )}

        <div className="mt-6 p-4 bg-gray-50 border-2 border-gray-200 rounded-lg">
          <h4 className="font-bold mb-2">Minimum Requirements</h4>
          <ul className="text-sm text-muted-foreground space-y-1">
            <li className="flex items-center gap-2">
              <MemoryStick className="w-4 h-4" />
              RAM: {SYSTEM_REQUIREMENTS.ram.minimum}
              {SYSTEM_REQUIREMENTS.ram.unit} (recommended:{" "}
              {SYSTEM_REQUIREMENTS.ram.recommended}
              {SYSTEM_REQUIREMENTS.ram.unit})
            </li>
            <li className="flex items-center gap-2">
              <Cpu className="w-4 h-4" />
              CPU: {SYSTEM_REQUIREMENTS.cpu.minimum}
            </li>
            <li className="flex items-center gap-2">
              <HardDrive className="w-4 h-4" />
              Disk: {SYSTEM_REQUIREMENTS.disk.minimum}
              {SYSTEM_REQUIREMENTS.disk.unit} (recommended:{" "}
              {SYSTEM_REQUIREMENTS.disk.recommended}
              {SYSTEM_REQUIREMENTS.disk.unit})
            </li>
            <li className="flex items-center gap-2">
              <Wifi className="w-4 h-4" />
              Network: {SYSTEM_REQUIREMENTS.network}
            </li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}

function DownloadSection({
  detectedOS,
  onDownloadStart,
}: {
  detectedOS: OperatingSystem;
  onDownloadStart: (os: OperatingSystem) => void;
}) {
  const [selectedOS, setSelectedOS] = useState<OperatingSystem>(detectedOS);
  const [downloadState, setDownloadState] = useState<DownloadState>("idle");
  const [progress, setProgress] = useState(0);

  const handleDownload = useCallback(
    (os: OperatingSystem) => {
      setDownloadState("downloading");
      setProgress(0);

      // Simulate download progress
      const interval = setInterval(() => {
        setProgress(p => {
          if (p >= 100) {
            clearInterval(interval);
            setDownloadState("complete");
            onDownloadStart(os);
            return 100;
          }
          return p + Math.random() * 15;
        });
      }, 200);
    },
    [onDownloadStart]
  );

  return (
    <Card className="border-4 border-black shadow-brutal-lg">
      <CardHeader className="text-center">
        <CardTitle className="text-3xl">Download Local Home Agent</CardTitle>
        <CardDescription className="text-lg">
          Private, AI-powered smart home management that runs on your network
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs
          value={selectedOS}
          onValueChange={v => setSelectedOS(v as OperatingSystem)}
          className="w-full"
        >
          <TabsList className="grid w-full grid-cols-3 mb-6">
            {DOWNLOAD_OPTIONS.map(option => (
              <TabsTrigger
                key={option.os}
                value={option.os}
                className="flex items-center gap-2 data-[state=active]:border-2 data-[state=active]:border-black"
              >
                <option.icon className="w-4 h-4" />
                {option.label}
                {option.os === detectedOS && (
                  <Badge variant="secondary" className="ml-1 text-xs">
                    Detected
                  </Badge>
                )}
              </TabsTrigger>
            ))}
          </TabsList>

          {DOWNLOAD_OPTIONS.map(option => (
            <TabsContent
              key={option.os}
              value={option.os}
              className="space-y-4"
            >
              <div className="text-center p-6 bg-gray-50 border-2 border-gray-200 rounded-lg">
                <option.icon className="w-16 h-16 mx-auto mb-4 text-gray-700" />
                <h3 className="text-xl font-bold mb-2">{option.label}</h3>
                <p className="text-muted-foreground mb-2">
                  {option.filename} • {option.size}
                </p>
                {option.arch && (
                  <p className="text-sm text-muted-foreground">
                    Supports: {option.arch.join(", ")}
                  </p>
                )}
              </div>

              {downloadState === "downloading" ? (
                <div className="space-y-2">
                  <Progress value={progress} className="h-3" />
                  <p className="text-center text-sm text-muted-foreground">
                    Downloading... {Math.round(progress)}%
                  </p>
                </div>
              ) : downloadState === "complete" ? (
                <div className="text-center p-4 bg-green-50 border-2 border-green-300 rounded-lg">
                  <CheckCircle2 className="w-8 h-8 mx-auto text-green-600 mb-2" />
                  <p className="font-bold text-green-800">Download Complete!</p>
                  <p className="text-sm text-green-600">
                    Check your downloads folder
                  </p>
                </div>
              ) : (
                <Button
                  size="lg"
                  className="w-full border-4 border-black shadow-brutal hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-all text-lg py-6"
                  onClick={() => handleDownload(option.os)}
                >
                  <Download className="mr-2 w-5 h-5" />
                  Download for {option.label}
                </Button>
              )}
            </TabsContent>
          ))}
        </Tabs>

        <div className="mt-6 flex justify-center">
          <a
            href="https://github.com/Fix-It-For-Me-AI/local-home-agent/releases"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" />
            View all releases on GitHub
          </a>
        </div>
      </CardContent>
    </Card>
  );
}

function ModelDownloadWizard() {
  const [selectedModel, setSelectedModel] = useState<string | null>(
    "llama3.2:3b"
  );
  const [copied, setCopied] = useState(false);
  const [testStatus, setTestStatus] = useState<
    "idle" | "testing" | "success" | "error"
  >("idle");
  const [showLMStudio, setShowLMStudio] = useState(false);

  const handleCopy = (command: string) => {
    navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // DW2.6: Model testing feature
  const handleTestModel = async () => {
    setTestStatus("testing");
    try {
      // Try to connect to local Ollama and test the model
      const response = await fetch("http://localhost:11434/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: selectedModel,
          prompt: "Say hello in exactly 5 words.",
          stream: false,
        }),
      });
      if (response.ok) {
        setTestStatus("success");
      } else {
        setTestStatus("error");
      }
    } catch {
      setTestStatus("error");
    }
    // Reset after 3 seconds
    setTimeout(() => setTestStatus("idle"), 3000);
  };

  // LM Studio model equivalents (DW2.5)
  const LM_STUDIO_MODELS: Record<string, { name: string; url: string }> = {
    "llama3.2:1b": {
      name: "Llama 3.2 1B Instruct",
      url: "https://huggingface.co/lmstudio-community/Llama-3.2-1B-Instruct-GGUF",
    },
    "phi3:mini": {
      name: "Phi-3 Mini Instruct",
      url: "https://huggingface.co/lmstudio-community/Phi-3-mini-4k-instruct-GGUF",
    },
    "llama3.2:3b": {
      name: "Llama 3.2 3B Instruct",
      url: "https://huggingface.co/lmstudio-community/Llama-3.2-3B-Instruct-GGUF",
    },
    "mistral:7b-instruct": {
      name: "Mistral 7B Instruct",
      url: "https://huggingface.co/lmstudio-community/Mistral-7B-Instruct-v0.3-GGUF",
    },
    "llama3.1:8b": {
      name: "Llama 3.1 8B Instruct",
      url: "https://huggingface.co/lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
    },
    "qwen2.5-coder:7b": {
      name: "Qwen 2.5 Coder 7B",
      url: "https://huggingface.co/lmstudio-community/Qwen2.5-Coder-7B-Instruct-GGUF",
    },
  };

  return (
    <Card className="border-4 border-black shadow-brutal">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Brain className="w-5 h-5" />
          Choose Your AI Model
        </CardTitle>
        <CardDescription>
          Select a model based on your hardware. All models run locally with
          Ollama.
        </CardDescription>
        {/* DW2.5: LM Studio toggle */}
        <div className="flex items-center gap-2 mt-2">
          <span className="text-sm text-muted-foreground">Using:</span>
          <Button
            size="sm"
            variant={!showLMStudio ? "default" : "outline"}
            onClick={() => setShowLMStudio(false)}
            className="text-xs"
          >
            Ollama
          </Button>
          <Button
            size="sm"
            variant={showLMStudio ? "default" : "outline"}
            onClick={() => setShowLMStudio(true)}
            className="text-xs"
          >
            LM Studio
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3">
          {MODEL_RECOMMENDATIONS.map(model => (
            <div
              key={model.id}
              onClick={() => setSelectedModel(model.id)}
              className={`
                p-4 border-2 rounded-lg cursor-pointer transition-all
                ${
                  selectedModel === model.id
                    ? "border-black bg-gray-50 shadow-md"
                    : "border-gray-200 hover:border-gray-400"
                }
                ${model.recommended ? "ring-2 ring-accent-yellow ring-offset-2" : ""}
              `}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-bold">{model.name}</h4>
                    {model.recommended && (
                      <Badge className="bg-accent-yellow text-black border-black">
                        Recommended
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground mb-2">
                    {model.description}
                  </p>
                  <div className="flex items-center gap-2 flex-wrap text-xs">
                    <Badge variant="outline">{model.size}</Badge>
                    <Badge variant="outline">RAM: {model.ram}+</Badge>
                    <Badge
                      variant="outline"
                      className="bg-purple-50 text-purple-700 border-purple-200"
                    >
                      Context: {model.context}
                    </Badge>
                    <Badge className={getQualityColor(model.quality)}>
                      {model.quality}
                    </Badge>
                    <Badge className={getSpeedColor(model.speed)}>
                      {model.speed}
                    </Badge>
                  </div>
                </div>
                <div
                  className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                    selectedModel === model.id
                      ? "border-black bg-black"
                      : "border-gray-300"
                  }`}
                >
                  {selectedModel === model.id && (
                    <Check className="w-3 h-3 text-white" />
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {selectedModel && (
          <>
            {/* Ollama command or LM Studio link */}
            {showLMStudio ? (
              <div className="mt-6 p-4 bg-blue-50 border-2 border-blue-200 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-blue-800 font-medium">
                    Download from HuggingFace (LM Studio):
                  </span>
                </div>
                {LM_STUDIO_MODELS[selectedModel] ? (
                  <a
                    href={LM_STUDIO_MODELS[selectedModel].url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-blue-600 hover:underline font-mono text-sm"
                  >
                    <ExternalLink className="w-4 h-4" />
                    {LM_STUDIO_MODELS[selectedModel].name}
                  </a>
                ) : (
                  <span className="flex items-center gap-2 text-gray-500 font-mono text-sm">
                    <AlertCircle className="w-4 h-4" />
                    Model not available for LM Studio - use Ollama instead
                  </span>
                )}
                <p className="text-xs text-blue-600 mt-2">
                  Download the GGUF file and import it into LM Studio
                </p>
              </div>
            ) : (
              <div className="mt-6 p-4 bg-gray-900 text-gray-100 rounded-lg font-mono text-sm">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-gray-400">
                    Run this command to download:
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-gray-400 hover:text-white"
                    onClick={() =>
                      handleCopy(
                        MODEL_RECOMMENDATIONS.find(m => m.id === selectedModel)
                          ?.command || ""
                      )
                    }
                  >
                    {copied ? (
                      <Check className="w-4 h-4" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </Button>
                </div>
                <code className="text-green-400">
                  {
                    MODEL_RECOMMENDATIONS.find(m => m.id === selectedModel)
                      ?.command
                  }
                </code>
              </div>
            )}

            {/* DW2.6: Test model button */}
            <div className="flex items-center gap-4 mt-4">
              <Button
                onClick={handleTestModel}
                disabled={testStatus === "testing"}
                variant="outline"
                className="border-2 border-black"
              >
                {testStatus === "testing" && (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                )}
                {testStatus === "success" && (
                  <CheckCircle2 className="w-4 h-4 mr-2 text-green-600" />
                )}
                {testStatus === "error" && (
                  <AlertCircle className="w-4 h-4 mr-2 text-red-600" />
                )}
                {testStatus === "idle" && <Play className="w-4 h-4 mr-2" />}
                {testStatus === "testing"
                  ? "Testing..."
                  : testStatus === "success"
                    ? "Model Working!"
                    : testStatus === "error"
                      ? "Model Not Found"
                      : "Test This Model"}
              </Button>
              <span className="text-xs text-muted-foreground">
                Requires Ollama running at localhost:11434
              </span>
            </div>

            {/* DW2.8: Model switching note */}
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800">
              <strong>💡 Tip:</strong> You can switch models anytime in Local
              Agent Settings → AI Model without restarting the application.
            </div>
          </>
        )}

        <div className="text-center text-sm text-muted-foreground pt-2">
          <p>
            Don't have Ollama?{" "}
            <a
              href="https://ollama.com/download"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-red hover:underline"
            >
              Download Ollama first →
            </a>
            {" | "}
            Prefer a GUI?{" "}
            <a
              href="https://lmstudio.ai/download"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-red hover:underline"
            >
              Try LM Studio →
            </a>
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function InstallationWizard() {
  const [currentStep, setCurrentStep] = useState<WizardStep>("welcome");
  const [adminName, setAdminName] = useState("");
  const [adminPin, setAdminPin] = useState("");
  const [networkName, setNetworkName] = useState("Home Network");
  const [selectedComponents, setSelectedComponents] = useState<string[]>([
    "core",
    "ollama",
    "homeassistant",
  ]);

  const stepIndex = WIZARD_STEPS.findIndex(s => s.id === currentStep);
  const progress = ((stepIndex + 1) / WIZARD_STEPS.length) * 100;

  const goNext = () => {
    const nextIndex = Math.min(stepIndex + 1, WIZARD_STEPS.length - 1);
    setCurrentStep(WIZARD_STEPS[nextIndex].id);
  };

  const goPrev = () => {
    const prevIndex = Math.max(stepIndex - 1, 0);
    setCurrentStep(WIZARD_STEPS[prevIndex].id);
  };

  const toggleComponent = (id: string) => {
    setSelectedComponents(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    );
  };

  return (
    <Card className="border-4 border-black shadow-brutal-lg">
      <CardHeader>
        <div className="flex items-center justify-between mb-4">
          <CardTitle>Installation Setup</CardTitle>
          <Badge variant="outline" className="font-mono">
            Step {stepIndex + 1} of {WIZARD_STEPS.length}
          </Badge>
        </div>
        <Progress value={progress} className="h-2" />
        <div className="flex justify-between mt-2">
          {WIZARD_STEPS.map((step, i) => (
            <div
              key={step.id}
              className={`flex flex-col items-center ${i <= stepIndex ? "text-black" : "text-gray-300"}`}
            >
              <step.icon className="w-4 h-4" />
              <span className="text-xs mt-1 hidden md:block">{step.label}</span>
            </div>
          ))}
        </div>
      </CardHeader>
      <CardContent className="min-h-[300px]">
        {/* Welcome Step */}
        {currentStep === "welcome" && (
          <div className="text-center py-8">
            <Home className="w-16 h-16 mx-auto mb-4 text-accent-red" />
            <h2 className="text-2xl font-bold mb-4">
              Welcome to Local Home Agent
            </h2>
            <p className="text-muted-foreground max-w-md mx-auto mb-6">
              This wizard will guide you through setting up your private,
              AI-powered smart home management system. It only takes about 5
              minutes.
            </p>
            <div className="grid grid-cols-3 gap-4 max-w-lg mx-auto text-sm">
              <div className="p-4 bg-gray-50 rounded-lg">
                <Lock className="w-6 h-6 mx-auto mb-2 text-green-600" />
                <p className="font-medium">100% Private</p>
                <p className="text-muted-foreground text-xs">
                  Runs on your network
                </p>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <Zap className="w-6 h-6 mx-auto mb-2 text-yellow-600" />
                <p className="font-medium">AI Powered</p>
                <p className="text-muted-foreground text-xs">
                  Local LLM included
                </p>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <Users className="w-6 h-6 mx-auto mb-2 text-blue-600" />
                <p className="font-medium">Family Ready</p>
                <p className="text-muted-foreground text-xs">
                  Multi-user support
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Requirements Step */}
        {currentStep === "requirements" && <SystemRequirementsCheck />}

        {/* Components Step */}
        {currentStep === "components" && (
          <div className="space-y-4">
            <h3 className="font-bold text-lg">Select Components to Install</h3>
            <div className="space-y-3">
              {[
                {
                  id: "core",
                  name: "Local Home Agent Core",
                  size: "45 MB",
                  required: true,
                  description: "Main application (required)",
                },
                {
                  id: "ollama",
                  name: "Ollama Runtime",
                  size: "200 MB",
                  required: false,
                  description: "Local AI model runner",
                },
                {
                  id: "homeassistant",
                  name: "Home Assistant Bridge",
                  size: "15 MB",
                  required: false,
                  description: "Connect to Home Assistant",
                },
                {
                  id: "matter",
                  name: "Matter/Thread Support",
                  size: "25 MB",
                  required: false,
                  description: "Modern smart home protocol",
                },
              ].map(component => (
                <div
                  key={component.id}
                  onClick={() =>
                    !component.required && toggleComponent(component.id)
                  }
                  className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${
                    selectedComponents.includes(component.id)
                      ? "border-black bg-gray-50"
                      : "border-gray-200"
                  } ${component.required ? "opacity-75 cursor-not-allowed" : ""}`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium">{component.name}</h4>
                        {component.required && (
                          <Badge variant="outline">Required</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {component.description}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-muted-foreground">
                        {component.size}
                      </span>
                      <div
                        className={`w-5 h-5 rounded border-2 flex items-center justify-center ${
                          selectedComponents.includes(component.id)
                            ? "border-black bg-black"
                            : "border-gray-300"
                        }`}
                      >
                        {selectedComponents.includes(component.id) && (
                          <Check className="w-3 h-3 text-white" />
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-sm text-muted-foreground">
              Total size: ~
              {selectedComponents.includes("ollama") ? "285" : "85"} MB
            </p>
          </div>
        )}

        {/* Network Step */}
        {currentStep === "network" && (
          <div className="space-y-6">
            <h3 className="font-bold text-lg">Network Configuration</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  Network Name
                </label>
                <input
                  type="text"
                  value={networkName}
                  onChange={e => setNetworkName(e.target.value)}
                  className="w-full p-3 border-2 border-black rounded-lg font-mono"
                  placeholder="My Home Network"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  This is just a label for your reference
                </p>
              </div>

              <div className="p-4 bg-blue-50 border-2 border-blue-200 rounded-lg">
                <h4 className="font-medium flex items-center gap-2 mb-2">
                  <Wifi className="w-4 h-4" />
                  Auto-Detected Network
                </h4>
                <div className="text-sm space-y-1">
                  <p>
                    <strong>IP Address:</strong> 192.168.1.xxx (auto-assigned)
                  </p>
                  <p>
                    <strong>Port:</strong> 8000 (default)
                  </p>
                  <p>
                    <strong>Access URL:</strong> http://localhost:8000
                  </p>
                </div>
              </div>

              <div className="p-4 bg-yellow-50 border-2 border-yellow-200 rounded-lg">
                <p className="text-sm">
                  <strong>Note:</strong> Other devices on your network will be
                  able to access the Local Agent at the IP address shown above
                  after installation.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Admin Step */}
        {currentStep === "admin" && (
          <div className="space-y-6">
            <h3 className="font-bold text-lg">Create Admin Account</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  Admin Name
                </label>
                <input
                  type="text"
                  value={adminName}
                  onChange={e => setAdminName(e.target.value)}
                  className="w-full p-3 border-2 border-black rounded-lg"
                  placeholder="Your name"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  Security PIN (6 digits)
                </label>
                <input
                  type="password"
                  value={adminPin}
                  onChange={e =>
                    setAdminPin(e.target.value.replace(/\D/g, "").slice(0, 6))
                  }
                  className="w-full p-3 border-2 border-black rounded-lg font-mono text-2xl tracking-widest"
                  placeholder="••••••"
                  maxLength={6}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  This PIN is required for high-security actions like door locks
                </p>
              </div>

              <div className="p-4 bg-green-50 border-2 border-green-200 rounded-lg">
                <h4 className="font-medium flex items-center gap-2 mb-2">
                  <Shield className="w-4 h-4 text-green-600" />
                  Thermodynamic Security Model
                </h4>
                <p className="text-sm text-muted-foreground">
                  Your Local Agent uses an energy-based security system.
                  Low-risk actions happen automatically. High-risk actions
                  require PIN verification.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Model Step */}
        {currentStep === "model" && <ModelDownloadWizard />}

        {/* Complete Step */}
        {currentStep === "complete" && (
          <div className="text-center py-8">
            <div className="w-20 h-20 mx-auto mb-4 bg-green-100 rounded-full flex items-center justify-center">
              <CheckCircle2 className="w-12 h-12 text-green-600" />
            </div>
            <h2 className="text-2xl font-bold mb-4">Setup Complete!</h2>
            <p className="text-muted-foreground max-w-md mx-auto mb-6">
              Your Local Home Agent is ready to use. Click the button below to
              launch the application and start managing your smart home.
            </p>
            <Button
              size="lg"
              className="border-4 border-black shadow-brutal hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-all"
            >
              <Play className="mr-2" />
              Launch Local Home Agent
            </Button>
            <p className="text-sm text-muted-foreground mt-4">
              Or open{" "}
              <code className="bg-gray-100 px-2 py-1 rounded">
                http://localhost:8000
              </code>{" "}
              in your browser
            </p>
          </div>
        )}
      </CardContent>

      {/* Navigation */}
      <div className="px-6 pb-6 flex justify-between">
        <Button
          variant="outline"
          onClick={goPrev}
          disabled={stepIndex === 0}
          className="border-2 border-black"
        >
          <ArrowLeft className="mr-2 w-4 h-4" />
          Back
        </Button>

        {stepIndex < WIZARD_STEPS.length - 1 ? (
          <Button
            onClick={goNext}
            className="border-2 border-black shadow-brutal hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-all"
          >
            Next
            <ArrowRight className="ml-2 w-4 h-4" />
          </Button>
        ) : (
          <Button className="border-2 border-black shadow-brutal bg-green-600 hover:bg-green-700 hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-all">
            <Play className="mr-2 w-4 h-4" />
            Finish & Launch
          </Button>
        )}
      </div>
    </Card>
  );
}

function FeatureHighlights() {
  const features = [
    {
      icon: Lock,
      title: "100% Private",
      description:
        "Runs entirely on your local network. No cloud required. Your data never leaves your home.",
    },
    {
      icon: Brain,
      title: "AI-Powered",
      description:
        "Natural language control with local LLM. Ask Felix to adjust temperature, lock doors, or create automations.",
    },
    {
      icon: Shield,
      title: "Thermodynamic Security",
      description:
        "Energy-based access control. Low-risk actions are automatic, high-risk actions require verification.",
    },
    {
      icon: Sparkles,
      title: "Smart Automations",
      description:
        "Create routines with natural language. 'When I say goodnight, turn off all lights and lock the doors.'",
    },
    {
      icon: Users,
      title: "Family Access",
      description:
        "Different permission levels for family members and guests. Kids can control their room, not the thermostat.",
    },
    {
      icon: Zap,
      title: "Energy Monitoring",
      description:
        "Track energy usage across all devices. Get AI-powered recommendations to reduce your bills.",
    },
  ];

  return (
    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
      {features.map((feature, i) => (
        <Card key={i} className="border-2 border-black">
          <CardContent className="pt-6">
            <feature.icon className="w-10 h-10 mb-4 text-accent-red" />
            <h3 className="font-bold text-lg mb-2">{feature.title}</h3>
            <p className="text-muted-foreground text-sm">
              {feature.description}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function LocalAgentDownload() {
  const [detectedOS, setDetectedOS] = useState<OperatingSystem>("unknown");
  const [showWizard, setShowWizard] = useState(false);

  useEffect(() => {
    setDetectedOS(detectOS());
  }, []);

  return (
    <div className="min-h-screen bg-background relative">
      <AnimatedBackground variant="geometric" opacity={0.04} />
      <div className="relative z-10">
        {/* Hero Section */}
        <section className="border-b-4 border-black py-16 md:py-24 bg-gradient-to-br from-white to-gray-50">
          <div className="container">
            <div className="max-w-4xl mx-auto text-center">
              <div className="mb-6">
                <Badge className="bg-accent-red text-white border-2 border-black px-4 py-1 text-sm font-mono">
                  FREE & OPEN SOURCE
                </Badge>
              </div>

              <h1 className="text-4xl md:text-5xl lg:text-6xl font-black mb-6">
                LOCAL HOME
                <br />
                <span className="text-accent-red">AGENT</span>
              </h1>

              <p className="text-xl md:text-2xl mb-6 font-mono max-w-2xl mx-auto text-muted-foreground">
                AI-powered smart home management that runs{" "}
                <strong>entirely on your network</strong>. No cloud. No
                subscriptions. Complete privacy.
              </p>

              <OSDetectionBanner detectedOS={detectedOS} />

              <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-center">
                <Button
                  size="lg"
                  className="border-4 border-black shadow-brutal hover:translate-x-2 hover:translate-y-2 hover:shadow-none transition-all text-lg px-8"
                  onClick={() =>
                    document
                      .getElementById("download")
                      ?.scrollIntoView({ behavior: "smooth" })
                  }
                >
                  <Download className="mr-2" />
                  Download Now
                </Button>
                <Button
                  size="lg"
                  variant="outline"
                  className="border-4 border-black shadow-brutal hover:translate-x-2 hover:translate-y-2 hover:shadow-none transition-all text-lg"
                  asChild
                >
                  <a
                    href="https://github.com/Fix-It-For-Me-AI/local-home-agent"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <ExternalLink className="mr-2" />
                    View on GitHub
                  </a>
                </Button>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="py-16 md:py-24">
          <div className="container">
            <h2 className="text-3xl font-black text-center mb-12">
              Why Local Home Agent?
            </h2>
            <FeatureHighlights />
          </div>
        </section>

        {/* Download Section */}
        <section
          id="download"
          className="py-16 md:py-24 bg-gray-50 border-y-4 border-black"
        >
          <div className="container">
            <div className="max-w-2xl mx-auto">
              {showWizard ? (
                <InstallationWizard />
              ) : (
                <>
                  <DownloadSection
                    detectedOS={detectedOS}
                    onDownloadStart={() => setShowWizard(true)}
                  />
                  <div className="mt-8">
                    <SystemRequirementsCheck />
                  </div>
                </>
              )}
            </div>
          </div>
        </section>

        {/* Model Recommendations Section */}
        <section className="py-16 md:py-24">
          <div className="container">
            <div className="max-w-2xl mx-auto">
              <h2 className="text-3xl font-black text-center mb-4">
                Choose Your AI Model
              </h2>
              <p className="text-center text-muted-foreground mb-8">
                Local Home Agent uses Ollama to run AI models locally. Choose
                based on your hardware.
              </p>
              <ModelDownloadWizard />
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-16 md:py-24 bg-black text-white">
          <div className="container text-center">
            <h2 className="text-3xl md:text-4xl font-black mb-6">
              Ready to take control of your smart home?
            </h2>
            <p className="text-xl text-gray-400 mb-8 max-w-2xl mx-auto">
              Join thousands of homeowners who manage their smart devices
              privately and securely.
            </p>
            <Button
              size="lg"
              className="bg-accent-red hover:bg-red-600 border-4 border-white shadow-brutal-white hover:translate-x-2 hover:translate-y-2 hover:shadow-none transition-all text-lg px-8"
              onClick={() =>
                document
                  .getElementById("download")
                  ?.scrollIntoView({ behavior: "smooth" })
              }
            >
              <Download className="mr-2" />
              Download Free
            </Button>
            <p className="text-sm text-gray-500 mt-4">
              MIT License • No account required • Works offline
            </p>
          </div>
        </section>

        {/* Back to Platform Link */}
        <section className="py-8 border-t-4 border-black">
          <div className="container text-center">
            <Link
              href="/"
              className="text-muted-foreground hover:text-foreground flex items-center justify-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Co-Living Platform
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
