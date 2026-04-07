import { useNavigate } from "react-router-dom";
import { Dog, Microscope, Heart, ChevronDown } from "lucide-react";
import { getProfile, type UserProfileId } from "../../lib/profile";

// Mirrors the ICONS map in Onboarding.tsx so the header affordance looks
// consistent with the profile picker. Kept in sync manually — if a new
// profile is added, both files need the icon entry.
const ICONS: Record<UserProfileId, typeof Dog> = {
  pet_owner: Dog,
  lab_tech: Microscope,
  field_worker: Heart,
};

/**
 * ProfileSwitcher — visible affordance in the app header to change the
 * active profile without having to discover the buried button at the
 * bottom of About.
 *
 * Rendered only when a profile is already set (the OnboardingGate ensures
 * this component is only mounted inside AppLayout, which only renders with
 * profile !== null, so getProfile() returning null here is defensive).
 *
 * Clicking navigates to /onboarding (direct route, outside the gate) which
 * renders Onboarding without the tick-counter dependency. Picking any
 * profile there calls setProfile() + navigate("/capture"), which remounts
 * Capture with the new profile. Picking the same profile is a no-op for
 * localStorage but still routes back to /capture, which is acceptable
 * cancel behavior.
 *
 * Deliberately NOT calling clearProfile() first: navigating away without
 * picking should preserve the current profile. The About page button
 * keeps its existing clearProfile-then-navigate behavior for backward
 * compat with users who learned that flow.
 */
export function ProfileSwitcher() {
  const navigate = useNavigate();
  const profile = getProfile();
  if (!profile) return null;

  const Icon = ICONS[profile.id];

  return (
    <button
      onClick={() => navigate("/onboarding")}
      aria-label={`Current profile: ${profile.label}. Tap to change.`}
      className="flex items-center gap-1.5 text-xs text-content-muted hover:text-teal-text transition-colors"
    >
      <Icon size={14} />
      <span className="hidden sm:inline">{profile.label}</span>
      <ChevronDown size={12} className="opacity-60" />
    </button>
  );
}
