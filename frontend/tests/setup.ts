import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

if (typeof window !== "undefined") Object.defineProperty(window, "matchMedia", { writable: true, value: (query: string) => ({
  matches: query.includes("dark"), media: query, onchange: null,
  addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
}) });
afterEach(() => {
  cleanup();
  if (typeof localStorage !== "undefined") localStorage.clear();
  vi.unstubAllGlobals();
});
