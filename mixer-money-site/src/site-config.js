(function (global) {
  'use strict';

  var STORAGE_KEY = 'mm5_mixer_site_admin_config_v1';
  var API_CONFIG_ENDPOINT = '/api/site-config';
  var API_RESET_ENDPOINT = '/api/site-config/reset';
  var API_ADMIN_LOGIN_ENDPOINT = '/api/admin/login';
  var API_ADMIN_LOGOUT_ENDPOINT = '/api/admin/logout';
  var API_ADMIN_ME_ENDPOINT = '/api/admin/me';

  var DEFAULT_CONFIG = {
    feePercent: 4.5,
    feeFixedBtc: 0.0007,
    depositAddress: 'bc1qga6mx70jx0uvfuk39eqpyyfwh9fsxzme75ckt7',
    qrImageSrc: './assets/payment_qr.png',
    telegramBotUrl: 'https://tele.click/mm5btc_bot',
    telegramChannelUrl: 'https://t.me/kitchen_crypto',
    onionDomain: 'mixermo4pgkgep3k3qr4fz7dhijavxnh6lwgu7gf5qeltpy4unjed2yd.onion'
  };

  var configCache = null;

  var STRING_KEYS = ['depositAddress', 'qrImageSrc', 'telegramBotUrl', 'telegramChannelUrl', 'onionDomain'];

  function cloneDefault() {
    return {
      feePercent: DEFAULT_CONFIG.feePercent,
      feeFixedBtc: DEFAULT_CONFIG.feeFixedBtc,
      depositAddress: DEFAULT_CONFIG.depositAddress,
      qrImageSrc: DEFAULT_CONFIG.qrImageSrc,
      telegramBotUrl: DEFAULT_CONFIG.telegramBotUrl,
      telegramChannelUrl: DEFAULT_CONFIG.telegramChannelUrl,
      onionDomain: DEFAULT_CONFIG.onionDomain
    };
  }

  function clone(obj) {
    return {
      feePercent: obj.feePercent,
      feeFixedBtc: obj.feeFixedBtc,
      depositAddress: obj.depositAddress,
      qrImageSrc: obj.qrImageSrc,
      telegramBotUrl: obj.telegramBotUrl,
      telegramChannelUrl: obj.telegramChannelUrl,
      onionDomain: obj.onionDomain
    };
  }

  function toFiniteNumber(value, fallback) {
    var n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function sanitizeConfig(raw) {
    var cfg = raw && typeof raw === 'object' ? raw : {};
    var next = cloneDefault();

    next.feePercent = Math.max(0, toFiniteNumber(cfg.feePercent, next.feePercent));
    next.feeFixedBtc = Math.max(0, toFiniteNumber(cfg.feeFixedBtc, next.feeFixedBtc));

    STRING_KEYS.forEach(function (key) {
      if (typeof cfg[key] === 'string' && cfg[key].trim()) {
        next[key] = cfg[key].trim();
      }
    });

    return next;
  }

  function safeReadStorage() {
    try {
      return global.localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      return null;
    }
  }

  function safeWriteStorage(value) {
    try {
      global.localStorage.setItem(STORAGE_KEY, value);
    } catch (error) {
      // ignore localStorage failures
    }
  }

  function safeRemoveStorage() {
    try {
      global.localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      // ignore
    }
  }

  function updateCache(next) {
    configCache = sanitizeConfig(next);
    safeWriteStorage(JSON.stringify(configCache));
    return clone(configCache);
  }

  function loadConfig() {
    if (configCache) {
      return clone(configCache);
    }

    var raw = safeReadStorage();
    if (!raw) {
      configCache = cloneDefault();
      return clone(configCache);
    }

    try {
      configCache = sanitizeConfig(JSON.parse(raw));
    } catch (error) {
      configCache = cloneDefault();
    }

    return clone(configCache);
  }

  function saveConfig(nextPartial) {
    var current = loadConfig();
    var merged = Object.assign({}, current, nextPartial || {});
    return updateCache(merged);
  }

  function resetConfig() {
    safeRemoveStorage();
    configCache = cloneDefault();
    return clone(configCache);
  }

  function hasRemoteApi() {
    return typeof global.fetch === 'function';
  }

  async function requestJson(url, init) {
    var res = await fetch(url, Object.assign({ cache: 'no-store', credentials: 'same-origin' }, init || {}));
    if (!res.ok) {
      var detail = 'Request failed: ' + res.status + ' ' + res.statusText;
      try {
        var body = await res.json();
        if (body && typeof body.detail === 'string' && body.detail) {
          detail = body.detail;
        }
      } catch (error) {
        // ignore json parse errors
      }
      throw new Error(detail);
    }
    return res.json();
  }

  async function loadConfigRemote() {
    if (!hasRemoteApi()) {
      throw new Error('fetch is not available');
    }
    var data = await requestJson(API_CONFIG_ENDPOINT);
    return updateCache(data);
  }

  async function saveConfigRemote(nextPartial) {
    if (!hasRemoteApi()) {
      throw new Error('fetch is not available');
    }
    var payload = Object.assign({}, nextPartial || {});
    var data = await requestJson(API_CONFIG_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return updateCache(data);
  }

  async function resetConfigRemote() {
    if (!hasRemoteApi()) {
      throw new Error('fetch is not available');
    }
    var data = await requestJson(API_RESET_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    });
    return updateCache(data);
  }

  async function adminLogin(username, password) {
    return requestJson(API_ADMIN_LOGIN_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: String(username || ''),
        password: String(password || '')
      })
    });
  }

  async function adminLogout() {
    return requestJson(API_ADMIN_LOGOUT_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    });
  }

  async function adminMe() {
    return requestJson(API_ADMIN_ME_ENDPOINT);
  }

  function trimZeros(str) {
    return str.replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
  }

  function formatNumberDot(value, maxDigits, minDigits) {
    var digits = Number.isFinite(maxDigits) ? maxDigits : 8;
    var min = Number.isFinite(minDigits) ? minDigits : 0;
    var fixed = toFiniteNumber(value, 0).toFixed(digits);
    var trimmed = trimZeros(fixed);

    if (min > 0) {
      var parts = trimmed.split('.');
      var frac = parts[1] || '';
      while (frac.length < min) {
        frac += '0';
      }
      trimmed = frac.length ? parts[0] + '.' + frac : parts[0];
    }

    return trimmed;
  }

  function dotToComma(text) {
    return String(text).replace(/\./g, ',');
  }

  function commissionTextDot(cfg) {
    var percent = formatNumberDot(cfg.feePercent, 4, 0);
    var fixed = formatNumberDot(cfg.feeFixedBtc, 8, 4);
    return percent + '% + ' + fixed + ' BTC';
  }

  function commissionText(cfg) {
    return dotToComma(commissionTextDot(cfg));
  }

  global.MixerSiteConfig = {
    STORAGE_KEY: STORAGE_KEY,
    API_CONFIG_ENDPOINT: API_CONFIG_ENDPOINT,
    API_RESET_ENDPOINT: API_RESET_ENDPOINT,
    API_ADMIN_LOGIN_ENDPOINT: API_ADMIN_LOGIN_ENDPOINT,
    API_ADMIN_LOGOUT_ENDPOINT: API_ADMIN_LOGOUT_ENDPOINT,
    API_ADMIN_ME_ENDPOINT: API_ADMIN_ME_ENDPOINT,
    DEFAULT_CONFIG: cloneDefault(),
    loadConfig: loadConfig,
    saveConfig: saveConfig,
    resetConfig: resetConfig,
    loadConfigRemote: loadConfigRemote,
    saveConfigRemote: saveConfigRemote,
    resetConfigRemote: resetConfigRemote,
    adminLogin: adminLogin,
    adminLogout: adminLogout,
    adminMe: adminMe,
    commissionText: commissionText,
    commissionTextDot: commissionTextDot,
    formatNumberDot: formatNumberDot,
    dotToComma: dotToComma,
    hasRemoteApi: hasRemoteApi
  };
})(window);
