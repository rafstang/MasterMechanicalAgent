"use client";

import { useCopilotChatHeadless_c } from "@copilotkit/react-core";

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
  const { sendMessage } = useCopilotChatHeadless_c();

  return (
    <div className="mx-auto w-full max-w-3xl">
      <h2 className="text-lg font-semibold text-zinc-900">Welcome back</h2>
      <p className="mt-2 text-sm text-zinc-600">
        Ask about HVAC topics or your BigQuery customer and job data. Attach PDF, CSV, text, or Excel
        files in the chat panel. Drag the sidebar edge to widen it for tables.
      </p>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map((item) => (
          <button
            key={item.title}
            type="button"
            onClick={() =>
              sendMessage({
                id: crypto.randomUUID(),
                role: "user",
                content: item.prompt,
              })
            }
            className="rounded-xl border border-zinc-200 bg-white px-4 py-3 text-left shadow-sm transition hover:border-zinc-300 hover:bg-zinc-50"
          >
            <span className="block text-sm font-medium text-zinc-900">{item.title}</span>
            <span className="mt-1 block text-xs text-zinc-500">{item.prompt}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
