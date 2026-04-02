/* ── API Client ─────────────────────────────────────────────────── */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ApiError {
  detail: string;
}

class ApiClient {
  private token: string | null = null;

  constructor() {
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('auth_token');
    }
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', token);
    }
  }

  clearToken() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...((options.headers as Record<string, string>) || {}),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    // Remove content-type for FormData
    if (options.body instanceof FormData) {
      delete headers['Content-Type'];
    }

    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${res.status}`);
    }

    if (res.status === 204) return {} as T;

    const contentType = res.headers.get('content-type');
    if (contentType?.includes('text/csv')) {
      return (await res.text()) as unknown as T;
    }

    return res.json();
  }

  // ── Auth ──
  async login(email: string, password: string) {
    const data = await this.request<{ access_token: string; token_type: string }>(
      '/api/v1/auth/login',
      { method: 'POST', body: JSON.stringify({ email, password }) }
    );
    this.setToken(data.access_token);
    return data;
  }

  async register(email: string, password: string, fullName?: string) {
    return this.request('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
  }

  async getMe() {
    return this.request<{
      id: string;
      email: string;
      full_name: string | null;
      is_admin: boolean;
    }>('/api/v1/auth/me');
  }

  // ── Reviews ──
  async getReviews() {
    return this.request<Review[]>('/api/v1/reviews');
  }

  async getReview(id: string) {
    return this.request<ReviewWithStats>(`/api/v1/reviews/${id}`);
  }

  async createReview(data: CreateReviewData) {
    return this.request<Review>('/api/v1/reviews', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateReview(id: string, data: Partial<CreateReviewData>) {
    return this.request<Review>(`/api/v1/reviews/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteReview(id: string) {
    return this.request(`/api/v1/reviews/${id}`, { method: 'DELETE' });
  }

  // ── Search ──
  async triggerSearch(reviewId: string, query: string, maxResults: number = 100) {
    return this.request<TaskStatus>(`/api/v1/reviews/${reviewId}/search`, {
      method: 'POST',
      body: JSON.stringify({ query, max_results: maxResults }),
    });
  }

  async getStudies(reviewId: string) {
    return this.request<StudyBrief[]>(`/api/v1/reviews/${reviewId}/studies`);
  }

  async getStudy(reviewId: string, studyId: string) {
    return this.request<Study>(`/api/v1/reviews/${reviewId}/studies/${studyId}`);
  }

  async getProgress(reviewId: string) {
    return this.request<TaskStatus[]>(`/api/v1/reviews/${reviewId}/progress`);
  }

  // ── Screening ──
  async triggerScreening(reviewId: string, batchSize: number = 10) {
    return this.request<TaskStatus>(`/api/v1/reviews/${reviewId}/screen`, {
      method: 'POST',
      body: JSON.stringify({ batch_size: batchSize }),
    });
  }

  async getScreenings(reviewId: string) {
    return this.request<Screening[]>(`/api/v1/reviews/${reviewId}/screenings`);
  }

  // ── Extraction ──
  async triggerExtraction(reviewId: string, batchSize: number = 5) {
    return this.request<TaskStatus>(`/api/v1/reviews/${reviewId}/extract`, {
      method: 'POST',
      body: JSON.stringify({ batch_size: batchSize }),
    });
  }

  async getExtractions(reviewId: string) {
    return this.request<Extraction[]>(`/api/v1/reviews/${reviewId}/extractions`);
  }

  async uploadPdf(reviewId: string, studyId: string, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    return this.request(`/api/v1/reviews/${reviewId}/studies/${studyId}/upload-pdf`, {
      method: 'POST',
      body: formData,
    });
  }

  // ── Validation ──
  async triggerValidation(reviewId: string, batchSize: number = 5) {
    return this.request<TaskStatus>(`/api/v1/reviews/${reviewId}/validate`, {
      method: 'POST',
      body: JSON.stringify({ batch_size: batchSize }),
    });
  }

  async getValidations(reviewId: string) {
    return this.request<Validation[]>(`/api/v1/reviews/${reviewId}/validations`);
  }

  // ── Export ──
  async exportResults(reviewId: string, format: 'csv' | 'json' = 'csv') {
    return this.request(`/api/v1/reviews/${reviewId}/export?format=${format}`);
  }
}

export const api = new ApiClient();

// ── Types ──
export interface Review {
  id: string;
  title: string;
  description: string | null;
  search_query: string | null;
  inclusion_criteria: string | null;
  exclusion_criteria: string | null;
  status: string;
  total_studies: number;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface ReviewStats {
  total_studies: number;
  screened: number;
  included: number;
  excluded: number;
  uncertain: number;
  extracted: number;
  validated: number;
  pending_review: number;
}

export interface ReviewWithStats extends Review {
  stats: ReviewStats;
}

export interface CreateReviewData {
  title: string;
  description?: string;
  search_query?: string;
  inclusion_criteria?: string;
  exclusion_criteria?: string;
}

export interface StudyBrief {
  id: string;
  pmid: string | null;
  title: string;
  authors: string | null;
  journal: string | null;
  screening_status: string;
  extraction_status: string;
  validation_status: string;
}

export interface Study extends StudyBrief {
  pmcid: string | null;
  doi: string | null;
  abstract: string | null;
  publication_date: string | null;
  mesh_terms: string | null;
  pdf_available: boolean;
  review_id: string;
  created_at: string;
}

export interface Screening {
  id: string;
  study_id: string;
  decision: 'include' | 'exclude' | 'uncertain';
  rationale: string;
  confidence: number;
  model_used: string;
  provider: string;
  created_at: string;
}

export interface Extraction {
  id: string;
  study_id: string;
  population: string;
  intervention: string;
  comparator: string;
  outcome: string;
  study_design: string;
  sample_size: string;
  duration: string;
  setting: string;
  confidence_scores: Record<string, number>;
  source_quotes: Record<string, string>;
  model_used: string;
  provider: string;
  created_at: string;
}

export interface Validation {
  id: string;
  extraction_id: string;
  validator_model: string;
  validator_provider: string;
  agreement_score: number;
  field_agreements: Record<string, boolean>;
  discrepancies: Record<string, any>;
  needs_human_review: boolean;
  human_reviewed: boolean;
  final_decision: string;
  created_at: string;
}

export interface TaskStatus {
  task_id: string;
  task_type: string;
  status: string;
  progress: number;
  total_items: number;
  completed_items: number;
  error_message: string | null;
}
