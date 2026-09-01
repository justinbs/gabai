import type { ButtonHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

// Shared primitives. Squared corners, hairline rules, no cards and no shadows.
// Colour appears only where it carries meaning, so the chrome stays black and
// white and urgency is the thing that draws the eye.

// GOV.UK's focus state is a yellow block with a black edge rather than a
// coloured outline. Exported because four files were repeating their own ring
// and drifting from it.
export const FOCUS_BUTTON =
  "focus-visible:outline-none focus-visible:bg-focus focus-visible:text-ink focus-visible:shadow-[0_3px_0_#0b0c0c]";

export const FOCUS_LINK =
  "focus-visible:outline-none focus-visible:bg-focus focus-visible:text-ink focus-visible:no-underline focus-visible:shadow-[0_2px_0_#0b0c0c]";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary";
};

export function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...props
}: ButtonProps) {
  const styles =
    variant === "primary"
      ? "bg-brand text-white shadow-[0_3px_0_var(--color-brand-edge)] hover:bg-[#005a30]"
      : "bg-wash text-ink shadow-[0_3px_0_#929191] hover:bg-[#dbdad9]";

  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center px-5 py-2.5 text-[17px] font-bold disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none ${FOCUS_BUTTON} ${styles} ${className}`}
      {...props}
    />
  );
}

export function PageHeading({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="mb-6 border-t-2 border-ink pt-5">
      <h1 className="text-[32px] font-bold leading-tight tracking-tight">
        {title}
      </h1>
      {description && <p className="mt-1 text-[19px] text-muted">{description}</p>}
    </div>
  );
}

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  hint?: string;
  error?: string;
};

export function Textarea({ label, hint, error, id, ...props }: TextareaProps) {
  const fieldId = id ?? props.name ?? "textarea";
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;

  return (
    <div>
      <label htmlFor={fieldId} className="block text-[19px] font-bold">
        {label}
      </label>
      {hint && (
        <p id={hintId} className="mt-1 text-muted">
          {hint}
        </p>
      )}
      {/* Always mounted. An alert region inserted into the DOM at the same moment
          as its text is routinely not announced, and this is the error path a
          citizen respondent actually hits. */}
      <p
        id={errorId}
        role="alert"
        className={
          error
            ? "mt-2 border-l-4 border-danger pl-3 font-bold text-danger"
            : "sr-only"
        }
      >
        {error}
      </p>
      <textarea
        id={fieldId}
        aria-describedby={
          [hint && hintId, error && errorId].filter(Boolean).join(" ") ||
          undefined
        }
        aria-invalid={error ? true : undefined}
        className={`mt-2 block w-full border-2 px-3 py-2 text-[19px] focus:outline-3 focus:outline-ink focus-visible:shadow-[0_0_0_4px_#ffdd00] ${
          error ? "border-danger" : "border-ink"
        }`}
        {...props}
      />
    </div>
  );
}

export function Select({
  label,
  id,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  children: ReactNode;
}) {
  const fieldId = id ?? props.name ?? "select";
  return (
    <div>
      <label htmlFor={fieldId} className="block text-[19px] font-bold">
        {label}
      </label>
      <select
        id={fieldId}
        className="mt-2 block w-full border-2 border-ink bg-white px-3 py-2 text-[19px] focus:outline-3 focus:outline-ink focus-visible:shadow-[0_0_0_4px_#ffdd00]"
        {...props}
      >
        {children}
      </select>
    </div>
  );
}

// Announced politely so a screen reader user learns the list finished loading
// without being interrupted.
export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="py-10 text-[19px] text-muted">
      {label}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="border-l-10 border-rule py-2 pl-4">
      <p className="text-[19px] font-bold">{title}</p>
      <p className="mt-1 text-[19px] text-muted">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  description,
  onRetry,
}: {
  title?: string;
  description: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="border-l-10 border-danger py-2 pl-4">
      <p className="text-[19px] font-bold text-danger">{title}</p>
      <p className="mt-1 text-[19px]">{description}</p>
      {onRetry && (
        <Button variant="secondary" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
