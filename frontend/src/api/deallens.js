const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const request = async (endpoint, options = {}) => {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
};

// Entity Resolution
export const resolveEntity = (query, queryType = "auto") =>
  request("/v1/entity/resolve", { 
    method: "POST",
    body: JSON.stringify({ query, query_type: queryType }) 
  });

// Company Profile
export const getCompanyProfile = (companyId) =>
  request(`/v1/company/${companyId}`);

export const getEnrichmentStatus = (companyId) =>
  request(`/v1/company/${companyId}/enrichment-status`);

export const checkDiscoveryEligibility = (companyId) =>
  request(`/v1/company/${companyId}/discovery-eligibility`);

export const triggerEnrichment = (companyId) =>
  request(`/v1/company/${companyId}/enrich`, { method: "POST" });

// Discovery
export const runBuySideDiscovery = (payload) =>
  request("/v1/discovery/buy-side", { 
    method: "POST",
    body: JSON.stringify(payload) 
  });

export const runSellSideDiscovery = (payload) =>
  request("/v1/discovery/sell-side", { 
    method: "POST",
    body: JSON.stringify(payload) 
  });

// Regulatory
export const predictRegulatory = (payload) =>
  request("/v1/regulatory/predict", { 
    method: "POST",
    body: JSON.stringify(payload) 
  });

// Drafts
export const generateDraft = (payload) =>
  request("/v1/drafts/generate", { 
    method: "POST",
    body: JSON.stringify(payload) 
  });

// Market Intelligence
export const getMarketFeed = (period = "daily", category = "all", limit = 50) =>
  request(`/v1/market-intelligence/feed?period=${period}&category=${category}&limit=${limit}`);

export const getCompanyNews = (companyId) =>
  request(`/v1/market-intelligence/company/${companyId}/news`);

export const triggerMarketFetch = () =>
  request("/v1/market-intelligence/fetch", { method: "POST" });

// Shortlists
export const getShortlists = () =>
  request("/v1/shortlists");

export const getShortlist = (shortlistId) =>
  request(`/v1/shortlists/${shortlistId}`);

export const addToShortlist = (payload) =>
  request("/v1/shortlists", {
    method: "POST",
    body: JSON.stringify(payload)
  });

export const removeFromShortlist = (shortlistId, companyId) =>
  request(`/v1/shortlists/${shortlistId}/company/${companyId}`, {
    method: "DELETE"
  });
