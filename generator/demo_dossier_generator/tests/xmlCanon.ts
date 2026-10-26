import { DOMParser } from "@xmldom/xmldom";

/**
 * Canonical form of an import.xml for comparison: elements, attributes and
 * text, in order. Comments and whitespace are ignored; CDATA and escaped text
 * count as the same text.
 */
export interface CanonNode {
  name: string;
  attrs: Record<string, string>;
  text: string;
  children: CanonNode[];
}

type XNode = { nodeType: number; nodeName: string; nodeValue: string | null; childNodes: ArrayLike<XNode>; attributes?: ArrayLike<{ name: string; value: string }> };

function canon(node: XNode): CanonNode {
  const attrs: Record<string, string> = {};
  const list = node.attributes;
  if (list) for (let i = 0; i < list.length; i++) attrs[list[i].name] = list[i].value;
  let text = "";
  const children: CanonNode[] = [];
  for (let i = 0; i < node.childNodes.length; i++) {
    const c = node.childNodes[i];
    if (c.nodeType === 1) children.push(canon(c));
    else if (c.nodeType === 3 || c.nodeType === 4) text += c.nodeValue ?? "";
  }
  return { name: node.nodeName, attrs, text: children.length ? "" : text.trim(), children };
}

export function canonicalXml(xml: string): CanonNode {
  const errors: string[] = [];
  const doc = new DOMParser({
    errorHandler: { error: (m: string) => errors.push(m), fatalError: (m: string) => errors.push(m), warning: () => {} },
  }).parseFromString(xml, "text/xml");
  if (errors.length) throw new Error(`XML parse errors: ${errors.join("; ")}`);
  return canon(doc.documentElement as unknown as XNode);
}
