"use client";

import * as React from "react";
import { useAuth, useClerk } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import {
  apiFetch,
  ApiError,
  type ApiRequestOptions,
} from "./client";

type RequestOpts = Omit<ApiRequestOptions, "method" | "token">;

export interface ApiClient {
  get: <T>(path: string, opts?: RequestOpts) => Promise<T>;
  post: <T>(path: string, opts?: RequestOpts) => Promise<T>;
  put: <T>(path: string, opts?: RequestOpts) => Promise<T>;
  patch: <T>(path: string, opts?: RequestOpts) => Promise<T>;
  delete: <T>(path: string, opts?: RequestOpts) => Promise<T>;
}

/**
 * Returns a token-bound API client. Every call mints a fresh Clerk JWT via
 * getToken(). A 401 response signs the user out and routes to /sign-in before
 * rethrowing the ApiError so callers can still surface the failure.
 */
export function useApi(): ApiClient {
  const { getToken } = useAuth();
  const { signOut } = useClerk();
  const router = useRouter();

  return React.useMemo<ApiClient>(() => {
    async function request<T>(
      method: string,
      path: string,
      opts: RequestOpts = {},
    ): Promise<T> {
      const token = (await getToken()) ?? undefined;
      try {
        return await apiFetch<T>(path, { ...opts, method, token });
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          await signOut();
          router.push("/sign-in");
        }
        throw e;
      }
    }
    return {
      get: <T>(p: string, o?: RequestOpts) => request<T>("GET", p, o),
      post: <T>(p: string, o?: RequestOpts) => request<T>("POST", p, o),
      put: <T>(p: string, o?: RequestOpts) => request<T>("PUT", p, o),
      patch: <T>(p: string, o?: RequestOpts) => request<T>("PATCH", p, o),
      delete: <T>(p: string, o?: RequestOpts) => request<T>("DELETE", p, o),
    };
  }, [getToken, signOut, router]);
}
