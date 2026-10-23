import type { ReactNode } from "react";

/** import.xml with light syntax colouring. Text is rendered by React, so nothing is interpreted as HTML. */
export function XmlView({ xml, maxLines }: { xml: string; maxLines?: number }) {
  const all = xml.split("\n");
  const lines = maxLines ? all.slice(0, maxLines) : all;
  return (
    <pre className="xml" tabIndex={0}>
      {lines.map((line, i) => (
        <span key={i}>
          {colour(line)}
          {"\n"}
        </span>
      ))}
      {maxLines && all.length > maxLines ? <span className="cmt">{`... ${all.length - maxLines} more lines`}</span> : null}
    </pre>
  );
}

function colour(line: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(<!--.*?-->|<!--.*$|^\s*-->|<\?xml[^>]*\?>)|(<\/?[\w:]+)|(\s[\w:]+=)("[^"]*")|(\/?>)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(line))) {
    if (m.index > last) out.push(line.slice(last, m.index));
    if (m[1]) out.push(<span key={k++} className="cmt">{m[1]}</span>);
    else if (m[2]) out.push(<span key={k++} className="tag">{m[2]}</span>);
    else if (m[3]) {
      out.push(<span key={k++} className="attr">{m[3]}</span>);
      out.push(m[4]);
    } else if (m[5]) out.push(<span key={k++} className="tag">{m[5]}</span>);
    last = m.index + m[0].length;
  }
  if (last < line.length) out.push(line.slice(last));
  return out;
}
