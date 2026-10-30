/**
 * Simple Credential Manager - Modern Single-Page Application Client
 * Zero-dependency ES6 application handling UI transitions, API communication,
 * Out-of-Band device enrollment, TOTP timer arcs, and secret management.
 */

(function () {
  'use strict';

  // --- Constants & Storage Keys ---
  const STORAGE_KEYS = {
    DEVICE_TOKEN: 'scm_device_token',
    DEVICE_ID: 'scm_device_id',
    DEVICE_NAME: 'scm_device_name',
    DEVICE_FINGERPRINT: 'scm_device_fingerprint',
    SESSION_TOKEN: 'scm_session_token'
  };

  // Compute base path relative to current URL (supports reverse-proxy subpaths like /password/)
  const API_BASE = (function () {
    const path = window.location.pathname;
    // If running at /enroll or /enroll/, root is parent
    if (path.includes('/enroll')) {
      const idx = path.indexOf('/enroll');
      return path.substring(0, idx).replace(/\/+$/, '') + '/api/v1';
    }
    // Normal root
    return path.replace(/\/+$/, '') + '/api/v1';
  })();

  // --- Application State ---
  const state = {
    deviceToken: localStorage.getItem(STORAGE_KEYS.DEVICE_TOKEN) || '',
    deviceId: localStorage.getItem(STORAGE_KEYS.DEVICE_ID) || '',
    deviceName: localStorage.getItem(STORAGE_KEYS.DEVICE_NAME) || '',
    deviceFingerprint: localStorage.getItem(STORAGE_KEYS.DEVICE_FINGERPRINT) || '',
    sessionToken: sessionStorage.getItem(STORAGE_KEYS.SESSION_TOKEN) || '',
    secrets: [],
    selectedSecretName: null,
    activeCategoryFilter: 'all',
    activeFavoritesOnly: false,
    searchQuery: '',
    sortAscending: true,
    totpInterval: null,
    enrollPollInterval: null,
    lockoutInterval: null,
    sessionCheckInterval: null
  };

  // --- DOM Elements Cache ---
  const el = {};

  function initElementRefs() {
    el.viewEnroll = document.getElementById('view-enroll');
    el.viewUnlock = document.getElementById('view-unlock');
    el.viewDashboard = document.getElementById('view-dashboard');
    el.toastContainer = document.getElementById('toast-container');

    // Enrollment
    el.enrollApprovedState = document.getElementById('enroll-approved-state');
    el.enrollApprovedDeviceName = document.getElementById('enroll-approved-device-name');
    el.btnGotoUnlock = document.getElementById('btn-goto-unlock');
    el.btnReRegister = document.getElementById('btn-re-register');
    el.enrollFormState = document.getElementById('enroll-form-state');
    el.enrollForm = document.getElementById('enroll-form');
    el.enrollDeviceName = document.getElementById('enroll-device-name');
    el.enrollSecretWrapper = document.getElementById('enroll-secret-wrapper');
    el.enrollSecretToken = document.getElementById('enroll-secret-token');
    el.enrollWaitingState = document.getElementById('enroll-waiting-state');
    el.enrollCliCommand = document.getElementById('enroll-cli-command');
    el.btnCopyCommand = document.getElementById('btn-copy-command');
    el.btnCopyFingerprint = document.getElementById('btn-copy-fingerprint');
    el.enrollFpDisplay = document.getElementById('enroll-fp-display');
    el.enrollIdDisplay = document.getElementById('enroll-id-display');

    // Unlock
    el.unlockForm = document.getElementById('unlock-form');
    el.unlockPassword = document.getElementById('unlock-password');
    el.lockoutWarning = document.getElementById('lockout-warning');
    el.lockoutMessage = document.getElementById('lockout-message');
    el.lockoutTimer = document.getElementById('lockout-timer');
    el.trustedDeviceName = document.getElementById('trusted-device-name');
    el.btnForgetDevice = document.getElementById('btn-forget-device');

    // Dashboard Header & Search
    el.globalSearch = document.getElementById('global-search');
    el.btnClearSearch = document.getElementById('btn-clear-search');
    el.btnAddSecretTop = document.getElementById('btn-add-secret-top');
    el.btnLockVault = document.getElementById('btn-lock-vault');

    // Sidebar
    el.navItems = document.querySelectorAll('.nav-item');
    el.countAll = document.getElementById('count-all');
    el.countLogin = document.getElementById('count-login');
    el.countCard = document.getElementById('count-card');
    el.countServer = document.getElementById('count-server');
    el.countNote = document.getElementById('count-note');
    el.countFavorites = document.getElementById('count-favorites');
    el.sidebarDeviceId = document.getElementById('sidebar-device-id');

    // List Pane
    el.currentViewHeading = document.getElementById('current-view-heading');
    el.filteredItemsCount = document.getElementById('filtered-items-count');
    el.btnToggleSort = document.getElementById('btn-toggle-sort');
    el.sortOrderLabel = document.getElementById('sort-order-label');
    el.secretsItemsContainer = document.getElementById('secrets-items-container');
    el.emptyStateList = document.getElementById('empty-state-list');
    el.emptyStateMessage = document.getElementById('empty-state-message');
    el.btnEmptyAdd = document.getElementById('btn-empty-add');

    // Detail Pane
    el.secretDetailPane = document.getElementById('secret-detail-pane');
    el.detailPlaceholder = document.getElementById('detail-placeholder');
    el.detailContent = document.getElementById('detail-content');
    el.detailCategoryIcon = document.getElementById('detail-category-icon');
    el.detailName = document.getElementById('detail-name');
    el.btnDetailFav = document.getElementById('btn-detail-fav');
    el.detailCategoryBadge = document.getElementById('detail-category-badge');
    el.detailDomain = document.getElementById('detail-domain');
    el.btnEditSecret = document.getElementById('btn-edit-secret');
    el.btnDeleteSecret = document.getElementById('btn-delete-secret');

    el.detailUsername = document.getElementById('detail-username');
    el.btnCopyUsername = document.getElementById('btn-copy-username');
    el.detailPassword = document.getElementById('detail-password');
    el.btnToggleDetailPassword = document.getElementById('btn-toggle-detail-password');
    el.btnCopyPassword = document.getElementById('btn-copy-password');

    // TOTP
    el.totpFieldWrapper = document.getElementById('totp-field-wrapper');
    el.totpCodeText = document.getElementById('totp-code-text');
    el.totpArcIndicator = document.getElementById('totp-arc-indicator');
    el.totpSecondsLabel = document.getElementById('totp-seconds-label');
    el.btnCopyTotp = document.getElementById('btn-copy-totp');

    // URL, Tags, Comments, Timestamps
    el.urlFieldWrapper = document.getElementById('url-field-wrapper');
    el.detailUrl = document.getElementById('detail-url');
    el.detailUrlLink = document.getElementById('detail-url-link');
    el.tagsFieldWrapper = document.getElementById('tags-field-wrapper');
    el.detailTagsList = document.getElementById('detail-tags-list');
    el.commentsFieldWrapper = document.getElementById('comments-field-wrapper');
    el.detailComments = document.getElementById('detail-comments');
    el.detailCreatedAt = document.getElementById('detail-created-at');
    el.detailUpdatedAt = document.getElementById('detail-updated-at');
    el.detailUpdatedRow = document.getElementById('detail-updated-row');

    // Secret Editor Modal
    el.modalSecretEditor = document.getElementById('modal-secret-editor');
    el.modalTitle = document.getElementById('modal-title');
    el.btnCloseModal = document.getElementById('btn-close-modal');
    el.btnCancelModal = document.getElementById('btn-cancel-modal');
    el.formSecretEditor = document.getElementById('form-secret-editor');
    el.editorOriginalName = document.getElementById('editor-original-name');
    el.editorName = document.getElementById('editor-name');
    el.editorCategory = document.getElementById('editor-category');
    el.editorUsername = document.getElementById('editor-username');
    el.editorPassword = document.getElementById('editor-password');
    el.editorUrl = document.getElementById('editor-url');
    el.editorTotp = document.getElementById('editor-totp');
    el.editorTags = document.getElementById('editor-tags');
    el.editorComments = document.getElementById('editor-comments');
    el.editorIsFavorite = document.getElementById('editor-is-favorite');
    el.btnGeneratePassword = document.getElementById('btn-generate-password');

    // Delete Confirmation Modal
    el.modalDeleteConfirm = document.getElementById('modal-delete-confirm');
    el.btnCloseDeleteModal = document.getElementById('btn-close-delete-modal');
    el.btnCancelDelete = document.getElementById('btn-cancel-delete');
    el.btnConfirmDelete = document.getElementById('btn-confirm-delete');
    el.deleteSecretNameLabel = document.getElementById('delete-secret-name-label');
  }

  // --- WebCrypto Transport Encryption ---
  function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    const chunkSize = 32768;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      const chunk = bytes.subarray(i, Math.min(i + chunkSize, bytes.length));
      binary += String.fromCharCode.apply(null, chunk);
    }
    return btoa(binary);
  }

  async function encryptDevicePayload(plaintextString, deviceToken) {
    if (!window.crypto || !window.crypto.subtle) {
      return null;
    }
    if (!deviceToken) {
      return null;
    }

    try {
      const encoder = new TextEncoder();
      const tokenBytes = encoder.encode(deviceToken);

      const baseKey = await window.crypto.subtle.importKey(
        'raw',
        tokenBytes,
        'HKDF',
        false,
        ['deriveKey']
      );

      const derivedKey = await window.crypto.subtle.deriveKey(
        {
          name: 'HKDF',
          hash: 'SHA-256',
          salt: encoder.encode('scm-transport-v1'),
          info: encoder.encode('scm-payload-encryption-v1')
        },
        baseKey,
        { name: 'AES-GCM', length: 256 },
        false,
        ['encrypt']
      );

      const iv = window.crypto.getRandomValues(new Uint8Array(12));
      const plaintextBytes = encoder.encode(plaintextString);

      const ciphertextBuffer = await window.crypto.subtle.encrypt(
        { name: 'AES-GCM', iv },
        derivedKey,
        plaintextBytes
      );

      return {
        iv: arrayBufferToBase64(iv.buffer),
        ciphertext: arrayBufferToBase64(ciphertextBuffer)
      };
    } catch (err) {
      console.warn('WebCrypto payload encryption failed, falling back to plaintext:', err);
      return null;
    }
  }

  // --- API Client ---
  async function apiFetch(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
    const headers = options.headers || {};

    // Attach device token if available
    if (state.deviceToken) {
      headers['X-Device-Token'] = state.deviceToken;
    }
    // Attach session token if available
    if (state.sessionToken) {
      headers['X-Session-Token'] = state.sessionToken;
    }

    let requestBody = options.body;

    // Device-bound WebCrypto encryption for request payload
    if (requestBody && state.deviceToken && !(requestBody instanceof FormData)) {
      const plaintextStr = typeof requestBody === 'string' ? requestBody : JSON.stringify(requestBody);
      const encrypted = await encryptDevicePayload(plaintextStr, state.deviceToken);
      if (encrypted) {
        requestBody = JSON.stringify(encrypted);
        headers['Content-Type'] = 'application/json';
      }
    }

    if (!headers['Content-Type'] && !(requestBody instanceof FormData) && options.method && options.method !== 'GET') {
      headers['Content-Type'] = 'application/json';
    }

    const config = {
      ...options,
      headers,
      body: requestBody
    };

    try {
      const response = await fetch(url, config);

      // Handle 401 Unauthorized (Session Expired / Vault Locked)
      if (response.status === 401 && !url.includes('/auth/unlock')) {
        state.sessionToken = '';
        sessionStorage.removeItem(STORAGE_KEYS.SESSION_TOKEN);
        showUnlockView();
        showToast('Vault locked due to inactivity.', 'error');
        throw new Error('Session expired');
      }

      // Handle 403 Forbidden (Device Not Whitelisted / Revoked)
      if (response.status === 403 && !url.includes('/devices/enroll')) {
        showToast('Device authorization revoked or unknown. Please re-enroll.', 'error');
        showEnrollmentView();
        throw new Error('Device not approved');
      }

      const contentType = response.headers.get('content-type') || '';
      let data = null;
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        const errorMsg = (data && data.detail) || (data && data.message) || response.statusText || 'Request failed';
        const err = new Error(errorMsg);
        err.status = response.status;
        err.data = data;
        throw err;
      }

      return data;
    } catch (err) {
      throw err;
    }
  }

  // --- UI Helpers & Notifications ---
  function showToast(message, type = 'info', duration = 3000) {
    if (!el.toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
    } else if (type === 'error') {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
    } else {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }

    toast.innerHTML = `${iconSvg}<span>${escapeHtml(message)}</span>`;
    el.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-10px)';
      toast.style.transition = 'all 0.2s ease-out';
      setTimeout(() => toast.remove(), 250);
    }, duration);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function detectClientDeviceName() {
    const ua = navigator.userAgent;
    let os = 'Unknown Device';
    if (ua.includes('Win')) os = 'Windows PC';
    else if (ua.includes('Macintosh') || ua.includes('Mac OS')) os = 'MacBook';
    else if (ua.includes('iPhone') || ua.includes('iPad')) os = 'Apple iOS';
    else if (ua.includes('Android')) os = 'Android Device';
    else if (ua.includes('Linux')) os = 'Linux Station';

    let browser = 'Browser';
    if (ua.includes('Edg/')) browser = 'Edge';
    else if (ua.includes('Chrome/')) browser = 'Chrome';
    else if (ua.includes('Safari/') && !ua.includes('Chrome')) browser = 'Safari';
    else if (ua.includes('Firefox/')) browser = 'Firefox';

    return `${os} (${browser})`;
  }

  function extractDomain(url) {
    if (!url) return '';
    try {
      const parsed = new URL(url.startsWith('http') ? url : `https://${url}`);
      return parsed.hostname.replace(/^www\./, '');
    } catch (e) {
      return url.split('/')[0];
    }
  }

  // --- View Switcher ---
  function showView(viewEl) {
    [el.viewEnroll, el.viewUnlock, el.viewDashboard].forEach(v => {
      if (v) v.classList.add('hidden');
    });
    if (viewEl) viewEl.classList.remove('hidden');
  }

  function showAlreadyApprovedView(deviceName) {
    showView(el.viewEnroll);
    stopPollingApproval();
    stopTotpTimer();

    const name = deviceName || state.deviceName || 'this device';
    if (el.enrollApprovedDeviceName) {
      el.enrollApprovedDeviceName.textContent = name;
    }
    if (el.enrollApprovedState) el.enrollApprovedState.classList.remove('hidden');
    if (el.enrollFormState) el.enrollFormState.classList.add('hidden');
    if (el.enrollWaitingState) el.enrollWaitingState.classList.add('hidden');
  }

  function showEnrollmentView() {
    showView(el.viewEnroll);
    stopPollingApproval();
    stopTotpTimer();

    if (el.enrollApprovedState) el.enrollApprovedState.classList.add('hidden');
    if (el.enrollWaitingState) el.enrollWaitingState.classList.add('hidden');
    if (el.enrollFormState) el.enrollFormState.classList.remove('hidden');

    // Check query params for secret
    const urlParams = new URLSearchParams(window.location.search);
    const secretFromUrl = urlParams.get('secret');

    if (secretFromUrl) {
      if (el.enrollSecretToken) el.enrollSecretToken.value = secretFromUrl;
      if (el.enrollSecretWrapper) el.enrollSecretWrapper.classList.add('hidden');
    } else {
      if (el.enrollSecretWrapper) el.enrollSecretWrapper.classList.remove('hidden');
    }

    // Default device name
    if (el.enrollDeviceName) {
      el.enrollDeviceName.value = state.deviceName || detectClientDeviceName();
    }
  }

  function showUnlockView() {
    showView(el.viewUnlock);
    stopPollingApproval();
    stopTotpTimer();

    if (el.trustedDeviceName) {
      el.trustedDeviceName.textContent = state.deviceName ? `(${state.deviceName})` : '';
    }
    if (el.unlockPassword) {
      el.unlockPassword.value = '';
      setTimeout(() => el.unlockPassword.focus(), 100);
    }
    checkLockoutState();
  }

  function showDashboardView() {
    showView(el.viewDashboard);
    stopPollingApproval();
    if (el.sidebarDeviceId) {
      el.sidebarDeviceId.textContent = `ID: ${state.deviceId || 'Host'}`;
    }
    loadSecrets();
    startSessionMonitor();
  }

  // --- Enrollment Flow ---
  async function handleEnrollSubmit(e) {
    e.preventDefault();
    const deviceName = el.enrollDeviceName.value.trim() || detectClientDeviceName();
    const urlParams = new URLSearchParams(window.location.search);
    const secret = urlParams.get('secret') || (el.enrollSecretToken ? el.enrollSecretToken.value.trim() : '');

    try {
      const endpoint = secret ? `/devices/enroll?secret=${encodeURIComponent(secret)}` : '/devices/enroll';
      const data = await apiFetch(endpoint, {
        method: 'POST',
        body: JSON.stringify({ device_name: deviceName })
      });

      // Save credentials in state and localStorage
      state.deviceToken = data.device_token || '';
      state.deviceId = data.device_id || '';
      state.deviceName = deviceName;
      state.deviceFingerprint = data.fingerprint || '';

      localStorage.setItem(STORAGE_KEYS.DEVICE_TOKEN, state.deviceToken);
      localStorage.setItem(STORAGE_KEYS.DEVICE_ID, state.deviceId);
      localStorage.setItem(STORAGE_KEYS.DEVICE_NAME, state.deviceName);
      localStorage.setItem(STORAGE_KEYS.DEVICE_FINGERPRINT, state.deviceFingerprint);

      // Render waiting view
      renderWaitingApproval(data.fingerprint, data.device_id);
    } catch (err) {
      showToast(err.message || 'Enrollment failed. Verify your enrollment secret.', 'error');
    }
  }

  function renderWaitingApproval(fingerprint, deviceId) {
    if (el.enrollApprovedState) el.enrollApprovedState.classList.add('hidden');
    if (el.enrollFormState) el.enrollFormState.classList.add('hidden');
    if (el.enrollWaitingState) el.enrollWaitingState.classList.remove('hidden');

    // Prominently display ONLY the full hex fingerprint
    if (el.enrollFpDisplay) el.enrollFpDisplay.textContent = fingerprint || '-';
    if (el.enrollIdDisplay) el.enrollIdDisplay.textContent = deviceId || '-';

    // Start polling device status
    startPollingApproval();
  }

  function startPollingApproval() {
    stopPollingApproval();
    state.enrollPollInterval = setInterval(async () => {
      try {
        const status = await apiFetch('/devices/status');
        if (status.status === 'APPROVED' || status.approved === true) {
          stopPollingApproval();
          showToast('Device approved successfully!', 'success');
          // Clear ?secret query param from URL without reloading
          if (window.history.replaceState) {
            const cleanUrl = window.location.pathname;
            window.history.replaceState({}, document.title, cleanUrl);
          }
          showUnlockView();
        }
      } catch (e) {
        // Continue polling
      }
    }, 2500);
  }

  function stopPollingApproval() {
    if (state.enrollPollInterval) {
      clearInterval(state.enrollPollInterval);
      state.enrollPollInterval = null;
    }
  }

  // --- Auth & Vault Lockout ---
  async function checkLockoutState() {
    try {
      const data = await apiFetch('/auth/status');
      if (data.is_locked_out && data.remaining_seconds > 0) {
        displayLockoutBanner(data.remaining_seconds);
      } else {
        if (el.lockoutWarning) el.lockoutWarning.classList.add('hidden');
        if (el.unlockPassword) el.unlockPassword.disabled = false;
        const btn = document.getElementById('btn-submit-unlock');
        if (btn) btn.disabled = false;
      }
    } catch (e) {
      // Non-fatal
    }
  }

  function displayLockoutBanner(remainingSeconds) {
    if (!el.lockoutWarning) return;
    el.lockoutWarning.classList.remove('hidden');
    if (el.unlockPassword) el.unlockPassword.disabled = true;
    const btn = document.getElementById('btn-submit-unlock');
    if (btn) btn.disabled = true;

    let sec = remainingSeconds;
    if (el.lockoutTimer) el.lockoutTimer.textContent = sec;

    clearInterval(state.lockoutInterval);
    state.lockoutInterval = setInterval(() => {
      sec -= 1;
      if (el.lockoutTimer) el.lockoutTimer.textContent = Math.max(0, sec);
      if (sec <= 0) {
        clearInterval(state.lockoutInterval);
        el.lockoutWarning.classList.add('hidden');
        if (el.unlockPassword) el.unlockPassword.disabled = false;
        if (btn) btn.disabled = false;
        if (el.unlockPassword) el.unlockPassword.focus();
      }
    }, 1000);
  }

  async function handleUnlockSubmit(e) {
    e.preventDefault();
    const password = el.unlockPassword.value;
    if (!password) return;

    try {
      const res = await apiFetch('/auth/unlock', {
        method: 'POST',
        body: JSON.stringify({ password })
      });

      const sessToken = res.session_token || res.token;
      if (sessToken) {
        state.sessionToken = sessToken;
        sessionStorage.setItem(STORAGE_KEYS.SESSION_TOKEN, state.sessionToken);
      }

      showToast('Vault unlocked successfully.', 'success');
      showDashboardView();
    } catch (err) {
      if (err.status === 429 || (err.data && err.data.lockout)) {
        const rem = (err.data && err.data.remaining_seconds) || 30;
        displayLockoutBanner(rem);
      } else {
        showToast(err.message || 'Invalid master password.', 'error');
        if (el.unlockPassword) {
          el.unlockPassword.value = '';
          el.unlockPassword.focus();
        }
      }
    }
  }

  async function handleLockVault() {
    try {
      await apiFetch('/auth/lock', { method: 'POST' });
    } catch (e) {
      // Ignored
    } finally {
      state.sessionToken = '';
      sessionStorage.removeItem(STORAGE_KEYS.SESSION_TOKEN);
      state.selectedSecretName = null;
      state.secrets = [];
      showUnlockView();
      showToast('Vault locked.', 'info');
    }
  }

  function startSessionMonitor() {
    stopSessionMonitor();
    // Periodically verify session is alive every 20 seconds
    state.sessionCheckInterval = setInterval(async () => {
      if (!state.sessionToken) return;
      try {
        const status = await apiFetch('/auth/status');
        if (!status.unlocked) {
          handleLockVault();
        }
      } catch (e) {
        // Handled in apiFetch 401
      }
    }, 20000);
  }

  function stopSessionMonitor() {
    if (state.sessionCheckInterval) {
      clearInterval(state.sessionCheckInterval);
      state.sessionCheckInterval = null;
    }
  }

  function forgetCurrentDevice() {
    if (!confirm('Forget this device? You will need to re-enroll and obtain administrator approval.')) return;
    localStorage.removeItem(STORAGE_KEYS.DEVICE_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.DEVICE_ID);
    localStorage.removeItem(STORAGE_KEYS.DEVICE_NAME);
    localStorage.removeItem(STORAGE_KEYS.DEVICE_FINGERPRINT);
    sessionStorage.removeItem(STORAGE_KEYS.SESSION_TOKEN);
    state.deviceToken = '';
    state.deviceId = '';
    state.deviceName = '';
    state.deviceFingerprint = '';
    state.sessionToken = '';
    showEnrollmentView();
    showToast('Device forgotten.', 'info');
  }

  // --- Secret List & Filters ---
  async function loadSecrets() {
    try {
      const data = await apiFetch('/secrets');
      state.secrets = Array.isArray(data) ? data : (data.secrets || []);
      updateCategoryCounts();
      renderSecretsList();

      // If a secret was previously selected, re-select or maintain selection
      if (state.selectedSecretName) {
        const found = state.secrets.find(s => s.name === state.selectedSecretName);
        if (found) {
          selectSecret(found.name);
        } else {
          deselectSecret();
        }
      }
    } catch (err) {
      showToast('Failed to load secrets.', 'error');
    }
  }

  function updateCategoryCounts() {
    const counts = { all: state.secrets.length, login: 0, card: 0, server: 0, note: 0, favorites: 0 };
    state.secrets.forEach(s => {
      const cat = (s.category || 'login').toLowerCase();
      if (counts[cat] !== undefined) counts[cat] += 1;
      if (s.is_favorite || s.favorite) counts.favorites += 1;
    });

    if (el.countAll) el.countAll.textContent = counts.all;
    if (el.countLogin) el.countLogin.textContent = counts.login;
    if (el.countCard) el.countCard.textContent = counts.card;
    if (el.countServer) el.countServer.textContent = counts.server;
    if (el.countNote) el.countNote.textContent = counts.note;
    if (el.countFavorites) el.countFavorites.textContent = counts.favorites;
  }

  function getFilteredSecrets() {
    return state.secrets.filter(secret => {
      // Category filter
      if (state.activeCategoryFilter !== 'all') {
        const cat = (secret.category || 'login').toLowerCase();
        if (cat !== state.activeCategoryFilter) return false;
      }

      // Favorites filter
      if (state.activeFavoritesOnly) {
        if (!(secret.is_favorite || secret.favorite)) return false;
      }

      // Search query filter
      if (state.searchQuery) {
        const q = state.searchQuery.toLowerCase();
        const nameMatch = (secret.name || '').toLowerCase().includes(q);
        const userMatch = (secret.username || '').toLowerCase().includes(q);
        const urlMatch = (secret.url || '').toLowerCase().includes(q);
        const tagMatch = Array.isArray(secret.tags) ? secret.tags.some(t => t.toLowerCase().includes(q)) : false;
        if (!nameMatch && !userMatch && !urlMatch && !tagMatch) return false;
      }

      return true;
    }).sort((a, b) => {
      const nameA = (a.name || '').toLowerCase();
      const nameB = (b.name || '').toLowerCase();
      return state.sortAscending ? nameA.localeCompare(nameB) : nameB.localeCompare(nameA);
    });
  }

  function renderSecretsList() {
    if (!el.secretsItemsContainer) return;
    const filtered = getFilteredSecrets();

    // Update list count header
    if (el.filteredItemsCount) {
      el.filteredItemsCount.textContent = `${filtered.length} ${filtered.length === 1 ? 'item' : 'items'}`;
    }

    if (filtered.length === 0) {
      el.secretsItemsContainer.innerHTML = '';
      if (el.emptyStateList) {
        el.emptyStateList.classList.remove('hidden');
        if (state.searchQuery) {
          el.emptyStateMessage.textContent = `No items found matching "${state.searchQuery}".`;
        } else if (state.activeCategoryFilter !== 'all') {
          el.emptyStateMessage.textContent = `No ${state.activeCategoryFilter} credentials yet.`;
        } else {
          el.emptyStateMessage.textContent = 'Your vault is currently empty.';
        }
      }
      return;
    }

    if (el.emptyStateList) el.emptyStateList.classList.add('hidden');
    el.secretsItemsContainer.innerHTML = '';

    filtered.forEach(secret => {
      const itemEl = document.createElement('div');
      itemEl.className = `secret-item ${state.selectedSecretName === secret.name ? 'selected' : ''}`;
      itemEl.setAttribute('role', 'listitem');
      itemEl.dataset.name = secret.name;

      const isFav = secret.is_favorite || secret.favorite;
      const cat = (secret.category || 'login').toLowerCase();
      const domain = extractDomain(secret.url);

      itemEl.innerHTML = `
        <div class="item-cat-icon">
          ${getCategoryIconSvg(cat)}
        </div>
        <div class="item-main-info">
          <div class="item-title-row">
            <span class="item-name">${escapeHtml(secret.name)}</span>
            ${isFav ? '<svg class="item-star" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>' : ''}
          </div>
          <div class="item-sub-row">
            <span class="item-username">${escapeHtml(secret.username || domain || 'No account')}</span>
            <span class="item-category-pill">${cat}</span>
          </div>
        </div>
      `;

      itemEl.addEventListener('click', () => selectSecret(secret.name));
      el.secretsItemsContainer.appendChild(itemEl);
    });
  }

  function getCategoryIconSvg(cat) {
    switch (cat) {
      case 'card':
        return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>';
      case 'server':
        return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>';
      case 'note':
        return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
      case 'login':
      default:
        return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
    }
  }

  // --- Secret Selection & Detail Rendering ---
  async function selectSecret(name) {
    state.selectedSecretName = name;
    stopTotpTimer();

    // Mark selected in item list
    document.querySelectorAll('.secret-item').forEach(item => {
      item.classList.toggle('selected', item.dataset.name === name);
    });

    try {
      const secret = await apiFetch(`/secrets/${encodeURIComponent(name)}`);
      renderSecretDetail(secret);
    } catch (err) {
      showToast('Could not load secret details.', 'error');
      deselectSecret();
    }
  }

  function deselectSecret() {
    state.selectedSecretName = null;
    stopTotpTimer();
    if (el.detailContent) el.detailContent.classList.add('hidden');
    if (el.detailPlaceholder) el.detailPlaceholder.classList.remove('hidden');
  }

  function renderSecretDetail(secret) {
    if (!el.detailContent || !el.detailPlaceholder) return;
    el.detailPlaceholder.classList.add('hidden');
    el.detailContent.classList.remove('hidden');

    const isFav = secret.is_favorite || secret.favorite;
    const cat = (secret.category || 'login').toLowerCase();

    // Name & Header
    if (el.detailName) el.detailName.textContent = secret.name;
    if (el.detailCategoryIcon) el.detailCategoryIcon.innerHTML = getCategoryIconSvg(cat);
    if (el.detailCategoryBadge) el.detailCategoryBadge.textContent = cat;

    if (el.btnDetailFav) {
      el.btnDetailFav.classList.toggle('active', !!isFav);
      el.btnDetailFav.onclick = () => toggleSecretFavorite(secret);
    }

    // Domain
    const domain = extractDomain(secret.url);
    if (el.detailDomain) {
      if (domain) {
        el.detailDomain.textContent = domain;
        el.detailDomain.classList.remove('hidden');
      } else {
        el.detailDomain.classList.add('hidden');
      }
    }

    // Username
    if (el.detailUsername) {
      el.detailUsername.textContent = secret.username || '(None)';
    }

    // Password & Reveal Toggle
    if (el.detailPassword) {
      el.detailPassword.textContent = '••••••••••••••••';
      el.detailPassword.dataset.revealed = 'false';
      el.detailPassword.dataset.realPassword = secret.password || '';
    }

    // TOTP Section
    if (secret.totp_secret) {
      if (el.totpFieldWrapper) el.totpFieldWrapper.classList.remove('hidden');
      startTotpCountdown(secret.name);
    } else {
      if (el.totpFieldWrapper) el.totpFieldWrapper.classList.add('hidden');
    }

    // URL
    if (secret.url) {
      if (el.urlFieldWrapper) el.urlFieldWrapper.classList.remove('hidden');
      if (el.detailUrl) el.detailUrl.textContent = secret.url;
      if (el.detailUrlLink) el.detailUrlLink.href = secret.url.startsWith('http') ? secret.url : `https://${secret.url}`;
    } else {
      if (el.urlFieldWrapper) el.urlFieldWrapper.classList.add('hidden');
    }

    // Tags
    if (secret.tags && secret.tags.length > 0) {
      if (el.tagsFieldWrapper) el.tagsFieldWrapper.classList.remove('hidden');
      if (el.detailTagsList) {
        el.detailTagsList.innerHTML = secret.tags.map(t => `<span class="tag-badge">#${escapeHtml(t)}</span>`).join('');
      }
    } else {
      if (el.tagsFieldWrapper) el.tagsFieldWrapper.classList.add('hidden');
    }

    // Comments / Notes
    if (secret.comments) {
      if (el.commentsFieldWrapper) el.commentsFieldWrapper.classList.remove('hidden');
      if (el.detailComments) el.detailComments.textContent = secret.comments;
    } else {
      if (el.commentsFieldWrapper) el.commentsFieldWrapper.classList.add('hidden');
    }

    // Timestamps
    if (el.detailCreatedAt) {
      el.detailCreatedAt.textContent = formatTimestamp(secret.create_date);
    }
    if (secret.update_date && el.detailUpdatedAt && el.detailUpdatedRow) {
      el.detailUpdatedAt.textContent = formatTimestamp(secret.update_date);
      el.detailUpdatedRow.classList.remove('hidden');
    } else if (el.detailUpdatedRow) {
      el.detailUpdatedRow.classList.add('hidden');
    }

    // Actions
    if (el.btnEditSecret) el.btnEditSecret.onclick = () => openEditModal(secret);
    if (el.btnDeleteSecret) el.btnDeleteSecret.onclick = () => openDeleteConfirmModal(secret.name);
  }

  function formatTimestamp(ts) {
    if (!ts) return '-';
    try {
      const d = new Date(ts);
      return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return String(ts);
    }
  }

  // --- TOTP Realtime Arc Countdown ---
  function startTotpCountdown(secretName) {
    stopTotpTimer();
    const circumference = 2 * Math.PI * 18; // r=18 -> 113.1

    async function tick() {
      try {
        const res = await apiFetch(`/totp/${encodeURIComponent(secretName)}`);
        const code = res.code || '------';
        const remaining = res.remaining_seconds !== undefined ? res.remaining_seconds : 30;

        if (el.totpCodeText) {
          // Format 6 digits with a space: 123 456
          el.totpCodeText.textContent = code.length === 6 ? `${code.slice(0, 3)} ${code.slice(3)}` : code;
          el.totpCodeText.dataset.rawCode = code;
        }

        if (el.totpSecondsLabel) {
          el.totpSecondsLabel.textContent = remaining;
        }

        if (el.totpArcIndicator) {
          // Progress: 0 (empty) to circumference (full)
          const offset = circumference - (remaining / 30) * circumference;
          el.totpArcIndicator.style.strokeDashoffset = offset;

          el.totpArcIndicator.classList.remove('warning', 'danger');
          if (remaining <= 5) {
            el.totpArcIndicator.classList.add('danger');
          } else if (remaining <= 10) {
            el.totpArcIndicator.classList.add('warning');
          }
        }
      } catch (e) {
        // Stop timer if request fails
      }
    }

    // Immediate first tick then interval
    tick();
    state.totpInterval = setInterval(tick, 1000);
  }

  function stopTotpTimer() {
    if (state.totpInterval) {
      clearInterval(state.totpInterval);
      state.totpInterval = null;
    }
  }

  // --- Click-to-Copy with Feedback & Memory Clearing ---
  async function copyToClipboard(text, buttonEl, successLabel = 'Copied!') {
    if (!text) return;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }

      // Visual feedback on button
      if (buttonEl) {
        const originalHtml = buttonEl.innerHTML;
        buttonEl.classList.add('copied');
        buttonEl.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg><span>${successLabel}</span>`;
        setTimeout(() => {
          buttonEl.classList.remove('copied');
          buttonEl.innerHTML = originalHtml;
        }, 2000);
      }

      showToast('Copied to clipboard! Wipes in 30s.', 'success', 2500);

      // Trigger automatic 30s clipboard purge if feasible
      setTimeout(() => {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          // Only clear if active tab
          navigator.clipboard.writeText('').catch(() => {});
        }
      }, 30000);

    } catch (err) {
      showToast('Clipboard copy failed.', 'error');
    }
  }

  // --- Favorite Toggle ---
  async function toggleSecretFavorite(secret) {
    const isFav = !(secret.is_favorite || secret.favorite);
    try {
      await apiFetch(`/secrets/${encodeURIComponent(secret.name)}`, {
        method: 'PUT',
        body: JSON.stringify({ is_favorite: isFav })
      });
      secret.is_favorite = isFav;
      secret.favorite = isFav;
      if (el.btnDetailFav) el.btnDetailFav.classList.toggle('active', isFav);
      updateCategoryCounts();
      renderSecretsList();
      showToast(isFav ? 'Added to favorites.' : 'Removed from favorites.');
    } catch (e) {
      showToast('Failed to update favorite status.', 'error');
    }
  }

  // --- Password Generator ---
  function generateStrongPassword(length = 20) {
    const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{}|;:,.<>?';
    const randomValues = new Uint32Array(length);
    window.crypto.getRandomValues(randomValues);
    let result = '';
    for (let i = 0; i < length; i++) {
      result += charset[randomValues[i] % charset.length];
    }
    return result;
  }

  // --- Add / Edit Secret Modal ---
  function openAddModal() {
    el.modalTitle.textContent = 'New Credential';
    el.editorOriginalName.value = '';
    el.editorName.value = '';
    el.editorName.disabled = false;
    el.editorCategory.value = state.activeCategoryFilter !== 'all' ? state.activeCategoryFilter : 'login';
    el.editorUsername.value = '';
    el.editorPassword.value = '';
    el.editorUrl.value = '';
    el.editorTotp.value = '';
    el.editorTags.value = '';
    el.editorComments.value = '';
    el.editorIsFavorite.checked = state.activeFavoritesOnly;

    el.modalSecretEditor.classList.remove('hidden');
    setTimeout(() => el.editorName.focus(), 50);
  }

  function openEditModal(secret) {
    el.modalTitle.textContent = `Edit ${secret.name}`;
    el.editorOriginalName.value = secret.name;
    el.editorName.value = secret.name;
    el.editorCategory.value = (secret.category || 'login').toLowerCase();
    el.editorUsername.value = secret.username || '';
    el.editorPassword.value = secret.password || '';
    el.editorUrl.value = secret.url || '';
    el.editorTotp.value = secret.totp_secret || '';
    el.editorTags.value = Array.isArray(secret.tags) ? secret.tags.join(', ') : '';
    el.editorComments.value = secret.comments || '';
    el.editorIsFavorite.checked = !!(secret.is_favorite || secret.favorite);

    el.modalSecretEditor.classList.remove('hidden');
    setTimeout(() => el.editorPassword.focus(), 50);
  }

  function closeModal() {
    el.modalSecretEditor.classList.add('hidden');
  }

  async function handleSaveSecret(e) {
    e.preventDefault();
    const originalName = el.editorOriginalName.value;
    const name = el.editorName.value.trim();
    const username = el.editorUsername.value.trim();
    const password = el.editorPassword.value;
    const category = el.editorCategory.value;
    const url = el.editorUrl.value.trim();
    const totp_secret = el.editorTotp.value.trim();
    const comments = el.editorComments.value.trim();
    const is_favorite = el.editorIsFavorite.checked;

    const tags = el.editorTags.value
      .split(',')
      .map(t => t.trim())
      .filter(t => t.length > 0);

    const payload = {
      name,
      username,
      password,
      category,
      url,
      totp_secret: totp_secret || null,
      comments,
      is_favorite,
      tags
    };

    try {
      if (originalName) {
        // Update existing secret
        payload.new_name = name;
        await apiFetch(`/secrets/${encodeURIComponent(originalName)}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        });
        showToast(`Saved "${name}" successfully.`, 'success');
      } else {
        // Add new secret
        await apiFetch('/secrets', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        showToast(`Created "${name}" successfully.`, 'success');
      }

      closeModal();
      await loadSecrets();
      selectSecret(name);
    } catch (err) {
      showToast(err.message || 'Failed to save secret.', 'error');
    }
  }

  // --- Delete Modal ---
  let secretNameToDelete = '';

  function openDeleteConfirmModal(name) {
    secretNameToDelete = name;
    el.deleteSecretNameLabel.textContent = `"${name}"`;
    el.modalDeleteConfirm.classList.remove('hidden');
  }

  function closeDeleteModal() {
    secretNameToDelete = '';
    el.modalDeleteConfirm.classList.add('hidden');
  }

  async function handleConfirmDelete() {
    if (!secretNameToDelete) return;
    try {
      await apiFetch(`/secrets/${encodeURIComponent(secretNameToDelete)}`, {
        method: 'DELETE'
      });
      showToast(`Deleted "${secretNameToDelete}".`, 'info');
      closeDeleteModal();
      deselectSecret();
      await loadSecrets();
    } catch (err) {
      showToast('Failed to delete secret.', 'error');
    }
  }

  // --- Event Listeners Setup ---
  function setupEventListeners() {
    // 1. Enrollment
    if (el.enrollForm) {
      el.enrollForm.addEventListener('submit', handleEnrollSubmit);
    }
    if (el.btnCopyCommand) {
      el.btnCopyCommand.addEventListener('click', () => {
        if (el.enrollCliCommand) {
          copyToClipboard(el.enrollCliCommand.textContent, el.btnCopyCommand, 'Copied!');
        }
      });
    }
    if (el.btnCopyFingerprint) {
      el.btnCopyFingerprint.addEventListener('click', () => {
        const fp = el.enrollFpDisplay ? el.enrollFpDisplay.textContent.trim() : '';
        if (fp && fp !== '-') {
          copyToClipboard(fp, el.btnCopyFingerprint, 'Copied!');
          showToast('Fingerprint copied to clipboard!', 'info', 2000);
        }
      });
    }
    if (el.btnGotoUnlock) {
      el.btnGotoUnlock.addEventListener('click', () => {
        if (window.history.replaceState) {
          const cleanUrl = window.location.pathname.replace(/\/enroll\/?$/, '') || '/';
          window.history.replaceState({}, document.title, cleanUrl);
        }
        showUnlockView();
      });
    }
    if (el.btnReRegister) {
      el.btnReRegister.addEventListener('click', () => {
        showEnrollmentView();
      });
    }

    // 2. Unlock & Forget Device
    if (el.unlockForm) {
      el.unlockForm.addEventListener('submit', handleUnlockSubmit);
    }
    if (el.btnForgetDevice) {
      el.btnForgetDevice.addEventListener('click', forgetCurrentDevice);
    }

    // 3. Password visibility toggles
    document.querySelectorAll('.toggle-pw-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const targetId = btn.dataset.target;
        const input = document.getElementById(targetId);
        if (!input) return;
        const eyeIcon = btn.querySelector('.icon-eye');
        const eyeOffIcon = btn.querySelector('.icon-eye-off');

        if (input.type === 'password') {
          input.type = 'text';
          if (eyeIcon) eyeIcon.classList.add('hidden');
          if (eyeOffIcon) eyeOffIcon.classList.remove('hidden');
        } else {
          input.type = 'password';
          if (eyeIcon) eyeIcon.classList.remove('hidden');
          if (eyeOffIcon) eyeOffIcon.classList.add('hidden');
        }
      });
    });

    // Detail password reveal toggle
    if (el.btnToggleDetailPassword) {
      el.btnToggleDetailPassword.addEventListener('click', () => {
        const isRevealed = el.detailPassword.dataset.revealed === 'true';
        const eyeIcon = el.btnToggleDetailPassword.querySelector('.icon-eye');
        const eyeOffIcon = el.btnToggleDetailPassword.querySelector('.icon-eye-off');

        if (isRevealed) {
          el.detailPassword.textContent = '••••••••••••••••';
          el.detailPassword.dataset.revealed = 'false';
          if (eyeIcon) eyeIcon.classList.remove('hidden');
          if (eyeOffIcon) eyeOffIcon.classList.add('hidden');
        } else {
          el.detailPassword.textContent = el.detailPassword.dataset.realPassword || '';
          el.detailPassword.dataset.revealed = 'true';
          if (eyeIcon) eyeIcon.classList.add('hidden');
          if (eyeOffIcon) eyeOffIcon.classList.remove('hidden');
        }
      });
    }

    // Copy actions in Detail pane
    if (el.btnCopyUsername) {
      el.btnCopyUsername.addEventListener('click', () => {
        copyToClipboard(el.detailUsername.textContent, el.btnCopyUsername);
      });
    }
    if (el.btnCopyPassword) {
      el.btnCopyPassword.addEventListener('click', () => {
        copyToClipboard(el.detailPassword.dataset.realPassword, el.btnCopyPassword);
      });
    }
    if (el.btnCopyTotp) {
      el.btnCopyTotp.addEventListener('click', () => {
        copyToClipboard(el.totpCodeText.dataset.rawCode, el.btnCopyTotp);
      });
    }

    // Search input
    if (el.globalSearch) {
      el.globalSearch.addEventListener('input', (e) => {
        state.searchQuery = e.target.value.trim();
        if (el.btnClearSearch) {
          el.btnClearSearch.classList.toggle('hidden', state.searchQuery.length === 0);
        }
        renderSecretsList();
      });

      // Quick search shortcut (/)
      window.addEventListener('keydown', (e) => {
        if (e.key === '/' && document.activeElement !== el.globalSearch && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
          e.preventDefault();
          el.globalSearch.focus();
        } else if (e.key === 'Escape' && document.activeElement === el.globalSearch) {
          el.globalSearch.value = '';
          state.searchQuery = '';
          if (el.btnClearSearch) el.btnClearSearch.classList.add('hidden');
          renderSecretsList();
        }
      });
    }

    if (el.btnClearSearch) {
      el.btnClearSearch.addEventListener('click', () => {
        el.globalSearch.value = '';
        state.searchQuery = '';
        el.btnClearSearch.classList.add('hidden');
        renderSecretsList();
        el.globalSearch.focus();
      });
    }

    // Category and filter navigation
    el.navItems.forEach(item => {
      item.addEventListener('click', () => {
        el.navItems.forEach(n => n.classList.remove('active'));
        item.classList.add('active');

        const filterType = item.dataset.filterType;
        const filterVal = item.dataset.filterValue;

        if (filterType === 'favorites') {
          state.activeFavoritesOnly = true;
          state.activeCategoryFilter = 'all';
          if (el.currentViewHeading) el.currentViewHeading.textContent = 'Favorites';
        } else {
          state.activeFavoritesOnly = false;
          state.activeCategoryFilter = filterVal;
          if (el.currentViewHeading) {
            el.currentViewHeading.textContent = filterVal === 'all' ? 'All Items' : item.querySelector('span').textContent;
          }
        }

        renderSecretsList();
      });
    });

    // Sort order toggle
    if (el.btnToggleSort) {
      el.btnToggleSort.addEventListener('click', () => {
        state.sortAscending = !state.sortAscending;
        if (el.sortOrderLabel) {
          el.sortOrderLabel.textContent = state.sortAscending ? 'A-Z' : 'Z-A';
        }
        renderSecretsList();
      });
    }

    // Top action buttons
    if (el.btnAddSecretTop) el.btnAddSecretTop.addEventListener('click', openAddModal);
    if (el.btnEmptyAdd) el.btnEmptyAdd.addEventListener('click', openAddModal);
    if (el.btnLockVault) el.btnLockVault.addEventListener('click', handleLockVault);

    // Modal controls
    if (el.btnCloseModal) el.btnCloseModal.addEventListener('click', closeModal);
    if (el.btnCancelModal) el.btnCancelModal.addEventListener('click', closeModal);
    if (el.formSecretEditor) el.formSecretEditor.addEventListener('submit', handleSaveSecret);
    if (el.btnGeneratePassword) {
      el.btnGeneratePassword.addEventListener('click', () => {
        const strong = generateStrongPassword(20);
        el.editorPassword.value = strong;
        el.editorPassword.type = 'text';
        showToast('Generated 20-character secure password.', 'info', 2000);
      });
    }

    // Delete modal controls
    if (el.btnCloseDeleteModal) el.btnCloseDeleteModal.addEventListener('click', closeDeleteModal);
    if (el.btnCancelDelete) el.btnCancelDelete.addEventListener('click', closeDeleteModal);
    if (el.btnConfirmDelete) el.btnConfirmDelete.addEventListener('click', handleConfirmDelete);
  }

  // --- Application Bootstrap ---
  async function initApp() {
    initElementRefs();
    setupEventListeners();

    const isEnrollPath = window.location.pathname.includes('/enroll');
    const urlParams = new URLSearchParams(window.location.search);
    const hasSecretParam = urlParams.has('secret');

    // 1. If deviceToken already exists in localStorage, verify with /devices/status
    if (state.deviceToken) {
      try {
        const devStatus = await apiFetch('/devices/status');
        const isApproved = devStatus.status === 'APPROVED' || devStatus.approved === true;

        if (isApproved) {
          // If visiting /enroll or has secret param, do not show the registration form
          if (isEnrollPath || hasSecretParam) {
            showAlreadyApprovedView(state.deviceName);
            return;
          }

          // Otherwise normal flow: check session status
          const authStatus = await apiFetch('/auth/status');
          if (authStatus.unlocked && state.sessionToken) {
            showDashboardView();
          } else {
            showUnlockView();
          }
          return;
        }

        // If pending approval
        if (devStatus.status === 'PENDING') {
          showView(el.viewEnroll);
          renderWaitingApproval(state.deviceFingerprint, state.deviceId);
          return;
        }
      } catch (err) {
        // Fallback to enrollment form if status verification failed / revoked
      }
    }

    // 2. Unregistered or unapproved device: show enrollment form
    showEnrollmentView();
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
  } else {
    initApp();
  }

})();
