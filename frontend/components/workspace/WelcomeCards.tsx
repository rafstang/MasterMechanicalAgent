"use client";

import { useCopilotChatInternal } from "@copilotkit/react-core";
import { randomUUID } from "@copilotkit/shared";
import { useCallback, useState } from "react";

const SUGGESTIONS = [
  {
    title: "Receivables",
    prompt: "Who owes us the most right now?",
  },
  {
    title: "Jobs this week",
    prompt: "What jobs are scheduled this week?",
  },
  {
    title: "Employees",
    prompt: "Who are our employees?",
  },
  {
    title: "Upload data",
    prompt: "I attached a spreadsheet — summarize the columns and first few rows.",
  },
] as const;

export function WelcomeCards() {
  const { sendMessage, isLoading } = useCopilotChatInternal();
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);

  const runSuggestion = useCallback(
    async (prompt: string) => {
      if (isLoading || pendingPrompt) return;
      setPendingPrompt(prompt);
      try {
        await sendMessage({
          id: randomUUID(),
          role: "user",
          content: prompt,
        });
      } finally {
        setPendingPrompt(null);
      }
    },
    [isLoading, pendingPrompt, sendMessage]
  );

  return (
    <div className="mx-auto w-full max-w-3xl">
      <h2 className="text-lg font-semibold text-zinc-900">Welcome back</h2>
      <p className="mt-2 text-sm text-zinc-600">
        Ask about HVAC topics or your BigQuery customer and job data. Attach PDF, CSV, text, or Excel
        files in the chat panel. Drag the sidebar edge to widen it for tables.
      </p>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map((item) => {
          const isPending = pendingPrompt === item.prompt;
          const disabled = isLoading || Boolean(pendingPrompt);
          return (
            <button
              key={item.title}
              type="button"
              disabled={disabled}
              onClick={() => void runSuggestion(item.prompt)}
              className="rounded-xl border border-zinc-200 bg-white px-4 py-3 text-left shadow-sm transition hover:border-zinc-300 hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span className="block text-sm font-medium text-zinc-900">
                {item.title}
                {isPending ? "…" : ""}
              </span>
              <span className="mt-1 block text-xs text-zinc-500">{item.prompt}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
