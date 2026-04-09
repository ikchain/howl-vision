/**
 * Active learning feedback — submit + offline sync (spec D4, D11, D12).
 *
 * Offline-first: saves to IndexedDB immediately, POSTs to server when
 * connected. Pending feedback is retried sequentially on app startup.
 */

import { getEffectiveServerUrl } from "./connection";
import {
  saveFeedback,
  getPendingFeedback,
  markFeedbackSynced,
} from "./db";
import type { FeedbackRecord } from "../types";

/**
 * Submit feedback for one analysis result.
 * Always saves to IndexedDB. Attempts server POST if online.
 * Returns true if the local save succeeded (the user should see "thank you"
 * regardless of server availability — spec AC5).
 */
export async function submitFeedback(
  analysisId: string,
  imageFile: File,
  userLabel: string,
  notes: string,
  originalLabel: string,
  originalConfidence: number,
  predictionQuality: FeedbackRecord["prediction_quality"],
  species: FeedbackRecord["species"],
): Promise<boolean> {
  const record: FeedbackRecord = {
    id: crypto.randomUUID(),
    analysis_id: analysisId,
    image_blob: imageFile,
    user_label: userLabel,
    notes,
    original_label: originalLabel,
    original_confidence: originalConfidence,
    prediction_quality: predictionQuality,
    species,
    timestamp: Date.now(),
    synced: false,
  };

  try {
    await saveFeedback(record);
  } catch (err) {
    console.error("[feedback] IndexedDB save failed:", err);
    return false;
  }

  // Attempt server sync (non-blocking for the user)
  await syncOneRecord(record).catch(() => {
    // Offline or server error — will retry on next startup
  });

  return true;
}

async function syncOneRecord(record: FeedbackRecord): Promise<void> {
  const serverUrl = getEffectiveServerUrl();
  if (!serverUrl) return;

  const form = new FormData();
  form.append("image", record.image_blob, `${record.analysis_id}.jpg`);
  form.append(
    "metadata",
    JSON.stringify({
      id: record.id,
      analysis_id: record.analysis_id,
      user_label: record.user_label,
      notes: record.notes,
      original_label: record.original_label,
      original_confidence: record.original_confidence,
      prediction_quality: record.prediction_quality,
      species: record.species,
      timestamp: record.timestamp,
    }),
  );

  const res = await fetch(`${serverUrl}/api/v1/feedback`, {
    method: "POST",
    body: form,
    signal: AbortSignal.timeout(30000),
  });

  // 200 = saved, 409 = duplicate (already synced in a previous partial attempt)
  // Both mean the server has it — mark as synced (spec D12).
  if (res.ok || res.status === 409) {
    await markFeedbackSynced(record.id);
  } else {
    throw new Error(`Server returned ${res.status}`);
  }
}

/**
 * Retry pending feedback on app startup (spec D4).
 * Processes sequentially to avoid saturating rural connections.
 */
export async function syncPendingFeedback(): Promise<void> {
  let pending: FeedbackRecord[];
  try {
    pending = await getPendingFeedback();
  } catch {
    return; // DB not ready or empty — nothing to sync
  }

  for (const record of pending) {
    try {
      await syncOneRecord(record);
    } catch {
      // Stop on first failure — likely offline, no point retrying the rest
      break;
    }
  }
}
