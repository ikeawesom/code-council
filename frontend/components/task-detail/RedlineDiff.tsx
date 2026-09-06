import type { DiffPair } from "@/lib/api";

// The money-shot component. Renders the word-level diff the backend computed
// in `analysis/proposal.py::render_diff()` - never re-diff in the browser.
// Body font (inherited from the page), not monospace: it must read like a
// contract, not a code diff.
export default function RedlineDiff({ diff }: { diff: DiffPair[] }) {
  return (
    <p className="text-[15px] leading-[1.8] text-text-main">
      {diff.map(([op, text], i) => {
        if (op === "delete") {
          return (
            <del
              key={i}
              className="text-severity-high bg-severity-high/10 px-0.5 rounded-[2px] decoration-severity-high"
            >
              {text}
            </del>
          );
        }
        if (op === "insert") {
          return (
            <ins
              key={i}
              className="text-status-approved bg-status-approved/10 px-0.5 rounded-[2px] decoration-status-approved no-underline"
            >
              {text}
            </ins>
          );
        }
        return <span key={i}>{text}</span>;
      })}
    </p>
  );
}
