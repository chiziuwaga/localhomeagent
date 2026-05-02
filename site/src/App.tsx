import { useState } from "react";
import { Home } from "./pages/Home";
import { Download } from "./pages/Download";

type Route = "home" | "download";

function getRouteFromHash(): Route {
  return window.location.hash === "#download" ? "download" : "home";
}

export default function App() {
  const [route, setRoute] = useState<Route>(getRouteFromHash());

  if (typeof window !== "undefined") {
    window.onhashchange = () => setRoute(getRouteFromHash());
  }

  return (
    <div className="min-h-screen bg-white text-black font-sans">
      <header className="border-b-4 border-black px-6 py-4 flex items-center justify-between">
        <a href="#" className="font-mono text-xl font-bold uppercase tracking-tight">
          Local Home <span className="text-red-600">Agent</span>
        </a>
        <nav className="flex items-center gap-6 font-mono text-sm uppercase">
          <a href="#" className="hover:text-red-600">Home</a>
          <a href="#download" className="hover:text-red-600">Download</a>
          <a
            href="https://coliving.fixitforme.ai"
            className="border-2 border-black px-3 py-1 shadow-[4px_4px_0_0_#000] hover:bg-black hover:text-white transition-colors"
          >
            Coliving Platform &rarr;
          </a>
        </nav>
      </header>

      <main>{route === "download" ? <Download /> : <Home />}</main>

      <footer className="border-t-4 border-black px-6 py-8 mt-16 font-mono text-xs uppercase">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <span>&copy; {new Date().getFullYear()} FixItForMe</span>
          <a
            href="https://github.com/chiziuwaga/localhomeagent"
            className="hover:text-red-600"
          >
            github.com/chiziuwaga/localhomeagent
          </a>
        </div>
      </footer>
    </div>
  );
}
