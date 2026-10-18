import { Link } from "react-router-dom";

const features = [
  { icon: "📄", title: "PDF 简历解析", desc: "上传 PDF，自动提取教育背景、技能、项目经历和工作经验等结构化数据。" },
  { icon: "📋", title: "JD 结构化解析", desc: "粘贴职位描述文本，自动提取所需技能、职责和任职资格。" },
  { icon: "📊", title: "多维度评分", desc: "技能匹配 (40%)、项目相关性 (25%)、语义相似度 (20%)、硬性要求 (15%)。" },
  { icon: "🔍", title: "技能差距分析", desc: "识别已匹配和缺失的技能，支持别名规范化（如 py → Python）。" },
  { icon: "🩺", title: "简历诊断", desc: "检测 10 类问题：描述模糊、缺少量化指标、角色不清晰等。" },
  { icon: "🎤", title: "面试准备", desc: "生成针对性面试问题，支持 AI 辅助作答评分练习。" },
];

export default function HomePage() {
  return (
    <div className="space-y-12">
      {/* Hero */}
      <section className="text-center py-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          AI 简历 & JD 匹配分析
        </h1>
        <p className="text-gray-600 max-w-2xl mx-auto text-lg">
          上传简历，粘贴职位描述，获取 AI 驱动的匹配评分、技能差距分析、简历诊断和面试准备建议。
        </p>
        <div className="flex justify-center gap-4 mt-8">
          <Link
            to="/upload"
            className="px-6 py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 transition-colors"
          >
            开始使用
          </Link>
          <Link
            to="/interview"
            className="px-6 py-3 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 transition-colors"
          >
            面试练习
          </Link>
        </div>
      </section>

      {/* Features */}
      <section>
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-8">核心功能</h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f) => (
            <div key={f.title} className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md transition-shadow">
              <div className="text-3xl mb-3">{f.icon}</div>
              <h3 className="font-semibold text-gray-800 mb-2">{f.title}</h3>
              <p className="text-sm text-gray-500">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Tech Stack */}
      <section className="bg-white rounded-xl border border-gray-200 p-8">
        <h2 className="text-xl font-bold text-gray-900 mb-4">技术栈</h2>
        <div className="grid md:grid-cols-2 gap-6 text-sm">
          <div>
            <h4 className="font-semibold text-gray-700 mb-2">Backend</h4>
            <p className="text-gray-500">Python · FastAPI · SQLAlchemy · Pydantic · PyMuPDF · sentence-transformers · MySQL</p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-700 mb-2">Frontend</h4>
            <p className="text-gray-500">React · TypeScript · Vite · Tailwind CSS · Recharts · React Router</p>
          </div>
        </div>
      </section>
    </div>
  );
}
