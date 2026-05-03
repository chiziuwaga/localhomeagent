export function Home() {
  return (
    <>
      <section className="px-6 py-20 max-w-5xl mx-auto">
        <h1 className="font-mono text-5xl md:text-7xl font-bold uppercase leading-none mb-6">
          The offline AI <br />
          for <span className="text-red-600">co-living</span> operators.
        </h1>
        <p className="text-lg md:text-xl max-w-2xl mb-10">
          Local Home Agent runs on the operator's own machine. It talks to local
          LLMs (Ollama, LM Studio), drives a captive-portal Wi-Fi onboarding
          flow for guests, and integrates with smart-home devices &mdash; all
          without sending data to the cloud.
        </p>
        <div className="flex flex-wrap gap-4">
          <a
            href="#download"
            className="font-mono uppercase border-4 border-black bg-black text-white px-6 py-3 shadow-brutal hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-transform"
          >
            Download &rarr;
          </a>
          <a
            href="https://github.com/chiziuwaga/localhomeagent"
            className="font-mono uppercase border-4 border-black bg-white text-black px-6 py-3 shadow-brutal hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-transform"
          >
            Source code
          </a>
        </div>
      </section>

      <section className="border-t-4 border-black px-6 py-16 max-w-5xl mx-auto">
        <h2 className="font-mono text-3xl uppercase font-bold mb-10">
          What it does
        </h2>
        <div className="grid md:grid-cols-2 gap-6">
          <Feature
            title="Offline AI Concierge"
            body="Greets guests, answers questions, and dispatches requests through a thermodynamic agent swarm. Powered by Kimi K2 in the cloud and your local LLM on-prem."
          />
          <Feature
            title="Wi-Fi Captive Portal"
            body="Guests join the network, authenticate with their reservation code, and land in your branded onboarding flow. Compliant with the major OS captive-portal probes."
          />
          <Feature
            title="Smart-Home Control"
            body="Locks, thermostats, lights, sensors. Z-Wave / Zigbee / Matter via the local hub. The agent acts on guest intent without phoning home."
          />
          <Feature
            title="Pairs with the Coliving platform"
            body="Listings, deals, and inquiries flow from coliving.fixitforme.ai into the agent. The agent reports occupancy and energy back."
          />
        </div>
      </section>
    </>
  );
}

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <article className="border-4 border-black bg-white p-6 shadow-brutal-sm">
      <h3 className="font-mono uppercase text-lg font-bold mb-2">{title}</h3>
      <p className="text-base text-neutral-800">{body}</p>
    </article>
  );
}
