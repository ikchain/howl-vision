import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MessageSquare, ScanLine, Database, ChevronRight, UserCircle } from "lucide-react";
import { getProfile, clearProfile } from "../lib/profile";
import type { BeforeInstallPromptEvent } from "../types";

const FEATURES = [
  {
    icon: MessageSquare,
    title: "Conversational AI",
    desc: "Chat naturally with Gemma 4 about symptoms, differential diagnoses, treatments, and drug interactions.",
  },
  {
    icon: ScanLine,
    title: "Vision Diagnosis",
    desc: "Upload clinical images for AI-powered dermatology classification and blood parasite detection.",
  },
  {
    icon: Database,
    title: "Clinical Knowledge",
    desc: "Search 22,000 veterinary cases with semantic similarity powered by SapBERT embeddings.",
  },
];

const METRICS = [
  { value: "94%", label: "Dermatology accuracy" },
  { value: "99.87%", label: "Parasite detection" },
  { value: "22K", label: "Clinical cases" },
  { value: "100%", label: "Offline capable" },
];

const PIPELINE = ["Clinical Image", "Vision Models", "Gemma 4 E4B", "Clinical Report"];

export function About() {
  const navigate = useNavigate();
  const profile = getProfile();
  const [installPrompt, setInstallPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setInstallPrompt(e as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  return (
    <div className="min-h-screen bg-ocean-deep text-content-primary flex flex-col">
      {/* Hero */}
      <section
        className="flex-shrink-0 flex items-center justify-center px-6 py-12 md:py-16 lg:py-20"
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(0,107,128,0.15) 0%, transparent 70%)",
        }}
      >
        <div className="text-center max-w-2xl">
          <img
            src="/logo-color.svg"
            alt="Howl Vision"
            className="w-16 h-16 md:w-20 md:h-20 lg:w-24 lg:h-24 mx-auto mb-4"
          />
          <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold">
            Howl Vision
          </h1>
          <p className="text-base md:text-lg text-content-secondary mt-2 md:mt-3">
            Accessible veterinary diagnosis where there is no specialist
          </p>
          <Link
            to="/chat"
            className="bg-teal hover:bg-teal-hover text-white rounded-xl px-6 py-2.5 md:px-8 md:py-3 font-medium text-sm md:text-base mt-5 md:mt-6 inline-block transition-colors shadow-lg shadow-teal/20"
          >
            Try it now &rarr;
          </Link>
          {installPrompt && (
            <button
              onClick={() => {
                installPrompt.prompt();
              }}
              className="px-4 py-2 bg-teal rounded-lg text-sm font-semibold text-white hover:bg-teal-hover transition-colors ml-3"
            >
              Install App
            </button>
          )}
        </div>
      </section>

      {/* Features + Metrics in a combined flow */}
      <section className="flex-1 px-4 md:px-6 pb-4">
        <div className="max-w-5xl mx-auto">
          {/* Features */}
          <h2 className="text-lg font-semibold text-center mb-5 md:mb-6">
            What it does
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="bg-ocean-surface rounded-xl p-5 md:p-6 border border-ocean-border hover:border-ocean-border-hover transition-colors"
              >
                <div className="w-10 h-10 rounded-xl bg-teal/10 flex items-center justify-center mb-3">
                  <f.icon size={22} className="text-teal-text" />
                </div>
                <h3 className="text-base font-semibold mb-1.5">{f.title}</h3>
                <p className="text-content-secondary text-sm leading-relaxed">
                  {f.desc}
                </p>
              </div>
            ))}
          </div>

          {/* Metrics */}
          <div className="bg-ocean-surface/50 rounded-xl p-5 md:p-6 border border-ocean-border mt-6 md:mt-8">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6 text-center">
              {METRICS.map((m) => (
                <div key={m.label}>
                  <div className="text-2xl md:text-3xl font-bold text-teal-light">
                    {m.value}
                  </div>
                  <div className="text-content-secondary text-xs md:text-sm mt-1">
                    {m.label}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Pipeline */}
          <div className="text-center mt-6 md:mt-8">
            <h2 className="text-sm font-semibold text-content-muted uppercase tracking-wider mb-3">
              How it works
            </h2>
            <div className="flex items-center justify-center flex-wrap gap-1.5 md:gap-2">
              {PIPELINE.map((step, i) => (
                <span key={step} className="contents">
                  <span className="bg-ocean-surface px-3 py-1.5 rounded-md text-xs md:text-sm text-content-secondary border border-ocean-border">
                    {step}
                  </span>
                  {i < PIPELINE.length - 1 && (
                    <ChevronRight size={14} className="text-teal-text flex-shrink-0" />
                  )}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Profile + Footer */}
      <footer className="flex-shrink-0 border-t border-ocean-border">
        {profile && (
          <div className="flex items-center justify-between px-4 py-3 border-b border-ocean-border">
            <div className="flex items-center gap-2">
              <UserCircle size={16} className="text-content-muted" />
              <span className="text-xs text-content-secondary">{profile.label}</span>
            </div>
            <button
              onClick={() => { clearProfile(); navigate("/onboarding", { replace: true }); }}
              className="text-xs text-teal-text hover:underline"
            >
              Change profile
            </button>
          </div>
        )}
        <div className="py-4 text-center space-y-1">
          <p className="text-content-muted text-xs">
            Powered by Gemma 4 &middot; Fine-tuned with Unsloth &middot; Runs on Ollama &middot; Exported with llama.cpp
          </p>
          <p className="text-content-muted text-xs opacity-60">
            Gemma 4 Good Hackathon 2026 &middot; Open Source
          </p>
        </div>
      </footer>
    </div>
  );
}
