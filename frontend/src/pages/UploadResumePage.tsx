import { useState } from "react";
import { useNavigate } from "react-router-dom";
import FileUpload from "@/components/FileUpload";
import LoadingSpinner from "@/components/LoadingSpinner";
import ErrorAlert from "@/components/ErrorAlert";
import { parseResume, uploadResume } from "@/api/resumeApi";

export default function UploadResumePage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [parseStatus, setParseStatus] = useState("");
  const [result, setResult] = useState<{
    resume_id: number;
    filename: string;
    text_preview: string;
  } | null>(null);

  const handleUpload = async (file: File) => {
    setLoading(true);
    setError("");
    setParseStatus("");
    setResult(null);
    try {
      const res = await uploadResume(file);
      setResult(res.data);
      localStorage.setItem("latest_resume_id", String(res.data.resume_id));
      localStorage.setItem("latest_resume_filename", res.data.filename);
      // 立即解析结构化简历，避免分析页提示“Resume has not been parsed”。
      setParseStatus("正在结构化解析简历...");
      await parseResume(res.data.resume_id);
      setParseStatus("简历已上传并解析完成，后续岗位搜索和匹配分析会自动使用这份简历。");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "上传或解析简历失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">上传简历</h1>
        <p className="text-sm text-gray-500 mt-1">
          上传 PDF 格式的简历，系统会提取文本并自动完成结构化解析。
        </p>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
        <strong>注意：</strong>支持文字型 PDF 和扫描件 PDF（通过 OCR 识别）。扫描件识别需安装 Tesseract 中文语言包。
      </div>

      <FileUpload onFileSelect={handleUpload} loading={loading} />

      {loading && <LoadingSpinner text={parseStatus || "正在解析 PDF 和结构化简历..."} size="sm" />}

      {error && <ErrorAlert message={error} />}

      {result && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-semibold text-green-800">上传成功</h3>
            <button
              onClick={() => navigate("/jd")}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm hover:bg-primary-700"
            >
              下一步：输入或搜索岗位
            </button>
          </div>
          {parseStatus && <p className="text-sm text-green-700">{parseStatus}</p>}
          <div className="text-sm space-y-1">
            <p><span className="font-medium">当前简历：</span> {result.filename}</p>
            <p><span className="font-medium">系统记录：</span> 已保存为最近使用的简历</p>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-700 mb-1">文本预览：</p>
            <pre className="text-xs bg-white rounded p-3 border border-gray-200 max-h-48 overflow-auto whitespace-pre-wrap text-gray-600">
              {result.text_preview}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
