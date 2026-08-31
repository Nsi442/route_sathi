import client from './client';

/** Thin, typed-ish wrappers around the FastAPI endpoints. */

// --- auth -------------------------------------------------------------------
export const authApi = {
  login: (payload) => client.post('/auth/login', payload).then((r) => r.data),
  signup: (payload) => client.post('/auth/signup', payload).then((r) => r.data),
  me: () => client.get('/auth/me').then((r) => r.data),
};

// --- citizen ----------------------------------------------------------------
export const userApi = {
  home: (params) => client.get('/user/home', { params }).then((r) => r.data),
  profile: () => client.get('/user/profile').then((r) => r.data),
  updateProfile: (payload) => client.patch('/user/profile', payload).then((r) => r.data),
  changePassword: (payload) => client.post('/user/password', payload).then((r) => r.data),
  reports: (params) => client.get('/user/reports', { params }).then((r) => r.data),
  report: (id) => client.get(`/user/reports/${id}`).then((r) => r.data),
  createReport: (formData) =>
    client
      .post('/user/reports', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data),
};

// --- facilities -------------------------------------------------------------
export const facilityApi = {
  types: () => client.get('/facilities/types').then((r) => r.data),
  nearby: (params) => client.get('/facilities/nearby', { params }).then((r) => r.data),
  list: (params) => client.get('/facilities', { params }).then((r) => r.data),
  detail: (id) => client.get(`/facilities/${id}`).then((r) => r.data),
  update: (id, payload) => client.patch(`/facilities/${id}`, payload).then((r) => r.data),
};

// --- reports (shared) -------------------------------------------------------
export const reportApi = {
  options: () => client.get('/reports/options').then((r) => r.data),
  mapPins: (params) => client.get('/reports/map', { params }).then((r) => r.data),
  imageLink: (id) => client.get(`/reports/${id}/image`).then((r) => r.data),
};

// --- notifications ----------------------------------------------------------
export const notificationApi = {
  list: (params) => client.get('/notifications', { params }).then((r) => r.data),
  count: () => client.get('/notifications/count').then((r) => r.data),
  markRead: (id) => client.post(`/notifications/${id}/read`).then((r) => r.data),
  markAllRead: () => client.post('/notifications/read-all').then((r) => r.data),
};

// --- authority --------------------------------------------------------------
export const authorityApi = {
  overview: () => client.get('/authority/overview').then((r) => r.data),
  filters: () => client.get('/authority/filters').then((r) => r.data),
  uploadCsv: (file, onProgress) => {
    const form = new FormData();
    form.append('file', file);
    return client
      .post('/authority/reports/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: onProgress,
      })
      .then((r) => r.data);
  },
  reports: (params) => client.get('/authority/reports', { params }).then((r) => r.data),
  report: (id) => client.get(`/authority/reports/${id}`).then((r) => r.data),
  reportAudit: (id) => client.get(`/authority/reports/${id}/audit`).then((r) => r.data),
  validate: (id, payload) =>
    client.post(`/authority/reports/${id}/validate`, payload).then((r) => r.data),
  setStatus: (id, payload) =>
    client.post(`/authority/reports/${id}/status`, payload).then((r) => r.data),
  predictPriority: (id) =>
    client.post(`/authority/reports/${id}/priority/predict`).then((r) => r.data),
  confirmPriority: (id, payload) =>
    client.post(`/authority/reports/${id}/priority/confirm`, payload).then((r) => r.data),
  assign: (id, payload) =>
    client.post(`/authority/reports/${id}/assign`, payload).then((r) => r.data),
  tasks: (params) => client.get('/authority/tasks', { params }).then((r) => r.data),
  verify: (taskId, payload) =>
    client.post(`/authority/tasks/${taskId}/verify`, payload).then((r) => r.data),
  teams: () => client.get('/authority/teams').then((r) => r.data),
  audit: (params) => client.get('/authority/audit', { params }).then((r) => r.data),
};

// --- analytics --------------------------------------------------------------
export const analyticsApi = {
  summary: (params) => client.get('/analytics', { params }).then((r) => r.data),
  map: (params) => client.get('/analytics/map', { params }).then((r) => r.data),
};

// --- maintenance ------------------------------------------------------------
export const maintenanceApi = {
  summary: () => client.get('/maintenance/summary').then((r) => r.data),
  tasks: (params) => client.get('/maintenance/tasks', { params }).then((r) => r.data),
  task: (id) => client.get(`/maintenance/tasks/${id}`).then((r) => r.data),
  setStatus: (id, payload) =>
    client.post(`/maintenance/tasks/${id}/status`, payload).then((r) => r.data),
  setNotes: (id, payload) =>
    client.patch(`/maintenance/tasks/${id}/notes`, payload).then((r) => r.data),
  resolutionLink: (id) =>
    client.get(`/maintenance/tasks/${id}/resolution/link`).then((r) => r.data),
  uploadResolution: (id, file, notes) => {
    const form = new FormData();
    form.append('photo', file);
    if (notes) form.append('maintenance_notes', notes);
    return client
      .post(`/maintenance/tasks/${id}/resolution`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },
};

export const systemApi = {
  health: () => client.get('/health').then((r) => r.data),
};
