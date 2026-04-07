import { openDB, type IDBPDatabase } from "idb";
import type { AnalysisRecord, AnalyzeResponse } from "../types";

const DB_NAME = "howl-vision";
const DB_VERSION = 1;
const STORE_NAME = "analyses";

async function getDb(): Promise<IDBPDatabase> {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: "id" });
        store.createIndex("timestamp", "timestamp");
        store.createIndex("species", "species");
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
  const record: AnalysisRecord = {
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

export async function getAnalyses(species?: string): Promise<AnalysisRecord[]> {
  const db = await getDb();
  const all = await db.getAllFromIndex(STORE_NAME, "timestamp");
  const sorted = all.reverse();
  if (species) return sorted.filter((r) => r.species === species);
  return sorted;
}

export async function getAnalysis(id: string): Promise<AnalysisRecord | undefined> {
  const db = await getDb();
  return db.get(STORE_NAME, id);
}
