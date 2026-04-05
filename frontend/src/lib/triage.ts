import { getServerUrl, checkServerHealth } from "./connection";
import symptomsData from "../data/symptoms.json";
import pharmaData from "../data/pharma.json";

export interface TriageResult {
  conditions: Array<{ name: string; matchScore: number; urgency: string }>;
  recommendation: string;
  source: "server" | "cached";
}

export interface DrugInfo {
  drug: string;
  species: string;
  route: string;
  dose_min: number;
  dose_max: number;
  freq_h: number | null;
  max_days: number | null;
  notes: string;
}

export interface DrugInteraction {
  drug_a: string;
  drug_b: string;
  severity: string;
  effect: string;
  management: string;
}

// --- Server triage ---

async function serverTriage(species: string, symptoms: string): Promise<TriageResult | null> {
  const url = getServerUrl();
  if (!url) return null;

  const healthy = await checkServerHealth(url);
  if (!healthy) return null;

  try {
    const res = await fetch(`${url}/api/v1/triage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ species, symptoms }),
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return {
      conditions: (data.possible_conditions ?? []).map(
        (c: { name: string; probability: number; urgency: string }) => ({
          name: c.name,
          matchScore: c.probability,
          urgency: c.urgency,
        }),
      ),
      recommendation: data.recommendation ?? "",
      source: "server",
    };
  } catch {
    return null;
  }
}

// --- Offline keyword triage ---

const URGENCY_MAP: Record<string, string> = {
  "Digestive Issues": "soon",
  "Mobility Problems": "soon",
  Parasites: "soon",
  "Ear Infections": "monitor",
  "Skin Irritations": "monitor",
};

function offlineTriage(symptoms: string): TriageResult {
  const words = symptoms.toLowerCase().split(/\s+/);

  const scores: Array<{ name: string; matchScore: number; urgency: string }> = [];

  for (const group of symptomsData) {
    let hits = 0;
    for (const record of group.records) {
      const recordWords = record.text.toLowerCase();
      for (const word of words) {
        if (word.length >= 3 && recordWords.includes(word)) {
          hits++;
          break;
        }
      }
    }
    if (hits > 0) {
      scores.push({
        name: group.condition,
        matchScore: Math.min(hits / group.records.length, 1),
        urgency: URGENCY_MAP[group.condition] ?? "monitor",
      });
    }
  }

  scores.sort((a, b) => b.matchScore - a.matchScore);

  const top = scores[0];
  const recommendation = top
    ? `Based on symptom keywords, this may be related to ${top.name.toLowerCase()}. Please consult a veterinarian for proper diagnosis.`
    : "Could not match symptoms to known conditions. Please consult a veterinarian.";

  return {
    conditions: scores.slice(0, 3),
    recommendation,
    source: "cached",
  };
}

// --- Public API ---

export async function triage(species: string, symptoms: string): Promise<TriageResult> {
  const serverResult = await serverTriage(species, symptoms);
  if (serverResult) return serverResult;
  return offlineTriage(symptoms);
}

export function lookupDrug(drugName: string, species?: string): DrugInfo[] {
  const needle = drugName.toLowerCase();
  return pharmaData.drugs.filter(
    (d) =>
      d.drug.toLowerCase().includes(needle) &&
      (!species || d.species === species),
  ) as DrugInfo[];
}

export function checkInteractions(drugNames: string[]): DrugInteraction[] {
  const lower = drugNames.map((d) => d.toLowerCase());
  return pharmaData.interactions.filter(
    (i) =>
      lower.some((d) => i.drug_a.includes(d) || d.includes(i.drug_a)) &&
      lower.some((d) => i.drug_b.includes(d) || d.includes(i.drug_b)),
  ) as DrugInteraction[];
}
