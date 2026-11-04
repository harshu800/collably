"use client";

import {
  useAdminCollaborations,
  useAdminDisputes,
  useAdminReports,
  useAdminUsers,
} from "@/lib/api/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";

export default function AdminOverviewPage() {
  const users = useAdminUsers();
  const collabs = useAdminCollaborations();
  const reports = useAdminReports();
  const disputes = useAdminDisputes();

  if (users.isLoading || collabs.isLoading || reports.isLoading || disputes.isLoading) {
    return <LoadingState />;
  }
  if (users.isError || collabs.isError || reports.isError || disputes.isError) {
    return <ErrorState description="Could not load admin stats." />;
  }
  const stats = [
    { label: "Users", value: users.data?.length ?? 0 },
    {
      label: "Active collaborations",
      value:
        (collabs.data ?? []).filter(
          (c) => !["completed", "cancelled"].includes(c.status),
        ).length,
    },
    {
      label: "Open reports",
      value: (reports.data ?? []).filter((r) => r.status === "open").length,
    },
    {
      label: "Open disputes",
      value: (disputes.data ?? []).filter((d) => d.status === "open").length,
    },
  ];
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Admin overview</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardHeader>
              <CardTitle>{s.label}</CardTitle>
            </CardHeader>
            <CardContent className="text-3xl font-semibold">
              {s.value}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
