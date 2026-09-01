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
                </td>
                <td className="py-3 pr-4 align-top">
                  <span className="line-clamp-2">{item.description}</span>
                </td>
                <td className="py-3 pr-4 align-top text-muted">
                  {item.category?.name ?? "Not yet sorted"}
                </td>
                <td className="py-3 pr-4 align-top">
                  <UrgencyBadge urgency={item.urgency} />
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
