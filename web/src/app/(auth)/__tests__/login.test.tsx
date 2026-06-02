/**
 * Failing tests for login page — must fail before login/page.tsx is implemented.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import LoginPage from "../login/page";

// Mock Supabase auth — login page calls supabase.auth.signInWithOtp
vi.mock("@/lib/supabase", () => ({
  createAuthBrowserClient: () => ({
    auth: {
      signInWithOtp: vi.fn().mockResolvedValue({ data: {}, error: null }),
    },
  }),
}));

describe("LoginPage", () => {
  it("renders email input and submit button", () => {
    render(<LoginPage />);
    expect(screen.getByRole("textbox", { name: /email/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send magic link/i })).toBeInTheDocument();
  });

  it("transitions to confirmation state after submit", async () => {
    render(<LoginPage />);

    fireEvent.change(screen.getByRole("textbox", { name: /email/i }), {
      target: { value: "test@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send magic link/i }));

    await waitFor(() => {
      expect(screen.getByText(/check your email/i)).toBeInTheDocument();
    });
  });

  it("does not show confirmation before submit", () => {
    render(<LoginPage />);
    expect(screen.queryByText(/check your email/i)).not.toBeInTheDocument();
  });
});
