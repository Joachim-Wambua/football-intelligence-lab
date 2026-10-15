import type { Metadata } from "next";
import { ThemeProvider } from "@/components/theme-provider";
import { Shell } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = { title: "Football Intelligence Lab", description: "A tactical workspace for football match and player analysis." };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" suppressHydrationWarning><body><ThemeProvider><Shell>{children}</Shell></ThemeProvider></body></html>;
}
