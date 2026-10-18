import { scoreColor } from "@/utils/scoreColor";

interface Props {
  label: string;
  score: number;
  reason?: string;
  color?: string;
}

export default function ScoreCard({ label, score, reason, color }: Props) {
  const bgColor = color || scoreColor(score);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm text-gray-500 mb-1">{label}</p>
      <div className="flex items-end gap-2">
        <span className="text-3xl font-bold" style={{ color: bgColor }}>
          {score.toFixed(1)}
        </span>
        <span className="text-sm text-gray-400 mb-1">/ 100</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2 mt-3">
        <div
          className="h-2 rounded-full transition-all duration-500"
          style={{ width: `${Math.min(100, score)}%`, backgroundColor: bgColor }}
        />
      </div>
      {reason && <p className="text-xs text-gray-400 mt-2">{reason}</p>}
    </div>
  );
}
