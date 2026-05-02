import { useEffect, useState } from "react";
import {
  detectHardware,
  recommendModel,
  type HardwareProfile,
  type ModelRecommendation,
} from "../lib/hardwareDetection";

const RELEASES_URL = "https://github.com/chiziuwaga/localhomeagent/releases/latest";

const OS_LABEL: Record<HardwareProfile["platform"]["os"], string> = {
  windows: "Windows",
  macos: "macOS",
  linux: "Linux",
  ios: "iOS",
  android: "Android",
  unknown: "your operating system",
};

export function Download() {
  const [profile, setProfile] = useState<HardwareProfile | null>(null);
  const [model, setModel] = useState<ModelRecommendation | null>(null);

  useEffect(() => {
    try {
      const p = detectHardware();
      setProfile(p);
      setModel(recommendModel(p));
    } catch {
      setProfile(null);
    }
  }, []);

  const osLabel = profile ? OS_LABEL[profile.platform.os] : "your operating system";

  return (
    <section className="px-6 py-16 max-w-5xl mx-auto">
      <h1 className="font-mono text-4xl md:text-6xl font-bold uppercase mb-6">
        Download <span className="text-red-600">Local Home Agent</span>
      </h1>
      <p className="text-lg max-w-2xl mb-10">
        We detected you're on <strong>{osLabel}</strong>. Grab the latest release,
        run the installer, and the agent will pair itself with your coliving platform.
      </p>

      <div className="border-4 border-black p-6 shadow-brutal mb-10">
        <h2 className="font-mono uppercase text-xl font-bold mb-4">
          Step 1 &mdash; Get the binary
        </h2>
        <a
          href={RELEASES_URL}
          className="inline-block font-mono uppercase border-4 border-black bg-black text-white px-6 py-3 shadow-brutal-sm hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-transform"
        >
          GitHub Releases &rarr;
        </a>
        <p className="mt-4 text-sm text-neutral-700">
          Pre-built artifacts for Windows, macOS (Apple Silicon &amp; Intel), and Linux x86_64.
        </p>
      </div>

      <div className="border-4 border-black p-6 shadow-brutal mb-10">
        <h2 className="font-mono uppercase text-xl font-bold mb-4">
          Step 2 &mdash; Pick a local LLM
        </h2>
        <p className="mb-4">
          The agent runs against{" "}
          <a className="underline" href="https://ollama.com">Ollama</a> by default and falls
          back to <a className="underline" href="https://lmstudio.ai">LM Studio</a>. Recommended
          model based on your hardware:
        </p>
        {profile ? (
          <ul className="font-mono text-sm space-y-1">
            <li>
              GPU: {profile.gpu.vendor} {profile.gpu.renderer} ({profile.gpu.tier})
            </li>
            <li>Estimated VRAM: {profile.gpu.estimatedVRAM} MB</li>
            <li>System RAM: {profile.memory.estimatedTotalRAM} GB</li>
            <li>CPU cores: {profile.cpu.cores}</li>
            {model && (
              <li className="pt-2">
                <strong>Recommended:</strong> {model.name} &mdash; {model.size}, {model.ram}, {model.contextWindow}
              </li>
            )}
          </ul>
        ) : (
          <p className="font-mono text-sm">
            Hardware detection unavailable in this browser &mdash; pick a model that matches your VRAM.
          </p>
        )}
      </div>

      <div className="border-4 border-black p-6 shadow-brutal-red">
        <h2 className="font-mono uppercase text-xl font-bold mb-4">
          Step 3 &mdash; Pair with your platform
        </h2>
        <p>
          On first run, the agent will print a one-time pairing code. Paste it into Settings
          &rarr; Agents on{" "}
          <a className="underline" href="https://coliving.fixitforme.ai">coliving.fixitforme.ai</a>{" "}
          and you're done.
        </p>
      </div>
    </section>
  );
}
