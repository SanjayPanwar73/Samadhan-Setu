import { useEffect, useId, useRef } from "react";
import Icon from "./Icon";

export function Button({
  variant = "primary",
  loading = false,
  disabled,
  children,
  className = "",
  type = "button",
  ...props
}) {
  return (
    <button
      type={type}
      className={`btn btn-${variant} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <span className="spinner" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function Card({ children, className = "", ...props }) {
  return (
    <section className={`panel ${className}`} {...props}>
      {children}
    </section>
  );
}
export function PageHeader({ eyebrow, title, description, actions }) {
  const heading = useRef(null);
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
  }, []);
  return (
    <div className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 ref={heading} tabIndex={-1} className="focus:outline-none">
          {title}
        </h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}
export function Alert({ variant = "info", title, children, className = "" }) {
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={`alert alert-${variant} ${className}`}
    >
      <Icon
        name={variant === "success" ? "checkCircle" : "alertCircle"}
        size={18}
      />
      <div>
        {title && <p className="font-semibold">{title}</p>}
        {children}
      </div>
    </div>
  );
}
export function Badge({ tone = "neutral", children, className = "" }) {
  return <span className={`badge badge-${tone} ${className}`}>{children}</span>;
}
export function StatusBadge({ status }) {
  const tones = {
    pending: "amber",
    in_progress: "blue",
    reopened: "orange",
    resolved: "green",
    rejected: "red",
  };
  return (
    <Badge tone={tones[status] || "neutral"}>
      <span className="status-dot" />
      {status ? status.replaceAll("_", " ") : "Unknown"}
    </Badge>
  );
}
export function PriorityBadge({ score }) {
  if (score == null || !Number.isFinite(Number(score)))
    return <Badge>Unscored</Badge>;
  const value = Number(score);
  const [label, tone] =
    value >= 90
      ? ["Critical", "red"]
      : value >= 70
        ? ["High", "orange"]
        : value >= 40
          ? ["Medium", "amber"]
          : ["Low", "neutral"];
  return (
    <span
      className="priority-badge"
      title={`Priority score: ${value.toFixed(2)} / 100`}
    >
      <span className={`priority-bars priority-${tone}`} aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span>{label}</span>
      <span className="priority-score">{value.toFixed(0)}</span>
    </span>
  );
}
export function Skeleton({ className = "" }) {
  return <div aria-hidden="true" className={`skeleton ${className}`} />;
}
export function PageSkeleton() {
  return (
    <div className="page-stack" role="status" aria-label="Loading page">
      <span className="sr-only">Loading, please wait.</span>
      <Skeleton className="h-8 w-56" />
      <div className="stats-grid">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
      <Skeleton className="h-72" />
    </div>
  );
}
export function TableSkeleton({ rows = 5 }) {
  return (
    <div className="p-5 space-y-5" role="status" aria-label="Loading records">
      <span className="sr-only">Loading records.</span>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex gap-5">
          <Skeleton className="h-10 w-10" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
          </div>
          <Skeleton className="h-6 w-20" />
        </div>
      ))}
    </div>
  );
}
export function EmptyState({
  icon = "file",
  title = "Nothing here yet",
  description,
  action,
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon name={icon} size={25} />
      </div>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
export function ErrorState({ message, onRetry }) {
  return (
    <div role="alert">
      <EmptyState
        icon="alertCircle"
        title="We couldn’t load this"
        description={message || "Something went wrong. Please try again."}
        action={
          onRetry && (
            <Button variant="secondary" onClick={onRetry}>
              <Icon name="refresh" size={16} />
              Try again
            </Button>
          )
        }
      />
    </div>
  );
}
export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
  className = "",
}) {
  return (
    <div className={`field ${className}`}>
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && (
        <p id={htmlFor ? `${htmlFor}-hint` : undefined} className="field-hint">
          {hint}
        </p>
      )}
      {error && (
        <p
          id={htmlFor ? `${htmlFor}-error` : undefined}
          className="field-error"
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  );
}
export function StatCard({
  label,
  value,
  hint,
  icon = "chart",
  tone = "green",
}) {
  return (
    <Card className="stat-card">
      <div className="stat-top">
        <p>{label}</p>
        <span className={`stat-icon stat-${tone}`}>
          <Icon name={icon} size={18} />
        </span>
      </div>
      <div className="stat-value">
        {value == null ? <span className="text-slate-400">—</span> : value}
      </div>
      {hint && <p className="stat-hint">{hint}</p>}
    </Card>
  );
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  busy = false,
}) {
  const dialogRef = useRef(null);
  const titleId = useId();
  const descriptionId = useId();
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    const previous = document.activeElement;
    dialog.showModal();
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = originalOverflow;
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, [open]);
  if (!open) return null;
  return (
    <dialog
      ref={dialogRef}
      className="modal"
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose?.();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget && !busy) {
          const bounds = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom
          )
            onClose?.();
        }
      }}
    >
      <div className="modal-heading">
        <div>
          <h2 id={titleId}>{title}</h2>
          {description && <p id={descriptionId}>{description}</p>}
        </div>
        <Button
          variant="ghost"
          className="icon-button"
          onClick={onClose}
          disabled={busy}
          aria-label="Close dialog"
        >
          <Icon name="x" />
        </Button>
      </div>
      <div className="modal-content">{children}</div>
      {footer && <div className="modal-footer">{footer}</div>}
    </dialog>
  );
}
export function Pagination({
  page,
  pageSize,
  count,
  hasMore,
  onPrevious,
  onNext,
  loading,
}) {
  return (
    <div className="pagination">
      <p>
        {count ? `${page * pageSize + 1}–${page * pageSize + count}` : "0"}{" "}
        records{hasMore ? " · More available" : ""}
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          disabled={page === 0 || loading}
          onClick={onPrevious}
        >
          <Icon name="arrowLeft" size={15} />
          <span>Previous</span>
        </Button>
        <Button
          variant="secondary"
          disabled={!hasMore || loading}
          onClick={onNext}
        >
          <span>Next</span>
          <Icon name="arrowRight" size={15} />
        </Button>
      </div>
    </div>
  );
}
