import type { MetadataRoute } from "next";
import { analyses, news, SITE_URL } from "@/lib/content";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const home: MetadataRoute.Sitemap = [
    {
      url: SITE_URL,
      lastModified: now,
      changeFrequency: "hourly",
      priority: 1,
    },
  ];
  const posts: MetadataRoute.Sitemap = analyses.map((a) => ({
    url: `${SITE_URL}/post/${a.slug}`,
    lastModified: a.published_utc ? new Date(a.published_utc) : now,
    changeFrequency: "monthly",
    priority: 0.7,
  }));
  const newsPages: MetadataRoute.Sitemap = news.map((n) => ({
    url: `${SITE_URL}/news/${n.slug}`,
    lastModified: n.date_utc ? new Date(n.date_utc) : now,
    changeFrequency: "weekly",
    priority: 0.6,
  }));
  // /admin intentionally excluded
  return [...home, ...posts, ...newsPages];
}
