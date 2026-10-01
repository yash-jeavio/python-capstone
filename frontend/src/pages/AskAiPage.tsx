import { useState } from "react";
import { askQuestion } from "../api/ai";

interface ChatTurn {
  question: string;
  answer: string | null;
  available: boolean;
}

export function AskAiPage() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [isAsking, setIsAsking] = useState(false);

  async function handleSend() {
    const trimmed = question.trim();
    if (!trimmed) return;
    setIsAsking(true);
    setQuestion("");
    const result = await askQuestion(trimmed);
    setTurns((prev) => [
      ...prev,
      { question: trimmed, answer: result.available ? result.data.answer : null, available: result.available },
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
            {turn.available ? (
              <p className="mt-1 text-gray-700">{turn.answer}</p>
            ) : (
              <span className="mt-1 inline-block rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-500">
                Ask AI — coming in Phase 2
              </span>
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
