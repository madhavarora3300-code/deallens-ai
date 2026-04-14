const API_BASE = import.meta.env.PROD 
  ? "/v1"  // Production: same domain
  : "http://localhost:8000/v1";  // Development

const request = async (endpoint, options = {}) => {
  const response = await fetch(`${API_BASE}${endpoint}`, {
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

export const resolveEntity = (query, queryType = "auto") =>
  request("/entity/resolve", { 
    method: "POST",
    body: JSON.stringify({ query, query_type: queryType }) 
  });

export const getCompanyProfile = (companyId) =>
  request(`/company/${companyId}`);

export const getEnrichmentStatus = (companyId) =>
  request(`/company/${companyId}/enrichment-status`);

export const checkDiscoveryEligibility = (companyId) =>
  request(`/company/${companyId}/discovery-eligibility`);

export const runBuySideDiscovery = (payload) =>
  request("/discovery/buy-side", { 
    method: "POST",
    body: JSON.stringify(payload) 
  });

export const runSellSideDiscovery = (payload) =>
  request("/discovery/sell-side", { 
    method: "POST",
    body: JSON.stringify(payload) 
  });

export const predictRegulatory = (payload) =>
  request("/regulatory/predict", { 
    method: "POST",
    body: JSON.stringify(payload) 
  });

export const generateDraft = (payload) =>
  request("/drafts/generate", { 
    method: "POST",
    body: JSON.stringify(payload) 
  });

export const getMarketFeed = (period = "daily", category = "all", limit = 50) =>
  request(`/market-intelligence/feed?period=${period}&category=${category}&limit=${limit}`);

export const getCompanyNews = (companyId) =>
  request(`/market-intelligence/company/${companyId}/news`);
