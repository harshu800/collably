"use client";

import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <main className="mx-auto flex max-w-md flex-col items-center gap-6 px-6 py-16">
      <SignIn />
    </main>
  );
}
