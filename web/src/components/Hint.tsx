/**
 * One visible line that explains a term a newcomer can't guess (#53).
 *
 * Visible text, not a tooltip: phones have no hover, and judges skim rather
 * than hover. `more` links to a section of the Methodology page, which stays
 * the one full explanation; hints never repeat it.
 */
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface Props {
  children: ReactNode;
  /** Methodology section id, e.g. "glossary". */
  more?: string;
  className?: string;
}

export function Hint({ children, more, className = "" }: Props) {
  return (
    <span className={`block text-[11px] font-normal normal-case leading-snug tracking-normal text-muted ${className}`}>
      {children}
      {more && (
        <>
          {" "}
          <Link
            to={`/methodology#${more}`}
            aria-label="How this works"
            title="How this works"
            className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-edge align-middle text-[9px] leading-none text-holds hover:border-holds"
          >
            ?
          </Link>
        </>
      )}
    </span>
  );
}
