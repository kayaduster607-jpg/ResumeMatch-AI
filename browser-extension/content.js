/**
 * Content script v3.6: DOM 抓取 + API 拦截（猎聘、前程无忧、智联招聘）
 * 在页面加载早期安装 fetch/XHR 拦截器，捕获 API 响应
 */

// ── API 拦截器（在页面 JS 执行前安装，捕获搜索 API 响应）─
(function installInterceptors() {
  const host = window.location.hostname;

  // 猎聘拦截器 — 捕获所有 /api/ 请求
  if (host.includes("liepin.com")) {
    const origFetch = window.fetch;
    window.fetch = function(...args) {
      const p = origFetch.apply(this, args);
      p.then(resp => {
        try {
          const url = resp.url || "";
          // 捕获搜索相关 API
          if (url.includes("/api/") || url.includes("search") || url.includes("job") || url.includes("list")) {
            const clone = resp.clone();
            clone.json().then(j => { window.__lpCaptured = j; }).catch(() => {});
          }
        } catch {}
      }).catch(() => {});
      return p;
    };
    const origXHRSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(...args) {
      this.addEventListener("load", () => {
        try {
          const url = this.responseURL || "";
          if (url.includes("/api/") || url.includes("search") || url.includes("job") || url.includes("list")) {
            window.__lpCaptured = JSON.parse(this.responseText);
          }
        } catch {}
      });
      return origXHRSend.apply(this, args);
    };
  }

  // 智联招聘拦截器 — 捕获所有 API 请求
  if (host.includes("zhaopin.com")) {
    const origFetch = window.fetch;
    window.fetch = function(...args) {
      const p = origFetch.apply(this, args);
      p.then(resp => {
        try {
          const url = resp.url || "";
          if (url.includes("/api/") || url.includes("/i/") || url.includes("search") || url.includes("position")) {
            const clone = resp.clone();
            clone.json().then(j => { window.__zcCaptured = j; }).catch(() => {});
          }
        } catch {}
      }).catch(() => {});
      return p;
    };
    const origXHRSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(...args) {
      this.addEventListener("load", () => {
        try {
          const url = this.responseURL || "";
          if (url.includes("/api/") || url.includes("/i/") || url.includes("search") || url.includes("position")) {
            window.__zcCaptured = JSON.parse(this.responseText);
          }
        } catch {}
      });
      return origXHRSend.apply(this, args);
    };
  }

  // 前程无忧拦截器 — 捕获所有搜索相关请求
  if (host.includes("51job.com")) {
    const origFetch = window.fetch;
    window.fetch = function(...args) {
      const p = origFetch.apply(this, args);
      p.then(resp => {
        try {
          const url = resp.url || "";
          if (url.includes("search") || url.includes("joblist") || url.includes("/api/") || url.includes("job-search") || url.includes("positionlist") || url.includes("job")) {
            const clone = resp.clone();
            clone.json().then(j => { window.__qcCaptured = j; }).catch(() => {});
          }
        } catch {}
      }).catch(() => {});
      return p;
    };
    const origXHRSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(...args) {
      this.addEventListener("load", () => {
        try {
          const url = this.responseURL || "";
          if (url.includes("search") || url.includes("joblist") || url.includes("/api/") || url.includes("job-search") || url.includes("positionlist") || url.includes("job")) {
            window.__qcCaptured = JSON.parse(this.responseText);
          }
        } catch {}
      });
      return origXHRSend.apply(this, args);
    };
  }
})();

// ── 平台检测 ──────────────────────────────────────────────
function detectPlatform() {
  const host = window.location.hostname;
  if (host.includes("zhipin.com")) return "boss";
  if (host.includes("zhaopin.com")) return "zhaopin";
  if (host.includes("liepin.com")) return "liepin";
  if (host.includes("51job.com")) return "qiancheng";
  return null;
}

function scrapeCurrentPage() {
  const getText = (sel) => { const el = document.querySelector(sel); return el ? el.innerText.trim() : ""; };
  const platform = detectPlatform();
  let title = "", company = "", jdText = "", salary = "", location = "";

  if (platform === "boss") {
    title = getText(".job-name"); company = getText(".company-name");
    jdText = getText(".job-sec-text"); salary = getText(".salary"); location = getText(".job-area");
  } else if (platform === "zhaopin") {
    title = getText(".summary-plane__title") || getText("h1"); company = getText(".company-title a");
    jdText = getText(".describtion__detail-content"); salary = getText(".summary-plane__salary");
    location = getText(".summary-plane__info");
  } else if (platform === "liepin") {
    title = getText(".job-title h1") || getText("h1"); company = getText(".company-name");
    jdText = getText(".job-intro-container"); salary = getText(".job-salary"); location = getText(".job-dq");
  } else if (platform === "qiancheng") {
    title = getText(".job_msg h1") || getText("h1"); company = getText(".cname a");
    jdText = getText(".job_msg div"); salary = getText(".cn strong"); location = getText(".job_msg .ltype");
  }

  if (!title && !jdText) return { success: false, error: "当前页面不支持抓取" };
  const tags = Array.from(document.querySelectorAll(".tag-list li, .job-tags span, .labels span"))
    .map(el => el.innerText.trim()).filter(Boolean);

  const parts = [];
  if (title) parts.push(`职位名称：${title}`);
  if (company) parts.push(`公司：${company}`);
  if (salary) parts.push(`薪资：${salary}`);
  if (location) parts.push(`地点：${location}`);
  if (tags.length) parts.push(`要求：${tags.join("、")}`);
  parts.push("", jdText || "");

  return { success: true, data: { title: title || "未知职位", company: company || "未知公司", raw_text: parts.join("\n") }, method: "dom" };
}

// ── 搜索页结果抓取 ──────────────────────────────────────
function scrapeSearchResults() {
  const platform = detectPlatform();
  const jobs = [];
  const seen = new Set();

  if (platform === "liepin") {
    // 检查拦截到的 API 数据
    if (window.__lpCaptured?.data) {
      const data = window.__lpCaptured.data;
      const list = data.jobCardList || data.list || data.data || [];
      list.forEach(item => {
        const name = item.title || item.jobName || item.name || "";
        if (!name || seen.has(name)) return;
        seen.add(name);
        jobs.push({
          encryptJobId: item.jobId || item.encryptJobId || "", securityId: item.jobId || item.encryptJobId || "",
          jobName: name, brandName: item.compName || item.company || item.brandName || "", salaryDesc: item.salary || item.salaryDesc || "",
          cityName: item.dq || item.city || item.cityName || "", areaDistrict: item.dqDesc || item.areaDistrict || "",
          experienceName: item.requireWorkYears || item.experience || "", degreeName: item.requireEduLevel || item.education || "",
          skills: item.labels || item.skills || [], jobDesc: item.jobDesc || item.description || "",
        });
      });
    }
    // 检查 __INITIAL_STATE__
    if (!jobs.length && window.__INITIAL_STATE__?.jobList) {
      window.__INITIAL_STATE__.jobList.forEach(item => {
        const name = item.title || item.jobName || "";
        if (!name || seen.has(name)) return;
        seen.add(name);
        jobs.push({
          encryptJobId: item.jobId || "", securityId: item.jobId || "",
          jobName: name, brandName: item.compName || "", salaryDesc: item.salary || "",
          cityName: item.dq || item.city || "", areaDistrict: item.dqDesc || "",
          experienceName: item.requireWorkYears || "", degreeName: item.requireEduLevel || "",
          skills: item.labels || [], jobDesc: item.jobDesc || "",
        });
      });
    }
    // DOM 抓取
    if (!jobs.length) {
      document.querySelectorAll(".job-card, .job-card-box, .job-list-item, [class*='JobCard'], [class*='search-result'] > *, a[href*='/job/']").forEach(card => {
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
    }
  }

  if (platform === "zhaopin") {
    // 检查拦截到的 API 数据
    if (window.__zcCaptured) {
      const d = window.__zcCaptured;
      const list = d?.data?.list || d?.list || d?.data?.data?.list || d?.data?.items || [];
      list.forEach(item => {
        const name = item.positionName || item.jobName || item.name || item.title || "";
        if (!name || seen.has(name)) return;
        seen.add(name);
        jobs.push({
          encryptJobId: item.number || item.jobId || "", securityId: item.number || item.jobId || "",
          jobName: name, brandName: item.companyName || "",
          salaryDesc: item.salary || "", cityName: item.cityDistrict || item.city || "",
          areaDistrict: item.cityDistrict || "", experienceName: item.workExperience || "",
          degreeName: item.education || "", skills: item.tags || [],
          jobDesc: item.jobDesc || "",
        });
      });
    }
    // DOM 抓取
    if (!jobs.length) {
      document.querySelectorAll("[class*='positionlist'] [class*='item'], [class*='joblist'] [class*='item'], [class*='job-card'], [class*='position-item']").forEach(card => {
        if (jobs.length >= 30) return;
        const titleEl = card.querySelector("[class*='position'], [class*='jobname'], [class*='name'], h3, a");
        const compEl = card.querySelector("[class*='company'], [class*='comp']");
        const salaryEl = card.querySelector("[class*='salary'], [class*='sal']");
        const name = titleEl?.innerText?.trim() || "";
        if (!name || name.length < 2) return;
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
    }
  }

  if (platform === "qiancheng") {
    if (window.__qcCaptured) {
      const d = window.__qcCaptured;
      const list = d?.data?.list || d?.list || d?.jobList || d?.data?.items || d?.items || d?.resultbody?.items || d?.data?.data?.list || [];
      list.forEach(item => {
        const name = item.jobName || item.positionName || item.name || item.title || "";
        if (!name || seen.has(name)) return;
        seen.add(name);
        jobs.push({
          encryptJobId: item.jobId || item.number || item.positionId || item.encryptJobId || "", securityId: item.jobId || item.number || "",
          jobName: name, brandName: item.companyName || item.company?.name || item.brandName || "",
          salaryDesc: item.salary || item.salary60 || item.salaryDesc || "", cityName: item.cityName || item.city || item.jobArea || "",
          areaDistrict: item.areaDistrict || "", experienceName: item.workYear || item.workExperience || item.experienceName || "",
          degreeName: item.education || item.degree || item.degreeName || "", skills: item.tags || item.skills || [],
          jobDesc: item.jobDesc || item.description || "",
        });
      });
    }
    // 检查 __INITIAL_STATE__
    if (!jobs.length && window.__INITIAL_STATE__) {
      const state = window.__INITIAL_STATE__;
      const list = state?.jobList || state?.searchResult?.list || state?.resultbody?.items || state?.data?.list || [];
      list.forEach(item => {
        const name = item.jobName || item.positionName || item.name || "";
        if (!name || seen.has(name)) return;
        seen.add(name);
        jobs.push({
          encryptJobId: item.jobId || item.number || item.positionId || "", securityId: item.jobId || item.number || "",
          jobName: name, brandName: item.companyName || item.company?.name || "",
          salaryDesc: item.salary || item.salary60 || "", cityName: item.cityName || item.city || item.jobArea || "",
          areaDistrict: item.areaDistrict || "", experienceName: item.workYear || item.workExperience || "",
          degreeName: item.education || item.degree || "", skills: item.tags || [],
          jobDesc: item.jobDesc || item.description || "",
        });
      });
    }
    if (!jobs.length) {
      document.querySelectorAll(".joblist-item, .j_jobitem, .job-item, [class*='joblist'] > * > *, a[href*='/job/']").forEach(card => {
        if (jobs.length >= 20) return;
        const titleEl = card.querySelector("[class*='job-name'], [class*='jobname'], [class*='tit'], h3, .jname");
        const compEl = card.querySelector("[class*='company'], [class*='com'], [class*='cname']");
        const salaryEl = card.querySelector("[class*='salary'], [class*='sal']");
        const name = titleEl?.innerText?.trim() || "";
        if (!name || name.length < 2 || seen.has(name)) return;
        seen.add(name);
        const link = card.querySelector("a[href*='job']") || (card.tagName === "A" ? card : null);
        let jid = card.dataset.jobid || card.dataset.id || "";
        if (!jid && link) { const m = link.href.match(/job\/([^/?]+)/) || link.href.match(/jobid=([^&]+)/); if (m) jid = m[1]; }
        jobs.push({ encryptJobId: jid, securityId: jid, jobName: name,
          brandName: compEl?.innerText?.trim() || "", salaryDesc: salaryEl?.innerText?.trim() || "",
          cityName: "", areaDistrict: "", experienceName: "", degreeName: "", skills: [], jobDesc: "" });
      });
    }
  }

  if (jobs.length > 0) return { success: true, jobs, total: jobs.length };
  return { success: false, error: "当前页面未找到搜索结果" };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "ping") {
    sendResponse({ pong: true });
    return false;
  }
  if (request.action === "scrape") {
    sendResponse(scrapeCurrentPage());
    return false;
  }
  if (request.action === "scrapeSearch") {
    sendResponse(scrapeSearchResults());
    return false;
  }
  if (request.action === "getCaptured") {
    const platform = detectPlatform();
    if (platform === "liepin") sendResponse(window.__lpCaptured || null);
    else if (platform === "zhaopin") sendResponse(window.__zcCaptured || null);
    else if (platform === "qiancheng") sendResponse(window.__qcCaptured || null);
    else sendResponse(null);
    return false;
  }
});
