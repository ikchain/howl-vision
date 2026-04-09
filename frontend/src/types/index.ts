// -- SSE Events from POST /api/v1/chat --

export interface SSEToolStatusEvent {
  type: "tool_status";
  tool: string;
  status: "running" | "done";
}

export interface SSETokenEvent {
  type: "token";
  content: string;
}

export interface SSEDoneEvent {
  type: "done";
}

export interface SSEErrorEvent {
  type: "error";
  message: string;
  code: string;
}

export type SSEEvent =
  | SSEToolStatusEvent
  | SSETokenEvent
  | SSEDoneEvent
  | SSEErrorEvent;

// -- Chat --

export type MessageRole = "user" | "assistant";

export type ChatStatus =
  | "idle"
  | "waiting"
  | "streaming"
  | "done"
  | "error";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  imagePreviewUrl?: string;
  timestamp: Date;
}

export interface ActiveTool {
  name: string;
  status: "running" | "done";
}

// -- API --

export interface ChatRequest {
  message: string;
  image_b64?: string;
  history: never[]; // Always empty until multi-turn is implemented
}

// -- Cases --

export interface CaseResult {
  id: string;
  text: string;
  score: number;
  source: string;
  record_type: string;
}

export interface CasesSearchResponse {
  results: CaseResult[];
  count: number;
}

// -- Analyze --

export interface Classification {
  label: string;
  confidence: number;
  differentials: Array<{ label: string; confidence: number }>;
}

export interface AnalyzeResponse {
  analysis_id: string;
  classification: Classification;
  narrative: string;
  urgency: "emergency" | "soon" | "monitor" | "healthy" | "unknown";
  rag_matches: Array<{ case_id: string; similarity: number; summary: string }>;
  pharma: Array<{ drug: string; dosage: string; warnings: string }>;
  source: string;
  /** Present when source is "local_ai" and the server was attempted but failed. */
  fallback_reason?: string;
  prediction_quality: "confident" | "low_confidence" | "inconclusive";
  entropy: number;
}

// -- History --
//
// HistoryRecord is a discriminated union over `kind`. Image analyses
// and triage records live in the same IndexedDB store but render and
// persist differently.
//
// Why discriminated union and not optional fields: optional fields defer
// validity to runtime and force consumers to repeatedly check for presence.
// The union gives compile-time exhaustiveness checking via switch (record.kind).

import type { TriageResult } from "../lib/triage";

export interface ImageAnalysisRecord {
  kind: "image";
  id: string;
  timestamp: number;
  species: "canine" | "feline";
  module: "dermatology" | "parasites";
  thumbnailDataUrl: string;
  classification: string;
  confidence: number;
  urgency: "emergency" | "soon" | "monitor" | "healthy" | "unknown";
  narrativeSummary: string;
  fullResult?: AnalyzeResponse;
}

export interface TriageRecord {
  kind: "triage";
  id: string;
  timestamp: number;
  species: "canine" | "feline";
  /** What the user typed in the symptoms textarea. */
  symptomsText: string;
  /** First condition's name. null if emergency override fired (conditions empty). */
  topCondition: string | null;
  urgency: "emergency" | "soon" | "monitor" | "healthy" | "unknown";
  /** First TRIAGE_SUMMARY_MAX_LEN chars of recommendation. */
  recommendationSummary: string;
  /**
   * Full result, REQUIRED. Used by History detail view to re-render the
   * TriageResultCard with the original data. Unlike ImageAnalysisRecord
   * (where fullResult is optional for backwards compat), triage records
   * start fresh and require it.
   */
  fullResult: TriageResult;
}

export type HistoryRecord = ImageAnalysisRecord | TriageRecord;

/**
 * Maximum length of the truncated recommendation stored in TriageRecord.
 * Shared between db.ts (truncation on save) and any consumer that wants
 * to predict the truncation behavior. No magic number 200 in two places.
 */
export const TRIAGE_SUMMARY_MAX_LEN = 200;


// -- PWA --

export interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}
