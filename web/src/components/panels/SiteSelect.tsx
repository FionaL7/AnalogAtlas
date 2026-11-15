/** Grouped dropdown that always opens below its button.
 *  A native <select> can't do this: macOS draws its menu over the control. */
import { useEffect, useId, useRef, useState, type Ref } from "react";

export type SiteOption = { value: string; label: string };
export type SiteGroup = { label: string; options: SiteOption[] };

type Props = {
  label: string;
  value: string;
  placeholder: string;
  groups: SiteGroup[];
  onChange: (value: string) => void;
  /** The combobox button, so a caller can open the list ("Pick another site"). */
  buttonRef?: Ref<HTMLButtonElement>;
};

export function SiteSelect({ label, value, placeholder, groups, onChange, buttonRef }: Props) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const root = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);

  // The placeholder only labels the closed button; it is not a choice in the list.
  const flat: SiteOption[] = groups.flatMap((g) => g.options);
  const current = flat.find((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  useEffect(() => {
    if (open && active >= 0) {
      const el = list.current?.querySelector<HTMLElement>(`[data-i="${active}"]`);
      el?.scrollIntoView?.({ block: "nearest" });  // absent in jsdom
    }
  }, [open, active]);

  const show = () => {
    setActive(Math.max(0, flat.findIndex((o) => o.value === value)));
    setOpen(true);
  };
  const pick = (v: string) => {
    setOpen(false);
    if (v !== value) onChange(v);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) { e.preventDefault(); show(); }
      return;
    }
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(flat.length - 1, i + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(0, i - 1)); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (active >= 0) pick(flat[active].value); }
    else if (e.key === "Escape" || e.key === "Tab") setOpen(false);
  };

  let i = 0;
  const optionEl = (o: SiteOption) => {
    const n = i++;
    return (
      <li
        key={o.value || "_none"}
        id={`${id}-opt-${n}`}
        data-i={n}
        role="option"
        aria-selected={o.value === value}
        onMouseEnter={() => setActive(n)}
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => pick(o.value)}
        className={`cursor-pointer break-words px-3 py-1.5 text-sm ${
          n === active ? "bg-hover" : ""
        } ${o.value === value ? "text-ink font-medium" : "text-ink/90"}`}
      >
        {o.label}
      </li>
    );
  };

  return (
    <div ref={root} className="relative w-[18rem] max-w-full">
      <span id={`${id}-label`} className="mb-1 block text-xs uppercase tracking-wide text-muted">
        {label}
      </span>
      <button
        ref={buttonRef}
        type="button"
        role="combobox"
        aria-labelledby={`${id}-label`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        aria-activedescendant={open && active >= 0 ? `${id}-opt-${active}` : undefined}
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={onKeyDown}
        className="flex w-full items-center justify-between gap-3 rounded border border-edge bg-base py-2 pl-3 pr-3 text-left text-sm"
      >
        <span className={`min-w-0 break-words ${current ? "" : "text-muted"}`}>{current?.label ?? placeholder}</span>
        <svg aria-hidden viewBox="0 0 20 20" className={`h-4 w-4 shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`}>
          <path d="M5 7.5l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <ul
          ref={list}
          id={`${id}-list`}
          role="listbox"
          aria-labelledby={`${id}-label`}
          className="absolute left-0 top-full z-[1100] mt-1 max-h-80 w-full overflow-y-auto rounded border border-edge bg-panel pb-1 shadow-lg"
        >
          {groups.filter((g) => g.options.length).map((g) => (
            <li key={g.label} role="presentation">
              <div className="sticky top-0 border-y border-edge bg-edge px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink">{g.label}</div>
              <ul role="group" aria-label={g.label}>{g.options.map(optionEl)}</ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
