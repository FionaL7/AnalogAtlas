/** Free-text terrain search. Needs CLIP, so this is the one control that
 * requires the API to be up; it says so plainly instead of failing silently. */
import { useState } from "react";

import { apiMode } from "../../lib/api";

interface Props {
  onSearch: (query: string) => void;
  busy?: boolean;
  error?: string | null;
}

export function SearchBox({ onSearch, busy, error }: Props) {
  const [value, setValue] = useState("");
  return (
    <form
      className="flex flex-col gap-2 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim()) onSearch(value.trim());
      }}
    >
      <label htmlFor="q" className="text-xs uppercase tracking-wide text-muted">
        Describe a landscape
      </label>
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
      {apiMode() === "mock" && (
        <p className="text-xs text-muted">
          Mock mode: responses come from fixtures. Set VITE_API_BASE to go live.
        </p>
      )}
      {error && <p className="text-xs text-breaks">{error}</p>}
    </form>
  );
}
