import type { Metadata, Viewport } from "next";
import "vazirmatn/Vazirmatn-font-face.css";
import "./globals.css";

const SITE_URL = "https://nabzekeyhan.ir";
const TITLE = "نبض کیهان — اخبار فضا و تحلیل‌های جیمز وب به فارسی";
const DESC =
  "نبض کیهان: تازه‌ترین اخبار رسمی ناسا و اسا از تلسکوپ جیمز وب به فارسی، همراه با تحلیل هوش مصنوعی داده‌های خام JWST در راز کیهان. منظومهٔ شمسی سه‌بعدی زنده، هم‌گام با زمان واقعی.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: TITLE,
    template: "%s | نبض کیهان",
  },
  description: DESC,
  keywords: [
    "جیمز وب", "تلسکوپ جیمز وب", "JWST", "اخبار فضا", "نجوم به فارسی",
    "نبض کیهان", "راز کیهان", "ناسا به فارسی", "تصاویر فضایی", "کهکشان",
    "تلسکوپ فضایی", "اخبار ناسا",
  ],
  applicationName: "نبض کیهان",
  authors: [{ name: "نبض کیهان" }],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "fa_IR",
    url: SITE_URL,
    siteName: "نبض کیهان",
    title: TITLE,
    description: DESC,
    images: [{ url: "/og-default.jpg", width: 1200, height: 630, alt: "نبض کیهان" }],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESC,
    images: ["/og-default.jpg"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 },
  },
};

export const viewport: Viewport = {
  themeColor: "#04060f",
  width: "device-width",
  initialScale: 1,
};

const orgJsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": SITE_URL + "/#website",
      url: SITE_URL,
      name: "نبض کیهان",
      alternateName: "Nabze Keyhan",
      description: DESC,
      inLanguage: "fa-IR",
      publisher: { "@id": SITE_URL + "/#org" },
    },
    {
      "@type": "Organization",
      "@id": SITE_URL + "/#org",
      name: "نبض کیهان",
      url: SITE_URL,
      description: "اخبار فضا و تحلیل داده‌های جیمز وب به فارسی و انگلیسی",
      sameAs: [
        "https://t.me/NabzeKeyhan1",
        "https://t.me/RazKeyhan",
        "https://t.me/CosmicNewsJWST",
        "https://t.me/CosmicInsightJWST",
      ],
    },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl">
      <body className="min-h-screen antialiased">
        {children}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(orgJsonLd) }}
        />
      </body>
    </html>
  );
}
