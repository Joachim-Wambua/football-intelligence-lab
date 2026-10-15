"use client";
import { ErrorState } from "@/components/ui";
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ErrorState message="The workspace encountered an unexpected error." retry={reset}/>;
}
