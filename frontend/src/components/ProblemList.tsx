import type { DiagnosisIssue } from "@/types/analysis";

interface Props {
  problems: DiagnosisIssue[];
}

const SEVERITY_STYLE: Record<string, string> = {
  high: "bg-red-50 border-red-200 text-red-800",
  medium: "bg-yellow-50 border-yellow-200 text-yellow-800",
  low: "bg-blue-50 border-blue-200 text-blue-800",
};

export default function ProblemList({ problems }: Props) {
  if (!problems.length) {
    return <p className="text-sm text-gray-400">未发现问题。</p>;
  }

  return (
    <div className="space-y-3">
      {problems.map((p, i) => (
        <div
          key={i}
          className={`border rounded-lg p-4 ${SEVERITY_STYLE[p.severity] || SEVERITY_STYLE.low}`}
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold uppercase px-2 py-0.5 rounded bg-white/50">
              {p.severity}
            </span>
            <span className="font-medium text-sm">{p.title}</span>
          </div>
          <p className="text-xs mt-1 opacity-80">{p.evidence}</p>
          <p className="text-xs mt-2 font-medium">建议：{p.suggestion}</p>
        </div>
      ))}
    </div>
  );
}
