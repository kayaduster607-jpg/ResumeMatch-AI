interface Props {
  totalScore: number;
  matchLevel: string;
  conclusion: string;
}

export default function ReportSummary({ totalScore, matchLevel, conclusion }: Props) {
  const color =
    totalScore >= 80
      ? "text-green-600"
      : totalScore >= 60
      ? "text-yellow-600"
      : "text-red-600";

  return (
    <div className="bg-gradient-to-r from-primary-50 to-blue-50 rounded-xl p-6 border border-primary-100">
      <div className="flex items-center gap-6">
        <div className="text-center">
          <p className={`text-5xl font-bold ${color}`}>{totalScore.toFixed(1)}</p>
          <p className="text-sm text-gray-500 mt-1">总分</p>
        </div>
        <div className="border-l border-primary-200 pl-6">
          <p className="text-lg font-semibold text-gray-800">{matchLevel}</p>
          <p className="text-sm text-gray-600 mt-1">{conclusion}</p>
        </div>
      </div>
    </div>
  );
}
