import { useNavigate } from "react-router-dom";
import { Dog, Microscope, Heart } from "lucide-react";
import { PROFILES, setProfile, type UserProfileId, type ProfileConfig } from "../lib/profile";

const ICONS: Record<UserProfileId, typeof Dog> = {
  pet_owner: Dog,
  lab_tech: Microscope,
  field_worker: Heart,
};

const PROFILE_ORDER: UserProfileId[] = ["pet_owner", "lab_tech", "field_worker"];

interface Props {
  onComplete?: () => void;
}

export default function Onboarding({ onComplete }: Props = {}) {
  const navigate = useNavigate();

  function handleSelect(id: UserProfileId) {
    setProfile(id);
    onComplete?.();
    navigate("/capture", { replace: true });
  }

  return (
    <div className="min-h-screen bg-ocean-deep flex flex-col items-center justify-center px-4 py-12">
      <div className="max-w-sm w-full space-y-6">
        <div className="text-center space-y-2">
          <img src="/logo-white.svg" alt="Howl Vision" className="w-10 h-10 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-content-primary">Welcome to Howl Vision</h1>
          <p className="text-sm text-content-muted">How will you use this app?</p>
        </div>

        <div className="space-y-3">
          {PROFILE_ORDER.map((id) => {
            const profile: ProfileConfig = PROFILES[id];
            const Icon = ICONS[id];
            return (
              <button
                key={id}
                onClick={() => handleSelect(id)}
                className="w-full flex items-start gap-4 bg-ocean-surface border border-ocean-border hover:border-teal rounded-xl p-4 text-left transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-teal/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Icon className="w-5 h-5 text-teal-text" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-content-primary">{profile.label}</p>
                  <p className="text-xs text-content-muted mt-0.5 leading-relaxed">{profile.description}</p>
                </div>
              </button>
            );
          })}
        </div>

        <p className="text-center text-[10px] text-content-muted">
          You can change this anytime from the header
        </p>
      </div>
    </div>
  );
}
