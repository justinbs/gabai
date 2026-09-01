import { percent } from "../lib/format";
import { REVIEW_THRESHOLD, URGENCY_LABELS } from "../api/types";
import type { RequestStatus, Urgency } from "../api/types";

// Colour is never the only signal. Every badge carries its own text, because
// contrast and colour-blind legibility are evaluated requirements.

const URGENCY_TEXT: Record<Urgency, string> = {
  high: "text-danger",
  medium: "text-warn",
  low: "text-muted",
};

// Only urgency and the review state get colour. Everything else is ink on white,
// so the two things worth spotting in a queue are the two things that stand out.
const STATUS_TEXT: Record<RequestStatus, string> = {
  submitted: "text-muted",
  classified: "text-muted",
  routed: "text-ink",
  under_review: "text-warn",
  in_progress: "text-ink",
  resolved: "text-ink",
  closed: "text-muted",
};

export function UrgencyBadge({ urgency }: { urgency: Urgency | null }) {
  if (!urgency) return <span className="text-muted">Not set</span>;
  return (
    <span className={`font-bold uppercase ${URGENCY_TEXT[urgency]}`}>
      {URGENCY_LABELS[urgency]}
    </span>
  );
}

export function StatusBadge({
  status,
  label,
}: {
  status: RequestStatus;
  label: string;
}) {
  return <span className={`font-bold ${STATUS_TEXT[status]}`}>{label}</span>;
}

// Shows the classifier's certainty rather than hiding it. Making the score
// visible is what lets an operator judge a prediction instead of trusting it.
export function Confidence({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  if (value === null) {
    return <div className="text-muted">{label}: not yet classified</div>;
  }

  const low = value < REVIEW_THRESHOLD;
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-muted">{label}</span>
      <span className={`font-bold tabular-nums ${low ? "text-warn" : ""}`}>
        {percent(value)}
        {low && " · below threshold"}
      </span>
    </div>
  );
}
