import axios from "axios";

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
  timeout: 10000
});

const LONG_RUNNING_TIMEOUT = 30000;

function normalizeError(error) {
  const status = error?.response?.status || 0;
  const detail = error?.response?.data?.detail || error?.message || "unknown error";
  return {
    ok: false,
    error: "Request failed",
    status,
    detail
  };
}

function ok(data) {
  return {
    ok: true,
    data
  };
}

export async function fetchHealth() {
  try {
    const { data } = await http.get("/health");
    return ok(data);
  } catch (error) {
    return normalizeError(error);
  }
}

export async function fetchGraphOverview() {
  try {
    const { data } = await http.get("/graph/overview");
    return ok(data);
  } catch (error) {
    return normalizeError(error);
  }
}

export async function fetchConceptDetail(conceptId) {
  try {
    const { data } = await http.get(`/concept/${encodeURIComponent(conceptId)}`);
    return ok(data);
  } catch (error) {
    return normalizeError(error);
  }
}

export async function fetchConceptCorpus(limit = 2000) {
  try {
    const { data } = await http.get("/concepts", { params: { limit } });
    return ok(data);
  } catch (error) {
    return normalizeError(error);
  }
}

export async function fetchRecommendPath(payload) {
  try {
    const { data } = await http.post("/path/recommend", payload, {
      timeout: LONG_RUNNING_TIMEOUT
    });
    return ok(data);
  } catch (error) {
    return normalizeError(error);
  }
}

export async function fetchPathExplanation(payload) {
  try {
    const { data } = await http.post("/path/explain", payload, {
      timeout: LONG_RUNNING_TIMEOUT
    });
    return ok(data);
  } catch (error) {
    return normalizeError(error);
  }
}

export async function fetchPlannerInterpret(payload) {
  try {
    const { data } = await http.post("/planner/interpret", payload, {
      timeout: LONG_RUNNING_TIMEOUT
    });
    return ok(data);
  } catch (error) {
    return normalizeError(error);
  }
}

export async function fetchGraphRagQuery(payload) {
  try {
    const { data } = await http.post("/graphrag/query", payload, {
      timeout: LONG_RUNNING_TIMEOUT
    });
    return ok(data);
  } catch (error) {
    return normalizeError(error);
  }
}
