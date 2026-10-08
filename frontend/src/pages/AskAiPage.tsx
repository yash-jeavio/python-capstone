import { useState } from "react";
import { askQuestion } from "../api/ai";

interface ChatTurn {
  question: string;
  state: "ok" | "unconfigured" | "failed";
  answer: string | null;
}

export function AskAiPage() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [isAsking, setIsAsking] = useState(false);

  async function handleSend() {
    const trimmed = question.trim();
    if (!trimmed || isAsking) return;
    setIsAsking(true);
    setQuestion("");
    const result = await askQuestion(trimmed);
    setTurns((prev) => [
      ...prev,
      {
        question: trimmed,
        state: result.state,
        answer: result.state === "ok" ? result.data.answer : null,
      },
    ]);
    setIsAsking(false);
  }

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="text-2xl font-bold">Ask AI</h1>
      <p className="mt-1 text-sm text-gray-500">Ask a question about the stored articles.</p>
      <div className="mt-4 space-y-4">
        {turns.map((turn, index) => (
          <div key={index} className="rounded-lg border border-gray-200 p-3">
            <p className="font-medium">{turn.question}</p>
            {turn.state === "ok" && <p className="mt-1 text-gray-700">{turn.answer}</p>}
            {turn.state === "unconfigured" && (
              <p className="mt-1 text-sm text-gray-500">AI features are not configured.</p>
            )}
            {turn.state === "failed" && (
              <p className="mt-1 text-sm text-gray-500">
                Couldn't answer that right now. Please try again.
              </p>
            )}
          </div>
        ))}
      </div>
      <div className="mt-4 flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask a question..."
          className="flex-1 rounded border border-gray-300 px-3 py-2"
        />
        <button
          onClick={handleSend}
          disabled={isAsking}
          className="rounded bg-orange-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {isAsking ? "Asking..." : "Send"}
        </button>
      </div>
    </div>
  );
}
