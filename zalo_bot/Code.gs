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
// Dòng NHAP trả hàng / huỷ đơn đã bán: Số chứng từ = TRA-<ddMMyy>, 3 cột trên = Tra_hang (không xuất phiếu nhập MISA)
const NHAP_RETURN_MARK = 'Tra_hang';

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
  INVOICE: 'HOÁ ĐƠN NCC',
};

const HELP_TEXT = [
  '📖 HƯỚNG DẪN BOT KHO HNC',
  '🔎 Kiểm hàng: TH2040D 40  |  TH2040 (mọi màu)',
  '🛒 Bán: ban TH2040D 40 YEN 800k  (bán ngoài cửa hàng: thêm shopee | tiktok | web | lazada | zalo | fb)',
  '📥 Nhập: nhap TH2040D 38/2 39 TBH',
  '↩️ Khách trả hàng / huỷ đơn: nhap TH2040D 40 15E tra hang',
  '📤 Xuất: xuat TH2040D 41 15E',
  '🔁 Chuyển kho: chuyen kho TH2040D 40 tu YEN den TBH',
  '📍 Chuyển vị trí: chuyen vi tri TH2040D YEN den K12',
  '📑 Nhiều dòng: mỗi dòng 1 lệnh ban/nhap/xuat (gửi chung 1 tin)',
  '↩️ Huỷ thao tác vừa rồi (10 phút, cả lô): huy',
  '📊 Báo cáo bán: bc  |  bc hom qua  |  bc 10/10',
  '🧾 Hoá đơn NCC: hoadon  |  hoadon <mã phiếu>  |  hoadon <mã phiếu> da / khong / chua',
  '— Kho: YEN/3C = Y3C, TBH/15E = 15E',
  '— Size: 40 | 40/2 | 40x2 | 40.2 | 2 đôi 40 | 38-43',
  '— Hàng không size: x2 | 2 cái | sl 2',
  '— Giá: 800k | 800000 | 800.000đ | 1tr2',
  '— Gõ không dấu vẫn được.',
].join('\n');

// Bộ nhớ đệm đọc Sheet trong 1 lần xử lý tin nhắn
let MEMO = {};
// Ngữ cảnh tin nhắn đang xử lý (tên người nhắn → cột seller của BAN)
let CTX = {};

// Cửa "ghi bán" cho app bán hàng
// Kênh nhận từ app; 'cua_hang' (bán tại quầy) ghi ô trống — quy ước: channel trống = bán tại cửa hàng theo KHO
const SALE_CHANNELS = ['cua_hang', 'web', 'shopee', 'tiktok', 'lazada', 'zalo', 'facebook'];
const SALE_MAX_LINES = 50;
const SALE_TICKET_DAYS = 30; // giữ mã phiếu / mã đơn đã xử lý 30 ngày để chống trùng

// Cửa "báo đơn web": chỉ nhắn anh, không đọc lệnh, không ghi Sheet
const NOTIFY_MAX_CHARS = 1800;

// =====================================================================
// WEBHOOK
// =====================================================================

function doGet() {
  return ContentService.createTextOutput('HNC Zalo Bot OK');
}

function doPost(e) {
  if (e && e.parameter && e.parameter.sale_key !== undefined) return handleSaleRequest_(e);
  if (e && e.parameter && e.parameter.notify_key !== undefined) return handleNotifyRequest_(e);
  if (e && e.parameter && e.parameter.export_key !== undefined) return handleExportRequest_(e);
  if (e && e.parameter && e.parameter.stock_key !== undefined) return handleStockRequest_(e);
  try {
    const props = PropertiesService.getScriptProperties();
    const key = props.getProperty('WEBHOOK_KEY');
    if (!key || !e || !e.parameter || e.parameter.key !== key) return ok_();

    const body = JSON.parse((e.postData && e.postData.contents) || '{}');
    const msg = body.message;
    if (!msg || !msg.chat) return ok_();
    if (!msg.text) {
      console.log('Zalo sự kiện chưa xử lý: ' + body.event_name + ' | khoá message: ' + Object.keys(msg).join(','));
      return ok_();
    }

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
  const out = handleTextLocked_(text, dryRun, chatId, sellerName);
  // Báo web chép lại Sheet SAU khi nhả khoá (trigger onEdit không chạy khi script tự ghi)
  if (!dryRun && out.syncTabs.length) {
    try { queueSyncHint_(out.syncTabs); } catch (e) { console.error(e && e.stack ? e.stack : e); }
  }
  return out.reply;
}

function handleTextLocked_(text, dryRun, chatId, sellerName) {
  MEMO = {};
  CTX = { seller: sellerName || '', pending: {} };
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    let res, isWrite;
    try {
      // Tin nhiều dòng: mỗi dòng bắt đầu bằng ban/nhap/xuat là 1 lệnh (dòng khác bỏ qua). Tin 1 dòng chạy như cũ.
      const lines = String(text || '').split(/\r?\n/).map(l => l.trim()).filter(Boolean);
      const cmdLines = lines.filter(isBatchCommandLine_);
      if (lines.length > 1 && cmdLines.length) {
        res = runBatch_(cmdLines, dryRun);
        isWrite = true;
      } else {
        const one = runOne_(text, dryRun, chatId);
        res = one.res;
        isWrite = one.isWrite;
      }
    } catch (err) {
      console.error(err && err.stack ? err.stack : err);
      // Có thể đã ghi dở → báo web chép lại các tab có thể đã đổi
      return { reply: '⚠️ Lỗi: ' + (err && err.message ? err.message : err) + '\nKiểm tra lại Sheet xem đã ghi chưa. Báo anh Kha nếu lỗi lặp lại.',
        syncTabs: ['BAN', 'NHAP', 'XUAT'] };
    }
    const syncTabs = uniq_((res.ops || []).map(o => o.sheet).concat(res.touched || []));
    if (res.ops && res.ops.length && !dryRun && chatId) {
      CacheService.getScriptCache().put('last_' + chatId,
        JSON.stringify({ label: res.label || '', ops: res.ops }), UNDO_SECONDS);
      res.text += '\n↩️ Nhắn "huy" trong 10 phút nếu ghi nhầm' + (res.batch ? ' (huỷ cả lô).' : '.');
    }
    return { reply: (dryRun && isWrite ? '🧪 CHẠY THỬ — chưa ghi Sheet\n' : '') + res.text, syncTabs };
  } finally {
    lock.releaseLock();
  }
}

function runOne_(text, dryRun, chatId) {
  const p = parseMessage_(text, knownCodes_());
  let res;
  switch (p.action) {
    case ACTIONS.HELP: res = { text: HELP_TEXT }; break;
    case ACTIONS.CHECK: res = doCheck_(p); break;
    case ACTIONS.REPORT: res = doReport_(p); break;
    case ACTIONS.INVOICE: res = doInvoice_(p.text, dryRun); break;
    case ACTIONS.UNDO: res = doUndo_(chatId, dryRun); break;
    case ACTIONS.MOVE_LOC: res = doMoveLocation_(p, dryRun); break;
    case ACTIONS.TRANSFER: res = doTransfer_(p, dryRun); break;
    default: res = doMovement_(p, p.action, p.kho, dryRun); break;
  }
  const writes = [ACTIONS.SELL, ACTIONS.OUT, ACTIONS.IN, ACTIONS.TRANSFER, ACTIONS.MOVE_LOC, ACTIONS.UNDO];
  return { res, isWrite: writes.indexOf(p.action) !== -1 };
}

/** Dòng bắt đầu bằng ban/bán/nhap/nhập/xuat/xuất. */
function isBatchCommandLine_(line) {
  const first = (String(line).normalize('NFC').toLowerCase().split(/\s+/)[0] || '').replace(/[.,:;!-]+$/, '');
  return ['bán', 'ban', 'nhập', 'nhap', 'xuất', 'xuat'].indexOf(first) !== -1;
}

/** Chạy lần lượt từng dòng lệnh, trả kết quả từng dòng; ops gộp chung để "huy" huỷ cả lô. */
function runBatch_(lines, dryRun) {
  const known = knownCodes_();
  const out = [];
  const ops = [];
  let okCount = 0;
  lines.forEach((line, i) => {
    let r;
    try {
      const p = parseMessage_(line, known);
      r = doMovement_(p, p.action, p.kho, dryRun);
    } catch (err) {
      r = { text: '⚠️ Lỗi: ' + (err && err.message ? err.message : err) };
    }
    if (r.ok) okCount++;
    if (r.ops) r.ops.forEach(o => ops.push(o));
    out.push((i + 1) + ') ' + r.text.replace(/\n/g, '\n   '));
  });
  const failed = lines.length - okCount;
  return {
    batch: true, ops, label: 'LÔ ' + okCount + ' lệnh',
    text: '📋 ' + lines.length + ' lệnh — ' + okCount + ' ghi được' + (failed ? ', ' + failed + ' lỗi (xem bên dưới)' : '') + '\n' + out.join('\n'),
  };
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
  'mau', 'doi', 'cai', 'huy', 'bao', 'cao', 'hom', 'nay', 'con', 'khong', 'size', 'gia', 'oi',
  'tra', 'hang', 'lai', 'khach'];

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
  else if (/^hoa\s*don(\s|$)/.test(n)) action = ACTIONS.INVOICE;
  else if (/chuyen\s*vi\s*tri/.test(n)) action = ACTIONS.MOVE_LOC;
  else if (/chuyen\s*kho/.test(n)) action = ACTIONS.TRANSFER;
  else if (hasRaw(['bán', 'ban'])) action = ACTIONS.SELL;
  else if (hasRaw(['xuất', 'xuat'])) action = ACTIONS.OUT;
  else if (hasRaw(['nhập', 'nhap'])) action = ACTIONS.IN;

  const p = {
    action, kho: '', khoFrom: '', khoTo: '', location: '', color: '', price: '',
    code: '', baseCode: '', sizes: [], qty: 0, sizeErrors: [], reportDate: null, channel: '', text,
  };
  if (action === ACTIONS.HELP || action === ACTIONS.UNDO || action === ACTIONS.INVOICE) return p;
  // Trả hàng / huỷ đơn: "tra hang", "trả hàng", "tra lai", "khach tra", "hang tra" (chỉ có tác dụng với lệnh nhập)
  p.returnGoods = action === ACTIONS.IN && /(^|\s)(tra\s*hang|tra\s*lai|khach\s*tra|hang\s*tra)(\s|$|[.,!])/.test(n);
  if (action === ACTIONS.REPORT) { p.reportDate = parseReportDate_(n); return p; }

  const used = {}; // chỉ số token đã dùng cho kho / vị trí / giá / mã

  // ---- Kênh bán (chỉ khi bán ngoài cửa hàng): shopee / tiktok / web. Trống = bán tại cửa hàng theo KHO ----
  if (action === ACTIONS.SELL) {
    toks.forEach((t, i) => {
      const tk = t.replace(/[^a-z]/g, '');
      const ch = { shopee: 'shopee', tiktok: 'tiktok', tt: 'tiktok', web: 'web', lazada: 'lazada', zalo: 'zalo', facebook: 'facebook', fb: 'facebook' }[tk] || '';
      if (ch && !p.channel) { p.channel = ch; used[i] = true; }
    });
  }

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
  if (!p.sizes.length) parseQtyNoSize_(list, p, pendingQty);
}

/** Hàng KHÔNG size: x2 | x 2 | *2 | /2 | sl 2 | sl2 | sl:2 | 2 cái | 2 đôi | 2cai → p.qty. */
function parseQtyNoSize_(list, p, pendingQty) {
  let m;
  for (let k = 0; k < list.length; k++) {
    const t = list[k], next = list[k + 1] || '';
    if ((m = t.match(/^[x*\/](\d{1,3})$/)) || (m = t.match(/^sl:?(\d{1,3})$/))) { p.qty = Number(m[1]); return; }
    if ((t === 'x' || t === '*' || t === 'sl') && /^\d{1,3}$/.test(next)) { p.qty = Number(next); return; }
  }
  if (pendingQty) p.qty = pendingQty;
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

  const sizes = p.sizes.length ? p.sizes : [{ size: '', qty: p.qty || 1 }];
  const color = p.color || lookupColor_(p.code);
  const warnings = [];
  const written = [];
  const ops = [];
  const kygui = [];

  for (const s of sizes) {
    const rows = findKhoRows_(kho, p.code, [s.size]);
    if (action !== ACTIONS.IN) {
      if (!rows.length) {
        warnings.push('⚠️ ' + kho + p.code + s.size + ' chưa có trong ' + KHO_SHEETS[kho] + ' → tồn kho sẽ không trừ.');
      } else {
        const pendKey = kho + p.code + s.size;
        const stock = (Number(rows[0].current_quantity) || 0) - ((CTX.pending || {})[pendKey] || 0);
        if (stock < s.qty) {
          warnings.push('⚠️ ' + (s.size ? 'size ' + s.size : p.code) + ' kho ' + kho + ': tồn ' + stock + ', ' +
            (action === ACTIONS.SELL ? 'bán' : 'xuất') + ' ' + s.qty + ' → tồn sẽ âm. Kiểm tra lại kho.');
        }
      }
    }
    // channel trống = bán tại cửa hàng theo KHO (quy ước 16/10); chỉ ghi khi bán ngoài cửa hàng. Bán: trừ hàng ký gửi trước.
    if (action === ACTIONS.SELL) {
      const sr = kyguiSale_(p.code, color, p.price, s.size, s.qty, kho, p.channel || '', CTX.seller, dryRun);
      sr.ops.forEach(o => ops.push(o));
      sr.phan.filter(x => x.chu_hang !== kho).forEach(x => kygui.push({ size: s.size, chu_hang: x.chu_hang, qty: x.qty, loai: 'ban_hang_ky_gui' }));
    } else if (!dryRun && action === ACTIONS.OUT) {
      ops.push(appendXuat_(p.code, color, s.size, s.qty, kho));
    } else if (action === ACTIONS.IN) {
      if (!dryRun) ops.push(appendNhap_(p.code, color, s.size, s.qty, kho, p.returnGoods));
      if (p.returnGoods) {
        const rr = kyguiReturn_(p.code, s.size, s.qty, kho, p.owner, dryRun);
        rr.ops.forEach(o => ops.push(o));
        if (rr.chu_hang !== kho) kygui.push({ size: s.size, chu_hang: rr.chu_hang, qty: s.qty, loai: 'tra_ve_ky_gui' });
      }
    }
    // Ghi nhớ số đã bán/xuất/nhập trong cùng lô để cảnh báo tồn của dòng sau tính đúng
    if (!CTX.pending) CTX.pending = {};
    const pk = kho + p.code + s.size;
    CTX.pending[pk] = (CTX.pending[pk] || 0) + (action === ACTIONS.IN ? -s.qty : s.qty);
    written.push((s.size ? 'size ' + s.size : 'không size') + ' × ' + s.qty);
    if (action !== ACTIONS.IN) { const w = kyguiCheck_(p.code, s.size, kho); if (w) warnings.push(w); }
  }
  const kyText = kygui.map(x => '  ↳ ' + (x.size ? 'size ' + x.size + ': ' : '') + x.qty + ' là hàng của hộ ' + x.chu_hang +
    (x.loai === 'tra_ve_ky_gui' ? ' (trả về sổ ký gửi)' : ' (ký gửi, tiền / hoá đơn thuộc ' + x.chu_hang + ')'));

  const tab = action === ACTIONS.SELL ? 'BAN' : action === ACTIONS.OUT ? 'XUAT' : 'NHAP';
  const label = action + ' ' + p.code + ' (' + written.join(', ') + ') kho ' + kho;
  return {
    ok: true, ops, label, warnings, kygui,
    text: (action === ACTIONS.IN && p.returnGoods ? '↩️ TRẢ HÀNG: nhập lại ' + p.code : '✅ ' + action + ' ' + p.code) +
      (action === ACTIONS.SELL && p.channel ? ' (' + p.channel + ')' : '') +
      (color ? ' màu ' + color : '') + ' kho ' + kho +
      (action === ACTIONS.SELL && p.price ? ' giá ' + money_(p.price) : '') +
      '\n  ' + written.join('\n  ') + (kyText.length ? '\n' + kyText.join('\n') : '') + '\n→ tab ' + tab +
      (action === ACTIONS.IN && p.returnGoods ? '\n(Số chứng từ TRA-…, không xuất phiếu nhập MISA)' : '') +
      (warnings.length ? '\n' + warnings.join('\n') : ''),
  };
}

/** Sổ ký gửi cho 1 lệnh chuyển kho (mọi size của lệnh) → { ops, notes, text }. */
function transferKygui_(p, from, to, dry) {
  const sizes = p.sizes.length ? p.sizes : [{ size: '', qty: p.qty || 1 }];
  const res = { ops: [], notes: [], text: '' };
  sizes.forEach(s => { const r = kyguiTransfer_(p.code, s.size, s.qty, from, to, dry); res.ops = res.ops.concat(r.ops); res.notes = res.notes.concat(r.notes); });
  res.text = res.notes.map(n => '  📒 ' + (n.size ? 'size ' + n.size + ': ' : '') + n.qty + (n.loai === 'tra_ve_chu' ? ' trả về hộ ' + n.chu_hang + ' (bớt ký gửi)' :
    ' thành hàng ký gửi của hộ ' + n.chu_hang + ' ở ' + to)).join('\n');
  return res;
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
  const ky = transferKygui_(p, p.khoFrom, p.khoTo, dryRun);
  return {
    ok: true,
    ops: out.ops.concat(inn.ops || [], ky.ops),
    label: 'CHUYỂN KHO ' + p.code + ' ' + p.khoFrom + ' → ' + p.khoTo,
    text: '🔁 CHUYỂN KHO ' + p.khoFrom + ' → ' + p.khoTo + '\n' + out.text + '\n' + inn.text + (ky.text ? '\n' + ky.text : ''),
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
  const r = undoRecord_(last, dryRun);
  if (r.ok && !dryRun) cache.remove('last_' + chatId);
  return r;
}

/** Huỷ 1 bản ghi thao tác ({label, ops}): kiểm tra toàn bộ trước, chỉ huỷ khi mọi dòng còn nguyên như lúc bot ghi. */
function undoRecord_(last, dryRun) {
  const problems = [];
  const ownRows = {};
  const tabCache = {};
  last.ops.forEach(op => { (ownRows[op.sheet] = ownRows[op.sheet] || {})[op.row] = true; });
  last.ops.forEach(op => {
    const sheet = getSheet_(op.sheet);
    if (op.guard) receiptUndoGuard_(op.guard, ownRows, tabCache).forEach(x => problems.push(x));
    if (op.type === 'kygui') {
      const col = headerMap_(sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]);
      const cur = Number(sheet.getRange(op.row, col.so_luong + 1).getValue()) || 0;
      if (cur !== op.after) problems.push('KYGUI dòng ' + op.row + ' đã đổi (' + cur + ', lúc ghi ' + op.after + ')');
      return;
    }
    if (op.type === 'loc') {
      const col = headerMap_(sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]);
      const cur = String(sheet.getRange(op.row, col.product_location + 1).getValue());
      if (cur !== op.newLoc) problems.push(op.sheet + ' dòng ' + op.row + ' đã bị đổi vị trí thành "' + cur + '"');
      return;
    }
    const header = sheet.getRange(op.hr || 1, 1, 1, sheet.getLastColumn()).getValues()[0];
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
    return { ok: false, problems: uniq_(problems),
      text: '⛔ Không huỷ được vì dữ liệu đã thay đổi:\n  ' + uniq_(problems).join('\n  ') + '\nVui lòng sửa tay trong Sheet.' };
  }

  if (!dryRun) {
    last.ops.forEach(op => {
      const sheet = getSheet_(op.sheet);
      const col = headerMap_(sheet.getRange(op.hr || 1, 1, 1, sheet.getLastColumn()).getValues()[0]);
      if (op.type === 'loc') {
        sheet.getRange(op.row, col.product_location + 1).setValue(op.oldLoc);
      } else if (op.type === 'kygui') {
        if (op.created) op.created.forEach(n => sheet.getRange(op.row, col[n] + 1).clearContent()); // dòng bot vừa thêm → xoá
        else {
          sheet.getRange(op.row, col.so_luong + 1).setValue(op.before);
          sheet.getRange(op.row, col.cap_nhat + 1).setValue(Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm'));
        }
      } else if (op.cols) {
        op.cols.forEach(c => sheet.getRange(op.row, c).clearContent()); // dòng SANPHAM tạo từ phiếu: xoá cả ô công thức đã chép
      } else {
        // Chỉ xoá các ô bot đã ghi (không đụng cột công thức khác, không xoá dòng)
        op.written.forEach(name => sheet.getRange(op.row, col[name] + 1).clearContent());
      }
    });
  }
  return { ok: true, text: '↩️ Đã huỷ: ' + last.label, touched: dryRun ? [] : uniq_(last.ops.map(o => o.sheet)) };
}

/**
 * Dòng SANPHAM / KHO tạo từ phiếu chỉ huỷ được khi mã (kho × size) chưa có giao dịch nào khác ngoài lần nhập đang huỷ:
 * còn dòng NHAP khác, hoặc đã bán / xuất → không huỷ, sửa tay.
 */
function receiptUndoGuard_(g, ownRows, tabCache) {
  const problems = [];
  [['NHAP'], ['BAN'], ['XUAT']].forEach(t => {
    const data = tabCache[t[0]] || (tabCache[t[0]] = getSheet_(t[0]).getDataRange().getValues()); // đọc mỗi tab 1 lần / lần huỷ
    const col = headerMap_(data[0]);
    if (col.product_code === undefined) return;
    for (let r = 1; r < data.length; r++) {
      if (String(data[r][col.product_code]).trim().toUpperCase() !== g.code) continue;
      if (g.size !== undefined && col.item_size !== undefined && normSize_(data[r][col.item_size]) !== g.size) continue;
      if (g.kho && col.KHO !== undefined && KHO_ALIASES[String(data[r][col.KHO]).trim().toUpperCase()] !== g.kho) continue;
      if ((ownRows[t[0]] || {})[r + 1]) continue;
      problems.push(g.code + (g.size ? ' size ' + g.size : '') + (g.kho ? ' kho ' + g.kho : '') + ' đã có giao dịch khác (' + t[0] + ' dòng ' + (r + 1) + ')');
      break;
    }
  });
  return problems;
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
      out = body.action === 'huy_ban' ? saleUndo_(body, dryRun) : handleSale_(body, dryRun);
      if (body.action === 'huy_ban') {
        if (!dryRun && out.ok) { try { queueSyncHint_(['BAN'].concat(out._ky ? [KYGUI_TAB] : [])); } catch (err) { console.error(err && err.stack ? err.stack : err); } }
        delete out._ky;
      } else if (!dryRun && (out.rows || out.partial) && !out.duplicate) {
        try { queueSyncHint_(['BAN']); } catch (err) { console.error(err && err.stack ? err.stack : err); }
      }
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
  CTX = { seller: '', pending: {} };
  const ticket = String(body.ticket_id || '').trim();
  const channel = String(body.channel || '').trim().toLowerCase();
  const seller = String(body.seller || '').trim().slice(0, 50);
  const lines = Array.isArray(body.lines) ? body.lines : [];
  if (!/^[A-Za-z0-9_.:\-]{1,64}$/.test(ticket)) return { ok: false, error: 'ticket_id không hợp lệ (1-64 ký tự: chữ, số, _ . : -)' };
  if (SALE_CHANNELS.indexOf(channel) === -1) return { ok: false, ticket_id: ticket, error: 'channel phải là: ' + SALE_CHANNELS.join(', ') };
  if (!lines.length || lines.length > SALE_MAX_LINES) return { ok: false, ticket_id: ticket, error: 'lines phải có 1-' + SALE_MAX_LINES + ' dòng' };
  const inv = misaInvoiceInput_(body);
  if (inv.error) return { ok: false, ticket_id: ticket, error: inv.error };

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
    let touchedKygui = false;
    let misaSent = 0;
    const saleOps = [];
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
      else {
        r.ok = true;
        // Chủ hàng theo sổ ký gửi (chạy thử, chưa ghi): hàng của hộ kia đang ở kho này bán trước
        const ph = kyguiSale_(code, '', price, size, qty, kho, '', '', true);
        r.phan = ph.phan;
        r.chu_hang = ph.phan.length === 1 ? ph.phan[0].chu_hang : '';
        CTX.pending[kho + code + size] = (CTX.pending[kho + code + size] || 0) + qty;
        const w = kyguiCheck_(code, size, kho);
        if (w) r.warning = (r.warning ? r.warning + '; ' : '') + w.replace(/^⚠️ /, '');
        plan.push({ r, code, size, qty, kho, price });
      }
      results.push(r);
    });
    if (results.some(r => !r.ok)) {
      return { ok: false, ticket_id: ticket, error: 'Có dòng lỗi, chưa ghi dòng nào', results };
    }

    if (!dryRun) {
      let written = 0;
      MEMO = {};
      CTX = { seller: '', pending: {} };
      try {
        plan.forEach(x => {
          const sr = kyguiSale_(x.code, lookupColor_(x.code), x.price, x.size, x.qty, x.kho, channel === 'cua_hang' ? '' : channel, seller, false);
          sr.ops.forEach(o => saleOps.push(o));
          const bans = sr.ops.filter(o => o.sheet === 'BAN');
          x.r.row = bans.length ? bans[0].row : '';
          if (bans.length > 1) x.r.rows = bans.map(o => o.row);
          x.r.phan = sr.phan;
          x.r.chu_hang = sr.phan.length === 1 ? sr.phan[0].chu_hang : '';
          if (sr.ops.some(o => o.sheet === KYGUI_TAB)) touchedKygui = true;
          written++;
        });
      } catch (err) {
        props.setProperty(ticketKey, JSON.stringify({ t: Date.now(), rows: written, partial: true }));
        return { ok: false, partial: true, ticket_id: ticket, rows: written,
          error: 'Ghi dở: đã ghi ' + written + '/' + plan.length + ' dòng (' + (err && err.message ? err.message : err) + ') — KHÔNG gửi lại, kiểm tra tab BAN',
          results };
      }
      props.setProperty(ticketKey, JSON.stringify({ t: Date.now(), rows: written }));
      pruneTickets_(props, 'sale_');
      saleRecordOps_(props, ticket, seller, saleOps, !!inv.hd);
      if (inv.hd) {
        try { misaSent = misaInvoiceSend_(ticket, channel, seller, inv, plan); }
        catch (err) { console.error('Không gửi được tin MISA: ' + (err && err.stack ? err.stack : err)); misaSent = 0; }
      }
      if (touchedKygui) { try { queueSyncHint_([KYGUI_TAB]); } catch (err) { console.error(err && err.stack ? err.stack : err); } }
    }
    const out = { ok: true, ticket_id: ticket, dry_run: dryRun, rows: plan.length, results };
    if (inv.hd) out.misa = dryRun ? { se_gui: uniq_([].concat.apply([], plan.map(x => (x.r.phan || [{ chu_hang: x.kho }]).map(ph => ph.chu_hang)))).sort() } : { da_gui: misaSent };
    return out;
  } finally {
    lock.releaseLock();
  }
}

// ---- Huỷ phiếu bán (huy_ban): người bán ≤ 10 phút, Chủ sau hạn (giữ 2 ngày) ----
const SALE_UNDO_KEEP_MS = 2 * 86400000;
const BAN_WRITE_COLS = ['Ngày', 'product_code', 'product_color', 'Giá', 'item_size', 'item_quantity', 'KHO', 'channel', 'seller', 'chu_hang'];

/** Lưu gọn thao tác của 1 phiếu bán để huỷ được: BAN [hàng, mã, size, sl, kho, chủ] · KYGUI [hàng, trước, sau]. */
function saleRecordOps_(props, ticket, seller, ops, hd) {
  const rec = { t: Date.now(), s: String(seller || '').toLowerCase(), hd: hd ? 1 : 0,
    b: ops.filter(o => o.sheet === 'BAN').map(o => [o.row, o.check.product_code, normSize_(o.check.item_size), o.check.item_quantity, o.check.KHO]),
    k: ops.filter(o => o.type === 'kygui').map(o => [o.row, o.before, o.after, o.created ? 1 : 0]) };
  try { props.setProperty('saleops_' + ticket, JSON.stringify(rec)); } catch (err) { console.error('Không lưu được thao tác phiếu ' + ticket + ': ' + err); }
  const cutoff = Date.now() - SALE_UNDO_KEEP_MS;
  Object.keys(props.getProperties()).forEach(k => {
    if (k.indexOf('saleops_') !== 0) return;
    try { if (JSON.parse(props.getProperty(k)).t < cutoff) props.deleteProperty(k); } catch (e) { /* bỏ qua */ }
  });
}

/** Huỷ phiếu bán: xoá ô các dòng BAN của phiếu (tồn KHO tự cộng lại theo công thức), trả KYGUI về như trước. */
function saleUndo_(body, dryRun) {
  const ticket = String(body.ticket_id || '').trim();
  const nguoi = String(body.nguoi || body.seller || '').trim().toLowerCase();
  const fail = msg => ({ ok: false, action: 'huy_ban', ticket_id: ticket, error: msg });
  if (!/^[A-Za-z0-9_.:\-]{1,64}$/.test(ticket)) return fail('ticket_id không hợp lệ');
  if (!nguoi) return fail('thiếu nguoi (email người dùng app)');
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    MEMO = {};
    const props = PropertiesService.getScriptProperties();
    let rec = null;
    try { rec = JSON.parse(props.getProperty('saleops_' + ticket) || 'null'); } catch (e) { rec = null; }
    if (!rec) return fail('không có phiếu ' + ticket + ' để huỷ (sai mã, quá 2 ngày, hoặc phiếu ghi trước khi có tính năng huỷ)');
    if (rec.huy) return Object.assign(fail('phiếu đã huỷ lúc ' + new Date(rec.huy).toISOString()), { da_huy: true });
    const owners = String(props.getProperty('OWNER_EMAILS') || OWNER_EMAILS_DEFAULT.join(',')).split(',').map(x => x.trim().toLowerCase()).filter(Boolean);
    const isOwner = body.chu === true && owners.indexOf(nguoi) !== -1;
    if (body.chu === true && !isOwner) return fail('chỉ Chủ được huỷ sau 10 phút');
    if (!isOwner) {
      if (rec.s !== nguoi) return fail('chỉ huỷ được phiếu của chính mình (hoặc Chủ)');
      if (Date.now() - rec.t > UNDO_SECONDS * 1000) return fail('quá 10 phút — nhờ Chủ huỷ');
    }
    // Kiểm hết trước: dòng BAN còn đúng như lúc ghi, sổ ký gửi chưa đổi
    const ban = getSheet_('BAN');
    const bh = ban.getRange(1, 1, 1, ban.getLastColumn()).getValues()[0];
    const bc = headerMap_(bh);
    const problems = [];
    rec.b.forEach(x => {
      const vals = ban.getRange(x[0], 1, 1, bh.length).getValues()[0];
      const same = String(vals[bc.product_code] || '').trim().toUpperCase() === x[1] && normSize_(vals[bc.item_size]) === x[2] &&
        Number(vals[bc.item_quantity]) === Number(x[3]) && String(vals[bc.KHO] || '').trim() === x[4];
      if (!same) problems.push('BAN dòng ' + x[0] + ' đã đổi');
    });
    let ky = null, kc = null;
    if (rec.k.length) {
      ky = getSheet_(KYGUI_TAB);
      kc = headerMap_(ky.getRange(1, 1, 1, ky.getLastColumn()).getValues()[0]);
      rec.k.forEach(x => { const cur = Number(ky.getRange(x[0], kc.so_luong + 1).getValue()) || 0; if (cur !== x[2]) problems.push('Sổ ký gửi dòng ' + x[0] + ' đã có giao dịch khác (' + cur + ', lúc bán ' + x[2] + ')'); });
    }
    if (problems.length) return Object.assign(fail('Không huỷ được, đã có thay đổi sau phiếu: ' + uniq_(problems).join('; ')), { loi: uniq_(problems) });
    const khos = uniq_(rec.b.map(x => x[4]));
    const out = { ok: true, action: 'huy_ban', ticket_id: ticket, dry_run: dryRun, so_dong: rec.b.length, kho: khos, chu: isOwner };
    if (dryRun) return out;
    rec.b.forEach(x => BAN_WRITE_COLS.forEach(n => { if (bc[n] !== undefined) ban.getRange(x[0], bc[n] + 1).clearContent(); }));
    rec.k.forEach(x => {
      if (x[3]) KYGUI_COLS.forEach(n => ky.getRange(x[0], kc[n] + 1).clearContent());
      else { ky.getRange(x[0], kc.so_luong + 1).setValue(x[1]); ky.getRange(x[0], kc.cap_nhat + 1).setValue(Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm')); }
    });
    rec.huy = Date.now();
    rec.huy_boi = nguoi;
    props.setProperty('saleops_' + ticket, JSON.stringify(rec));
    if (rec.hd) { // đã gửi tin hoá đơn MISA → báo huỷ
      const text = '❌ HUỶ phiếu ' + ticket + ' (đã gửi tin hoá đơn MISA) · ' + rec.b.length + ' dòng · ' + khos.join(', ') + ' · bởi ' + nguoi + ' — bỏ / xoá chứng từ này trên MISA nếu đã nhập.';
      misaChats_().forEach(c => { try { sendMessage_(c, text); } catch (err) { console.error(err); } });
      out.misa_huy = true;
    }
    out._ky = rec.k.length > 0;
    return out;
  } finally {
    lock.releaseLock();
  }
}

/** Xoá mã phiếu / mã đơn (theo tiền tố) cũ hơn SALE_TICKET_DAYS ngày khỏi Script Properties. */
function pruneTickets_(props, prefix) {
  const cutoff = Date.now() - SALE_TICKET_DAYS * 86400000;
  const all = props.getProperties();
  Object.keys(all).forEach(k => {
    if (k.indexOf(prefix) !== 0) return;
    try { if (JSON.parse(all[k]).t < cutoff) props.deleteProperty(k); } catch (e) { /* bỏ qua */ }
  });
}

// =====================================================================
// CỬA "KHO" CHO APP ĐIỆN THOẠI — dùng lại đúng hàm của lệnh Zalo (cùng kiểm tra, cảnh báo tồn âm)
// POST {WEBAPP_URL}?stock_key=<STOCK_KEY>
// Body: { action, ticket_id, seller (email người dùng app), dry_run?, lines:[…], from?, to?, warehouse?, location?, undo_ticket_id? }
//   nhap / tra_hang / xuat : lines [{code, size, qty, warehouse}]
//   chuyen_kho            : from, to + lines [{code, size, qty}]
//   chuyen_vi_tri         : warehouse, location (K12 / B2 / T4 / S1 / TH2) + lines [{code, size?}] (bỏ size = mọi size)
//   huy                   : undo_ticket_id = ticket_id của thao tác cần huỷ (chỉ của chính seller, ≤ 10 phút)
// Khoá riêng STOCK_KEY (không dùng chung SALE_KEY): thao tác kho quyền mạnh hơn ghi bán → khoá / đổi độc lập được.
// =====================================================================

const STOCK_ACTIONS = ['nhap', 'tra_hang', 'xuat', 'chuyen_kho', 'chuyen_vi_tri', 'huy'];
const LOCATION_RE = /^(TH|K|B|T|S)\d{1,3}[A-Z]?$/; // TH (thùng) phải khớp trước T (tủ)

function handleStockRequest_(e) {
  let out;
  let syncTabs = [];
  try {
    const props = PropertiesService.getScriptProperties();
    const key = props.getProperty('STOCK_KEY') || '';
    const others = ['WEBHOOK_KEY', 'SALE_KEY', 'WEB_NOTIFY_KEY', 'SYNC_HINT_KEY', 'EXPORT_KEY'].map(n => props.getProperty(n)).filter(Boolean);
    if (key.length < 16 || others.indexOf(key) !== -1) {
      out = { ok: false, error: 'chưa cấu hình STOCK_KEY (≥16 ký tự, khác các khoá khác) trong Script Properties' };
    } else if (e.parameter.stock_key !== key) {
      out = { ok: false, error: 'unauthorized' };
    } else {
      const body = JSON.parse((e.postData && e.postData.contents) || '{}');
      const dryRun = String(props.getProperty('DRY_RUN') || '').toLowerCase() === 'true' || body.dry_run === true;
      out = handleStock_(body, dryRun);
      syncTabs = out._sync || [];
      delete out._sync;
    }
  } catch (err) {
    console.error(err && err.stack ? err.stack : err);
    out = { ok: false, error: 'bad_request: ' + (err && err.message ? err.message : err) };
  }
  if (syncTabs.length) {
    try { queueSyncHint_(syncTabs); } catch (err) { console.error(err && err.stack ? err.stack : err); }
  }
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
}

function handleStock_(body, dryRun) {
  MEMO = {};
  CTX = { seller: '', pending: {} };
  const action = String(body.action || '').trim().toLowerCase();
  const ticket = String(body.ticket_id || '').trim();
  const seller = String(body.seller || body.nguoi || '').trim().toLowerCase().slice(0, 80);
  if (PN_ACTIONS.indexOf(action) !== -1) return handleReceipt_(action, body, dryRun);
  if (action === 'bo_sung_sp') return productFill_(body, seller, dryRun);
  if (action === 'xuat_misa') return handleMisaExport_(body, seller, dryRun);
  if (STOCK_ACTIONS.indexOf(action) === -1) return { ok: false, error: 'action phải là: ' + STOCK_ACTIONS.concat(PN_ACTIONS, ['bo_sung_sp', 'xuat_misa']).join(', ') };
  if (!/^[A-Za-z0-9_.:\-]{1,64}$/.test(ticket)) return { ok: false, action, error: 'ticket_id không hợp lệ (1-64 ký tự: chữ, số, _ . : -)' };
  if (!seller) return { ok: false, action, ticket_id: ticket, error: 'thiếu seller (email người dùng app)' };

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const props = PropertiesService.getScriptProperties();
    const ticketKey = 'stk_' + ticket;
    const prev = props.getProperty(ticketKey);
    if (prev) {
      const pv = JSON.parse(prev);
      return { ok: !pv.partial, duplicate: true, partial: !!pv.partial, action, ticket_id: ticket,
        error: pv.partial ? 'Thao tác này lần trước ghi dở — kiểm tra Sheet, KHÔNG gửi lại' : undefined };
    }
    if (action === 'huy') return stockUndo_(body, seller, ticket, dryRun, props);

    const lines = Array.isArray(body.lines) ? body.lines : [];
    if (!lines.length || lines.length > SALE_MAX_LINES) return { ok: false, action, ticket_id: ticket, error: 'lines phải có 1-' + SALE_MAX_LINES + ' dòng' };

    // Lượt 1: chạy thử mọi dòng — có dòng lỗi thì không ghi dòng nào
    const checked = lines.map((ln, i) => stockLine_(action, body, ln || {}, i, true));
    if (checked.some(r => !r.ok)) {
      return { ok: false, action, ticket_id: ticket, error: 'Có dòng lỗi, chưa ghi dòng nào', results: checked.map(r => r.result) };
    }
    if (dryRun) return { ok: true, action, ticket_id: ticket, dry_run: true, results: checked.map(r => r.result) };

    // Lượt 2: ghi thật
    MEMO = {};
    CTX = { seller: '', pending: {} };
    const ops = [];
    const results = [];
    try {
      lines.forEach((ln, i) => {
        const r = stockLine_(action, body, ln || {}, i, false);
        results.push(r.result);
        r.ops.forEach(o => ops.push(o));
      });
    } catch (err) {
      props.setProperty(ticketKey, JSON.stringify({ t: Date.now(), partial: true }));
      return { ok: false, partial: true, action, ticket_id: ticket, results, _sync: uniq_(ops.map(o => o.sheet)),
        error: 'Ghi dở (' + (err && err.message ? err.message : err) + ') — KHÔNG gửi lại, kiểm tra Sheet' };
    }
    props.setProperty(ticketKey, JSON.stringify({ t: Date.now(), rows: ops.length }));
    pruneTickets_(props, 'stk_');
    CacheService.getScriptCache().put('stkops_' + ticket, JSON.stringify({ seller, label: action + ' ' + ticket, ops }), UNDO_SECONDS);
    return { ok: true, action, ticket_id: ticket, dry_run: false, results,
      undo_until: new Date(Date.now() + UNDO_SECONDS * 1000).toISOString(), _sync: uniq_(ops.map(o => o.sheet)) };
  } finally {
    lock.releaseLock();
  }
}

/** Mã có trong SANPHAM (tên cột hàng 1 hoặc 2) hoặc trong tab KHO. */
function knownProductCode_(code) {
  if (!MEMO.__spCodes) {
    const sp = sheetValues_('SANPHAM');
    let hr = 0;
    for (let r = 0; r < Math.min(2, sp.length); r++) if (sp[r].map(h => String(h).trim()).indexOf('product_code') !== -1) { hr = r; break; }
    const ci = headerMap_(sp[hr]).product_code;
    MEMO.__spCodes = new Set(sp.slice(hr + 1).map(r => String(r[ci] || '').trim().toUpperCase()).filter(Boolean));
  }
  return MEMO.__spCodes.has(code) || codeExists_(code) || !!(CTX.newCodes && CTX.newCodes.has(code));
}

/** 1 dòng thao tác kho → { ok, ops, result } (result trả cho app). */
function stockLine_(action, body, ln, i, dry) {
  const code = String(ln.code || '').trim().toUpperCase();
  const size = normSize_(ln.size === undefined || ln.size === null ? '' : ln.size);
  const qty = ln.qty === undefined || ln.qty === null || ln.qty === '' ? 1 : Number(ln.qty);
  const res = { line: i + 1, code, size, qty };
  const fail = msg => ({ ok: false, ops: [], result: Object.assign(res, { ok: false, error: msg }) });
  const clean = t => String(t || '').split('\n')[0].replace(/^[^\wÀ-ỹ]+/, '').trim();

  if (!/^[A-Z0-9]{2,20}$/.test(code)) return fail('mã không hợp lệ');
  if (!knownProductCode_(code)) return fail('mã không có trong SANPHAM / KHO');
  if (size && !/^\d{2}$/.test(size)) return fail('size không hợp lệ');
  if (action !== 'chuyen_vi_tri' && (!Number.isInteger(qty) || qty < 1 || qty > 99)) return fail('qty phải là số nguyên 1-99');
  const p = { code, sizes: size ? [{ size, qty }] : [], qty: size ? 0 : qty, color: '', price: '', sizeErrors: [],
    returnGoods: action === 'tra_hang', kho: '', location: '', owner: ln.chu_hang || '' };
  const done = r => (r.ok
    ? { ok: true, ops: r.ops || [], result: Object.assign(res, { ok: true, warnings: (r.warnings || []).map(clean), rows: (r.ops || []).map(o => o.sheet + '!' + o.row) }) }
    : fail(clean(r.text)));

  if (action === 'nhap' || action === 'tra_hang' || action === 'xuat') {
    const kho = KHO_ALIASES[String(ln.warehouse || body.warehouse || '').trim().toUpperCase()];
    if (!kho) return fail('warehouse phải là 15E hoặc Y3C');
    res.warehouse = kho;
    const mv = doMovement_(p, action === 'xuat' ? ACTIONS.OUT : ACTIONS.IN, kho, dry);
    if (mv.kygui && mv.kygui.length) res.ky_gui = mv.kygui;
    if (action === 'tra_hang') res.chu_hang = mv.kygui && mv.kygui.length ? mv.kygui[0].chu_hang : kho;
    return done(mv);
  }
  if (action === 'chuyen_kho') {
    const from = KHO_ALIASES[String(ln.from || body.from || '').trim().toUpperCase()];
    const to = KHO_ALIASES[String(ln.to || body.to || '').trim().toUpperCase()];
    if (!from || !to || from === to) return fail('from / to phải là 2 kho khác nhau (15E, Y3C)');
    res.from = from;
    res.to = to;
    const out = doMovement_(p, ACTIONS.OUT, from, dry);
    if (!out.ok) return fail(clean(out.text));
    const inn = doMovement_(p, ACTIONS.IN, to, dry);
    if (!inn.ok) return fail(clean(inn.text));
    const ky = transferKygui_(p, from, to, dry);
    res.ky_gui = ky.notes;
    return done({ ok: true, ops: (out.ops || []).concat(inn.ops || [], ky.ops), warnings: (out.warnings || []).concat(inn.warnings || []) });
  }
  // chuyen_vi_tri
  const kho = KHO_ALIASES[String(ln.warehouse || body.warehouse || '').trim().toUpperCase()];
  const location = String(ln.location || body.location || '').trim().toUpperCase();
  if (!kho) return fail('warehouse phải là 15E hoặc Y3C');
  if (!LOCATION_RE.test(location)) return fail('vị trí phải dạng K12, B2, T4, S1, TH2 (K kệ, B bàn, T tủ, S sọc, TH thùng)');
  res.warehouse = kho;
  res.location = location;
  p.kho = kho;
  p.location = location;
  p.sizes = size ? [{ size, qty: 1 }] : [];
  return done(doMoveLocation_(p, dry));
}

/** Huỷ thao tác app của chính seller trong ≤ 10 phút (kiểm lại từng dòng như lệnh "huy"). */
function stockUndo_(body, seller, ticket, dryRun, props) {
  const target = String(body.undo_ticket_id || '').trim();
  if (!target) return { ok: false, action: 'huy', ticket_id: ticket, error: 'thiếu undo_ticket_id' };
  const cache = CacheService.getScriptCache();
  const raw = cache.get('stkops_' + target);
  if (!raw) return { ok: false, action: 'huy', ticket_id: ticket, undo_ticket_id: target, error: 'không có thao tác để huỷ (quá 10 phút, đã huỷ, hoặc sai mã)' };
  const rec = JSON.parse(raw);
  if (rec.seller !== seller) return { ok: false, action: 'huy', ticket_id: ticket, undo_ticket_id: target, error: 'chỉ huỷ được thao tác của chính mình' };
  const r = undoRecord_(rec, dryRun);
  if (r.ok && !dryRun) {
    cache.remove('stkops_' + target);
    props.setProperty('stk_' + ticket, JSON.stringify({ t: Date.now(), undo: target }));
  }
  return { ok: r.ok, action: 'huy', ticket_id: ticket, undo_ticket_id: target, dry_run: dryRun,
    error: r.ok ? undefined : 'Không huỷ được vì dữ liệu đã thay đổi: ' + (r.problems || []).join('; '), _sync: r.touched || [] };
}

// =====================================================================
// NHẬP TỪ PHIẾU NHÀ CUNG CẤP — đọc phiếu → nháp → (app chia size) → ghi NHAP
// Gửi ảnh: web /admin + app (cửa kho, action doc_phieu); KHÔNG nhận ảnh qua Zalo (anh Kha 16/10), Zalo chỉ báo "có phiếu chờ chia".
// Gemini 1 lượt / phiếu. Mã mới (chưa có SANPHAM): xác nhận kèm ma_moi → tạo dòng SANPHAM tối thiểu + dòng 2 kho rồi ghi NHAP (V2 16/10).
// Phiếu lưu Drive riêng tư "Phiếu mua hàng" (theo ID, kéo thư mục vẫn chạy): chưa chia kho → "Chưa chia/<NCC>/";
// xác nhận xong → "<hộ>/<NCC>/" (Hải Nancy = 15E, Yen Leather = Y3C; chia cả 2 kho thì mỗi hộ 1 bản). Chỉ mục: Script Properties pnx_<mã>.
// Giá nhập / NCC chỉ HNC giữ: API trả cho web KHÔNG có đơn giá. Riêng Chủ: xem_nhap kem_gia: true + nguoi thuộc OWNER_EMAILS thì trả don_gia.
// =====================================================================

const PN_ACTIONS = ['doc_phieu', 'ds_nhap', 'xem_nhap', 'xac_nhan', 'huy_nhap', 'bo_nhap'];
const PN_FOLDER_DEFAULT = '1uE5qpQLtXPYiHpRlpRsNVv8ddT0pyTrD'; // My Drive/HNC/Thue/2026/Phiếu mua hàng (theo ID), đổi bằng PN_FOLDER_ID
const PN_UNSPLIT = 'Chưa chia';
// Email Chủ được xem giá nhập (xem_nhap kem_gia); đổi bằng Script Property OWNER_EMAILS (cách nhau dấu phẩy)
const OWNER_EMAILS_DEFAULT = ['ltckha@gmail.com', 'giayhainancy@gmail.com'];
const PN_REASONS = { thieu: 'Thiếu so phiếu', du: 'Dư so phiếu', loi_tra_lai: 'Hàng lỗi trả lại', khac: 'Khác' };
const PN_STATUS_LABEL = { nhap: 'cho_chia', da_ghi: 'da_ghi', huy: 'huy' };
const GEMINI_SHARED_HASH = '8412f316'; // khoá Gemini chung cũ của các repo (checkConfig cảnh báo nếu bot còn dùng)
const RECEIPT_MODELS = ['gemini-2.5-flash', 'gemini-3.6-flash', 'gemini-3.8-flash'];
// Mã "cần bổ sung" (anh Kha 16/10): SANPHAM trống Tên Ngành Hàng hoặc giá bán → xuất sàn / MISA / mark_exported bỏ qua, web ẩn.
const PN_NEED_INFO_COLS = ['Tên Ngành Hàng', 'product_price'];
// Cột thông tin mẫu: chép từ mẫu cùng mã cha khi tạo mã mới; form "Bổ sung thông tin" (bo_sung_sp) chỉ được ghi các cột này + product_price
const PN_INFO_COLS = ['Tên Ngành Hàng', 'Đặc điểm', 'Chất liệu', 'Nhấn mạnh', 'Chất liệu quai:', 'Chất liệu đế:', 'Lót trong:', 'Mặt lót đế:',
  'Dáng giày mũi:', 'Phần dưới giày:', 'Kết hợp trang phục:', 'Sử dụng:', 'Bonus:'];
// Cột công thức phụ thuộc ngành: ngành trống thì để trống (tránh "female" / #N/A), có ngành thì chép lại công thức
const PN_NGANH_FORMULA_COLS = ['Giới tính', 'product_category_id'];

function handleReceipt_(action, body, dryRun) {
  MEMO = {};
  const nguoi = String(body.nguoi || body.seller || '').trim().toLowerCase().slice(0, 80);
  if (action === 'ds_nhap') return receiptList_(body);
  if (action === 'xem_nhap') return receiptView_(body);
  if (!nguoi) return { ok: false, action, error: 'thiếu nguoi (email người dùng app)' };
  if (action === 'doc_phieu') {
    const b64 = String(body.anh_base64 || '').replace(/^data:[^,]+,/, '');
    if (!b64) return { ok: false, action, error: 'thiếu anh_base64' };
    const bytes = Utilities.base64Decode(b64);
    if (bytes.length > 8 * 1024 * 1024) return { ok: false, action, error: 'ảnh quá lớn (> 8 MB), hãy nén trước' };
    if (dryRun) return { ok: true, action, dry_run: true, note: 'chạy thử: đã nhận ảnh ' + bytes.length + ' byte, chưa đọc phiếu' };
    let r;
    try { r = receiptCreate_(bytes, String(body.mime || 'image/jpeg'), String(body.nguon || 'app'), nguoi); }
    catch (err) { return { ok: false, action, error: err && err.message ? err.message : String(err) }; }
    receiptNotify_(r);
    return Object.assign({ action }, r);
  }
  if (action === 'bo_nhap') return receiptDiscard_(body, nguoi);
  if (action === 'huy_nhap') return receiptUndo_(body, nguoi, dryRun);
  return receiptConfirm_(body, nguoi, dryRun);
}

function receiptAppLink_(id) {
  const props = PropertiesService.getScriptProperties();
  let base = props.getProperty('APP_URL') || '';
  if (!base) {
    const m = String(props.getProperty('SYNC_HINT_URL') || '').match(/^(https?:\/\/[^/]+)/);
    base = m ? m[1] + '/admin/app' : '/admin/app';
  }
  return base + '#phieu-' + id;
}

/** Câu lệnh cho Gemini đọc phiếu xuất kho NCC (phiếu in hoặc viết tay). */
function receiptPrompt_(suppliers) {
  return [
    'Đây là ảnh phiếu xuất kho / phiếu giao hàng của nhà cung cấp giày dép cho Hiệu giày Hải Nancy (phiếu in hoặc viết tay).',
    'Đọc và trả về JSON đúng dạng: {"ncc": "", "so_phieu": "", "ngay": "yyyy-mm-dd", "dong": [{"ma_ncc": "", "mo_ta": "", "sl": 0, "don_gia": 0}], "tong_sl": 0, "tong_tien": 0}.',
    '- ncc: tên nhà cung cấp; nếu giống một tên trong danh sách sau thì dùng ĐÚNG tên đó: ' + suppliers.join(', ') + '.',
    '- so_phieu: số phiếu / số chứng từ in trên phiếu (vd PX2898); không có thì "".',
    '- dong: mỗi dòng hàng 1 phần tử. ma_ncc = mã hàng của nhà cung cấp nếu có (vd 32837), mo_ta = tên / mô tả hàng như ghi trên phiếu,',
    '  sl = tổng số lượng (đôi / cái) của dòng, don_gia = đơn giá 1 đôi (số nguyên VND, bỏ dấu chấm). Bỏ dòng tổng cộng, công nợ, chữ ký.',
    '- Không đoán: chữ không đọc được thì để "" hoặc 0. Chỉ trả JSON, không giải thích.',
  ].join('\n');
}

function receiptGemini_(bytes, mime) {
  const key = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  if (!key) throw new Error('chưa cấu hình GEMINI_API_KEY trong Script Properties');
  const payload = { contents: [{ parts: [{ inline_data: { mime_type: mime, data: Utilities.base64Encode(bytes) } },
    { text: receiptPrompt_(Object.keys(supplierInfo_())) }] }], generationConfig: { temperature: 0.1, responseMimeType: 'application/json' } };
  // Khoá miễn phí: 2.5 Flash nhiều lượt nhất → thử trước; lỗi / hết lượt thì lùi sang bản mới hơn (anh Kha 16/10)
  let last = '';
  let quota = 0;
  for (const model of RECEIPT_MODELS) {
    const res = UrlFetchApp.fetch('https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent?key=' + encodeURIComponent(key),
      { method: 'post', contentType: 'application/json', payload: JSON.stringify(payload), muteHttpExceptions: true });
    if (res.getResponseCode() === 429) { quota++; last = model + ' hết lượt'; continue; }
    if (res.getResponseCode() !== 200) { last = model + ' HTTP ' + res.getResponseCode(); continue; }
    try {
      const txt = JSON.parse(res.getContentText()).candidates[0].content.parts[0].text.trim().replace(/^```(?:json)?\s*|\s*```$/g, '');
      let ans = JSON.parse(txt);
      if (Array.isArray(ans)) ans = ans.find(x => x && typeof x === 'object') || {};
      return { model, data: ans };
    } catch (e) { last = model + ': ' + e.message; }
  }
  if (quota === RECEIPT_MODELS.length) throw new Error('Gemini hết lượt miễn phí (mọi model báo 429) — thử lại sau ít phút, hoặc ngày mai nếu hết lượt trong ngày');
  throw new Error('Gemini không đọc được phiếu (' + last + ')');
}

/** Ghép tên NCC đọc được với tên trong SUB (bỏ dấu; trùng, chứa nhau, hoặc khớp tên pháp lý). */
function matchSupplier_(raw) {
  const n = norm_(raw).replace(/\s+/g, ' ').trim();
  if (!n) return '';
  const info = supplierInfo_();
  const names = Object.keys(info);
  return names.find(x => norm_(x) === n) ||
    names.find(x => { const k = norm_(x); return k && (n.indexOf(k) !== -1 || k.indexOf(n) !== -1); }) ||
    names.find(x => info[x].legal && norm_(info[x].legal).indexOf(n) !== -1) || '';
}

function receiptRoot_() {
  return DriveApp.getFolderById(PropertiesService.getScriptProperties().getProperty('PN_FOLDER_ID') || PN_FOLDER_DEFAULT);
}

/** Thư mục con theo đường (tạo nếu chưa có), vd ["Chưa chia", "Tuấn Phong"]. */
function receiptSubfolder_(names) {
  let f = receiptRoot_();
  names.forEach(n => { const it = f.getFoldersByName(n); f = it.hasNext() ? it.next() : f.createFolder(n); });
  return f;
}

/** Xác nhận xong: chuyển ảnh + dữ liệu phiếu sang "<hộ>/<NCC>/" theo kho đã chia (2 kho → bản sao ảnh cho hộ thứ 2). */
function receiptFileByHousehold_(d, khos) {
  const ix = receiptIndex_(d.id);
  const ncc = d.ncc || 'Chưa rõ NCC';
  const list = uniq_(khos.filter(k => INVOICE_HKD_FOLDERS[k]));
  if (!ix || !list.length) return;
  const first = receiptSubfolder_([INVOICE_HKD_FOLDERS[list[0]], ncc]);
  const img = DriveApp.getFileById(ix.img);
  img.moveTo(first);
  DriveApp.getFileById(ix.f).moveTo(first);
  list.slice(1).forEach(k => img.makeCopy(img.getName(), receiptSubfolder_([INVOICE_HKD_FOLDERS[k], ncc])));
}

function receiptIndex_(id) {
  if (!id || String(id).indexOf('PN') !== 0) return null;
  if (!MEMO.__pnx) MEMO.__pnx = {};
  if (MEMO.__pnx[id] === undefined) {
    let v = null;
    try { v = JSON.parse(PropertiesService.getScriptProperties().getProperty('pnx_' + id) || 'null'); } catch (e) { v = null; }
    MEMO.__pnx[id] = v;
  }
  return MEMO.__pnx[id];
}

function receiptLoad_(id) {
  const ix = receiptIndex_(id);
  return ix ? JSON.parse(DriveApp.getFileById(ix.f).getBlob().getDataAsString()) : null;
}

function receiptSave_(d) {
  const ix = receiptIndex_(d.id);
  DriveApp.getFileById(ix.f).setContent(JSON.stringify(d, null, 1));
  const nx = Object.assign({}, ix, { ncc: d.ncc, so: d.so_phieu, ngay: d.ngay, nd: d.dong.length, sl: d.tong_sl, st: d.trang_thai,
    nk: d.xac_nhan && d.xac_nhan.so_ct ? d.xac_nhan.so_ct : undefined });
  PropertiesService.getScriptProperties().setProperty('pnx_' + d.id, JSON.stringify(nx));
  MEMO.__pnx[d.id] = nx;
  delete MEMO.__pnByNk;
}

function receiptCreate_(bytes, mime, nguon, nguoi) {
  const r = receiptGemini_(bytes, mime);
  const a = r.data || {};
  const dong = (Array.isArray(a.dong) ? a.dong : []).map(x => ({
    ma_ncc: String(x.ma_ncc || '').trim(), mo_ta: String(x.mo_ta || '').trim(),
    sl: Math.max(0, Math.round(Number(x.sl) || 0)), don_gia: Math.max(0, Math.round(moneyValue_(x.don_gia))),
  })).filter(x => x.ma_ncc || x.mo_ta || x.sl).map((x, i) => Object.assign({ dong: i + 1 }, x));
  const ncc = matchSupplier_(a.ncc);
  const ngay = /^\d{4}-\d{2}-\d{2}$/.test(String(a.ngay || '')) ? String(a.ngay) : '';
  const id = 'PN' + Utilities.formatDate(new Date(), TZ, 'yyMMdd') + '-' + Math.random().toString(36).slice(2, 6).toUpperCase();
  const d = { id, tao_luc: new Date().toISOString(), nguon, nguoi_gui: nguoi, model: r.model,
    ncc, ncc_doc_duoc: String(a.ncc || '').trim(), so_phieu: String(a.so_phieu || '').trim(), ngay,
    dong, tong_sl: dong.reduce((t, x) => t + x.sl, 0), tong_tien_phieu: Math.round(moneyValue_(a.tong_tien)), trang_thai: 'nhap' };
  const sf = receiptSubfolder_([PN_UNSPLIT, ncc || 'Chưa rõ NCC']);
  const ext = /png/.test(mime) ? 'png' : /webp/.test(mime) ? 'webp' : 'jpg';
  const img = sf.createFile(Utilities.newBlob(bytes, mime, id + '.' + ext));
  const json = sf.createFile(Utilities.newBlob(JSON.stringify(d, null, 1), 'application/json', id + '.json'));
  const ix = { f: json.getId(), img: img.getId(), ncc, so: d.so_phieu, ngay, nd: dong.length, sl: d.tong_sl, st: 'nhap', t: Date.now() };
  PropertiesService.getScriptProperties().setProperty('pnx_' + id, JSON.stringify(ix));
  if (!MEMO.__pnx) MEMO.__pnx = {};
  MEMO.__pnx[id] = ix;
  return { ok: true, id, ncc_ten: ncc || d.ncc_doc_duoc, so_phieu: d.so_phieu, ngay, so_dong: dong.length, so_doi: d.tong_sl, trang_thai: 'cho_chia', model: r.model };
}

/** Zalo chỉ báo tin: nhắn anh "có phiếu chờ chia" + link mở app (không nhận ảnh qua Zalo). */
function receiptNotify_(r) {
  const owner = PropertiesService.getScriptProperties().getProperty('OWNER_CHAT_ID');
  if (!owner || !r || !r.ok) return;
  try {
    sendMessage_(owner, '📄 Có phiếu chờ chia: ' + (r.ncc_ten || 'chưa rõ NCC') + (r.so_phieu ? ' ' + r.so_phieu : '') + ' · ' + r.so_dong + ' dòng · ' +
      r.so_doi + ' đôi → ' + receiptAppLink_(r.id));
  } catch (err) { console.error('Không báo được phiếu mới: ' + (err && err.message ? err.message : err)); }
}

function receiptList_(body) {
  const all = PropertiesService.getScriptProperties().getProperties();
  const rows = Object.keys(all).filter(k => k.indexOf('pnx_') === 0).map(k => {
    let v = {};
    try { v = JSON.parse(all[k]); } catch (e) { /* bỏ qua */ }
    return { id: k.slice(4), ncc_ten: v.ncc || '', so_phieu: v.so || '', ngay: v.ngay || '', so_dong: v.nd || 0, so_doi: v.sl || 0,
      trang_thai: PN_STATUS_LABEL[v.st] || v.st || '', _t: v.t || 0 };
  }).filter(r => body.tat_ca === true || r.trang_thai !== 'huy').sort((a, b) => b._t - a._t).slice(0, Number(body.limit) || 50);
  rows.forEach(r => delete r._t);
  return { ok: true, action: 'ds_nhap', phieu: rows };
}

/** Gợi ý mã HNC theo bảng học dần (mỗi NCC: mã NCC / mô tả → mã HNC đã xác nhận trước đó). */
function receiptMapKey_(line) { return norm_(line.ma_ncc || line.mo_ta).replace(/[^a-z0-9]+/g, ' ').trim(); }
function receiptMapProp_(ncc) { return 'pnmap_' + norm_(ncc).replace(/[^a-z0-9]/g, ''); }
function receiptMap_(ncc) {
  try { return JSON.parse(PropertiesService.getScriptProperties().getProperty(receiptMapProp_(ncc)) || '{}'); } catch (e) { return {}; }
}

function receiptView_(body) {
  const id = String(body.id || '').trim();
  const d = receiptLoad_(id);
  if (!d) return { ok: false, action: 'xem_nhap', error: 'không có phiếu ' + id };
  const map = receiptMap_(d.ncc);
  const owners = String(PropertiesService.getScriptProperties().getProperty('OWNER_EMAILS') || OWNER_EMAILS_DEFAULT.join(','))
    .split(',').map(x => x.trim().toLowerCase()).filter(Boolean);
  const withPrice = body.kem_gia === true && owners.indexOf(String(body.nguoi || body.seller || '').trim().toLowerCase()) !== -1;
  const out = { ok: true, action: 'xem_nhap', id: d.id, ncc_ten: d.ncc || d.ncc_doc_duoc, so_phieu: d.so_phieu, ngay: d.ngay,
    so_dong: d.dong.length, so_doi: d.tong_sl, trang_thai: PN_STATUS_LABEL[d.trang_thai] || d.trang_thai,
    dong: d.dong.map(x => Object.assign({ dong: x.dong, ma_ncc: x.ma_ncc, mo_ta: x.mo_ta, sl_phieu: x.sl },
      map[receiptMapKey_(x)] ? { goi_y_ma_hnc: map[receiptMapKey_(x)] } : {}, withPrice ? { don_gia: x.don_gia } : {})) };
  if (body.kem_gia === true && !withPrice) out.canh_bao = ['không phải Chủ → không trả giá nhập'];
  if (d.xac_nhan) out.da_ghi = { luc: d.xac_nhan.luc, nguoi: d.xac_nhan.nguoi, ticket_id: d.xac_nhan.ticket_id };
  if (body.kem_anh === true) {
    const blob = DriveApp.getFileById(receiptIndex_(id).img).getBlob();
    out.anh_mime = blob.getContentType();
    out.anh_base64 = Utilities.base64Encode(blob.getBytes());
  }
  return out;
}

function receiptDiscard_(body, nguoi) {
  const d = receiptLoad_(String(body.id || '').trim());
  if (!d) return { ok: false, action: 'bo_nhap', error: 'không có phiếu ' + body.id };
  if (d.trang_thai !== 'nhap') return { ok: false, action: 'bo_nhap', id: d.id, error: 'phiếu đã ' + (d.trang_thai === 'da_ghi' ? 'ghi' : 'bỏ') + ', không bỏ được' };
  d.trang_thai = 'huy';
  d.bo = { luc: new Date().toISOString(), nguoi };
  receiptSave_(d);
  return { ok: true, action: 'bo_nhap', id: d.id, trang_thai: 'huy' };
}

/**
 * Xác nhận phiếu → ghi NHAP bằng đúng hàm nhập sẵn có.
 *   dong   [{dong, ma_hnc, kho, sizes:{"39":2}, sl?, ly_do?, ghi_chu?}] — 1 dòng phiếu được nhiều phần tử (tách màu × kho)
 *   ma_moi [{ma_hnc, ma_goc?, mau, day_size?:["38",…], ten_tam?, nganh?}] — mã chưa có SANPHAM: tạo dòng SANPHAM tối thiểu
 *          + dòng KHO 2 kho cho dãy size, rồi mới ghi NHAP. Mã có rồi mà thiếu dòng KHO (kho × size) cũng tạo dòng KHO.
 */
function receiptConfirm_(body, nguoi, dryRun) {
  const id = String(body.id || '').trim();
  const ticket = String(body.ticket_id || '').trim();
  if (!/^[A-Za-z0-9_.:\-]{1,64}$/.test(ticket)) return { ok: false, action: 'xac_nhan', error: 'ticket_id không hợp lệ' };
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const props = PropertiesService.getScriptProperties();
    if (props.getProperty('stk_' + ticket)) return { ok: true, duplicate: true, action: 'xac_nhan', id, ticket_id: ticket };
    const d = receiptLoad_(id);
    if (!d) return { ok: false, action: 'xac_nhan', ticket_id: ticket, error: 'không có phiếu ' + id };
    if (d.trang_thai !== 'nhap') return { ok: false, action: 'xac_nhan', id, ticket_id: ticket, error: 'phiếu đã ' + (d.trang_thai === 'da_ghi' ? 'ghi' : 'bỏ') };
    const input = Array.isArray(body.dong) ? body.dong : [];
    if (!input.length) return { ok: false, action: 'xac_nhan', id, ticket_id: ticket, error: 'thiếu dong' };

    // Kiểm từng dòng phiếu: tổng chia (mọi mã, mọi kho, mọi size) khớp SL phiếu; lệch thì bắt buộc lý do
    const byLine = {};
    input.forEach(x => { const k = Number(x.dong) || 0; (byLine[k] = byLine[k] || []).push(x); });
    const lineErrors = [];
    const canhBao = [];
    const lines = [];
    d.dong.forEach(pl => {
      const parts = byLine[pl.dong] || [];
      let total = 0;
      parts.forEach(x => {
        const sizes = Object.assign({}, x.sizes && typeof x.sizes === 'object' ? x.sizes : {});
        if (!Object.keys(sizes).length && Number(x.sl) > 0) sizes[''] = Number(x.sl);
        Object.keys(sizes).forEach(sz => {
          const q = Number(sizes[sz]) || 0;
          if (q <= 0) return;
          total += q;
          lines.push({ src: pl.dong, code: String(x.ma_hnc || '').trim().toUpperCase(), size: sz === '_' ? '' : sz, qty: q, warehouse: x.kho });
        });
      });
      const reason = (parts.find(x => x.ly_do) || {}).ly_do || '';
      if (total !== pl.sl) {
        if (!reason) lineErrors.push({ dong: pl.dong, error: 'đã chia ' + total + ' / ' + pl.sl + ' — cần chọn lý do (thieu / du / loi_tra_lai / khac)' });
        else if (!PN_REASONS[reason]) lineErrors.push({ dong: pl.dong, error: 'ly_do phải là: ' + Object.keys(PN_REASONS).join(', ') });
        else canhBao.push('Dòng ' + pl.dong + ': chia ' + total + ' / ' + pl.sl + ' — ' + PN_REASONS[reason]);
      }
    });
    Object.keys(byLine).forEach(k => { if (!d.dong.some(pl => pl.dong === Number(k))) lineErrors.push({ dong: Number(k), error: 'phiếu không có dòng này' }); });

    // Mã mới: kiểm trước, chưa ghi gì
    const plan = receiptNewCodesPlan_(body.ma_moi, lines, d, canhBao);
    plan.errors.forEach(e => lineErrors.push(e));
    if (lineErrors.length) return { ok: false, action: 'xac_nhan', id, ticket_id: ticket, error: 'Có dòng lỗi, chưa ghi dòng nào', loi_dong: lineErrors };
    if (!lines.length) return { ok: false, action: 'xac_nhan', id, ticket_id: ticket, error: 'không có dòng nào để ghi', canh_bao: canhBao };
    const khoRows = receiptKhoRowsPlan_(plan, lines);
    const taoMoi = { sanpham: plan.list.map(m => m.code), kho: khoRows.map(k => k.kho + ' ' + k.code + (k.size ? ' ' + k.size : '')) };
    const nk = receiptNkPlan_(uniq_(lines.map(l => KHO_ALIASES[String(l.warehouse || '').trim().toUpperCase()]).filter(Boolean)), d.ncc);

    // Lượt 1: chạy thử bằng đúng hàm "nhap" (mã mới coi như đã có)
    CTX = { seller: '', pending: {}, receiptId: d.id, newCodes: plan.codes, nk };
    const checked = lines.map((ln, i) => stockLine_('nhap', {}, ln, i, true));
    checked.forEach((r, i) => { r.result.dong_phieu = lines[i].src; });
    if (checked.some(r => !r.ok)) return { ok: false, action: 'xac_nhan', id, ticket_id: ticket, error: 'Có dòng lỗi, chưa ghi dòng nào', results: checked.map(r => r.result), canh_bao: canhBao };
    if (dryRun) return { ok: true, action: 'xac_nhan', id, ticket_id: ticket, dry_run: true, results: checked.map(r => r.result), canh_bao: canhBao, tao_moi: taoMoi, so_chung_tu: nk };

    // Lượt 2: ghi thật — SANPHAM mới → dòng KHO → NHAP
    MEMO = { __pnx: MEMO.__pnx };
    CTX = { seller: '', pending: {}, receiptId: d.id, newCodes: plan.codes, nk };
    const ops = [];
    const out = [];
    try {
      plan.list.forEach(m => ops.push(appendSanphamMin_(m)));
      khoRows.forEach(k => ops.push(appendKhoRow_(k)));
      if (ops.length) MEMO = { __pnx: MEMO.__pnx }; // đọc lại SANPHAM / KHO sau khi thêm dòng
      lines.forEach((ln, i) => {
        const r = stockLine_('nhap', {}, ln, i, false);
        r.result.dong_phieu = ln.src;
        out.push(r.result);
        r.ops.forEach(o => ops.push(o));
      });
    } catch (err) {
      props.setProperty('stk_' + ticket, JSON.stringify({ t: Date.now(), partial: true }));
      return { ok: false, partial: true, action: 'xac_nhan', id, ticket_id: ticket, results: out, _sync: uniq_(ops.map(o => o.sheet)),
        error: 'Ghi dở (' + (err && err.message ? err.message : err) + ') — KHÔNG gửi lại, kiểm tra Sheet' };
    } finally {
      CTX.receiptId = '';
      CTX.newCodes = null;
    }
    d.trang_thai = 'da_ghi';
    d.xac_nhan = { luc: new Date().toISOString(), nguoi, ticket_id: ticket, dong: input, ma_moi: plan.list, canh_bao: canhBao, so_ct: nk,
      rows: ops.map(o => o.sheet + '!' + o.row), ops }; // ops: để Chủ huỷ được sau 10 phút (huy_nhap chu:true)
    receiptSave_(d);
    try { receiptFileByHousehold_(d, lines.map(l => KHO_ALIASES[String(l.warehouse || '').trim().toUpperCase()])); }
    catch (err) { console.error('Không chuyển được ảnh phiếu sang thư mục hộ: ' + (err && err.message ? err.message : err)); }
    if (d.ncc) { // học bảng ghép mã NCC / mô tả → mã HNC (tách nhiều màu thì nhớ mã gốc)
      const map = receiptMap_(d.ncc);
      d.dong.forEach(pl => {
        const codes = uniq_(lines.filter(l => l.src === pl.dong).map(l => l.code));
        if (!codes.length || !receiptMapKey_(pl)) return;
        const nm = plan.list.find(m => codes.indexOf(m.code) !== -1);
        map[receiptMapKey_(pl)] = codes.length === 1 ? codes[0] : (nm ? nm.base : codes[0].slice(0, -1));
      });
      const txt = JSON.stringify(map);
      if (txt.length < 8500) props.setProperty(receiptMapProp_(d.ncc), txt);
    }
    props.setProperty('stk_' + ticket, JSON.stringify({ t: Date.now(), rows: ops.length }));
    pruneTickets_(props, 'stk_');
    CacheService.getScriptCache().put('stkops_' + ticket, JSON.stringify({ seller: nguoi, label: 'nhập phiếu ' + d.id, ops, pn: d.id }), UNDO_SECONDS);
    return { ok: true, action: 'xac_nhan', id, ticket_id: ticket, dry_run: false, results: out, canh_bao: canhBao, tao_moi: taoMoi, so_chung_tu: nk,
      undo_until: new Date(Date.now() + UNDO_SECONDS * 1000).toISOString(), _sync: uniq_(ops.map(o => o.sheet)) };
  } finally {
    lock.releaseLock();
  }
}

/** Kiểm danh sách mã mới → { list:[{code, base, color, sizes, name, nganh}], codes:Set, errors:[] } (chưa ghi gì). */
function receiptNewCodesPlan_(raw, lines, d, canhBao) {
  const plan = { list: [], codes: new Set(), errors: [] };
  (Array.isArray(raw) ? raw : []).forEach(m => {
    const code = String((m && m.ma_hnc) || '').trim().toUpperCase();
    const err = msg => plan.errors.push({ ma_hnc: code, error: msg });
    if (!/^[A-Z0-9]{3,20}$/.test(code)) return err('mã mới không hợp lệ (3-20 chữ / số)');
    if (plan.codes.has(code)) return err('mã mới trùng trong danh sách');
    const used = lines.filter(l => l.code === code);
    if (!used.length) return err('mã mới không có trong dòng chia nào');
    if (knownProductCode_(code)) { canhBao.push(code + ' đã có trong SANPHAM / KHO → nhập như mã cũ, không tạo mới'); return; }
    const base = String(m.ma_goc || code.slice(0, -1)).trim().toUpperCase();
    if (!base || code.indexOf(base) !== 0 || code.length <= base.length) return err('mã mới phải là mã gốc + chữ màu (vd ' + (base || '32837') + 'D)');
    const color = String(m.mau || '').trim().slice(0, 30);
    if (!color) return err('thiếu màu (mau)');
    const sizes = uniq_((Array.isArray(m.day_size) ? m.day_size : []).map(x => normSize_(x)).concat(used.map(l => normSize_(l.size))));
    if (sizes.some(x => x && !/^\d{2}$/.test(x))) return err('day_size phải là size 2 chữ số');
    const price = Math.round(moneyValue_(m.gia_ban));
    if (!(price >= 1000)) return err('thiếu giá bán (gia_ban, đồng, ≥ 1.000)');
    const nganh = String(m.nganh || '').trim();
    if (nganh && productCategories_().indexOf(nganh) === -1) return err('ngành "' + nganh + '" không có trong SUB');
    const pl = d.dong.find(x => x.dong === used[0].src) || {};
    plan.list.push({ code, base, color, sizes: sizes.sort((a, b) => sizeOrder_(a) - sizeOrder_(b)), price, cost: pl.don_gia || 0,
      name: String(m.ten_tam || pl.mo_ta || pl.ma_ncc || code).trim().slice(0, 120), nganh, ncc: d.ncc || '' });
    plan.codes.add(code);
  });
  return plan;
}

/** Dòng KHO cần thêm: mã mới → cả 2 kho × dãy size; mã có rồi → đúng kho × size đang nhập mà KHO chưa có dòng. */
function receiptKhoRowsPlan_(plan, lines) {
  const out = [];
  const seen = {};
  const add = (kho, code, size, color) => {
    const k = kho + '|' + code + '|' + size;
    if (seen[k]) return;
    seen[k] = true;
    if (!plan.codes.has(code) && findKhoRows_(kho, code, [size]).length) return;
    out.push({ kho, code, size, color });
  };
  plan.list.forEach(m => ['15E', 'Y3C'].forEach(kho => m.sizes.forEach(sz => add(kho, m.code, sz, m.color))));
  lines.forEach(l => {
    const kho = KHO_ALIASES[String(l.warehouse || '').trim().toUpperCase()];
    const size = normSize_(l.size);
    if (!kho || plan.codes.has(l.code) || !knownProductCode_(l.code)) return;
    add(kho, l.code, size, lookupColor_(l.code));
  });
  return out;
}

/**
 * Thêm 1 dòng SANPHAM tối thiểu (tiêu đề hàng 2): chép công thức của dòng cuối (mã cha, tên, mô tả…; product_name giữ công thức),
 * điền mã, màu, giá bán (app nhập), giá nhập = đơn giá phiếu, NCC, size = dãy size; cột thông tin mẫu chép từ mẫu cùng mã cha nếu có.
 * Ngành trống → Giới tính / product_category_id để trống (mã "cần bổ sung", bổ sung qua bo_sung_sp).
 */
function appendSanphamMin_(m) {
  const sheet = getSheet_('SANPHAM');
  const data = sheetValues_('SANPHAM');
  let hr = -1;
  for (let r = 0; r < Math.min(2, data.length); r++) if (data[r].map(h => String(h).trim()).indexOf('product_code') !== -1) { hr = r; break; }
  if (hr === -1) throw new Error('Tab SANPHAM không có cột product_code ở hàng 1-2');
  const col = headerMap_(data[hr]);
  requireColumns_('SANPHAM', col, ['product_code', 'product_color', 'product_price']);
  let last = data.length;
  while (last > hr + 1 && String(data[last - 1][col.product_code]).trim() === '') last--;
  const row = last + 1;
  if (row > sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(), 100);
  const ncol = data[hr].length;

  // Mẫu cùng mã cha (cùng mẫu, khác màu) → chép cột thông tin mẫu (không chép giá, ảnh, cờ đã đăng)
  const pc = col.parent_product_code;
  const sib = data.slice(hr + 1).find(r => String(r[col.product_code]).trim() &&
    ((pc !== undefined && String(r[pc]).trim().toUpperCase() === m.base) || String(r[col.product_code]).trim().toUpperCase().slice(0, -1) === m.base));
  const values = { product_code: m.code, product_color: m.color, product_price: m.price };
  PN_INFO_COLS.concat(['Thương hiệu', 'product_unit', 'product_origin']).forEach(n => {
    if (sib && col[n] !== undefined && String(sib[col[n]]).trim() !== '') values[n] = sib[col[n]];
  });
  if (m.nganh && col['Tên Ngành Hàng'] !== undefined) values['Tên Ngành Hàng'] = m.nganh;
  if (col.product_unit !== undefined && values.product_unit === undefined) values.product_unit = 'Đôi';
  if (col.product_origin !== undefined && values.product_origin === undefined) values.product_origin = 'Việt Nam'; // anh Kha 16/10
  if (col.Size !== undefined && m.sizes.some(Boolean)) values.Size = m.sizes.filter(Boolean).join(',');
  if (col.purchase_price !== undefined && m.cost) values.purchase_price = m.cost; // invoice_price để anh điền (anh Kha 16/10)
  if (col.supplier !== undefined && m.ncc) values.supplier = m.ncc;
  const hasNganh = col['Tên Ngành Hàng'] !== undefined && String(values['Tên Ngành Hàng'] || '').trim() !== '';
  if (!hasNganh) PN_NGANH_FORMULA_COLS.forEach(n => { if (col[n] !== undefined) values[n] = ''; });

  const formulas = last > hr + 1 ? sheet.getRange(last, 1, 1, ncol).getFormulasR1C1()[0] : [];
  const cols = [];
  const mem = new Array(ncol).fill('');
  for (let c = 0; c < ncol; c++) {
    const name = String(data[hr][c]).trim();
    if (formulas[c] && String(formulas[c]).charAt(0) === '=' && !(name && values[name] !== undefined)) {
      sheet.getRange(row, c + 1).setFormulaR1C1(formulas[c]);
      cols.push(c + 1);
      mem[c] = formulas[c];
    }
  }
  if (pc !== undefined && !(formulas[pc] && String(formulas[pc]).charAt(0) === '=')) values.parent_product_code = m.base;
  Object.keys(values).forEach(n => {
    if (values[n] !== '') sheet.getRange(row, col[n] + 1).setValue(values[n]);
    if (cols.indexOf(col[n] + 1) === -1) cols.push(col[n] + 1);
    mem[col[n]] = values[n];
  });
  while (data.length < row - 1) data.push(new Array(ncol).fill(''));
  data[row - 1] = mem; // bộ nhớ đệm: mã mới tiếp theo ghi dòng kế
  return { type: 'row', sheet: 'SANPHAM', row, hr: hr + 1, cols, check: { product_code: m.code }, guard: { code: m.code } };
}

/** Các ngành trong SUB (cột Tên Ngành Hàng). */
function productCategories_() {
  if (!MEMO.__cats) {
    const sub = sheetValues_('SUB');
    const c = headerMap_(sub[0] || []);
    MEMO.__cats = c['Tên Ngành Hàng'] === undefined ? [] : uniq_(sub.slice(1).map(r => String(r[c['Tên Ngành Hàng']] || '').trim()).filter(Boolean));
  }
  return MEMO.__cats;
}

/** Mã "cần bổ sung": dòng SANPHAM trống Tên Ngành Hàng hoặc giá bán. */
function needsInfo_(row, col) {
  return PN_NEED_INFO_COLS.some(n => col[n] !== undefined &&
    (n === 'product_price' ? !(moneyValue_(row[col[n]]) > 0) : String(row[col[n]] === undefined || row[col[n]] === null ? '' : row[col[n]]).trim() === ''));
}

/**
 * Số chứng từ NHAP cho lần xác nhận: theo từng kho, NK + 6 số (như Sheet đang dùng).
 * Cùng kho + cùng NCC + cùng ngày (hôm nay) đã có số → dùng chung; khác → số lớn nhất của kho đó + 1.
 */
function receiptNkPlan_(khos, ncc) {
  const nh = sheetValues_('NHAP');
  const col = headerMap_(nh[0]);
  requireColumns_('NHAP', col, ['Ngày chứng từ (*)', 'Số chứng từ (*)', 'product_code', 'KHO']);
  const today = Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd');
  const sup = productSuppliers_();
  const max = {}, same = {};
  for (let r = 1; r < nh.length; r++) {
    const m = String(nh[r][col['Số chứng từ (*)']] || '').trim().toUpperCase().match(/^NK(\d+)$/);
    if (!m) continue;
    const kho = KHO_ALIASES[String(nh[r][col.KHO] || '').trim().toUpperCase()];
    if (!kho) continue;
    max[kho] = Math.max(max[kho] || 0, Number(m[1]));
    if (!ncc || same[kho] || dateKey_(nh[r][col['Ngày chứng từ (*)']]) !== today) continue;
    const pnr = receiptByNhap_(kho, 'NK' + m[1]); // dòng của phiếu NCC → NCC theo phiếu, còn lại theo SANPHAM
    const rowNcc = pnr ? pnr.ncc : sup[String(nh[r][col.product_code] || '').trim().toUpperCase()];
    if (norm_(rowNcc || '') === norm_(ncc)) same[kho] = 'NK' + m[1];
  }
  const out = {};
  khos.forEach(k => { out[k] = same[k] || 'NK' + String((max[k] || 0) + 1).padStart(6, '0'); });
  return out;
}

/** product_code → supplier (SANPHAM). */
function productSuppliers_() {
  if (!MEMO.__sup) {
    const sp = sheetValues_('SANPHAM');
    let hr = 0;
    for (let r = 0; r < Math.min(2, sp.length); r++) if (sp[r].map(h => String(h).trim()).indexOf('product_code') !== -1) { hr = r; break; }
    const c = headerMap_(sp[hr]);
    MEMO.__sup = {};
    if (c.supplier !== undefined) for (let r = hr + 1; r < sp.length; r++) {
      const code = String(sp[r][c.product_code] || '').trim().toUpperCase();
      if (code) MEMO.__sup[code] = String(sp[r][c.supplier] || '').trim();
    }
  }
  return MEMO.__sup;
}

/**
 * Form "Bổ sung thông tin mã mới" (web /admin): ghi đúng các cột PN_INFO_COLS (+ product_price) của 1 mã, theo tên cột hàng 2.
 * Body: { action:"bo_sung_sp", product_code, nguoi, dry_run?, cot:{"Tên Ngành Hàng": "...", …}, product_price? }
 * Ngành phải có trong SUB. Có ngành thì chép lại công thức Giới tính / product_category_id (từ dòng gần nhất có công thức).
 */
function productFill_(body, nguoi, dryRun) {
  const code = String(body.product_code || '').trim().toUpperCase();
  const fail = msg => ({ ok: false, action: 'bo_sung_sp', product_code: code, error: msg });
  if (!nguoi) return fail('thiếu nguoi (email người dùng app)');
  if (!/^[A-Z0-9]{2,20}$/.test(code)) return fail('product_code không hợp lệ');
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    MEMO = {};
    const sheet = getSheet_('SANPHAM');
    const data = sheetValues_('SANPHAM');
    let hr = -1;
    for (let r = 0; r < Math.min(2, data.length); r++) if (data[r].map(h => String(h).trim()).indexOf('product_code') !== -1) { hr = r; break; }
    if (hr === -1) return fail('Tab SANPHAM không có cột product_code');
    const col = headerMap_(data[hr]);
    let ri = -1;
    for (let r = hr + 1; r < data.length; r++) if (String(data[r][col.product_code]).trim().toUpperCase() === code) { ri = r; break; }
    if (ri === -1) return fail('không có mã ' + code + ' trong SANPHAM');

    const cot = body.cot && typeof body.cot === 'object' ? body.cot : {};
    const errors = [], canhBao = [];
    const values = {};
    Object.keys(cot).forEach(k => {
      const name = String(k).trim();
      if (PN_INFO_COLS.indexOf(name) === -1) { errors.push('cột "' + name + '" không được sửa'); return; }
      if (col[name] === undefined) { canhBao.push('SANPHAM không có cột "' + name + '", bỏ qua'); return; }
      const v = String(cot[k] === null || cot[k] === undefined ? '' : cot[k]).replace(/\s+/g, ' ').trim();
      if (v.length > 200) { errors.push('"' + name + '" dài quá 200 ký tự'); return; }
      if (v.charAt(0) === '=') { errors.push('"' + name + '" không được bắt đầu bằng ='); return; }
      values[name] = v;
    });
    if (values['Tên Ngành Hàng'] !== undefined) {
      if (!values['Tên Ngành Hàng']) errors.push('Tên Ngành Hàng không được để trống');
      else if (productCategories_().indexOf(values['Tên Ngành Hàng']) === -1) errors.push('ngành "' + values['Tên Ngành Hàng'] + '" không có trong SUB');
    }
    if (body.product_price !== undefined && body.product_price !== null && body.product_price !== '') {
      const price = Math.round(moneyValue_(body.product_price));
      if (!(price >= 1000)) errors.push('product_price phải ≥ 1.000 đồng');
      else values.product_price = price;
    }
    if (errors.length) return Object.assign(fail('Có lỗi, chưa ghi gì'), { loi: errors });
    const names = Object.keys(values);
    if (!names.length) return fail('không có cột nào để ghi');

    // Có ngành → khôi phục công thức phụ thuộc ngành nếu ô đang không phải công thức
    const nganh = values['Tên Ngành Hàng'] !== undefined ? values['Tên Ngành Hàng'] : String(data[ri][col['Tên Ngành Hàng']] || '').trim();
    const restore = [];
    if (nganh) {
      const rowF = sheet.getRange(ri + 1, 1, 1, data[hr].length).getFormulasR1C1()[0];
      PN_NGANH_FORMULA_COLS.forEach(n => {
        if (col[n] === undefined || String(rowF[col[n]] || '').charAt(0) === '=') return;
        for (let r = ri; r > hr; r--) { // dòng gần nhất phía trên có công thức ở cột này
          const f = sheet.getRange(r, col[n] + 1).getFormulaR1C1();
          if (f && f.charAt(0) === '=') { restore.push({ name: n, f }); break; }
        }
      });
    }
    const after = data[ri].slice();
    names.forEach(n => { after[col[n]] = values[n]; });
    const result = { ok: true, action: 'bo_sung_sp', product_code: code, dry_run: dryRun, da_ghi: names.concat(restore.map(x => x.name)), canh_bao: canhBao,
      can_bo_sung: needsInfo_(after, col) };
    if (dryRun) return result;
    names.forEach(n => sheet.getRange(ri + 1, col[n] + 1).setValue(values[n]));
    restore.forEach(x => sheet.getRange(ri + 1, col[x.name] + 1).setFormulaR1C1(x.f));
    console.log('bo_sung_sp ' + code + ' bởi ' + nguoi + ': ' + result.da_ghi.join(', '));
    result._sync = ['SANPHAM'];
    return result;
  } finally {
    lock.releaseLock();
  }
}

/** Thêm 1 dòng KHO (tồn đầu 0) như HNC "Đồng bộ SKU" — công thức FSKU + tồn hiện tại dựng theo tên cột NHAP / XUAT / BAN. */
function appendKhoRow_(k) {
  const sheetName = KHO_SHEETS[k.kho];
  const sheet = getSheet_(sheetName);
  const data = sheetValues_(sheetName);
  const col = headerMap_(data[0]);
  requireColumns_(sheetName, col, ['product_code', 'product_color', 'item_size', 'opening_quantity', 'current_quantity', 'product_location', k.kho]);
  let last = data.length;
  while (last > 1 && String(data[last - 1][col.product_code]).trim() === '') last--;
  const row = last + 1;
  if (row > sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(), 100);
  const L = c => columnLetter_(col[c] + 1);
  const src = (tab, qtyCol) => {
    const h = headerMap_(sheetValues_(tab)[0]);
    requireColumns_(tab, h, ['FSKU', qtyCol]);
    const f = columnLetter_(h.FSKU + 1), q = columnLetter_(h[qtyCol] + 1);
    return 'SUMIF(' + tab + '!' + f + ':' + f + '; ' + L(k.kho) + row + '; ' + tab + '!' + q + ':' + q + ')';
  };
  const same = findKhoRows_(k.kho, k.code, null).find(r => r.product_location);
  const values = { product_code: k.code, product_color: k.color || '', item_size: sizeValue_(k.size), opening_quantity: 0,
    product_location: same ? same.product_location : '' };
  const formulas = {};
  formulas[k.kho] = '=CONCATENATE($' + L(k.kho) + '$1;' + L('product_code') + row + ';' + L('item_size') + row + ')';
  formulas.current_quantity = '=' + L('opening_quantity') + row + ' + ' + src('NHAP', 'Số lượng (*)') + ' - ' + src('XUAT', 'item_quantity') + ' - ' + src('BAN', 'item_quantity');
  // Ghi cả dòng 1 lần (chuỗi bắt đầu "=" thành công thức); dòng mới nên các cột khác vốn trống
  const arr = new Array(data[0].length).fill('');
  Object.keys(values).forEach(n => { arr[col[n]] = values[n]; });
  Object.keys(formulas).forEach(n => { arr[col[n]] = formulas[n]; });
  sheet.getRange(row, 1, 1, arr.length).setValues([arr]);
  while (data.length < row - 1) data.push(new Array(arr.length).fill(''));
  data[row - 1] = arr; // bộ nhớ đệm: dòng KHO tiếp theo ghi dòng kế, khỏi đọc lại tab
  return { type: 'row', sheet: sheetName, row, written: Object.keys(values).concat(Object.keys(formulas)),
    check: { product_code: k.code, item_size: k.size }, guard: { code: k.code, size: k.size, kho: k.kho } };
}

/**
 * Huỷ lần xác nhận phiếu (ticket_id của xac_nhan) → phiếu về "chờ chia".
 * Người ghi: ≤ 10 phút. Chủ (chu: true, web kiểm quyền, kèm id phiếu): quá 10 phút vẫn huỷ được nếu các mã chưa có giao dịch khác.
 */
function receiptUndo_(body, nguoi, dryRun) {
  const ticket = String(body.ticket_id || '').trim();
  const cache = CacheService.getScriptCache();
  const raw = cache.get('stkops_' + ticket);
  let rec = raw ? JSON.parse(raw) : null;
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    if (!rec && body.chu === true) rec = receiptUndoRecord_(String(body.id || '').trim(), ticket);
    if (!rec) return { ok: false, action: 'huy_nhap', ticket_id: ticket, error: 'không có thao tác để huỷ (quá 10 phút, đã huỷ, hoặc sai mã)' };
    if (rec.error) return { ok: false, action: 'huy_nhap', ticket_id: ticket, error: rec.error };
    if (rec.seller !== nguoi && body.chu !== true) return { ok: false, action: 'huy_nhap', ticket_id: ticket, error: 'chỉ huỷ được thao tác của chính mình' };
    const r = undoRecord_(rec, dryRun);
    if (r.ok && !dryRun) {
      cache.remove('stkops_' + ticket);
      const d = rec.pn ? receiptLoad_(rec.pn) : null;
      if (d && d.trang_thai === 'da_ghi') {
        d.trang_thai = 'nhap';
        d.lich_su_huy = (d.lich_su_huy || []).concat([{ luc: new Date().toISOString(), nguoi, chu: body.chu === true, xac_nhan: d.xac_nhan }]);
        delete d.xac_nhan;
        receiptSave_(d);
      }
    }
    return { ok: r.ok, action: 'huy_nhap', ticket_id: ticket, id: rec.pn || '', dry_run: dryRun, so_dong: rec.ops.length,
      error: r.ok ? undefined : 'Không huỷ được vì dữ liệu đã thay đổi: ' + (r.problems || []).join('; '), _sync: r.touched || [] };
  } finally {
    lock.releaseLock();
  }
}

/**
 * Bản ghi huỷ của phiếu đã ghi, lấy từ dữ liệu phiếu (Chủ huỷ sau 10 phút). Phiếu ghi trước khi lưu ops: dựng lại từ danh sách dòng
 * (xoá cả dòng vì đều là dòng bot thêm), kiểm từng dòng còn đúng mã / số chứng từ của phiếu.
 */
function receiptUndoRecord_(id, ticket) {
  const d = receiptLoad_(id);
  if (!d) return { error: 'thiếu / sai id phiếu' };
  if (d.trang_thai !== 'da_ghi' || !d.xac_nhan) return { error: 'phiếu ' + id + ' chưa ghi hoặc đã huỷ' };
  if (d.xac_nhan.ticket_id !== ticket) return { error: 'ticket_id không khớp lần ghi của phiếu ' + id };
  let ops = d.xac_nhan.ops;
  if (!ops) {
    const newCodes = (d.xac_nhan.ma_moi || []).map(m => m.code);
    const lineCodes = uniq_((d.xac_nhan.dong || []).map(x => String(x.ma_hnc || '').trim().toUpperCase()));
    const docs = [d.id].concat(Object.keys(d.xac_nhan.so_ct || {}).map(k => d.xac_nhan.so_ct[k]));
    ops = [];
    for (const ref of d.xac_nhan.rows || []) {
      const m = String(ref).match(/^([A-Z0-9]+)!(\d+)$/);
      if (!m) continue;
      const sheet = getSheet_(m[1]);
      const hr = m[1] === 'SANPHAM' ? 2 : 1;
      const header = sheet.getRange(hr, 1, 1, sheet.getLastColumn()).getValues()[0];
      const col = headerMap_(header);
      const vals = sheet.getRange(Number(m[2]), 1, 1, header.length).getValues()[0];
      const code = String(vals[col.product_code] || '').trim().toUpperCase();
      const allCols = header.map((_, i) => i + 1);
      if (m[1] === 'NHAP') {
        if (lineCodes.indexOf(code) === -1 || docs.indexOf(String(vals[col['Số chứng từ (*)']] || '').trim()) === -1) return { error: ref + ' không còn là dòng của phiếu' };
        ops.push({ type: 'row', sheet: 'NHAP', row: Number(m[2]), cols: allCols, check: { product_code: code } });
      } else if (m[1] === 'SANPHAM') {
        if (newCodes.indexOf(code) === -1) return { error: ref + ' không còn là mã mới của phiếu' };
        ops.push({ type: 'row', sheet: 'SANPHAM', row: Number(m[2]), hr: 2, cols: allCols, check: { product_code: code }, guard: { code } });
      } else if (KHO_SHEETS['15E'] === m[1] || KHO_SHEETS['Y3C'] === m[1]) {
        if (lineCodes.indexOf(code) === -1 && newCodes.indexOf(code) === -1) return { error: ref + ' không còn là dòng kho của phiếu' };
        const kho = m[1] === KHO_SHEETS['15E'] ? '15E' : 'Y3C';
        ops.push({ type: 'row', sheet: m[1], row: Number(m[2]), cols: allCols, check: { product_code: code },
          guard: { code, size: normSize_(vals[col.item_size]), kho } });
      }
    }
  }
  return { seller: d.xac_nhan.nguoi, label: 'nhập phiếu ' + d.id, ops, pn: d.id };
}

/** Dòng NHAP có Số chứng từ NK… → phiếu NCC đã ghi (theo chỉ mục pnx: nk theo kho; phiếu cũ: theo danh sách dòng). */
function receiptByNhap_(kho, so) {
  if (!MEMO.__pnByNk) {
    MEMO.__pnByNk = {};
    const all = PropertiesService.getScriptProperties().getProperties();
    Object.keys(all).filter(k => k.indexOf('pnx_') === 0).forEach(k => {
      let v = null;
      try { v = JSON.parse(all[k]); } catch (e) { return; }
      if (!v || v.st !== 'da_ghi') return;
      if (!MEMO.__pnx) MEMO.__pnx = {};
      MEMO.__pnx[k.slice(4)] = v;
      if (v.nk) Object.keys(v.nk).forEach(kh => { MEMO.__pnByNk[kh + '|' + v.nk[kh]] = v; });
    });
  }
  return (so && MEMO.__pnByNk[kho + '|' + so]) || null;
}

// =====================================================================
// TIN ZALO MISA (anh Kha "làm" 17/10): bot soạn sẵn để nhập MISA ở quầy, theo CHỦ HÀNG (tính ký gửi).
// - Đơn khách lấy hoá đơn (lay_hoa_don trong phiếu bán): gửi ngay 1 tin / hộ, đủ ô MISA.
// - Còn lại: dailyMisaSummary (trigger 21:00) gửi 1 tin tổng / hộ từ dòng BAN hôm nay, bỏ các dòng đã gửi riêng.
// Gửi tới Script Property MISA_CHAT_IDS (phẩy), mặc định OWNER_CHAT_ID. Thuế theo danh mục MISA HNC xuất: GTGT 1%, TNCN 0,5%.
// =====================================================================

const MISA_TAX_TEXT = 'Thuế: GTGT 1% · TNCN 0,5% (theo danh mục MISA)';
const SALE_CHANNEL_LABEL = { '': 'quầy', cua_hang: 'quầy', web: 'web', shopee: 'Shopee', tiktok: 'TikTok', lazada: 'Lazada', zalo: 'Zalo', facebook: 'Facebook' };

/** Kiểm trường khách / hoá đơn của phiếu bán → { hd?, khach?, thanh_toan, phi_ship } hoặc { error }. */
function misaInvoiceInput_(body) {
  const clip = (v, n) => String(v === undefined || v === null ? '' : v).replace(/\s+/g, ' ').trim().slice(0, n);
  const out = { thanh_toan: clip(body.thanh_toan, 60), phi_ship: '' };
  if (body.phi_ship !== undefined && body.phi_ship !== null && body.phi_ship !== '') {
    const f = Number(body.phi_ship);
    if (!isFinite(f) || f < 0) return { error: 'phi_ship không hợp lệ' };
    out.phi_ship = Math.round(f);
  }
  const k = body.khach && typeof body.khach === 'object' ? body.khach : {};
  out.khach = { ten: clip(k.ten, 80), sdt: clip(k.sdt, 20) };
  const h = body.lay_hoa_don;
  if (h && typeof h === 'object') {
    const hd = { ten_cty: clip(h.ten_cty, 160), mst: clip(h.mst, 20).replace(/\s/g, ''), dia_chi: clip(h.dia_chi, 200), email: clip(h.email, 100) };
    if (!hd.ten_cty && !hd.mst) return { error: 'lay_hoa_don cần ten_cty hoặc mst' };
    if (hd.mst && !/^\d{10}(-\d{3})?$|^\d{12}$/.test(hd.mst)) return { error: 'mst phải 10 số, 10 số-3 số, hoặc 12 số (CCCD)' };
    if (hd.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(hd.email)) return { error: 'email hoá đơn không hợp lệ' };
    out.hd = hd;
  }
  return out;
}

function misaChats_() {
  const p = PropertiesService.getScriptProperties();
  return String(p.getProperty('MISA_CHAT_IDS') || p.getProperty('OWNER_CHAT_ID') || '').split(',').map(x => x.trim()).filter(Boolean);
}

/** Tên hộ theo kho chủ hàng (Script Property HKD_<kho> = tên | MST | địa chỉ). */
function householdName_(kho) {
  const v = PropertiesService.getScriptProperties().getProperty('HKD_' + kho) || '';
  return (v.split('|')[0] || '').trim() || INVOICE_HKD_FOLDERS[kho] || kho;
}

/** Tên / ĐVT theo mã (SANPHAM, tên cột hàng 2). */
function productInfo_(code) {
  if (!MEMO.__pinfo) {
    MEMO.__pinfo = {};
    const sp = sheetValues_('SANPHAM');
    let hr = 0;
    for (let r = 0; r < Math.min(2, sp.length); r++) if (sp[r].map(h => String(h).trim()).indexOf('product_code') !== -1) { hr = r; break; }
    const c = headerMap_(sp[hr]);
    for (let r = hr + 1; r < sp.length; r++) {
      const k = String(sp[r][c.product_code] || '').trim().toUpperCase();
      if (k) MEMO.__pinfo[k] = { name: c.product_name !== undefined ? String(sp[r][c.product_name] || '').trim() : '', unit: c.product_unit !== undefined ? String(sp[r][c.product_unit] || '').trim() : '' };
    }
  }
  return MEMO.__pinfo[code] || { name: '', unit: '' };
}

/** 1 dòng hàng kiểu MISA: mã MISA (mã + size, như danh mục con HNC xuất) · tên · ĐVT · SL × đơn giá = thành tiền. */
function misaLine_(i, code, size, qty, price) {
  const info = productInfo_(code);
  const amount = (Number(price) || 0) * qty;
  return (i + 1) + '. ' + code + (size || '') + ' · ' + (info.name || code) + ' · ' + (info.unit || 'Đôi') + ' · ' + qty + ' × ' +
    (price === '' || price === null || price === undefined ? '(chưa có giá)' : money_(price)) + ' = ' + money_(amount);
}

/** Gửi tin hoá đơn MISA ngay (mỗi hộ chủ hàng 1 tin), ghi nhớ dòng BAN đã gửi để tin cuối ngày bỏ qua. Trả số tin đã gửi. */
function misaInvoiceSend_(ticket, channel, seller, inv, plan) {
  const byOwner = {};
  plan.forEach(x => (x.r.phan || [{ chu_hang: x.kho, qty: x.qty }]).forEach(ph => {
    (byOwner[ph.chu_hang] = byOwner[ph.chu_hang] || []).push({ code: x.code, size: x.size, qty: ph.qty, price: x.price });
  }));
  const day = Utilities.formatDate(new Date(), TZ, 'dd/MM/yyyy');
  const chats = misaChats_();
  let sent = 0;
  Object.keys(byOwner).forEach(owner => {
    const items = byOwner[owner];
    const total = items.reduce((t, it) => t + (Number(it.price) || 0) * it.qty, 0);
    const text = ['🧾 HOÁ ĐƠN MISA – ' + householdName_(owner) + ' (' + owner + ')',
      'Ngày ' + day + ' · Số CT ' + ticket + ' · Kênh ' + (SALE_CHANNEL_LABEL[channel] || channel) + ' · Người bán ' + (seller || '-'),
      'Khách: ' + ([inv.khach.ten, inv.khach.sdt].filter(Boolean).join(' · ') || '-'),
      'Công ty: ' + (inv.hd.ten_cty || '-') + ' · MST ' + (inv.hd.mst || '-'),
      'Địa chỉ: ' + (inv.hd.dia_chi || '-') + ' · Email: ' + (inv.hd.email || '-'),
    ].concat(items.map((it, i) => misaLine_(i, it.code, it.size, it.qty, it.price)), [MISA_TAX_TEXT,
      'Tổng: ' + money_(total) + ' · Thanh toán: ' + (inv.thanh_toan || '-') + ' · Ship: ' + (inv.phi_ship === '' ? '-' : money_(inv.phi_ship))]).join('\n');
    chats.forEach(c => { if (sendMessage_(c, text)) sent++; });
  });
  // dòng BAN của phiếu này → không lặp ở tin cuối ngày
  const key = 'misa_hd_' + Utilities.formatDate(new Date(), TZ, 'yyyyMMdd');
  const props = PropertiesService.getScriptProperties();
  let rows = [];
  try { rows = JSON.parse(props.getProperty(key) || '[]'); } catch (e) { rows = []; }
  plan.forEach(x => (x.r.rows || [x.r.row]).forEach(r => { if (r) rows.push(r); }));
  props.setProperty(key, JSON.stringify(uniq_(rows)));
  return sent;
}

/** Trigger 21:00: 1 tin tổng / hộ chủ hàng các dòng BAN hôm nay (bỏ dòng đã gửi riêng vì lấy hoá đơn). dryRun = chỉ ghi Nhật ký. */
function dailyMisaSummary(dryRun) {
  MEMO = {};
  dryRun = dryRun === true;
  const props = PropertiesService.getScriptProperties();
  const todayKey = Utilities.formatDate(new Date(), TZ, 'yyyyMMdd');
  let skip = [];
  try { skip = JSON.parse(props.getProperty('misa_hd_' + todayKey) || '[]'); } catch (e) { skip = []; }
  const msgs = misaSummaryMessages_(today_(), skip);
  const chats = misaChats_();
  msgs.forEach(m => { if (dryRun) console.log(m); else chats.forEach(c => sendMessage_(c, m)); });
  // dọn khoá misa_hd_ cũ hơn 7 ngày
  Object.keys(props.getProperties()).filter(k => k.indexOf('misa_hd_') === 0 && k.slice(8) < Utilities.formatDate(new Date(Date.now() - 7 * 86400000), TZ, 'yyyyMMdd'))
    .forEach(k => props.deleteProperty(k));
  return msgs;
}

/** Soạn tin tổng cuối ngày (cắt nhiều tin nếu dài). */
function misaSummaryMessages_(day, skipRows) {
  const ban = sheetValues_('BAN');
  const c = headerMap_(ban[0]);
  requireColumns_('BAN', c, ['Ngày', 'product_code', 'item_size', 'item_quantity', 'KHO', 'Giá']);
  const dayKey = Utilities.formatDate(day, TZ, 'yyyy-MM-dd');
  const owners = {};
  let skipped = 0;
  for (let r = 1; r < ban.length; r++) {
    if (dateKey_(ban[r][c['Ngày']]) !== dayKey) continue;
    const code = String(ban[r][c.product_code] || '').trim().toUpperCase();
    if (!code) continue;
    if (skipRows.indexOf(r + 1) !== -1) { skipped++; continue; }
    const kho = KHO_ALIASES[String(ban[r][c.KHO] || '').trim().toUpperCase()] || String(ban[r][c.KHO] || '');
    const owner = (c.chu_hang !== undefined && KHO_ALIASES[String(ban[r][c.chu_hang] || '').trim().toUpperCase()]) || kho;
    const ch = c.channel !== undefined ? String(ban[r][c.channel] || '').trim().toLowerCase() : '';
    (owners[owner] = owners[owner] || []).push({ code, size: normSize_(ban[r][c.item_size]), qty: Number(ban[r][c.item_quantity]) || 0,
      price: ban[r][c['Giá']] === '' ? '' : moneyValue_(ban[r][c['Giá']]), kho, ch, seller: c.seller !== undefined ? String(ban[r][c.seller] || '').trim() : '' });
  }
  const dd = Utilities.formatDate(day, TZ, 'dd/MM/yyyy');
  const out = [];
  Object.keys(owners).sort().forEach(owner => {
    const items = owners[owner];
    const total = items.reduce((t, it) => t + (Number(it.price) || 0) * it.qty, 0);
    const byCh = {};
    items.forEach(it => { const l = SALE_CHANNEL_LABEL[it.ch] || it.ch; byCh[l] = (byCh[l] || 0) + (Number(it.price) || 0) * it.qty; });
    const head = '📒 MISA CUỐI NGÀY ' + dd + ' – ' + householdName_(owner) + ' (' + owner + '): ' + items.length + ' dòng · ' + money_(total);
    const lines = items.map((it, i) => misaLine_(i, it.code, it.size, it.qty, it.price) + ' · ' + (SALE_CHANNEL_LABEL[it.ch] || it.ch) +
      (it.kho !== owner ? ' · ký gửi ở ' + it.kho : '') + (it.seller ? ' · ' + it.seller : ''));
    const tail = ['Theo kênh: ' + Object.keys(byCh).map(k => k + ' ' + money_(byCh[k])).join(' · '), MISA_TAX_TEXT];
    let cur = head;
    lines.concat(tail).forEach(l => {
      if ((cur + '\n' + l).length > 1900) { out.push(cur); cur = head + ' (tiếp)'; }
      cur += '\n' + l;
    });
    out.push(cur);
  });
  if (!out.length) out.push('📒 MISA CUỐI NGÀY ' + dd + ': không có dòng bán nào cần nhập' + (skipped ? ' (đã gửi riêng ' + skipped + ' dòng lấy hoá đơn)' : '') + '.');
  else if (skipped) out[out.length - 1] += '\n(Đã gửi riêng ' + skipped + ' dòng lấy hoá đơn, không lặp ở đây.)';
  return out;
}

// =====================================================================
// CỬA "BÁO ĐƠN WEB"
// POST {WEBAPP_URL}?notify_key=<WEB_NOTIFY_KEY>   Body JSON: { order_id, text }
// Chỉ gửi text tới OWNER_CHAT_ID. KHÔNG đọc lệnh, KHÔNG ghi Sheet. Chống trùng theo order_id.
// =====================================================================

function handleNotifyRequest_(e) {
  let out;
  try {
    const props = PropertiesService.getScriptProperties();
    const key = props.getProperty('WEB_NOTIFY_KEY') || '';
    const owner = String(props.getProperty('OWNER_CHAT_ID') || '').trim();
    if (key.length < 16 || key === props.getProperty('WEBHOOK_KEY') || key === props.getProperty('SALE_KEY')) {
      out = { ok: false, error: 'chưa cấu hình WEB_NOTIFY_KEY (≥16 ký tự, khác WEBHOOK_KEY và SALE_KEY) trong Script Properties' };
    } else if (e.parameter.notify_key !== key) {
      out = { ok: false, error: 'unauthorized' };
    } else if (!owner) {
      out = { ok: false, error: 'chưa cấu hình OWNER_CHAT_ID trong Script Properties' };
    } else {
      out = handleNotify_(JSON.parse((e.postData && e.postData.contents) || '{}'), owner, props);
    }
  } catch (err) {
    console.error(err && err.stack ? err.stack : err);
    out = { ok: false, error: 'bad_request: ' + (err && err.message ? err.message : err) };
  }
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
}

function handleNotify_(body, owner, props) {
  const orderId = String(body.order_id || '').trim();
  const text = String(body.text || '').trim();
  if (!/^[A-Za-z0-9_.:\-]{1,64}$/.test(orderId)) return { ok: false, error: 'order_id không hợp lệ (1-64 ký tự: chữ, số, _ . : -)' };
  if (!text) return { ok: false, order_id: orderId, error: 'text trống' };

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const key = 'notify_' + orderId;
    if (props.getProperty(key)) return { ok: true, duplicate: true, order_id: orderId };
    const truncated = text.length > NOTIFY_MAX_CHARS;
    const msg = truncated ? text.slice(0, NOTIFY_MAX_CHARS) + '\n…(đã cắt bớt)' : text;
    if (!sendMessage_(owner, msg)) return { ok: false, order_id: orderId, error: 'Zalo không nhận tin (xem Nhật ký thực thi)' };
    props.setProperty(key, JSON.stringify({ t: Date.now() }));
    pruneTickets_(props, 'notify_');
    return { ok: true, order_id: orderId, truncated };
  } finally {
    lock.releaseLock();
  }
}

// =====================================================================
// BÁO WEB CHÉP LẠI SHEET KHI SHEET ĐỔI
// Trigger cài đặt onEdit + onChange → ghi tên tab vào hàng chờ (CacheService).
// Mỗi phút gửi tối đa 1 lần: POST SYNC_HINT_URL, header x-sync-key: SYNC_HINT_KEY (không để khoá trong URL — lọt log), body {"tabs":[...]}.
// Web trả 202 ok · 403 sai khoá · 503 web chưa đặt khoá · 429 quá 60 lần/giờ. Lỗi chỉ ghi log, không gửi dồn lại.
// =====================================================================

const SYNC_WATCH_TABS = ['SANPHAM', 'KHO15E', 'KHOY3C', 'BAN', 'NHAP', 'XUAT', 'SUB', 'META', 'KYGUI'];
const SYNC_STOCK_TABS = ['BAN', 'NHAP', 'XUAT']; // đổi các tab này = tồn kho đổi → gửi kèm KHO15E, KHOY3C
const SYNC_MIN_INTERVAL_MS = 60 * 1000;
const SYNC_TRIGGER_HANDLERS = ['onSheetEditHint', 'onSheetChangeHint', 'flushSyncHints', 'weeklyInvoiceReminder', 'dailyMisaSummary'];

/** Trigger cài đặt onEdit (người sửa ô). */
function onSheetEditHint(e) {
  try {
    const name = e && e.range ? e.range.getSheet().getName() : '';
    if (name) queueSyncHint_([name]);
  } catch (err) { console.error(err && err.stack ? err.stack : err); }
}

/** Trigger cài đặt onChange (thêm/xoá dòng, cột, dán…). Sự kiện không có tên tab → lấy tab đang mở. */
function onSheetChangeHint(e) {
  try {
    const ss = e && e.source ? e.source : SpreadsheetApp.getActiveSpreadsheet();
    const name = ss.getActiveSheet().getName();
    if (name) queueSyncHint_([name]);
  } catch (err) { console.error(err && err.stack ? err.stack : err); }
}

/** Trigger mỗi phút: gửi phần còn trong hàng chờ. */
function flushSyncHints() {
  try { flushSyncHint_(false); } catch (err) { console.error(err && err.stack ? err.stack : err); }
}

/** Thêm tab vào hàng chờ (chỉ tab đang theo dõi) rồi gửi ngay nếu đã quá 60 giây kể từ lần gửi trước. */
function queueSyncHint_(tabs) {
  let add = tabs.filter(t => SYNC_WATCH_TABS.indexOf(t) !== -1);
  if (!add.length) return;
  if (add.some(t => SYNC_STOCK_TABS.indexOf(t) !== -1)) add = add.concat(['KHO15E', 'KHOY3C']);
  const lock = LockService.getDocumentLock() || LockService.getScriptLock();
  if (!lock.tryLock(10000)) return;
  try {
    const cache = CacheService.getScriptCache();
    const queued = JSON.parse(cache.get('sync_q') || '[]');
    cache.put('sync_q', JSON.stringify(uniq_(queued.concat(add))), 21600);
  } finally {
    lock.releaseLock();
  }
  flushSyncHint_(false);
}

/** Gửi hàng chờ nếu có và đã đủ 60 giây. Trả về { code, body }, hoặc null nếu không gửi. */
function flushSyncHint_(force) {
  const props = PropertiesService.getScriptProperties();
  const url = props.getProperty('SYNC_HINT_URL');
  const key = props.getProperty('SYNC_HINT_KEY');
  if (!url || !key) return null;
  const lock = LockService.getDocumentLock() || LockService.getScriptLock();
  if (!lock.tryLock(10000)) return null;
  let tabs;
  try {
    const cache = CacheService.getScriptCache();
    tabs = JSON.parse(cache.get('sync_q') || '[]');
    if (!tabs.length) return null;
    const last = Number(cache.get('sync_last') || 0);
    if (!force && Date.now() - last < SYNC_MIN_INTERVAL_MS) return null; // trigger mỗi phút sẽ gửi sau
    cache.put('sync_last', String(Date.now()), 21600);
    cache.remove('sync_q');
  } finally {
    lock.releaseLock();
  }
  const res = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: { 'x-sync-key': key },
    payload: JSON.stringify({ tabs: SYNC_WATCH_TABS.filter(t => tabs.indexOf(t) !== -1) }),
    muteHttpExceptions: true,
  });
  const code = res.getResponseCode();
  const body = res.getContentText();
  if (code !== 202 && code !== 200) console.error('sync-hint lỗi ' + code + ' (tabs ' + tabs.join(',') + '): ' + body.slice(0, 200));
  return { code, body };
}

/** Cài trigger onEdit + onChange + mỗi phút + nhắc hoá đơn sáng thứ Hai (chạy 1 lần; không tạo trùng nếu đã có). */
function setupChangeTrigger() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const have = ScriptApp.getProjectTriggers().map(t => t.getHandlerFunction());
  if (have.indexOf('onSheetEditHint') === -1) ScriptApp.newTrigger('onSheetEditHint').forSpreadsheet(ss).onEdit().create();
  if (have.indexOf('onSheetChangeHint') === -1) ScriptApp.newTrigger('onSheetChangeHint').forSpreadsheet(ss).onChange().create();
  if (have.indexOf('flushSyncHints') === -1) ScriptApp.newTrigger('flushSyncHints').timeBased().everyMinutes(1).create();
  if (have.indexOf('weeklyInvoiceReminder') === -1) {
    ScriptApp.newTrigger('weeklyInvoiceReminder').timeBased().onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(8).create();
  }
  if (have.indexOf('dailyMisaSummary') === -1) {
    ScriptApp.newTrigger('dailyMisaSummary').timeBased().everyDays(1).atHour(21).create(); // tin MISA cuối ngày
  }
  console.log('Trigger hiện có: ' + ScriptApp.getProjectTriggers().map(t => t.getHandlerFunction()).join(', '));
}

/** Gửi thử 1 lần báo đồng bộ tab SANPHAM ngay (bỏ qua giới hạn 60 giây) — xem mã trả về ở Nhật ký. */
function testSyncHint() {
  const cache = CacheService.getScriptCache();
  cache.put('sync_q', JSON.stringify(['SANPHAM']), 21600);
  const r = flushSyncHint_(true);
  if (!r) { console.log('Không gửi: thiếu SYNC_HINT_URL / SYNC_HINT_KEY trong Script Properties.'); return; }
  let tabs = '';
  try { tabs = JSON.stringify(JSON.parse(r.body).tabs || []); } catch (e) { /* web không trả JSON */ }
  console.log('sync-hint trả về: ' + r.code + (r.code === 202 ? ' ✅ web đã nhận' : ' ❌') + (tabs ? ' | web sẽ đọc: ' + tabs : '') +
    (r.code === 403 ? ' (sai khoá)' : r.code === 503 ? ' (web chưa đặt khoá)' : r.code === 429 ? ' (quá 60 lần/giờ)' : ''));
}

// =====================================================================
// XUẤT FILE MISA QUA BOT (web /admin/san gọi, anh Kha "làm" 17/10) — giống menu HNC mục 4 (TASK 4 danh mục, TASK 8 nhập kho).
// POST ?stock_key  { action:"xuat_misa", loai: danh_muc | nhap_kho_15e | nhap_kho_3c, nguoi, dry_run? }
// File điền vào mẫu gốc trong HNC/He_thong/HNC_Templates (sửa XML của xlsx, giữ nguyên định dạng / danh sách chọn của MISA),
// lưu HNC/He_thong/HNC_Exported_Files; ghi cờ misa_upload (SANPHAM) / misa_stock (NHAP) như menu. Bỏ mã "cần bổ sung", dòng TRA-…
// dry_run: chỉ đếm, không tạo file, không ghi cờ.
// =====================================================================

const MISA_LOAI = ['danh_muc', 'nhap_kho_15e', 'nhap_kho_3c'];
const SYSTEM_FOLDER_DEFAULT = '1rZ_ynNNKLXfviqXBlnQyMYQcJYPPeok4'; // My Drive/HNC/He_thong (theo ID; đổi bằng SYSTEM_FOLDER_ID)
const MISA_STOCK_STATUS_COLS = ['misa_stock', 'misa_stock_y3c', 'misa_stock_15e']; // như main.py STATUS_COLUMNS[8]
const MISA_CAREER_NEW = '101-Hoạt động bán buôn, bán lẻ các loại hàng hóa (trừ giá trị hàng hóa đại lý bán đúng giá hưởng hoa hồng);';
const MISA_CAREER_UPDATE = '101 - Hoạt động bán buôn, bán lẻ các loại hàng hóa (trừ giá trị hàng hóa đại lý bán đúng giá hưởng hoa hồng);';
const MISA_STOCK_KHO = { '15E': { tpl: 'tpl_misa_stock_15e.xlsx', misa: '15ETBH', out: 'MISA_STOCK_15E_' },
  '3C': { tpl: 'tpl_misa_stock_y3c.xlsx', misa: '3CTBH', out: 'MISA_STOCK_3C_' } };
const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

function handleMisaExport_(body, nguoi, dryRun) {
  const loai = String(body.loai || '').trim().toLowerCase();
  if (MISA_LOAI.indexOf(loai) === -1) return { ok: false, action: 'xuat_misa', error: 'loai phải là: ' + MISA_LOAI.join(', ') };
  if (!nguoi) return { ok: false, action: 'xuat_misa', loai, error: 'thiếu nguoi (email người dùng app)' };
  // Hộ Y3C dùng MISA riêng (chưa khai mẫu / mã kho cho HNC), kho 3C trong MISA 15E sẽ xoá (anh Kha 17/10) → tạm tắt; bật lại: Script Property MISA_3C = "1"
  if (loai === 'nhap_kho_3c' && PropertiesService.getScriptProperties().getProperty('MISA_3C') !== '1') {
    return { ok: false, action: 'xuat_misa', loai, tat: true, error: 'Chưa khai MISA của Yen Leather (Y3C) — tạm không xuất phiếu nhập kho 3C. Dòng NHAP kho Y3C để trống cờ, xuất sau.' };
  }
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    MEMO = {};
    const flags = body.ghi_co !== false; // ghi_co:false = tạo file để thử, không ghi cờ (hàm thuXuatMisa)
    const r = loai === 'danh_muc' ? misaCatalogExport_(dryRun, flags) : misaStockExport_(loai === 'nhap_kho_15e' ? '15E' : '3C', dryRun, flags);
    if (!flags) { r.khong_ghi_co = true; r._sync = []; }
    console.log('xuat_misa ' + loai + ' bởi ' + nguoi + (dryRun ? ' (chạy thử)' : '') + ': ' + r.files.map(f => f.ten + ' ' + f.so_dong).join(', '));
    return Object.assign({ ok: true, action: 'xuat_misa', loai, dry_run: dryRun }, r);
  } finally {
    lock.releaseLock();
  }
}

/** Thư mục con của HNC/He_thong theo tên (HNC_Templates, HNC_Exported_Files). */
function systemSubfolder_(name) {
  const root = DriveApp.getFolderById(PropertiesService.getScriptProperties().getProperty('SYSTEM_FOLDER_ID') || SYSTEM_FOLDER_DEFAULT);
  const it = root.getFoldersByName(name);
  if (!it.hasNext()) throw new Error('Không thấy thư mục ' + name + ' trong HNC/He_thong');
  return it.next();
}

/** Điền rows vào mẫu → lưu file xuất. dry → chỉ trả tên + số dòng. */
function misaWriteFile_(tplName, sheetName, startRow, rows, outName, dry) {
  if (dry) return { ten: outName, url: '', so_dong: rows.length };
  const it = systemSubfolder_('HNC_Templates').getFilesByName(tplName);
  if (!it.hasNext()) throw new Error('Thiếu mẫu ' + tplName + ' trong HNC_Templates');
  const blob = xlsxFill_(it.next().getBlob(), sheetName, startRow, rows).setName(outName);
  const f = systemSubfolder_('HNC_Exported_Files').createFile(blob);
  return { ten: outName, url: f.getUrl(), so_dong: rows.length };
}

function misaStamp_() { return Utilities.formatDate(new Date(), TZ, 'yyyyMMdd_HHmmss'); }
function misaNow_() { return Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm'); }

/** '38,39 40' → ['38','39','40'] (như unroll_sizes của main.py); trống → ['']. */
function unrollSizes_(v) {
  const parts = String(v === null || v === undefined ? '' : v).trim().split(/[,;\s]+/).map(x => x.trim()).filter(Boolean);
  return parts.length ? parts : [''];
}

/** '8%', '0,60%', '0.05', '0' → 0.08, 0.006, 0.05, 0 (như parse_percent_rate). */
function parsePercent_(v) {
  const raw = String(v === null || v === undefined ? '' : v).trim();
  if (!raw) return 0;
  const f = Number(raw.replace('%', '').replace(',', '.'));
  if (!isFinite(f)) return 0;
  return f > 1 || raw.indexOf('%') !== -1 ? f / 100 : f;
}

/** Ngành SUB → {cat (Mã nhóm hàng hóa), weight (Cân nặng)}. */
function subCategories_() {
  const sub = sheetValues_('SUB');
  const c = headerMap_(sub[0] || []);
  const out = {};
  for (let r = 1; r < sub.length; r++) {
    const name = c['Tên Ngành Hàng'] !== undefined ? String(sub[r][c['Tên Ngành Hàng']] || '').trim() : '';
    if (name) out[name.toLowerCase()] = { cat: c['Mã nhóm hàng hóa'] !== undefined ? String(sub[r][c['Mã nhóm hàng hóa']] || '').trim() : '',
      weight: c['Cân nặng'] !== undefined && sub[r][c['Cân nặng']] !== '' ? sub[r][c['Cân nặng']] : 1500 };
  }
  return out;
}

/** NCC SUB → {ma_dt, ten_dt, ck, vat} theo tên supplier (chữ thường). */
function subSuppliers_() {
  const sub = sheetValues_('SUB');
  const c = headerMap_(sub[0] || []);
  const out = {};
  if (c.supplier === undefined) return out;
  for (let r = 1; r < sub.length; r++) {
    const name = String(sub[r][c.supplier] || '').trim();
    if (name) out[name.toLowerCase()] = { ma_dt: c['Mã đối tượng'] !== undefined ? String(sub[r][c['Mã đối tượng']] || '').trim() : '',
      ten_dt: c['Tên đối tượng'] !== undefined ? String(sub[r][c['Tên đối tượng']] || '').trim() : '',
      ck: c['% chiết khấu'] !== undefined ? sub[r][c['% chiết khấu']] : '0', vat: c['Thuế suất'] !== undefined ? sub[r][c['Thuế suất']] : '0' };
  }
  return out;
}

/** Ghi cờ trạng thái từng dòng (row 1-based, cột 0-based). */
function misaWriteStatus_(sheetName, colIdx, statuses) {
  const sheet = getSheet_(sheetName);
  statuses.forEach(st => sheet.getRange(st.row, colIdx + 1).setValue(st.value));
}

/** Danh mục hàng hoá MISA (TASK 4): mã cha mới → tpl_misa_upload; mã cha đã lên MISA (thêm màu) → tpl_misa_update. */
function misaCatalogExport_(dry, flags) {
  const sp = sheetValues_('SANPHAM');
  let hr = 0;
  for (let r = 0; r < Math.min(2, sp.length); r++) if (sp[r].map(h => String(h).trim()).indexOf('product_code') !== -1) { hr = r; break; }
  const c = headerMap_(sp[hr]);
  requireColumns_('SANPHAM', c, ['product_code', 'misa_upload']);
  const v = (row, n) => (c[n] === undefined ? '' : row[c[n]]);
  const cats = subCategories_();
  const now = misaNow_();
  const statuses = [], canhBao = [], boQua = [], valid = [];
  const uploadedParents = {};
  for (let r = hr + 1; r < sp.length; r++) {
    const parent = String(v(sp[r], 'parent_product_code') || v(sp[r], 'Mã hàng hóa cha') || '').trim();
    if (parent && String(v(sp[r], 'misa_upload')).toLowerCase().indexOf('done') !== -1) uploadedParents[parent] = true;
  }
  for (let r = hr + 1; r < sp.length; r++) {
    const row = sp[r];
    const code = String(v(row, 'product_code') || '').trim();
    if (!code && !String(v(row, 'FSKU') || '').trim()) continue;
    if (String(v(row, 'misa_upload') || '').trim()) continue;
    if (needsInfo_(row, c)) { boQua.push(code.toUpperCase()); continue; }
    const parent = String(v(row, 'parent_product_code') || v(row, 'Mã hàng hóa cha') || '').trim();
    const name = String(v(row, 'product_name') || '').trim();
    const price = moneyValue_(v(row, 'product_price'));
    const unit = String(v(row, 'product_unit') || v(row, 'ĐVT') || '').trim();
    const nganh = String(v(row, 'Tên nhóm hàng hóa') || v(row, 'Tên Ngành Hàng') || '').trim();
    const sub = cats[nganh.toLowerCase()] || {};
    const reasons = [];
    if (!parent) reasons.push('Thiếu mã cha');
    if (!code) reasons.push('Thiếu mã SP');
    if (!name) reasons.push('Thiếu tên');
    if (!(price > 0)) reasons.push('Thiếu giá');
    if (!unit) reasons.push('Thiếu ĐVT');
    if (!sub.cat) reasons.push('Thiếu nhóm hàng');
    if (reasons.length) { statuses.push({ row: r + 1, value: reasons.join(', ') }); canhBao.push('Dòng ' + (r + 1) + ' ' + code + ': ' + reasons.join(', ')); continue; }
    statuses.push({ row: r + 1, value: 'Done - ' + now });
    valid.push({ parent, code, name, price, unit, color: String(v(row, 'product_color') || '').trim(), brand: String(v(row, 'Thương hiệu') || 'Hải Nancy').trim(),
      cat: sub.cat, weight: sub.weight, desc: String(v(row, 'product_description') || v(row, 'CON_DES') || '').trim(),
      sizes: unrollSizes_(v(row, 'Size')).filter(Boolean) });
  }
  const group = list => { const g = {}; list.forEach(x => (g[x.parent] = g[x.parent] || []).push(x)); return g; };
  const newRecs = valid.filter(x => !uploadedParents[x.parent]);
  const upRecs = valid.filter(x => uploadedParents[x.parent]);
  const stamp = misaStamp_();
  const files = [];
  if (newRecs.length) {
    const rows = [], seen = {};
    const g = group(newRecs);
    Object.keys(g).forEach(p => {
      const f = g[p][0];
      const pr = {}; pr[3] = 'Hàng hóa cha '; pr[4] = p; pr[7] = f.name; pr[8] = f.price; pr[9] = f.unit; pr[11] = 'Không'; pr[12] = f.brand;
      pr[13] = f.cat; pr[15] = f.weight; pr[19] = 1; pr[20] = 0.5; pr[22] = MISA_CAREER_NEW; pr[45] = f.desc;
      rows.push(pr);
      g[p].forEach(x => (x.sizes.length ? x.sizes : ['']).forEach(sz => {
        const sku = x.code + sz;
        if (seen[sku]) return;
        seen[sku] = true;
        const cr = {}; cr[3] = 'Hàng hóa con theo thuộc tính'; cr[4] = sku; cr[5] = sku; cr[6] = p; cr[7] = x.name; cr[8] = x.price; cr[9] = x.unit;
        const attrs = (x.color ? [['Màu sắc', x.color]] : []).concat(sz ? [['Size', sz]] : []);
        attrs.forEach((a, k) => { cr[32 + 2 * k] = a[0]; cr[33 + 2 * k] = a[1]; });
        rows.push(cr);
      }));
    });
    files.push(misaWriteFile_('tpl_misa_upload.xlsx', 'Tep nhap khau', 6, rows,
      (upRecs.length ? 'MISA_PRODUCTS_NEW_' : 'MISA_PRODUCTS_') + stamp + '.xlsx', dry));
  }
  if (upRecs.length) {
    const rows = [], seen = {};
    const g = group(upRecs);
    Object.keys(g).forEach(p => {
      const f = g[p][0];
      const pr = {}; pr[1] = p; pr[7] = f.name; pr[8] = f.cat; pr[9] = f.unit; pr[10] = f.price; pr[11] = 1; pr[12] = f.brand || 'Hải nancy';
      pr[13] = f.weight; pr[16] = 1; pr[17] = 0.5; pr[18] = MISA_CAREER_UPDATE;
      rows.push(pr);
      g[p].forEach(x => (x.sizes.length ? x.sizes : ['']).forEach(sz => {
        const sku = x.code + sz;
        if (seen[sku]) return;
        seen[sku] = true;
        const cr = {}; cr[1] = sku; cr[2] = p; cr[3] = sku;
        cr[7] = sz ? (x.color ? x.name + ' (' + x.color + '/' + sz + ')' : x.name + ' (Size ' + sz + ')') : (x.color ? x.name + ' (' + x.color + ')' : x.name);
        cr[9] = x.unit; cr[10] = x.price; cr[11] = 1; cr[16] = 1; cr[17] = 0.5; cr[18] = MISA_CAREER_UPDATE;
        const attrs = (x.color ? [['Màu sắc', x.color]] : []).concat(sz ? [['Size', sz]] : []);
        attrs.forEach((a, k) => { cr[24 + 2 * k] = a[0]; cr[25 + 2 * k] = a[1]; });
        rows.push(cr);
      }));
    });
    files.push(misaWriteFile_('tpl_misa_update.xlsx', 'Nhap_khau_cap_nhat_thong_tin', 3, rows, 'MISA_PRODUCTS_UPDATE_' + stamp + '.xlsx', dry));
  }
  if (!dry && flags !== false && statuses.length) misaWriteStatus_('SANPHAM', c.misa_upload, statuses);
  return { files, canh_bao: canhBao, bo_qua: uniq_(boQua), so_hop_le: valid.length, so_loi: canhBao.length, _sync: !dry && statuses.length ? ['SANPHAM'] : [] };
}

/** Phiếu nhập kho MISA (TASK 8) cho 1 kho: dòng NHAP chưa có cờ misa_stock. Đơn giá = invoice_price, trống thì purchase_price (anh Kha 17/10). */
function misaStockExport_(kho, dry, flags) {
  const nh = sheetValues_('NHAP');
  const c = headerMap_(nh[0]);
  const stCol = MISA_STOCK_STATUS_COLS.map(n => c[n]).find(x => x !== undefined);
  if (stCol === undefined) throw new Error('Tab NHAP thiếu cột ' + MISA_STOCK_STATUS_COLS.join(' / '));
  const sp = sheetValues_('SANPHAM');
  let hr = 0;
  for (let r = 0; r < Math.min(2, sp.length); r++) if (sp[r].map(h => String(h).trim()).indexOf('product_code') !== -1) { hr = r; break; }
  const sc = headerMap_(sp[hr]);
  const prod = {};
  for (let r = hr + 1; r < sp.length; r++) {
    const code = String(sp[r][sc.product_code] || '').trim().toUpperCase();
    if (code) prod[code] = { row: sp[r], supplier: sc.supplier !== undefined ? String(sp[r][sc.supplier] || '').trim() : '',
      unit: sc.product_unit !== undefined ? String(sp[r][sc.product_unit] || '').trim() : '',
      inv: sc.invoice_price !== undefined ? moneyValue_(sp[r][sc.invoice_price]) : 0, pur: sc.purchase_price !== undefined ? moneyValue_(sp[r][sc.purchase_price]) : 0 };
  }
  const sups = subSuppliers_();
  const now = misaNow_();
  const statuses = [], canhBao = [], boQua = [], rows = [];
  const v = (row, n) => (c[n] === undefined ? '' : row[c[n]]);
  for (let r = 1; r < nh.length; r++) {
    const row = nh[r];
    const code = String(v(row, 'product_code') || '').trim();
    if (!code && !String(v(row, 'FSKU') || '').trim()) continue;
    if (code === 'product_code') continue; // hàng 2 tiêu đề kỹ thuật
    if (String(row[stCol] || '').trim()) continue;
    const kRaw = String(v(row, 'KHO') || '').trim().toUpperCase();
    const rowKho = ['15E', '15ETBH'].indexOf(kRaw) !== -1 ? '15E' : ['Y3C', '3C', '3CTBH'].indexOf(kRaw) !== -1 ? '3C' : '';
    if (rowKho && rowKho !== kho) continue; // kho kia: để lần xuất kho đó
    const docNo = String(v(row, 'Số chứng từ (*)') || '').trim();
    if (docNo.toUpperCase().indexOf('TRA-') === 0) { if (rowKho) statuses.push({ row: r + 1, value: 'Bỏ qua - trả hàng' }); continue; }
    const p = prod[code.toUpperCase()];
    if (p && needsInfo_(p.row, sc)) { boQua.push(code.toUpperCase()); continue; }
    const size = normSize_(v(row, 'item_size'));
    const sku = code + size;
    const d = v(row, 'Ngày chứng từ (*)') || v(row, 'Ngày');
    const docDate = d instanceof Date ? Utilities.formatDate(d, TZ, 'dd/MM/yyyy') : String(d || '').trim();
    const qty = Number(String(v(row, 'Số lượng (*)') || v(row, 'item_quantity') || 0).replace(',', '.')) || 0;
    const price = p ? (p.inv > 0 ? p.inv : p.pur) : 0;
    const sup = p && p.supplier ? sups[p.supplier.toLowerCase()] : null;
    const reasons = [];
    if (!docNo) reasons.push('Thiếu số chứng từ');
    if (!(p && p.unit)) reasons.push('Thiếu ĐVT');
    if (!docDate) reasons.push('Thiếu ngày');
    if (!(qty > 0)) reasons.push('Thiếu số lượng');
    if (!(price > 0)) reasons.push('Thiếu đơn giá');
    if (!sup) reasons.push('Thiếu NCC');
    if (!rowKho) reasons.push('Thiếu kho');
    if (reasons.length) { statuses.push({ row: r + 1, value: reasons.join(', ') }); canhBao.push('Dòng ' + (r + 1) + ' ' + sku + ': ' + reasons.join(', ')); continue; }
    statuses.push({ row: r + 1, value: 'Done - ' + now });
    const amount = qty * price;
    const ckRate = parsePercent_(sup.ck);
    const ck = Math.round(amount * ckRate * 100) / 100;
    const vatRate = parsePercent_(sup.vat);
    const tax = Math.round((amount - ck) * vatRate * 100) / 100;
    const o = {};
    o[1] = 'Nhập kho mua hàng'; o[2] = docDate; o[3] = docNo; o[4] = sup.ma_dt; o[5] = sup.ten_dt;
    o[6] = sup.ten_dt ? 'Nhập kho mua hàng từ ' + sup.ten_dt : 'Nhập kho mua hàng'; o[7] = 'Chưa thanh toán'; o[8] = sku;
    o[12] = MISA_STOCK_KHO[kho].misa; o[14] = p.unit; o[15] = qty; o[16] = price; o[17] = amount; o[18] = ckRate; o[19] = ck;
    o[20] = vatRate; o[21] = tax; o[22] = amount - ck + tax;
    rows.push(o);
  }
  const files = rows.length ? [misaWriteFile_(MISA_STOCK_KHO[kho].tpl, 'Nhap kho', 9, rows, MISA_STOCK_KHO[kho].out + misaStamp_() + '.xlsx', dry)] : [];
  if (!dry && flags !== false && statuses.length) misaWriteStatus_('NHAP', stCol, statuses);
  return { files, canh_bao: canhBao, bo_qua: uniq_(boQua), so_hop_le: rows.length, so_loi: canhBao.length, _sync: !dry && statuses.length ? ['NHAP'] : [] };
}

// ---- Sửa xlsx bằng XML (Apps Script không có openpyxl): giữ nguyên mẫu, xoá dòng mẫu từ startRow, chèn dòng mới ----

/** Điền rows ([{cột 1-based: giá trị}]) vào sheetName của file mẫu, từ startRow; dòng cũ từ startRow trở xuống bị xoá (như openpyxl delete_rows). */
function xlsxFill_(tplBlob, sheetName, startRow, rows) {
  const files = Utilities.unzip(tplBlob.setContentType('application/zip'));
  const get = n => files.find(f => f.getName() === n);
  const target = xlsxSheetPath_(get('xl/workbook.xml').getDataAsString('UTF-8'), get('xl/_rels/workbook.xml.rels').getDataAsString('UTF-8'), sheetName);
  const sheetFile = get(target);
  if (!sheetFile) throw new Error('Không thấy ' + target + ' trong mẫu');
  const xml = xlsxReplaceRows_(sheetFile.getDataAsString('UTF-8'), startRow, rows);
  const blobs = files.map(f => (f.getName() === target ? Utilities.newBlob(xml, 'application/xml', target) : f));
  return Utilities.zip(blobs, 'misa.xlsx').setContentType(XLSX_MIME);
}

/** Đường file XML của sheet theo tên (workbook.xml + rels). */
function xlsxSheetPath_(workbookXml, relsXml, sheetName) {
  const esc = sheetName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const sh = new RegExp('<sheet\\b[^>]*\\bname="' + esc + '"[^>]*>').exec(workbookXml);
  if (!sh) throw new Error('Mẫu không có sheet "' + sheetName + '"');
  const rid = /\br:id="([^"]+)"/.exec(sh[0])[1];
  const rel = new RegExp('<Relationship\\b[^>]*\\bId="' + rid + '"[^>]*>').exec(relsXml);
  if (!rel) throw new Error('Mẫu thiếu liên kết sheet ' + rid);
  const t = /\bTarget="([^"]+)"/.exec(rel[0])[1];
  return t.charAt(0) === '/' ? t.slice(1) : 'xl/' + t;
}

function xlsxEsc_(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

/** Thay phần dữ liệu của sheet: giữ dòng < startRow, xoá phần còn lại, chèn rows; bỏ ô gộp nằm ở vùng đã xoá, sửa dimension. */
function xlsxReplaceRows_(xml, startRow, rows) {
  const open = xml.search(/<sheetData\b/);
  if (open === -1) throw new Error('sheet không có sheetData');
  const selfClose = /^<sheetData\b[^>]*\/>/.exec(xml.slice(open));
  let head, body, tail;
  if (selfClose) { head = xml.slice(0, open) + '<sheetData>'; body = ''; tail = '</sheetData>' + xml.slice(open + selfClose[0].length); }
  else {
    const gt = xml.indexOf('>', open) + 1;
    const close = xml.indexOf('</sheetData>', gt);
    head = xml.slice(0, gt); body = xml.slice(gt, close); tail = xml.slice(close);
  }
  const kept = (body.match(/<row\b[^>]*\/>|<row\b[^>]*>[\s\S]*?<\/row>/g) || []).filter(rw => Number((/\br="(\d+)"/.exec(rw) || [0, 0])[1]) < startRow);
  let maxCol = 1;
  const added = rows.map((cells, i) => {
    const r = startRow + i;
    const cols = Object.keys(cells).map(Number).sort((a, b) => a - b);
    const cx = cols.map(cn => {
      const val = cells[cn];
      if (val === '' || val === null || val === undefined) return '';
      maxCol = Math.max(maxCol, cn);
      const ref = columnLetter_(cn) + r;
      return typeof val === 'number' && isFinite(val) ? '<c r="' + ref + '"><v>' + val + '</v></c>'
        : '<c r="' + ref + '" t="inlineStr"><is><t xml:space="preserve">' + xlsxEsc_(val) + '</t></is></c>';
    }).join('');
    return '<row r="' + r + '">' + cx + '</row>';
  });
  let out = head + kept.join('') + added.join('') + tail;
  // ô gộp ở vùng đã xoá → bỏ (tránh Excel báo lỗi khi mở)
  out = out.replace(/<mergeCells\b[^>]*>([\s\S]*?)<\/mergeCells>/, (m, inner) => {
    const keep = (inner.match(/<mergeCell\b[^>]*\/>/g) || []).filter(mc => Number(/[A-Z]+(\d+)/.exec(/\bref="([^"]+)"/.exec(mc)[1])[1]) < startRow);
    return keep.length ? '<mergeCells count="' + keep.length + '">' + keep.join('') + '</mergeCells>' : '';
  });
  const lastRow = Math.max(startRow - 1 + rows.length, 1);
  const colNum = l => l.split('').reduce((t, ch) => t * 26 + ch.charCodeAt(0) - 64, 0);
  out = out.replace(/<dimension\b[^>]*\bref="([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?"[^>]*\/>/, (m, c1, r1, c2) =>
    '<dimension ref="' + c1 + r1 + ':' + columnLetter_(Math.max(colNum(c2 || c1), maxCol)) + lastRow + '"/>');
  return out;
}

// =====================================================================
// CỬA "ĐÁNH DẤU ĐÃ XUẤT FILE SÀN" (web xuất file Shopee / TikTok song song menu HNC)
// POST {WEBAPP_URL}?export_key=<EXPORT_KEY>
// Body: { action:"mark_exported", channel:"shopee"|"tiktok", kind:"upload"|"update", codes:[…], at:"<ISO>", stock_included?, dry_run? }
//  - upload: SANPHAM cột shopee_upload / tiktok_upload = "Done - yyyy-MM-dd HH:mm" cho mã có trong codes (giống main.py).
//  - update: ghi mốc "lần cập nhật tồn/giá gần nhất" vào tab META (key | value | updated_at), dòng key = shopee_last_update / tiktok_last_update.
// =====================================================================

const EXPORT_CHANNELS = ['shopee', 'tiktok'];
const EXPORT_MAX_CODES = 3000;

function handleExportRequest_(e) {
  let out;
  try {
    const props = PropertiesService.getScriptProperties();
    const key = props.getProperty('EXPORT_KEY') || '';
    const others = ['WEBHOOK_KEY', 'SALE_KEY', 'WEB_NOTIFY_KEY', 'SYNC_HINT_KEY'].map(n => props.getProperty(n)).filter(Boolean);
    if (key.length < 16 || others.indexOf(key) !== -1) {
      out = { ok: false, error: 'chưa cấu hình EXPORT_KEY (≥16 ký tự, khác các khoá khác) trong Script Properties' };
    } else if (e.parameter.export_key !== key) {
      out = { ok: false, error: 'unauthorized' };
    } else {
      const body = JSON.parse((e.postData && e.postData.contents) || '{}');
      const dryRun = String(props.getProperty('DRY_RUN') || '').toLowerCase() === 'true' || body.dry_run === true;
      out = handleExport_(body, dryRun);
      if (!dryRun && out.ok && !out.duplicate && out.written) {
        try { queueSyncHint_([out.kind === 'update' ? 'META' : 'SANPHAM']); } catch (err) { console.error(err && err.stack ? err.stack : err); }
      }
    }
  } catch (err) {
    console.error(err && err.stack ? err.stack : err);
    out = { ok: false, error: 'bad_request: ' + (err && err.message ? err.message : err) };
  }
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
}

function handleExport_(body, dryRun) {
  MEMO = {};
  const channel = String(body.channel || '').trim().toLowerCase();
  const kind = String(body.kind || '').trim().toLowerCase();
  if (body.action !== 'mark_exported') return { ok: false, error: 'action phải là "mark_exported"' };
  if (EXPORT_CHANNELS.indexOf(channel) === -1) return { ok: false, error: 'channel phải là shopee hoặc tiktok' };
  if (kind !== 'upload' && kind !== 'update') return { ok: false, error: 'kind phải là upload hoặc update' };
  const codes = Array.isArray(body.codes) ? uniq_(body.codes.map(c => String(c || '').trim().toUpperCase()).filter(Boolean)) : [];
  if (kind === 'upload' && (!codes.length || codes.length > EXPORT_MAX_CODES)) return { ok: false, error: 'codes phải có 1-' + EXPORT_MAX_CODES + ' mã' };
  // Mốc *_last_update là "lần cập nhật TỒN gần nhất": file không có cột tồn (vd mẫu TikTok All_Information) thì không ghi
  if (kind === 'update' && body.stock_included === false) {
    return { ok: false, kind, written: 0, error: 'mẫu không có cột tồn — không ghi mốc ' + channel + '_last_update' };
  }
  let at = body.at ? new Date(body.at) : new Date();
  if (isNaN(at)) at = new Date();
  const stamp = Utilities.formatDate(at, TZ, 'yyyy-MM-dd HH:mm');

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const props = PropertiesService.getScriptProperties();
    const digestKey = 'export_' + digestHex_([channel, kind, stamp].concat(codes.slice().sort()).join('|'));
    if (props.getProperty(digestKey)) return { ok: true, duplicate: true, kind, written: 0, not_found: [] };

    let result;
    if (kind === 'upload') {
      const data = sheetValues_('SANPHAM');
      let headerRow = -1;
      for (let r = 0; r < Math.min(2, data.length); r++) {
        if (data[r].map(h => String(h).trim()).indexOf('product_code') !== -1) { headerRow = r; break; }
      }
      if (headerRow === -1) throw new Error('Tab SANPHAM thiếu cột product_code');
      const col = headerMap_(data[headerRow]);
      const statusName = channel + '_upload';
      requireColumns_('SANPHAM', col, ['product_code', statusName]);
      const want = {};
      codes.forEach(c => { want[c] = true; });
      const found = {};
      const cells = [];
      const pending = []; // mã "cần bổ sung" (trống ngành / giá bán) → không đánh dấu đã đăng
      for (let r = headerRow + 1; r < data.length; r++) {
        const c = String(data[r][col.product_code]).trim().toUpperCase();
        if (!want[c]) continue;
        found[c] = true;
        if (needsInfo_(data[r], col)) { pending.push(c); continue; }
        cells.push(columnLetter_(col[statusName] + 1) + (r + 1));
      }
      if (!dryRun && cells.length) getSheet_('SANPHAM').getRangeList(cells).setValue('Done - ' + stamp);
      result = { ok: true, kind, column: statusName, value: 'Done - ' + stamp, written: cells.length, not_found: codes.filter(c => !found[c]),
        chua_bo_sung: uniq_(pending) };
    } else {
      const meta = writeMeta_(channel + '_last_update', stamp, dryRun);
      if (!meta.ok) return { ok: false, error: meta.error };
      result = { ok: true, kind, cell: meta.cell, value: stamp, written: 1, not_found: [] };
    }
    if (!dryRun) {
      props.setProperty(digestKey, JSON.stringify({ t: Date.now() }));
      pruneTickets_(props, 'export_');
    }
    result.dry_run = dryRun;
    return result;
  } finally {
    lock.releaseLock();
  }
}

/**
 * Ghi 1 mốc vào tab META (cột key | value | updated_at, tìm theo TÊN cột và theo key).
 * Chưa có dòng key → thêm dòng mới cuối bảng. Chưa có tab / cột → báo lỗi, không tự tạo.
 */
function writeMeta_(key, value, dryRun) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('META');
  if (!sheet) return { ok: false, error: 'chưa có tab META (cần anh Kha cho tạo)' };
  const data = sheet.getDataRange().getValues();
  const col = headerMap_(data[0] || []);
  const missing = ['key', 'value', 'updated_at'].filter(n => col[n] === undefined);
  if (missing.length) return { ok: false, error: 'tab META thiếu cột: ' + missing.join(', ') };
  let row = -1;
  for (let r = 1; r < data.length; r++) {
    if (String(data[r][col.key]).trim() === key) { row = r + 1; break; }
  }
  if (row === -1) {
    row = 1;
    for (let r = data.length; r >= 1; r--) {
      if (data[r - 1].some(v => String(v).trim() !== '')) { row = r + 1; break; }
    }
    if (!dryRun) sheet.getRange(row, col.key + 1).setValue(key);
  }
  if (!dryRun) {
    sheet.getRange(row, col.value + 1).setValue(value);
    sheet.getRange(row, col.updated_at + 1).setValue(Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm:ss'));
  }
  return { ok: true, cell: 'META!' + columnLetter_(col.value + 1) + row };
}

function digestHex_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, text, Utilities.Charset.UTF_8)
    .map(b => ('0' + (b & 0xff).toString(16)).slice(-2)).join('');
}

// =====================================================================
// THEO DÕI HOÁ ĐƠN NHÀ CUNG CẤP (không thêm tab / cột)
// Phiếu = ngày nhập + nhà cung cấp + kho (2 kho = 2 hộ kinh doanh, mỗi hộ 1 hoá đơn riêng), gom từ tab NHAP.
// Dòng NHAP chưa có KHO = chưa chia hàng = chưa đòi hoá đơn. Bỏ dòng trả hàng (Số chứng từ TRA-…).
// Hoá đơn đã về: tự nhận từ thư mục Drive "Hoá đơn 2026/<hộ>/<nhà cung cấp>/<yyyymmdd>/" (có file);
// mỗi thư mục ngày ghép với phiếu gần nhất chưa ghép có ngày nhập ≤ ngày hoá đơn; anh sửa tay bằng lệnh "hoadon <mã phiếu> da / khong / chua" (lưu Script Properties, không ghi Sheet).
// =====================================================================

const INVOICE_START = '2026-09-01';       // chỉ theo dõi / nhắc phiếu từ ngày này
const INVOICE_MATCH_FROM = '2026-01-01';  // ghép hoá đơn với phiếu từ đầu năm để hoá đơn cũ không ghép nhầm vào phiếu mới
const INVOICE_REMIND_DAYS = 7;
const INVOICE_FOLDER_DEFAULT = '1KLzyJnbtSEd2BhE_GPxshqxTNqmR5hs4'; // My Drive/HNC/Thue/2026/Hoá đơn 2026 (theo ID, kéo thư mục vẫn chạy; đổi bằng INVOICE_FOLDER_ID)
const INVOICE_HKD_FOLDERS = { '15E': 'Hải Nancy', 'Y3C': 'Yen Leather' };
const NO_SUPPLIER = '(chưa có NCC)';

/** Các phiếu (ngày + NCC + kho) từ NHAP, kèm dòng hàng gộp theo mã và tiền theo đơn giá hoá đơn SANPHAM. */
function invoiceTickets_() {
  const nh = sheetValues_('NHAP');
  const col = headerMap_(nh[0]);
  requireColumns_('NHAP', col, ['Ngày chứng từ (*)', 'Số chứng từ (*)', 'product_code', 'KHO', 'Số lượng (*)']);

  const sp = sheetValues_('SANPHAM');
  let hr = 0;
  for (let r = 0; r < Math.min(2, sp.length); r++) if (sp[r].map(h => String(h).trim()).indexOf('product_code') !== -1) { hr = r; break; }
  const sc = headerMap_(sp[hr]);
  const nameCol = sc.CON_NAME !== undefined ? sc.CON_NAME : sc.product_name;
  const prod = {};
  for (let r = hr + 1; r < sp.length; r++) {
    const c = String(sp[r][sc.product_code] || '').trim().toUpperCase();
    if (c) prod[c] = { supplier: sc.supplier !== undefined ? String(sp[r][sc.supplier] || '').trim() : '',
      parent: (sc.parent_product_code !== undefined ? String(sp[r][sc.parent_product_code] || '').trim().toUpperCase() : '') || c.replace(/[A-Z]$/, ''),
      price: (sc.invoice_price !== undefined ? moneyValue_(sp[r][sc.invoice_price]) : 0) ||
        (sc.purchase_price !== undefined ? moneyValue_(sp[r][sc.purchase_price]) : 0), // invoice_price trống → giá nhập (anh Kha 17/10)
      name: nameCol !== undefined ? String(sp[r][nameCol] || '').trim() : '' };
  }

  const tickets = {};
  for (let r = 1; r < nh.length; r++) {
    const code = String(nh[r][col.product_code] || '').trim().toUpperCase();
    if (!code || code === 'PRODUCT_CODE') continue;
    if (String(nh[r][col['Số chứng từ (*)']] || '').trim().toUpperCase().indexOf('TRA-') === 0) continue;
    const kho = KHO_ALIASES[String(nh[r][col.KHO] || '').trim().toUpperCase()];
    if (!kho) continue; // chưa chia kho → chưa đòi hoá đơn
    const date = dateKey_(nh[r][col['Ngày chứng từ (*)']]);
    if (!date || date < INVOICE_MATCH_FROM) continue;
    const qty = Number(nh[r][col['Số lượng (*)']]) || 0;
    if (qty <= 0) continue;
    const p = prod[code] || { supplier: '', price: 0, name: '', parent: code.replace(/[A-Z]$/, '') };
    const so = String(nh[r][col['Số chứng từ (*)']] || '').trim();
    const pn = receiptIndex_(so) || receiptByNhap_(kho, so); // nhập từ phiếu NCC → NCC / số phiếu theo phiếu
    const supplier = (pn && pn.ncc) || p.supplier || NO_SUPPLIER;
    const key = date + '|' + supplier + '|' + kho;
    const t = tickets[key] || (tickets[key] = { date, supplier, kho, qty: 0, amount: 0, lines: {}, ncc_docs: [] });
    if (pn && pn.so && t.ncc_docs.indexOf(pn.so) === -1) t.ncc_docs.push(pn.so);
    const line = t.lines[code] || (t.lines[code] = { code, parent: p.parent || code, name: p.name, price: p.price, qty: 0 });
    line.qty += qty;
    t.qty += qty;
    t.amount += qty * p.price;
  }

  const sup = supplierInfo_();
  return Object.keys(tickets).map(k => {
    const t = tickets[k];
    const info = sup[t.supplier] || {};
    const short = String(info.code || '').replace(/^NCC/i, '') || norm_(t.supplier).replace(/[^a-z0-9]/g, '').toUpperCase().slice(0, 8) || 'NCC';
    t.id = t.date.slice(2).replace(/-/g, '') + '-' + short + '-' + t.kho;
    t.info = info;
    t.lines = Object.keys(t.lines).sort().map(c => t.lines[c]);
    return t;
  }).sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : a.id < b.id ? -1 : 1));
}

/** Nhà cung cấp trong SUB (cột supplier, Mã đối tượng, Tên đối tượng, Số điện thoại, Thuế suất). */
function supplierInfo_() {
  const sub = sheetValues_('SUB');
  const c = headerMap_(sub[0] || []);
  const out = {};
  if (c.supplier === undefined) return out;
  for (let r = 1; r < sub.length; r++) {
    const s = String(sub[r][c.supplier] || '').trim();
    if (!s) continue;
    const g = n => (c[n] !== undefined ? String(sub[r][c[n]] || '').trim() : '');
    out[s] = { code: g('Mã đối tượng'), legal: g('Tên đối tượng'), phone: g('Số điện thoại'), tax: g('Thuế suất') };
  }
  return out;
}

/** Ngày hoá đơn đã lưu trên Drive: { kho: { tên NCC đã bỏ dấu: [yyyy-MM-dd…] } }. Lỗi đọc Drive → null. */
function invoiceFolders_() {
  const cache = CacheService.getScriptCache();
  const hit = cache.get('invoice_folders');
  if (hit) return JSON.parse(hit);
  try {
    const id = PropertiesService.getScriptProperties().getProperty('INVOICE_FOLDER_ID') || INVOICE_FOLDER_DEFAULT;
    const root = DriveApp.getFolderById(id);
    const out = {};
    Object.keys(INVOICE_HKD_FOLDERS).forEach(kho => {
      out[kho] = {};
      const hk = root.getFoldersByName(INVOICE_HKD_FOLDERS[kho]);
      while (hk.hasNext()) {
        const sups = hk.next().getFolders();
        while (sups.hasNext()) {
          const sf = sups.next();
          const dates = [];
          const ds = sf.getFolders();
          while (ds.hasNext()) {
            const df = ds.next();
            const m = String(df.getName()).match(/^(\d{4})(\d{2})(\d{2})/);
            if (m && df.getFiles().hasNext()) dates.push(m[1] + '-' + m[2] + '-' + m[3]);
          }
          const k = norm_(sf.getName()).replace(/\s+/g, ' ').trim();
          out[kho][k] = (out[kho][k] || []).concat(dates).sort();
        }
      }
    });
    cache.put('invoice_folders', JSON.stringify(out), 600);
    return out;
  } catch (err) {
    console.error('Không đọc được thư mục hoá đơn: ' + (err && err.message ? err.message : err));
    return null;
  }
}

/** Gắn trạng thái cho từng phiếu: sửa tay (Script Properties) > tự nhận từ thư mục Drive > chưa. */
function invoiceStatus_(tickets) {
  const folders = invoiceFolders_();
  const auto = {};
  if (folders) {
    const groups = {};
    tickets.slice().sort((a, b) => (a.date < b.date ? -1 : 1)).forEach(t => {
      const k = t.kho + '|' + norm_(t.supplier).replace(/\s+/g, ' ').trim();
      (groups[k] = groups[k] || []).push(t);
    });
    Object.keys(groups).forEach(k => {
      const [kho, sup] = k.split('|');
      const dates = ((folders[kho] || {})[sup] || []).slice().sort();
      const list = groups[k];
      dates.forEach(d => {
        // Phiếu GẦN NHẤT chưa ghép có ngày nhập không sau ngày hoá đơn (hoá đơn thường xin ngay sau đợt nhập)
        for (let i = list.length - 1; i >= 0; i--) {
          if (!auto[list[i].id] && list[i].date <= d) { auto[list[i].id] = d; break; }
        }
      });
    });
  }
  const props = PropertiesService.getScriptProperties();
  tickets.forEach(t => {
    let manual = null;
    try { manual = JSON.parse(props.getProperty('hdon_' + t.id) || 'null'); } catch (e) { /* bỏ qua */ }
    if (manual && manual.s) { t.status = manual.s; t.source = 'tay ' + (manual.at || ''); }
    else if (auto[t.id]) { t.status = 'da'; t.source = 'thư mục ' + auto[t.id]; }
    else { t.status = 'chua'; t.source = ''; }
  });
  return { tickets, driveOk: !!folders };
}

function invoiceAgeDays_(t) {
  const today = Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd');
  return Math.round((Date.parse(today) - Date.parse(t.date)) / 86400000);
}

/** Câu nhắn soạn sẵn gửi nhà cung cấp, ghi rõ hộ kinh doanh nhận hoá đơn. */
function invoiceMessage_(t) {
  const raw = PropertiesService.getScriptProperties().getProperty('HKD_' + t.kho) || '';
  const parts = raw.split('|').map(x => x.trim());
  const d = t.date.split('-');
  const lines = [
    'Chào ' + (t.supplier === NO_SUPPLIER ? 'anh/chị' : t.supplier) + ',',
    'Hiệu giày Hải Nancy nhờ anh/chị xuất hoá đơn cho hàng nhập ngày ' + d[2] + '/' + d[1] + '/' + d[0] + ' (kho ' + t.kho + ')' +
      (t.ncc_docs && t.ncc_docs.length ? ', theo phiếu xuất ' + t.ncc_docs.join(', ') : '') + ':',
  ];
  if (raw) {
    lines.push('• Đơn vị mua: ' + (parts[0] || ''));
    if (parts[1]) lines.push('• MST: ' + parts[1]);
    if (parts[2]) lines.push('• Địa chỉ: ' + parts.slice(2).join(' | '));
  } else {
    lines.push('• Đơn vị mua: (chưa có thông tin — anh điền HKD_' + t.kho + ' trong Apps Script)');
  }
  lines.push('Hàng hoá:');
  // Gọn: gom theo mã cha (cùng mẫu khác màu cộng lại), không ghi tên / giá
  const byParent = {};
  t.lines.forEach(l => { byParent[l.parent] = (byParent[l.parent] || 0) + l.qty; });
  Object.keys(byParent).sort().forEach(pc => lines.push(pc + ' x ' + byParent[pc]));
  lines.push('Tổng: ' + t.qty + ' sản phẩm');
  lines.push('Cảm ơn anh/chị!');
  return lines.join('\n');
}

/** Lệnh Zalo: hoadon | hoadon <mã phiếu> | hoadon <mã phiếu> da / khong / chua */
function doInvoice_(text, dryRun) {
  const rest = norm_(text).replace(/^hoa\s*don/, '').trim();
  const toks = rest.split(/\s+/).filter(Boolean);
  const st = invoiceStatus_(invoiceTickets_());
  const tickets = st.tickets.filter(t => t.date >= INVOICE_START);
  const note = st.driveOk ? '' : '\n⚠️ Chưa đọc được thư mục hoá đơn trên Drive — chỉ dựa vào lệnh tay.';

  if (!toks.length) {
    const pending = tickets.filter(t => t.status === 'chua');
    if (!pending.length) return { text: '🧾 Không còn phiếu nào chưa có hoá đơn (từ ' + INVOICE_START.split('-').reverse().join('/') + ').' + note };
    const bySup = {};
    pending.forEach(t => { (bySup[t.supplier] = bySup[t.supplier] || []).push(t); });
    const out = ['🧾 PHIẾU CHƯA CÓ HOÁ ĐƠN: ' + pending.length + ' (đã có ' + tickets.filter(t => t.status === 'da').length +
      ', không cần ' + tickets.filter(t => t.status === 'khong').length + ')'];
    Object.keys(bySup).sort().forEach(s => {
      out.push('• ' + s);
      bySup[s].forEach(t => {
        const age = invoiceAgeDays_(t);
        out.push('  ' + t.id + ': ' + t.qty + ' sp' + (t.amount ? ', ' + money_(t.amount) : '') + (age >= INVOICE_REMIND_DAYS ? ' ⏰ ' + age + ' ngày' : ''));
      });
    });
    out.push('Xem câu nhắn: hoadon <mã phiếu> · Ghi nhận: hoadon <mã phiếu> da / khong');
    return { text: out.join('\n') + note };
  }

  const key = toks[0].toUpperCase();
  const matches = st.tickets.filter(t => t.id.indexOf(key) === 0);
  if (!matches.length) return { text: '❓ Không có phiếu nào bắt đầu bằng "' + key + '". Nhắn "hoadon" để xem danh sách mã phiếu.' };
  const stTok = toks[1] || '';
  const newStatus = /^(da|roi|xong|ok)$/.test(stTok) ? 'da' : /^(khong|ko|k)$/.test(stTok) ? 'khong' : /^chua$/.test(stTok) ? 'chua' : '';
  if (!newStatus) {
    return { text: matches.slice(0, 3).map(t => '🧾 ' + t.id + ' — ' + ({ da: '✅ đã có hoá đơn', khong: '➖ không cần', chua: '⏳ chưa có' })[t.status] +
      (t.source ? ' (' + t.source + ')' : '') + '\n\n' + invoiceMessage_(t)).join('\n\n—\n\n') };
  }
  if (!dryRun) {
    const props = PropertiesService.getScriptProperties();
    const at = Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd');
    matches.forEach(t => props.setProperty('hdon_' + t.id, JSON.stringify({ s: newStatus, at })));
  }
  return { text: '🧾 Đã ghi ' + ({ da: '✅ đã có hoá đơn', khong: '➖ không cần hoá đơn', chua: '⏳ chưa có hoá đơn' })[newStatus] + ': ' + matches.map(t => t.id).join(', ') };
}

/** Trigger sáng thứ Hai: nhắc anh các phiếu quá INVOICE_REMIND_DAYS ngày chưa có hoá đơn, kèm câu nhắn soạn sẵn. */
function weeklyInvoiceReminder() {
  try {
    MEMO = {};
    const owner = PropertiesService.getScriptProperties().getProperty('OWNER_CHAT_ID');
    if (!owner) return;
    invoiceReminderMessages_().forEach(m => sendMessage_(owner, m));
  } catch (err) { console.error(err && err.stack ? err.stack : err); }
}

function invoiceReminderMessages_() {
  const due = invoiceStatus_(invoiceTickets_()).tickets
    .filter(t => t.date >= INVOICE_START && t.status === 'chua' && invoiceAgeDays_(t) >= INVOICE_REMIND_DAYS);
  if (!due.length) return [];
  const msgs = ['⏰ ' + due.length + ' phiếu nhập quá ' + INVOICE_REMIND_DAYS + ' ngày chưa có hoá đơn. Câu nhắn soạn sẵn bên dưới — chép gửi nhà cung cấp.\n' +
    'Đã nhận thì nhắn: hoadon <mã phiếu> da · Không cần: hoadon <mã phiếu> khong'];
  due.slice(0, 10).forEach(t => msgs.push('🧾 ' + t.id + ' (' + invoiceAgeDays_(t) + ' ngày)\n\n' + invoiceMessage_(t)));
  if (due.length > 10) msgs.push('… còn ' + (due.length - 10) + ' phiếu nữa — nhắn "hoadon" để xem hết.');
  return msgs;
}

/** Chạy thử trong trình soạn thảo: in danh sách phiếu + tin nhắc tuần (KHÔNG gửi Zalo). */
function testInvoice() {
  MEMO = {};
  console.log(doInvoice_('hoadon', true).text);
  invoiceReminderMessages_().forEach(m => console.log(m));
}

// =====================================================================
// SỔ KÝ GỬI GIỮA 2 HỘ (tab KYGUI, anh Kha "làm" 17/10)
// Hàng của hộ này đang nằm ở kho hộ kia (chuyển kho giữa 2 hộ không xuất hoá đơn).
// Chuyển A → B: trả trước hàng của B đang ký gửi ở A (trừ KYGUI chủ B ở A), phần còn lại thành ký gửi của A ở B.
// Bán / xuất ở kho K: trừ hàng ký gửi của hộ kia ở K trước → BAN.chu_hang = hộ kia; còn lại chu_hang = K.
// Trả hàng: về đúng chủ (chu_hang gửi kèm, hoặc dòng BAN gần nhất cùng mã / size / kho). Chưa có tab KYGUI → tắt, chủ hàng = kho.
// =====================================================================

const KYGUI_TAB = 'KYGUI';
const KYGUI_COLS = ['product_code', 'item_size', 'chu_hang', 'kho_dang_o', 'so_luong', 'cap_nhat'];

function kyguiOn_() {
  if (MEMO.__kyOn === undefined) MEMO.__kyOn = !!SpreadsheetApp.getActiveSpreadsheet().getSheetByName(KYGUI_TAB);
  return MEMO.__kyOn;
}

/** Các dòng KYGUI → [{row, code, size, chu, at, qty}] (theo tên cột hàng 1). */
function kyguiRows_() {
  if (!MEMO.__ky) {
    const data = sheetValues_(KYGUI_TAB);
    const col = headerMap_(data[0] || []);
    requireColumns_(KYGUI_TAB, col, KYGUI_COLS);
    MEMO.__ky = [];
    for (let r = 1; r < data.length; r++) {
      const code = String(data[r][col.product_code] || '').trim().toUpperCase();
      if (!code) continue;
      MEMO.__ky.push({ row: r + 1, code, size: normSize_(data[r][col.item_size]), chu: KHO_ALIASES[String(data[r][col.chu_hang] || '').trim().toUpperCase()] || '',
        at: KHO_ALIASES[String(data[r][col.kho_dang_o] || '').trim().toUpperCase()] || '', qty: Number(data[r][col.so_luong]) || 0 });
    }
  }
  return MEMO.__ky;
}

/** Số đang ký gửi: hàng của `chu` đang ở `at` (CTX.kyPending: thay đổi chưa ghi trong lô chạy thử). */
function kyguiQty_(chu, at, code, size) {
  if (!kyguiOn_()) return 0;
  const k = chu + '|' + at + '|' + code + '|' + size;
  const row = kyguiRows_().find(x => x.chu === chu && x.at === at && x.code === code && x.size === size);
  return Math.max(0, (row ? row.qty : 0) + (((CTX.kyPending || {})[k]) || 0));
}

/** Cộng / trừ KYGUI 1 ô (chủ × kho đang ở × mã × size). Chạy thật → trả op để huỷ được. */
function kyguiAdjust_(chu, at, code, size, delta, dry) {
  const k = chu + '|' + at + '|' + code + '|' + size;
  if (!CTX.kyPending) CTX.kyPending = {};
  if (dry) { CTX.kyPending[k] = (CTX.kyPending[k] || 0) + delta; return null; }
  const sheet = getSheet_(KYGUI_TAB);
  const data = sheetValues_(KYGUI_TAB);
  const col = headerMap_(data[0]);
  const rows = kyguiRows_();
  let row = rows.find(x => x.chu === chu && x.at === at && x.code === code && x.size === size);
  const now = Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm');
  if (row) {
    const before = row.qty;
    row.qty = before + delta;
    sheet.getRange(row.row, col.so_luong + 1).setValue(row.qty);
    sheet.getRange(row.row, col.cap_nhat + 1).setValue(now);
    return { type: 'kygui', sheet: KYGUI_TAB, row: row.row, before, after: row.qty };
  }
  let last = data.length;
  while (last > 1 && String(data[last - 1][col.product_code] || '').trim() === '') last--;
  const r = last + 1;
  if (r > sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(), 100);
  const arr = new Array(data[0].length).fill('');
  arr[col.product_code] = code; arr[col.item_size] = sizeValue_(size); arr[col.chu_hang] = chu; arr[col.kho_dang_o] = at; arr[col.so_luong] = delta; arr[col.cap_nhat] = now;
  sheet.getRange(r, 1, 1, arr.length).setValues([arr]);
  while (data.length < r - 1) data.push(new Array(arr.length).fill(''));
  data[r - 1] = arr;
  rows.push({ row: r, code, size, chu, at, qty: delta });
  return { type: 'kygui', sheet: KYGUI_TAB, row: r, before: null, after: delta, created: KYGUI_COLS.slice() };
}

/** Chuyển kho from → to: trả hàng của `to` đang ký gửi ở `from` trước, phần còn lại thành ký gửi của `from` ở `to`. */
function kyguiTransfer_(code, size, qty, from, to, dry) {
  const out = { ops: [], notes: [] };
  if (!kyguiOn_()) return out;
  const back = Math.min(qty, kyguiQty_(to, from, code, size));
  if (back > 0) {
    const op = kyguiAdjust_(to, from, code, size, -back, dry);
    if (op) out.ops.push(op);
    out.notes.push({ size, chu_hang: to, qty: back, loai: 'tra_ve_chu' });
  }
  if (qty - back > 0) {
    const op = kyguiAdjust_(from, to, code, size, qty - back, dry);
    if (op) out.ops.push(op);
    out.notes.push({ size, chu_hang: from, qty: qty - back, loai: 'thanh_ky_gui' });
  }
  return out;
}

/** Bán ở kho `kho`: tách theo chủ hàng (ký gửi của hộ kia trước) → [{chu_hang, qty}]; chạy thật thì ghi BAN + trừ KYGUI. */
function kyguiSale_(code, color, price, size, qty, kho, channel, seller, dry) {
  const other = kho === 'Y3C' ? '15E' : 'Y3C';
  const cons = Math.min(qty, kyguiQty_(other, kho, code, size));
  const phan = [];
  if (cons > 0) phan.push({ chu_hang: other, qty: cons });
  if (qty - cons > 0) phan.push({ chu_hang: kho, qty: qty - cons });
  const ops = [];
  phan.forEach(ph => {
    if (ph.chu_hang !== kho) { const op = kyguiAdjust_(ph.chu_hang, kho, code, size, -ph.qty, dry); if (op) ops.push(op); }
    if (!dry) ops.push(appendBan_(code, color, price, size, ph.qty, kho, channel, seller, ph.chu_hang));
  });
  return { ops, phan };
}

/** Trả hàng về đúng chủ: chủ gửi kèm, không có thì theo dòng BAN gần nhất cùng mã / size / kho có chu_hang. */
function kyguiReturn_(code, size, qty, kho, hint, dry) {
  const out = { ops: [], chu_hang: kho };
  if (!kyguiOn_()) return out;
  let chu = KHO_ALIASES[String(hint || '').trim().toUpperCase()] || '';
  if (!chu) {
    const ban = sheetValues_('BAN');
    const c = headerMap_(ban[0]);
    if (c.chu_hang !== undefined) {
      for (let r = ban.length - 1; r >= 1; r--) {
        if (String(ban[r][c.product_code] || '').trim().toUpperCase() !== code) continue;
        if (normSize_(ban[r][c.item_size]) !== size || KHO_ALIASES[String(ban[r][c.KHO] || '').trim().toUpperCase()] !== kho) continue;
        chu = KHO_ALIASES[String(ban[r][c.chu_hang] || '').trim().toUpperCase()] || '';
        if (chu) break;
      }
    }
  }
  out.chu_hang = chu || kho;
  if (out.chu_hang !== kho) { const op = kyguiAdjust_(out.chu_hang, kho, code, size, qty, dry); if (op) out.ops.push(op); }
  return out;
}

/** Cảnh báo (không chặn): tổng ký gửi đang ở kho > tồn kho đó. pendingStock: số đã trừ / cộng trong lô chưa ghi. */
function kyguiCheck_(code, size, kho) {
  if (!kyguiOn_()) return '';
  const other = kho === 'Y3C' ? '15E' : 'Y3C';
  const ky = kyguiQty_(other, kho, code, size);
  if (ky <= 0) return '';
  const rows = findKhoRows_(kho, code, [size]);
  const stock = (rows.length ? Number(rows[0].current_quantity) || 0 : 0) - (((CTX.pending || {})[kho + code + size]) || 0);
  return ky > stock ? '⚠️ Sổ ký gửi: ' + code + (size ? ' size ' + size : '') + ' kho ' + kho + ' ghi ' + ky + ' của ' + other + ' nhưng tồn chỉ ' + stock + ' — kiểm lại sổ / kho' : '';
}

// =====================================================================
// GHI SHEET
// =====================================================================

function appendBan_(code, color, price, size, qty, kho, channel, seller, chuHang) {
  // FSKU của BAN tự tính bằng ARRAYFORMULA → không ghi cột FSKU.
  // channel / seller chỉ ghi khi tab BAN đã có 2 cột đó (cột thêm cuối hàng tiêu đề).
  return appendByHeader_('BAN', {
    'Ngày': today_(), 'product_code': code, 'product_color': color,
    'Giá': price ? Number(price) : '', 'item_size': sizeValue_(size), 'item_quantity': qty, 'KHO': kho,
  }, null, { product_code: code, item_size: size, item_quantity: qty, KHO: kho },
  { 'channel': channel || '', 'seller': seller || '', 'chu_hang': chuHang || '' });
}

function appendXuat_(code, color, size, qty, kho) {
  // FSKU của XUAT tự tính bằng ARRAYFORMULA → không ghi cột FSKU
  return appendByHeader_('XUAT', {
    'Ngày': today_(), 'product_code': code, 'product_color': color,
    'KHO': kho, 'item_size': sizeValue_(size), 'item_quantity': qty,
  }, null, { product_code: code, item_size: size, item_quantity: qty, KHO: kho });
}

function appendNhap_(code, color, size, qty, kho, isReturn) {
  const values = {
    'Ngày chứng từ (*)': today_(), 'product_code': code, 'product_color': color,
    'KHO': kho, 'item_size': sizeValue_(size), 'Số lượng (*)': qty,
  };
  if (isReturn) values['Số chứng từ (*)'] = 'TRA-' + Utilities.formatDate(new Date(), TZ, 'ddMMyy');
  if (CTX.receiptId && !isReturn) {
    // Nhập từ phiếu NCC: như nhập thường (anh Kha 16/10) — không đánh dấu, HNC in tem / đồng bộ kho / xuất MISA;
    // Số chứng từ = NK<6 số> chạy theo kho (receiptNkPlan_); mã phiếu PN… chỉ giữ nội bộ.
    values['Số chứng từ (*)'] = (CTX.nk && CTX.nk[kho]) || '';
  } else {
    NHAP_MARK_COLUMNS.forEach(c => { values[c] = isReturn ? NHAP_RETURN_MARK : NHAP_ZALO_MARK; });
  }
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
  const body = res.getContentText();
  let okBody = res.getResponseCode() === 200;
  try { okBody = okBody && JSON.parse(body).ok !== false; } catch (e) { /* không phải JSON */ }
  if (!okBody) console.error('sendMessage lỗi ' + res.getResponseCode() + ': ' + body);
  return okBody;
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
    'ban AROMAX60T x2 YEN 70k',
    'ĐƠN WEB #123 — chị Lan 0909xxx\nban TH2040D 40 15E 800k\nban TH2040D 41/2 YEN 800k\nGhi chú: giao chiều',
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
    { ticket_id: 'TEST-004', seller: 'Kha', channel: 'instagram', lines: [{ code: 'TH2040D', size: 40, warehouse: 'Y3C' }] },
  ].forEach(t => console.log('▶ ' + t.ticket_id + '\n' + JSON.stringify(handleSale_(t, true), null, 1)));
}

/** Kiểm cấu hình Script Properties: chỉ in tên, độ dài, các khoá có khác nhau không — KHÔNG in giá trị. */
/** Chạy trong trình soạn thảo: tạo thử 3 file MISA (danh mục, nhập kho 15E, 3C) KHÔNG ghi cờ — mở / nhập thử vào MISA. Xem link ở Nhật ký. */
function thuXuatMisa() {
  ['danh_muc', 'nhap_kho_15e', 'nhap_kho_3c'].forEach(loai => {
    if (loai === 'nhap_kho_3c' && PropertiesService.getScriptProperties().getProperty('MISA_3C') !== '1') return; // chưa khai MISA Yen Leather
    const r = handleMisaExport_({ loai, ghi_co: false }, 'thu@editor', false);
    console.log(loai + ': ' + JSON.stringify({ files: r.files, so_hop_le: r.so_hop_le, so_loi: r.so_loi, bo_qua: r.bo_qua, canh_bao: (r.canh_bao || []).slice(0, 10) }));
  });
}

function checkConfig() {
  const props = PropertiesService.getScriptProperties();
  const names = ['BOT_TOKEN', 'WEBHOOK_KEY', 'WEBAPP_URL', 'ALLOWED_CHAT_IDS', 'DRY_RUN', 'SALE_KEY', 'WEB_NOTIFY_KEY', 'OWNER_CHAT_ID',
    'SYNC_HINT_URL', 'SYNC_HINT_KEY', 'EXPORT_KEY', 'STOCK_KEY', 'GEMINI_API_KEY'];
  names.forEach(n => {
    const v = props.getProperty(n);
    console.log(n + ': ' + (v === null ? '❌ CHƯA CÓ' : '✅ có, dài ' + String(v).length + ' ký tự'));
  });
  // Khoá Gemini: in 8 ký tự đầu sha256 (không in khoá) để so với .env HNC — mỗi repo 1 khoá riêng (anh Kha 16/10)
  const gk = props.getProperty('GEMINI_API_KEY');
  if (gk) {
    const h = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, gk, Utilities.Charset.UTF_8)
      .map(b => ('0' + (b & 255).toString(16)).slice(-2)).join('').slice(0, 8);
    console.log('GEMINI_API_KEY sha256 8 ký tự đầu: ' + h + (h === GEMINI_SHARED_HASH ? ' ❌ vẫn là khoá chung các repo' : ''));
  }
  const keys = ['WEBHOOK_KEY', 'SALE_KEY', 'WEB_NOTIFY_KEY', 'EXPORT_KEY', 'SYNC_HINT_KEY', 'STOCK_KEY'].map(n => props.getProperty(n) || '');
  console.log('Các khoá khác nhau: ' + (new Set(keys.filter(Boolean)).size === keys.filter(Boolean).length ? '✅' : '❌ có khoá trùng'));
  console.log('SALE_KEY ≥16: ' + (keys[1].length >= 16 ? '✅' : '❌') + ' | WEB_NOTIFY_KEY ≥16: ' + (keys[2].length >= 16 ? '✅' : '❌') +
    ' | EXPORT_KEY ≥16: ' + (keys[3].length >= 16 ? '✅' : '❌') + ' | STOCK_KEY ≥16: ' + (keys[5].length >= 16 ? '✅' : '❌'));
  const meta = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('META');
  if (!meta) { console.log('Tab META: ❌ chưa có'); } else {
    const md = meta.getDataRange().getValues();
    const mh = (md[0] || []).map(h => String(h).trim());
    console.log('Tab META cột key/value/updated_at: ' + (['key', 'value', 'updated_at'].every(n => mh.indexOf(n) !== -1) ? '✅' : '❌ thiếu'));
    const keys = md.slice(1).map(r => String(r[mh.indexOf('key')] || '').trim());
    ['shopee_last_update', 'tiktok_last_update'].forEach(k => console.log('META dòng ' + k + ': ' + (keys.indexOf(k) !== -1 ? '✅' : '⚠️ chưa có (sẽ tự thêm khi ghi lần đầu)')));
  }
  const owner = props.getProperty('OWNER_CHAT_ID') || '';
  const allowed = (props.getProperty('ALLOWED_CHAT_IDS') || '').split(',').map(s => s.trim());
  console.log('OWNER_CHAT_ID nằm trong ALLOWED_CHAT_IDS: ' + (owner && allowed.indexOf(owner) !== -1 ? '✅' : '⚠️ không'));
  ['HKD_15E', 'HKD_Y3C'].forEach(n => { const v = props.getProperty(n) || ''; console.log(n + ': ' + (v ? '✅ có (' + v.split('|').length + ' phần: tên | MST | địa chỉ)' : '❌ chưa có')); });
  const folders = invoiceFolders_();
  console.log('Thư mục hoá đơn Drive: ' + (folders ? '✅ đọc được (' + Object.keys(folders).map(k => k + ': ' + Object.keys(folders[k]).length + ' NCC').join(', ') + ')' : '❌ chưa đọc được'));
  try {
    const pf = receiptRoot_();
    let path = pf.getName();
    const up = pf.getParents();
    if (up.hasNext()) path = up.next().getName() + '/' + path;
    console.log('Thư mục phiếu mua hàng Drive: ✅ đọc được (' + path + ')');
  } catch (err) { console.log('Thư mục phiếu mua hàng Drive: ❌ ' + (err && err.message ? err.message : err)); }
  const handlers = ScriptApp.getProjectTriggers().map(t => t.getHandlerFunction());
  SYNC_TRIGGER_HANDLERS.forEach(h => console.log('Trigger ' + h + ': ' + (handlers.indexOf(h) !== -1 ? '✅' : '❌ chưa có (chạy setupChangeTrigger)')));
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
