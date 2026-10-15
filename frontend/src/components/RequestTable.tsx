import { Link } from "react-router-dom";

import { UrgencyBadge } from "./badges";
import { FOCUS_LINK } from "./ui";
import { timeAgo } from "../lib/format";
import { REVIEW_THRESHOLD, STAFF_STATUS_LABELS, URGENCY_LABELS } from "../api/types";
import type { RequestSummary } from "../api/types";

// Staff view. A table because the job is scanning for the one thing that needs
// attention, and cards make that slower.

// The routing gate is the lower of the two heads, so that is the number shown.
// One head alone does not tell an operator whether the request routed.
// Same list as OPEN in backend/app/queue_order.py.
const OPEN: RequestSummary["status"][] = ["submitted", "under_review", "routed", "in_progress"];

const hoursSince = (iso: string) => Math.floor((Date.now() - new Date(iso).getTime()) / 3_600_000);

const lowest = (r: RequestSummary) =>
  r.category_confidence === null || r.urgency_confidence === null
    ? null
    : Math.min(r.category_confidence, r.urgency_confidence);

export function RequestTable({
  items,
  caption,
}: {
  items: RequestSummary[];
  caption: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b-2 border-ink">
            <th scope="col" className="w-px whitespace-nowrap py-2 pr-4 font-bold">
              Reference
            </th>
            <th scope="col" className="w-1/2 py-2 pr-4 font-bold">Concern</th>
            <th scope="col" className="py-2 pr-4 font-bold">Category</th>
            <th scope="col" className="py-2 pr-4 font-bold">Urgency</th>
            <th scope="col" className="whitespace-nowrap py-2 pr-4 text-right font-bold">
              Lowest score
            </th>
            <th scope="col" className="w-px whitespace-nowrap py-2 text-right font-bold">
              Age
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const score = lowest(item);
            return (
              <tr key={item.id} className="border-b border-rule">
                <td className="whitespace-nowrap py-3 pr-4 align-top">
                  <Link
                    to={`/requests/${item.id}`}
                    aria-label={`Request ${item.reference_number}, ${
                      STAFF_STATUS_LABELS[item.status]
                    }${item.urgency ? `, ${URGENCY_LABELS[item.urgency]} urgency` : ""}`}
                    className={`font-bold text-link underline tabular-nums ${FOCUS_LINK}`}
                  >
                    {item.reference_number}
                  </Link>
                  <span className="block text-[15px] text-muted">
                    {STAFF_STATUS_LABELS[item.status]}
                  </span>
                  {item.linked_count > 0 && (
                    <span className="block text-[15px] font-bold">
                      {item.linked_count + 1} reports
                    </span>
                  )}
                </td>
                <td className="py-3 pr-4 align-top">
                  {item.location && <span className="block text-[15px] font-bold">{item.location.name}</span>}
                  <span className="line-clamp-2">{item.description}</span>
                </td>
                <td className="py-3 pr-4 align-top text-muted">
                  {item.category?.name ?? "Not yet sorted"}
                </td>
                <td className="py-3 pr-4 align-top">
                  <UrgencyBadge urgency={item.urgency} />
                  {item.urgent_flagged_at && OPEN.includes(item.status) && (
                    <span className="mt-1 block text-[15px] font-bold text-danger">
                      Marked urgent by resident
                    </span>
                  )}
                  {item.aged && (
                    <span className="mt-1 block text-[15px] font-bold text-warn">
                      Waiting {hoursSince(item.waiting_since)}h
                    </span>
                  )}
                </td>
                <td
                  className={`py-3 pr-4 text-right align-top tabular-nums ${
                    score !== null && score < REVIEW_THRESHOLD ? "font-bold text-warn" : "text-muted"
                  }`}
                >
                  {score === null ? "-" : `${Math.round(score * 100)}%`}
                </td>
                <td className="whitespace-nowrap py-3 text-right align-top tabular-nums text-muted">
                  {timeAgo(item.created_at)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
