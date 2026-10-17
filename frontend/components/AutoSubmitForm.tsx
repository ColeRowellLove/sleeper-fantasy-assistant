"use client";

import type { ReactNode } from "react";

/**
 * A plain GET form that submits itself when a choice changes (a team picked from a list), so there
 * is no button to press. Without JavaScript the form still works: the submit button inside the
 * `<noscript>` is there for that case.
 */
export default function AutoSubmitForm({
  action,
  className,
  submitLabel,
  children,
}: {
  action: string;
  className?: string;
  submitLabel: string;
  children: ReactNode;
}) {
  return (
    <form
      method="get"
      action={action}
      className={className}
      onChange={(event) => event.currentTarget.requestSubmit()}
    >
      {children}
      <noscript>
        <button type="submit" className="btn">
          {submitLabel}
        </button>
      </noscript>
    </form>
  );
}
