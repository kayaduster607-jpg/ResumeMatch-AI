/**
 * Background service worker: 直接处理 popup 的 API 请求
 * Popup → Background (直接通信，不经过 content script)
 * 对于需要 cookie 的平台，在目标网站的 tab 中执行 fetch
 */

async function doFetch(url, options = {}) {
  const resp = await fetch(url, {
    method: options.method || "GET",
    headers: options.headers || { "Accept": "application/json, text/plain, */*" },
    body: options.body || undefined,
  });
  const text = await resp.text();
  let data;
  try { data = JSON.parse(text); } catch { data = text; }
  return { ok: resp.ok, status: resp.status, data };
}

// ── 在指定域名的 tab 中执行 fetch（携带 cookie）──────────
async function findTabForDomain(domain) {
  const tabs = await chrome.tabs.query({});
  return tabs.find(t => t.url && (t.url.startsWith("http://") || t.url.startsWith("https://")) && t.url.includes(domain));
}

async function executeInTab(domain, script, fallbackUrl, ...args) {
  let tab = await findTabForDomain(domain);
  if (!tab) {
    // 没有打开的 tab，创建一个临时的
    tab = await chrome.tabs.create({ url: fallbackUrl, active: false });
    // 等待页面加载完成
    await new Promise(resolve => {
      const listener = (tabId, info) => {
        if (tabId === tab.id && info.status === "complete") {
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
      // 超时 10 秒
      setTimeout(() => { chrome.tabs.onUpdated.removeListener(listener); resolve(); }, 10000);
    });
  }
  // 确保 tab URL 是 http(s) —— 防止注入到扩展页面
  if (!tab.url || !(tab.url.startsWith("http://") || tab.url.startsWith("https://"))) {
    return { success: false, error: `无法访问的页面` };
  }
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN",
      func: script,
      args,
    });
    return results?.[0]?.result;
  } catch (e) {
    return { success: false, error: `注入脚本失败: ${e.message}` };
  }
}

// ── BOSS 直聘 ──────────────────────────────────────────
async function searchBoss(params) {
  const { keyword, city, jobType, experience, degree, page = 1 } = params;
  const sp = new URLSearchParams({
    query: keyword, city: city || "101280100", page: page.toString(), pageSize: "30",
  });
  if (jobType) sp.set("jobNature", jobType);
  if (experience) sp.set("experience", experience);
  if (degree) sp.set("degree", degree);

  try {
    // 通过 tab 执行 fetch 以携带 cookie
    const result = await executeInTab(
      "zhipin.com",
      async (paramsStr) => {
        const resp = await fetch(`https://www.zhipin.com/wapi/zpgeek/search/joblist.json?${paramsStr}`, {
          credentials: "include",
          headers: { "Accept": "application/json" },
        });
        if (!resp.ok) return { success: false, error: `HTTP ${resp.status}` };
        const json = await resp.json();
        if (json.code !== 0) {
          if (json.code === 1 || json.code === 7) return { success: false, error: "请先登录 BOSS 直聘" };
          return { success: false, error: json.message || `API 错误码 ${json.code}` };
        }
        const jobs = (json.zpData?.jobList || []).map((item) => ({
          encryptJobId: item.encryptJobId, securityId: item.securityId,
          jobName: item.jobName || "", brandName: item.brandName || "",
          salaryDesc: item.salaryDesc || "", cityName: item.cityName || "",
          areaDistrict: item.areaDistrict || "", experienceName: item.experienceName || "",
          degreeName: item.degreeName || "", skills: item.skills || [], jobDesc: item.jobDesc || "",
        }));
        return { success: true, jobs, total: json.zpData?.totalCount || jobs.length, hasMore: jobs.length >= 30 };
      },
      "https://www.zhipin.com/web/geek/job",
      sp.toString(),
    );
    return result || { success: false, error: "BOSS 直聘执行失败" };
  } catch (e) { return { success: false, error: e.message }; }
}

async function fetchBossDetail(securityId) {
  try {
    // 通过 tab 执行 fetch 以携带 cookie
    const result = await executeInTab(
      "zhipin.com",
      async (sid) => {
        const resp = await fetch(`https://www.zhipin.com/wapi/zpgeek/job/detail.json?securityId=${encodeURIComponent(sid)}`, {
          credentials: "include",
          headers: { "Accept": "application/json" },
        });
        if (!resp.ok) return { success: false, error: `HTTP ${resp.status}` };
        const json = await resp.json();
        if (json.code !== 0) return { success: false, error: json.message || `API 错误码 ${json.code}` };
        const jobInfo = json.zpData?.jobInfo;
        const brandInfo = json.zpData?.brandComInfo;
        if (!jobInfo) return { success: false, error: "未获取到岗位信息" };

        const parts = [`职位名称：${jobInfo.jobName || ""}`];
        if (brandInfo?.brandName) parts.push(`公司：${brandInfo.brandName}`);
        if (jobInfo.salaryDesc) parts.push(`薪资：${jobInfo.salaryDesc}`);
        if (jobInfo.cityName) parts.push(`地点：${jobInfo.cityName}`);
        if (jobInfo.address) parts.push(`地址：${jobInfo.address}`);
        const reqs = [jobInfo.experienceName, jobInfo.degreeName].filter(Boolean);
        if (reqs.length) parts.push(`要求：${reqs.join(" / ")}`);
        if (jobInfo.skills?.length) parts.push(`技能标签：${jobInfo.skills.join("、")}`);
        parts.push("", jobInfo.postDescription || jobInfo.jobDetail || "");
        return { success: true, raw_text: parts.join("\n") };
      },
      "https://www.zhipin.com/web/geek/job",
      securityId,
    );
    return result || { success: false, error: "BOSS 直聘详情获取失败" };
  } catch (e) { return { success: false, error: e.message }; }
}

// ── 智联招聘（拦截器 + DOM 双路）──────────
async function searchZhaopin(params) {
  const { keyword, city, cityName, jobType, experience, degree, page = 1 } = params;
  const cityCode = city || "530";
  try {
    const t = Date.now();
    const sp = new URLSearchParams({
      pageSize: "30", cityId: cityCode, kw: keyword, kt: "3",
      workExperience: experience || "-1", education: degree || "-1",
      employmentType: jobType || "-1", pageIndex: String(page - 1),
      _t: String(t),
    });
    const searchUrl = `https://sou.zhaopin.com/?${sp}`;

    let tab = await findTabForDomain("zhaopin.com");
    if (tab) {
      await chrome.tabs.update(tab.id, { url: searchUrl, active: false });
    } else {
      tab = await chrome.tabs.create({ url: searchUrl, active: false });
    }
    await new Promise(resolve => {
      const listener = (tabId, info) => {
        if (tabId === tab.id && info.status === "complete") {
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
      setTimeout(() => { chrome.tabs.onUpdated.removeListener(listener); resolve(); }, 15000);
    });

    // 等待 SPA 渲染和 API 响应
    await new Promise(r => setTimeout(r, 3000));

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN",
      func: (cityNm) => {
        return new Promise(async resolve => {
          // 方法1: 读取 content.js 拦截到的 API 数据
          if (window.__zcCaptured) {
            const d = window.__zcCaptured;
            const list = d?.data?.list || d?.list || d?.data?.data?.list || d?.data?.items || [];
            if (list.length > 0) {
              const jobs = list.map(item => ({
                encryptJobId: item.number || item.jobId || "", securityId: item.number || item.jobId || "",
                jobName: item.positionName || item.jobName || item.name || "", brandName: item.companyName || "",
                salaryDesc: item.salary || "", cityName: item.cityDistrict || item.city || "",
                areaDistrict: item.cityDistrict || "", experienceName: item.workExperience || "",
                degreeName: item.education || "", skills: item.tags || [],
                jobDesc: item.jobDesc || "",
              }));
              resolve({ success: true, jobs, total: d?.data?.count || d?.data?.pageSize || jobs.length, hasMore: jobs.length >= 30 });
              return;
            }
          }

          // 方法2: 检查 __INITIAL_STATE__
          if (window.__INITIAL_STATE__) {
            const state = window.__INITIAL_STATE__;
            const list = state?.searchResult?.list || state?.jobList || state?.data?.list || [];
            if (list.length > 0) {
              const jobs = list.map(item => ({
                encryptJobId: item.number || item.jobId || "", securityId: item.number || item.jobId || "",
                jobName: item.positionName || item.jobName || "", brandName: item.companyName || "",
                salaryDesc: item.salary || "", cityName: item.cityDistrict || item.city || "",
                areaDistrict: item.cityDistrict || "", experienceName: item.workExperience || "",
                degreeName: item.education || "", skills: item.tags || [],
                jobDesc: item.jobDesc || "",
              }));
              resolve({ success: true, jobs, total: jobs.length, hasMore: false });
              return;
            }
          }

          // 方法3: DOM — 从职位卡片提取
          const jobCards = document.querySelectorAll("[class*='positionlist'] [class*='item'], [class*='joblist'] [class*='item'], [class*='job-card'], [class*='position-item']");
          if (jobCards.length > 0) {
            const jobs = [];
            const seen = new Set();
            jobCards.forEach(card => {
              if (jobs.length >= 30) return;
              const titleEl = card.querySelector("[class*='position'], [class*='jobname'], [class*='name'], h3, a");
              const compEl = card.querySelector("[class*='company'], [class*='comp']");
              const salaryEl = card.querySelector("[class*='salary'], [class*='sal']");
              const name = titleEl?.innerText?.trim() || "";
              if (!name || name.length < 2 || seen.has(name)) return;
              const link = card.querySelector("a[href*='job']") || (card.tagName === "A" ? card : null);
              let jid = "";
              if (link) {
                const m = link.href.match(/jobdetail\/([^/?]+)/i) || link.href.match(/jobs\.zhaopin\.com\/([^/?]+)/i) || link.href.match(/\/(CC\d+|\d{8,})/);
                if (m) jid = m[1];
              }
              if (!jid) return;
              seen.add(name);
              jobs.push({ encryptJobId: jid, securityId: jid, jobName: name,
                brandName: compEl?.innerText?.trim() || "", salaryDesc: salaryEl?.innerText?.trim() || "",
                cityName: "", areaDistrict: "", experienceName: "", degreeName: "", skills: [], jobDesc: "" });
            });
            if (jobs.length > 0) { resolve({ success: true, jobs, total: jobs.length, hasMore: jobs.length >= 30 }); return; }
          }

          // 方法4: DOM — 从链接提取
          const checkDOM = () => {
            const candidates = document.querySelectorAll("a[href*='jobdetail'], a[href*='jobs.zhaopin'], a[href*='position']");
            const seen = new Set();
            const jobs = [];
            candidates.forEach(link => {
              if (jobs.length >= 30) return;
              const name = (link.innerText || link.getAttribute("title") || "").trim();
              if (!name || name.length < 2 || name.length > 80 || seen.has(name)) return;
              const href = link.href;
              let jid = "";
              const m1 = href.match(/jobdetail\/([^/?]+)/i);
              const m2 = href.match(/jobs\.zhaopin\.com\/([^/?]+)/i);
              const m3 = href.match(/position\/([^/?]+)/i);
              const m4 = href.match(/\/(CC\d+|\d{8,})/);
              if (m1) jid = m1[1];
              else if (m2) jid = m2[1];
              else if (m3) jid = m3[1];
              else if (m4) jid = m4[1];
              if (!jid) return;
              seen.add(name);
              jobs.push({ encryptJobId: jid, securityId: jid, jobName: name,
                brandName: "", salaryDesc: "",
                cityName: "", areaDistrict: "", experienceName: "", degreeName: "", skills: [], jobDesc: "" });
            });
            return jobs;
          };

          let jobs = checkDOM();
          if (jobs.length > 0) { resolve({ success: true, jobs, total: jobs.length, hasMore: jobs.length >= 30 }); return; }

          // 轮询等待 SPA 渲染
          for (let i = 0; i < 15; i++) {
            await new Promise(r => setTimeout(r, 800));
            jobs = checkDOM();
            if (jobs.length > 0) { resolve({ success: true, jobs, total: jobs.length, hasMore: jobs.length >= 30 }); return; }
          }

          resolve({
            success: false,
            error: "智联搜索无结果，请确认已登录智联招聘",
            debug: { url: location.href, title: document.title,
              linkCount: document.querySelectorAll("a").length,
              hasCaptured: !!window.__zcCaptured,
              hasInitialState: !!window.__INITIAL_STATE__,
              bodySnippet: document.body?.innerText?.substring(0, 400) || "" },
          });
        });
      },
      args: [cityName],
    });
    return results?.[0]?.result || { success: false, error: "智联执行失败" };
  } catch (e) { return { success: false, error: e.message }; }
}

async function fetchZhaopinDetail(jobId) {
  try {
    const result = await executeInTab(
      "zhaopin.com",
      async (jid) => {
        // 尝试多个可能的 API endpoint
        const apiUrls = [
          "https://fe-api.zhaopin.com/c/i/job-detail",
          "https://fe-api.zhaopin.com/c/i/sou/job-detail",
          "https://sou.zhaopin.com/api/job-detail",
        ];
        for (const apiUrl of apiUrls) {
          try {
            const resp = await fetch(apiUrl, {
              method: "POST",
              headers: { "Accept": "application/json", "Content-Type": "application/json" },
              credentials: "include",
              body: JSON.stringify({ number: jid, demand: "" }),
            });
            if (!resp.ok) continue;
            const json = await resp.json();
            if (json.code !== 200) continue;
            const data = json.data || {};
            const pos = data.position || {};
            const comp = data.company || {};
            const parts = [`职位名称：${pos.name || data.jobName || ""}`];
            if (comp.name) parts.push(`公司：${comp.name}`);
            if (pos.salary || data.salary) parts.push(`薪资：${pos.salary || data.salary}`);
            if (pos.city?.display || data.city) parts.push(`地点：${pos.city?.display || data.city}`);
            if (pos.workExp || data.workExperience) parts.push(`经验：${pos.workExp || data.workExperience}`);
            if (pos.education || data.education) parts.push(`学历：${pos.education || data.education}`);
            parts.push("", pos.content || data.jobDesc || "");
            return { success: true, raw_text: parts.join("\n") };
          } catch {}
        }
        return { success: false, error: "智联详情 API 请求失败" };
      },
      "https://sou.zhaopin.com/",
      jobId,
    );
    return result || { success: false, error: "智联详情获取失败" };
  } catch (e) { return { success: false, error: e.message }; }
}

// ── 猎聘（拦截器 + DOM 双路）──────────
async function searchLiepin(params) {
  const { keyword, city, cityName, page = 1 } = params;
  const dq = city || "";
  try {
    // 猎聘搜索 URL
    const searchUrl = `https://www.liepin.com/zhaopin/?key=${encodeURIComponent(keyword)}&dq=${dq}&currentPage=${page - 1}&pageSize=40`;

    let tab = await findTabForDomain("liepin.com");
    if (tab) {
      await chrome.tabs.update(tab.id, { url: searchUrl, active: false });
    } else {
      tab = await chrome.tabs.create({ url: searchUrl, active: false });
    }
    await new Promise(resolve => {
      const listener = (tabId, info) => {
        if (tabId === tab.id && info.status === "complete") {
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
      setTimeout(() => { chrome.tabs.onUpdated.removeListener(listener); resolve(); }, 15000);
    });

    // 等待 SPA 渲染和 API 响应
    await new Promise(r => setTimeout(r, 3000));

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN",
      func: (cityNm) => {
        return new Promise(resolve => {
          let attempts = 0;
          const check = () => {
            // 方法1: 读取 content.js 拦截到的 API 数据
            if (window.__lpCaptured?.data) {
              const data = window.__lpCaptured.data;
              const list = data.jobCardList || data.list || data.data || [];
              if (list.length > 0) {
                const jobs = list.map((item) => ({
                  encryptJobId: item.jobId || item.encryptJobId || "", securityId: item.jobId || item.encryptJobId || "",
                  jobName: item.title || item.jobName || item.name || "", brandName: item.compName || item.company || item.brandName || "",
                  salaryDesc: item.salary || item.salaryDesc || "", cityName: item.dq || item.city || item.cityName || "",
                  areaDistrict: item.dqDesc || item.areaDistrict || "", experienceName: item.requireWorkYears || item.experience || "",
                  degreeName: item.requireEduLevel || item.education || "", skills: item.labels || item.skills || [],
                  jobDesc: item.jobDesc || item.description || "",
                }));
                resolve({ success: true, jobs, total: data.totalCount || data.total || jobs.length, hasMore: jobs.length >= 40 });
                return;
              }
            }

            // 方法2: 检查 __INITIAL_STATE__
            if (window.__INITIAL_STATE__?.jobList) {
              const list = window.__INITIAL_STATE__.jobList;
              if (list.length > 0) {
                const jobs = list.map((item) => ({
                  encryptJobId: item.jobId || "", securityId: item.jobId || "",
                  jobName: item.title || item.jobName || "", brandName: item.compName || "",
                  salaryDesc: item.salary || "", cityName: item.dq || item.city || "",
                  areaDistrict: item.dqDesc || "", experienceName: item.requireWorkYears || "",
                  degreeName: item.requireEduLevel || "", skills: item.labels || [],
                  jobDesc: item.jobDesc || "",
                }));
                resolve({ success: true, jobs, total: list.length, hasMore: false });
                return;
              }
            }

            // 方法3: DOM — 从职位卡片提取
            const jobCards = document.querySelectorAll(".job-card, .job-card-box, .job-list-item, [class*='JobCard'], [class*='search-result'] > *");
            if (jobCards.length > 0) {
              const seen = new Set();
              const jobs = [];
              jobCards.forEach(card => {
                if (jobs.length >= 40) return;
                const titleEl = card.querySelector("[class*='title'], [class*='name'], h3, a");
                const compEl = card.querySelector("[class*='company'], [class*='comp']");
                const salaryEl = card.querySelector("[class*='salary']");
                const name = titleEl?.innerText?.trim() || "";
                if (!name || name.length < 2 || seen.has(name)) return;
                seen.add(name);
                const link = card.querySelector("a[href*='job']") || (card.tagName === "A" ? card : null);
                let jid = card.dataset.jobid || "";
                if (!jid && link) { const m = link.href.match(/job\/(\d+)/); if (m) jid = m[1]; }
                jobs.push({ encryptJobId: jid, securityId: jid, jobName: name,
                  brandName: compEl?.innerText?.trim() || "", salaryDesc: salaryEl?.innerText?.trim() || "",
                  cityName: "", areaDistrict: "", experienceName: "", degreeName: "", skills: [], jobDesc: "" });
              });
              if (jobs.length > 0) {
                resolve({ success: true, jobs, total: jobs.length, hasMore: jobs.length >= 40 });
                return;
              }
            }

            // 方法4: DOM — 从详情链接提取
            const jobLinks = document.querySelectorAll("a[href*='/job/']");
            if (jobLinks.length > 0) {
              const seen = new Set();
              const jobs = [];
              jobLinks.forEach(link => {
                if (jobs.length >= 40) return;
                const name = link.innerText?.trim() || link.getAttribute("title") || "";
                if (!name || name.length < 2 || name.length > 80 || seen.has(name)) return;
                const m = link.href.match(/\/job\/(\d+)/);
                if (!m) return;
                seen.add(name);
                jobs.push({ encryptJobId: m[1], securityId: m[1], jobName: name,
                  brandName: "", salaryDesc: "",
                  cityName: "", areaDistrict: "", experienceName: "", degreeName: "", skills: [], jobDesc: "" });
              });
              if (jobs.length > 0) {
                resolve({ success: true, jobs, total: jobs.length, hasMore: jobs.length >= 40 });
                return;
              }
            }

            attempts++;
            if (attempts >= 30) {
              resolve({ success: false, error: "猎聘搜索超时，请确认已登录猎聘",
                debug: { title: document.title, url: location.href,
                  bodySnippet: document.body?.innerText?.substring(0, 500) || "",
                  hasCaptured: !!window.__lpCaptured, hasInitialState: !!window.__INITIAL_STATE__ } });
              return;
            }
            setTimeout(check, 500);
          };
          check();
        });
      },
      args: [cityName],
    });
    return results?.[0]?.result || { success: false, error: "猎聘执行失败" };
  } catch (e) { return { success: false, error: e.message }; }
}

async function fetchLiepinDetail(jobId) {
  try {
    // 猎聘详情页 URL - 尝试多种格式
    const detailUrls = [
      `https://www.liepin.com/job/${jobId}.shtml`,
      `https://www.liepin.com/job/${jobId}`,
      `https://www.liepin.com/zhaopin/?jobId=${jobId}`,
    ];
    const detailUrl = detailUrls[0];
    const tab = await chrome.tabs.create({ url: detailUrl, active: false });
    await new Promise(resolve => {
      const listener = (tabId, info) => {
        if (tabId === tab.id && info.status === "complete") {
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
      setTimeout(() => { chrome.tabs.onUpdated.removeListener(listener); resolve(); }, 10000);
    });

    // 等待页面渲染
    await new Promise(r => setTimeout(r, 1500));

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN",
      func: () => {
        const title = document.title?.replace(/ - 猎聘.*$/, "").replace(/_猎聘.*$/, "").trim() || "";
        // 方法1: JSON-LD
        const jsonldEl = document.querySelector('script[type="application/ld+json"]');
        if (jsonldEl) {
          try {
            const ld = JSON.parse(jsonldEl.textContent);
            const parts = [`职位名称：${ld.title || title}`];
            if (ld.hiringOrganization?.name) parts.push(`公司：${ld.hiringOrganization.name}`);
            if (ld.baseSalary?.value) parts.push(`薪资：${ld.baseSalary.value}`);
            if (ld.jobLocation?.address?.addressLocality) parts.push(`地点：${ld.jobLocation.address.addressLocality}`);
            if (ld.description) parts.push("", ld.description.replace(/<[^>]+>/g, ""));
            return { success: true, raw_text: parts.join("\n") };
          } catch {}
        }
        // 方法2: __INITIAL_STATE__
        const state = window.__INITIAL_STATE__;
        if (state?.jobDetail || state?.jobInfo) {
          const jd = state.jobDetail || state.jobInfo;
          const parts = [`职位名称：${jd.title || jd.jobName || title}`];
          if (jd.compName || jd.companyName) parts.push(`公司：${jd.compName || jd.companyName}`);
          if (jd.salary) parts.push(`薪资：${jd.salary}`);
          if (jd.dq || jd.city) parts.push(`地点：${jd.dq || jd.city}`);
          if (jd.requireWorkYears) parts.push(`经验：${jd.requireWorkYears}`);
          if (jd.requireEduLevel) parts.push(`学历：${jd.requireEduLevel}`);
          if (jd.jobDesc || jd.description) parts.push("", jd.jobDesc || jd.description);
          return { success: true, raw_text: parts.join("\n") };
        }
        // 方法3: DOM
        const titleEl = document.querySelector(".job-title h1, h1, .job-name, [class*='job-title']");
        const compEl = document.querySelector(".company-name, .comp-name, [class*='company-name']");
        const salaryEl = document.querySelector(".job-salary, .salary, [class*='salary']");
        const jdEl = document.querySelector(".job-intro-container, .job-detail, .job-desc, [class*='job-intro'], [class*='job-detail'], [class*='job-content']");
        const parts = [`职位名称：${titleEl?.innerText?.trim() || title}`];
        if (compEl) parts.push(`公司：${compEl.innerText.trim()}`);
        if (salaryEl) parts.push(`薪资：${salaryEl.innerText.trim()}`);
        if (jdEl) parts.push("", jdEl.innerText.trim());
        return { success: true, raw_text: parts.join("\n") };
      },
    });
    return results?.[0]?.result || { success: false, error: "猎聘详情获取失败" };
  } catch (e) { return { success: false, error: e.message }; }
}

// ── 前程无忧（在 51job tab 中等 SPA 渲染后抓 DOM）─────────
async function searchQiancheng(params) {
  const { keyword, city, experience, degree, page = 1 } = params;
  const cityCode = city || "010000";
  try {
    // 前程无忧搜索 URL - 使用 we.51job.com 格式
    const sp = new URLSearchParams({
      jobArea: cityCode,
      keyword: keyword,
      searchType: "1",
      page: page.toString(),
      pageSize: "20",
    });
    if (experience) sp.set("workYearCode", experience);
    if (degree) sp.set("educationCode", degree);
    const searchUrl = `https://we.51job.com/pc/search?${sp}`;

    let tab = await findTabForDomain("51job.com");
    if (tab) {
      await chrome.tabs.update(tab.id, { url: searchUrl, active: false });
    } else {
      tab = await chrome.tabs.create({ url: searchUrl, active: false });
    }
    await new Promise(resolve => {
      const listener = (tabId, info) => {
        if (tabId === tab.id && info.status === "complete") {
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
      setTimeout(() => { chrome.tabs.onUpdated.removeListener(listener); resolve(); }, 15000);
    });

    // 等待 SPA 渲染
    await new Promise(r => setTimeout(r, 2000));

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN",
      func: () => {
        return new Promise(resolve => {
          let attempts = 0;
          const check = () => {
            // content.js 拦截器已安装，检查拦截到的数据
            if (window.__qcCaptured) {
              const d = window.__qcCaptured;
              const list = d?.data?.list || d?.list || d?.jobList || d?.data?.items || d?.items || d?.resultbody?.items || d?.data?.data?.list || [];
              if (list.length > 0) {
                const jobs = list.map((item) => ({
                  encryptJobId: item.jobId || item.number || item.positionId || item.encryptJobId || "", securityId: item.jobId || item.number || "",
                  jobName: item.jobName || item.positionName || item.name || item.title || "", brandName: item.companyName || item.company?.name || item.brandName || "",
                  salaryDesc: item.salary || item.salary60 || item.salaryDesc || "", cityName: item.cityName || item.city || item.jobArea || "",
                  areaDistrict: item.areaDistrict || "", experienceName: item.workYear || item.workExperience || item.experienceName || "",
                  degreeName: item.education || item.degree || item.degreeName || "", skills: item.tags || item.skills || [],
                  jobDesc: item.jobDesc || item.description || "",
                }));
                resolve({ success: true, jobs, total: d?.totalCount || d?.total || d?.count || jobs.length, hasMore: jobs.length >= 20 });
                return;
              }
            }

            // SSR 状态
            const state = window.__INITIAL_STATE__;
            if (state) {
              const list = state?.jobList || state?.searchResult?.list || state?.resultbody?.items || state?.data?.list || [];
              if (list.length > 0) {
                const jobs = list.map((item) => ({
                  encryptJobId: item.jobId || item.number || item.positionId || "", securityId: item.jobId || item.number || "",
                  jobName: item.jobName || item.positionName || item.name || "", brandName: item.companyName || item.company?.name || "",
                  salaryDesc: item.salary || item.salary60 || "", cityName: item.cityName || item.city || item.jobArea || "",
                  areaDistrict: item.areaDistrict || "", experienceName: item.workYear || item.workExperience || "",
                  degreeName: item.education || item.degree || "", skills: item.tags || [],
                  jobDesc: item.jobDesc || item.description || "",
                }));
                resolve({ success: true, jobs, total: state?.totalCount || state?.total || jobs.length, hasMore: jobs.length >= 20 });
                return;
              }
            }

            // DOM — 从职位卡片提取
            const jobCards = document.querySelectorAll("[class*='joblist'] [class*='item'], [class*='job-item'], [class*='j_jobitem'], .joblist-item");
            if (jobCards.length > 0) {
              const jobs = [];
              jobCards.forEach(card => {
                if (jobs.length >= 20) return;
                const titleEl = card.querySelector("[class*='job-name'], [class*='jobname'], [class*='tit'], h3, .jname");
                const compEl = card.querySelector("[class*='company'], [class*='com'], [class*='cname']");
                const salaryEl = card.querySelector("[class*='salary'], [class*='sal']");
                const name = titleEl?.innerText?.trim() || "";
                if (!name || name.length < 2) return;
                const link = card.querySelector("a[href*='job']") || (card.tagName === "A" ? card : null);
                let jid = card.dataset?.jobid || card.dataset?.id || "";
                if (!jid && link) {
                  const m = link.href.match(/job\/([^/?]+)/) || link.href.match(/jobid=([^&]+)/);
                  if (m) jid = m[1];
                }
                if (!jid) return;
                jobs.push({ encryptJobId: jid, securityId: jid, jobName: name,
                  brandName: compEl?.innerText?.trim() || "", salaryDesc: salaryEl?.innerText?.trim() || "",
                  cityName: "", areaDistrict: "", experienceName: "", degreeName: "", skills: [], jobDesc: "" });
              });
              if (jobs.length > 0) { resolve({ success: true, jobs, total: jobs.length, hasMore: jobs.length >= 20 }); return; }
            }

            // DOM — 从详情链接提取
            const jobLinks = document.querySelectorAll("a[href*='/job/'], a[href*='jobid=']");
            if (jobLinks.length > 0) {
              const seen = new Set();
              const jobs = [];
              jobLinks.forEach(link => {
                if (jobs.length >= 20) return;
                const name = link.innerText?.trim() || link.getAttribute("title") || "";
                if (!name || name.length < 2 || name.length > 80 || seen.has(name)) return;
                const m = link.href.match(/\/job\/([^/?]+)/) || link.href.match(/jobid=([^&]+)/);
                if (!m) return;
                seen.add(name);
                jobs.push({ encryptJobId: m[1], securityId: m[1], jobName: name,
                  brandName: "", salaryDesc: "",
                  cityName: "", areaDistrict: "", experienceName: "", degreeName: "", skills: [], jobDesc: "" });
              });
              if (jobs.length > 0) { resolve({ success: true, jobs, total: jobs.length, hasMore: jobs.length >= 20 }); return; }
            }

            attempts++;
            if (attempts >= 40) {
              resolve({ success: false, error: "前程无忧搜索超时，请确认已登录前程无忧",
                debug: { title: document.title, url: location.href, bodySnippet: document.body?.innerText?.substring(0, 500) || "", captured: !!window.__qcCaptured, initialState: !!window.__INITIAL_STATE__ } });
              return;
            }
            setTimeout(check, 500);
          };
          check();
        });
      },
    });
    return results?.[0]?.result || { success: false, error: "前程无忧执行失败" };
  } catch (e) { return { success: false, error: e.message }; }
}

async function fetchQianchengDetail(jobId) {
  try {
    // 前程无忧详情页 URL - 尝试多种格式
    const detailUrls = [
      `https://we.51job.com/pc/job/${jobId}.html`,
      `https://www.51job.com/job/${jobId}.html`,
      `https://we.51job.com/pc/job/detail/${jobId}`,
    ];
    const detailUrl = detailUrls[0];
    const tab = await chrome.tabs.create({ url: detailUrl, active: false });
    await new Promise(resolve => {
      const listener = (tabId, info) => {
        if (tabId === tab.id && info.status === "complete") {
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
      setTimeout(() => { chrome.tabs.onUpdated.removeListener(listener); resolve(); }, 10000);
    });

    // 等待页面渲染
    await new Promise(r => setTimeout(r, 1500));

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN",
      func: () => {
        const title = document.title?.replace(/ - 前程无忧.*$/, "").replace(/ - 51job.*$/, "").replace(/_前程无忧.*$/, "").trim() || "";
        // 方法1: JSON-LD
        const jsonldEl = document.querySelector('script[type="application/ld+json"]');
        if (jsonldEl) {
          try {
            const ld = JSON.parse(jsonldEl.textContent);
            const parts = [`职位名称：${ld.title || title}`];
            if (ld.hiringOrganization?.name) parts.push(`公司：${ld.hiringOrganization.name}`);
            if (ld.description) parts.push("", ld.description.replace(/<[^>]+>/g, ""));
            return { success: true, raw_text: parts.join("\n") };
          } catch {}
        }
        // 方法2: __INITIAL_STATE__
        const state = window.__INITIAL_STATE__;
        if (state?.jobDetail || state?.jobInfo) {
          const jd = state.jobDetail || state.jobInfo;
          const parts = [`职位名称：${jd.jobName || jd.title || title}`];
          if (jd.companyName || jd.company?.name) parts.push(`公司：${jd.companyName || jd.company.name}`);
          if (jd.salary || jd.salary60) parts.push(`薪资：${jd.salary || jd.salary60}`);
          if (jd.cityName || jd.city) parts.push(`地点：${jd.cityName || jd.city}`);
          if (jd.jobDesc || jd.description) parts.push("", jd.jobDesc || jd.description);
          return { success: true, raw_text: parts.join("\n") };
        }
        // 方法3: DOM
        const titleEl = document.querySelector(".jname, h1, .job-name, .job_msg h1, [class*='job-title']");
        const compEl = document.querySelector(".cname a, .company-name, .com_name, [class*='company-name']");
        const salaryEl = document.querySelector(".sal, .salary, .cn strong, [class*='salary']");
        const jdEl = document.querySelector(".bmsg, .job-detail, .job_msg div, .job-desc, [class*='job-detail'], [class*='job-content'], [class*='job_msg']");
        const parts = [`职位名称：${titleEl?.innerText?.trim() || title}`];
        if (compEl) parts.push(`公司：${compEl.innerText.trim()}`);
        if (salaryEl) parts.push(`薪资：${salaryEl.innerText.trim()}`);
        if (jdEl) parts.push("", jdEl.innerText.trim());
        return { success: true, raw_text: parts.join("\n") };
      },
    });
    return results?.[0]?.result || { success: false, error: "前程无忧详情获取失败" };
  } catch (e) { return { success: false, error: e.message }; }
}

// ── 消息监听（popup 直接调用，不经过 content script） ──
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "search") {
    const platform = request.platform;
    let promise;
    switch (platform) {
      case "boss": promise = searchBoss(request.params); break;
      case "zhaopin": promise = searchZhaopin(request.params); break;
      case "liepin": promise = searchLiepin(request.params); break;
      case "qiancheng": promise = searchQiancheng(request.params); break;
      default: promise = Promise.resolve({ success: false, error: "不支持的平台" });
    }
    promise.then(sendResponse);
    return true;
  }

  if (request.action === "fetchDetail") {
    const platform = request.platform;
    let promise;
    switch (platform) {
      case "boss": promise = fetchBossDetail(request.securityId); break;
      case "zhaopin": promise = fetchZhaopinDetail(request.jobId); break;
      case "liepin": promise = fetchLiepinDetail(request.jobId); break;
      case "qiancheng": promise = fetchQianchengDetail(request.jobId); break;
      default: promise = Promise.resolve({ success: false, error: "不支持的平台" });
    }
    promise.then(sendResponse);
    return true;
  }

  if (request.action === "ping") {
    sendResponse({ pong: true });
    return false;
  }
});
