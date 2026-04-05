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
  urgency: "emergency" | "soon" | "monitor" | "healthy";
  rag_matches: Array<{ case_id: string; similarity: number; summary: string }>;
  pharma: Array<{ drug: string; dosage: string; warnings: string }>;
  source: string;
}

// -- History --

export interface AnalysisRecord {
  id: string;
  timestamp: number;
  species: "canine" | "feline";
  module: "dermatology" | "parasites";
  thumbnailDataUrl: string;
  classification: string;
  confidence: number;
  urgency: "emergency" | "soon" | "monitor" | "healthy";
  narrativeSummary: string;
  fullResult?: AnalyzeResponse;
}
