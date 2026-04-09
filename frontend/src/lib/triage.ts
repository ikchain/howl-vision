import { getServerUrl, checkServerHealth } from "./connection";
import symptomsData from "../data/symptoms.json";
import pharmaData from "../data/pharma.json";

// ─────────────────────────────────────────────────────────────────────────────
// Public type contracts for triage functionality
// ─────────────────────────────────────────────────────────────────────────────

export interface TriageCondition {
  name: string;
  /** Raw ratio in [0, 1]. Kept for debugging and history. */
  matchScore: number;
  /** Discrete display tier. Derived from matchScore via matchScoreToTier(). */
  matchTier: "low" | "medium" | "high";
  /** Per-condition urgency for the matcher path. Top-level emergency overrides this. */
  urgency: "soon" | "monitor";
}

/**
 * Why no `triggered: boolean`: the presence of the object IS the trigger.
 * If the override did not fire, the field on TriageResult is `null`.
 * `triggered: false` alongside a present object would be a useless wrapper.
 */
export type EmergencyOverride = { message: string };

export interface TriageResult {
  /** Top-N matching conditions. Empty if emergency fired or no matches. */
  conditions: TriageCondition[];
  recommendation: string;
  source: "server" | "cached";
  /**
   * Set when the emergency keyword override fires in `triage()`.
   * When non-null, `conditions` is `[]` and the UI must render an emergency banner.
   */
  emergency: EmergencyOverride | null;
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

// ─────────────────────────────────────────────────────────────────────────────
// SAFETY: Emergency keyword override (§6.1)
// ─────────────────────────────────────────────────────────────────────────────
//
// Veterinary emergencies that override the matcher and the server result.
// If any of these substrings appear in the user input, urgency is forced
// to "emergency" regardless of what serverTriage or offlineTriage would
// return.
//
// Why this exists: the keyword matcher cannot recognize toxic ingestion or
// acute neurological symptoms — it only counts hits against records. A user
// typing "my dog ate chocolate" must not get back "Ear Infections, monitor".
// This pattern mirrors URGENCY_EMERGENCY in analyze.ts (line 19) for the
// image analysis path.
//
// List validated by ml-eval-rigor against veterinary toxicology references.
// Substring matching (not whole-word) so "convulsing" matches "convulsion"
// → "convuls" stem, etc. False positives are acceptable here — erring on
// the side of "go to vet" is never harmful; the opposite is.
//
// CRITICAL: this list MUST include "permethrin" — a canine flea topical
// applied by mistake to a cat is fatal in 2-4h. ml-eval-rigor caught this
// gap in the original list.

const EMERGENCY_KEYWORDS: ReadonlySet<string> = new Set([
  // Toxic ingestion — confirmed high-risk (4-6h windows)
  "chocolate", "xylitol", "grape", "grapes", "raisin", "raisins",
  "onion", "onions", "garlic", "leek",
  "ibuprofen", "acetaminophen", "paracetamol", "aspirin",
  "metaldehyde", "rat poison", "rodenticide",
  "antifreeze", "ethylene glycol",
  "permethrin",
  "lilies", "lily",
  "sago palm",
  "macadamia",
  "avocado",
  "alcohol", "ethanol",

  // Acute neurological / cardiopulmonary
  "seizure", "seizures", "convulsion", "convulsions", "convulsing",
  "unconscious", "unresponsive",
  "collapse", "collapsed",
  "can't breathe", "cannot breathe", "difficulty breathing",
  "gasping",
  "blue gums", "pale gums", "white gums",

  // GDV / acute abdomen
  "bloat", "bloated", "torsion", "twisted stomach",
  "distended abdomen", "swollen belly",

  // Acute hemorrhage
  "bleeding", "hemorrhage",
  "blood in urine", "blood in stool",
  "vomiting blood", "bloody vomit", "coughing blood",

  // Trauma / shock
  "hit by car", "run over", "crushed",
  "broken bone", "open fracture",
  "shock",

  // Thermal / environmental
  "heatstroke", "heat stroke", "overheating",
  "hypothermia", "frozen",
  "electrocution", "electric shock",

  // Urinary obstruction (feline emergency, 24-48h window)
  "can't urinate", "cannot urinate", "not urinating",
  "straining to urinate", "blocked bladder",

  // Dystocia
  "stuck puppy", "stuck kitten", "can't give birth",
  "labor stopped", "dystocia",

  // Anaphylaxis
  "bee sting", "allergic reaction", "anaphylaxis",
  "swollen face", "swollen throat",
]);

const EMERGENCY_MESSAGE =
  "Possible poisoning or emergency. Contact a veterinarian immediately.";

function checkEmergencyKeywords(symptomsLower: string): boolean {
  for (const keyword of EMERGENCY_KEYWORDS) {
    if (symptomsLower.includes(keyword)) return true;
  }
  return false;
}

// ─────────────────────────────────────────────────────────────────────────────
// SAFETY: Stopword filter (§6.2)
// ─────────────────────────────────────────────────────────────────────────────
//
// Tokens with no clinical discriminative power. Filtered out before matching
// to prevent base-rate contamination across condition groups.
//
// Why "dog" and "cat" are stopwords: the records are not segmented by species,
// so the species token matches ~50% of every group equally, drowning the
// signal of meaningful symptom keywords.
//
// Why "rabbit" is in the list: empirically appears 27 times across condition
// groups (the corpus has rabbit-specific records mixed in), same problem as
// "dog" and "cat".
//
// Why "and" is in the list: empirically the #1 contaminating token. Matches
// 54/104 ear-infection records purely as a conjunction. Without filtering it,
// "my dog ate chocolate and is vomiting" returns Ear Infections as top match.
//
// The "clinical SOAP boilerplate" group is corpus-validated by ml-eval-rigor:
// tokens that appear frequently in the records but carry no diagnostic
// meaning. They are part of the clinical documentation style, not content.

const CLINICAL_STOPWORDS: ReadonlySet<string> = new Set([
  // Species / demographics (match uniformly across groups)
  "dog", "dogs", "cat", "cats", "puppy", "kitten", "kittens", "puppies",
  "pet", "pets", "animal", "animals",
  "rabbit", "rabbits",

  // English function words ≥3 chars that pass the length filter
  "the", "and", "but", "for", "with", "from", "into", "onto",
  "are", "was", "were", "has", "have", "had",
  "his", "her", "him", "she", "its", "out",
  "this", "that", "these", "those",
  "does", "did", "doing", "been", "being",
  "they", "them", "their",
  "myself", "yourself",
  "when", "also", "then", "than",

  // Clinical SOAP boilerplate (corpus-validated, no diagnostic value)
  "seems", "noted", "condition", "suspected", "consider",
  "recommend", "rule", "back",
  "chronic", "test", "like",
  "patient", "owner", "history",
  "please", "consult",
]);

function tokenize(input: string): string[] {
  return input
    .toLowerCase()
    .split(/\s+/)
    .map((w) => w.replace(/[^a-z']/g, ""))
    .filter((w) => w.length >= 3 && !CLINICAL_STOPWORDS.has(w));
}

// ─────────────────────────────────────────────────────────────────────────────
// Score tier thresholds (§6.4)
// ─────────────────────────────────────────────────────────────────────────────
//
// Empirically derived from real corpus data. The same function is used by
// both offlineTriage (matchScore = hits/total ratio) and serverTriage
// (matchScore = LLM probability). LLM probabilities tend to cluster higher
// than keyword matcher ratios, so server results will skew toward "high" —
// that is intentional and honest: when the LLM is confident, the tier
// reflects it.

function matchScoreToTier(matchScore: number): "low" | "medium" | "high" {
  if (matchScore >= 0.2) return "high";
  if (matchScore >= 0.08) return "medium";
  return "low";
}

// ─────────────────────────────────────────────────────────────────────────────
// Per-condition urgency mapping (offline path only)
// ─────────────────────────────────────────────────────────────────────────────

const URGENCY_MAP: Record<string, "soon" | "monitor"> = {
  "Digestive Issues": "soon",
  "Mobility Problems": "soon",
  Parasites: "soon",
  "Ear Infections": "monitor",
  "Skin Irritations": "monitor",
};

function normalizeUrgency(urgency: string): "soon" | "monitor" {
  if (urgency === "soon") return "soon";
  return "monitor";
}

// ─────────────────────────────────────────────────────────────────────────────
// Server triage (Gemma 4 via /api/v1/triage)
// ─────────────────────────────────────────────────────────────────────────────

const SERVER_TRIAGE_TIMEOUT_MS = 10000;

async function serverTriage(
  species: string,
  symptoms: string,
): Promise<TriageResult | null> {
  const url = getServerUrl();
  if (!url) return null;

  const healthy = await checkServerHealth(url);
  if (!healthy) return null;

  try {
    const res = await fetch(`${url}/api/v1/triage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ species, symptoms }),
      signal: AbortSignal.timeout(SERVER_TRIAGE_TIMEOUT_MS),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const conditions: TriageCondition[] = (data.possible_conditions ?? []).map(
      (c: { name: string; probability: number; urgency: string }) => ({
        name: c.name,
        matchScore: c.probability,
        matchTier: matchScoreToTier(c.probability),
        urgency: normalizeUrgency(c.urgency),
      }),
    );
    return {
      conditions,
      recommendation: data.recommendation ?? "",
      source: "server",
      emergency: null,
    };
  } catch {
    return null;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Offline triage (keyword matcher with stopword filter)
// ─────────────────────────────────────────────────────────────────────────────

function offlineTriage(species: string, symptoms: string): TriageResult {
  const tokens = tokenize(symptoms);

  const scores: TriageCondition[] = [];

  for (const group of symptomsData) {
    let hits = 0;
    for (const record of group.records) {
      const recordText = record.text.toLowerCase();
      for (const token of tokens) {
        if (recordText.includes(token)) {
          hits++;
          break;
        }
      }
    }
    if (hits > 0) {
      const matchScore = hits / group.records.length;
      scores.push({
        name: group.condition,
        matchScore,
        matchTier: matchScoreToTier(matchScore),
        urgency: URGENCY_MAP[group.condition] ?? "monitor",
      });
    }
  }

  scores.sort((a, b) => b.matchScore - a.matchScore);

  const top = scores[0];
  const speciesLabel = species === "feline" ? "cat" : "dog";
  const recommendation = top
    ? `Based on symptom keywords for your ${speciesLabel}, this may be related to ${top.name.toLowerCase()}. Please consult a veterinarian for proper diagnosis.`
    : `Could not match symptoms to known conditions for ${speciesLabel}s. Please consult a veterinarian.`;

  return {
    conditions: scores.slice(0, 3),
    recommendation,
    source: "cached",
    emergency: null,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Public entry point
// ─────────────────────────────────────────────────────────────────────────────
//
// SAFETY CONTRACT: the emergency keyword override is a precondition of
// triage()'s public contract. It runs before deciding between server and
// offline, before any network call. If it fires, neither serverTriage nor
// offlineTriage is called — the function returns immediately with an
// EmergencyOverride.
//
// The override applies EVEN if the server would otherwise respond with a
// non-emergency urgency. This is the client-side last firewall.

export async function triage(
  species: string,
  symptoms: string,
): Promise<TriageResult> {
  // Named variable, not inline. A future refactor that passes the original
  // string instead of the lowercase one must not silently break the override.
  const lower = symptoms.toLowerCase();

  if (checkEmergencyKeywords(lower)) {
    return {
      conditions: [],
      recommendation: EMERGENCY_MESSAGE,
      source: "cached",
      emergency: { message: EMERGENCY_MESSAGE },
    };
  }

  const serverResult = await serverTriage(species, symptoms);
  if (serverResult) return serverResult;
  return offlineTriage(species, symptoms);
}

// ─────────────────────────────────────────────────────────────────────────────
// Pharma lookups (unchanged, currently unused by the UI but kept for the
// future ticket that wires them up — see §11 of the spec)
// ─────────────────────────────────────────────────────────────────────────────

const SPECIES_TO_PHARMA: Record<string, string> = { canine: "dog", feline: "cat" };

export function lookupDrug(drugName: string, species?: string): DrugInfo[] {
  const needle = drugName.toLowerCase();
  const pharmaSpecies = species ? SPECIES_TO_PHARMA[species] ?? species : undefined;
  return pharmaData.drugs.filter(
    (d) =>
      d.drug.toLowerCase().includes(needle) &&
      (!pharmaSpecies || d.species === pharmaSpecies),
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
