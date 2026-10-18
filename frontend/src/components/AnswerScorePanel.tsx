import { useState } from "react";
import { scoreAnswer } from "@/api/interviewApi";
import type { MockInterviewResult } from "@/types/interview";

interface Props {
  question: string;
  questionType: string;
}

const LEVEL_COLOR: Record<string, string> = {
  excellent: "text-green-600",
  good: "text-blue-600",
  fair: "text-yellow-600",
  needs_improvement: "text-red-600",
};

export default function AnswerScorePanel({ question, questionType }: Props) {
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MockInterviewResult | null>(null);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!answer.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await scoreAnswer({ question, answer, question_type: questionType });
      setResult(res.data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border-t pt-4 mt-4 space-y-4">
      <h4 className="text-sm font-semibold text-gray-700">你的回答</h4>
      <textarea
        className="w-full border border-gray-300 rounded-lg p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        rows={5}
        placeholder="在此输入你的回答..."
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
      />
      <button
        onClick={handleSubmit}
        disabled={loading || !answer.trim()}
        className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? "评分中..." : "对我的回答评分"}
      </button>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {result && (
        <div className="bg-gray-50 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-3xl font-bold text-primary-600">{result.score}</span>
            <span className={`text-sm font-medium ${LEVEL_COLOR[result.level] || ""}`}>
              {result.level.replace("_", " ")}
            </span>
          </div>

          {result.strengths.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-green-700 mb-1">优点</p>
              <ul className="text-xs text-gray-600 space-y-1">
                {result.strengths.map((s, i) => <li key={i}>+ {s}</li>)}
              </ul>
            </div>
          )}

          {result.weaknesses.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-red-700 mb-1">不足</p>
              <ul className="text-xs text-gray-600 space-y-1">
                {result.weaknesses.map((w, i) => <li key={i}>- {w}</li>)}
              </ul>
            </div>
          )}

          {result.suggestions.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-blue-700 mb-1">建议</p>
              <ul className="text-xs text-gray-600 space-y-1">
                {result.suggestions.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}

          {result.improved_answer && (
            <div>
              <p className="text-xs font-semibold text-gray-700 mb-1">改进回答</p>
              <p className="text-xs text-gray-600 whitespace-pre-line">{result.improved_answer}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
