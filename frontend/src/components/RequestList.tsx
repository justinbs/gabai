import { Link } from "react-router-dom";

import { FOCUS_LINK } from "./ui";
import { timeAgo } from "../lib/format";
import { citizenStatus } from "../lib/citizenStatus";
import type { RequestSummary } from "../api/types";

// Resident view. Roomier than the staff table because a resident reads two or
// three of these, not fifty, and reads them on a phone.
//
// No confidence scores. Confidence describes an internal routing decision, not
// the resident's request, and there is no action a resident can take on it.
export function RequestList({ items }: { items: RequestSummary[] }) {
  return (
    <ul>
      {items.map((item) => {
        const status = citizenStatus(item);
        return (
          <li key={item.id} className="border-b border-rule py-5">
            <Link
              to={`/requests/${item.id}`}
              aria-label={`Request ${item.reference_number}, ${status}`}
              className={`text-[19px] font-bold text-link underline ${FOCUS_LINK}`}
            >
              {item.reference_number}
            </Link>
            <p className="mt-2 text-[19px] leading-relaxed">
              {item.description}
            </p>
            <p className="mt-2 text-muted">
              {status}
              {item.category && ` · ${item.category.name}`} ·{" "}
              {timeAgo(item.created_at)}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
