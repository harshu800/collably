export default function FaqPage() {
  const faqs = [
    {
      q: "Is this live?",
      a: "It is in active development. Payments run through a mock provider so you can rehearse the full flow without real money moving.",
    },
    {
      q: "Who verifies the follower counts I enter?",
      a: "Nobody. Social-handle follower counts are self-reported, and the platform tags them as unverified. We do not misrepresent reach.",
    },
    {
      q: "How do payouts work?",
      a: "You add a payout method (UPI VPA or bank + IFSC). Once the brand funds and the deliverable is approved, we initiate a payout against the stored method. Timing depends on the provider.",
    },
    {
      q: "Can I pick who I collaborate with?",
      a: "Yes. Brands can invite creators directly; creators choose which campaigns to apply to.",
    },
    {
      q: "Who holds the funds between funding and payout?",
      a: "An integration with a licensed payment provider will. In this early build it is a mock. Nothing here is escrow until stated otherwise.",
    },
  ];
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-16">
      <header>
        <h1 className="text-3xl font-bold">Frequently asked</h1>
      </header>
      <dl className="flex flex-col gap-5">
        {faqs.map((f) => (
          <div
            key={f.q}
            className="rounded-lg border border-slate-200 bg-white p-5"
          >
            <dt className="font-semibold">{f.q}</dt>
            <dd className="mt-1 text-sm text-slate-600">{f.a}</dd>
          </div>
        ))}
      </dl>
    </main>
  );
}
