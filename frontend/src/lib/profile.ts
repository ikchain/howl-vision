export type UserProfileId = "pet_owner" | "lab_tech" | "field_worker";

export interface ProfileConfig {
  id: UserProfileId;
  label: string;
  description: string;
  cameraHint: string;
  modules: Array<"dermatology" | "parasites">;
}

const STORAGE_KEY = "howl-user-profile";

export const PROFILES: Record<UserProfileId, ProfileConfig> = {
  pet_owner: {
    id: "pet_owner",
    label: "Pet Owner",
    description: "I want to check my pet's skin condition and get guidance on what to do next.",
    cameraHint: "Hold camera 30cm from affected area",
    modules: ["dermatology"],
  },
  lab_tech: {
    id: "lab_tech",
    label: "Lab Technician",
    description: "I analyze blood samples under a microscope and need help identifying parasites.",
    cameraHint: "Center the microscope field",
    modules: ["parasites", "dermatology"],
  },
  field_worker: {
    id: "field_worker",
    label: "Field Worker",
    description: "I work with animals in shelters or rural communities and need fast screening.",
    cameraHint: "Photograph the lesion or sample",
    modules: ["dermatology", "parasites"],
  },
};

export function getProfile(): ProfileConfig | null {
  const id = localStorage.getItem(STORAGE_KEY) as UserProfileId | null;
  return id && PROFILES[id] ? PROFILES[id] : null;
}

export function setProfile(id: UserProfileId): void {
  localStorage.setItem(STORAGE_KEY, id);
}

export function clearProfile(): void {
  localStorage.removeItem(STORAGE_KEY);
}
