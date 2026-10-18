import { useRef, useState } from "react";

interface Props {
  onFileSelect: (file: File) => void;
  loading?: boolean;
  accept?: string;
}

export default function FileUpload({ onFileSelect, loading, accept = ".pdf" }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [fileName, setFileName] = useState("");

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    if (accept === ".pdf" && file.type !== "application/pdf") {
      alert("仅支持 PDF 文件");
      return;
    }
    setFileName(file.name);
    onFileSelect(file);
  };

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-10 text-center transition-colors cursor-pointer ${
        dragOver
          ? "border-primary-400 bg-primary-50"
          : "border-gray-300 hover:border-primary-400"
      } ${loading ? "opacity-50 pointer-events-none" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFile(e.dataTransfer.files[0]);
      }}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      <div className="text-4xl mb-3">📄</div>
      {fileName ? (
        <p className="text-sm text-gray-700 font-medium">{fileName}</p>
      ) : (
        <>
          <p className="text-gray-600 font-medium">拖拽或点击选择文件</p>
          <p className="text-xs text-gray-400 mt-1">仅 PDF，最大 10MB</p>
        </>
      )}
    </div>
  );
}
