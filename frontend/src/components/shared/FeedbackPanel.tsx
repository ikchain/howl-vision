import { useState, useEffect } from "react";
import { MessageCircleQuestion, Check } from "lucide-react";
import { submitFeedback } from "../../lib/feedback";
import { getFeedbackByAnalysisId } from "../../lib/db";
import type { FeedbackRecord } from "../../types";

const LABEL_OPTIONS = [
  { value: "demodicosis", label: "Demodicosis" },
  { value: "Dermatitis", label: "Dermatitis" },
  { value: "Fungal_infections", label: "Fungal infection" },
  { value: "Healthy", label: "Healthy" },
  { value: "Hypersensitivity_Allergic_Dermatitis", label: "Allergic / Hyper." },
  { value: "ringworm", label: "Ringworm" },
  { value: "other", label: "Other condition" },
  { value: "not_skin", label: "Not a skin condition" },
] as const;

interface Props {
  analysisId: string;
  imageFile: File | null;
  originalLabel: string;
  originalConfidence: number;
  predictionQuality: FeedbackRecord["prediction_quality"];
  species: FeedbackRecord["species"];
}

export function FeedbackPanel({
  analysisId,
  imageFile,
  originalLabel,
  originalConfidence,
  predictionQuality,
  species,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [selectedLabel, setSelectedLabel] = useState<string>("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Check if feedback was already submitted for this analysis (spec D11)
  useEffect(() => {
    getFeedbackByAnalysisId(analysisId)
      .then((existing) => {
        if (existing) setSubmitted(true);
      })
      .catch(() => {});
  }, [analysisId]);

  async function handleSubmit() {
    if (!selectedLabel || !imageFile) return;
    setSubmitting(true);
    const ok = await submitFeedback(
      analysisId,
      imageFile,
      selectedLabel,
      notes,
      originalLabel,
      originalConfidence,
      predictionQuality,
      species,
    );
    setSubmitting(false);
    if (ok) {
      setSubmitted(true);
      setExpanded(false);
    }
  }

  if (submitted) {
    return (
      <div className="flex items-center gap-1.5 px-4 py-2 text-[10px] text-teal-text">
        <Check size={12} />
        <span>Feedback sent — thank you!</span>
      </div>
    );
  }

  return (
    <div className="border-t border-ocean-border">
      {!expanded ? (
        <button
          onClick={() => setExpanded(true)}
          className="w-full flex items-center justify-center gap-1.5 px-4 py-2.5 text-xs text-content-muted hover:text-teal-text transition-colors"
        >
          <MessageCircleQuestion size={14} />
          Help improve: What is this?
        </button>
      ) : (
        <div className="px-4 py-3 space-y-3">
          <p className="text-xs font-medium text-content-secondary">
            What do you think this is?
          </p>

          <div className="grid grid-cols-2 gap-x-2 gap-y-0.5">
            {LABEL_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex items-center gap-2 px-2 py-1 rounded-md text-xs cursor-pointer transition-colors ${
                  selectedLabel === opt.value
                    ? "bg-teal/15 text-teal-text"
                    : "text-content-secondary hover:bg-ocean-surface"
                }`}
              >
                <input
                  type="radio"
                  name="feedback-label"
                  value={opt.value}
                  checked={selectedLabel === opt.value}
                  onChange={() => setSelectedLabel(opt.value)}
                  className="sr-only"
                />
                <div
                  className={`w-3 h-3 rounded-full border ${
                    selectedLabel === opt.value
                      ? "border-teal bg-teal"
                      : "border-content-muted"
                  }`}
                />
                {opt.label}
              </label>
            ))}
          </div>

          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional: describe what you see (e.g., wart, wound, abscess)"
            maxLength={500}
            rows={1}
            className="w-full bg-ocean-surface border border-ocean-border rounded-lg px-3 py-2 text-xs text-content-primary placeholder:text-content-muted resize-none focus:border-teal/60 focus:outline-none"
          />

          <div className="flex gap-2">
            <button
              onClick={handleSubmit}
              disabled={!selectedLabel || submitting}
              className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                selectedLabel && !submitting
                  ? "bg-teal/20 text-teal-text hover:bg-teal/30"
                  : "bg-ocean-surface text-content-muted cursor-not-allowed"
              }`}
            >
              {submitting ? "Sending..." : "Submit feedback"}
            </button>
            <button
              onClick={() => setExpanded(false)}
              className="px-3 py-2 rounded-lg text-xs text-content-muted hover:text-content-secondary transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
