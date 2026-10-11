/**
 * HNC Zalo Bot — Quản lý bán hàng / kho qua Zalo, ghi thẳng vào HNC_Control_Center.
 *
 * Gắn vào spreadsheet HNC_Control_Center (Tiện ích mở rộng → Apps Script).
 * Cấu hình trong Script Properties (Cài đặt dự án → Thuộc tính tập lệnh):
 *   BOT_TOKEN         Mã bot Zalo (bot-api.zapps.me)
 *   WEBHOOK_KEY       Chuỗi bí mật tự đặt, gắn vào link webhook (?key=...)
 *   WEBAPP_URL        Link Web App sau khi Triển khai (kết thúc bằng /exec)
 *   ALLOWED_CHAT_IDS  Danh sách chat_id được dùng bot, cách nhau bằng dấu phẩy
 *   DRY_RUN           "true" = chỉ trả lời sẽ ghi gì, KHÔNG ghi Sheet (dùng khi chạy thử)
 *
 * Mọi đọc/ghi Sheet đều theo TÊN CỘT ở hàng 1, không theo chỉ số cột.
 */

const ZALO_API = 'https://bot-api.zapps.me/bot';
const TZ = 'Asia/Ho_Chi_Minh';

// Bí danh kho trong tin nhắn → mã kho của HNC_Control_Center
const KHO_ALIASES = { 'YEN': 'Y3C', 'Y3C': 'Y3C', '3C': 'Y3C', 'TBH': '15E', '15E': '15E' };
const KHO_SHEETS = { 'Y3C': 'KHOY3C', '15E': 'KHO15E' };

// Dòng NHAP từ Zalo: đánh dấu để HNC bỏ qua khi xuất web / tem / MISA; kho_sync để trống
// để tác vụ đồng bộ kho của HNC tự thêm SKU mới vào KHO15E / KHOY3C.
const NHAP_ZALO_MARK = 'Zalo_Update';
const NHAP_MARK_COLUMNS = ['web_stock', 'web_label', 'misa_stock'];

const ACTIONS = {
  CHECK: 'KIỂM TRA HÀNG',
  MOVE_LOC: 'CHUYỂN VỊ TRÍ',
  TRANSFER: 'CHUYỂN KHO',
  SELL: 'BÁN',
  OUT: 'XUẤT',
  IN: 'NHẬP',
};

// =====================================================================
// WEBHOOK
// =====================================================================

function doGet() {
  return ContentService.createTextOutput('HNC Zalo Bot OK');
}

function doPost(e) {
  try {
    const props = PropertiesService.getScriptProperties();
    const key = props.getProperty('WEBHOOK_KEY');
    if (!key || !e || !e.parameter || e.parameter.key !== key) return ok_();

    const body = JSON.parse((e.postData && e.postData.contents) || '{}');
    const msg = body.message;
    if (!msg || !msg.text || !msg.chat) return ok_();

    // Zalo có thể gửi lại cùng một tin → mỗi message_id chỉ xử lý 1 lần
    const cache = CacheService.getScriptCache();
    const dedupeKey = 'msg_' + (msg.message_id || (msg.chat.id + '_' + msg.date));
    if (cache.get(dedupeKey)) return ok_();
    cache.put(dedupeKey, '1', 21600);

    const chatId = String(msg.chat.id);
    const allowed = (props.getProperty('ALLOWED_CHAT_IDS') || '')
      .split(',').map(s => s.trim()).filter(Boolean);
    if (allowed.indexOf(chatId) === -1) {
      sendMessage_(chatId, '⛔ Bạn chưa được cấp quyền dùng bot.\nchat_id của bạn: ' + chatId +
        '\nGửi chat_id này cho anh Kha để được cấp quyền.');
      return ok_();
    }

    const dryRun = String(props.getProperty('DRY_RUN') || '').toLowerCase() === 'true';
    const reply = handleText_(msg.text, dryRun);
    sendMessage_(chatId, reply);
  } catch (err) {
    console.error(err && err.stack ? err.stack : err);
  }
  return ok_();
}

function ok_() {
  return ContentService.createTextOutput('ok');
}

/** Xử lý 1 tin nhắn, trả về câu trả lời. Dùng chung cho webhook và hàm chạy thử. */
function handleText_(text, dryRun) {
  const p = parseMessage_(text);
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    let reply;
    switch (p.action) {
      case ACTIONS.CHECK: reply = doCheck_(p); break;
      case ACTIONS.MOVE_LOC: reply = doMoveLocation_(p, dryRun); break;
      case ACTIONS.TRANSFER: reply = doTransfer_(p, dryRun); break;
      default: reply = doMovement_(p, p.action, p.kho, dryRun); break;
    }
    return (dryRun && p.action !== ACTIONS.CHECK ? '🧪 CHẠY THỬ — chưa ghi Sheet\n' : '') + reply;
  } finally {
    lock.releaseLock();
  }
}

// =====================================================================
// PHÂN TÍCH TIN NHẮN (không dùng AI)
// =====================================================================

function parseMessage_(textRaw) {
  const text = String(textRaw || '').trim();
  const lower = text.toLowerCase();

  let action = ACTIONS.CHECK;
  if (/chuyển\s*vị\s*trí/.test(lower)) action = ACTIONS.MOVE_LOC;
  else if (/chuyển\s*kho/.test(lower)) action = ACTIONS.TRANSFER;
  else if (/bán/.test(lower)) action = ACTIONS.SELL;
  else if (/xuất/.test(lower)) action = ACTIONS.OUT;
  else if (/nhập/.test(lower)) action = ACTIONS.IN;

  // Kho
  let kho = '', khoFrom = '', khoTo = '';
  const khoPattern = '(YEN|Y3C|3C|TBH|15E)';
  const mFrom = text.match(new RegExp('từ\\s+(?:kho\\s+)?' + khoPattern + '(?![A-Za-z0-9])', 'i'));
  const mTo = text.match(new RegExp('(?:đến|tới|sang|qua)\\s+(?:kho\\s+)?' + khoPattern + '(?![A-Za-z0-9])', 'i'));
  if (mFrom) khoFrom = KHO_ALIASES[mFrom[1].toUpperCase()];
  if (mTo) khoTo = KHO_ALIASES[mTo[1].toUpperCase()];
  const mKho = text.match(new RegExp('(?:^|[^A-Za-z0-9])' + khoPattern + '(?![A-Za-z0-9])', 'i'));
  if (mKho) kho = KHO_ALIASES[mKho[1].toUpperCase()];

  // Vị trí (chỉ cho chuyển vị trí): "... đến/tới [vị trí] K12"
  let location = '';
  if (action === ACTIONS.MOVE_LOC) {
    const mLoc = text.match(/(?:đến|tới|về|sang)(?:\s+vị\s*trí)?\s+([A-Za-z0-9\-]{1,10})(?![A-Za-z0-9])/i);
    if (mLoc && !KHO_ALIASES[mLoc[1].toUpperCase()]) location = mLoc[1].toUpperCase();
  }

  // Màu: "màu Đen"
  let color = '';
  const mColor = text.match(/màu\s+([^\s,.;]+)/i);
  if (mColor) color = mColor[1].charAt(0).toUpperCase() + mColor[1].slice(1).toLowerCase();

  // Tách token (giữ "/" để đọc size/số lượng)
  const tokens = text.split(/[\s,;]+/).filter(Boolean);

  // Giá: 450000, 450.000, 450.000đ, 450k
  let price = '', priceToken = -1;
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i].toLowerCase();
    const m = t.match(/^(\d{1,3}(?:\.\d{3})+|\d+000)(?:đ|d|vnd|vnđ)?$/);
    if (m) { price = m[1].replace(/\./g, ''); priceToken = i; break; }
    const mk = t.match(/^(\d{2,4})k$/);
    if (mk) { price = String(Number(mk[1]) * 1000); priceToken = i; break; }
  }

  // Mã SP: chữ + số, có ít nhất 1 chữ số, kết thúc bằng 1 chữ cái (mã màu). Bỏ qua giá, kho và vị trí.
  let code = '';
  for (let i = 0; i < tokens.length; i++) {
    if (i === priceToken) continue;
    const tk = tokens[i].replace(/[^A-Za-z0-9]/g, '');
    if (tk.length < 3) continue;
    if (KHO_ALIASES[tk.toUpperCase()]) continue;
    if (location && tk.toUpperCase() === location) continue;
    if (/^[A-Za-z0-9]*\d[A-Za-z0-9]*[A-Za-z]$/.test(tk)) { code = tk.toUpperCase(); break; }
  }

  // Size/số lượng: "40/2" hoặc chỉ "40" (= 1 đôi)
  const sizes = [];
  for (const t of tokens) {
    const mp = t.match(/^(3[0-9]|4[0-9])\/(\d{1,3})$/);
    if (mp) { addSize_(sizes, mp[1], Number(mp[2])); continue; }
    const ms = t.match(/^(3[0-9]|4[0-9])$/);
    if (ms) addSize_(sizes, ms[1], 1);
  }

  return { action, kho, khoFrom, khoTo, location, color, price, code, sizes, text };
}

function addSize_(sizes, size, qty) {
  const found = sizes.find(s => s.size === size);
  if (found) found.qty += qty; else sizes.push({ size, qty });
}

// =====================================================================
// TÁC VỤ
// =====================================================================

function doCheck_(p) {
  if (!p.code) return '❓ Không thấy mã sản phẩm. Ví dụ: "AP0408D 40" hoặc "AP0408D".';
  const lines = [];
  let foundAny = false;
  for (const kho of ['Y3C', '15E']) {
    const rows = findKhoRows_(kho, p.code, p.sizes.map(s => s.size));
    if (!rows.length) continue;
    foundAny = true;
    const parts = rows.map(r => {
      const qty = Number(r.current_quantity) || 0;
      const loc = r.product_location ? ' (' + r.product_location + ')' : '';
      return (r.item_size ? 'size ' + r.item_size : 'không size') + ': ' +
        (qty > 0 ? qty + ' đôi' + loc : 'hết');
    });
    lines.push('📦 Kho ' + kho + ' — ' + (rows[0].product_color || '') + '\n  ' + parts.join('\n  '));
  }
  if (!foundAny) {
    return '❌ Không có ' + p.code + (p.sizes.length ? ' size ' + p.sizes.map(s => s.size).join(',') : '') +
      ' trong KHOY3C / KHO15E.';
  }
  return '🔎 ' + p.code + '\n' + lines.join('\n');
}

/** Bán / Nhập / Xuất tại 1 kho. */
function doMovement_(p, action, kho, dryRun) {
  if (!p.code) return '❓ Không thấy mã sản phẩm. Ví dụ: "bán AP0408D 40 YEN 450k".';
  if (!kho) return '❓ Chưa ghi kho (YEN/3C hoặc TBH/15E). Ví dụ: "' + action.toLowerCase() + ' ' + p.code + ' 40 YEN".';

  const sizes = p.sizes.length ? p.sizes : [{ size: '', qty: 1 }];
  const color = p.color || lookupColor_(p.code);
  const warnings = [];
  const written = [];

  for (const s of sizes) {
    if (action !== ACTIONS.IN && !findKhoRows_(kho, p.code, s.size ? [s.size] : []).length) {
      warnings.push('⚠️ SKU ' + kho + p.code + s.size + ' chưa có trong ' + KHO_SHEETS[kho] + ' → tồn kho sẽ không trừ.');
    }
    if (!dryRun) {
      if (action === ACTIONS.SELL) appendBan_(p.code, color, p.price, s.size, s.qty, kho);
      else if (action === ACTIONS.OUT) appendXuat_(p.code, color, s.size, s.qty, kho);
      else appendNhap_(p.code, color, s.size, s.qty, kho);
    }
    written.push((s.size ? 'size ' + s.size : 'không size') + ' × ' + s.qty);
  }

  const tab = action === ACTIONS.SELL ? 'BAN' : action === ACTIONS.OUT ? 'XUAT' : 'NHAP';
  return '✅ ' + action + ' ' + p.code + (color ? ' màu ' + color : '') + ' kho ' + kho +
    (action === ACTIONS.SELL && p.price ? ' giá ' + Number(p.price).toLocaleString('vi-VN') + 'đ' : '') +
    '\n  ' + written.join('\n  ') + '\n→ tab ' + tab +
    (warnings.length ? '\n' + warnings.join('\n') : '');
}

/** Chuyển kho = XUẤT ở kho nguồn + NHẬP ở kho đích. */
function doTransfer_(p, dryRun) {
  if (!p.khoFrom || !p.khoTo) {
    return '❓ Chuyển kho cần ghi rõ "từ kho ... đến kho ...". Ví dụ: "chuyển kho AP0408D 40 từ kho YEN đến kho TBH".';
  }
  if (p.khoFrom === p.khoTo) return '❓ Kho nguồn và kho đích giống nhau (' + p.khoFrom + ').';
  const out = doMovement_(p, ACTIONS.OUT, p.khoFrom, dryRun);
  if (out.indexOf('✅') !== 0) return out;
  const inn = doMovement_(p, ACTIONS.IN, p.khoTo, dryRun);
  return '🔁 CHUYỂN KHO ' + p.khoFrom + ' → ' + p.khoTo + '\n' + out + '\n' + inn;
}

/** Sửa product_location trong tab KHO. Không ghi size = đổi vị trí tất cả size của mã đó. */
function doMoveLocation_(p, dryRun) {
  if (!p.code) return '❓ Không thấy mã sản phẩm. Ví dụ: "chuyển vị trí AP0408D 40 YEN đến K12".';
  if (!p.kho) return '❓ Chưa ghi kho (YEN/3C hoặc TBH/15E).';
  if (!p.location) return '❓ Chưa ghi vị trí mới. Ví dụ: "... đến K12".';

  const sheet = getSheet_(KHO_SHEETS[p.kho]);
  const data = sheet.getDataRange().getValues();
  const col = headerMap_(data[0]);
  requireColumns_(KHO_SHEETS[p.kho], col, ['product_code', 'item_size', 'product_location']);

  const wantSizes = p.sizes.map(s => s.size);
  const changed = [];
  for (let r = 1; r < data.length; r++) {
    if (String(data[r][col.product_code]).trim().toUpperCase() !== p.code) continue;
    const size = normSize_(data[r][col.item_size]);
    if (wantSizes.length && wantSizes.indexOf(size) === -1) continue;
    if (!dryRun) sheet.getRange(r + 1, col.product_location + 1).setValue(p.location);
    changed.push(size || 'không size');
  }
  if (!changed.length) return '❌ Không tìm thấy ' + p.code + ' trong ' + KHO_SHEETS[p.kho] + '.';
  return '✅ Đã chuyển ' + p.code + ' (' + changed.join(',') + ') kho ' + p.kho + ' về vị trí ' + p.location;
}

// =====================================================================
// GHI SHEET
// =====================================================================

function appendBan_(code, color, price, size, qty, kho) {
  // FSKU của BAN tự tính bằng ARRAYFORMULA → không ghi cột FSKU
  appendByHeader_('BAN', {
    'Ngày': today_(), 'product_code': code, 'product_color': color,
    'Giá': price ? Number(price) : '', 'item_size': sizeValue_(size), 'item_quantity': qty, 'KHO': kho,
  });
}

function appendXuat_(code, color, size, qty, kho) {
  // FSKU của XUAT tự tính bằng ARRAYFORMULA → không ghi cột FSKU
  appendByHeader_('XUAT', {
    'Ngày': today_(), 'product_code': code, 'product_color': color,
    'KHO': kho, 'item_size': sizeValue_(size), 'item_quantity': qty,
  });
}

function appendNhap_(code, color, size, qty, kho) {
  const values = {
    'Ngày chứng từ (*)': today_(), 'product_code': code, 'product_color': color,
    'KHO': kho, 'item_size': sizeValue_(size), 'Số lượng (*)': qty,
  };
  NHAP_MARK_COLUMNS.forEach(c => { values[c] = NHAP_ZALO_MARK; });
  // FSKU của NHAP là công thức từng dòng: =CONCATENATE(KHO; product_code; item_size)
  appendByHeader_('NHAP', values, (row, col) => {
    const a1 = c => columnLetter_(col[c] + 1) + row;
    return { 'FSKU': '=CONCATENATE(' + a1('KHO') + '; ' + a1('product_code') + '; ' + a1('item_size') + ')' };
  });
}

/**
 * Ghi 1 dòng mới ngay sau dòng cuối có product_code, theo tên cột hàng 1.
 * Chỉ ghi vào các cột được truyền vào (không đè cột công thức khác). Tự thêm dòng nếu hết lưới.
 */
function appendByHeader_(sheetName, values, formulaBuilder) {
  const sheet = getSheet_(sheetName);
  const header = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const col = headerMap_(header);
  requireColumns_(sheetName, col, Object.keys(values).concat(['product_code']));

  const codes = sheet.getRange(1, col.product_code + 1, sheet.getMaxRows(), 1).getValues();
  let last = codes.length;
  while (last > 1 && String(codes[last - 1][0]).trim() === '') last--;
  const row = last + 1;
  if (row > sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(), 100);

  const all = Object.assign({}, values, formulaBuilder ? formulaBuilder(row, col) : {});
  if (formulaBuilder) requireColumns_(sheetName, col, Object.keys(all));
  Object.keys(all).forEach(name => {
    const cell = sheet.getRange(row, col[name] + 1);
    const v = all[name];
    if (typeof v === 'string' && v.charAt(0) === '=') cell.setFormula(v);
    else cell.setValue(v);
  });
}

// =====================================================================
// ĐỌC SHEET
// =====================================================================

/** Các dòng trong tab KHO của 1 kho khớp mã (và size nếu có), dạng object theo tên cột. */
function findKhoRows_(kho, code, sizes) {
  const sheetName = KHO_SHEETS[kho];
  const data = getSheet_(sheetName).getDataRange().getValues();
  const col = headerMap_(data[0]);
  requireColumns_(sheetName, col, ['product_code', 'product_color', 'item_size', 'current_quantity', 'product_location']);
  const out = [];
  for (let r = 1; r < data.length; r++) {
    if (String(data[r][col.product_code]).trim().toUpperCase() !== code) continue;
    const size = normSize_(data[r][col.item_size]);
    if (sizes.length && sizes.indexOf(size) === -1) continue;
    out.push({
      item_size: size,
      product_color: data[r][col.product_color],
      current_quantity: data[r][col.current_quantity],
      product_location: data[r][col.product_location],
    });
  }
  return out;
}

function lookupColor_(code) {
  for (const kho of ['Y3C', '15E']) {
    const rows = findKhoRows_(kho, code, []);
    if (rows.length && rows[0].product_color) return rows[0].product_color;
  }
  return '';
}

// =====================================================================
// TIỆN ÍCH
// =====================================================================

function getSheet_(name) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(name);
  if (!sheet) throw new Error('Không tìm thấy tab ' + name);
  return sheet;
}

function headerMap_(header) {
  const map = {};
  header.forEach((h, i) => {
    const k = String(h).trim();
    if (k && map[k] === undefined) map[k] = i;
  });
  return map;
}

function requireColumns_(sheetName, col, names) {
  const missing = names.filter(n => col[n] === undefined);
  if (missing.length) throw new Error('Tab ' + sheetName + ' thiếu cột: ' + missing.join(', '));
}

function normSize_(v) {
  const s = String(v === null || v === undefined ? '' : v).trim();
  return s.endsWith('.0') ? s.slice(0, -2) : s;
}

function sizeValue_(size) {
  return size && /^\d+$/.test(size) ? Number(size) : (size || '');
}

function today_() {
  const parts = Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd').split('-').map(Number);
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

function columnLetter_(n) {
  let s = '';
  while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); }
  return s;
}

function sendMessage_(chatId, text) {
  const token = PropertiesService.getScriptProperties().getProperty('BOT_TOKEN');
  if (!token) throw new Error('Thiếu BOT_TOKEN trong Script Properties');
  const res = UrlFetchApp.fetch(ZALO_API + token + '/sendMessage', {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({ chat_id: chatId, text: String(text).slice(0, 2000) }),
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) console.error('sendMessage lỗi ' + res.getResponseCode() + ': ' + res.getContentText());
}

// =====================================================================
// HÀM CHẠY TAY TRONG TRÌNH SOẠN THẢO APPS SCRIPT
// =====================================================================

/** Chạy thử phân tích + trả lời mà KHÔNG ghi Sheet (luôn dry-run). Xem kết quả ở Nhật ký thực thi. */
function testMessages() {
  [
    'AP0408D 40',
    'AP0408D',
    'bán AP0408D 40 YEN 450k',
    'nhập AP0408D 38/2 39 TBH',
    'xuất AP0408D 41 15E',
    'chuyển kho AP0408D 40 từ kho YEN đến kho TBH',
    'chuyển vị trí AP0408D YEN đến K12',
    'bán 450000 AP0408D 40 YEN',
  ].forEach(t => {
    console.log('▶ ' + t + '\n' + JSON.stringify(parseMessage_(t)) + '\n' + handleText_(t, true));
  });
}

/** Trỏ bot Zalo về Web App này (chạy 1 lần sau khi Triển khai). */
function setupWebhook() {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('BOT_TOKEN');
  const url = props.getProperty('WEBAPP_URL');
  const key = props.getProperty('WEBHOOK_KEY');
  if (!token || !url || !key) throw new Error('Cần đủ BOT_TOKEN, WEBAPP_URL, WEBHOOK_KEY trong Script Properties');
  if (!/^[A-Za-z0-9_-]{8,256}$/.test(key)) {
    throw new Error('WEBHOOK_KEY phải dài 8-256 ký tự, chỉ gồm chữ không dấu, số, _ và -');
  }
  const res = UrlFetchApp.fetch(ZALO_API + token + '/setWebhook', {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({ url: url + '?key=' + encodeURIComponent(key), secret_token: key }),
    muteHttpExceptions: true,
  });
  console.log(res.getResponseCode() + ' ' + res.getContentText());
}

/** Xem bot đang trỏ webhook về đâu. */
function checkWebhook() {
  const token = PropertiesService.getScriptProperties().getProperty('BOT_TOKEN');
  const res = UrlFetchApp.fetch(ZALO_API + token + '/getWebhookInfo', { muteHttpExceptions: true });
  console.log(res.getResponseCode() + ' ' + res.getContentText());
}
