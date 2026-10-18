import { scoreColor } from "@/utils/scoreColor";

interface Props {
  scores: { label: string; value: number }[];
}

export default function ScoreChart({ scores }: Props) {
  return (
    <div className="space-y-3">
      {scores.map((s) => (
        <div key={s.label}>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">{s.label}</span>
            <span className="font-medium text-gray-800">{s.value.toFixed(1)}</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-2.5">
            <div
              className="h-2.5 rounded-full transition-all duration-500"
              style={{
                width: `${(s.value / 100) * 100}%`,
                backgroundColor: scoreColor(s.value),
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
