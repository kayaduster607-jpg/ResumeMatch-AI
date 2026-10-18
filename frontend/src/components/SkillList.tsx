interface Props {
  title: string;
  skills: string[];
  variant?: "matched" | "missing" | "default";
}

export default function SkillList({ title, skills, variant = "default" }: Props) {
  const badgeClass =
    variant === "matched"
      ? "bg-green-50 text-green-700 border-green-200"
      : variant === "missing"
      ? "bg-red-50 text-red-700 border-red-200"
      : "bg-gray-50 text-gray-700 border-gray-200";

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">{title}</h3>
      {skills.length === 0 ? (
        <p className="text-xs text-gray-400">无</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {skills.map((s) => (
            <span
              key={s}
              className={`text-xs px-2.5 py-1 rounded-full border ${badgeClass}`}
            >
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
