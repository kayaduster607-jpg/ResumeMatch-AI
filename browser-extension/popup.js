/**
 * Popup v3.2: popup 直接和 background 通信
 * 所有 API 请求由 background 发起，不经过 content script
 */

const DEFAULT_API = "http://localhost:8000";

// ── 平台配置 ──────────────────────────────────────────────
const PLATFORMS = {
  boss: {
    name: "BOSS 直聘",
    url: "https://www.zhipin.com/web/geek/job",
    detailBase: "https://www.zhipin.com/job_detail/",
    detailSuffix: ".html",
    cities: [
      { code: "101010100", name: "北京" }, { code: "101020100", name: "上海" },
      { code: "101280100", name: "广州" }, { code: "101280600", name: "深圳" },
      { code: "101210100", name: "杭州" }, { code: "101270100", name: "成都" },
      { code: "101030100", name: "天津" }, { code: "101110100", name: "西安" },
      { code: "101050100", name: "武汉" }, { code: "101180100", name: "南京" },
      { code: "101190100", name: "苏州" }, { code: "101200100", name: "长沙" },
      { code: "101230100", name: "厦门" }, { code: "101160100", name: "重庆" },
      { code: "101250100", name: "东莞" }, { code: "101120100", name: "济南" },
      { code: "101220100", name: "合肥" }, { code: "101330100", name: "珠海" },
    ],
  },
  zhaopin: {
    name: "智联招聘",
    url: "https://sou.zhaopin.com/",
    detailBase: "https://www.zhaopin.com/jobdetail/",
    detailSuffix: "",
    cities: [
      { code: "530", name: "北京" }, { code: "538", name: "上海" },
      { code: "763", name: "广州" }, { code: "765", name: "深圳" },
      { code: "653", name: "杭州" }, { code: "801", name: "成都" },
      { code: "531", name: "天津" }, { code: "854", name: "西安" },
      { code: "736", name: "武汉" }, { code: "635", name: "南京" },
      { code: "639", name: "苏州" }, { code: "749", name: "长沙" },
      { code: "682", name: "厦门" }, { code: "811", name: "重庆" },
      { code: "769", name: "东莞" }, { code: "702", name: "济南" },
      { code: "664", name: "合肥" }, { code: "773", name: "珠海" },
    ],
  },
  liepin: {
    name: "猎聘",
    url: "https://www.liepin.com/zhaopin/",
    detailBase: "https://www.liepin.com/job/",
    detailSuffix: ".shtml",
    cities: [
      { code: "010", name: "北京" }, { code: "020", name: "上海" },
      { code: "050020", name: "广州" }, { code: "050090", name: "深圳" },
      { code: "070020", name: "杭州" }, { code: "280020", name: "成都" },
      { code: "030", name: "天津" }, { code: "270020", name: "西安" },
      { code: "170020", name: "武汉" }, { code: "060020", name: "南京" },
      { code: "060080", name: "苏州" }, { code: "180020", name: "长沙" },
      { code: "090040", name: "厦门" }, { code: "040030", name: "重庆" },
      { code: "050060", name: "东莞" }, { code: "120020", name: "济南" },
      { code: "150020", name: "合肥" }, { code: "050050", name: "珠海" },
    ],
  },
  qiancheng: {
    name: "前程无忧",
    url: "https://www.51job.com/",
    detailBase: "https://we.51job.com/pc/job/",
    detailSuffix: ".html",
    cities: [
      { code: "010000", name: "北京" }, { code: "020000", name: "上海" },
      { code: "030200", name: "广州" }, { code: "040000", name: "深圳" },
      { code: "080200", name: "杭州" }, { code: "090200", name: "成都" },
      { code: "050000", name: "天津" }, { code: "200200", name: "西安" },
      { code: "180200", name: "武汉" }, { code: "070200", name: "南京" },
      { code: "070300", name: "苏州" }, { code: "140300", name: "长沙" },
      { code: "110300", name: "厦门" }, { code: "060000", name: "重庆" },
      { code: "030800", name: "东莞" }, { code: "120300", name: "济南" },
      { code: "150200", name: "合肥" }, { code: "030500", name: "珠海" },
    ],
  },
};

let jobList = [];
let importedIds = new Set();
let apiUrl = DEFAULT_API;
let currentPlatform = "boss";

// ── DOM ─────────────────────────────────────────────────
const platformSelect = document.getElementById("platform");
const keywordInput = document.getElementById("keyword");
const citySelect = document.getElementById("city");
const jobTypeSelect = document.getElementById("jobType");
const expSelect = document.getElementById("experience");
const degSelect = document.getElementById("degree");
const btnSearch = document.getElementById("btn-search");
const contentDiv = document.getElementById("content");
const msgArea = document.getElementById("msg-area");
const footerLeft = document.getElementById("footer-left");
const btnSettings = document.getElementById("btn-settings");
const btnImportAll = document.getElementById("btn-import-all");
const btnOpenTab = document.getElementById("btn-open-tab");
const settingsPanel = document.getElementById("settings-panel");
const apiUrlInput = document.getElementById("api-url");

// ── 发送消息到 background（带重试，解决 service worker 未唤醒问题）─
async function sendToBackground(message, retries = 2) {
  for (let i = 0; i <= retries; i++) {
    try {
      const result = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(message, (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve(response);
          }
        });
      });
      return result;
    } catch (e) {
      if (i < retries && e.message.includes("Receiving end does not exist")) {
        await new Promise(r => setTimeout(r, 300 * (i + 1)));
        continue;
      }
      throw e;
    }
  }
}

// ── 初始化 ──────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  const stored = await chrome.storage.local.get([
    "apiUrl", "keyword", "city", "jobType", "platform",
    "savedResults", "savedImportedIds",
  ]);
  apiUrl = stored.apiUrl || DEFAULT_API;
  apiUrlInput.value = apiUrl;

  currentPlatform = stored.platform || "boss";
  platformSelect.value = currentPlatform;
  populateCities();

  if (stored.city) citySelect.value = stored.city;
  if (stored.keyword) keywordInput.value = stored.keyword;
  if (stored.jobType) jobTypeSelect.value = stored.jobType;

  // 恢复上次搜索结果
  if (stored.savedResults && stored.savedResults.jobs?.length > 0) {
    jobList = stored.savedResults.jobs;
    importedIds = new Set(stored.savedImportedIds || []);
    handleSearchResult({ success: true, jobs: jobList, total: stored.savedResults.total });
    showMsg(`已恢复上次搜索结果（${jobList.length} 个岗位）`, "info");
  }

  keywordInput.focus();
});

// ── 平台切换 ──────────────────────────────────────────────
platformSelect.addEventListener("change", () => {
  currentPlatform = platformSelect.value;
  chrome.storage.local.set({ platform: currentPlatform });
  populateCities();
  jobList = [];
  importedIds = new Set();
  contentDiv.innerHTML = `<div class="login-hint">已切换到 ${PLATFORMS[currentPlatform].name}，输入关键词搜索岗位</div>`;
  btnImportAll.style.display = "none";
  footerLeft.textContent = "就绪";
  showMsg("");
  chrome.storage.local.remove(["savedResults", "savedImportedIds"]);
});

function populateCities() {
  const cities = PLATFORMS[currentPlatform]?.cities || PLATFORMS.boss.cities;
  citySelect.innerHTML = cities.map(c => `<option value="${c.code}">${c.name}</option>`).join("");
}

// ── 设置 ────────────────────────────────────────────────
btnSettings.addEventListener("click", () => {
  const visible = settingsPanel.style.display !== "none";
  settingsPanel.style.display = visible ? "none" : "block";
  if (!visible) apiUrlInput.focus();
  else {
    apiUrl = apiUrlInput.value.trim() || DEFAULT_API;
    chrome.storage.local.set({ apiUrl });
  }
});

// ── 在标签页中打开 ────────────────────────────────────────
btnOpenTab.addEventListener("click", () => {
  chrome.tabs.create({ url: chrome.runtime.getURL("popup.html") });
  window.close();
});

// ── 搜索（直接发给 background） ──────────────────────────
btnSearch.addEventListener("click", searchJobs);
keywordInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") searchJobs();
});

async function searchJobs() {
  const keyword = keywordInput.value.trim();
  if (!keyword) { showMsg("请输入搜索关键词", "warn"); return; }

  const city = citySelect.value;
  const cityName = citySelect.options[citySelect.selectedIndex]?.text || "";
  const jobType = jobTypeSelect.value;
  const experience = expSelect.value;
  const degree = degSelect.value;
  chrome.storage.local.set({ keyword, city, jobType });

  btnSearch.disabled = true;
  btnSearch.innerHTML = '<span class="spinner"></span>搜索中';
  showMsg("");
  btnImportAll.style.display = "none";

  try {
    const result = await sendToBackground({
      action: "search",
      platform: currentPlatform,
      params: { keyword, city, cityName, jobType, experience, degree, platform: currentPlatform },
    });
    handleSearchResult(result);
  } catch (e) {
    showMsg("搜索失败：" + e.message, "err");
  } finally {
    btnSearch.disabled = false;
    btnSearch.textContent = "搜索";
  }
}

function handleSearchResult(result) {
  if (!result || !result.success) {
    const err = result?.error || "搜索失败";
    // 清除旧数据
    jobList = [];
    btnImportAll.style.display = "none";
    footerLeft.textContent = "就绪";
    // 如果有调试信息，显示在 content 区域
    if (result?.debug) {
      contentDiv.innerHTML = `<pre style="font-size:10px;max-height:400px;overflow:auto;background:#f5f5f5;padding:8px;">${esc(JSON.stringify(result.debug, null, 2))}</pre>`;
    } else {
      contentDiv.innerHTML = `<div class="login-hint">搜索失败，请重试</div>`;
    }
    chrome.storage.local.remove(["savedResults", "savedImportedIds"]);
    if (err.includes("登录") || err.includes("login")) {
      const pf = PLATFORMS[currentPlatform];
      showMsg(err + `，请先 <a href="${pf.url}" target="_blank">登录 ${pf.name}</a>`, "err");
    } else {
      showMsg(err, "err");
    }
    return;
  }

  jobList = result.jobs || [];

  // 按城市过滤结果
  const selectedCityName = citySelect.options[citySelect.selectedIndex]?.text || "";
  if (selectedCityName && selectedCityName !== "不限" && jobList.length > 0) {
    const filtered = jobList.filter(job => {
      const jobCity = (job.cityName || job.areaDistrict || "").toLowerCase();
      const target = selectedCityName.toLowerCase();
      // 宽松匹配：城市名包含在结果中，或结果包含城市名
      return jobCity.includes(target) || target.includes(jobCity.replace(/-.*$/, ""));
    });
    // 只有在有匹配结果时才过滤，避免过滤掉全部结果
    if (filtered.length > 0) {
      jobList = filtered;
    }
  }

  if (jobList.length === 0) {
    showMsg("没有找到相关岗位，换个关键词试试", "warn");
    contentDiv.innerHTML = "";
    return;
  }

  const totalInfo = result.total > jobList.length ? `（共 ${result.total} 个）` : "";
  const filteredInfo = selectedCityName && selectedCityName !== "不限" ? ` - ${selectedCityName}` : "";
  showMsg(`找到 ${jobList.length} 个岗位${filteredInfo}${totalInfo}`, "ok");
  btnImportAll.style.display = jobList.length > 0 ? "inline-block" : "none";
  footerLeft.textContent = `共 ${jobList.length} 个岗位`;
  renderJobList(jobList);

  // 持久化搜索结果
  chrome.storage.local.set({
    savedResults: { jobs: jobList, total: result.total },
    savedImportedIds: [...importedIds],
  });
}

// ── 渲染岗位列表 ────────────────────────────────────────
function renderJobList(jobs) {
  const pf = PLATFORMS[currentPlatform];
  contentDiv.innerHTML = '<div class="job-list">' + jobs.map((job, i) => `
    <div class="job-card ${importedIds.has(job.encryptJobId) ? 'imported' : ''}" data-idx="${i}">
      <div class="job-title">
        <span>${esc(job.jobName)}</span>
        <span class="salary">${esc(job.salaryDesc)}</span>
      </div>
      <div class="job-meta">
        ${esc(job.brandName)} · ${esc(job.cityName)}${job.areaDistrict ? ' · ' + esc(job.areaDistrict) : ''}
        · ${esc(job.experienceName)} · ${esc(job.degreeName)}
      </div>
      <div class="job-tags">${(job.skills || []).map(s => `<span>${esc(s)}</span>`).join("")}</div>
      <div class="job-actions">
        <button class="btn btn-primary btn-sm btn-fetch" data-idx="${i}" ${importedIds.has(job.encryptJobId) ? 'disabled' : ''}>
          ${importedIds.has(job.encryptJobId) ? '已导入' : '获取详情并导入'}
        </button>
        ${job.encryptJobId ? `<a href="${pf.detailBase}${job.encryptJobId}${pf.detailSuffix || '.html'}" target="_blank" style="font-size:11px;color:#4f46e5;">在${pf.name}打开</a>` : ''}
      </div>
      <div id="preview-${i}" style="display:none;"></div>
    </div>
  `).join("") + "</div>";

  contentDiv.querySelectorAll(".btn-fetch").forEach((btn) => {
    btn.addEventListener("click", () => fetchAndImport(parseInt(btn.dataset.idx)));
  });
}

// ── 获取详情并导入（直接发给 background） ────────────────
async function fetchAndImport(idx) {
  const job = jobList[idx];
  if (!job || importedIds.has(job.encryptJobId)) return;

  const previewEl = document.getElementById(`preview-${idx}`);
  const btn = contentDiv.querySelector(`.btn-fetch[data-idx="${idx}"]`);
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>获取中';
  showMsg("");

  try {
    const detailData = await sendToBackground({
      action: "fetchDetail",
      platform: currentPlatform,
      securityId: job.securityId || job.encryptJobId,
      jobId: job.encryptJobId,
    });

    let rawText;
    if (detailData && detailData.success) {
      rawText = detailData.raw_text;
      previewEl.innerHTML = `<div class="jd-preview">${esc(rawText.substring(0, 500))}${rawText.length > 500 ? '...' : ''}</div>`;
      previewEl.style.display = "block";
    } else {
      rawText = buildRawTextFromCard(job);
    }

    btn.innerHTML = '<span class="spinner"></span>导入中';
    const result = await importToBackend(job.jobName, job.brandName, rawText);

    importedIds.add(job.encryptJobId);
    btn.textContent = "已导入";
    btn.classList.remove("btn-primary");
    btn.classList.add("btn-success");

    const card = contentDiv.querySelector(`.job-card[data-idx="${idx}"]`);
    if (card) card.classList.add("imported");

    showMsg(`已导入「${job.jobName}」→ JD ID: ${result.jd_id}`, "ok");
    footerLeft.textContent = `已导入 ${importedIds.size} / ${jobList.length}`;

    // 持久化导入状态
    chrome.storage.local.set({ savedImportedIds: [...importedIds] });
  } catch (e) {
    showMsg(`导入失败：${e.message}`, "err");
    btn.disabled = false;
    btn.textContent = "获取详情并导入";
  }
}

function buildRawTextFromCard(job) {
  const parts = [`职位名称：${job.jobName}`];
  if (job.brandName) parts.push(`公司：${job.brandName}`);
  if (job.salaryDesc) parts.push(`薪资：${job.salaryDesc}`);
  if (job.cityName) parts.push(`地点：${job.cityName}`);
  const reqs = [job.experienceName, job.degreeName].filter(Boolean);
  if (reqs.length) parts.push(`要求：${reqs.join(" / ")}`);
  if (job.skills?.length) parts.push(`技能标签：${job.skills.join("、")}`);
  parts.push("", job.jobDesc || "（请在详情页查看完整 JD）");
  return parts.join("\n");
}

// ── 全部导入 ────────────────────────────────────────────
btnImportAll.addEventListener("click", async () => {
  btnImportAll.disabled = true;
  btnImportAll.innerHTML = '<span class="spinner"></span>批量导入中';
  let success = 0, fail = 0;

  for (let i = 0; i < jobList.length; i++) {
    const job = jobList[i];
    if (importedIds.has(job.encryptJobId)) continue;
    try {
      await importToBackend(job.jobName, job.brandName, buildRawTextFromCard(job));
      importedIds.add(job.encryptJobId);
      success++;
      const btn = contentDiv.querySelector(`.btn-fetch[data-idx="${i}"]`);
      if (btn) { btn.textContent = "已导入"; btn.disabled = true; btn.classList.remove("btn-primary"); btn.classList.add("btn-success"); }
      const card = contentDiv.querySelector(`.job-card[data-idx="${i}"]`);
      if (card) card.classList.add("imported");
    } catch (e) { fail++; }
  }

  btnImportAll.disabled = false;
  btnImportAll.textContent = "全部导入系统";
  showMsg(`批量导入完成：成功 ${success} 个${fail ? `，失败 ${fail} 个` : ""}`, success > 0 ? "ok" : "err");
  footerLeft.textContent = `已导入 ${importedIds.size} / ${jobList.length}`;
});

// ── 发送到后端 ──────────────────────────────────────────
async function importToBackend(title, company, rawText) {
  const createResp = await fetch(`${apiUrl}/api/v1/jds/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, company, raw_text: rawText }),
  });
  if (!createResp.ok) {
    const err = await createResp.json().catch(() => ({}));
    throw new Error(err.message || `HTTP ${createResp.status}`);
  }
  const createResult = await createResp.json();
  const jdId = createResult.data.jd_id;

  const parseResp = await fetch(`${apiUrl}/api/v1/jds/${jdId}/parse`, { method: "POST" });
  if (!parseResp.ok) {
    const err = await parseResp.json().catch(() => ({}));
    throw new Error(err.message || `解析失败 HTTP ${parseResp.status}`);
  }
  return { jd_id: jdId };
}

// ── 工具 ────────────────────────────────────────────────
function showMsg(text, type) {
  if (!text) { msgArea.innerHTML = ""; return; }
  msgArea.innerHTML = `<div class="msg msg-${type}">${text}</div>`;
}

function esc(s) {
  if (!s) return "";
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
