import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import * as api from "../api/client";
import { Confidence, StatusBadge, UrgencyBadge } from "../components/badges";
import {
  Button,
  ErrorState,
  FOCUS_LINK,
  Loading,
  Select,
  Textarea,
} from "../components/ui";
import { fullDate, timeAgo } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { usePageTitle } from "../lib/usePageTitle";
import { useUser } from "../session-context";
import { citizenStatus, citizenStatusNote } from "../lib/citizenStatus";
import { STAFF_STATUS_LABELS, URGENCY_LABELS } from "../api/types";
import { ApiError } from "../api/http";
import type {
  Agency,
  Category,
  DuplicateSuggestion,
  RequestStatus,
  ServiceRequest,
  Urgency,
  User,
} from "../api/types";

export function RequestDetail() {
  usePageTitle("Request");
  const user = useUser();
  const { id } = useParams();
  const requestId = Number(id);

  const { state, reload } = useAsync(
    () => api.getRequest(user, requestId),
    [user.id, requestId],
  );

  if (state.status === "loading") return <Loading label="Loading" />;
  if (state.status === "error")
    return <ErrorState description={state.message} onRetry={reload} />;

  if (!state.data) {
    return (
      <ErrorState
        title="Request not found"
        description="It doesn't exist, or it isn't yours to see"
      />
    );
  }

  return (
    <Detail
      key={requestId}
      request={state.data}
      user={user}
      onChanged={reload}
    />
  );
}

function Detail({
  request,
  user,
  onChanged,
}: {
  request: ServiceRequest;
  user: User;
  onChanged: () => void;
}) {
  const isStaff = user.role === "staff" || user.role === "admin";

  return (
    <>
      <Link
        to={user.role === "citizen" ? "/requests" : "/queue"}
        className={`mb-4 inline-block text-link underline ${FOCUS_LINK}`}
      >
        Back
      </Link>

      <div className="mb-6 flex flex-wrap items-center gap-3 border-t-2 border-ink pt-5">
        <h1 className="font-mono text-[32px] font-bold text-ink">
          {request.reference_number}
        </h1>
        <StatusBadge
          status={request.status}
          label={
            isStaff ? STAFF_STATUS_LABELS[request.status] : citizenStatus(request)
          }
        />
        {isStaff && <UrgencyBadge urgency={request.urgency} />}
      </div>

      {!isStaff && <ResidentUpdate request={request} />}
      {!isStaff && <ReferralBox request={request} />}
      {!isStaff && <UrgentFlag request={request} onChanged={onChanged} />}
      {!isStaff && request.duplicate_of && (
        <p className="mb-5 border-l-4 border-rule py-1 pl-4">
          Others reported the same problem. Your report follows {request.duplicate_of.reference_number}, and you get its updates.
          <span className="block text-muted">May iba pang nag-report ng parehong problema. Sinusundan ng inyong report ang {request.duplicate_of.reference_number}.</span>
        </p>
      )}
      {isStaff && request.urgent_flagged_at && OPEN_STATUSES.includes(request.status) && (
        <div role="note" className="mb-5 border-l-4 border-danger py-1 pl-4">
          <p className="font-bold">
            Marked urgent by the resident {timeAgo(request.urgent_flagged_at)}
          </p>
          {request.urgent_reason && <p className="mt-1">{request.urgent_reason}</p>}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <section className="border-t-2 border-ink pt-5">
            <h2 className="text-[24px] font-bold">
              Concern
            </h2>
            <p className="mt-2 whitespace-pre-wrap text-lg text-ink">
              {request.description}
            </p>
            <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 border-t border-rule pt-4 text-sm">
              <div>
                <dt className="text-muted">Submitted</dt>
                <dd className="text-ink">{fullDate(request.created_at)}</dd>
              </div>
              <div>
                <dt className="text-muted">Category</dt>
                <dd className="text-ink">
                  {request.category?.name ?? "Not yet assigned"}
                </dd>
              </div>
              {isStaff && (
                <div>
                  <dt className="text-muted">Submitted by</dt>
                  <dd className="text-ink">{request.citizen.full_name}</dd>
                </div>
              )}
              {isStaff && request.assigned_staff && (
                <div>
                  <dt className="text-muted">Handled by</dt>
                  <dd className="text-ink">
                    {request.assigned_staff.full_name}
                  </dd>
                </div>
              )}
            </dl>

            {request.attachments.length > 0 && (
              <div className="mt-4 border-t border-rule pt-4">
                <h3 className="font-bold">Photos</h3>
                <ul className="mt-2 flex flex-wrap gap-4">
                  {request.attachments.map((file) => (
                    <Attachment key={file.id} file={file} requestId={request.id} />
                  ))}
                </ul>
              </div>
            )}
          </section>

          {isStaff && <SameProblem request={request} onChanged={onChanged} />}
          {isStaff && !request.duplicate_of && (
            <StaffActions request={request} user={user} onChanged={onChanged} />
          )}
        </div>

        <div className="space-y-5">
          {isStaff && <ClassificationPanel request={request} />}
          <Timeline request={request} isStaff={isStaff} />
        </div>
      </div>
    </>
  );
}

function Attachment({
  file,
  requestId,
}: {
  file: ServiceRequest["attachments"][number];
  requestId: number;
}) {
  const url = api.attachmentUrl(requestId, file.id);
  const isImage = file.mime_type.startsWith("image/");
  const viewer = useRef<HTMLDialogElement>(null);

  if (!isImage) {
    return (
      <li>
        <a href={url} download className={`block text-link underline ${FOCUS_LINK}`}>
          {file.filename}
        </a>
      </li>
    );
  }

  // A native dialog gives Esc to close, focus kept inside, and the page behind
  // marked inert, without writing any of it. The full image is the same URL as
  // the thumbnail, so opening it downloads nothing new.
  return (
    <li>
      <button
        type="button"
        onClick={() => viewer.current?.showModal()}
        className={`block text-left text-link underline ${FOCUS_LINK}`}
      >
        <img
          src={url}
          alt=""
          className="mb-1 h-28 w-28 border border-rule object-cover"
        />
        {file.filename}
      </button>

      <dialog
        ref={viewer}
        aria-label={file.filename}
        className="m-auto max-h-[92vh] max-w-[92vw] bg-white p-0 backdrop:bg-ink/80"
      >
        <div className="flex flex-wrap items-center gap-4 border-b border-rule px-4 py-2">
          <span className="mr-auto break-all font-bold">{file.filename}</span>
          <a href={url} download className={`text-link underline ${FOCUS_LINK}`}>
            Download
          </a>
          <Button variant="secondary" onClick={() => viewer.current?.close()}>
            Close
          </Button>
        </div>
        <img
          src={url}
          alt={file.filename}
          className="mx-auto block max-h-[80vh] max-w-full object-contain"
        />
      </dialog>
    </li>
  );
}

// Same list as OPEN in backend/app/queue_order.py.
const OPEN_STATUSES: RequestStatus[] = ["submitted", "under_review", "routed", "in_progress"];

function UrgentFlag({ request, onChanged }: { request: ServiceRequest; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (request.urgent_flagged_at) {
    return (
      <p className="mb-5 border-l-4 border-rule py-1 pl-4">
        You marked this as urgent. Staff see it first.
        <span className="block text-muted">Minarkahan ninyo itong urgent. Ito ang unang makikita ng staff.</span>
      </p>
    );
  }
  if (!OPEN_STATUSES.includes(request.status)) return null;

  if (!open) {
    return (
      <div className="mb-5">
        <Button variant="secondary" onClick={() => setOpen(true)}>
          This is urgent · Urgent po ito
        </Button>
      </div>
    );
  }

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (reason.trim().length < 10) {
      setError("Say why in at least 10 characters · Sabihin kung bakit, kahit 10 titik");
      return;
    }
    setBusy(true);
    try {
      const saved = await api.flagUrgent(request.id, reason);
      if (saved) onChanged();
      else setError("Couldn't mark it, it may already be finished · Hindi na ito mamarkahan, baka tapos na");
    } catch {
      setError("Didn't save, try again · Hindi na-save, subukan ulit");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={save} className="mb-5 border-l-4 border-rule py-1 pl-4" noValidate>
      <Textarea
        name="urgent-reason"
        label="Why is it urgent? · Bakit po ito urgent?"
        hint="Once only. For an emergency, call 911 · Isang beses lang. Kung emergency, tumawag sa 911"
        rows={3}
        maxLength={200}
        value={reason}
        error={error}
        onChange={(e) => {
          setReason(e.target.value);
          setError("");
        }}
      />
      <div className="mt-3 flex gap-3">
        <Button type="submit" disabled={busy}>
          Mark as urgent
        </Button>
        <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

// Linking reports about one problem, so staff act once for everyone who reported it.
function SameProblem({ request, onChanged }: { request: ServiceRequest; onChanged: () => void }) {
  const [suggestions, setSuggestions] = useState<DuplicateSuggestion[]>([]);
  const [reference, setReference] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const open = OPEN_STATUSES.includes(request.status);

  useEffect(() => {
    if (request.duplicate_of || !open) return;
    api.listDuplicateSuggestions(request.id).then(setSuggestions).catch(() => setSuggestions([]));
  }, [request.id, request.duplicate_of, open]);

  const act = async (work: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setMessage("");
    try {
      await work();
      setMessage(done);
      onChanged();
    } catch (err) {
      setMessage(err instanceof ApiError && err.status !== 500 ? err.message : "Didn't save, try again");
    } finally {
      setBusy(false);
    }
  };

  if (request.duplicate_of) {
    return (
      <section className="border-t-2 border-ink pt-5">
        <h2 className="text-[24px] font-bold">Same problem</h2>
        <p className="mt-2">
          This report follows{" "}
          <Link to={`/requests/${request.duplicate_of.id}`} className={`font-bold text-link underline ${FOCUS_LINK}`}>
            {request.duplicate_of.reference_number}
          </Link>
          . Update that one; this report and its resident follow it.
        </p>
        <Button
          variant="secondary"
          className="mt-3"
          disabled={busy}
          onClick={() => act(() => api.unlinkDuplicate(request.id), "Link removed")}
        >
          Remove the link
        </Button>
        <p role="status" className={message ? "mt-3 font-bold" : "sr-only"}>{message}</p>
      </section>
    );
  }

  if (!open && request.linked_count === 0) return null;

  return (
    <section className="border-t-2 border-ink pt-5">
      <h2 className="text-[24px] font-bold">Same problem</h2>
      {request.linked_count > 0 && (
        <p className="mt-2">
          {request.linked_count} other {request.linked_count === 1 ? "report follows" : "reports follow"} this one:{" "}
          {request.linked_reports.map((r, i) => (
            <span key={r.id}>
              {i > 0 && ", "}
              <Link to={`/requests/${r.id}`} className={`text-link underline ${FOCUS_LINK}`}>
                {r.reference_number}
              </Link>
            </span>
          ))}
          . Status changes here reach them too.
        </p>
      )}

      {open && suggestions.length > 0 && (
        <div className="mt-4">
          <h3 className="font-bold">Possible duplicates</h3>
          <ul className="mt-2 space-y-3">
            {suggestions.map((s) => (
              <li key={s.id} className="border-l-4 border-rule pl-3">
                <Link to={`/requests/${s.candidate.id}`} className={`font-bold text-link underline ${FOCUS_LINK}`}>
                  {s.candidate.reference_number}
                </Link>
                <span className="text-muted"> · {timeAgo(s.candidate.created_at)}</span>
                <p className="line-clamp-2">{s.candidate.description}</p>
                <div className="mt-2 flex flex-wrap gap-3">
                  <Button
                    disabled={busy}
                    onClick={() =>
                      act(
                        () => api.linkDuplicate(request.id, s.candidate.reference_number),
                        `Linked to ${s.candidate.reference_number}`,
                      )
                    }
                  >
                    Link
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() => act(() => api.dismissSuggestion(request.id, s.id), "Marked not a duplicate")}
                  >
                    Not a duplicate
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {open && request.linked_count === 0 && (
        <form
          className="mt-4 flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (reference.trim()) act(() => api.linkDuplicate(request.id, reference), `Linked to ${reference.trim().toUpperCase()}`);
          }}
        >
          <div>
            <label htmlFor="link-reference" className="block font-bold">
              Link to another report about the same problem
            </label>
            <input
              id="link-reference"
              value={reference}
              placeholder="GAB-2026-00000"
              onChange={(e) => setReference(e.target.value)}
              className="mt-1 w-48 border-2 border-ink bg-white px-2 py-1 font-mono focus:outline-3 focus:outline-ink"
            />
          </div>
          <Button type="submit" variant="secondary" disabled={busy || !reference.trim()}>
            Link
          </Button>
        </form>
      )}
      <p role="status" className={message ? "mt-3 font-bold" : "sr-only"}>{message}</p>
    </section>
  );
}

function ResidentUpdate({ request }: { request: ServiceRequest }) {
  const note = citizenStatusNote(request);
  if (request.status === "referred") return null;

  const line =
    request.status === "submitted" || request.status === "classified"
      ? "Sorting this and passing it on"
      : request.status === "under_review"
        ? "Staff are checking who should handle this"
        : null;

  return (
    <div className="mb-5 border-l-4 border-rule py-1 pl-4">
      {note ? (
        <p className="text-lg text-ink">{note}</p>
      ) : (
        <>
          {line && <p className="text-lg text-ink">{line}</p>}
          <p className={line ? "mt-1 text-muted" : "text-lg text-ink"}>
            Nothing needed from you, updates show up here
          </p>
        </>
      )}
    </div>
  );
}

function ClassificationPanel({ request }: { request: ServiceRequest }) {
  const corrected =
    request.final_category !== null &&
    request.final_category.id !== request.predicted_category?.id;

  return (
    <section className="border-t-2 border-ink pt-5">
      <h2 className="text-[24px] font-bold">
        Classification
      </h2>

      {request.predicted_category === null ? (
        <p className="mt-2 text-muted">
          Not classified yet
        </p>
      ) : (
        <>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Model predicted</dt>
              <dd className="text-right font-medium text-ink">
                {request.predicted_category.name}
                {request.predicted_urgency && (
                  <> · {URGENCY_LABELS[request.predicted_urgency]}</>
                )}
              </dd>
            </div>
            {request.final_category && (
              <div className="flex justify-between gap-3">
                <dt className="text-muted">Set by staff</dt>
                <dd className="text-right font-medium text-ink">
                  {request.final_category.name}
                  {request.final_urgency && (
                    <> · {URGENCY_LABELS[request.final_urgency]}</>
                  )}
                </dd>
              </div>
            )}
          </dl>

          {corrected && (
            <p className="mt-3 text-sm text-warn">
              Changed by staff, the original prediction is kept
            </p>
          )}

          <div className="mt-4 space-y-3 border-t border-rule pt-4">
            <Confidence label="Category" value={request.category_confidence} />
            <Confidence label="Urgency" value={request.urgency_confidence} />
          </div>

          {request.model_version && (
            <p className="mt-3 text-xs text-muted">
              Model {request.model_version}
              {request.classified_at && <> · {timeAgo(request.classified_at)}</>}
            </p>
          )}
        </>
      )}
    </section>
  );
}

function Timeline({
  request,
  isStaff,
}: {
  request: ServiceRequest;
  isStaff: boolean;
}) {
  return (
    <section className="border-t-2 border-ink pt-5">
      <h2 className="text-[24px] font-bold">
        History
      </h2>
      <ol className="mt-3 space-y-4">
        {request.status_history.map((entry) => (
          <li key={entry.id} className="border-l-2 border-rule pl-3">
            <p className="font-medium text-ink">
              {isStaff
                ? STAFF_STATUS_LABELS[entry.to_status]
                : citizenStatus({
                    status: entry.to_status,
                    assigned_staff: null,
                  })}
            </p>
            <p className="text-sm text-muted">
              {fullDate(entry.created_at)} ·{" "}
              {entry.actor ? entry.actor.full_name : "System"}
            </p>
            {entry.note && (
              <p className="mt-1 text-sm text-ink">{entry.note}</p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

type NextStatus = "in_progress" | "resolved" | "closed";

const NEXT_STATUS: Partial<Record<RequestStatus, { to: NextStatus; label: string }>> = {
  routed: { to: "in_progress", label: "Mark in progress" },
  in_progress: { to: "resolved", label: "Mark resolved" },
  resolved: { to: "closed", label: "Close" },
  referred: { to: "closed", label: "Close" },
};

function StaffActions({
  request,
  user,
  onChanged,
}: {
  request: ServiceRequest;
  user: User;
  onChanged: () => void;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const next = NEXT_STATUS[request.status];
  const finished = request.status === "resolved" || request.status === "closed";

  const changeStatus = async (to: NextStatus) => {
    setBusy(true);
    setMessage("");
    try {
      const updated = await api.updateStatus(user, request.id, to, note);
      if (!updated) {
        setMessage("Not yours any more");
        return;
      }
      setNote("");
      setMessage(`Set to ${STAFF_STATUS_LABELS[to]}`);
      onChanged();
    } catch {
      setMessage("Didn't save, try again");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="border-t-2 border-ink pt-5">
      <h2 className="text-[24px] font-bold">
        Actions
      </h2>

      <p
        role="status"
        aria-live="polite"
        className={
          message
            ? "mt-3 text-sm text-brand"
            : "sr-only"
        }
      >
        {message}
      </p>

      {next ? (
        <>
          <div className="mt-4">
            <Textarea
              name="note"
              label="Note"
              hint="Optional, will be sent to the resident"
              rows={3}
              maxLength={2000}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          <div className="mt-4">
            <Button disabled={busy} onClick={() => changeStatus(next.to)}>
              {busy ? "Saving" : next.label}
            </Button>
          </div>
        </>
      ) : (
        <p className="mt-3 text-muted">
          {finished
            ? "Finished"
            : "Needs a category first"}
        </p>
      )}

      <Reclassify
        request={request}
        user={user}
        note={note}
        disabled={finished || request.status === "referred"}
        onSaved={() => {
          setNote("");
          onChanged();
        }}
      />
      <Referral request={request} onChanged={onChanged} />
    </section>
  );
}

function Reclassify({
  request,
  user,
  note,
  disabled,
  onSaved,
}: {
  request: ServiceRequest;
  user: User;
  note: string;
  disabled: boolean;
  onSaved: () => void;
}) {
  const { state } = useAsync<Category[]>(() => api.getCategories(), []);
  const unlabelled = request.status === "under_review" || request.status === "submitted";
  const [open, setOpen] = useState(unlabelled);
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [urgency, setUrgency] = useState<Urgency | "">("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");

  const categories = state.status === "ready" ? state.data : [];

  const save = async () => {
    const category = categories.find((c) => c.id === categoryId);
    if (!category || urgency === "") return;

    const previousHandler = request.assigned_staff?.id;
    setBusy(true);
    setResult("");
    try {
      const updated = await api.reclassify(
        user,
        request.id,
        category,
        urgency,
        note,
      );
      if (!updated) {
        setResult("Cannot be changed now");
        return;
      }
      const movedAway = updated.assigned_staff?.id !== previousHandler;
      setResult(
        movedAway && updated.assigned_staff
          ? `Saved, now with ${updated.assigned_staff.full_name}`
          : "Saved",
      );
      onSaved();
    } catch {
      setResult("Didn't save, try again");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-6 border-t border-rule pt-4">
      <p
        role="status"
        aria-live="polite"
        className={result ? "mb-3 text-sm text-ink" : "sr-only"}
      >
        {result}
      </p>

      {!open ? (
        <Button
          variant="secondary"
          disabled={disabled || state.status !== "ready"}
          onClick={() => setOpen(true)}
        >
          {disabled
            ? request.status === "referred"
              ? "Take the referral back first"
              : "Finished, cannot change"
            : "Correct the classification"}
        </Button>
      ) : (
        <>
          <h3 className="font-medium text-ink">
            {unlabelled
              ? "Assign a category and urgency"
              : "Correct the classification"}
          </h3>
          <p className="mt-1 text-sm text-muted">
            Changing the category may pass this to someone else
          </p>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Select
              name="category"
              label="Category"
              value={categoryId}
              disabled={state.status !== "ready"}
              onChange={(e) =>
                setCategoryId(e.target.value === "" ? "" : Number(e.target.value))
              }
            >
              <option value="">Choose</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>

            <Select
              name="urgency"
              label="Urgency"
              value={urgency}
              onChange={(e) => setUrgency(e.target.value as Urgency | "")}
            >
              <option value="">Choose</option>
              {(["high", "medium", "low"] as const).map((u) => (
                <option key={u} value={u}>
                  {URGENCY_LABELS[u]}
                </option>
              ))}
            </Select>
          </div>

          <div className="mt-4 flex gap-3">
            <Button
              disabled={busy || categoryId === "" || urgency === ""}
              onClick={save}
            >
              {busy ? "Saving" : "Save classification"}
            </Button>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

function ReferralBox({ request }: { request: ServiceRequest }) {
  const agency = request.referred_agency;
  if (request.status !== "referred" || !agency) return null;
  return (
    <section className="mb-5 border-l-4 border-brand pl-4">
      <h2 className="text-[24px] font-bold">Please contact {agency.name}</h2>
      <p className="text-muted">Mangyaring makipag-ugnayan sa {agency.name}</p>
      <p className="mt-2 text-[19px]">
        This concern is handled by {agency.name}, not the barangay. The barangay has not sent
        your report to them.
      </p>
      <p className="text-muted">
        Ang concern na ito ay hawak ng {agency.name}, hindi ng barangay. Hindi ipinadala ng
        barangay ang inyong report sa kanila.
      </p>
      <dl className="mt-3 grid max-w-md grid-cols-[auto_1fr] gap-x-6 gap-y-1">
        {agency.phone && (
          <>
            <dt className="text-muted">Phone</dt>
            <dd>
              <a href={`tel:${agency.phone}`} className={`text-link underline ${FOCUS_LINK}`}>
                {agency.phone}
              </a>
            </dd>
          </>
        )}
        {agency.hours && (
          <>
            <dt className="text-muted">Hours</dt>
            <dd>{agency.hours}</dd>
          </>
        )}
        {agency.website && (
          <>
            <dt className="text-muted">Website</dt>
            <dd className="break-all">
              <a
                href={agency.website}
                target="_blank"
                rel="noopener noreferrer"
                className={`text-link underline ${FOCUS_LINK}`}
              >
                {agency.website}
              </a>
            </dd>
          </>
        )}
        {agency.notes && (
          <>
            <dt className="text-muted">Note</dt>
            <dd>{agency.notes}</dd>
          </>
        )}
      </dl>
      {!agency.phone && !agency.website && (
        <p className="mt-2 text-muted">
          Ask at the barangay hall for their contact details · Magtanong po sa barangay hall
        </p>
      )}
      {request.referral_note && <p className="mt-3">Staff note: {request.referral_note}</p>}
      <p className="mt-3 font-bold">
        In an emergency, call 911 or go to the barangay hall right away.
        <span className="block font-normal text-muted">
          Kung emergency, tumawag sa 911 o pumunta agad sa barangay hall.
        </span>
      </p>
    </section>
  );
}

const REFERRABLE: RequestStatus[] = ["submitted", "under_review", "routed"];

function Referral({ request, onChanged }: { request: ServiceRequest; onChanged: () => void }) {
  const { state } = useAsync<Agency[]>(() => api.listAgencies(), []);
  const [open, setOpen] = useState(false);
  const [agencyId, setAgencyId] = useState<number | "">("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");

  const agencies = state.status === "ready" ? state.data : [];

  const run = async (work: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setResult("");
    try {
      await work();
      setResult(done);
      onChanged();
    } catch (err) {
      setResult(
        err instanceof ApiError && err.status !== 500 ? err.message : "Didn't save, try again",
      );
    } finally {
      setBusy(false);
    }
  };

  if (request.status === "referred") {
    return (
      <div className="mt-6 border-t border-rule pt-4">
        <h3 className="font-medium text-ink">Referred to {request.referred_agency?.name}</h3>
        <p className="mt-1 text-sm text-muted">
          The resident was told to contact them. Close it when it's settled, or take it back if
          the barangay should handle it.
        </p>
        <Button
          variant="secondary"
          className="mt-3"
          disabled={busy}
          onClick={() => run(() => api.takeBackReferral(request.id), "Taken back")}
        >
          Handle it here instead
        </Button>
        <p role="status" aria-live="polite" className={result ? "mt-2 text-sm" : "sr-only"}>
          {result}
        </p>
      </div>
    );
  }

  if (!REFERRABLE.includes(request.status) || request.linked_count > 0) return null;

  return (
    <div className="mt-6 border-t border-rule pt-4">
      <p role="status" aria-live="polite" className={result ? "mb-3 text-sm" : "sr-only"}>
        {result}
      </p>
      {!open ? (
        <Button
          variant="secondary"
          disabled={state.status !== "ready"}
          onClick={() => setOpen(true)}
        >
          Refer to another agency
        </Button>
      ) : (
        <>
          <h3 className="font-medium text-ink">Refer to another agency</h3>
          <p className="mt-1 text-sm text-muted">
            For concerns the barangay doesn't handle. The resident is told whom to contact.
            Nothing is sent to the agency.
          </p>
          <div className="mt-4 grid gap-4">
            <Select
              name="agency"
              label="Agency"
              value={agencyId}
              onChange={(e) => setAgencyId(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <option value="">Choose</option>
              {agencies.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
            <Textarea
              name="referral-note"
              label="Note"
              hint="Optional, shown to the resident"
              rows={3}
              maxLength={500}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          <div className="mt-4 flex gap-3">
            <Button
              disabled={busy || agencyId === ""}
              onClick={() =>
                run(() => api.referRequest(request.id, Number(agencyId), note), "Referred")
              }
            >
              {busy ? "Saving" : "Refer"}
            </Button>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </>
      )}
    </div>
  );
}