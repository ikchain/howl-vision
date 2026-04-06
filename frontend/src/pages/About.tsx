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
    <div className="px-4 py-6 space-y-6">
      {/* Hero */}
      <div
        className="text-center py-8 rounded-2xl"
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(0,107,128,0.15) 0%, transparent 70%)",
        }}
      >
        <img
          src="/logo-color.svg"
          alt="Howl Vision"
          className="w-16 h-16 mx-auto mb-4"
        />
        <h1 className="text-2xl font-bold">Howl Vision</h1>
        <p className="text-sm text-content-secondary mt-2">
          Accessible veterinary diagnosis where there is no specialist
        </p>
        <div className="flex items-center justify-center gap-3 mt-5">
          <Link
            to="/capture"
            className="bg-teal hover:bg-teal-hover text-white rounded-xl px-6 py-2.5 font-medium text-sm transition-colors shadow-lg shadow-teal/20"
          >
            Try it now &rarr;
          </Link>
          {installPrompt && (
            <button
              onClick={() => installPrompt.prompt()}
              className="px-4 py-2.5 bg-teal rounded-xl text-sm font-medium text-white hover:bg-teal-hover transition-colors"
            >
              Install App
            </button>
          )}
        </div>
      </div>

      {/* Features */}
      <div>
        <h2 className="text-base font-semibold text-center mb-4">What it does</h2>
        <div className="space-y-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="bg-ocean-surface rounded-xl p-4 border border-ocean-border flex items-start gap-3"
            >
              <div className="w-10 h-10 rounded-lg bg-teal/10 flex items-center justify-center flex-shrink-0">
                <f.icon size={20} className="text-teal-text" />
              </div>
              <div>
                <h3 className="text-sm font-semibold mb-0.5">{f.title}</h3>
                <p className="text-content-secondary text-xs leading-relaxed">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Metrics */}
      <div className="bg-ocean-surface/50 rounded-xl p-4 border border-ocean-border">
        <div className="grid grid-cols-2 gap-4 text-center">
          {METRICS.map((m) => (
            <div key={m.label}>
              <div className="text-xl font-bold text-teal-light">{m.value}</div>
              <div className="text-content-secondary text-[10px] mt-0.5">{m.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Pipeline */}
      <div className="text-center">
        <h2 className="text-xs font-semibold text-content-muted uppercase tracking-wider mb-2">
          How it works
        </h2>
        <div className="flex items-center justify-center flex-wrap gap-1.5">
          {PIPELINE.map((step, i) => (
            <span key={step} className="contents">
              <span className="bg-ocean-surface px-2.5 py-1 rounded-md text-[10px] text-content-secondary border border-ocean-border">
                {step}
              </span>
              {i < PIPELINE.length - 1 && (
                <ChevronRight size={12} className="text-teal-text flex-shrink-0" />
              )}
            </span>
          ))}
        </div>
      </div>

      {/* Profile */}
      {profile && (
        <div className="flex items-center justify-between bg-ocean-surface rounded-xl px-4 py-3 border border-ocean-border">
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

      {/* Footer */}
      <div className="text-center space-y-1 pt-2 pb-2">
        <p className="text-content-muted text-[10px]">
          Powered by Gemma 4 &middot; Fine-tuned with Unsloth &middot; Runs on Ollama &middot; Exported with llama.cpp
        </p>
        <p className="text-content-muted text-[10px] opacity-60">
          Gemma 4 Good Hackathon 2026 &middot; Open Source
        </p>
      </div>
    </div>
  );
}
