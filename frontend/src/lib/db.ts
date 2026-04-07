import { openDB, type IDBPDatabase } from "idb";
import type {
  AnalyzeResponse,
  HistoryRecord,
  ImageAnalysisRecord,
  TriageRecord,
} from "../types";
import { TRIAGE_SUMMARY_MAX_LEN } from "../types";
import type { TriageResult } from "./triage";

const DB_NAME = "howl-vision";
const DB_VERSION = 2;

// "analyses" is the historical name from v1 when this store only held image
// analyses. As of  it holds a discriminated union (HistoryRecord) of
// ImageAnalysisRecord and TriageRecord. The store name is preserved for
// backwards compatibility with v1 users — renaming would force a destructive
// migration. Do not let the name mislead you: this is the history store, not
// the image-analyses store.
const STORE_NAME = "analyses";

async function getDb(): Promise<IDBPDatabase> {
  return openDB(DB_NAME, DB_VERSION, {
    /**
     * Migration v1 → v2 :
     *
     * v1 records have no `kind` field — they are all image analyses by
     * definition. v2 records carry `kind: "image" | "triage"` to support
     * the discriminated union HistoryRecord.
     *
     * IMPORTANT: this callback receives the active versionchange transaction
     * as its 4th parameter. We MUST use it directly via
     * `transaction.objectStore(STORE_NAME)` — calling `db.transaction()`
     * inside the upgrade throws InvalidStateError because a versionchange
     * transaction is already active.
     *
     * The migration uses `oldVersion` explicitly (not field inference): if a
     * record is coming from v1, we know with certainty it is an image
     * analysis. We never guess based on which fields are present.
     */
    async upgrade(db, oldVersion, _newVersion, transaction) {
      if (oldVersion < 1) {
        // First-time install: create the store and indices.
        const store = db.createObjectStore(STORE_NAME, { keyPath: "id" });
        store.createIndex("timestamp", "timestamp");
        store.createIndex("species", "species");
      }

      if (oldVersion < 2) {
        // v1 → v2: backfill kind:"image" on every existing record.
        // Use the transaction parameter, never db.transaction() inside upgrade.
        const store = transaction.objectStore(STORE_NAME);
        let cursor = await store.openCursor();
        while (cursor) {
          const record = cursor.value as Record<string, unknown>;
          if (!("kind" in record)) {
            record.kind = "image";
            await cursor.update(record);
          }
          cursor = await cursor.continue();
        }
      }
    },
  });
}

async function createThumbnail(file: File): Promise<string> {
  const img = await createImageBitmap(file);
  const scale = 200 / img.width;
  const canvas = new OffscreenCanvas(200, Math.round(img.height * scale));
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  const blob = await canvas.convertToBlob({ type: "image/jpeg", quality: 0.7 });
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.readAsDataURL(blob);
  });
}

export async function saveAnalysis(
  file: File,
  result: AnalyzeResponse,
  species: "canine" | "feline",
  module: "dermatology" | "parasites",
): Promise<void> {
  const db = await getDb();
  const thumbnail = await createThumbnail(file);
  const record: ImageAnalysisRecord = {
    kind: "image",
    id: result.analysis_id,
    timestamp: Date.now(),
    species,
    module,
    thumbnailDataUrl: thumbnail,
    classification: result.classification.label,
    confidence: result.classification.confidence,
    urgency: result.urgency,
    narrativeSummary: result.narrative.slice(0, 200),
    fullResult: result,
  };
  await db.put(STORE_NAME, record);
}

/**
 * Persist a triage result. Separate from saveAnalysis() because triage
 * records have no File (no thumbnail) and a different schema. The two
 * persist functions converge on the same store but build different shapes.
 */
export async function saveTriage(
  species: "canine" | "feline",
  symptomsText: string,
  result: TriageResult,
): Promise<void> {
  const db = await getDb();
  const top = result.conditions[0];
  // urgency hierarchy: emergency override beats per-condition urgency.
  // If neither set anything, default to "unknown" (matcher returned no hits).
  const urgency: TriageRecord["urgency"] = result.emergency
    ? "emergency"
    : top
      ? top.urgency
      : "unknown";
  const record: TriageRecord = {
    kind: "triage",
    id: crypto.randomUUID(),
    timestamp: Date.now(),
    species,
    symptomsText,
    topCondition: top ? top.name : null,
    urgency,
    recommendationSummary: result.recommendation.slice(0, TRIAGE_SUMMARY_MAX_LEN),
    fullResult: result,
  };
  await db.put(STORE_NAME, record);
}

export async function getAnalyses(species?: string): Promise<HistoryRecord[]> {
  const db = await getDb();
  const all = (await db.getAllFromIndex(STORE_NAME, "timestamp")) as HistoryRecord[];
  const sorted = all.reverse();
  if (species) return sorted.filter((r) => r.species === species);
  return sorted;
}

export async function getAnalysis(id: string): Promise<HistoryRecord | undefined> {
  const db = await getDb();
  return (await db.get(STORE_NAME, id)) as HistoryRecord | undefined;
}
