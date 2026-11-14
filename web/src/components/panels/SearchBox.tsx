/** Free-text or image terrain search. Needs CLIP at request time, so this is
 * the one control that requires the API; in mock mode it says so plainly
 * instead of failing silently. */
import { useRef, useState } from "react";

import { apiMode } from "../../lib/api";
import type { Body } from "../../lib/types";

export type SearchInput = { query: string } | { image_b64: string; filename: string };

interface Props {
  body: Body;
  onBodyChange: (body: Body) => void;
  onSearch: (input: SearchInput) => void;
  busy?: boolean;
  error?: string | null;
}

const BODY_OPTIONS: { value: Body; label: string }[] = [
  { value: "moon", label: "Moon (60°S–60°N)" },
  { value: "moon_polar", label: "Moon south pole" },
  { value: "earth", label: "Earth" },
];

const MAX_IMAGE_BYTES = 6 * 1024 * 1024;

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error ?? new Error("could not read the file"));
    r.readAsDataURL(file);
  });
}

export function SearchBox({ body, onBodyChange, onSearch, busy, error }: Props) {
  const [value, setValue] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  return (
    <form
      className="flex flex-col gap-2 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim()) onSearch({ query: value.trim() });
      }}
    >
      <span className="flex items-end justify-between gap-2">
        <label htmlFor="q" className="text-xs uppercase tracking-wide text-muted">
          Describe a landscape
        </label>
        <label className="flex items-center gap-1 text-xs text-muted">
          <span className="sr-only">Search on</span>
          on
          <select
            aria-label="Search on"
            value={body}
            onChange={(e) => onBodyChange(e.target.value as Body)}
            className="rounded border border-edge bg-base px-1.5 py-0.5 text-xs text-ink"
          >
            {BODY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
      </span>
      <span className="flex gap-2">
        <input
          id="q"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="smooth flat dark lava plains"
          className="min-w-0 flex-1 rounded border border-edge bg-base px-3 py-2 text-sm
                     focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1"
        />
        <button
          type="submit"
          disabled={busy || !value.trim()}
          className="rounded border border-edge bg-panel px-3 py-2 text-sm disabled:opacity-50"
        >
          {busy ? "Searching…" : "Search"}
        </button>
      </span>
      <span className="flex items-center gap-2 text-xs text-muted">
        or
        <button
          type="button"
          disabled={busy}
          onClick={() => fileRef.current?.click()}
          className="rounded border border-edge px-2 py-1 text-ink hover:bg-edge/40 disabled:opacity-50"
        >
          search with a picture…
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          aria-label="Search with a picture"
          className="sr-only"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (!file) return;
            if (file.size > MAX_IMAGE_BYTES) {
              setFileError("That image is over 6 MB. Try a smaller one.");
              return;
            }
            setFileError(null);
            try {
              onSearch({ image_b64: await readAsDataUrl(file), filename: file.name });
            } catch (err) {
              setFileError((err as Error).message);
            }
          }}
        />
      </span>
      {apiMode() === "mock" && (
        <p className="text-xs text-muted">
          Mock mode: search answers come from fixtures. Set VITE_API_BASE to go live.
        </p>
      )}
      {(fileError || error) && <p role="alert" className="text-xs text-breaks">{fileError ?? error}</p>}
    </form>
  );
}
