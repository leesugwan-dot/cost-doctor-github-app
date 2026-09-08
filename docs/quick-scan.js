(function () {
  "use strict";

  var MAX_LENGTH = 2048;
  var issueFormUrl = "https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new";
  var form = document.querySelector("[data-quick-scan-form]");
  var input = document.querySelector("[data-repository-url]");
  var language = document.querySelector("[data-result-language]");
  var status = document.querySelector("[data-quick-scan-status]");
  if (!form || !input || !language || !status) return;

  function setStatus(kind, message) {
    status.dataset.state = kind;
    status.textContent = message;
  }

  function normalizeRepository(value) {
    var raw = String(value || "").trim();
    if (!raw || raw.length > MAX_LENGTH || /[\u0000-\u001f\u007f]/.test(raw)) {
      throw new Error("URL_INVALID");
    }
    if (raw.indexOf("://") === -1 && raw.indexOf("github.com/") === 0) {
      raw = "https://" + raw;
    }
    var parsed;
    try {
      parsed = new URL(raw);
    } catch (_) {
      throw new Error("URL_INVALID");
    }
    if (parsed.protocol !== "https:" || parsed.hostname.toLowerCase() !== "github.com" || parsed.username || parsed.password || parsed.port) {
      throw new Error("URL_INVALID");
    }
    var parts = parsed.pathname.split("/").filter(Boolean).map(function (part) {
      try { return decodeURIComponent(part); } catch (_) { throw new Error("URL_INVALID"); }
    });
    if (parts.length < 2 || parts.some(function (part) { return part === "." || part === ".." || !/^[A-Za-z0-9_.-]+$/.test(part); })) {
      throw new Error("URL_INVALID");
    }
    var repo = parts[1].replace(/\.git$/, "");
    if (!repo || repo === "." || repo === "..") throw new Error("URL_INVALID");
    return parts[0] + "/" + repo;
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var normalized;
    try {
      normalized = normalizeRepository(input.value);
    } catch (_) {
      setStatus("failure", language.value === "en" ? "Please enter a valid public GitHub repository URL." : "공개 GitHub 저장소 주소를 확인해 주세요.");
      input.focus();
      return;
    }
    setStatus("accepted", language.value === "en" ? "Accepted. Opening the trusted GitHub scan form…" : "요청을 확인했습니다. 안전한 GitHub 진단 양식을 엽니다…");
    var params = new URLSearchParams();
    params.set("template", "public-scan.yml");
    params.set("repository_url", normalized);
    params.set("result_language", language.value === "en" ? "English" : "한국어");
    window.location.assign(issueFormUrl + "?" + params.toString());
  });
}());
