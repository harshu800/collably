export default function HowItWorksPage() {
  const steps = [
    {
      title: "Brand posts a campaign",
      description:
        "A brand defines the deliverables, budget, revision limit, usage rights, and deadline. Nothing is hidden from either side.",
    },
    {
      title: "Creators apply",
      description:
        "Creators browse open campaigns and apply with a pitch. Brands can also invite specific creators.",
    },
    {
      title: "Both sides sign the agreement",
      description:
        "Each agreement version captures the scope and terms. Work only unlocks after both parties sign.",
    },
    {
      title: "Brand funds the campaign",
      description:
        "Funding is marked confirmed only after the payment provider confirms the transfer.",
    },
    {
      title: "Creator delivers, brand reviews",
      description:
        "Creators submit deliverables. The brand can request revisions within the agreed limit or approve.",
    },
    {
      title: "Payout to the creator",
      description:
        "Once every deliverable is approved, the platform initiates the creator's payout against their active payout method.",
    },
  ];
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-10 px-6 py-16">
      <header>
        <h1 className="text-3xl font-bold">How it works</h1>
        <p className="mt-2 text-slate-600">
          Clear deals. Verified funding. Defined deliverables.
        </p>
      </header>
      <ol className="flex flex-col gap-6">
        {steps.map((s, i) => (
          <li
            key={s.title}
            className="rounded-lg border border-slate-200 bg-white p-5"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">
              Step {i + 1}
            </p>
            <h2 className="mt-1 text-lg font-semibold">{s.title}</h2>
            <p className="mt-1 text-sm text-slate-600">{s.description}</p>
          </li>
        ))}
      </ol>
    </main>
  );
}
