"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  payoutMethodSchema,
  type PayoutMethodInput,
} from "@/lib/zod/payout";
import {
  useMyPayoutMethod,
  useSavePayoutMethod,
} from "@/lib/api/queries";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { FormField, FormMessage } from "@/components/ui/form";
import { Alert } from "@/components/ui/alert";
import { useToast } from "@/components/ui/toast";

export default function PayoutMethodPage() {
  const q = useMyPayoutMethod();
  const save = useSavePayoutMethod();
  const { push } = useToast();
  const [serverError, setServerError] = React.useState<string | null>(null);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<PayoutMethodInput>({
    resolver: zodResolver(payoutMethodSchema),
    defaultValues: { method: "upi" } as unknown as PayoutMethodInput,
  });

  const method = watch("method");

  const submit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      await save.mutateAsync(
        Object.fromEntries(
          Object.entries(values).filter(([, v]) => v !== undefined && v !== ""),
        ),
      );
      push({ title: "Payout method saved", tone: "success" });
      reset({ method: values.method } as unknown as PayoutMethodInput);
    } catch (e) {
      setServerError(
        e instanceof Error ? e.message : "Could not save payout method.",
      );
    }
  });

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Payout method</h1>
      <Card>
        <CardHeader>
          <CardTitle>Current method</CardTitle>
        </CardHeader>
        <CardContent>
          {q.isLoading ? (
            <LoadingState />
          ) : q.isError ? (
            <ErrorState onRetry={() => q.refetch()} />
          ) : !q.data ? (
            <Alert tone="warning">No payout method on file.</Alert>
          ) : (
            (() => {
              const pm = q.data;
              return (
                <dl className="grid gap-2 text-sm sm:grid-cols-2">
                  <dt className="text-slate-500">Method</dt>
                  <dd className="uppercase">{pm.method}</dd>
                  <dt className="text-slate-500">Holder</dt>
                  <dd>{pm.holder_name}</dd>
                  {pm.method === "upi" ? (
                    <>
                      <dt className="text-slate-500">UPI</dt>
                      <dd>{pm.upi_vpa_masked ?? "—"}</dd>
                    </>
                  ) : (
                    <>
                      <dt className="text-slate-500">Account</dt>
                      <dd>•••• {pm.account_number_last4}</dd>
                    </>
                  )}
                  <dt className="text-slate-500">Verified</dt>
                  <dd>{pm.verified ? "Yes" : "No (not yet implemented)"}</dd>
                </dl>
              );
            })()
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Update method</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} noValidate className="flex flex-col gap-4">
            <FormField>
              <Label htmlFor="pm-method">Method</Label>
              <Select id="pm-method" {...register("method")}>
                <option value="upi">UPI</option>
                <option value="bank">Bank account</option>
              </Select>
            </FormField>
            <FormField>
              <Label htmlFor="pm-holder">Holder name</Label>
              <Input id="pm-holder" {...register("holder_name")} />
              <FormMessage>{errors.holder_name?.message}</FormMessage>
            </FormField>
            {method === "upi" ? (
              <FormField>
                <Label htmlFor="pm-upi">UPI VPA</Label>
                <Input
                  id="pm-upi"
                  placeholder="name@okbank"
                  {...register("upi_vpa" as const)}
                />
                <FormMessage>
                  {(errors as Record<string, { message?: string } | undefined>).upi_vpa?.message}
                </FormMessage>
              </FormField>
            ) : (
              <>
                <FormField>
                  <Label htmlFor="pm-acct">Account number</Label>
                  <Input
                    id="pm-acct"
                    {...register("account_number" as const)}
                  />
                  <FormMessage>
                    {(errors as Record<string, { message?: string } | undefined>)
                      .account_number?.message}
                  </FormMessage>
                </FormField>
                <FormField>
                  <Label htmlFor="pm-ifsc">IFSC</Label>
                  <Input id="pm-ifsc" {...register("ifsc" as const)} />
                  <FormMessage>
                    {(errors as Record<string, { message?: string } | undefined>).ifsc?.message}
                  </FormMessage>
                </FormField>
              </>
            )}
            {serverError ? <Alert tone="danger">{serverError}</Alert> : null}
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : "Save method"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
