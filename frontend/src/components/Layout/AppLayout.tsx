import { Outlet, Link, useLocation } from "react-router-dom";

const navItems = [
  { path: "/upload", label: "上传简历" },
  { path: "/jd", label: "搜索/输入JD" },
  { path: "/analysis", label: "分析匹配" },
  { path: "/interview", label: "面试准备" },
];

export default function AppLayout() {
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold text-primary-600">
            AI 简历 JD 匹配器
          </Link>
          <nav className="flex gap-6">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`text-sm font-medium transition-colors ${
                  pathname === item.path
                    ? "text-primary-600"
                    : "text-gray-500 hover:text-gray-900"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
