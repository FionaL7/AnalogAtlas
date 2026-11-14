/**
 * Horizontal bars for one series: label, thin bar, printed value. The value is
 * always printed, so colour is never the only carrier (§6); the highlighted
 * row is also marked in text. Optional reference line (e.g. random = 50%).
 */
export interface Bar {
  label: string;
  value: number;
  /** Shown instead of the raw value. */
  display?: string;
  highlight?: boolean;
  /** Hover text with the full numbers. */
  detail?: string;
}

interface Props {
  bars: Bar[];
  max: number;
  reference?: { value: number; label: string };
  caption: string;
}

export function BarList({ bars, max, reference, caption }: Props) {
  const pct = (v: number) => `${Math.max(0, Math.min(1, v / max)) * 100}%`;
  return (
    <figure className="mt-3">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <tbody>
          {bars.map((b) => (
            <tr key={b.label} title={b.detail ?? `${b.label}: ${b.display ?? b.value}`} className="group">
              <th scope="row" className="w-[45%] py-1.5 pr-3 text-left font-normal">
                {b.label}
                {b.highlight && <span className="sr-only"> (ours)</span>}
              </th>
              <td className="py-1.5">
                <span className="relative block h-2.5 rounded-r bg-edge/40">
                  <span
                    className={`block h-full rounded-r ${b.highlight ? "bg-holds" : "bg-muted/70"} group-hover:brightness-125`}
                    style={{ width: pct(b.value) }}
                  />
                  {reference && (
                    <span
                      aria-hidden
                      className="absolute -top-1 -bottom-1 w-px bg-ink/60"
                      style={{ left: pct(reference.value) }}
                    />
                  )}
                </span>
              </td>
              <td className="w-16 py-1.5 pl-3 text-right tabular-nums">{b.display ?? b.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {reference && (
        <figcaption className="mt-1 text-[11px] text-muted">Thin line: {reference.label}</figcaption>
      )}
    </figure>
  );
}
