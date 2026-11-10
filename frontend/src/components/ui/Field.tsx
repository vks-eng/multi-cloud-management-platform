import clsx from 'clsx';
import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react';

const CONTROL =
  'block w-full rounded-lg border-0 bg-canvas py-2 px-3 text-sm text-ink ring-1 ring-inset ring-line ' +
  'placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-inset focus:ring-orbit-400 disabled:opacity-60';

interface FieldShellProps {
  label: string;
  error?: string;
  hint?: ReactNode;
  className?: string;
}

function Help({ id, error, hint }: { id: string; error?: string; hint?: ReactNode }) {
  if (error) {
    return (
      <p id={`${id}-error`} className="mt-1 text-xs text-rose-300">
        {error}
      </p>
    );
  }
  return hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null;
}

export function TextField({ label, error, hint, className, ...rest }: FieldShellProps & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="block text-xs font-medium text-muted">
        {label}
      </label>
      <input
        id={id}
        className={clsx(CONTROL, 'mt-1', error && 'ring-rose-400')}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        {...rest}
      />
      <Help id={id} error={error} hint={hint} />
    </div>
  );
}

export interface Option {
  value: string;
  label: string;
}

export function SelectField({
  label,
  error,
  hint,
  className,
  options,
  ...rest
}: FieldShellProps & SelectHTMLAttributes<HTMLSelectElement> & { options: Option[] }) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="block text-xs font-medium text-muted">
        {label}
      </label>
      <select
        id={id}
        className={clsx(CONTROL, 'mt-1 pr-8', error && 'ring-rose-400')}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        {...rest}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <Help id={id} error={error} hint={hint} />
    </div>
  );
}
