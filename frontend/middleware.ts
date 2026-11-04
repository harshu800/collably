import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// Dashboard route groups `(dashboard)` resolve to the top-level creator/brand/admin
// URL prefixes at runtime, so we protect those plus /onboarding. Everything else
// (/, /how-it-works, /pricing, /faq, /terms, /privacy, /creators/**, /campaigns/**,
// /sign-in/**, /sign-up/**) is public.
const isProtectedRoute = createRouteMatcher([
  "/creator(.*)",
  "/brand(.*)",
  "/admin(.*)",
  "/onboarding(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    "/((?!_next|.*\\.(?:css|js|svg|png|jpg|jpeg|gif|webp|ico|json|txt|map)).*)",
    "/(api|trpc)(.*)",
  ],
};
