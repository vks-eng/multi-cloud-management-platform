import clsx from 'clsx';
import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react';

const CONTROL =
  'block w-full rounded-md border-0 py-1.5 px-2.5 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 ' +
  'placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-brand-600 disabled:bg-slate-50';

interface FieldShellProps {
  label: string;
  error?: string;
  hint?: ReactNode;
  className?: string;
}

function Help({ id, error, hint }: { id: string; error?: string; hint?: ReactNode }) {
  if (error) {
    return (
      <p id={`${id}-error`} className="mt-1 text-xs text-rose-700">
        {error}
      </p>
    );
  }
  return hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null;
}

export function TextField({ label, error, hint, className, ...rest }: FieldShellProps & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="block text-xs font-medium text-slate-700">
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
      <label htmlFor={id} className="block text-xs font-medium text-slate-700">
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
