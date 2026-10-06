export default function UnifiedDiff({ diff }) {
  if (!diff) return <p className="change-purpose">No changed lines.</p>;
  return (
    <div className="diff-code" aria-label="Git-style unified diff">
      {diff.split("\n").map((line, index) => {
        let style = "context";
        if (line.startsWith("---") || line.startsWith("+++")) style = "header";
        else if (line.startsWith("+")) style = "added";
        else if (line.startsWith("-")) style = "removed";
        else if (line.startsWith("@@")) style = "hunk";
        return (
          <div key={index} className={`diff-line diff-line-${style}`}>
            {line || " "}
          </div>
        );
      })}
    </div>
  );
}
