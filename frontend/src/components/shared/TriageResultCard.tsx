import { AlertTriangle } from "lucide-react";
import type { TriageResult, TriageCondition } from "../../lib/triage";
import { UrgencyBadge } from "./UrgencyBadge";

interface Props {
  result: TriageResult;
}

const TIER_DOTS: Record<TriageCondition["matchTier"], number> = {
  low: 1,
  medium: 2,
  high: 3,
};

const TIER_COLOR: Record<TriageCondition["matchTier"], string> = {
  low: "bg-gray-500",
  medium: "bg-amber-500",
  high: "bg-teal",
};

const EMPTY_STATE_MESSAGE =
  "No matching conditions found.\nPlease consult a veterinarian if you're concerned.";

/**
 * Visual tier indicator: three small squares, filled left-to-right by tier.
 * Discrete, NOT a continuous progress bar — the matcher is keyword-based and
 * a percentage display would imply calibration that does not exist.
 */
function TierIndicator({ tier }: { tier: TriageCondition["matchTier"] }) {
  const filled = TIER_DOTS[tier];
  const color = TIER_COLOR[tier];
  return (
    <div className="flex items-center gap-0.5" aria-label={`Relevance: ${tier}`}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={`w-1.5 h-3 rounded-sm ${i < filled ? color : "bg-ocean-border"}`}
        />
      ))}
      <span className="ml-1.5 text-[10px] uppercase tracking-wider text-content-muted">
        {tier}
      </span>
    </div>
  );
}

export function TriageResultCard({ result }: Props) {
  // Branch 1: emergency override fired. The matcher and the server are both
  // bypassed by the safety override in triage(). Render a prominent banner
  // with no conditions list — the user must contact a vet immediately.
  if (result.emergency) {
    return (
      <div className="rounded-xl border border-red-500/60 bg-red-950/30 overflow-hidden">
        <div className="flex items-start gap-3 p-4">
          <AlertTriangle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="text-sm font-semibold text-red-200">
                Possible emergency
              </span>
              <UrgencyBadge urgency="emergency" />
            </div>
            <p className="text-sm text-red-100 leading-snug">
              {result.emergency.message}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Branch 2 + 3: normal result (server or offline matcher). Source badge,
  // conditions list (or empty state), recommendation.
  const isOffline = result.source === "cached";
  const borderClass = isOffline ? "border-gray-500/40" : "border-teal/40";

  return (
    <div className={`rounded-xl border ${borderClass} bg-ocean-surface overflow-hidden`}>
      {/* Source badge — kept inline (matches ResultCard pattern, no shared component) */}
      {isOffline ? (
        <>
          <div className="flex items-center gap-1.5 px-4 pt-3 text-content-muted">
            <div className="w-1.5 h-1.5 rounded-full bg-gray-400" />
            <span className="text-[10px] font-medium uppercase tracking-wider">
              Keyword Search — Offline
            </span>
          </div>
          {/* Inline disclaimer — required, NOT a tooltip. Health information
              cannot be hidden behind hover interactions on mobile. */}
          <p className="text-xs text-content-muted px-4 mt-1">
            Based on keyword matching. Not a diagnosis.
          </p>
        </>
      ) : (
        <div className="flex items-center gap-1.5 px-4 pt-3 text-teal-text">
          <div className="w-1.5 h-1.5 rounded-full bg-teal" />
          <span className="text-[10px] font-medium uppercase tracking-wider">
            Clinic Hub
          </span>
        </div>
      )}

      {/* Conditions list (top 3) or empty state */}
      {result.conditions.length > 0 ? (
        <div className="px-4 pt-3 pb-2 space-y-2">
          {result.conditions.map((condition, i) => (
            <div
              key={`${condition.name}-${i}`}
              className="flex items-center justify-between gap-3"
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <span className="text-sm font-medium text-content-primary truncate">
                  {condition.name}
                </span>
                <UrgencyBadge urgency={condition.urgency} />
              </div>
              <TierIndicator tier={condition.matchTier} />
            </div>
          ))}
          {result.conditions.some((c) => c.urgency === "monitor") && (
            <p className="text-[10px] text-yellow-400/90 pt-1">
              If no improvement in 48h, see a vet.
            </p>
          )}
        </div>
      ) : (
        <div className="px-4 pt-3 pb-1">
          {EMPTY_STATE_MESSAGE.split("\n").map((line, i) => (
            <p key={i} className="text-sm text-content-muted">
              {line}
            </p>
          ))}
        </div>
      )}

      {/* Recommendation */}
      {result.recommendation && (
        <div
          className={`border-t ${
            isOffline ? "border-gray-500/20" : "border-teal/30"
          } px-4 py-3 mt-2`}
        >
          <p className="text-sm text-content-secondary leading-snug">
            {result.recommendation}
          </p>
        </div>
      )}
    </div>
  );
}
