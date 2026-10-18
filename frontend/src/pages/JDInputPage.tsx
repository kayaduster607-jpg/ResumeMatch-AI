import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import LoadingSpinner from "@/components/LoadingSpinner";
import ErrorAlert from "@/components/ErrorAlert";
import {
  createJD,
  openLoginBrowser,
  parseJD,
  saveLoginState,
  searchJobsFromPlatforms,
  collectCurrentEdgePages,
  closeJobBrowser,
  clearPlatformCache,
} from "@/api/jdApi";
import type { ParsedJD, PlatformJobItem } from "@/types/jd";

const PLATFORM_OPTIONS = [
  { id: "boss", label: "BOSS直聘" },
  { id: "zhaopin", label: "智联招聘" },
  { id: "liepin", label: "猎聘" },
  { id: "qiancheng", label: "前程无忧" },
];

export default function JDInputPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"manual" | "search">("search");

  // Manual JD state
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [rawText, setRawText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [jdId, setJdId] = useState<number | null>(null);
  const [parsed, setParsed] = useState<ParsedJD | null>(null);

  // Platform search state
  const [keyword, setKeyword] = useState(localStorage.getItem("latest_job_keyword") || "AI开发实习生");
  const [city, setCity] = useState(localStorage.getItem("latest_job_city") || "广州");
  const [pages, setPages] = useState(1);
  const [minScore, setMinScore] = useState(50);
  const [top, setTop] = useState(50);
  const [strictCity, setStrictCity] = useState(true);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(PLATFORM_OPTIONS.map((p) => p.id));
  const [loginLoading, setLoginLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [importingId, setImportingId] = useState<string | null>(null);
  const [loginMessage, setLoginMessage] = useState("");
  const [activePlatformFilter, setActivePlatformFilter] = useState<string | null>(null);
  const [jobType, setJobType] = useState(localStorage.getItem("latest_job_type") || "");
  const [filterExperience, setFilterExperience] = useState(localStorage.getItem("latest_filter_experience") || "");
  const [filterEducation, setFilterEducation] = useState(localStorage.getItem("latest_filter_education") || "");
  const [forceRefresh, setForceRefresh] = useState(false);

  const latestResumeId = useMemo(() => {
    const raw = localStorage.getItem("latest_resume_id");
    const value = raw ? Number(raw) : NaN;
    return Number.isFinite(value) && value > 0 ? value : null;
  }, []);
  const latestResumeName = localStorage.getItem("latest_resume_filename") || "未选择简历";

  // Restore persisted search results on mount (no network request)
  const [jobs, setJobs] = useState<PlatformJobItem[]>(() => {
    try {
      const raw = localStorage.getItem("latest_search_jobs");
      return raw ? JSON.parse(raw) : [];
    } catch { return []; }
  });
  const [searchMessage, setSearchMessage] = useState(localStorage.getItem("latest_search_message") || "");
  const [searchFromCache, setSearchFromCache] = useState(localStorage.getItem("latest_search_from_cache") === "1");
  const [searchErrors, setSearchErrors] = useState<Array<{ platform?: string; platform_name?: string; message: string; bookmarklet?: { method: string; title: string; steps: string[]; code: string } }>>([]);

  const handleSubmit = async () => {
    if (!title.trim() || !rawText.trim()) {
      setError("请填写职位标题和 JD 内容");
      return;
    }
    setLoading(true);
    setError("");
    setParsed(null);
    try {
      const createRes = await createJD({ title, company, raw_text: rawText });
      const id = createRes.data.jd_id;
      setJdId(id);
      localStorage.setItem("latest_jd_id", String(id));
      localStorage.setItem("latest_jd_title", title.trim());

      const parseRes = await parseJD(id);
      setParsed(parseRes.data.parsed_json);
    } catch (e: any) {
      setError(e.message || "保存解析 JD 失败");
    } finally {
      setLoading(false);
    }
  };

  const togglePlatform = (id: string) => {
    setSelectedPlatforms((prev) => {
      if (prev.includes(id)) return prev.filter((item) => item !== id);
      return [...prev, id];
    });
  };

  const selectAllPlatforms = () => setSelectedPlatforms(PLATFORM_OPTIONS.map((p) => p.id));

  const handleOpenLogin = async () => {
    setLoginLoading(true);
    setError("");
    setLoginMessage("");
    try {
      const res = await openLoginBrowser(selectedPlatforms.length ? selectedPlatforms : ["all"]);
      setLoginMessage(res.data.message || "已打开浏览器登录页");
    } catch (e: any) {
      setError(e.message || "打开浏览器失败");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleSaveLogin = async () => {
    setLoginLoading(true);
    setError("");
    setLoginMessage("");
    try {
      const res = await saveLoginState();
      setLoginMessage(res.data.message || "登录状态已保存");
    } catch (e: any) {
      setError(e.message || "保存登录状态失败");
    } finally {
      setLoginLoading(false);
    }
  };

  const buildPlatformSearchRequest = () => ({
    keyword: keyword.trim(),
    city: city.trim(),
    platforms: selectedPlatforms,
    pages,
    min_score: minScore,
    top,
    strict_city: strictCity,
    resume_id: latestResumeId,
    timeout_ms: 60000,
    render_wait_ms: 5000,
    job_type: jobType || undefined,
    experience: filterExperience || undefined,
    education: filterEducation || undefined,
    force_refresh: forceRefresh,
  });

  const handleSearchJobs = async () => {
    if (!keyword.trim()) {
      setError("请先填写要搜索的岗位，例如：AI开发实习生 / Python后端 / 产品经理");
      return;
    }
    if (!city.trim()) {
      setError("请先填写目标城市，例如：广州 / 深圳 / 上海");
      return;
    }
    if (!selectedPlatforms.length) {
      setError("请至少选择一个招聘平台");
      return;
    }

    setSearchLoading(true);
    setError("");
    setSearchMessage("");
    setJobs([]);
    setSearchFromCache(false);
    localStorage.setItem("latest_job_keyword", keyword.trim());
    localStorage.setItem("latest_job_city", city.trim());
    // Persist all filter settings so cache key matches on return
    localStorage.setItem("latest_job_type", jobType);
    localStorage.setItem("latest_filter_experience", filterExperience);
    localStorage.setItem("latest_filter_education", filterEducation);

    try {
      const res = await searchJobsFromPlatforms(buildPlatformSearchRequest());
      const jobsList = res.data.jobs || [];
      const fromCache = !!res.data.from_cache;
      const platformErrors = res.data.errors?.length
        ? `；部分平台异常：${res.data.errors.map((x) => `${x.platform_name || x.platform}: ${x.message}`).join("；")}`
        : "";
      const msg = `${res.data.message || "搜索完成"}${platformErrors}`;
      setJobs(jobsList);
      setSearchFromCache(fromCache);
      setSearchMessage(msg);
      setSearchErrors(res.data.errors || []);
      // Persist results so navigating away and back restores them instantly
      localStorage.setItem("latest_search_jobs", JSON.stringify(jobsList));
      localStorage.setItem("latest_search_message", msg);
      localStorage.setItem("latest_search_from_cache", fromCache ? "1" : "0");
    } catch (e: any) {
      setError(e.message || "搜索岗位失败");
    } finally {
      setSearchLoading(false);
    }
  };

  const handleCollectCurrentPages = async () => {
    if (!keyword.trim()) {
      setError("请先填写要搜索的岗位关键词");
      return;
    }
    if (!city.trim()) {
      setError("请先填写目标城市");
      return;
    }
    setSearchLoading(true);
    setError("");
    setSearchMessage("");
    setJobs([]);
    try {
      const res = await collectCurrentEdgePages(buildPlatformSearchRequest());
      const jobsList = res.data.jobs || [];
      const platformErrors = res.data.errors?.length
        ? `；页面提示：${res.data.errors.map((x) => `${x.platform_name || x.platform}: ${x.message}`).join("；")}`
        : "";
      const msg = `${res.data.message || "当前页面采集完成"}${platformErrors}`;
      setJobs(jobsList);
      setSearchMessage(msg);
      setSearchErrors(res.data.errors || []);
      localStorage.setItem("latest_search_jobs", JSON.stringify(jobsList));
      localStorage.setItem("latest_search_message", msg);
      localStorage.setItem("latest_search_from_cache", "0");
    } catch (e: any) {
      setError(e.message || "采集当前 Edge 页面失败");
    } finally {
      setSearchLoading(false);
    }
  };

  const handleCloseBrowser = async () => {
    setLoginLoading(true);
    setError("");
    try {
      const res = await closeJobBrowser();
      setLoginMessage(res.data.message || "招聘浏览器已关闭");
    } catch (e: any) {
      setError(e.message || "关闭招聘浏览器失败");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleClearCache = async () => {
    setLoginLoading(true);
    setError("");
    try {
      // Clear backend DB cache
      const res = await clearPlatformCache();
      // Clear frontend persisted results
      localStorage.removeItem("latest_search_jobs");
      localStorage.removeItem("latest_search_message");
      localStorage.removeItem("latest_search_from_cache");
      setJobs([]);
      setSearchMessage("");
      setSearchFromCache(false);
      setLoginMessage(res.message || "缓存已清空，下次搜索将重新爬取");
    } catch (e: any) {
      setError(e.message || "清空缓存失败");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleImportJob = async (job: PlatformJobItem) => {
    setImportingId(job.id);
    setError("");
    try {
      const jdTitle = job.title || keyword;
      const jdCompany = cleanCompanyName(job.company, job.title) || job.platform_name;
      const composedRawText = buildJDText(job);
      const createRes = await createJD({
        title: jdTitle,
        company: jdCompany,
        raw_text: composedRawText,
      });
      const id = createRes.data.jd_id;
      localStorage.setItem("latest_jd_id", String(id));
      localStorage.setItem("latest_jd_title", `${jdTitle}${jdCompany ? ` - ${jdCompany}` : ""}`);
      setJdId(id);
      setTitle(jdTitle);
      setCompany(jdCompany);
      setRawText(composedRawText);

      const parseRes = await parseJD(id);
      setParsed(parseRes.data.parsed_json);
      setActiveTab("manual");
    } catch (e: any) {
      setError(e.message || "导入岗位失败");
    } finally {
      setImportingId(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">职位描述</h1>
        <p className="text-sm text-gray-500 mt-1">
          可以手动粘贴 JD，也可以一键从四个招聘平台搜索岗位，按城市和简历匹配度筛选后导入分析。
        </p>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-1 grid grid-cols-2 gap-1">
        <button
          onClick={() => setActiveTab("manual")}
          className={`rounded-lg px-4 py-2 text-sm font-medium ${activeTab === "manual" ? "bg-primary-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
        >
          手动粘贴 JD
        </button>
        <button
          onClick={() => setActiveTab("search")}
          className={`rounded-lg px-4 py-2 text-sm font-medium ${activeTab === "search" ? "bg-primary-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
        >
          从招聘平台搜索
        </button>
      </div>

      {activeTab === "search" && (
        <div className="space-y-5">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800 space-y-2">
            <p className="font-semibold">使用方式</p>
            <p>
              先点击“打开浏览器登录”，在弹出的浏览器里完成 BOSS、智联、猎聘、前程无忧登录或验证码，然后点击“保存登录状态”。之后填写岗位关键词和城市即可搜索。
            </p>
            <p>
              当前用于筛选的简历：<span className="font-semibold">{latestResumeName}</span>
              {!latestResumeId && <span className="text-red-600 ml-2">未上传简历时也能搜索，但匹配评分只会使用岗位关键词。</span>}
            </p>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
            <div className="grid md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  要搜索的岗位 <span className="text-red-500">*</span>
                </label>
                <input
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="例如：AI开发实习生、Python后端、产品经理"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  目标城市 <span className="text-red-500">*</span>
                </label>
                <input
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="例如：广州、深圳、上海"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">每个平台页数</label>
                <input
                  type="number"
                  min={1}
                  max={5}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  value={pages}
                  onChange={(e) => setPages(Math.max(1, Math.min(5, Number(e.target.value) || 1)))}
                />
              </div>
            </div>

            <div className="grid md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">最低匹配分</label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  value={minScore}
                  onChange={(e) => setMinScore(Math.max(0, Math.min(100, Number(e.target.value) || 0)))}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">最多返回</label>
                <input
                  type="number"
                  min={1}
                  max={200}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  value={top}
                  onChange={(e) => setTop(Math.max(1, Math.min(200, Number(e.target.value) || 50)))}
                />
              </div>
              <label className="flex items-end gap-2 text-sm text-gray-700 pb-2">
                <input type="checkbox" checked={strictCity} onChange={(e) => setStrictCity(e.target.checked)} />
                严格过滤城市，避免岗位地址不符合
              </label>
              <label className="flex items-end gap-2 text-sm text-amber-700 pb-2">
                <input type="checkbox" checked={forceRefresh} onChange={(e) => setForceRefresh(e.target.checked)} />
                强制重新爬取（忽略缓存）
              </label>
            </div>

            <div className="grid md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">岗位类型</label>
                <select
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  value={jobType}
                  onChange={(e) => setJobType(e.target.value)}
                >
                  <option value="">不限</option>
                  <option value="全职">全职</option>
                  <option value="实习">实习</option>
                  <option value="兼职">兼职</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">工作经验</label>
                <select
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  value={filterExperience}
                  onChange={(e) => setFilterExperience(e.target.value)}
                >
                  <option value="">不限</option>
                  <option value="应届生">应届生</option>
                  <option value="1年以下">1年以下</option>
                  <option value="1-3年">1-3年</option>
                  <option value="3-5年">3-5年</option>
                  <option value="5-10年">5-10年</option>
                  <option value="10年以上">10年以上</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">学历要求</label>
                <select
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  value={filterEducation}
                  onChange={(e) => setFilterEducation(e.target.value)}
                >
                  <option value="">不限</option>
                  <option value="大专">大专</option>
                  <option value="本科">本科</option>
                  <option value="硕士">硕士</option>
                  <option value="博士">博士</option>
                </select>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-700">选择平台</label>
                <button onClick={selectAllPlatforms} className="text-xs text-primary-600 hover:text-primary-700">全选</button>
              </div>
              <div className="flex flex-wrap gap-2">
                {PLATFORM_OPTIONS.map((platform) => (
                  <button
                    key={platform.id}
                    onClick={() => togglePlatform(platform.id)}
                    className={`px-3 py-1.5 rounded-full border text-sm ${selectedPlatforms.includes(platform.id) ? "bg-primary-600 text-white border-primary-600" : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"}`}
                  >
                    {platform.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap gap-3 pt-1">
              <button
                onClick={handleOpenLogin}
                disabled={loginLoading}
                className="px-5 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {loginLoading ? "处理中..." : "打开浏览器登录"}
              </button>
              <button
                onClick={handleSaveLogin}
                disabled={loginLoading}
                className="px-5 py-2.5 bg-white border border-blue-300 text-blue-700 font-medium rounded-lg hover:bg-blue-50 disabled:opacity-50"
              >
                保存登录状态
              </button>
              <button
                onClick={handleSearchJobs}
                disabled={searchLoading}
                className="px-5 py-2.5 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {searchLoading ? "搜索筛选中..." : "一键搜索并筛选岗位"}
              </button>
              <button
                onClick={handleCollectCurrentPages}
                disabled={searchLoading}
                className="px-5 py-2.5 bg-white border border-green-300 text-green-700 font-medium rounded-lg hover:bg-green-50 disabled:opacity-50"
              >
                采集当前 Edge 页面
              </button>
              <button
                onClick={handleCloseBrowser}
                disabled={loginLoading}
                className="px-5 py-2.5 bg-white border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                关闭招聘浏览器
              </button>
              <button
                onClick={handleClearCache}
                disabled={loginLoading}
                className="px-4 py-2.5 bg-white border border-orange-300 text-orange-700 font-medium rounded-lg hover:bg-orange-50 disabled:opacity-50 text-sm"
              >
                清空搜索缓存
              </button>
            </div>
          </div>

          {loginMessage && <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">{loginMessage}</div>}
          {searchMessage && (
            <div className={`rounded-lg border p-3 text-sm ${searchFromCache ? "bg-amber-50 border-amber-200 text-amber-800" : "bg-green-50 border-green-200 text-green-800"}`}>
              {searchFromCache && <span className="font-semibold mr-1">缓存命中：</span>}
              {searchMessage}
            </div>
          )}
          {searchErrors.filter((e) => e.bookmarklet).length > 0 && (
            <BookmarkletCard bookmarklet={searchErrors.find((e) => e.bookmarklet)!.bookmarklet!} />
          )}
          {searchLoading && <LoadingSpinner text="正在打开招聘网站并抓取岗位，首次搜索可能需要较久..." />}
        </div>
      )}

      {activeTab === "manual" && (
        <div className="space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
            <strong>提示：</strong>手动粘贴 JD 后会自动保存最近的 JD，分析页会直接使用，不需要你再填写 1、2 这种内部 ID。
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                职位名称 <span className="text-red-500">*</span>
              </label>
              <input
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                placeholder="例如：Python 后端开发工程师"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">公司名称</label>
              <input
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                placeholder="例如：字节跳动"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              职位描述内容 <span className="text-red-500">*</span>
            </label>
            <textarea
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              rows={12}
              placeholder="在此粘贴完整的 JD 文本..."
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />
          </div>

          <button
            onClick={handleSubmit}
            disabled={loading || !title.trim() || !rawText.trim()}
            className="px-6 py-2.5 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "保存解析中..." : "保存并解析 JD"}
          </button>
        </div>
      )}

      {error && <ErrorAlert message={error} />}

      {jobs.length > 0 && activeTab === "search" && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-semibold text-gray-900">筛选结果</h3>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setActivePlatformFilter(null)}
                className={`px-3 py-1 rounded-full text-xs font-medium border ${activePlatformFilter === null ? "bg-primary-600 text-white border-primary-600" : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"}`}
              >
                全部
              </button>
              {PLATFORM_OPTIONS.map((p) => {
                const count = jobs.filter((j) => j.platform === p.id).length;
                if (count === 0) return null;
                return (
                  <button
                    key={p.id}
                    onClick={() => setActivePlatformFilter(activePlatformFilter === p.id ? null : p.id)}
                    className={`px-3 py-1 rounded-full text-xs font-medium border ${activePlatformFilter === p.id ? "bg-primary-600 text-white border-primary-600" : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"}`}
                  >
                    {p.label} ({count})
                  </button>
                );
              })}
            </div>
          </div>
          {jobs.filter((j) => !activePlatformFilter || j.platform === activePlatformFilter).map((job) => (
            <div key={job.id} className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="font-semibold text-gray-900">{job.title}</h4>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">{job.platform_name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${scoreBadge(job.match_score)}`}>{job.match_score} 分 · {job.match_level}</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1">
                    {job.company || "公司未提取"} · {job.city || city} · {job.salary || "薪资未提取"}
                  </p>
                  {(job.experience || job.education) && (
                    <p className="text-xs text-gray-500 mt-0.5">
                      {job.experience}{job.experience && job.education ? " · " : ""}{job.education}
                    </p>
                  )}
                  <p className="text-xs text-gray-500 mt-1">{job.score_reason}</p>
                </div>
                <div className="flex gap-2 shrink-0">
                  {job.detail_url && (
                    <a
                      href={job.detail_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm hover:bg-gray-50"
                    >
                      查看详细 JD
                    </a>
                  )}
                  <button
                    onClick={() => handleImportJob(job)}
                    disabled={importingId === job.id}
                    className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm hover:bg-primary-700 disabled:opacity-50"
                  >
                    {importingId === job.id ? "导入中..." : "导入此岗位并解析"}
                  </button>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="font-medium text-gray-700 mb-1">命中技能</p>
                  <ChipList items={job.matched_skills} empty="暂无命中技能" variant="green" />
                </div>
                <div>
                  <p className="font-medium text-gray-700 mb-1">建议补充</p>
                  <ChipList items={job.missing_skills} empty="暂无明显缺口" variant="yellow" />
                </div>
              </div>

              <p className="text-sm text-gray-600 line-clamp-3 whitespace-pre-wrap">
                {job.raw_text || "暂无岗位详情文本"}
              </p>
            </div>
          ))}
        </div>
      )}

      {parsed && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-semibold text-green-800">解析结果</h3>
            <div className="flex items-center gap-2">
              <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">JD ID: {jdId}</span>
              <button
                onClick={() => navigate("/analysis")}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm hover:bg-primary-700"
              >
                下一步：分析匹配
              </button>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4 text-sm">
            <Section title="职位名称" content={parsed.job_title} />
            <Section title="公司名称" content={parsed.company} />
            <Section title="学历要求" content={parsed.education_requirement} />
            <Section title="经验要求" content={parsed.experience_requirement} />
            <Section title="职级" content={parsed.seniority_level} />
          </div>

          <ListSection title="岗位职责" items={parsed.responsibilities} />
          <ListSection title="必备技能" items={parsed.required_skills} color="red" />
          <ListSection title="加分技能" items={parsed.preferred_skills} color="yellow" />
          <ListSection title="编程语言" items={parsed.programming_languages} />
          <ListSection title="框架" items={parsed.frameworks} />
          <ListSection title="数据库" items={parsed.databases} />
          <ListSection title="工具" items={parsed.tools} />
          <ListSection title="软技能" items={parsed.soft_skills} />

          {parsed.raw_summary && (
            <div>
              <h4 className="text-xs font-semibold text-gray-600 mb-1">概要</h4>
              <p className="text-sm text-gray-700">{parsed.raw_summary}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


function cleanCompanyName(company: string, title = "") {
  const text = (company || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  const suffix = /([\u4e00-\u9fa5A-Za-z0-9·（）()]{2,35}(?:有限公司|股份有限公司|上市公司|公司|集团|科技|信息|网络|软件|智能|数据|研究院|学院|大学|银行|证券|保险|医疗|生物|制造|传媒|资本|投资|电商|咨询))/g;
  const candidates = [...text.matchAll(suffix)]
    .map((m) => (m[1] || "").trim())
    .filter((x) => x && x !== title && !/\d+\s*[-~]\s*\d+/.test(x));
  if (candidates.length) return candidates.sort((a, b) => a.length - b.length)[0].slice(0, 80);
  const parts = text.split(/[\n|·•,，;；]+|\s{2,}/).map((x) => x.trim()).filter(Boolean);
  for (const part of parts) {
    if (part === title || part.length > 50) continue;
    if (/\d+\s*[-~]\s*\d+|年|学历|在线|顾问|招聘|职位|岗位/.test(part)) continue;
    return part.slice(0, 80);
  }
  if (text.length > 80 || (title && text.includes(title))) return "";
  return text.slice(0, 80);
}

function buildJDText(job: PlatformJobItem) {
  const parts = [
    `职位名称：${job.title}`,
    cleanCompanyName(job.company, job.title) ? `公司名称：${cleanCompanyName(job.company, job.title)}` : "",
    `招聘平台：${job.platform_name}`,
    job.city ? `工作地点：${job.city}` : "",
    job.salary ? `薪资：${job.salary}` : "",
    job.experience ? `经验要求：${job.experience}` : "",
    job.education ? `学历要求：${job.education}` : "",
    job.detail_url ? `岗位链接：${job.detail_url}` : "",
    "",
    "岗位详情：",
    job.raw_text || "招聘平台未返回完整详情，请打开岗位链接查看后补充。",
  ];
  return parts.filter(Boolean).join("\n");
}

function scoreBadge(score: number) {
  if (score >= 85) return "bg-green-100 text-green-700";
  if (score >= 75) return "bg-blue-100 text-blue-700";
  if (score >= 60) return "bg-yellow-100 text-yellow-700";
  if (score >= 50) return "bg-orange-100 text-orange-700";
  return "bg-red-100 text-red-700";
}

function ChipList({ items, empty, variant }: { items: string[]; empty: string; variant: "green" | "yellow" }) {
  const color = variant === "green" ? "bg-green-50 text-green-700 border-green-200" : "bg-yellow-50 text-yellow-700 border-yellow-200";
  if (!items.length) return <p className="text-xs text-gray-400">{empty}</p>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.slice(0, 12).map((item) => (
        <span key={item} className={`text-xs px-2 py-0.5 rounded-full border ${color}`}>{item}</span>
      ))}
    </div>
  );
}

function Section({ title, content }: { title: string; content: string }) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-gray-600 mb-1">{title}</h4>
      <p className="text-sm text-gray-800">{content || "—"}</p>
    </div>
  );
}

function ListSection({ title, items, color }: { title: string; items: string[]; color?: string }) {
  if (!items.length) return null;
  const badge =
    color === "red"
      ? "bg-red-50 text-red-700 border-red-200"
      : color === "yellow"
      ? "bg-yellow-50 text-yellow-700 border-yellow-200"
      : "bg-gray-50 text-gray-700 border-gray-200";

  return (
    <div>
      <h4 className="text-xs font-semibold text-gray-600 mb-2">{title} ({items.length})</h4>
      <div className="flex flex-wrap gap-1.5">
        {items.map((s) => (
          <span key={s} className={`text-xs px-2 py-0.5 rounded-full border ${badge}`}>
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}

function BookmarkletCard({ bookmarklet }: { bookmarklet: { method: string; title: string; steps: string[]; code: string } }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(bookmarklet.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for non-HTTPS or older browsers
      const ta = document.createElement("textarea");
      ta.value = bookmarklet.code;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch {}
      document.body.removeChild(ta);
    }
  };

  return (
    <div className="bg-amber-50 border border-amber-300 rounded-lg p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="font-semibold text-amber-900">{bookmarklet.title}</h4>
        <span className="text-xs bg-amber-200 text-amber-800 px-2 py-0.5 rounded-full">方法一 · 备用方案</span>
      </div>
      <p className="text-sm text-amber-700">
        BOSS 直聘反爬检测较严格，自动抓取可能失败。你可以使用浏览器书签脚本手动导出当前页面的岗位数据：
      </p>
      <ol className="list-decimal list-inside text-sm text-amber-800 space-y-1">
        {bookmarklet.steps.map((step, i) => (
          <li key={i}>{step.replace(/^\d+\.\s*/, "")}</li>
        ))}
      </ol>
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-semibold text-amber-700">书签脚本代码（点击复制后添加到浏览器书签）</span>
          <button
            onClick={handleCopy}
            className="px-3 py-1 text-xs bg-amber-200 hover:bg-amber-300 text-amber-800 rounded transition-colors"
          >
            {copied ? "已复制" : "复制代码"}
          </button>
        </div>
        <pre className="bg-amber-100 border border-amber-200 rounded p-3 text-xs text-amber-900 overflow-x-auto max-h-32 whitespace-pre-wrap break-all select-all">
          {bookmarklet.code}
        </pre>
      </div>
      <p className="text-xs text-amber-600">
        使用方法：在 BOSS 直聘搜索结果页点击书签，会自动下载当前页面的岗位数据为 JSON 文件。多次导出后可自行合并。
      </p>
    </div>
  );
}
