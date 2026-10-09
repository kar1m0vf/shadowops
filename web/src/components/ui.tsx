import { useId, type ReactNode } from "react";
import { AlertCircle, ArrowRight, LoaderCircle } from "lucide-react";

export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon" aria-hidden="true">
        {icon}
      </div>
      <h3>{title}</h3>
      <div className="empty-copy">{children}</div>
      {action}
    </div>
  );
}
export function ErrorNotice({
  message,
  title = "Request could not be completed",
}: {
  message: string;
  title?: string;
}) {
  return (
    <div className="error-notice" role="alert">
      <AlertCircle size={18} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}
export function Loading({ children }: { children: ReactNode }) {
  return (
    <div className="loading" role="status">
      <LoaderCircle size={18} className="spin" aria-hidden="true" />
      {children}
    </div>
  );
}
export function ArrowLabel({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <ArrowRight size={15} aria-hidden="true" />
    </>
  );
}
export function JsonView({
  value,
  label = "API response",
}: {
  value: unknown;
  label?: string;
}) {
  return (
    <pre className="json-view" tabIndex={0} aria-label={label}>
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
export function timeLabel(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(new Date(value));
}

export function TextField({
  label,
  value,
  onChange,
  multiline = false,
  maxLength = 2000,
  rows = 2,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  maxLength?: number;
  rows?: number;
  disabled?: boolean;
}) {
  const id = useId();
  const props = {
    id,
    value,
    maxLength,
    disabled,
    onChange: (
      event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
    ) => onChange(event.target.value),
  };
  return (
    <div className="field-label">
      <label htmlFor={id}>{label}</label>
      {multiline ? <textarea {...props} rows={rows} /> : <input {...props} />}
    </div>
  );
}
