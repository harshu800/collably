"use client";

import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <main className="mx-auto flex max-w-md flex-col items-center gap-6 px-6 py-16">
      <SignUp />
    </main>
  );
}
