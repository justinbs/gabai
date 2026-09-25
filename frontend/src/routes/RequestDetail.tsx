import { useRef, useState } from "react";
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
import type {
  Category,
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

          {isStaff && (
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

function ResidentUpdate({ request }: { request: ServiceRequest }) {
  const note = citizenStatusNote(request);

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
        disabled={finished}
        onSaved={() => {
          setNote("");
          onChanged();
        }}
      />
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
  const [open, setOpen] = useState(request.status === "under_review");
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
            ? "Finished, cannot change"
            : "Correct the classification"}
        </Button>
      ) : (
        <>
          <h3 className="font-medium text-ink">
            {request.status === "under_review"
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