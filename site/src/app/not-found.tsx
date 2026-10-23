import Link from "next/link";

export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center px-4 text-center">
      <div>
        <p className="mb-4 text-7xl">🌠</p>
        <h1 className="mb-3 text-3xl font-black">۴۰۴ — این صفحه در کهکشان پیدا نشد</h1>
        <p className="mb-8 text-sm leading-7 text-muted">
          شاید ستاره‌ای که دنبالش بودید جای دیگری می‌درخشد.
        </p>
        <Link href="/" className="btn-cosmic btn-primary">
          بازگشت به نبض کیهان
        </Link>
      </div>
    </main>
  );
}
