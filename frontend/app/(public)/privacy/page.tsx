export default function PrivacyPage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-16 text-slate-700">
      <h1 className="text-3xl font-bold text-slate-900">Privacy policy</h1>
      <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
        Placeholder. A full privacy policy consistent with Indian data
        protection law will be published before this platform processes real
        payments.
      </p>
      <p>
        We collect the information you give us (email, profile, payout
        details) and operational metadata needed to run the service
        (timestamps, status transitions, audit records).
      </p>
      <p>
        Payout fields are encrypted at rest. Logs do not include plaintext
        payout details. Private files are only served through signed download
        URLs.
      </p>
      <p>
        You can request deletion of your account; some records (audit logs,
        completed payments) are retained for legal and accounting reasons.
      </p>
    </main>
  );
}
