import { Link } from "react-router-dom";

export function About() {
  return (
    <div className="min-h-screen bg-ocean-deep flex items-center justify-center">
      <div className="text-center">
        <img src="/logo-color.svg" alt="Howl Vision" className="w-24 h-24 mx-auto mb-6" />
        <h1 className="text-4xl font-semibold text-content-primary mb-2">Howl Vision</h1>
        <p className="text-content-secondary mb-8">AI-powered veterinary copilot for clinics without internet</p>
        <Link to="/chat" className="px-6 py-3 bg-teal hover:bg-teal-hover text-white rounded-lg font-medium transition-colors">
          Try it now
        </Link>
      </div>
    </div>
  );
}
