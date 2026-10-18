interface Props {
  title: string;
  items: { priority?: number; action: string; reason: string }[];
}

export default function SuggestionList({ title, items }: Props) {
  if (!items.length) return null;

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-3">{title}</h3>
      <ol className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="flex gap-3 text-sm">
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-xs font-bold">
              {item.priority ?? i + 1}
            </span>
            <div>
              <p className="text-gray-800">{item.action}</p>
              <p className="text-xs text-gray-400">{item.reason}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
