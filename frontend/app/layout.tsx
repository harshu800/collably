import type { Metadata } from "next";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import { AppProviders } from "@/lib/providers";

export const metadata: Metadata = {
  title: "Collably",
  description:
    "Small steps. Big collabs. India-first marketplace pairing UGC creators and influencers with D2C brands.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider
      publishableKey={process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}
      appearance={{
        variables: {
          colorPrimary: "#7FB069",
          colorBackground: "#F6F1E6",
          colorText: "#1F2A24",
        },
      }}
    >
      <html lang="en">
        <body className="min-h-screen bg-white text-slate-900 antialiased">
          <AppProviders>{children}</AppProviders>
        </body>
      </html>
    </ClerkProvider>
  );
}
