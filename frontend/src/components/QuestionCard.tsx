import type { InterviewQuestionItem } from "@/types/analysis";

interface Props {
  question: InterviewQuestionItem;
  selected?: boolean;
  onSelect?: () => void;
}

const TYPE_LABELS: Record<string, string> = {
  technical: "技术题",
  project: "项目题",
  gap_based: "差距题",
  scenario: "场景题",
  behavioral: "行为题",
};

const DIFF_COLOR: Record<string, string> = {
  easy: "bg-green-100 text-green-700",
  medium: "bg-yellow-100 text-yellow-700",
  hard: "bg-red-100 text-red-700",
};

export default function QuestionCard({ question, selected, onSelect }: Props) {
  return (
    <div
      className={`border rounded-lg p-4 cursor-pointer transition-all ${
        selected
          ? "border-primary-400 bg-primary-50 ring-2 ring-primary-200"
          : "border-gray-200 hover:border-gray-300"
      }`}
      onClick={onSelect}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600 font-medium">
          {TYPE_LABELS[question.question_type] || question.question_type}
        </span>
        <span className={`text-xs px-2 py-0.5 rounded font-medium ${DIFF_COLOR[question.difficulty] || ""}`}>
          {question.difficulty}
        </span>
      </div>
      <p className="text-sm font-medium text-gray-800 mb-2">{question.question}</p>
      <p className="text-xs text-gray-500 mb-2">
        <span className="font-medium">考察意图：</span> {question.why_ask}
      </p>
      <details className="text-xs text-gray-600">
        <summary className="cursor-pointer text-primary-600 font-medium">
          参考答案
        </summary>
        <p className="mt-1 pl-3 border-l-2 border-gray-200">
          {question.reference_answer}
        </p>
      </details>
    </div>
  );
}
