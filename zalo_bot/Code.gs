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
 * Mọi đọc/ghi Sheet đều theo TÊN CỘT (hàng 1, hoặc hàng 2 với tab SANPHAM), không theo chỉ số cột.
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

const UNDO_SECONDS = 600; // Cho huỷ thao tác gần nhất trong 10 phút

const ACTIONS = {
  CHECK: 'KIỂM TRA HÀNG',
  MOVE_LOC: 'CHUYỂN VỊ TRÍ',
  TRANSFER: 'CHUYỂN KHO',
  SELL: 'BÁN',
  OUT: 'XUẤT',
  IN: 'NHẬP',
  UNDO: 'HUỶ',
  REPORT: 'BÁO CÁO',
  HELP: 'HƯỚNG DẪN',
};

const HELP_TEXT = [
  '📖 HƯỚNG DẪN BOT KHO HNC',
  '🔎 Kiểm hàng: TH2040D 40  |  TH2040 (mọi màu)',
  '🛒 Bán: ban TH2040D 40 YEN 800k',
  '📥 Nhập: nhap TH2040D 38/2 39 TBH',
  '📤 Xuất: xuat TH2040D 41 15E',
  '🔁 Chuyển kho: chuyen kho TH2040D 40 tu YEN den TBH',
  '📍 Chuyển vị trí: chuyen vi tri TH2040D YEN den K12',
  '↩️ Huỷ thao tác vừa rồi (10 phút): huy',
  '📊 Báo cáo bán: bc  |  bc hom qua  |  bc 10/10',
  '— Kho: YEN/3C = Y3C, TBH/15E = 15E',
  '— Size: 40 | 40/2 | 40x2 | 40.2 | 2 đôi 40 | 38-43',
  '— Giá: 800k | 800000 | 800.000đ | 1tr2',
  '— Gõ không dấu vẫn được.',
].join('\n');

// Bộ nhớ đệm đọc Sheet trong 1 lần xử lý tin nhắn
let MEMO = {};
// Ngữ cảnh tin nhắn đang xử lý (tên người nhắn → cột seller của BAN)
let CTX = {};

// Cửa "ghi bán" cho app bán hàng
const SALE_CHANNELS = ['cua_hang', 'web', 'shopee', 'tiktok'];
const SALE_MAX_LINES = 50;
const SALE_TICKET_DAYS = 30; // giữ mã phiếu đã ghi 30 ngày để chống ghi trùng

// =====================================================================
// WEBHOOK
// =====================================================================

function doGet() {
  return ContentService.createTextOutput('HNC Zalo Bot OK');
}

function doPost(e) {
  if (e && e.parameter && e.parameter.sale_key !== undefined) return handleSaleRequest_(e);
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
    const sellerName = msg.from && msg.from.display_name ? String(msg.from.display_name).slice(0, 50) : '';
    sendMessage_(chatId, handleText_(msg.text, dryRun, chatId, sellerName));
  } catch (err) {
    console.error(err && err.stack ? err.stack : err);
  }
  return ok_();
}

function ok_() {
  return ContentService.createTextOutput('ok');
}

/** Xử lý 1 tin nhắn, trả về câu trả lời. Dùng chung cho webhook và hàm chạy thử. */
function handleText_(text, dryRun, chatId, sellerName) {
  MEMO = {};
  CTX = { seller: sellerName || '' };
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    let res;
    let p;
    try {
      p = parseMessage_(text, knownCodes_());
      switch (p.action) {
        case ACTIONS.HELP: res = { text: HELP_TEXT }; break;
        case ACTIONS.CHECK: res = doCheck_(p); break;
        case ACTIONS.REPORT: res = doReport_(p); break;
        case ACTIONS.UNDO: res = doUndo_(chatId, dryRun); break;
        case ACTIONS.MOVE_LOC: res = doMoveLocation_(p, dryRun); break;
        case ACTIONS.TRANSFER: res = doTransfer_(p, dryRun); break;
        default: res = doMovement_(p, p.action, p.kho, dryRun); break;
      }
    } catch (err) {
      console.error(err && err.stack ? err.stack : err);
      return '⚠️ Lỗi: ' + (err && err.message ? err.message : err) + '\nKiểm tra lại Sheet xem đã ghi chưa. Báo anh Kha nếu lỗi lặp lại.';
    }
    if (res.ops && res.ops.length && !dryRun && chatId) {
      CacheService.getScriptCache().put('last_' + chatId,
        JSON.stringify({ label: res.label || '', ops: res.ops }), UNDO_SECONDS);
      res.text += '\n↩️ Nhắn "huy" trong 10 phút nếu ghi nhầm.';
    }
    const writes = [ACTIONS.SELL, ACTIONS.OUT, ACTIONS.IN, ACTIONS.TRANSFER, ACTIONS.MOVE_LOC, ACTIONS.UNDO];
    return (dryRun && writes.indexOf(p.action) !== -1 ? '🧪 CHẠY THỬ — chưa ghi Sheet\n' : '') + res.text;
  } finally {
    lock.releaseLock();
  }
}

// =====================================================================
// PHÂN TÍCH TIN NHẮN (không dùng AI)
// =====================================================================

/** Chữ thường, bỏ dấu tiếng Việt (đ → d). */
function norm_(s) {
  return String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd');
}

function isSize_(t) {
  return /^(3\d|4\d)$/.test(t);
}

// Từ thường gặp trong tin nhắn, không bao giờ là mã gốc
const STOP_WORDS = ['ban', 'nhap', 'xuat', 'chuyen', 'kho', 'tri', 'den', 'toi', 'sang', 'qua',
  'mau', 'doi', 'cai', 'huy', 'bao', 'cao', 'hom', 'nay', 'con', 'khong', 'size', 'gia', 'oi'];

/**
 * known = { codes: Set, bases: Set } lấy từ tab KHO (mã thật đang có). Có known thì ưu tiên khớp mã thật
 * (giải quyết mã không có số như CXED, mã ngắn như T1D, mã giống giá như 119K); không có thì đoán theo mẫu.
 */
function parseMessage_(textRaw, known) {
  const text = String(textRaw || '').normalize('NFC').trim();
  const lower = text.toLowerCase();
  const n = norm_(text);
  // Token gốc (có dấu) để nhận lệnh, tránh nhầm "bạn" với "bán"; token bỏ dấu để đọc mã/size/giá
  const rawToks = lower.split(/\s+/).filter(Boolean);
  const toks = n.split(/[\s;]+/).filter(Boolean);
  const hasRaw = words => rawToks.some(t => words.indexOf(t.replace(/[.,!?:]+$/, '')) !== -1);

  // ---- Lệnh ----
  let action = ACTIONS.CHECK;
  if ((toks.length <= 3 && (/^(hd|hdsd|help|\?|menu)$/.test(toks[0] || ''))) || /^huong\s*dan/.test(n)) action = ACTIONS.HELP;
  else if (/^(huỷ|hủy|huy|undo)$/.test((rawToks[0] || '').replace(/[.!]+$/, '')) || /^hoan\s*tac/.test(n)) action = ACTIONS.UNDO;
  else if (toks[0] === 'bc' || /^bao\s*cao/.test(n)) action = ACTIONS.REPORT;
  else if (/chuyen\s*vi\s*tri/.test(n)) action = ACTIONS.MOVE_LOC;
  else if (/chuyen\s*kho/.test(n)) action = ACTIONS.TRANSFER;
  else if (hasRaw(['bán', 'ban'])) action = ACTIONS.SELL;
  else if (hasRaw(['xuất', 'xuat'])) action = ACTIONS.OUT;
  else if (hasRaw(['nhập', 'nhap'])) action = ACTIONS.IN;

  const p = {
    action, kho: '', khoFrom: '', khoTo: '', location: '', color: '', price: '',
    code: '', baseCode: '', sizes: [], sizeErrors: [], reportDate: null, text,
  };
  if (action === ACTIONS.HELP || action === ACTIONS.UNDO) return p;
  if (action === ACTIONS.REPORT) { p.reportDate = parseReportDate_(n); return p; }

  const used = {}; // chỉ số token đã dùng cho kho / vị trí / giá / mã

  // ---- Kho ----
  const khoRe = '(yen|y3c|3c|tbh|15e)';
  const mFrom = n.match(new RegExp('(?:^|\\s)tu\\s+(?:kho\\s+)?' + khoRe + '(?![a-z0-9])'));
  const mTo = n.match(new RegExp('(?:^|\\s)(?:den|toi|sang|qua|ve)\\s+(?:kho\\s+)?' + khoRe + '(?![a-z0-9])'));
  if (mFrom) p.khoFrom = KHO_ALIASES[mFrom[1].toUpperCase()];
  if (mTo) p.khoTo = KHO_ALIASES[mTo[1].toUpperCase()];
  toks.forEach((t, i) => {
    const tk = t.replace(/[^a-z0-9]/g, '').toUpperCase();
    if (KHO_ALIASES[tk]) { used[i] = true; if (!p.kho) p.kho = KHO_ALIASES[tk]; }
  });

  // ---- Vị trí (chỉ cho chuyển vị trí): "... den/toi/ve/sang [vi tri] K12" ----
  if (action === ACTIONS.MOVE_LOC) {
    for (let i = 0; i < toks.length - 1; i++) {
      if (!/^(den|toi|ve|sang)$/.test(toks[i])) continue;
      let j = i + 1;
      if (toks[j] === 'vi' && toks[j + 1] === 'tri') j += 2;
      const tk = (toks[j] || '').replace(/[^a-z0-9\-]/g, '').toUpperCase();
      if (tk && !KHO_ALIASES[tk]) { p.location = tk; used[j] = true; break; }
    }
  }

  // ---- Màu: "màu Đen" / "mau den" (giữ chữ có dấu nếu có) ----
  const mColor = text.match(/(?:màu|mau)\s+([^\s,.;0-9]+)/i);
  if (mColor) p.color = mColor[1].charAt(0).toUpperCase() + mColor[1].slice(1).toLowerCase();

  // ---- Mã có trong tab KHO: ưu tiên mã không giống giá (119K vs "119k" là giá) ----
  if (known && known.codes) {
    const cands = [];
    toks.forEach((t, i) => {
      if (used[i]) return;
      const tk = t.replace(/[^a-z0-9]/g, '').toUpperCase();
      if (tk && known.codes.has(tk)) cands.push({ i, tk, priceLike: /^\d{1,4}K$/.test(tk) });
    });
    const pick = cands.find(c => !c.priceLike) || cands[0];
    if (pick) { p.code = pick.tk; used[pick.i] = true; }
  }

  // ---- Giá: 800000, 800.000đ, 800,000, 800k, 1tr2, 1.5tr ----
  for (let i = 0; i < toks.length; i++) {
    if (used[i]) continue;
    const t = toks[i].replace(/[!?]+$/, '');
    let m = t.match(/^(\d{1,3}(?:[.,]\d{3})+|\d+000)(?:d|vnd|dong)?$/);
    if (m) { p.price = m[1].replace(/[.,]/g, ''); used[i] = true; break; }
    m = t.match(/^(\d{1,4})k$/);
    if (m) { p.price = String(Number(m[1]) * 1000); used[i] = true; break; }
    m = t.match(/^(\d+)(?:[.,](\d+))?(?:tr|trieu)(\d)?$/);
    if (m) {
      const frac = m[2] || m[3] || '';
      p.price = String(Math.round(Number(m[1] + '.' + (frac || '0')) * 1000000));
      used[i] = true; break;
    }
  }

  // ---- Mã SP: chữ + số, kết thúc bằng 1 chữ cái (mã màu). Không có thì nhận mã gốc (không màu). ----
  // Không loại "d"/"k" đứng sau số dài: mã như 56307D (Đen) là mã thật; giá "800k"/"800000d" đã tách ở trên
  const unitWord = /^(\d+(doi|cai|sl|vnd|tr\d*|trieu)|\d{1,2}[dk])$/;
  const pairForm = /^\d{2}[x*:\/.\-]\d{1,2}$/;
  if (!p.code && known && known.bases) {
    for (let i = 0; i < toks.length; i++) {
      if (used[i]) continue;
      const tk = toks[i].replace(/[^a-z0-9]/g, '');
      if (tk.length >= 2 && STOP_WORDS.indexOf(tk) === -1 && known.bases.has(tk.toUpperCase())) {
        p.baseCode = tk.toUpperCase(); used[i] = true; break;
      }
    }
  }
  for (let i = 0; i < toks.length && !p.code && !p.baseCode; i++) {
    if (used[i]) continue;
    const tk = toks[i].replace(/[^a-z0-9]/g, '');
    if (tk.length < 3 || unitWord.test(tk) || pairForm.test(toks[i])) continue;
    if (/^[a-z0-9]*\d[a-z0-9]*[a-z]$/.test(tk)) { p.code = tk.toUpperCase(); used[i] = true; break; }
  }
  if (!p.code && !p.baseCode) {
    for (let i = 0; i < toks.length; i++) {
      if (used[i] || pairForm.test(toks[i])) continue;
      const tk = toks[i].replace(/[^a-z0-9]/g, '');
      if (tk.length >= 4 && /[a-z]/.test(tk) && /\d.*\d/.test(tk) && /\d$/.test(tk) && !/^sl\d/.test(tk)) {
        p.baseCode = tk.toUpperCase(); used[i] = true; break;
      }
    }
  }

  // ---- Size / số lượng ----
  parseSizes_(toks, used, p);
  return p;
}

/**
 * Đọc size/số lượng: 40 | 40/2 | 40.2 | 40x2 | 40*2 | 40:2 | 40-2 | 40 x2 | 40 2 đôi | 40 sl 2 |
 * 2 đôi 40 | 2doi 40 | 38,39,40 | 38-43 | 38 - 43. Size trùng thì cộng dồn.
 */
function parseSizes_(toks, used, p) {
  const list = [];
  toks.forEach((t, i) => {
    if (used[i]) return;
    t.split(',').forEach(part => { if (part) list.push(part.replace(/[!?]+$/, '')); });
  });
  const unit = /^(doi|cai|d)$/;
  let pendingQty = 0; // "2 đôi 40": số lượng đứng trước size

  for (let k = 0; k < list.length; k++) {
    const t = list[k];
    let m;

    // Số lượng đứng trước: "2 đôi" / "2doi"
    if (/^\d{1,2}$/.test(t) && !isSize_(t) && unit.test(list[k + 1] || '')) { pendingQty = Number(t); k++; continue; }
    if ((m = t.match(/^(\d{1,2})(doi|cai)$/))) { pendingQty = Number(m[1]); continue; }

    // Cặp trong 1 token: 40/2, 40.2, 40x2, 40*2, 40:2, 40-2, hoặc dải 38-43
    if ((m = t.match(/^(\d{2})([\/.x*:\-])(\d{1,2})$/)) && isSize_(m[1])) {
      if (m[2] === '-' && isSize_(m[3])) {
        addRange_(p, m[1], m[3]);
      } else if (Number(m[3]) > 0) {
        addSize_(p.sizes, m[1], Number(m[3]));
      }
      pendingQty = 0;
      continue;
    }

    if (isSize_(t)) {
      const next = list[k + 1] || '';
      let qty = pendingQty || 1;
      pendingQty = 0;
      if ((m = next.match(/^[x*\/:](\d{1,2})$/))) { qty = Number(m[1]); k++; }
      else if (/^[x*\/:]$/.test(next) && /^\d{1,2}$/.test(list[k + 2] || '') && !isSize_(list[k + 2])) { qty = Number(list[k + 2]); k += 2; }
      else if (next === '-' && isSize_(list[k + 2] || '')) { addRange_(p, t, list[k + 2]); k += 2; continue; }
      else if (/^\d{1,2}$/.test(next) && !isSize_(next) && unit.test(list[k + 2] || '')) { qty = Number(next); k += 2; }
      else if ((m = next.match(/^(\d{1,2})(doi|cai)$/))) { qty = Number(m[1]); k++; }
      else if (next === 'sl' && /^\d{1,2}$/.test(list[k + 2] || '')) { qty = Number(list[k + 2]); k += 2; }
      else if ((m = next.match(/^sl:?(\d{1,2})$/))) { qty = Number(m[1]); k++; }
      if (qty > 0) addSize_(p.sizes, t, qty);
    }
  }
}

function addRange_(p, from, to) {
  const a = Number(from), b = Number(to);
  if (b <= a) { p.sizeErrors.push(from + '-' + to); return; }
  for (let s = a; s <= b; s++) addSize_(p.sizes, String(s), 1);
}

function addSize_(sizes, size, qty) {
  const found = sizes.find(s => s.size === size);
  if (found) found.qty += qty; else sizes.push({ size, qty });
}

/** "bc" = hôm nay, "bc hom qua", "bc 10/10", "bc 10/10/2026". Trả về Date. */
function parseReportDate_(n) {
  const today = today_();
  if (/hom\s*qua/.test(n)) return new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
  const m = n.match(/(\d{1,2})[\/\-.](\d{1,2})(?:[\/\-.](\d{2,4}))?/);
  if (m) {
    let y = m[3] ? Number(m[3]) : today.getFullYear();
    if (y < 100) y += 2000;
    return new Date(y, Number(m[2]) - 1, Number(m[1]));
  }
  return today;
}

// =====================================================================
// TÁC VỤ
// =====================================================================

function doCheck_(p) {
  if (!p.code && !p.baseCode) {
    return { text: '🤔 Mình chưa hiểu tin này.\n\n' + HELP_TEXT };
  }
  const wantSizes = p.sizes.length ? p.sizes.map(s => s.size) : null;
  let codes = p.code ? [p.code] : [];
  if (!codes.length || !codeExists_(p.code)) {
    const base = p.baseCode || p.code;
    const byBase = codesByBase_(base);
    if (byBase.length) codes = byBase;
    else if (!p.code) return { text: '❌ Không có mã nào bắt đầu bằng ' + base + ' trong KHOY3C / KHO15E.' };
  }

  const prices = priceMap_();
  const blocks = [];
  codes.forEach(code => {
    const price = prices[code];
    const lines = ['🔎 ' + code + (price ? ' — ' + money_(price) : '')];
    let found = false;
    ['Y3C', '15E'].forEach(kho => {
      const rows = findKhoRows_(kho, code, wantSizes).sort((a, b) => sizeOrder_(a.item_size) - sizeOrder_(b.item_size));
      if (!rows.length) return;
      found = true;
      lines.push('📦 Kho ' + kho + ' — ' + (rows[0].product_color || ''));
      rows.forEach(r => {
        const qty = Number(r.current_quantity) || 0;
        const loc = r.product_location ? ' (' + r.product_location + ')' : '';
        lines.push('  ' + (r.item_size ? 'size ' + r.item_size : 'không size') + ': ' + (qty > 0 ? qty + ' đôi' + loc : 'hết'));
      });
    });
    if (!found) {
      lines.push('❌ Không có' + (wantSizes ? ' size ' + wantSizes.join(',') : '') + ' trong KHOY3C / KHO15E.');
    }
    blocks.push(lines.join('\n'));
  });
  return { text: blocks.join('\n\n') };
}

/** Bán / Nhập / Xuất tại 1 kho. */
function doMovement_(p, action, kho, dryRun) {
  const verb = action === ACTIONS.SELL ? 'ban' : action === ACTIONS.OUT ? 'xuat' : 'nhap';
  const codeEx = p.code || 'TH2040D';
  const sizeEx = p.sizes.length ? p.sizes.map(s => s.qty > 1 ? s.size + '/' + s.qty : s.size).join(' ') : '40';
  const priceEx = action === ACTIONS.SELL ? ' ' + (p.price ? Number(p.price) / 1000 + 'k' : '800k') : '';

  if (!p.code) {
    return { text: '❓ Thiếu mã sản phẩm (mã có chữ màu ở cuối, ví dụ TH2040D).' +
      (p.baseCode ? '\nMã ' + p.baseCode + ' chưa có màu — nhắn "' + p.baseCode + '" để xem các màu.' : '') +
      '\nNhắn lại: ' + verb + ' ' + codeEx + ' ' + sizeEx + ' YEN' + priceEx + '\n(nhắn "hd" để xem hướng dẫn)' };
  }
  if (!kho) {
    return { text: '❓ Thiếu kho (YEN/3C hoặc TBH/15E).\nNhắn lại: ' + verb + ' ' + codeEx + ' ' + sizeEx + ' YEN' + priceEx };
  }
  if (p.sizeErrors.length) {
    return { text: '❓ Dải size ' + p.sizeErrors.join(', ') + ' không hợp lệ (size đầu phải nhỏ hơn size cuối, ví dụ 38-43).' };
  }

  const khoRowsAll = findKhoRows_(kho, p.code, null);
  const otherKho = kho === 'Y3C' ? '15E' : 'Y3C';
  const knownSizes = khoRowsAll.length ? khoRowsAll : findKhoRows_(otherKho, p.code, null);
  if (!p.sizes.length && knownSizes.some(r => r.item_size)) {
    const list = knownSizes.map(r => r.item_size).filter(Boolean).sort((a, b) => sizeOrder_(a) - sizeOrder_(b));
    return { text: '❓ Thiếu size. ' + p.code + ' có size: ' + uniq_(list).join(', ') +
      '\nNhắn lại: ' + verb + ' ' + p.code + ' 40 ' + (kho === 'Y3C' ? 'YEN' : 'TBH') + priceEx };
  }

  const sizes = p.sizes.length ? p.sizes : [{ size: '', qty: 1 }];
  const color = p.color || lookupColor_(p.code);
  const warnings = [];
  const written = [];
  const ops = [];

  for (const s of sizes) {
    const rows = findKhoRows_(kho, p.code, [s.size]);
    if (action !== ACTIONS.IN) {
      if (!rows.length) {
        warnings.push('⚠️ ' + kho + p.code + s.size + ' chưa có trong ' + KHO_SHEETS[kho] + ' → tồn kho sẽ không trừ.');
      } else {
        const stock = Number(rows[0].current_quantity) || 0;
        if (stock < s.qty) {
          warnings.push('⚠️ ' + (s.size ? 'size ' + s.size : p.code) + ' kho ' + kho + ': tồn ' + stock + ', ' +
            (action === ACTIONS.SELL ? 'bán' : 'xuất') + ' ' + s.qty + ' → tồn sẽ âm. Kiểm tra lại kho.');
        }
      }
    }
    if (!dryRun) {
      if (action === ACTIONS.SELL) ops.push(appendBan_(p.code, color, p.price, s.size, s.qty, kho, 'cua_hang', CTX.seller));
      else if (action === ACTIONS.OUT) ops.push(appendXuat_(p.code, color, s.size, s.qty, kho));
      else ops.push(appendNhap_(p.code, color, s.size, s.qty, kho));
    }
    written.push((s.size ? 'size ' + s.size : 'không size') + ' × ' + s.qty);
  }

  const tab = action === ACTIONS.SELL ? 'BAN' : action === ACTIONS.OUT ? 'XUAT' : 'NHAP';
  const label = action + ' ' + p.code + ' (' + written.join(', ') + ') kho ' + kho;
  return {
    ok: true, ops, label,
    text: '✅ ' + action + ' ' + p.code + (color ? ' màu ' + color : '') + ' kho ' + kho +
      (action === ACTIONS.SELL && p.price ? ' giá ' + money_(p.price) : '') +
      '\n  ' + written.join('\n  ') + '\n→ tab ' + tab +
      (warnings.length ? '\n' + warnings.join('\n') : ''),
  };
}

/** Chuyển kho = XUẤT ở kho nguồn + NHẬP ở kho đích. */
function doTransfer_(p, dryRun) {
  if (!p.khoFrom || !p.khoTo) {
    return { text: '❓ Chuyển kho cần ghi "tu ... den ...".\nNhắn lại: chuyen kho ' + (p.code || 'TH2040D') + ' 40 tu YEN den TBH' };
  }
  if (p.khoFrom === p.khoTo) return { text: '❓ Kho nguồn và kho đích giống nhau (' + p.khoFrom + ').' };
  const out = doMovement_(p, ACTIONS.OUT, p.khoFrom, dryRun);
  if (!out.ok) return out;
  const inn = doMovement_(p, ACTIONS.IN, p.khoTo, dryRun);
  return {
    ok: true,
    ops: out.ops.concat(inn.ops || []),
    label: 'CHUYỂN KHO ' + p.code + ' ' + p.khoFrom + ' → ' + p.khoTo,
    text: '🔁 CHUYỂN KHO ' + p.khoFrom + ' → ' + p.khoTo + '\n' + out.text + '\n' + inn.text,
  };
}

/** Sửa product_location trong tab KHO. Không ghi size = đổi vị trí tất cả size của mã đó. */
function doMoveLocation_(p, dryRun) {
  if (!p.code) return { text: '❓ Thiếu mã sản phẩm.\nNhắn lại: chuyen vi tri TH2040D 40 YEN den K12' };
  if (!p.kho) return { text: '❓ Thiếu kho (YEN/3C hoặc TBH/15E).\nNhắn lại: chuyen vi tri ' + p.code + ' YEN den K12' };
  if (!p.location) return { text: '❓ Thiếu vị trí mới.\nNhắn lại: chuyen vi tri ' + p.code + ' ' + (p.kho === 'Y3C' ? 'YEN' : 'TBH') + ' den K12' };

  const sheetName = KHO_SHEETS[p.kho];
  const sheet = getSheet_(sheetName);
  const data = sheet.getDataRange().getValues();
  const col = headerMap_(data[0]);
  requireColumns_(sheetName, col, ['product_code', 'item_size', 'product_location']);

  const wantSizes = p.sizes.map(s => s.size);
  const changed = [];
  const ops = [];
  for (let r = 1; r < data.length; r++) {
    if (String(data[r][col.product_code]).trim().toUpperCase() !== p.code) continue;
    const size = normSize_(data[r][col.item_size]);
    if (wantSizes.length && wantSizes.indexOf(size) === -1) continue;
    if (!dryRun) {
      sheet.getRange(r + 1, col.product_location + 1).setValue(p.location);
      ops.push({ type: 'loc', sheet: sheetName, row: r + 1, oldLoc: String(data[r][col.product_location]), newLoc: p.location });
    }
    changed.push(size || 'không size');
  }
  if (!changed.length) return { text: '❌ Không tìm thấy ' + p.code + (wantSizes.length ? ' size ' + wantSizes.join(',') : '') + ' trong ' + sheetName + '.' };
  return {
    ok: true, ops, label: 'CHUYỂN VỊ TRÍ ' + p.code + ' về ' + p.location,
    text: '✅ Đã chuyển ' + p.code + ' (' + changed.join(',') + ') kho ' + p.kho + ' về vị trí ' + p.location,
  };
}

/** Huỷ thao tác gần nhất của người nhắn (trong 10 phút). Kiểm tra lại từng dòng trước khi huỷ. */
function doUndo_(chatId, dryRun) {
  const cache = CacheService.getScriptCache();
  const raw = chatId ? cache.get('last_' + chatId) : null;
  if (!raw) return { text: 'ℹ️ Không có thao tác nào của bạn trong 10 phút qua để huỷ.' };
  const last = JSON.parse(raw);

  // Kiểm tra toàn bộ trước, chỉ huỷ khi mọi dòng còn nguyên như lúc bot ghi
  const problems = [];
  last.ops.forEach(op => {
    const sheet = getSheet_(op.sheet);
    if (op.type === 'loc') {
      const col = headerMap_(sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]);
      const cur = String(sheet.getRange(op.row, col.product_location + 1).getValue());
      if (cur !== op.newLoc) problems.push(op.sheet + ' dòng ' + op.row + ' đã bị đổi vị trí thành "' + cur + '"');
      return;
    }
    const header = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    const col = headerMap_(header);
    const rowVals = sheet.getRange(op.row, 1, 1, header.length).getValues()[0];
    Object.keys(op.check).forEach(name => {
      if (normSize_(rowVals[col[name]]) !== normSize_(op.check[name])) {
        problems.push(op.sheet + ' dòng ' + op.row + ' đã bị sửa (' + name + ')');
      }
    });
    if (op.sheet === 'NHAP' && col.kho_sync !== undefined && String(rowVals[col.kho_sync]).trim()) {
      problems.push('NHAP dòng ' + op.row + ' đã được đồng bộ kho (kho_sync)');
    }
  });
  if (problems.length) {
    return { text: '⛔ Không huỷ được vì dữ liệu đã thay đổi:\n  ' + uniq_(problems).join('\n  ') + '\nVui lòng sửa tay trong Sheet.' };
  }

  if (!dryRun) {
    last.ops.forEach(op => {
      const sheet = getSheet_(op.sheet);
      const col = headerMap_(sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]);
      if (op.type === 'loc') {
        sheet.getRange(op.row, col.product_location + 1).setValue(op.oldLoc);
      } else {
        // Chỉ xoá các ô bot đã ghi (không đụng cột công thức khác, không xoá dòng)
        op.written.forEach(name => sheet.getRange(op.row, col[name] + 1).clearContent());
      }
    });
    cache.remove('last_' + chatId);
  }
  return { text: '↩️ Đã huỷ: ' + last.label };
}

/** Báo cáo bán trong 1 ngày theo kho, từ tab BAN. Doanh thu = Giá × số lượng. */
function doReport_(p) {
  const day = p.reportDate || today_();
  const dayKey = Utilities.formatDate(day, TZ, 'yyyy-MM-dd');
  const data = sheetValues_('BAN');
  const col = headerMap_(data[0]);
  requireColumns_('BAN', col, ['Ngày', 'Giá', 'item_quantity', 'KHO']);

  const byKho = {};
  let noPrice = 0;
  for (let r = 1; r < data.length; r++) {
    if (dateKey_(data[r][col['Ngày']]) !== dayKey) continue;
    const kho = String(data[r][col.KHO]).trim() || '?';
    const qty = Number(data[r][col.item_quantity]) || 0;
    const price = moneyValue_(data[r][col['Giá']]);
    if (!price) noPrice++;
    byKho[kho] = byKho[kho] || { qty: 0, revenue: 0 };
    byKho[kho].qty += qty;
    byKho[kho].revenue += price * qty;
  }

  const label = Utilities.formatDate(day, TZ, 'dd/MM/yyyy');
  const khos = Object.keys(byKho).sort();
  if (!khos.length) return { text: '📊 Ngày ' + label + ': chưa có dòng bán nào (có ghi ngày) trong tab BAN.' };
  let totalQty = 0, totalRev = 0;
  const lines = ['📊 BÁN NGÀY ' + label];
  khos.forEach(k => {
    lines.push('  Kho ' + k + ': ' + byKho[k].qty + ' đôi — ' + money_(byKho[k].revenue));
    totalQty += byKho[k].qty; totalRev += byKho[k].revenue;
  });
  lines.push('  Tổng: ' + totalQty + ' đôi — ' + money_(totalRev));
  if (noPrice) lines.push('  (' + noPrice + ' dòng chưa có giá, không tính doanh thu)');
  return { text: lines.join('\n') };
}

// =====================================================================
// CỬA "GHI BÁN" CHO APP BÁN HÀNG
// POST {WEBAPP_URL}?sale_key=<SALE_KEY>
// Body JSON: { ticket_id, seller, channel, lines: [{ code, size, qty, warehouse, price }], dry_run? }
// =====================================================================

function handleSaleRequest_(e) {
  let out;
  try {
    const props = PropertiesService.getScriptProperties();
    const saleKey = props.getProperty('SALE_KEY') || '';
    if (saleKey.length < 16 || saleKey === props.getProperty('WEBHOOK_KEY')) {
      out = { ok: false, error: 'chưa cấu hình SALE_KEY (≥16 ký tự, khác WEBHOOK_KEY) trong Script Properties' };
    } else if (e.parameter.sale_key !== saleKey) {
      out = { ok: false, error: 'unauthorized' };
    } else {
      const body = JSON.parse((e.postData && e.postData.contents) || '{}');
      const dryRun = String(props.getProperty('DRY_RUN') || '').toLowerCase() === 'true' || body.dry_run === true;
      out = handleSale_(body, dryRun);
    }
  } catch (err) {
    console.error(err && err.stack ? err.stack : err);
    out = { ok: false, error: 'bad_request: ' + (err && err.message ? err.message : err) };
  }
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
}

/**
 * Ghi 1 phiếu bán vào BAN. Kiểm tra hết các dòng trước: có dòng lỗi thì không ghi dòng nào.
 * Chống trùng theo ticket_id (lưu Script Properties 30 ngày). Trả kết quả từng dòng.
 */
function handleSale_(body, dryRun) {
  MEMO = {};
  const ticket = String(body.ticket_id || '').trim();
  const channel = String(body.channel || '').trim().toLowerCase();
  const seller = String(body.seller || '').trim().slice(0, 50);
  const lines = Array.isArray(body.lines) ? body.lines : [];
  if (!/^[A-Za-z0-9_.:\-]{1,64}$/.test(ticket)) return { ok: false, error: 'ticket_id không hợp lệ (1-64 ký tự: chữ, số, _ . : -)' };
  if (SALE_CHANNELS.indexOf(channel) === -1) return { ok: false, ticket_id: ticket, error: 'channel phải là: ' + SALE_CHANNELS.join(', ') };
  if (!lines.length || lines.length > SALE_MAX_LINES) return { ok: false, ticket_id: ticket, error: 'lines phải có 1-' + SALE_MAX_LINES + ' dòng' };

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const props = PropertiesService.getScriptProperties();
    const ticketKey = 'sale_' + ticket;
    const prev = props.getProperty(ticketKey);
    if (prev) {
      const p = JSON.parse(prev);
      return { ok: !p.partial, duplicate: true, partial: !!p.partial, ticket_id: ticket, rows: p.rows,
        error: p.partial ? 'Phiếu này lần trước chỉ ghi được ' + p.rows + ' dòng — kiểm tra tab BAN, KHÔNG gửi lại' : undefined };
    }

    const results = [];
    const plan = [];
    lines.forEach((ln, i) => {
      ln = ln || {};
      const code = String(ln.code || '').trim().toUpperCase();
      const size = normSize_(ln.size === undefined || ln.size === null ? '' : ln.size);
      const qty = ln.qty === undefined || ln.qty === null || ln.qty === '' ? 1 : Number(ln.qty);
      const kho = KHO_ALIASES[String(ln.warehouse || '').trim().toUpperCase()];
      const price = ln.price === undefined || ln.price === null || ln.price === '' ? '' : Number(ln.price);
      const r = { line: i + 1, code, size, qty, warehouse: kho || String(ln.warehouse || '') };
      const errs = [];
      if (!/^[A-Z0-9]{2,20}$/.test(code)) errs.push('mã không hợp lệ');
      else if (!codeExists_(code)) errs.push('mã không có trong KHOY3C/KHO15E');
      if (size && !/^\d{2}$/.test(size)) errs.push('size không hợp lệ');
      if (!Number.isInteger(qty) || qty < 1 || qty > 99) errs.push('qty phải là số nguyên 1-99');
      if (!kho) errs.push('warehouse phải là 15E hoặc Y3C');
      if (price !== '' && (!isFinite(price) || price < 0)) errs.push('price không hợp lệ');
      if (!errs.length) {
        const here = findKhoRows_(kho, code, null);
        const known = here.length ? here : findKhoRows_(kho === 'Y3C' ? '15E' : 'Y3C', code, null);
        if (!size && known.some(x => x.item_size)) errs.push('thiếu size');
        const rows = errs.length ? null : findKhoRows_(kho, code, [size]);
        if (!rows) {
          // đã có lỗi → không cần cảnh báo tồn
        } else if (!rows.length) {
          r.warning = 'SKU chưa có trong ' + KHO_SHEETS[kho] + ', tồn không trừ';
        } else {
          r.stock_before = Number(rows[0].current_quantity) || 0;
          if (r.stock_before < qty) r.warning = 'tồn ' + r.stock_before + ' < bán ' + qty + ' → tồn âm';
        }
      }
      if (errs.length) { r.ok = false; r.error = errs.join('; '); }
      else { r.ok = true; plan.push({ r, code, size, qty, kho, price }); }
      results.push(r);
    });
    if (results.some(r => !r.ok)) {
      return { ok: false, ticket_id: ticket, error: 'Có dòng lỗi, chưa ghi dòng nào', results };
    }

    if (!dryRun) {
      let written = 0;
      try {
        plan.forEach(x => {
          const op = appendBan_(x.code, lookupColor_(x.code), x.price, x.size, x.qty, x.kho, channel, seller);
          x.r.row = op.row;
          written++;
        });
      } catch (err) {
        props.setProperty(ticketKey, JSON.stringify({ t: Date.now(), rows: written, partial: true }));
        return { ok: false, partial: true, ticket_id: ticket, rows: written,
          error: 'Ghi dở: đã ghi ' + written + '/' + plan.length + ' dòng (' + (err && err.message ? err.message : err) + ') — KHÔNG gửi lại, kiểm tra tab BAN',
          results };
      }
      props.setProperty(ticketKey, JSON.stringify({ t: Date.now(), rows: written }));
      pruneSaleTickets_(props);
    }
    return { ok: true, ticket_id: ticket, dry_run: dryRun, rows: plan.length, results };
  } finally {
    lock.releaseLock();
  }
}

/** Xoá mã phiếu cũ hơn SALE_TICKET_DAYS ngày khỏi Script Properties. */
function pruneSaleTickets_(props) {
  const cutoff = Date.now() - SALE_TICKET_DAYS * 86400000;
  const all = props.getProperties();
  Object.keys(all).forEach(k => {
    if (k.indexOf('sale_') !== 0) return;
    try { if (JSON.parse(all[k]).t < cutoff) props.deleteProperty(k); } catch (e) { /* bỏ qua */ }
  });
}

// =====================================================================
// GHI SHEET
// =====================================================================

function appendBan_(code, color, price, size, qty, kho, channel, seller) {
  // FSKU của BAN tự tính bằng ARRAYFORMULA → không ghi cột FSKU.
  // channel / seller chỉ ghi khi tab BAN đã có 2 cột đó (cột thêm cuối hàng tiêu đề).
  return appendByHeader_('BAN', {
    'Ngày': today_(), 'product_code': code, 'product_color': color,
    'Giá': price ? Number(price) : '', 'item_size': sizeValue_(size), 'item_quantity': qty, 'KHO': kho,
  }, null, { product_code: code, item_size: size, item_quantity: qty, KHO: kho },
  { 'channel': channel || '', 'seller': seller || '' });
}

function appendXuat_(code, color, size, qty, kho) {
  // FSKU của XUAT tự tính bằng ARRAYFORMULA → không ghi cột FSKU
  return appendByHeader_('XUAT', {
    'Ngày': today_(), 'product_code': code, 'product_color': color,
    'KHO': kho, 'item_size': sizeValue_(size), 'item_quantity': qty,
  }, null, { product_code: code, item_size: size, item_quantity: qty, KHO: kho });
}

function appendNhap_(code, color, size, qty, kho) {
  const values = {
    'Ngày chứng từ (*)': today_(), 'product_code': code, 'product_color': color,
    'KHO': kho, 'item_size': sizeValue_(size), 'Số lượng (*)': qty,
  };
  NHAP_MARK_COLUMNS.forEach(c => { values[c] = NHAP_ZALO_MARK; });
  // FSKU của NHAP là công thức từng dòng: =CONCATENATE(KHO; product_code; item_size)
  return appendByHeader_('NHAP', values, (row, col) => {
    const a1 = c => columnLetter_(col[c] + 1) + row;
    return { 'FSKU': '=CONCATENATE(' + a1('KHO') + '; ' + a1('product_code') + '; ' + a1('item_size') + ')' };
  }, { product_code: code, item_size: size, 'Số lượng (*)': qty, KHO: kho });
}

/**
 * Ghi 1 dòng mới ngay sau dòng cuối có product_code, theo tên cột hàng 1.
 * Chỉ ghi vào các cột được truyền vào (không đè cột công thức khác). Tự thêm dòng nếu hết lưới.
 * optional: các cột chỉ ghi nếu tab có cột đó (không báo lỗi khi thiếu).
 * Trả về thông tin để có thể huỷ: { type, sheet, row, written, check }.
 */
function appendByHeader_(sheetName, values, formulaBuilder, check, optional) {
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
  Object.keys(optional || {}).forEach(name => {
    if (col[name] !== undefined && optional[name] !== '') all[name] = optional[name];
  });
  Object.keys(all).forEach(name => {
    const cell = sheet.getRange(row, col[name] + 1);
    const v = all[name];
    if (typeof v === 'string' && v.charAt(0) === '=') cell.setFormula(v);
    else cell.setValue(v);
  });
  return { type: 'row', sheet: sheetName, row, written: Object.keys(all), check };
}

// =====================================================================
// ĐỌC SHEET
// =====================================================================

function sheetValues_(name) {
  if (!MEMO[name]) MEMO[name] = getSheet_(name).getDataRange().getValues();
  return MEMO[name];
}

/** Các dòng trong tab KHO của 1 kho khớp mã. sizes = null → mọi size; mảng → đúng các size đó ('' = không size). */
function findKhoRows_(kho, code, sizes) {
  const sheetName = KHO_SHEETS[kho];
  const data = sheetValues_(sheetName);
  const col = headerMap_(data[0]);
  requireColumns_(sheetName, col, ['product_code', 'product_color', 'item_size', 'current_quantity', 'product_location']);
  const out = [];
  for (let r = 1; r < data.length; r++) {
    if (String(data[r][col.product_code]).trim().toUpperCase() !== code) continue;
    const size = normSize_(data[r][col.item_size]);
    if (sizes && sizes.indexOf(size) === -1) continue;
    out.push({
      item_size: size,
      product_color: data[r][col.product_color],
      current_quantity: data[r][col.current_quantity],
      product_location: data[r][col.product_location],
    });
  }
  return out;
}

/** Tập mã thật trong KHOY3C + KHO15E và mã gốc (bỏ chữ màu cuối) để nhận diện trong tin nhắn. */
function knownCodes_() {
  const codes = new Set(), bases = new Set();
  ['Y3C', '15E'].forEach(kho => {
    const data = sheetValues_(KHO_SHEETS[kho]);
    const col = headerMap_(data[0]);
    if (col.product_code === undefined) return;
    for (let r = 1; r < data.length; r++) {
      const c = String(data[r][col.product_code]).trim().toUpperCase();
      if (!c) continue;
      codes.add(c);
      if (c.length >= 3) bases.add(c.slice(0, -1));
    }
  });
  return { codes, bases };
}

function codeExists_(code) {
  return ['Y3C', '15E'].some(kho => findKhoRows_(kho, code, null).length > 0);
}

/** Các mã đầy đủ = mã gốc + 1 chữ màu (TH2040 → TH2040D, TH2040N...). */
function codesByBase_(base) {
  const found = {};
  ['Y3C', '15E'].forEach(kho => {
    const data = sheetValues_(KHO_SHEETS[kho]);
    const col = headerMap_(data[0]);
    for (let r = 1; r < data.length; r++) {
      const c = String(data[r][col.product_code]).trim().toUpperCase();
      if (c.length === base.length + 1 && c.indexOf(base) === 0 && /[A-Z]$/.test(c)) found[c] = true;
    }
  });
  return Object.keys(found).sort();
}

function lookupColor_(code) {
  for (const kho of ['Y3C', '15E']) {
    const rows = findKhoRows_(kho, code, null);
    if (rows.length && rows[0].product_color) return rows[0].product_color;
  }
  return '';
}

/** Giá bán theo mã từ tab SANPHAM (cột product_price; tên cột nằm ở hàng 1 hoặc hàng 2). */
function priceMap_() {
  if (MEMO.__prices) return MEMO.__prices;
  const data = sheetValues_('SANPHAM');
  let headerRow = -1;
  for (let r = 0; r < Math.min(2, data.length); r++) {
    if (data[r].map(h => String(h).trim()).indexOf('product_code') !== -1) { headerRow = r; break; }
  }
  const map = {};
  if (headerRow !== -1) {
    const col = headerMap_(data[headerRow]);
    if (col.product_price !== undefined) {
      for (let r = headerRow + 1; r < data.length; r++) {
        const code = String(data[r][col.product_code]).trim().toUpperCase();
        const price = moneyValue_(data[r][col.product_price]);
        if (code && price) map[code] = price;
      }
    }
  }
  MEMO.__prices = map;
  return map;
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

function sizeOrder_(s) {
  return s === '' ? 9999 : (Number(s) || 9998);
}

function sizeValue_(size) {
  return size && /^\d+$/.test(size) ? Number(size) : (size || '');
}

function uniq_(arr) {
  return arr.filter((v, i) => arr.indexOf(v) === i);
}

/** Số tiền từ ô Sheet: 800000 hoặc "800.000 đ" → 800000. */
function moneyValue_(v) {
  if (typeof v === 'number') return v;
  const digits = String(v || '').replace(/[^\d]/g, '');
  return digits ? Number(digits) : 0;
}

function money_(v) {
  return Number(v).toLocaleString('vi-VN') + 'đ';
}

/** Ô ngày (Date hoặc chuỗi dd/MM/yyyy) → "yyyy-MM-dd". */
function dateKey_(v) {
  if (v instanceof Date && !isNaN(v)) return Utilities.formatDate(v, TZ, 'yyyy-MM-dd');
  const m = String(v || '').trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (!m) return '';
  return m[3] + '-' + ('0' + m[2]).slice(-2) + '-' + ('0' + m[1]).slice(-2);
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
    'TH2040D 40',
    'TH2040',
    'ban TH2040D 40 YEN 800k',
    'nhap TH2040D 38/2 39 TBH',
    'xuat TH2040D 41.2 15E',
    'chuyen kho TH2040D 40 tu YEN den TBH',
    'chuyen vi tri TH2040D YEN den K12',
    'bc',
    'hd',
    'xin chào',
  ].forEach(t => {
    console.log('▶ ' + t + '\n' + handleText_(t, true, ''));
  });
}

/** Chạy thử cửa "ghi bán" (luôn dry-run, KHÔNG ghi Sheet). Xem kết quả ở Nhật ký thực thi. */
function testSale() {
  [
    { ticket_id: 'TEST-001', seller: 'Kha', channel: 'cua_hang',
      lines: [{ code: 'TH2040D', size: 40, qty: 1, warehouse: 'Y3C', price: 800000 },
              { code: 'TH2040D', size: '41', qty: 2, warehouse: 'YEN', price: 800000 }] },
    { ticket_id: 'TEST-002', seller: 'Kha', channel: 'web',
      lines: [{ code: 'TH2040D', size: 40, qty: 1, warehouse: '15E', price: 800000 }] },
    { ticket_id: 'TEST-003', seller: 'Kha', channel: 'shopee',
      lines: [{ code: 'KHONGCO1X', size: 40, qty: 1, warehouse: '15E' },
              { code: 'TH2040D', qty: 1, warehouse: 'Y3C' }] },
    { ticket_id: 'TEST-004', seller: 'Kha', channel: 'facebook', lines: [{ code: 'TH2040D', size: 40, warehouse: 'Y3C' }] },
  ].forEach(t => console.log('▶ ' + t.ticket_id + '\n' + JSON.stringify(handleSale_(t, true), null, 1)));
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
