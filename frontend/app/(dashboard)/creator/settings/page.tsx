"use client";

import { useClerk, useUser } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function CreatorSettingsPage() {
  const { signOut } = useClerk();
  const { user } = useUser();
  const email = user?.primaryEmailAddress?.emailAddress ?? "";
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Settings</h1>
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 text-sm">
          <p>
            Signed in as <span className="font-medium">{email}</span>.
          </p>
          <div>
            <Button
              variant="outline"
              onClick={() => signOut({ redirectUrl: "/sign-in" })}
            >
              Sign out
            </Button>
          </div>
          <p className="text-slate-500">
            Account deactivation is handled through admin review. Contact
            support if you need to deactivate.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
