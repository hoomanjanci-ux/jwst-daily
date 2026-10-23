import type { Metadata } from "next";
import AdminClient from "./AdminClient";

// Hidden owner panel: invisible to search engines at four layers —
// robots.txt Disallow + noindex,nofollow meta + excluded from sitemap + no inbound links.
export const metadata: Metadata = {
  title: "…",
  robots: { index: false, follow: false, nocache: true, googleBot: { index: false, follow: false } },
};

export default function AdminPage() {
  return <AdminClient />;
}
