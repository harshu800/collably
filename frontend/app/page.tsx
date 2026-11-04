import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-16 px-6 py-16">
      <header className="flex flex-col gap-6">
        <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">
          Creator – Brand Marketplace
        </p>
        <h1 className="text-4xl font-bold leading-tight sm:text-5xl">
          Clear deals. Verified funding. Defined deliverables.
        </h1>
        <p className="max-w-2xl text-lg text-slate-600">
          We help Indian UGC creators, influencers, and D2C brands collaborate
          on paid campaigns with transparent terms. Agreements are versioned
          and signed by both sides. Campaign funding is visible before work
          starts. Deliverables and revision counts are explicit, not implied.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/sign-up"
            className="rounded-md bg-brand-600 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-2"
          >
            Get started
          </Link>
          <Link
            href="/how-it-works"
            className="rounded-md border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
          >
            How it works
          </Link>
        </div>
      </header>

      <section className="grid gap-8 sm:grid-cols-2">
        <article className="rounded-lg border border-slate-200 p-6">
          <h2 className="text-xl font-semibold">What this platform does</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-slate-700">
            <li>Lets brands post UGC, influencer, or hybrid campaigns.</li>
            <li>Lets creators find and apply to paid opportunities.</li>
            <li>Captures scope, deliverables, revision limits, and usage rights in a versioned agreement.</li>
            <li>Marks campaigns as funded only after the money has arrived.</li>
            <li>Tracks deliverable submission, revisions, and approval.</li>
          </ul>
        </article>

        <article className="rounded-lg border border-slate-200 p-6">
          <h2 className="text-xl font-semibold">What we do not promise</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-slate-700">
            <li>Guaranteed campaign fit or guaranteed earnings.</li>
            <li>Legal, tax, or compliance advice for your business.</li>
            <li>Instant payouts. Payout timing depends on the payment provider.</li>
            <li>Any AI-generated outcome or match quality claim.</li>
          </ul>
        </article>
      </section>

      <footer className="border-t border-slate-200 pt-6 text-sm text-slate-500">
        <p>
          This is an early-stage product. Payments are handled by a mock
          provider in development. Real money flow requires licensed payment
          infrastructure and legal review — see the project README.
        </p>
      </footer>
    </main>
  );
}
