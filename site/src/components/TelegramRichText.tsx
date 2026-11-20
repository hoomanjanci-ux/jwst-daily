"use client";

import type { ReactNode } from "react";

type Node = { kind: "text" | "bold" | "italic" | "link"; text: string; href?: string };

export default function TelegramRichText({ text }: { text: string }) {
  const nodes: Node[] = [];
  const re = /<(b|strong|i|em|a)\b([^>]*)>([\s\S]*?)<\/\1>/gi;
  let last = 0;
  const pushText = (value: string) => { if (value) nodes.push({ kind: "text", text: value }); };
  for (const m of text.matchAll(re)) {
    pushText(text.slice(last, m.index));
    const tag = m[1].toLowerCase();
    const inner = m[3].replace(/<[^>]+>/g, "");
    if (tag === "a") {
      const href = /\bhref\s*=\s*["'](https?:\/\/[^"']+)["']/i.exec(m[2])?.[1];
      if (href) nodes.push({ kind: "link", text: inner, href }); else pushText(inner);
    } else nodes.push({ kind: tag === "b" || tag === "strong" ? "bold" : "italic", text: inner });
    last = (m.index ?? 0) + m[0].length;
  }
  pushText(text.slice(last));
  const out: ReactNode[] = [];
  nodes.forEach((n, i) => {
    const key = `${n.kind}-${i}`;
    if (n.kind === "bold") out.push(<strong key={key}>{n.text}</strong>);
    else if (n.kind === "italic") out.push(<em key={key}>{n.text}</em>);
    else if (n.kind === "link") out.push(<a key={key} href={n.href} target="_blank" rel="noopener noreferrer" className="text-star hover:underline">{n.text}</a>);
    else out.push(<span key={key}>{n.text}</span>);
  });
  return <>{out}</>;
}
