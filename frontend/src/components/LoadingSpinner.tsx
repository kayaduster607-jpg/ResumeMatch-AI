export default function LoadingSpinner({ size = "md", text }: { size?: "sm" | "md" | "lg"; text?: string }) {
  const sizeClass = { sm: "w-5 h-5", md: "w-8 h-8", lg: "w-12 h-12" }[size];
  return (
    <div className="text-center py-6">
      <div className={`inline-block ${sizeClass} border-2 border-primary-600 border-t-transparent rounded-full animate-spin`} />
      {text && <p className="text-sm text-gray-500 mt-2">{text}</p>}
    </div>
  );
}
