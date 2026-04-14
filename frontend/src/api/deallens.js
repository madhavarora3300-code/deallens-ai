const API = "/v1";

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    let error;
    try {
      error = await res.json();
    } catch {
      error = { message: `HTTP ${res.status}` };
    }
    throw Object.assign(new Error(error.message || `API error ${res.status}`), { status: res.status, body: error });
  }
  return res.json();
}

// Entity
export const resolveEntity = (query, queryType = "auto", jurisdictionHint = null) =>
  request(`${API}/entity/resolve`, {
    method: "POST",
    body: JSON.stringify({ query, query_type: queryType, jurisdiction_hint: jurisdictionHint }),
  });

// Company
export const getCompanyProfile = (companyId) =>
  request(`${API}/company/${companyId}`);

export const getEnrichmentStatus = (companyId) =>
  request(`${API}/company/${companyId}/enrichment-status`);

export const checkDiscoveryEligibility = (companyId) =>
  request(`${API}/company/${companyId}/discovery-eligibility`);

export const triggerEnrichment = (companyId) =>
  request(`${API}/company/${companyId}/enrich`, { method: "POST" });

// Discovery
export const runBuySideDiscovery = (payload) =>
  request(`${API}/discovery/buy-side`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const runSellSideDiscovery = (payload) =>
  request(`${API}/discovery/sell-side`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

// Regulatory
export const predictRegulatory = (payload) =>
  request(`${API}/regulatory/predict`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

// Drafts
export const generateDraft = (payload) =>
  request(`${API}/drafts/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

// Market Intelligence
export const getMarketFeed = (period = "daily", category = "all", limit = 50) =>
  request(`${API}/market-intelligence/feed?period=${period}&category=${category}&limit=${limit}`);

export const getCompanyNews = (companyId) =>
  request(`${API}/market-intelligence/company/${companyId}/news`);

export const triggerMarketFetch = () =>
  request(`${API}/market-intelligence/fetch`, { method: "POST" });

// Shortlists
export const addToShortlist = (payload) =>
  request(`${API}/shortlists`, { method: "POST", body: JSON.stringify(payload) });

export const listShortlists = () =>
  request(`${API}/shortlists`);

export const getShortlist = (shortlistId) =>
  request(`${API}/shortlists/${shortlistId}`);

export const removeFromShortlist = (shortlistId, companyId) =>
  request(`${API}/shortlists/${shortlistId}/company/${companyId}`, { method: "DELETE" });

// Health
export const healthCheck = () =>
  request(`${API}/health`);
