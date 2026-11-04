export default function PricingPage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-16">
      <header>
        <h1 className="text-3xl font-bold">Pricing</h1>
        <p className="mt-2 text-slate-600">
          Honest, early-stage pricing. No surprise cuts.
        </p>
      </header>
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold">While we are in beta</h2>
        <p className="mt-2 text-sm text-slate-600">
          Creating an account, posting campaigns, and applying to campaigns are
          all free. Payouts run through a mock provider during development; a
          real provider lands after legal review.
        </p>
      </section>
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold">After launch</h2>
        <p className="mt-2 text-sm text-slate-600">
          Our plan is a flat percentage platform fee charged to the brand on
          each campaign. We will publish the exact number before taking any
          real payments. Creators keep the full agreed amount; the brand sees
          the fee as a line item.
        </p>
      </section>
    </main>
  );
}
