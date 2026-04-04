import { Link } from "react-router-dom";
import { MessageSquare, ScanLine, Database, ChevronRight } from "lucide-react";

export function About() {
  return (
    <div className="min-h-screen bg-ocean-deep text-content-primary">
      {/* Hero */}
      <section
        className="min-h-[70vh] flex items-center justify-center"
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(0,107,128,0.15) 0%, transparent 70%)",
        }}
      >
        <div className="text-center px-6">
          <img
            src="/logo-color.svg"
            alt="Howl Vision"
            className="w-28 h-28 mx-auto mb-6"
          />
          <h1 className="text-5xl font-bold text-content-primary">
            Howl Vision
          </h1>
          <p className="text-xl text-content-secondary max-w-lg mx-auto mt-3">
            AI-powered veterinary copilot for clinics without internet
          </p>
          <Link
            to="/chat"
            className="bg-teal hover:bg-teal-hover text-white rounded-xl px-8 py-3.5 font-medium text-lg mt-8 inline-block transition-colors shadow-lg shadow-teal/20"
          >
            Try it now →
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 max-w-5xl mx-auto px-6">
        <h2 className="text-2xl font-semibold text-content-primary text-center mb-12">
          What it does
        </h2>
        <div className="grid grid-cols-3 gap-8">
          {/* Card 1 */}
          <div className="bg-ocean-surface rounded-xl p-8 border border-ocean-border">
            <div className="w-12 h-12 rounded-xl bg-teal/10 flex items-center justify-center mb-4">
              <MessageSquare size={24} className="text-teal-text" />
            </div>
            <h3 className="text-lg font-semibold text-content-primary mb-2">
              Conversational AI
            </h3>
            <p className="text-content-secondary text-sm leading-relaxed">
              Chat naturally with Gemma 4 about symptoms, differential
              diagnoses, treatments, and drug interactions.
            </p>
          </div>

          {/* Card 2 */}
          <div className="bg-ocean-surface rounded-xl p-8 border border-ocean-border">
            <div className="w-12 h-12 rounded-xl bg-teal/10 flex items-center justify-center mb-4">
              <ScanLine size={24} className="text-teal-text" />
            </div>
            <h3 className="text-lg font-semibold text-content-primary mb-2">
              Vision Diagnosis
            </h3>
            <p className="text-content-secondary text-sm leading-relaxed">
              Upload clinical images for AI-powered dermatology classification
              and blood parasite detection.
            </p>
          </div>

          {/* Card 3 */}
          <div className="bg-ocean-surface rounded-xl p-8 border border-ocean-border">
            <div className="w-12 h-12 rounded-xl bg-teal/10 flex items-center justify-center mb-4">
              <Database size={24} className="text-teal-text" />
            </div>
            <h3 className="text-lg font-semibold text-content-primary mb-2">
              Clinical Knowledge
            </h3>
            <p className="text-content-secondary text-sm leading-relaxed">
              Search 22,000 veterinary cases with semantic similarity powered
              by SapBERT embeddings.
            </p>
          </div>
        </div>
      </section>

      {/* Metrics */}
      <section className="py-16 max-w-4xl mx-auto px-6">
        <div className="bg-ocean-surface/50 rounded-2xl p-8 border border-ocean-border">
          <div className="grid grid-cols-4 gap-6 text-center">
            <div>
              <div className="text-3xl font-bold text-teal-light">94%</div>
              <div className="text-content-secondary text-sm mt-1">
                Dermatology accuracy
              </div>
            </div>
            <div>
              <div className="text-3xl font-bold text-teal-light">99.87%</div>
              <div className="text-content-secondary text-sm mt-1">
                Parasite detection
              </div>
            </div>
            <div>
              <div className="text-3xl font-bold text-teal-light">22K</div>
              <div className="text-content-secondary text-sm mt-1">
                Clinical cases
              </div>
            </div>
            <div>
              <div className="text-3xl font-bold text-teal-light">100%</div>
              <div className="text-content-secondary text-sm mt-1">
                Offline capable
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-16 max-w-3xl mx-auto px-6 text-center">
        <h2 className="text-2xl font-semibold text-content-primary mb-6">
          How it works
        </h2>
        <div className="flex items-center justify-center flex-wrap gap-2">
          <span className="bg-ocean-surface px-4 py-2 rounded-lg text-sm text-content-secondary border border-ocean-border">
            Clinical Image
          </span>
          <ChevronRight size={16} className="text-teal-text" />
          <span className="bg-ocean-surface px-4 py-2 rounded-lg text-sm text-content-secondary border border-ocean-border">
            Vision Models
          </span>
          <ChevronRight size={16} className="text-teal-text" />
          <span className="bg-ocean-surface px-4 py-2 rounded-lg text-sm text-content-secondary border border-ocean-border">
            Gemma 4 E4B
          </span>
          <ChevronRight size={16} className="text-teal-text" />
          <span className="bg-ocean-surface px-4 py-2 rounded-lg text-sm text-content-secondary border border-ocean-border">
            Clinical Report
          </span>
        </div>
      </section>

      {/* Tech strip */}
      <section className="py-8 text-center">
        <p className="text-content-muted text-sm">
          Powered by Gemma 4 · Fine-tuned with Unsloth · Runs on Ollama ·
          Exported with llama.cpp
        </p>
      </section>

      {/* Footer */}
      <footer className="py-6 text-center border-t border-ocean-border">
        <p className="text-content-muted text-xs">
          Gemma 4 Good Hackathon 2026 · Open Source
        </p>
      </footer>
    </div>
  );
}
