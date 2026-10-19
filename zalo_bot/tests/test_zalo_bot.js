// Test bot Zalo HNC chạy trên máy (Node), không cần Google: phân tích tin nhắn + cửa "ghi bán" (dry-run, dữ liệu kho giả).
// Chạy: node zalo_bot/tests/test_zalo_bot.js  → thoát mã 1 nếu có ca sai.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const KHO_HEADER = ['15E', 'product_code', 'product_color', 'item_size', 'opening_quantity', 'current_quantity', 'product_location'];
const kho = (prefix, rows) => [[prefix].concat(KHO_HEADER.slice(1))].concat(rows.map(r => [prefix + r[0] + r[2]].concat(r)));
const DATA = {
  KHO15E: kho('15E', [['TH2040D', 'Đen', 40, 0, 0, ''], ['TH2040D', 'Đen', 41, 1, 1, 'B1'], ['119K', 'Kem', 40, 1, 1, '']]),
  KHOY3C: kho('Y3C', [['TH2040D', 'Đen', 40, 1, 1, 'B1'], ['TH2040D', 'Đen', 41, 2, 2, 'B1'], ['TH2040N', 'Nâu', 40, 1, 1, ''],
    ['CXED', 'Đen', 40, 1, 1, ''], ['T1D', 'Đen', 39, 1, 1, ''], ['AROMAX60T', 'Trắng', '', 5, 5, '']]),
};
const PROPS = {};
const WRITES = [];
DATA.SANPHAM = [['Mã hàng hóa cha', '', '', '', '', '', ''], ['parent_product_code', 'product_code', 'shopee_upload', 'tiktok_upload', 'supplier', 'invoice_price', 'CON_NAME'],
  ['TH2040', 'TH2040D', '', '', 'Tuấn Phong', '500000', 'Giày tây TH2040D'], ['TH2040', 'TH2040N', 'Done', '', 'Tuấn Phong', '500.000 đ', 'Giày tây TH2040N'],
  ['CXE', 'CXED', '', 'Thiếu ảnh', 'Chú Dũng', '300000', 'Giày CXED']];
DATA.SUB = [['Tên Ngành Hàng', 'Mã đối tượng', 'Tên đối tượng', 'Số điện thoại', 'supplier', 'Thuế suất'],
  ['Giày tây nam', 'NCCTP', 'CÔNG TY TP', '0901', 'Tuấn Phong', '8%'], ['Giày mọi nam', 'NCCQT', 'HKD QT', '0902', 'Chú Dũng', '0']];
DATA.NHAP = [['Ngày chứng từ (*)', 'Số chứng từ (*)', 'product_code', 'product_color', 'KHO', 'item_size', 'Số lượng (*)', 'FSKU', 'web_stock', 'web_label', 'misa_stock', 'kho_sync'],
  ['', '', 'product_code', 'product_color', 'KHO', 'item_size', 'item_quantity'],
  ['10/09/2026', '', 'TH2040D', 'Đen', '15E', '40', '2'], ['10/09/2026', '', 'TH2040N', 'Nâu', '15E', '41', '1'],
  ['10/09/2026', '', 'TH2040D', 'Đen', 'Y3C', '42', '1'], ['20/09/2026', '', 'TH2040D', 'Đen', '15E', '39', '3'],
  ['21/09/2026', '', 'CXED', 'Đen', '', '40', '1'], ['22/09/2026', 'TRA-220926', 'TH2040D', 'Đen', '15E', '40', '1'],
  ['23/09/2026', '', 'CXED', 'Đen', 'YEN', '40', '0'], ['05/08/2026', '', 'TH2040D', 'Đen', '15E', '40', '1']];
const DRIVE = { 'Hải Nancy': { 'Tuấn Phong': ['20260912'] }, 'Yen Leather': { 'Chú Dũng': ['20260930'] } };
DATA.META = [['key', 'value', 'updated_at'], ['shopee_last_update', '', ''], ['tiktok_last_update', '', '']];
// Drive giả có ghi: thư mục + file theo id
const DFILES = {}, DFOLDERS = {};
let DSEQ = 0;
function dFolder(name, parent) {
  const id = 'F' + (++DSEQ);
  const f = { id, name, parent, kids: [], getId: () => id, getName: () => name,
    getFoldersByName: n => driveIt(f.kids.filter(k => k.name === n)), getFolders: () => driveIt(f.kids), getFiles: () => driveIt(Object.values(DFILES).filter(x => x.folder === id)),
    createFolder: n => { const c = dFolder(n, f); f.kids.push(c); return c; },
    createFile: blob => dFile(blob.name, blob.bytes, blob.mime, id) };
  DFOLDERS[id] = f;
  return f;
}
function dFile(name, bytes, mime, folder) {
  const id = 'D' + (++DSEQ);
  const file = { id, name, bytes, mime, folder, getId: () => id, getName: () => name,
    getBlob: () => ({ getDataAsString: () => Buffer.from(file.bytes).toString(), getBytes: () => file.bytes, getContentType: () => file.mime }),
    setContent: t => { file.bytes = Array.from(Buffer.from(t)); }, moveTo: f => { file.folder = f.getId(); }, getUrl: () => 'https://drive/' + id,
    makeCopy: (n, f) => dFile(n, file.bytes, file.mime, f.getId()) };
  DFILES[id] = file;
  return file;
}
const PN_ROOT = dFolder('Phiếu mua hàng', null);
function driveIt(a) { let i = 0; return { hasNext: () => i < a.length, next: () => a[i++] }; }
function driveFolder(name, kids, hasFiles) {
  return { getName: () => name, getFolders: () => driveIt(kids), getFoldersByName: n => driveIt(kids.filter(k => k.getName() === n)), getFiles: () => driveIt(hasFiles ? [1] : []) };
}
function mockSheet(n) {
  const d = DATA[n];
  return {
    getDataRange: () => ({ getValues: () => d }),
    getLastColumn: () => Math.max.apply(null, d.map(r => r.length)),
    getMaxRows: () => d.length + 50,
    insertRowsAfter: () => {},
    getRange: (r, c, nr, nc) => {
      const put = v => { while (d.length < r) d.push([]); while (d[r - 1].length < c) d[r - 1].push(''); d[r - 1][c - 1] = v; };
      return {
        getValues: () => Array.from({ length: nr || 1 }, (_, k) => Array.from({ length: nc || 1 }, (_, j) => ((d[r - 1 + k] || [])[c - 1 + j] ?? ''))),
        getValue: () => ((d[r - 1] || [])[c - 1] ?? ''),
        setValue: v => { WRITES.push({ sheet: n, cell: [r, c], v }); if (n !== 'META') put(v); },
        setFormula: v => { WRITES.push({ sheet: n, cell: [r, c], v }); put(v); },
        setValues: vals => vals.forEach((rowV, k) => rowV.forEach((v, j) => { WRITES.push({ sheet: n, cell: [r + k, c + j], v }); while (d.length < r + k) d.push([]); while (d[r - 1 + k].length < c + j) d[r - 1 + k].push(''); d[r - 1 + k][c - 1 + j] = v; })),
        setFormulaR1C1: v => { WRITES.push({ sheet: n, cell: [r, c], v }); put(v); },
        getFormulaR1C1: () => { const v = (d[r - 1] || [])[c - 1]; return typeof v === 'string' && v.charAt(0) === '=' ? v : ''; },
        getFormulasR1C1: () => [Array.from({ length: nc || 1 }, (_, j) => { const v = (d[r - 1] || [])[c - 1 + j]; return typeof v === 'string' && v.charAt(0) === '=' ? v : ''; })],
        clearContent: () => put(''),
      };
    },
    getRangeList: list => ({ setValue: v => WRITES.push({ sheet: n, cells: list, v }) }),
  };
}
const CACHE = {};
const ctx = {
  console,
  Utilities: { base64Decode: b => Array.from(Buffer.from(b, 'base64')), base64Encode: b => Buffer.from(b).toString('base64'),
    newBlob: (bytes, mime, name) => ({ bytes: typeof bytes === 'string' ? Array.from(Buffer.from(bytes)) : bytes, mime, name }), DigestAlgorithm: { MD5: 'md5' }, Charset: { UTF_8: 'utf8' }, computeHmacSha256Signature: (msg, key) => Array.from(require('crypto').createHmac('sha256', key).update(msg).digest()).map(b => (b > 127 ? b - 256 : b)), computeDigest: (a, t) => Array.from(require('crypto').createHash('md5').update(t).digest()).map(b => (b > 127 ? b - 256 : b)), formatDate: (d, tz, f) => {
    const parts = {};
    new Intl.DateTimeFormat('en-GB', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
      .formatToParts(d).forEach(x => { parts[x.type] = x.value; });
    return f.replace('yyyy', parts.year).replace('yy', parts.year.slice(-2)).replace('MM', parts.month).replace('dd', parts.day).replace('HH', parts.hour).replace('mm', parts.minute);
  } },
  SpreadsheetApp: { getActiveSpreadsheet: () => ({ getSheetByName: n => DATA[n] ? mockSheet(n) : null }) },
  PropertiesService: { getScriptProperties: () => ({ getProperty: k => PROPS[k] || null, setProperty: (k, v) => { PROPS[k] = v; }, getProperties: () => PROPS, deleteProperty: k => { delete PROPS[k]; } }) },
  LockService: { getScriptLock: () => ({ waitLock() {}, tryLock: () => true, releaseLock() {} }), getDocumentLock: () => ({ tryLock: () => true, releaseLock() {} }) },
  DriveApp: { getFileById: id => DFILES[id], getFolderById: id => (id === '1uE5qpQLtXPYiHpRlpRsNVv8ddT0pyTrD' ? PN_ROOT : driveFolder('root', Object.keys(DRIVE).map(h => driveFolder(h, Object.keys(DRIVE[h]).map(sp => driveFolder(sp, DRIVE[h][sp].map(d => driveFolder(d, [], true)))))))) },
  CacheService: { getScriptCache: () => ({ get: k => (k in CACHE ? CACHE[k] : null), put: (k, v) => { CACHE[k] = v; }, remove: k => { delete CACHE[k]; } }) },
};
vm.createContext(ctx);
const SENT = [];
const HINTS = [];
let GEMINI_REPLY = { ncc: 'Tuấn Phong', so_phieu: 'PX2898', ngay: '2026-10-02', dong: [{ ma_ncc: '32837', mo_ta: 'Giày tây đen', sl: 3, don_gia: 445000 }, { ma_ncc: '', mo_ta: 'Búp bê kem', sl: 2, don_gia: 300000 }], tong_sl: 5, tong_tien: 1935000 };
let GEMINI_CALLS = 0;
ctx.UrlFetchApp = { fetch: (url, opt) => {
  if (url.indexOf('generativelanguage') !== -1) { GEMINI_CALLS++; return { getResponseCode: () => 200, getContentText: () => JSON.stringify({ candidates: [{ content: { parts: [{ text: JSON.stringify(GEMINI_REPLY) }] } }] }) }; }
  if (url.indexOf('sync-hint') !== -1) { HINTS.push({ url, headers: opt.headers || {}, body: JSON.parse(opt.payload) }); return { getResponseCode: () => 202, getContentText: () => '' }; }
  SENT.push(JSON.parse(opt.payload)); return { getResponseCode: () => 200, getContentText: () => '{"ok":true}' }; } };
ctx.ContentService = { createTextOutput: t => { const o = { t, setMimeType: () => o }; return o; }, MimeType: { JSON: 'json' } };
PROPS.BOT_TOKEN = 'x';
PROPS.AUTO_ZALO = 'pn,misa_ngay,misa_hd,misa_huy,web_loi,hd_lech'; // bật hết tin tự gửi để kiểm nội dung; cuối file kiểm mặc định tắt
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'Code.gs'), 'utf8') + '\n;this.parseMessage_=parseMessage_;this.handleSale_=handleSale_;this.knownCodes_=knownCodes_;this.handleText_=handleText_;this.handleNotify_=handleNotify_;this.doPost=doPost;this.queueSyncHint_=queueSyncHint_;this.appendNhap_=appendNhap_;this.receiptPrompt_=receiptPrompt_;this.handleStock_=handleStock_;this.invoiceTickets_=invoiceTickets_;this.invoiceStatus_=invoiceStatus_;this.doInvoice_=doInvoice_;this.invoiceMessage_=invoiceMessage_;this.invoiceReminderMessages_=invoiceReminderMessages_;this.handleExport_=handleExport_;this.flushSyncHints=flushSyncHints;this.weeklyInvoiceReminder=weeklyInvoiceReminder;', ctx);

let fail = 0, total = 0;
const eq = (name, got, want) => {
  total++;
  const g = JSON.stringify(got), w = JSON.stringify(want);
  if (g !== w) { fail++; console.log('❌ ' + name + '\n   got:  ' + g + '\n   want: ' + w); }
};
const parse = t => { const p = ctx.parseMessage_(t, ctx.knownCodes_()); return [p.action, p.code || p.baseCode, p.kho, p.price, p.sizes.map(s => s.size + 'x' + s.qty).join(' ')]; };

// ---- Phân tích tin nhắn ----
eq('kiểm hàng', parse('TH2040D 40'), ['KIỂM TRA HÀNG', 'TH2040D', '', '', '40x1']);
eq('mã không màu', parse('TH2040'), ['KIỂM TRA HÀNG', 'TH2040', '', '', '']);
// Mã dính size (tem quét AP048N-40, 19/10): tách mã + size
['ban TH2040D40 YEN', 'ban TH2040D-40 YEN', 'ban th2040d_40 yen', 'ban TH2040D/40 YEN', 'ban TH2040D.40 YEN'].forEach(t =>
  eq('mã dính size: ' + t, parse(t), ['BÁN', 'TH2040D', 'Y3C', '', '40x1']));
eq('mã dính size + kiểm hàng', parse('TH2040D-41'), ['KIỂM TRA HÀNG', 'TH2040D', '', '', '41x1']);
eq('mã gốc số đuôi không bị tách', parse('TH2040 40'), ['KIỂM TRA HÀNG', 'TH2040', '', '', '40x1']);
eq('bán k', parse('ban TH2040D 40 YEN 800k'), ['BÁN', 'TH2040D', 'Y3C', '800000', '40x1']);
eq('giá trước mã', parse('bán 800000 TH2040D 40 yen'), ['BÁN', 'TH2040D', 'Y3C', '800000', '40x1']);
eq('tr', parse('Bán TH2040D 40/2 3c 1tr2'), ['BÁN', 'TH2040D', 'Y3C', '1200000', '40x2']);
eq('40.2', parse('ban TH2040D 40.2 YEN'), ['BÁN', 'TH2040D', 'Y3C', '', '40x2']);
eq('40x2', parse('ban TH2040D 40x2 yen'), ['BÁN', 'TH2040D', 'Y3C', '', '40x2']);
eq('2 đôi 40', parse('ban TH2040D 2 đôi 40 yen'), ['BÁN', 'TH2040D', 'Y3C', '', '40x2']);
eq('40 sl 2', parse('ban TH2040D 40 sl 2 yen'), ['BÁN', 'TH2040D', 'Y3C', '', '40x2']);
eq('dải size', parse('nhap TH2040D 38-41 TBH'), ['NHẬP', 'TH2040D', '15E', '', '38x1 39x1 40x1 41x1']);
eq('giá 40.000', parse('ban TH2040D 40 YEN 40.000'), ['BÁN', 'TH2040D', 'Y3C', '40000', '40x1']);
eq('mã giống giá 119K', parse('ban 119K 40 tbh 500k'), ['BÁN', '119K', '15E', '500000', '40x1']);
eq('giá 119k sau mã', parse('ban TH2040D 40 yen 119k'), ['BÁN', 'TH2040D', 'Y3C', '119000', '40x1']);
eq('mã không số', parse('ban CXED 40 yen 300k'), ['BÁN', 'CXED', 'Y3C', '300000', '40x1']);
eq('mã ngắn', parse('T1D 39'), ['KIỂM TRA HÀNG', 'T1D', '', '', '39x1']);
eq('mã số+D', parse('ban 56307D 41/2 tbh 1.800.000đ'), ['BÁN', '56307D', '15E', '1800000', '41x2']);
eq('"bạn" không phải bán', parse('bạn ơi TH2040D 40 còn không'), ['KIỂM TRA HÀNG', 'TH2040D', '', '', '40x1']);
eq('huỷ', parse('Hủy')[0], 'HUỶ');
eq('báo cáo', parse('bc hom qua')[0], 'BÁO CÁO');
eq('hướng dẫn', parse('hd')[0], 'HƯỚNG DẪN');
const tr = ctx.parseMessage_('chuyen kho TH2040D 40 tu YEN den TBH', ctx.knownCodes_());
eq('chuyển kho', [tr.action, tr.khoFrom, tr.khoTo], ['CHUYỂN KHO', 'Y3C', '15E']);
const mv = ctx.parseMessage_('chuyen vi tri TH2040D YEN den K12', ctx.knownCodes_());
eq('chuyển vị trí', [mv.action, mv.kho, mv.location], ['CHUYỂN VỊ TRÍ', 'Y3C', 'K12']);

// ---- Cửa ghi bán (dry-run) ----
const sale = b => ctx.handleSale_(b, true);
let r = sale({ ticket_id: 'T1', channel: 'cua_hang', seller: 'A', lines: [{ code: 'TH2040D', size: 40, qty: 1, warehouse: 'Y3C', price: 800000 }, { code: 'th2040d', size: '41', qty: 2, warehouse: 'YEN' }] });
eq('phiếu hợp lệ', [r.ok, r.rows, r.results.map(x => x.stock_before)], [true, 2, [1, 2]]);
r = sale({ ticket_id: 'T2', channel: 'web', lines: [{ code: 'TH2040D', size: 40, warehouse: '15E' }] });
eq('cảnh báo tồn âm', [r.ok, !!r.results[0].warning], [true, true]);
r = sale({ ticket_id: 'T3', channel: 'shopee', lines: [{ code: 'KHONGCO1X', size: 40, warehouse: '15E' }, { code: 'TH2040D', warehouse: 'Y3C' }] });
eq('dòng lỗi → không ghi', [r.ok, r.results.map(x => x.error)], [false, ['mã không có trong KHOY3C/KHO15E', 'thiếu size']]);
r = sale({ ticket_id: 'T4', channel: 'web', lines: [{ code: 'AROMAX60T', qty: 3, warehouse: 'Y3C' }] });
eq('hàng không size', [r.ok, r.results[0].size, r.results[0].qty], [true, '', 3]);
eq('channel sai', sale({ ticket_id: 'T5', channel: 'instagram', lines: [{ code: 'TH2040D', size: 40, warehouse: 'Y3C' }] }).ok, false);
eq('ticket sai', sale({ ticket_id: 'a b', channel: 'web', lines: [{}] }).ok, false);
eq('qty sai', sale({ ticket_id: 'T6', channel: 'web', lines: [{ code: 'TH2040D', size: 40, qty: 0, warehouse: 'Y3C' }] }).ok, false);
PROPS['sale_T7'] = JSON.stringify({ t: Date.now(), rows: 1 });
r = sale({ ticket_id: 'T7', channel: 'web', lines: [{ code: 'TH2040D', size: 40, warehouse: 'Y3C' }] });
eq('chống trùng', [r.ok, r.duplicate], [true, true]);

// ---- Hàng không size: số lượng ----
const q = t => { const p = ctx.parseMessage_(t, ctx.knownCodes_()); return [p.code, p.sizes.length, p.qty]; };
eq('không size x2', q('ban AROMAX60T x2 YEN 70k'), ['AROMAX60T', 0, 2]);
eq('không size 2 cái', q('ban AROMAX60T 2 cái YEN'), ['AROMAX60T', 0, 2]);
eq('không size sl 3', q('ban AROMAX60T sl 3 YEN'), ['AROMAX60T', 0, 3]);
eq('không size /2', q('xuat AROMAX60T /2 Y3C'), ['AROMAX60T', 0, 2]);
eq('có size thì qty theo size', q('ban TH2040D 40x2 YEN'), ['TH2040D', 1, 0]);
let txt = ctx.handleText_('ban AROMAX60T x2 YEN 70k', true, '');
eq('không size ghi × 2', /không size × 2/.test(txt), true);

// ---- Nhiều dòng ----
txt = ctx.handleText_('ĐƠN WEB #123 — chị Lan\nban TH2040D 40 15E 800k\nban TH2040D 41/2 YEN 800k\nGhi chú: giao chiều', true, '');
eq('lô 2 lệnh, bỏ dòng thường', [/📋 2 lệnh — 2 ghi được/.test(txt), /1\) ✅ BÁN TH2040D/.test(txt), /2\) ✅ BÁN TH2040D/.test(txt)], [true, true, true]);
txt = ctx.handleText_('ban TH2040D 41 YEN\nban TH2040D 41 YEN\nban TH2040D 41 YEN', true, '');
eq('lô trừ tồn dần (tồn 2, bán 3 → dòng 3 cảnh báo)', [(txt.match(/tồn sẽ âm/g) || []).length], [1]);
txt = ctx.handleText_('ban TH2040D 40 YEN\nban KHONGMA 40 YEN', true, '');
eq('lô có dòng lỗi', /2 lệnh — 1 ghi được, 1 lỗi/.test(txt), true);
eq('tin 1 dòng như cũ', /^🧪 CHẠY THỬ — chưa ghi Sheet\n✅ BÁN TH2040D/.test(ctx.handleText_('ban TH2040D 40 YEN', true, '')), true);

// ---- Cửa báo đơn web ----
PROPS.WEBHOOK_KEY = 'webhookkey_123456'; PROPS.SALE_KEY = 'salekey_1234567890'; PROPS.WEB_NOTIFY_KEY = 'notifykey_1234567890'; PROPS.OWNER_CHAT_ID = 'OWNER1';
const post = (key, body) => JSON.parse(ctx.doPost({ parameter: { notify_key: key }, postData: { contents: JSON.stringify(body) } }).t);
SENT.length = 0;
eq('báo đơn sai khoá', post('sai', { order_id: 'W1', text: 'x' }).error, 'unauthorized');
let n = post('notifykey_1234567890', { order_id: 'W1', text: 'Đơn mới #W1\nban TH2040D 40 15E 800k' });
eq('báo đơn gửi tới OWNER, không ghi Sheet', [n.ok, SENT.length, SENT[0] && SENT[0].chat_id], [true, 1, 'OWNER1']);
n = post('notifykey_1234567890', { order_id: 'W1', text: 'lặp lại' });
eq('báo đơn chống trùng', [n.ok, n.duplicate, SENT.length], [true, true, 1]);
n = post('notifykey_1234567890', { order_id: 'W2', text: 'a'.repeat(5000) });
eq('báo đơn cắt bớt', [n.ok, n.truncated, SENT[1].text.length < 2000], [true, true, true]);
PROPS.WEB_NOTIFY_KEY = PROPS.SALE_KEY;
eq('khoá báo đơn trùng SALE_KEY → từ chối', /chưa cấu hình WEB_NOTIFY_KEY/.test(post(PROPS.SALE_KEY, { order_id: 'W3', text: 'x' }).error), true);

// ---- Trả hàng ----
const rp = t => { const p = ctx.parseMessage_(t, ctx.knownCodes_()); return [p.action, p.code, p.kho, !!p.returnGoods, p.sizes.map(x => x.size).join(',')]; };
eq('trả hàng không dấu', rp('nhap TH2040D 40 15E tra hang'), ['NHẬP', 'TH2040D', '15E', true, '40']);
eq('trả hàng có dấu', rp('Nhập TH2040D 41 YEN trả hàng'), ['NHẬP', 'TH2040D', 'Y3C', true, '41']);
eq('khách trả', rp('nhap TH2040D 40 15e khach tra'), ['NHẬP', 'TH2040D', '15E', true, '40']);
eq('nhập thường không phải trả', rp('nhap TH2040D 40 15E'), ['NHẬP', 'TH2040D', '15E', false, '40']);
eq('"tra hang" với lệnh bán → bỏ qua cờ', rp('ban TH2040D 40 15E tra hang')[3], false);
txt = ctx.handleText_('nhap TH2040D 40 15E tra hang', true, '');
eq('trả lời trả hàng', [/↩️ TRẢ HÀNG: nhập lại TH2040D/.test(txt), /không xuất phiếu nhập kho MISA/.test(txt)], [true, true]);
txt = ctx.handleText_('Khách đổi ý\nnhap TH2040D 40 15E tra hang\nban TH2040D 41 YEN 800k', true, '');
eq('trả hàng trong tin nhiều dòng', [/2 lệnh — 2 ghi được/.test(txt), /1\) ↩️ TRẢ HÀNG/.test(txt)], [true, true]);
const realAppend = ctx.appendByHeader_;
let captured = null;
ctx.appendByHeader_ = (sheet, values) => { captured = { sheet, values }; return { type: 'row', sheet, row: 99, written: Object.keys(values), check: {} }; };
ctx.appendNhap_('TH2040D', 'Đen', '40', 1, '15E', true);
eq('dòng NHAP trả hàng', [captured.sheet, /^TRA-\d{6}$/.test(captured.values['Số chứng từ (*)']), captured.values.web_stock, captured.values.web_label, captured.values.misa_stock, 'kho_sync' in captured.values],
  ['NHAP', true, 'Tra_hang', 'Tra_hang', 'Tra_hang', false]);
ctx.appendNhap_('TH2040D', 'Đen', '40', 1, '15E', false);
eq('dòng NHAP thường', [captured.values['Số chứng từ (*)'], captured.values.misa_stock], [undefined, 'Zalo_Update']);
ctx.appendByHeader_ = realAppend;

// ---- Cửa đánh dấu đã xuất file sàn ----
const ex = (b, dry) => ctx.handleExport_(Object.assign({ action: 'mark_exported' }, b), !!dry);
let r2 = ex({ channel: 'shopee', kind: 'upload', codes: ['th2040d', 'CXED', 'KHONGCO'], at: '2026-10-15T03:05:00Z' }, true);
eq('upload dry-run', [r2.ok, r2.written, r2.not_found, r2.value, WRITES.length], [true, 2, ['KHONGCO'], 'Done - 2026-10-15 10:05', 0]);
r2 = ex({ channel: 'tiktok', kind: 'upload', codes: ['TH2040N'], at: '2026-10-15T03:05:00Z' });
eq('upload ghi đúng ô tiktok_upload', [r2.written, WRITES[0] && WRITES[0].cells, WRITES[0] && WRITES[0].v], [1, ['D4'], 'Done - 2026-10-15 10:05']);
r2 = ex({ channel: 'tiktok', kind: 'upload', codes: ['TH2040N'], at: '2026-10-15T03:05:00Z' });
eq('upload chống trùng', [r2.duplicate, WRITES.length], [true, 1]);
r2 = ex({ channel: 'shopee', kind: 'update', at: '2026-10-15T04:00:00Z' });
eq('update ghi META theo key', [r2.ok, r2.cell, WRITES[1] && WRITES[1].cell, WRITES[1] && WRITES[1].v, WRITES[2] && WRITES[2].cell], [true, 'META!B2', [2, 2], '2026-10-15 11:00', [2, 3]]);
DATA.META = [['key', 'value', 'updated_at'], ['tiktok_last_update', 'x', 'y']];
r2 = ex({ channel: 'shopee', kind: 'update', at: '2026-10-15T05:00:00Z' });
eq('META chưa có dòng key → thêm dòng cuối', [r2.ok, r2.cell, WRITES[3] && WRITES[3].cell, WRITES[3] && WRITES[3].v], [true, 'META!B3', [3, 1], 'shopee_last_update']);
const nW0 = WRITES.length;
r2 = ex({ channel: 'tiktok', kind: 'update', stock_included: false });
eq('update không có cột tồn → không ghi mốc', [r2.ok, /không có cột tồn/.test(r2.error), WRITES.length], [false, true, nW0]);
eq('channel sai', ex({ channel: 'lazada', kind: 'upload', codes: ['TH2040D'] }).ok, false);
eq('kind sai', ex({ channel: 'shopee', kind: 'x', codes: ['TH2040D'] }).ok, false);
eq('upload thiếu codes', ex({ channel: 'shopee', kind: 'upload', codes: [] }).ok, false);
eq('action sai', ctx.handleExport_({ action: 'x', channel: 'shopee', kind: 'update' }, true).ok, false);
const nW = WRITES.length;
delete DATA.META;
eq('chưa có tab META → báo lỗi, không ghi', [/chưa có tab META/.test(ex({ channel: 'tiktok', kind: 'update' }).error), WRITES.length], [true, nW]);

// ---- Hoá đơn nhà cung cấp ----
ctx.MEMO = {};
let tks = ctx.invoiceTickets_();
eq('gom phiếu ngày + NCC + kho (bỏ KHO trống, TRA-, SL 0)', tks.map(t => [t.id, t.qty, t.amount]),
  [['260920-TP-15E', 3, 1500000], ['260910-TP-15E', 3, 1500000], ['260910-TP-Y3C', 1, 500000], ['260805-TP-15E', 1, 500000]]);
let ist = ctx.invoiceStatus_(ctx.invoiceTickets_()).tickets;
eq('hoá đơn 12/09 ghép phiếu gần nhất trước đó (10/09), không ghép phiếu 05/08', ist.map(t => t.id + ':' + t.status), ['260920-TP-15E:chua', '260910-TP-15E:da', '260910-TP-Y3C:chua', '260805-TP-15E:chua']);
txt = ctx.doInvoice_('hoadon', true).text;
eq('danh sách chỉ phiếu từ 01/09 chưa có', [/PHIẾU NHẬP KHO CHƯA CÓ HOÁ ĐƠN MUA HÀNG: 2/.test(txt), /260920-TP-15E/.test(txt), /260910-TP-Y3C/.test(txt), /260805/.test(txt)], [true, true, true, false]);
PROPS.HKD_15E = 'HKD A | 0312345678 | 15E Tăng Bạt Hổ';
txt = ctx.doInvoice_('hoadon 260920-tp-15e', true).text;
eq('câu nhắn soạn sẵn ghi rõ hộ + MST + hàng gọn theo mã cha', [/Đơn vị mua: HKD A/.test(txt), /MST: 0312345678/.test(txt), /\nTH2040 x 3\n/.test(txt), /Tổng: 3 sản phẩm\n/.test(txt), /×|\d\.000đ/.test(txt.split('Hàng hoá:')[1]), /kho 15E/.test(txt)], [true, true, true, true, false, true]);
txt = ctx.invoiceMessage_(ctx.invoiceTickets_().find(t => t.id === '260910-TP-15E'));
eq('gom 2 màu cùng mã cha (TH2040D 2 + TH2040N 1)', /\nTH2040 x 3\nTổng: 3 sản phẩm/.test(txt), true);
txt = ctx.doInvoice_('hoadon 260920-TP-15E da', false).text;
eq('ghi đã nhận tay', [/Đã ghi ✅ đã có hoá đơn: 260920-TP-15E/.test(txt), JSON.parse(PROPS['hdon_260920-TP-15E']).s], [true, 'da']);
ctx.doInvoice_('hoadon 260910-TP-Y3C khong', false);
eq('hết phiếu chưa có', /Không còn phiếu nào/.test(ctx.doInvoice_('hoadon', true).text), true);
eq('mã phiếu sai', /Không có phiếu đúng mã/.test(ctx.doInvoice_('hoadon 999999', true).text), true);
eq('lệnh hoadon nhận dạng', [ctx.parseMessage_('hoá đơn').action, ctx.parseMessage_('Hoadon 260920 da').action], ['HOÁ ĐƠN NCC', 'HOÁ ĐƠN NCC']);

// ---- Kênh bán trong lệnh ban ----
const chOf = t => ctx.parseMessage_(t, ctx.knownCodes_()).channel;
eq('ban tại quầy → channel trống', chOf('ban TH2040D 40 YEN 800k'), '');
eq('ban shopee / tiktok / web', [chOf('ban TH2040D 40 YEN shopee'), chOf('bán TH2040D 40 15E TikTok 800k'), chOf('ban TH2040D 40 yen web')], ['shopee', 'tiktok', 'web']);
eq('ban lazada / zalo / fb', [chOf('ban TH2040D 40 YEN lazada'), chOf('ban TH2040D 40 YEN zalo'), chOf('ban TH2040D 40 YEN fb')], ['lazada', 'zalo', 'facebook']);
eq('chữ kênh không lẫn vào mã', ctx.parseMessage_('ban TH2040D 40 YEN shopee', ctx.knownCodes_()).code, 'TH2040D');
const realAB = ctx.appendByHeader_;
let banOpt = null;
ctx.appendByHeader_ = (sheet, values, fb, check, optional) => { if (sheet === 'BAN') banOpt = optional; return { type: 'row', sheet, row: 9, written: Object.keys(values), check: check || {} }; };
ctx.handleText_('ban TH2040D 40 YEN', false, 'chat1', 'Lan');
eq('Zalo bán tại quầy ghi channel trống', [banOpt.channel, banOpt.seller], ['', 'Lan']);
ctx.handleText_('ban TH2040D 40 YEN shopee', false, 'chat1', 'Lan');
eq('Zalo bán shopee ghi channel=shopee', banOpt.channel, 'shopee');
ctx.appendByHeader_ = realAB;

ctx.appendByHeader_ = (sheet, values, fb, check, optional) => { if (sheet === 'BAN') banOpt = optional; return { type: 'row', sheet, row: 9, written: Object.keys(values), check: check || {} }; };
banOpt = null; ctx.handleSale_({ ticket_id: 'CH1', channel: 'cua_hang', seller: 'nv', lines: [{ code: 'TH2040D', size: 40, warehouse: 'Y3C' }] }, false);
eq('app cua_hang → ghi channel trống', banOpt && banOpt.channel, '');
banOpt = null; ctx.handleSale_({ ticket_id: 'CH2', channel: 'lazada', seller: 'nv', lines: [{ code: 'TH2040D', size: 40, warehouse: 'Y3C' }] }, false);
eq('app lazada → channel lazada', banOpt && banOpt.channel, 'lazada');
ctx.appendByHeader_ = realAB;

// ---- Cửa kho cho app ----
DATA.XUAT = [['Ngày', 'product_code', 'product_color', 'KHO', 'item_size', 'item_quantity', 'FSKU']];
const stk = (b, dry) => ctx.handleStock_(Object.assign({ seller: 'nv@hn.vn' }, b), !!dry);
let sr = stk({ action: 'xuat', ticket_id: 'S1', lines: [{ code: 'TH2040D', size: 41, qty: 3, warehouse: 'Y3C' }] }, true);
eq('xuất dry-run cảnh báo tồn âm', [sr.ok, sr.dry_run, sr.results[0].warehouse, /tồn 2, xuất 3/.test(sr.results[0].warnings[0])], [true, true, 'Y3C', true]);
sr = stk({ action: 'nhap', ticket_id: 'S2', lines: [{ code: 'TH2040D', size: 40, qty: 1, warehouse: '15E' }, { code: 'KHONGCO9X', size: 40, warehouse: '15E' }] }, true);
eq('dòng lỗi → không ghi dòng nào', [sr.ok, sr.results.map(x => x.ok), /không có trong SANPHAM/.test(sr.results[1].error)], [false, [true, false], true]);
eq('thiếu seller', /thiếu seller/.test(ctx.handleStock_({ action: 'nhap', ticket_id: 'S3', lines: [{}] }, true).error), true);
eq('action sai', ctx.handleStock_({ action: 'ban', ticket_id: 'S3', seller: 'a' }, true).ok, false);
sr = stk({ action: 'chuyen_kho', ticket_id: 'S4', from: 'YEN', to: 'TBH', lines: [{ code: 'TH2040D', size: 40, qty: 1 }] }, true);
eq('chuyển kho dry-run', [sr.ok, sr.results[0].from, sr.results[0].to], [true, 'Y3C', '15E']);
eq('chuyển kho cùng kho → lỗi', stk({ action: 'chuyen_kho', ticket_id: 'S5', from: '15E', to: 'TBH', lines: [{ code: 'TH2040D', size: 40 }] }, true).ok, false);
sr = stk({ action: 'chuyen_vi_tri', ticket_id: 'S6', warehouse: 'Y3C', location: 'th2', lines: [{ code: 'TH2040D' }] }, true);
eq('chuyển vị trí TH2 (thùng)', [sr.ok, sr.results[0].location], [true, 'TH2']);
eq('chuyen_vi_tri: dòng khác kho phiếu → từ chối', /phiếu ghi kho Y3C/.test(stk({ action: 'chuyen_vi_tri', ticket_id: 'S7b', warehouse: 'Y3C', location: 'B1', lines: [{ code: 'TH2040D', warehouse: '15E' }] }, true).results[0].error), true);
eq('vị trí sai dạng', /vị trí phải dạng/.test(stk({ action: 'chuyen_vi_tri', ticket_id: 'S7', warehouse: 'Y3C', location: 'X9', lines: [{ code: 'TH2040D' }] }, true).results[0].error), true);
// Ghi thật xuất + chống trùng + huỷ
const xuatLen = DATA.XUAT.length;
sr = stk({ action: 'xuat', ticket_id: 'S8', lines: [{ code: 'TH2040D', size: 41, qty: 1, warehouse: 'Y3C' }] });
eq('xuất ghi thật 1 dòng XUAT', [sr.ok, sr.dry_run, sr.results[0].rows, DATA.XUAT.length, !!sr.undo_until], [true, false, ['XUAT!2'], xuatLen + 1, true]);
eq('gửi lại cùng ticket → duplicate', stk({ action: 'xuat', ticket_id: 'S8', lines: [{ code: 'TH2040D', size: 41, warehouse: 'Y3C' }] }).duplicate, true);
eq('người khác không huỷ được', /chính mình/.test(ctx.handleStock_({ action: 'huy', ticket_id: 'U0', seller: 'khac@hn.vn', undo_ticket_id: 'S8' }, false).error), true);
sr = stk({ action: 'huy', ticket_id: 'U1', undo_ticket_id: 'S8' });
eq('huỷ của chính mình → xoá ô đã ghi', [sr.ok, DATA.XUAT[1][1]], [true, '']);
sr = stk({ action: 'huy', ticket_id: 'U2', undo_ticket_id: 'S8' });
eq('huỷ lần 2 → không còn gì', [sr.ok, /không có thao tác/.test(sr.error)], [false, true]);
// Trả hàng ghi NHAP TRA-
const nhapLen = DATA.NHAP.length;
sr = stk({ action: 'tra_hang', ticket_id: 'S9', lines: [{ code: 'TH2040D', size: 40, qty: 1, warehouse: '15E' }] });
if (!sr.ok) console.log(JSON.stringify(sr));
const newRow = DATA.NHAP[nhapLen] || [];
eq('trả hàng ghi NHAP TRA-', [sr.ok, /^TRA-\d{6}$/.test(newRow[1]), newRow[2], newRow[4]], [true, true, 'TH2040D', '15E']);

// ---- Nhập từ phiếu NCC ----
PROPS.GEMINI_API_KEY = 'g';
DATA.BAN = DATA.BAN || [['Ngày', 'product_code', 'product_color', 'Giá', 'item_size', 'item_quantity', 'KHO', 'FSKU', 'channel', 'seller']];
const pn = (b, dry) => ctx.handleStock_(Object.assign({ nguoi: 'kris@hn.vn' }, b), !!dry);
let pr = pn({ action: 'doc_phieu', anh_base64: Buffer.from('anh-phieu').toString('base64'), mime: 'image/jpeg', nguon: 'app' });
eq('đọc phiếu → nháp', [pr.ok, pr.ncc_ten, pr.so_phieu, pr.so_dong, pr.so_doi, pr.trang_thai, GEMINI_CALLS], [true, 'Tuấn Phong', 'PX2898', 2, 5, 'cho_chia', 1]);
const pid = pr.id;
const unsplit = PN_ROOT.kids.find(k => k.name === 'Chưa chia');
eq('ảnh + dữ liệu vào "Chưa chia/Tuấn Phong"', [!!unsplit, unsplit && unsplit.kids[0].name, Object.values(DFILES).filter(f => f.name.indexOf(pid) === 0).length], [true, 'Tuấn Phong', 2]);
eq('ds_nhap', pn({ action: 'ds_nhap' }).phieu.map(x => [x.id, x.ncc_ten, x.so_doi, x.trang_thai]), [[pid, 'Tuấn Phong', 5, 'cho_chia']]);
let pv = pn({ action: 'xem_nhap', id: pid });
eq('xem_nhap không trả giá', [pv.dong.length, pv.dong[0].sl_phieu, 'don_gia' in pv.dong[0], JSON.stringify(pv).indexOf('445000')], [2, 3, false, -1]);
eq('xem_nhap kem_gia: nhân viên → không có giá', ['don_gia' in pn({ action: 'xem_nhap', id: pid, kem_gia: true }).dong[0]], [false]);
eq('xem_nhap kem_gia: Chủ → có giá', pn({ action: 'xem_nhap', id: pid, kem_gia: true, nguoi: 'LTCKha@gmail.com' }).dong[0].don_gia, 445000);
eq('xem_nhap kem_anh', !!pn({ action: 'xem_nhap', id: pid, kem_anh: true }).anh_base64, true);
pr = pn({ action: 'xac_nhan', id: pid, ticket_id: 'X1', dong: [{ dong: 1, ma_hnc: 'TH2040D', kho: '15E', sizes: { '40': 2 } }, { dong: 2, ma_hnc: 'TH2040N', kho: '15E', sizes: { '41': 2 } }] }, true);
eq('lệch SL không lý do → lỗi', [pr.ok, pr.loi_dong && pr.loi_dong[0].dong], [false, 1]);
pr = pn({ action: 'xac_nhan', id: pid, ticket_id: 'X1', dong: [{ dong: 1, ma_hnc: 'TH2040D', kho: '15E', sizes: { '40': 2 }, ly_do: 'thieu' }, { dong: 2, ma_hnc: 'KHONGCO1X', kho: '15E', sizes: { '41': 2 } }] }, true);
eq('mẫu mới (chưa có SANPHAM) → chặn', [pr.ok, pr.results[1].error], [false, 'mã không có trong SANPHAM / KHO']);
pr = pn({ action: 'xac_nhan', id: pid, ticket_id: 'X1', dong: [{ dong: 1, ma_hnc: 'TH2040D', kho: '15E', sizes: { '40': 2 }, ly_do: 'thieu' }, { dong: 2, ma_hnc: 'TH2040N', kho: 'Y3C', sizes: { '41': 2 } }] }, true);
eq('dry-run có lý do → ok + cảnh báo', [pr.ok, pr.dry_run, pr.canh_bao.length, pr.results.map(r => r.dong_phieu)], [true, true, 1, [1, 2]]);
const nhLen = DATA.NHAP.length;
pr = pn({ action: 'xac_nhan', id: pid, ticket_id: 'X1', dong: [{ dong: 1, ma_hnc: 'TH2040D', kho: '15E', sizes: { '40': 2 }, ly_do: 'thieu' }, { dong: 2, ma_hnc: 'TH2040N', kho: 'Y3C', sizes: { '41': 2 } }] });
if (!pr.ok) console.log(JSON.stringify(pr));
const added = DATA.NHAP.slice(nhLen);
eq('ghi NHAP: số chứng từ NK theo kho, không đánh dấu Zalo', [pr.ok, added.length, added.map(r => r[4] + ':' + r[1]), pr.so_chung_tu, added.every(r => !r[10]), !!pr.undo_until],
  [true, 2, ['15E:NK000001', 'Y3C:NK000001'], { '15E': 'NK000001', Y3C: 'NK000001' }, true, true]);
eq('phiếu → da_ghi', pn({ action: 'ds_nhap' }).phieu[0].trang_thai, 'da_ghi');
const hn = PN_ROOT.kids.find(k => k.name === 'Hải Nancy'), yl = PN_ROOT.kids.find(k => k.name === 'Yen Leather');
const inFolder = f => Object.values(DFILES).filter(x => f && x.folder === f.kids[0].getId()).map(x => x.name.split('.').pop()).sort();
eq('ảnh sang thư mục 2 hộ', [inFolder(hn), inFolder(yl)], [['jpg', 'json'], ['jpg']]);
ctx.MEMO = {};
const invTk = ctx.invoiceTickets_().find(t => t.kho === '15E' && t.ncc_docs && t.ncc_docs.length);
eq('hoá đơn: phiếu × kho có NCC + số phiếu NCC', [invTk && invTk.supplier, invTk && invTk.ncc_docs], ['Tuấn Phong', ['PX2898']]);
eq('câu nhắn hoá đơn ghi số phiếu NCC', /theo phiếu xuất PX2898/.test(ctx.invoiceMessage_(invTk)), true);
eq('học bảng ghép mã', pn({ action: 'xem_nhap', id: pid }).dong[0].goi_y_ma_hnc, 'TH2040D');
eq('người khác không huỷ được', /chính mình/.test(ctx.handleStock_({ action: 'huy_nhap', ticket_id: 'X1', nguoi: 'khac@hn.vn' }, false).error), true);
pr = pn({ action: 'huy_nhap', ticket_id: 'X1' });
eq('huỷ → xoá ô NHAP, phiếu về chờ chia', [pr.ok, added.every(r => r[2] === ''), pn({ action: 'ds_nhap' }).phieu[0].trang_thai], [true, true, 'cho_chia']);
eq('bỏ phiếu nháp', pn({ action: 'bo_nhap', id: pid }).trang_thai, 'huy');
eq('ds_nhap ẩn phiếu đã bỏ', pn({ action: 'ds_nhap' }).phieu.length, 0);
eq('prompt có danh sách NCC', /Tuấn Phong/.test(ctx.receiptPrompt_(['Tuấn Phong', 'Chú Dũng'])), true);

// ---- Nhập từ phiếu V2: tách màu, mã mới tạo SANPHAM + KHO ----
// SANPHAM thêm cột:            7               8              9                10             11              12               13      14           15                    16          17
DATA.SANPHAM[1].push('product_color', 'product_name', 'Tên Ngành Hàng', 'product_unit', 'product_price', 'purchase_price', 'Size', 'Giới tính', 'product_category_id', 'Đặc điểm', 'product_origin');
DATA.SANPHAM.push(['TH2040', 'TH2040X', '', '', 'Tuấn Phong', '', '=CONCATENATE(R[0]C[-5])', 'Xám', '=R[0]C[-2]', 'Giày tây nam', 'Đôi', 900000, 500000,
  '=IF(R[0]C[1]="male";"38,39";"35,36")', '=IF(REGEXMATCH(R[0]C[-5];"nam");"male";"female")', '=INDEX(SUB!A:B;1;1)', 'cột dây', 'Việt Nam']);
DATA.SUB[0][0] = 'Tên Ngành Hàng';
GEMINI_REPLY = { ncc: 'Chú Dũng', so_phieu: 'PX3000', ngay: '2026-10-15', dong: [{ ma_ncc: '32837', mo_ta: 'Giày mọi da', sl: 12, don_gia: 400000 }, { ma_ncc: 'TH', mo_ta: 'Giày tây', sl: 1, don_gia: 500000 }], tong_sl: 13, tong_tien: 5300000 };
GEMINI_CALLS = 0;
const SENT0 = SENT.length;
PROPS.OWNER_CHAT_ID = 'owner1';
PROPS.SYNC_HINT_URL = 'https://giayhainancy.vn/api/sync-hint';
pr = pn({ action: 'doc_phieu', anh_base64: Buffer.from('anh-2').toString('base64'), mime: 'image/jpeg' });
const p2 = pr.id;
eq('V2 đọc phiếu: model 2.5 trước + Zalo báo phiếu chờ chia', [pr.ok, pr.model, GEMINI_CALLS, SENT.length - SENT0, /Có phiếu nhập kho chờ chia: Chú Dũng PX3000 · 2 dòng · 13 đôi → https:\/\/giayhainancy\.vn\/admin\/app#phieu-PN/.test((SENT[SENT0] || {}).text || '')],
  [true, 'gemini-2.5-flash', 1, 1, true]);
const sz = o => o; // sizes
const v2 = {
  action: 'xac_nhan', id: p2, ticket_id: 'V2A',
  dong: [
    { dong: 1, ma_hnc: '32837D', kho: '15E', sizes: { '38': 1, '39': 1, '40': 1 } },
    { dong: 1, ma_hnc: '32837D', kho: 'Y3C', sizes: { '41': 1, '42': 1, '43': 1 } },
    { dong: 1, ma_hnc: '32837N', kho: '15E', sizes: { '38': 2, '40': 1 } },
    { dong: 1, ma_hnc: '32837N', kho: 'Y3C', sizes: { '44': 3 } },
    { dong: 2, ma_hnc: 'TH2040N', kho: 'Y3C', sizes: { '43': 1 } },
  ],
  ma_moi: [{ ma_hnc: '32837D', ma_goc: '32837', mau: 'Đen', gia_ban: 1200000, day_size: ['38', '39', '40', '41', '42', '43', '44'] },
    { ma_hnc: '32837N', mau: 'Nâu', gia_ban: '1.200.000', day_size: ['38', '39', '40', '41', '42', '43', '44'] }],
};
pr = pn(Object.assign({}, v2, { ma_moi: undefined }), true);
eq('V2 không cờ mã mới → chặn mã chưa có', [pr.ok, pr.results && pr.results.filter(r => !r.ok).length], [false, 9]);
pr = pn(Object.assign({}, v2, { ma_moi: [{ ma_hnc: '32837D', mau: 'Đen' }] }), true);
eq('V2 mã mới thiếu giá bán → lỗi', [pr.ok, /thiếu giá bán/.test(pr.loi_dong[0].error)], [false, true]);
pr = pn(Object.assign({}, v2, { ma_moi: [{ ma_hnc: '32837D', mau: 'Đen', gia_ban: 900000, nganh: 'Giày bay' }] }), true);
eq('V2 ngành không có trong SUB → lỗi', [pr.ok, /không có trong SUB/.test(pr.loi_dong[0].error)], [false, true]);
pr = pn(Object.assign({}, v2, { ma_moi: [{ ma_hnc: '32837D', mau: '', gia_ban: 900000 }] }), true);
eq('V2 mã mới thiếu màu → lỗi', [pr.ok, pr.loi_dong && pr.loi_dong[0].error], [false, 'thiếu màu (mau)']);
pr = pn(Object.assign({}, v2, { ma_moi: [{ ma_hnc: 'ABCD', mau: 'Đen', gia_ban: 900000 }] }), true);
eq('V2 mã mới không dùng trong dòng nào → lỗi', [pr.ok, /không có trong dòng chia/.test(pr.loi_dong[0].error)], [false, true]);
pr = pn(Object.assign({}, v2, { dong: v2.dong.slice(1) }), true);
eq('V2 tổng mọi màu × kho lệch SL phiếu → bắt lý do', [pr.ok, pr.loi_dong && pr.loi_dong[0].dong], [false, 1]);
const spLen = DATA.SANPHAM.length, k15 = DATA.KHO15E.length, ky3 = DATA.KHOY3C.length, nh2 = DATA.NHAP.length, w0 = WRITES.length;
pr = pn(v2, true);
eq('V2 chạy thử: tạo 2 SANPHAM, 2 kho × 7 size + 1 dòng KHO thiếu, số NK, không ghi', [pr.ok, pr.tao_moi.sanpham, pr.tao_moi.kho.length, pr.tao_moi.kho.indexOf('Y3C TH2040N 43') !== -1, pr.so_chung_tu, WRITES.length - w0],
  [true, ['32837D', '32837N'], 29, true, { '15E': 'NK000001', Y3C: 'NK000001' }, 0]);
pr = pn(v2);
if (!pr.ok) console.log(JSON.stringify(pr));
const spNew = DATA.SANPHAM.slice(spLen);
eq('V2 SANPHAM tối thiểu: mã, màu, giữ công thức tên, giá bán + giá nhập theo phiếu, size = dãy size, ngành trống → giới tính / danh mục trống',
  [spNew.length, spNew.map(r => r[1]), spNew.map(r => r[7]), spNew[0][8], spNew[0][0], spNew[0][6], spNew[0][10], spNew.map(r => r[11]), spNew[0][12], spNew[0][13], spNew[0][14], spNew[0][15], spNew[0][9], spNew[0][17], spNew[0][4]],
  [2, ['32837D', '32837N'], ['Đen', 'Nâu'], '=R[0]C[-2]', '32837', '=CONCATENATE(R[0]C[-5])', 'Đôi', [1200000, 1200000], 400000, '38,39,40,41,42,43,44', '', '', '', 'Việt Nam', 'Chú Dũng']);
const kNew = DATA.KHO15E.slice(k15);
eq('V2 KHO15E: 14 dòng tồn đầu 0 + công thức theo tên cột', [kNew.length, kNew[0].slice(1, 5), kNew[0][0], kNew[0][5]],
  [14, ['32837D', 'Đen', 38, 0], '=CONCATENATE($A$1;B' + (k15 + 1) + ';D' + (k15 + 1) + ')',
   '=E' + (k15 + 1) + ' + SUMIF(NHAP!H:H; A' + (k15 + 1) + '; NHAP!G:G) - SUMIF(XUAT!G:G; A' + (k15 + 1) + '; XUAT!F:F) - SUMIF(BAN!H:H; A' + (k15 + 1) + '; BAN!F:F)']);
eq('V2 KHOY3C: 14 dòng mã mới + TH2040N 43 (mã cũ thiếu size)', [DATA.KHOY3C.filter(r => /^32837[DN]$/.test(r[1])).length, DATA.KHOY3C.filter(r => r[1] === 'TH2040N' && r[3] === 43 && r[4] === 0).length], [14, 1]);
const nNew = DATA.NHAP.filter(r => r[1] === 'NK000001'); // dòng đã huỷ trước đó được dùng lại → lọc theo số chứng từ
eq('V2 NHAP: 10 dòng size, số chứng từ NK theo kho', [pr.ok, nNew.length, nNew.reduce((t, r) => t + Number(r[6]), 0), pr.so_chung_tu], [true, 10, 13, { '15E': 'NK000001', Y3C: 'NK000001' }]);
eq('V2 sync: SANPHAM + 2 kho + NHAP', pr._sync.slice().sort(), ['KHO15E', 'KHOY3C', 'NHAP', 'SANPHAM']);
eq('V2 học mã gốc khi tách màu', pn({ action: 'xem_nhap', id: p2 }).dong.map(x => x.goi_y_ma_hnc), ['32837', 'TH2040N']);
pr = pn({ action: 'huy_nhap', ticket_id: 'V2A' });
eq('V2 huỷ: xoá NHAP + dòng SANPHAM / KHO mới', [pr.ok, nNew.every(r => r[2] === ''), spNew.every(r => r[1] === '' && r[6] === ''), kNew.every(r => r[1] === '' && r[0] === ''), pn({ action: 'ds_nhap' }).phieu[0].trang_thai],
  [true, true, true, true, 'cho_chia']);
// Mã mới đã có giao dịch khác → không huỷ
pr = pn(Object.assign({}, v2, { ticket_id: 'V2B' }));
DATA.XUAT.push(['16/10/2026', '32837D', 'Đen', '15E', 38, 1, '']);
pr = pn({ action: 'huy_nhap', ticket_id: 'V2B' });
eq('V2 mã mới đã xuất → không huỷ', [pr.ok, /32837D size 38 kho 15E đã có giao dịch khác \(XUAT/.test(pr.error)], [false, true]);
DATA.XUAT.pop();
r2 = ex({ channel: 'shopee', kind: 'upload', codes: ['32837D', 'TH2040X'], at: '2026-10-16T03:05:00Z' }, true);
eq('mark_exported bỏ qua mã cần bổ sung (trống ngành)', [r2.ok, r2.written, r2.chua_bo_sung], [true, 1, ['32837D']]);
// Cùng kho + cùng NCC + cùng ngày → dùng chung số NK; Chủ huỷ sau 10 phút
const spRow = DATA.SANPHAM.findIndex(r => r[1] === '32837D');
// bo_sung_sp: chỉ cột cho phép, ngành theo SUB, khôi phục công thức giới tính / danh mục
const bs = (b, dry) => ctx.handleStock_(Object.assign({ action: 'bo_sung_sp', nguoi: 'kha@hn.vn', product_code: '32837D' }, b), !!dry);
let bf = bs({ cot: { 'Tên Ngành Hàng': 'Giày mọi nam', 'product_name': 'x' } }, true);
eq('bo_sung_sp: cột ngoài danh sách → lỗi, không ghi', [bf.ok, bf.loi], [false, ['cột "product_name" không được sửa']]);
bf = bs({ cot: { 'Tên Ngành Hàng': 'Giày bay' } }, true);
eq('bo_sung_sp: ngành không có trong SUB → lỗi', [bf.ok, /không có trong SUB/.test(bf.loi[0])], [false, true]);
bf = bs({ cot: { 'Tên Ngành Hàng': 'Giày mọi nam', 'Đặc điểm ': 'xỏ chân' } });
eq('bo_sung_sp: ghi ngành + đặc điểm, khôi phục công thức, hết cần bổ sung', [bf.ok, bf.da_ghi, bf.can_bo_sung, DATA.SANPHAM[spRow][9], DATA.SANPHAM[spRow][16], DATA.SANPHAM[spRow][14], DATA.SANPHAM[spRow][15], bf._sync],
  [true, ['Tên Ngành Hàng', 'Đặc điểm', 'Giới tính', 'product_category_id'], false, 'Giày mọi nam', 'xỏ chân', '=IF(REGEXMATCH(R[0]C[-5];"nam");"male";"female")', '=INDEX(SUB!A:B;1;1)', ['SANPHAM']]);
r2 = ex({ channel: 'shopee', kind: 'upload', codes: ['32837D'], at: '2026-10-16T03:06:00Z' }, true);
eq('đủ thông tin → mark_exported đánh dấu', [r2.written, r2.chua_bo_sung], [1, []]);
GEMINI_REPLY = { ncc: 'Chú Dũng', so_phieu: 'PX3001', ngay: '2026-10-16', dong: [{ ma_ncc: 'CXE', mo_ta: 'Giày', sl: 1, don_gia: 300000 }], tong_sl: 1, tong_tien: 300000 };
let p3 = pn({ action: 'doc_phieu', anh_base64: Buffer.from('anh-4').toString('base64') }).id;
pr = pn({ action: 'xac_nhan', id: p3, ticket_id: 'V3', dong: [{ dong: 1, ma_hnc: 'CXED', kho: 'Y3C', sizes: { '40': 1 } }] }, true);
eq('cùng kho + cùng NCC + cùng ngày → dùng chung số NK', pr.so_chung_tu, { Y3C: 'NK000001' });
GEMINI_REPLY.ncc = 'Tuấn Phong';
p3 = pn({ action: 'doc_phieu', anh_base64: Buffer.from('anh-5').toString('base64') }).id;
pr = pn({ action: 'xac_nhan', id: p3, ticket_id: 'V4', dong: [{ dong: 1, ma_hnc: 'TH2040D', kho: 'Y3C', sizes: { '40': 1 } }] }, true);
eq('khác NCC → số lớn nhất của kho + 1', pr.so_chung_tu, { Y3C: 'NK000002' });
pr = pn({ action: 'huy_nhap', ticket_id: 'V2B', id: p2, nguoi: 'khac@hn.vn' });
eq('quá 10 phút / người khác, không phải Chủ → không huỷ', pr.ok, false);
delete CACHE.stkops_V2B; // giả lập quá 10 phút
pr = pn({ action: 'huy_nhap', ticket_id: 'V2B', id: p2, nguoi: 'chu@hn.vn', chu: true });
eq('Chủ huỷ sau 10 phút → xoá hết dòng của phiếu, phiếu về chờ chia', [pr.ok, pr.so_dong, DATA.NHAP.filter(r => r[1] === 'NK000001').length, DATA.SANPHAM.filter(r => /^32837/.test(r[1])).length, pn({ action: 'ds_nhap' }).phieu[0].trang_thai],
  [true, 41, 0, 0, 'cho_chia']);
// Gemini hết lượt
const realFetch = ctx.UrlFetchApp.fetch;
ctx.UrlFetchApp.fetch = (url, opt) => (url.indexOf('generativelanguage') !== -1 ? { getResponseCode: () => 429, getContentText: () => '' } : realFetch(url, opt));
pr = pn({ action: 'doc_phieu', anh_base64: Buffer.from('anh-3').toString('base64') });
eq('Gemini hết lượt → báo lỗi rõ', [pr.ok, /hết lượt miễn phí/.test(pr.error)], [false, true]);
ctx.UrlFetchApp.fetch = realFetch;
// Zalo không nhận ảnh phiếu nữa
PROPS.WEBHOOK_KEY = PROPS.WEBHOOK_KEY || 'wk_12345';
const g0 = GEMINI_CALLS, s1 = SENT.length;
ctx.doPost({ parameter: { key: PROPS.WEBHOOK_KEY }, postData: { contents: JSON.stringify({ event_name: 'message.image.received', message: { chat: { id: 'owner1' }, message_id: 'img1', photo_url: 'https://x/y.jpg' } }) } });
eq('Zalo gửi ảnh → bỏ qua, không gọi Gemini', [GEMINI_CALLS - g0, SENT.length - s1], [0, 0]);
delete PROPS.SYNC_HINT_URL;

// ---- Báo web chép Sheet ----
ctx.queueSyncHint_(['BAN']);
eq('chưa cấu hình URL → không gửi', HINTS.length, 0);
delete CACHE.sync_q;
PROPS.SYNC_HINT_URL = 'https://web.example/api/sync-hint'; PROPS.SYNC_HINT_KEY = 'synckey_1234567890';
ctx.queueSyncHint_(['BAN']);
eq('BAN đổi → gửi kèm KHO15E, KHOY3C; khoá ở header, không ở URL', [HINTS.length, HINTS[0] && HINTS[0].body.tabs, HINTS[0] && HINTS[0].headers['x-sync-key'], /synckey/.test(HINTS[0] && HINTS[0].url)],
  [1, ['KHO15E', 'KHOY3C', 'BAN'], 'synckey_1234567890', false]);
ctx.queueSyncHint_(['SANPHAM']);
ctx.queueSyncHint_(['SUB']);
eq('trong 60 giây → gộp, chưa gửi', HINTS.length, 1);
ctx.queueSyncHint_(['Trang tính 1']);
eq('tab không theo dõi → bỏ qua', JSON.parse(CACHE.sync_q), ['SANPHAM', 'SUB']);
ctx.flushSyncHints();
eq('trigger mỗi phút chưa đủ 60s → chờ', HINTS.length, 1);
CACHE.sync_last = String(Date.now() - 61000);
ctx.flushSyncHints();
eq('đủ 60s → gửi 1 lần gộp', [HINTS.length, HINTS[1] && HINTS[1].body.tabs], [2, ['SANPHAM', 'SUB']]);
ctx.flushSyncHints();
eq('hàng chờ trống → không gửi', HINTS.length, 2);

// ---- Sổ ký gửi (tab KYGUI) ----
delete PROPS.SYNC_HINT_URL;
const kyStk = (b, dry) => ctx.handleStock_(Object.assign({ seller: 'nv@hn.vn' }, b), !!dry);
const tf = (t, from, to, size, qty, dry) => kyStk({ action: 'chuyen_kho', ticket_id: t, from, to, lines: [{ code: 'TH2040D', size, qty }] }, dry);
let kr = tf('K0', '15E', 'Y3C', 41, 1, true);
eq('chưa có tab KYGUI → tắt sổ ký gửi', [kr.ok, kr.results[0].ky_gui], [true, []]);
DATA.KHO15E[0].push('cua_Y3C'); DATA.KHOY3C[0].push('cua_15E'); // ký gửi lưu ở cột KHO (18/10)
if (DATA.BAN[0].indexOf('chu_hang') === -1) DATA.BAN[0].push('chu_hang');
const kyRow = (chu, at, size) => { // ô cột cua_… của dòng KHO (TH2040D, size) ở kho `at`; [4] = số ký gửi
  const t = DATA[at === '15E' ? 'KHO15E' : 'KHOY3C'], ci = t[0].indexOf(at === '15E' ? 'cua_Y3C' : 'cua_15E');
  const r = t.find(x => x[1] === 'TH2040D' && String(x[3]) === String(size));
  return r ? { get 4() { return Number(r[ci]) || 0; }, set 4(v) { r[ci] = v; } } : undefined;
};
kr = tf('K1', '15E', 'Y3C', 41, 1, true);
eq('chạy thử: 15E → Y3C thành ký gửi của 15E ở Y3C, chưa ghi', [kr.ok, kr.results[0].ky_gui, kyRow('15E', 'Y3C', 41)[4]], [true, [{ size: '41', chu_hang: '15E', qty: 1, loai: 'thanh_ky_gui' }], 0]);
kr = tf('K1', '15E', 'Y3C', 41, 1);
eq('ghi: KHOY3C.cua_15E dòng TH2040D 41 = 1 + gửi web tab KHOY3C', [kr.ok, kyRow('15E', 'Y3C', 41)[4], kr._sync.indexOf('KHOY3C') !== -1], [true, 1, true]);
// Bán ở Y3C 2 đôi size 41: 1 đôi ký gửi của 15E + 1 đôi của Y3C
let ks = ctx.handleSale_({ ticket_id: 'KS1', channel: 'cua_hang', seller: 'nv@hn.vn', lines: [{ code: 'TH2040D', size: 41, qty: 2, warehouse: 'Y3C', price: 800000 }] }, true);
eq('bán chạy thử: tách chủ hàng (ký gửi trước)', [ks.ok, ks.results[0].phan, ks.results[0].chu_hang], [true, [{ chu_hang: '15E', qty: 1 }, { chu_hang: 'Y3C', qty: 1 }], '']);
const banLen = DATA.BAN.length;
ks = ctx.handleSale_({ ticket_id: 'KS1', channel: 'cua_hang', seller: 'nv@hn.vn', lines: [{ code: 'TH2040D', size: 41, qty: 2, warehouse: 'Y3C', price: 800000 }] }, false);
const chuCol = DATA.BAN[0].indexOf('chu_hang'), qCol = DATA.BAN[0].indexOf('item_quantity');
eq('bán ghi: 2 dòng BAN theo chủ hàng, KYGUI về 0', [ks.ok, DATA.BAN.slice(banLen).map(r => [r[chuCol], r[qCol]]), kyRow('15E', 'Y3C', 41)[4]], [true, [['15E', 1], ['Y3C', 1]], 0]);
ks = ctx.handleSale_({ ticket_id: 'KS2', channel: 'cua_hang', seller: 'nv@hn.vn', lines: [{ code: 'TH2040D', size: 40, qty: 1, warehouse: 'Y3C' }] }, true);
eq('bán món không ký gửi → chủ hàng = kho', [ks.results[0].chu_hang, ks.results[0].phan], ['Y3C', [{ chu_hang: 'Y3C', qty: 1 }]]);
// Chuyển ngược Y3C → 15E: trả hàng của 15E đang ký gửi ở Y3C trước, phần còn lại thành ký gửi của Y3C ở 15E
tf('K2', '15E', 'Y3C', 40, 1);
kr = tf('K3', 'Y3C', '15E', 40, 2, true);
eq('Y3C → 15E: trả về chủ trước, dư thành ký gửi của Y3C', kr.results[0].ky_gui, [{ size: '40', chu_hang: '15E', qty: 1, loai: 'tra_ve_chu' }, { size: '40', chu_hang: 'Y3C', qty: 1, loai: 'thanh_ky_gui' }]);
kr = tf('K3', 'Y3C', '15E', 40, 2);
eq('ghi: KYGUI 15E ở Y3C = 0, Y3C ở 15E = 1', [kyRow('15E', 'Y3C', 40)[4], kyRow('Y3C', '15E', 40)[4]], [0, 1]);
kr = kyStk({ action: 'huy', ticket_id: 'K4', undo_ticket_id: 'K3' });
eq('huỷ chuyển kho → ký gửi trả lại như trước', [kr.ok, kyRow('15E', 'Y3C', 40)[4], kyRow('Y3C', '15E', 40)[4]], [true, 1, 0]);
// Chuyển hàng ký gửi về kho của hộ chủ: tồn kho nguồn còn đúng bằng số ký gửi → không báo đỏ (19/10, ca 2032D 39)
{ const y40 = DATA.KHOY3C.find(x => x[1] === 'TH2040D' && String(x[3]) === '40'), qi = DATA.KHOY3C[0].indexOf('current_quantity'), q0 = y40[qi];
  y40[qi] = 1;
  const kb = tf('K3b', 'Y3C', '15E', 40, 1, true);
  eq('chuyển ký gửi về kho chủ: trả về chủ, không cảnh báo sổ ký gửi', [kb.ok, kb.results[0].ky_gui[0].loai, JSON.stringify(kb.results[0]).indexOf('Sổ ký gửi')], [true, 'tra_ve_chu', -1]);
  y40[qi] = q0; }
// Trả hàng về đúng chủ
kr = kyStk({ action: 'tra_hang', ticket_id: 'K5', lines: [{ code: 'TH2040D', size: 41, qty: 1, warehouse: 'Y3C' }] });
eq('trả hàng không kèm chủ → theo dòng BAN gần nhất (Y3C)', [kr.ok, kr.results[0].chu_hang, kyRow('15E', 'Y3C', 41)[4]], [true, 'Y3C', 0]);
kr = kyStk({ action: 'tra_hang', ticket_id: 'K6', lines: [{ code: 'TH2040D', size: 41, qty: 1, warehouse: 'Y3C', chu_hang: '15E' }] });
eq('trả hàng kèm chu_hang 15E ở Y3C → cộng lại ký gửi', [kr.ok, kr.results[0].chu_hang, kyRow('15E', 'Y3C', 41)[4]], [true, '15E', 1]);
// Lệch sổ: ký gửi > tồn → cảnh báo, không chặn
kyRow('15E', 'Y3C', 41)[4] = 50;
ctx.MEMO = {};
ks = ctx.handleSale_({ ticket_id: 'KS3', channel: 'cua_hang', seller: 'nv@hn.vn', lines: [{ code: 'TH2040D', size: 41, qty: 1, warehouse: 'Y3C' }] }, true);
eq('ký gửi > tồn → cảnh báo, vẫn ok', [ks.ok, /Sổ ký gửi/.test(ks.results[0].warning || '')], [true, true]);
// Lệnh Zalo "ban" cũng trừ ký gửi
const zt = ctx.handleText_('ban TH2040D 41 YEN 800k', true, 'c1', 'Kris');
eq('Zalo bán: báo phần hàng ký gửi', /là hàng của hộ 15E/.test(zt), true);

// ---- Tin Zalo MISA ----
vm.runInContext('this.dailyMisaSummary=dailyMisaSummary;this.misaSummaryMessages_=misaSummaryMessages_;', ctx);
PROPS.OWNER_CHAT_ID = 'owner1';
PROPS.HKD_15E = 'Hải Nancy|0000000000|Đà Lạt'; PROPS.HKD_Y3C = 'Yen Leather|1111111111|Đà Lạt';
kyRow('15E', 'Y3C', 41)[4] = 1; ctx.MEMO = {};
let mb = ctx.handleSale_({ ticket_id: 'M0', channel: 'web', seller: 'kris', lines: [{ code: 'TH2040D', size: 41, qty: 1, warehouse: 'Y3C', price: 800000 }], lay_hoa_don: { ten_cty: 'Cty A' , mst: '12345' } }, true);
eq('MST sai → lỗi, không ghi', [mb.ok, /mst/.test(mb.error)], [false, true]);
mb = ctx.handleSale_({ ticket_id: 'M1', channel: 'web', seller: 'kris', lines: [{ code: 'TH2040D', size: 41, qty: 2, warehouse: 'Y3C', price: 800000 }],
  khach: { ten: 'Chị B', sdt: '0909' }, lay_hoa_don: { ten_cty: 'Cty A', mst: '0312345678', dia_chi: '1 Lê Lợi', email: 'a@b.vn' }, thanh_toan: 'CK Techcombank', phi_ship: 30000 }, true);
eq('chạy thử lấy hoá đơn: báo sẽ gửi cho 2 hộ, chưa gửi', [mb.ok, mb.misa, SENT.length], [true, { se_gui: ['15E', 'Y3C'] }, SENT.length]);
const s0 = SENT.length;
mb = ctx.handleSale_({ ticket_id: 'M1', channel: 'web', seller: 'kris', lines: [{ code: 'TH2040D', size: 41, qty: 2, warehouse: 'Y3C', price: 800000 }],
  khach: { ten: 'Chị B', sdt: '0909' }, lay_hoa_don: { ten_cty: 'Cty A', mst: '0312345678', dia_chi: '1 Lê Lợi', email: 'a@b.vn' }, thanh_toan: 'CK Techcombank', phi_ship: 30000 }, false);
const misaMsgs = SENT.slice(s0).map(x => x.text);
eq('lấy hoá đơn: gửi ngay 1 tin / hộ chủ hàng', [mb.ok, mb.misa, misaMsgs.length, misaMsgs.map(t => t.split('\n')[0])],
  [true, { da_gui: 2 }, 2, ['🧾 HOÁ ĐƠN BÁN HÀNG (MISA) – Hải Nancy (15E)', '🧾 HOÁ ĐƠN BÁN HÀNG (MISA) – Yen Leather (Y3C)']]);
eq('tin hoá đơn đủ ô: số CT, kênh, người bán, khách, MST, dòng mã MISA, thuế, tổng, thanh toán, ship',
  [/Số CT M1 · Kênh web · Người bán kris/.test(misaMsgs[0]), /Khách: Chị B · 0909/.test(misaMsgs[0]), /MST 0312345678/.test(misaMsgs[0]), /Email: a@b\.vn/.test(misaMsgs[0]),
   /1\. TH2040D41 · .* · Đôi · 1 × 800\.000/.test(misaMsgs[0]), /GTGT 1% · TNCN 0,5%/.test(misaMsgs[0]), /Tổng: 800\.000đ · Thanh toán: CK Techcombank · Ship: 30\.000đ/.test(misaMsgs[0])],
  [true, true, true, true, true, true, true]);
const sumMsgs = ctx.dailyMisaSummary(true);
eq('tin cuối ngày: theo hộ chủ hàng, bỏ dòng đã gửi riêng', [sumMsgs.every(m => !/M1/.test(m)), /Đã gửi riêng 2 dòng lấy hoá đơn/.test(sumMsgs[sumMsgs.length - 1]), sumMsgs.some(m => /^📒 ĐƠN HÀNG CHO MISA CUỐI NGÀY .* – Yen Leather \(Y3C\)/.test(m))], [true, true, true]);
eq('tin cuối ngày ghi hàng ký gửi theo chủ', sumMsgs.some(m => /Hải Nancy \(15E\)[\s\S]*ký gửi ở Y3C/.test(m)), true);

// ---- Xuất file MISA qua bot ----
vm.runInContext('this.xlsxReplaceRows_=xlsxReplaceRows_;this.xlsxSheetPath_=xlsxSheetPath_;', ctx);
const xm = ctx.xlsxReplaceRows_('<worksheet><dimension ref="A1:V15"/><sheetData><row r="1"><c r="A1"><v>1</v></c></row><row r="2"/><row r="3"><c r="A3"><v>9</v></c></row></sheetData><mergeCells count="2"><mergeCell ref="A1:B1"/><mergeCell ref="A3:B3"/></mergeCells></worksheet>',
  3, [{ 1: 'Tên <&>', 3: 5, 2: '' }]);
eq('xlsx: giữ dòng trên, xoá dòng mẫu, chèn dòng mới, bỏ ô gộp vùng xoá, sửa dimension', xm,
  '<worksheet><dimension ref="A1:V3"/><sheetData><row r="1"><c r="A1"><v>1</v></c></row><row r="2"/><row r="3"><c r="A3" t="inlineStr"><is><t xml:space="preserve">Tên &lt;&amp;&gt;</t></is></c><c r="C3"><v>5</v></c></row></sheetData><mergeCells count="1"><mergeCell ref="A1:B1"/></mergeCells></worksheet>');
eq('xlsx: tìm file sheet theo tên', ctx.xlsxSheetPath_('<sheets><sheet name="A" sheetId="1" r:id="rId3"/><sheet name="Tep nhap khau" sheetId="2" r:id="rId4"/></sheets>',
  '<Relationship Id="rId3" Target="worksheets/sheet1.xml"/><Relationship Id="rId4" Type="x" Target="worksheets/sheet2.xml"/>', 'Tep nhap khau'), 'xl/worksheets/sheet2.xml');
DATA.SANPHAM[1].push('misa_upload');                     // cột 18
DATA.SUB[0].push('Mã nhóm hàng hóa', '% chiết khấu', 'Cân nặng');
DATA.SUB[1].push('6', '0', 1200); DATA.SUB[2].push('7', '10%', 1500);
const spIx = c => DATA.SANPHAM.findIndex(r => r[1] === c);
DATA.SANPHAM[spIx('TH2040N')][18] = 'Done - 2026-10-01 10:00';
DATA.SANPHAM[spIx('TH2040X')][13] = '38,39';
DATA.SANPHAM[spIx('TH2040X')][8] = 'Giày tây TH2040X'; // Sheet thật trả giá trị đã tính của công thức
DATA.SANPHAM.push(['MS1', 'MS1D', '', '', 'Chú Dũng', '', '', 'Đen', 'Giày MS1 đen', 'Giày mọi nam', 'Đôi', 900000, 400000, '39,40', 'male', '7', '', 'Việt Nam', '']);
const xm2 = (b, dry) => ctx.handleStock_(Object.assign({ action: 'xuat_misa', nguoi: 'kha@hn.vn' }, b), !!dry);
let xr = xm2({ loai: 'abc' }, true);
eq('xuat_misa: loai sai → lỗi', [xr.ok, /loai phải là/.test(xr.error)], [false, true]);
xr = xm2({ loai: 'danh_muc' }, true);
eq('danh mục chạy thử: mã cha mới → file NEW, mã cha đã lên MISA → file UPDATE, bỏ mã cần bổ sung, không ghi cờ',
  [xr.ok, xr.files.map(f => f.ten.replace(/\d{8}_\d{4}(\d\d|ss)/, 'T') + ':' + f.so_dong), xr.bo_qua.sort(), DATA.SANPHAM[spIx('MS1D')][18]],
  [true, ['MISA_PRODUCTS_NEW_T.xlsx:3', 'MISA_PRODUCTS_UPDATE_T.xlsx:3'], ['CXED', 'TH2040D'], '']);
const realWrite = ctx.misaWriteFile_;
const WROTE = [];
ctx.misaWriteFile_ = (tpl, sheet, start, rows, out, dry) => { WROTE.push({ tpl, sheet, start, rows, out }); return { ten: out, url: 'https://drive/x', so_dong: rows.length }; };
xr = xm2({ loai: 'danh_muc' });
const nw = WROTE[0], up = WROTE[1];
eq('danh mục ghi: cột MISA như menu (cha / con, thuộc tính màu + size, thuế 1% / 0,5%)',
  [nw.tpl, nw.sheet, nw.start, nw.rows[0][3], nw.rows[0][4], nw.rows[0][13], nw.rows[0][15], nw.rows[0][19], nw.rows[0][20], nw.rows[1][4], nw.rows[1][6], nw.rows[1][32], nw.rows[1][33], nw.rows[1][34], nw.rows[1][35]],
  ['tpl_misa_upload.xlsx', 'Tep nhap khau', 6, 'Hàng hóa cha ', 'MS1', '7', 1500, 1, 0.5, 'MS1D39', 'MS1', 'Màu sắc', 'Đen', 'Size', '39']);
eq('danh mục ghi: file cập nhật thêm màu', [up.tpl, up.sheet, up.start, up.rows[0][1], up.rows[1][1], up.rows[1][7]], ['tpl_misa_update.xlsx', 'Nhap_khau_cap_nhat_thong_tin', 3, 'TH2040', 'TH2040X38', 'Giày tây TH2040X (Xám/38)']);
eq('danh mục ghi cờ misa_upload, gửi web SANPHAM', [/^Done - /.test(DATA.SANPHAM[spIx('MS1D')][18]), /^Done - /.test(DATA.SANPHAM[spIx('TH2040X')][18]), xr._sync], [true, true, ['SANPHAM']]);
// Nhập kho 15E
const nhBase = DATA.NHAP.length;
DATA.NHAP.push(['01/10/2026', 'NK000009', 'MS1D', 'Đen', '15E', 39, 2, '', '', '', '', ''],
  ['01/10/2026', 'NK000015', 'MS1D', 'Đen', 'Y3C', 40, 1, '', '', '', '', ''],
  ['01/10/2026', 'TRA-171026', 'MS1D', 'Đen', '15E', 39, 1, '', '', '', '', '']);
WROTE.length = 0;
xr = xm2({ loai: 'nhap_kho_15e' });
const st = WROTE[0];
const msRow = st.rows.find(r => r[8] === 'MS1D39');
eq('nhập kho 15E: mẫu, mã kho MISA, đơn giá = giá nhập khi invoice_price trống, NCC + chiết khấu theo SUB',
  [st.tpl, st.sheet, st.start, msRow && msRow[3], msRow && msRow[4], msRow && msRow[12], msRow && msRow[15], msRow && msRow[16], msRow && msRow[17], msRow && msRow[18], msRow && msRow[19], msRow && msRow[22]],
  ['tpl_misa_stock_15e.xlsx', 'Nhap kho', 9, 'NK000009', 'NCCQT', '15ETBH', 2, 400000, 800000, 0.1, 80000, 720000]);
eq('nhập kho 15E: dòng TRA- → "Bỏ qua - trả hàng", dòng Y3C để nguyên', [DATA.NHAP[nhBase + 2][10], DATA.NHAP[nhBase + 1][10], /^Done - /.test(DATA.NHAP[nhBase][10])], ['Bỏ qua - trả hàng', '', true]);
ctx.misaWriteFile_ = realWrite;

// ---- Huỷ phiếu bán (huy_ban) ----
vm.runInContext('this.saleUndo_=saleUndo_;', ctx);
const kyR = kyRow('15E', 'Y3C', 41); kyR[4] = 1; ctx.MEMO = {};
const bLen = DATA.BAN.length;
let hb = ctx.handleSale_({ ticket_id: 'HB1', channel: 'cua_hang', seller: 'nv@hn.vn', lines: [{ code: 'TH2040D', size: 41, qty: 2, warehouse: 'Y3C', price: 800000 }] }, false);
const hbRows = DATA.BAN.slice(bLen);
eq('bán để thử huỷ: 2 dòng BAN, ký gửi về 0', [hb.ok, hbRows.length, kyR[4]], [true, 2, 0]);
const hu = (b, dry) => ctx.saleUndo_(Object.assign({ ticket_id: 'HB1' }, b), !!dry);
eq('người khác huỷ → chặn', /chính mình/.test(hu({ nguoi: 'khac@hn.vn' }).error), true);
eq('nhân viên tự nhận là Chủ → chặn', /chỉ Chủ/.test(hu({ nguoi: 'nv@hn.vn', chu: true }).error), true);
hb = hu({ nguoi: 'nv@hn.vn' }, true);
eq('huỷ chạy thử: báo số dòng + kho, chưa xoá', [hb.ok, hb.so_dong, hb.kho, hbRows[0][1]], [true, 2, ['Y3C'], 'TH2040D']);
hb = hu({ nguoi: 'NV@hn.vn' });
eq('huỷ: xoá ô dòng BAN, trả ký gửi', [hb.ok, hbRows.every(r => r[1] === '' && r[5] === ''), kyR[4]], [true, true, 1]);
eq('huỷ lần 2 → báo đã huỷ', [hu({ nguoi: 'nv@hn.vn' }).ok, !!hu({ nguoi: 'nv@hn.vn' }).da_huy], [false, true]);
// Quá 10 phút: chỉ Chủ; sổ ký gửi đổi sau phiếu → chặn
ctx.MEMO = {};
ctx.handleSale_({ ticket_id: 'HB2', channel: 'web', seller: 'nv@hn.vn', lines: [{ code: 'TH2040D', size: 41, qty: 1, warehouse: 'Y3C', price: 800000 }],
  lay_hoa_don: { ten_cty: 'Cty A', mst: '0312345678' } }, false);
const hbRec = JSON.parse(PROPS.saleops_HB2); hbRec.t -= 11 * 60000; PROPS.saleops_HB2 = JSON.stringify(hbRec);
eq('quá 10 phút, nhân viên → nhờ Chủ', /quá 10 phút/.test(ctx.saleUndo_({ ticket_id: 'HB2', nguoi: 'nv@hn.vn' }).error), true);
kyR[4] = 5;
eq('sổ ký gửi đổi sau phiếu → không huỷ', /Ký gửi/.test(ctx.saleUndo_({ ticket_id: 'HB2', nguoi: 'ltckha@gmail.com', chu: true }).error), true);
kyR[4] = 0;
const s3 = SENT.length;
hb = ctx.saleUndo_({ ticket_id: 'HB2', nguoi: 'ltckha@gmail.com', chu: true });
eq('Chủ huỷ sau hạn + đã gửi tin hoá đơn → gửi tin HUỶ', [hb.ok, hb.chu, hb.misa_huy, /❌ HUỶ đơn hàng HB2/.test((SENT[s3] || {}).text || '')], [true, true, true, true]);
eq('phiếu không có / cũ → báo rõ', /không có phiếu/.test(ctx.saleUndo_({ ticket_id: 'ZZZ', nguoi: 'nv@hn.vn' }).error), true);

// ---- Điều khiển bằng số ----
PROPS.OWNER_CHAT_ID = 'owner1';
const z = (txt, chat) => ctx.handleText_(txt, false, chat || 'owner1', 'Kha');
let zr = z('menu');
eq('Chủ: menu đủ mục + số việc chờ', [/^📋 MENU HNC/.test(zr), /3 Phiếu nhập kho chờ chia \(\d+\)/.test(zr), /4 Hoá đơn mua hàng chưa có \(\d+\)/.test(zr), /5 Mã cần bổ sung \(\d+\)/.test(zr), /6 Huỷ/.test(zr)], [true, true, true, true, true]);
zr = z('m', 'nv1');
eq('Nhân viên: chỉ 1 2 6 9', [/1 Kiểm tồn kho/.test(zr), /3 Phiếu/.test(zr), /4 Hoá đơn/.test(zr), /6 Huỷ/.test(zr), /9 Hướng dẫn/.test(zr)], [true, false, false, true, true]);
eq('nhân viên chọn 3 → chỉ Chủ', /chỉ Chủ/.test(z('3', 'nv1')), true);
delete PROPS.ask_nv2;
eq('tin số không có câu hỏi → menu', /^📋 MENU HNC/.test(z('2', 'nv2')), true);
eq('chữ không hiểu → menu', /Mình chưa hiểu[\s\S]*MENU HNC/.test(z('xin chào cả nhà', 'nv3')), true);
eq('"hd" vẫn là hướng dẫn lệnh chữ', /HƯỚNG DẪN BOT KHO HNC/.test(z('hd', 'nv3')), true);
z('menu', 'nv1');
eq('1 → hỏi mã; gõ mã → kiểm hàng', [/Gõ mã cần kiểm tồn kho/.test(z('1', 'nv1')), /TH2040D/.test(z('TH2040D', 'nv1')), !PROPS.ask_nv1], [true, true, true]);
z('menu', 'nv1'); z('2', 'nv1');
eq('2 → 3 báo cáo tuần này', /ĐƠN HÀNG TUẦN/.test(z('3', 'nv1')) || /Tuần .*chưa có dòng bán/.test(z('3', 'nv1')), true);
z('menu', 'nv1');
eq('0 → để sau, xoá câu hỏi', [/Để sau/.test(z('0', 'nv1')), !PROPS.ask_nv1], [true, true]);
// 6 huỷ: phải nhắn 6 hai lần
z('nhap TH2040D 40 TBH', 'nv4');
z('menu', 'nv4');
eq('6 lần 1 → nhắc thao tác, chưa huỷ', /Nhắn 6 lần nữa để HUỶ/.test(z('6', 'nv4')), true);
eq('6 lần 2 → huỷ', /Đã huỷ/.test(z('6', 'nv4')), true);
// 4 duyệt hoá đơn
ctx.MEMO = {};
const dueIds = ctx.invoiceStatus_(ctx.invoiceTickets_()).tickets.filter(t => t.status === 'chua').map(t => t.id);
vm.runInContext('this.navInvoiceShow_=navInvoiceShow_;', ctx);
if (dueIds.length) {
  // Ca "không có giá ở đâu cả": bỏ tạm giá nhập SANPHAM (từ 19/10 dòng trống giá phiếu lấy giá nhập SANPHAM)
  const spHr = DATA.SANPHAM.findIndex(r => r.indexOf('purchase_price') !== -1), spPc = DATA.SANPHAM[spHr].indexOf('purchase_price');
  const spBuy0 = DATA.SANPHAM.map(r => r[spPc]); DATA.SANPHAM.forEach((r, i) => { if (i > spHr) r[spPc] = ''; });
  ctx.navInvoiceShow_('owner1', dueIds, 0);
  zr = z('1');
  eq('4: nhắn 1 → hỏi số hoá đơn', /gõ số hoá đơn/.test(zr), true);
  zr = z('0001234');
  eq('4: gõ số HĐ khi dòng chưa có giá phiếu → báo nhập trên app, sang phiếu kế', [/chưa có giá phiếu/.test(zr), /Phiếu 2\//.test(zr) || /Đã duyệt hết/.test(zr)], [true, true]);
  DATA.SANPHAM.forEach((r, i) => { r[spPc] = spBuy0[i]; });
} else eq('4: có phiếu để duyệt', dueIds.length > 0, true);
const s4 = SENT.length;
PROPS.SYNC_HINT_URL = 'https://giayhainancy.vn/api/sync-hint';
eq('nhắc hoá đơn thứ Hai gộp 1 tin + "4 Duyệt từng phiếu"', ctx.invoiceReminderMessages_().length <= 1 && (ctx.invoiceReminderMessages_()[0] || 'Nhắn số: 4').indexOf('Nhắn số: 4') !== -1, true);
delete PROPS.SYNC_HINT_URL;

// ---- Dự phòng (A1–A5) ----
DATA.BAN[0].push('payment_method', 'customer_phone');
const pIx = n => DATA.BAN[0].indexOf(n);
let dp = ctx.parseMessage_('ban TH2040D 40 YEN 800k ck sdt 0909123456', ctx.knownCodes_());
eq('bán Zalo: đọc ck + sdt, không lẫn vào giá / size', [dp.payment, dp.phone, dp.price, dp.sizes.map(x => x.size + 'x' + x.qty).join(), dp.code], ['Chuyển khoản', '0909123456', '800000', '40x1', 'TH2040D']);
dp = ctx.parseMessage_('ban TH2040D 41 TBH 0912345678 the', ctx.knownCodes_());
eq('bán Zalo: số điện thoại trần + thẻ', [dp.payment, dp.phone, dp.price], ['Thẻ', '0912345678', '']);
const bl = DATA.BAN.length;
z('ban TH2040D 40 YEN 800k', 'nv9');
eq('bán Zalo không ghi cách trả → mặc định Tiền mặt', DATA.BAN.filter(r => r[pIx('payment_method')]).map(r => [r[1], r[pIx('payment_method')]]).slice(-1), [['TH2040D', 'Tiền mặt']]);
dp = ctx.parseMessage_('nhap TH2040D 41 TBH nk45', ctx.knownCodes_());
eq('nhập Zalo có số chứng từ', [dp.nhapDoc, dp.sizes.map(x => x.size).join(), dp.code], ['NK000045', '41', 'TH2040D']);
const nl = DATA.NHAP.length;
zr = z('nhap TH2040D 41 TBH NK000045', 'nv9');
const nr = DATA.NHAP.find(r => r[1] === 'NK000045') || [];
eq('nhập có NK → Số chứng từ NK, cờ MISA trống (vào tem + MISA)', [nr[1], nr[8], nr[10], /Số chứng từ NK000045/.test(zr)], ['NK000045', '', '', true]);
const nl2 = DATA.NHAP.length;
z('nhap TH2040D 39 TBH misa', 'nv9');
eq('nhập "misa" không số → cùng kho + NCC + ngày dùng chung số NK đã có', DATA.NHAP.some(r => r[2] === 'TH2040D' && String(r[5]) === '39' && r[1] === 'NK000045' && !r[10]), true);
const nl3 = DATA.NHAP.length;
z('nhap TH2040D 39 TBH', 'nv9');
eq('nhập không số → Zalo_Update như cũ', DATA.NHAP.filter(r => r[2] === 'TH2040D' && String(r[5]) === '39' && !r[1]).some(r => r[10] === 'Zalo_Update'), true);
eq('lệnh "du phong" → bảng cú pháp theo số', /DỰ PHÒNG[\s\S]*1 Tiền mặt · 2 Chuyển khoản · 3 Thẻ[\s\S]*menu → 6/.test(z('du phong', 'nv9')), true);
eq('menu có 8 Dự phòng', /8 Dự phòng/.test(z('menu', 'nv9')), true);
// A4: Chủ huỷ dòng bán Zalo
const banRow = DATA.BAN.length - 1;
eq('nhân viên huỷ dòng cũ → chặn', /Chỉ Chủ/.test(z('huy TH2040D 40', 'nv9')), true);
zr = z('huy TH2040D 40');
eq('Chủ: liệt kê dòng bán khớp', /HUỶ ĐƠN HÀNG[\s\S]*TH2040D size 40 × 1 · Y3C/.test(zr), true);
zr = z('1');
eq('nhắn 1 → huỷ dòng bán gần nhất', [/Đã huỷ đơn hàng TH2040D size 40/.test(zr)], [true]);
// Chọn số sau khi bán: đổi cách trả; Chủ huỷ dòng bán qua menu 6
zr = z('ban TH2040D 41 YEN 800k', 'nv8');
eq('bán xong → hỏi cách trả bằng số', /Nhắn số: 1 Tiền mặt · 2 Chuyển khoản · 3 Thẻ/.test(zr), true);
zr = z('2', 'nv8');
const lastPay = DATA.BAN.filter(r => r[1] === 'TH2040D' && String(r[4]) === '41' && r[pIx('payment_method')]).slice(-1)[0];
eq('nhắn 2 → ghi Chuyển khoản vào dòng vừa bán', [/Đã ghi hình thức thanh toán: Chuyển khoản/.test(zr), lastPay && lastPay[pIx('payment_method')]], [true, 'Chuyển khoản']);
z('ban TH2040D 40 YEN 700k');
zr = z('6');
eq('Chủ: menu 6 → 1 lệnh vừa rồi + các dòng bán 2 ngày', [/1 Lệnh vừa rồi/.test(zr), /2 Đơn hàng .* TH2040D size 40 × 1/.test(zr)], [true, true]);
zr = z('2');
eq('chọn 2 → huỷ dòng bán đó', /Đã huỷ đơn hàng TH2040D size 40/.test(zr), true);

// A1: web lỗi → giữ hàng chờ, thử lại, báo Chủ, báo khi chạy lại
PROPS.SYNC_HINT_URL = 'https://web.example/api/sync-hint'; PROPS.SYNC_HINT_KEY = 'synckey_1234567890';
const okFetch = ctx.UrlFetchApp.fetch;
let webDown = true;
ctx.UrlFetchApp.fetch = (url, opt) => (url.indexOf('sync-hint') !== -1 && webDown ? { getResponseCode: () => 503, getContentText: () => 'down' } : okFetch(url, opt));
delete CACHE.sync_q; delete CACHE.sync_last; delete PROPS.sync_retry;
ctx.queueSyncHint_(['BAN']);
CACHE.sync_last = String(Date.now() - 61000); ctx.flushSyncHints();
let rt = JSON.parse(PROPS.sync_retry || 'null');
eq('web lỗi lần 1: giữ hàng chờ, hẹn thử lại 5 phút, chưa báo', [JSON.parse(CACHE.sync_q).indexOf('BAN') !== -1, rt && rt.n, rt && Math.round((rt.next - Date.now()) / 60000), rt && rt.alerted], [true, 1, 5, false]);
CACHE.sync_last = String(Date.now() - 61000); ctx.flushSyncHints();
eq('chưa tới giờ thử lại → không gửi', JSON.parse(PROPS.sync_retry).n, 1);
rt = JSON.parse(PROPS.sync_retry); rt.next = Date.now() - 1; PROPS.sync_retry = JSON.stringify(rt);
const sa = SENT.length;
CACHE.sync_last = String(Date.now() - 61000); ctx.flushSyncHints();
rt = JSON.parse(PROPS.sync_retry);
eq('lỗi lần 2: hẹn 15 phút + báo Chủ kèm bảng dự phòng', [rt.n, Math.round((rt.next - Date.now()) / 60000), rt.alerted, /Web không nhận[\s\S]*DỰ PHÒNG/.test((SENT[sa] || {}).text || '')], [2, 15, true, true]);
webDown = false; rt.next = Date.now() - 1; PROPS.sync_retry = JSON.stringify(rt);
const sb = SENT.length, hb0 = HINTS.length;
CACHE.sync_last = String(Date.now() - 61000); ctx.flushSyncHints();
eq('web chạy lại: gửi bù, xoá hàng chờ + hẹn, báo Chủ', [HINTS.length - hb0, !CACHE.sync_q, !PROPS.sync_retry, /Web chạy lại/.test((SENT[sb] || {}).text || '')], [1, true, true, true]);
ctx.UrlFetchApp.fetch = okFetch;
delete PROPS.SYNC_HINT_URL;

// ---- Tin web có lựa chọn số (notify options) ----
PROPS.SYNC_HINT_URL = 'https://giayhainancy.vn/api/sync-hint'; PROPS.URL_ALLOW = 'yenleather.com';
const nt = b => ctx.handleNotify_(b, 'owner1', ctx.PropertiesService.getScriptProperties());
let nr2 = nt({ order_id: 'HN-1710-901', text: 'Đơn mới', options: [{ so: 9, nhan: 'x', hanh_dong: 'ghi_nhan' }] });
eq('options: số 9 bị chặn, không gửi', [nr2.ok, /so phải là số 1–8/.test(nr2.error)], [false, true]);
nr2 = nt({ order_id: 'HN-1710-902', text: 'Đơn mới', options: [{ so: 1, nhan: 'Xem', hanh_dong: 'url', url: 'https://evil.com/x' }] });
eq('options: url ngoài tên miền → lỗi', [nr2.ok, /url của số 1/.test(nr2.error)], [false, true]);
const s5 = SENT.length;
nr2 = nt({ order_id: 'HN-1710-903', text: '🛒 Đơn web mới', options: [
  { so: 1, nhan: 'Đã gọi khách', hanh_dong: 'callback', callback: { loai: 'don_da_goi', id: 'HN-1710-903' } },
  { so: 3, nhan: 'Huỷ đơn', hanh_dong: 'callback', callback: { loai: 'don_huy', id: 'HN-1710-903' }, xac_nhan_2_lan: true },
  { so: 4, nhan: 'Xem đơn', hanh_dong: 'url', url: 'https://giayhainancy.vn/admin/don/HN-1710-903' },
  { so: 5, nhan: 'Mở admin Yen', hanh_dong: 'url', url: 'https://admin.yenleather.com/x' }] });
eq('tin web: gửi kèm dòng Nhắn số + nhớ câu hỏi', [nr2.ok, nr2.so_lua_chon, /Nhắn số: 1 Đã gọi khách · 3 Huỷ đơn · 4 Xem đơn · 5 Mở admin Yen · 0 Để sau · 9 Menu/.test((SENT[s5] || {}).text || ''), JSON.parse(PROPS.ask_owner1).k], [true, 4, true, 'web']);
eq('chọn url → gửi link', /🔗 Xem đơn: https:\/\/giayhainancy\.vn\/admin\/don\/HN-1710-903/.test(z('4')), true);
nt({ order_id: 'HN-1710-904', text: 'Đơn', options: [{ so: 1, nhan: 'Đã gọi khách', hanh_dong: 'callback', callback: { loai: 'don_da_goi', id: 'HN-1710-904' } },
  { so: 3, nhan: 'Huỷ đơn', hanh_dong: 'callback', callback: { loai: 'don_huy', id: 'HN-1710-904' }, xac_nhan_2_lan: true }] });
const nk0 = PROPS.WEB_NOTIFY_KEY; delete PROPS.WEB_NOTIFY_KEY;
eq('callback khi chưa có khoá → báo làm trên web', /chưa có khoá/.test(z('1')), true);
PROPS.WEB_NOTIFY_KEY = 'notifykey_1234567890';
const CB = [];
const f0 = ctx.UrlFetchApp.fetch;
let cbFail = false;
ctx.UrlFetchApp.fetch = (url, opt) => {
  if (url.indexOf('/api/bot-callback') !== -1) { CB.push({ url, headers: opt.headers, body: JSON.parse(opt.payload) }); return cbFail ? { getResponseCode: () => 500, getContentText: () => '{"ok":false,"error":"lỗi web"}' } : { getResponseCode: () => 200, getContentText: () => '{"ok":true,"text":"Đã ghi: đã gọi khách"}' }; }
  return f0(url, opt);
};
cbFail = true;
eq('callback web lỗi → giữ câu hỏi, báo nhắn lại', [/Web chưa nhận \(lỗi web\)/.test(z('1')), JSON.parse(PROPS.ask_owner1).k], [true, 'web']);
cbFail = false;
zr = z('1');
const lastCb = CB.slice(-1)[0];
const expSig = require('crypto').createHmac('sha256', 'notifykey_1234567890').update(lastCb.headers['x-bot-time'] + '.' + JSON.stringify(lastCb.body)).digest('hex');
eq('callback: POST /api/bot-callback, ký HMAC bằng khoá notify (không gửi khoá), trả text của web',
  [zr.indexOf('Đã ghi: đã gọi khách') === 0, lastCb.headers['x-bot-sig'] === expSig, JSON.stringify(lastCb.headers).indexOf('notifykey') === -1, lastCb.body.loai, lastCb.body.so],
  [true, true, true, 'don_da_goi', 1]);
nt({ order_id: 'HN-1710-905', text: 'Đơn', options: [{ so: 3, nhan: 'Huỷ đơn', hanh_dong: 'callback', callback: { loai: 'don_huy', id: 'HN-1710-905' }, xac_nhan_2_lan: true }] });
const cb0 = CB.length;
eq('việc khó quay lại: nhắn 3 lần 1 → hỏi lại, chưa gọi web', [/nhắn 3 lần nữa/.test(z('3')), CB.length - cb0], [true, 0]);
eq('nhắn 3 lần 2 → gọi web', [z('3').length > 0, CB.length - cb0, CB.slice(-1)[0].body.loai], [true, 1, 'don_huy']);
ctx.UrlFetchApp.fetch = f0;
delete PROPS.SYNC_HINT_URL; delete PROPS.URL_ALLOW;
if (nk0) PROPS.WEB_NOTIFY_KEY = nk0; else delete PROPS.WEB_NOTIFY_KEY;

// ---- Hoá đơn NCC theo lô (hoa_don) ----
vm.runInContext('this.invoiceAction_=invoiceAction_;this.misaStockExport_=misaStockExport_;', ctx);
DATA.NHAP[0].push('don_gia_phieu', 'don_gia_hd', 'so_hd', 'ngay_hd'); // cột 12–15
const hdIx = n => DATA.NHAP[0].indexOf(n);
const today = (() => { const d = new Date(); return ('0' + d.getDate()).slice(-2) + '/' + ('0' + (d.getMonth() + 1)).slice(-2) + '/' + d.getFullYear(); })();
const hdRow = ['01/10/2026', 'NK000077', 'TH2040N', 'Nâu', '15E', 41, 2, '', '', '', '', ''];
hdRow[hdIx('don_gia_phieu')] = 500000;
DATA.NHAP.push(hdRow);
const hdRowN = DATA.NHAP.length;
ctx.MEMO = {};
const hdT = ctx.invoiceStatus_(ctx.invoiceTickets_()).tickets.find(t => (t.rows || []).indexOf(hdRowN) !== -1);
const ha = (b, dry, who) => ctx.invoiceAction_(b, who || 'ltckha@gmail.com', !!dry);
eq('hoa_don: nhân viên bị chặn', /chỉ Chủ/.test(ha({ che_do: 'ds' }, true, 'nv@hn.vn').error), true);
eq('hoa_don ds có phiếu', ha({ che_do: 'ds' }, true).phieu.some(p => p.id === hdT.id), true);
let hx = ha({ che_do: 'xem', phieu: hdT.id }, true);
eq('hoa_don xem: dòng kèm giá phiếu', hx.dong.find(d => d.dong === hdRowN).don_gia_phieu, 500000);
hx = ha({ che_do: 'ghi', phieu: hdT.id, so_hd: '0001234', ngay_hd: '05/10/2026', dong: [{ dong: hdRowN, don_gia_hd: 520000 }] }, true);
eq('ghi chạy thử: báo lệch giá, chưa ghi', [hx.ok, hx.lech_gia.some(x => /phiếu 500\.000đ → HĐ 520\.000đ/.test(x)), hdRow[hdIx('so_hd')]], [true, true, undefined]);
const hdOthers = (ha({ che_do: 'xem', phieu: hdT.id }, true).dong || []).filter(d => d.dong !== hdRowN && !d.don_gia_phieu);
const s6 = SENT.length;
hx = ha({ che_do: 'ghi', phieu: hdT.id, so_hd: '0001234', ngay_hd: '05/10/2026', dong: [{ dong: hdRowN, don_gia_hd: 520000 }].concat(hdOthers.map(d => ({ dong: d.dong, don_gia_hd: 300000 }))) });
eq('ghi: số / ngày / giá HĐ vào dòng NHAP, phiếu = đã có HĐ, nhắn Chủ lệch giá', [hx.ok, hdRow[hdIx('so_hd')], hdRow[hdIx('ngay_hd')], hdRow[hdIx('don_gia_hd')], JSON.parse(PROPS['hdon_' + hdT.id]).s, /Lệch giá phiếu/.test((SENT[s6] || {}).text || '')],
  [true, '0001234', '05/10/2026', 520000, 'da', true]);
eq('ghi: invoice_price = giá HĐ gần nhất', String(DATA.SANPHAM[DATA.SANPHAM.findIndex(r => r[1] === 'TH2040N')][5]), '520000');
eq('ghi: dòng chưa có giá phiếu mà không gửi giá → lỗi', /chưa có giá phiếu/.test((ha({ che_do: 'ghi', phieu: hdT.id, so_hd: 'X1', dung_nhu_phieu: true }, true).loi || []).join() || 'chưa có giá phiếu'), true);
eq('ngày HĐ trống = hôm nay', ha({ che_do: 'ghi', phieu: hdT.id, so_hd: 'X2', dong: [{ dong: hdRowN, don_gia_hd: 1 }].concat(hdOthers.map(d => ({ dong: d.dong, don_gia_hd: 1 }))) }, true).ngay_hd, today);
// hoadon: chỉ Chủ, đúng mã, tudong
// MISA nhập kho theo lô: giá HĐ, chờ HĐ 3 ngày, giá tạm
const mk = (doc, date, code, size, extra) => { const r = [date, doc, code, 'Đen', '15E', size, 1, '', '', '', '', '', '', '', '', '']; Object.keys(extra || {}).forEach(k => { r[hdIx(k)] = extra[k]; }); DATA.NHAP.push(r); return r; };
const todayStr = today;
const rHd = mk('NK000090', '01/10/2026', 'MS1D', 39, { don_gia_phieu: 410000, don_gia_hd: 420000, so_hd: '00055', ngay_hd: '03/10/2026' });
const rNew = mk('NK000091', todayStr, 'MS1D', 40, { don_gia_phieu: 410000 });
const rOld = mk('NK000092', '01/10/2026', 'MS1D', 40, { don_gia_phieu: 415000 });
WROTE.length = 0;
ctx.misaWriteFile_ = (tpl, sheet, start, rows, out, dry) => { WROTE.push({ rows }); return { ten: out, url: '', so_dong: rows.length }; };
ctx.MEMO = {};
const ms = ctx.misaStockExport_('15E', false, true);
const rowOf = doc => (WROTE[0] ? WROTE[0].rows : []).find(r => r[3] === doc);
eq('MISA lô: có HĐ → giá HĐ + số HĐ trong diễn giải', [rowOf('NK000090') && rowOf('NK000090')[16], /HĐ 00055 ngày 03\/10\/2026/.test(rowOf('NK000090') && rowOf('NK000090')[6])], [420000, true]);
eq('MISA lô: chưa HĐ ≤3 ngày → chờ, không xuất, cờ trống', [!rowOf('NK000091'), rNew[10], ms.cho_hd.some(x => x.so_chung_tu === 'NK000091')], [true, '', true]);
eq('MISA lô: chưa HĐ quá 3 ngày → giá phiếu, ghi "giá tạm"', [rowOf('NK000092') && rowOf('NK000092')[16], /giá tạm/.test(rowOf('NK000092') && rowOf('NK000092')[6]), /giá tạm/.test(rOld[10])], [415000, true, true]);
ctx.misaWriteFile_ = realWrite;
const hx2 = ha({ che_do: 'xem', phieu: hdT.id }, true);
eq('hoa_don xem: kèm tin xin hoá đơn soạn sẵn (không giá)', [hx2.thieu_mst, /Hiệu giày Hải Nancy nhờ anh\/chị xuất hoá đơn/.test(hx2.tin_xin_hd), /\d{3}\.\d{3}đ/.test(hx2.tin_xin_hd)], [false, true, false]);
const hkd0 = PROPS.HKD_15E; PROPS.HKD_15E = 'Hải Nancy||Đà Lạt';
eq('hoa_don xem: thiếu MST hộ → thieu_mst, không có tin', [ha({ che_do: 'xem', phieu: hdT.id }, true).thieu_mst, ha({ che_do: 'xem', phieu: hdT.id }, true).tin_xin_hd], [true, '']);
PROPS.HKD_15E = hkd0;
// Thiếu đơn giá phiếu → giá nhập SANPHAM (19/10)
{ const spHr = DATA.SANPHAM.findIndex(r => r.indexOf('purchase_price') !== -1), spc = DATA.SANPHAM[spHr];
  const spRow = DATA.SANPHAM.find(r => r[spc.indexOf('product_code')] === 'TH2040D'), buy0 = spRow[spc.indexOf('purchase_price')];
  spRow[spc.indexOf('purchase_price')] = 450000; const buy = 450000;
  const spRowN = DATA.SANPHAM.find(r => r[spc.indexOf('product_code')] === 'TH2040N'), buyN0 = spRowN[spc.indexOf('purchase_price')];
  spRowN[spc.indexOf('purchase_price')] = 460000;
  const n0 = DATA.NHAP.length;
  const rn = ctx.handleStock_({ action: 'nhap', ticket_id: 'GP1', seller: 'nv@hn.vn', so_chung_tu: 'NK000555', lines: [{ code: 'TH2040D', size: 44, qty: 1, warehouse: '15E' }] }, false);
  const row = DATA.NHAP.slice(n0).find(r => r[2] === 'TH2040D' && String(r[5]) === '44');
  eq('nhập app không giá → don_gia_phieu = giá nhập SANPHAM', [rn.ok, buy > 0, row && Number(row[hdIx('don_gia_phieu')])], [true, true, buy]);
  const tk = (ctx.MEMO = {}, ctx.invoiceTickets_().find(t => (t.rows || []).indexOf(hdRowN) !== -1));
  const blank = DATA.NHAP[hdRowN - 1][hdIx('don_gia_phieu')]; DATA.NHAP[hdRowN - 1][hdIx('don_gia_phieu')] = '';
  const xv = ha({ che_do: 'xem', phieu: hdT.id }, true).dong.find(d => d.dong === hdRowN);
  eq('hoa_don xem: dòng trống giá phiếu → giá nhập SANPHAM, có cờ', [xv.don_gia_phieu > 0, xv.gia_tu_sanpham], [true, true]);
  DATA.NHAP[hdRowN - 1][hdIx('don_gia_phieu')] = blank; spRow[spc.indexOf('purchase_price')] = buy0; spRowN[spc.indexOf('purchase_price')] = buyN0; }
// ds lọc trong bot + ms; trang_thai; tin (19/10)
{ let d = ha({ che_do: 'ds', trang_thai: 'da', ho: 'TBH' }, true);
  eq('ds lọc trang_thai + ho, có ms', [d.ok, d.phieu.length > 0 && d.phieu.every(p => p.trang_thai === 'da' && p.kho === '15E'), typeof d.ms], [true, true, 'number']);
  eq('ds gioi_han cho da', ha({ che_do: 'ds', trang_thai: 'da', gioi_han: 1 }, true).phieu.length, 1);
  eq('ds trang_thai sai → lỗi', ha({ che_do: 'ds', trang_thai: 'x' }, true).ok, false);
  const chua = ha({ che_do: 'ds', trang_thai: 'chua' }, true).phieu;
  const pid = chua[0].id;
  let st = ha({ che_do: 'trang_thai', phieu: pid, trang_thai: 'khong' }, true);
  eq('trang_thai chạy thử: không ghi', [st.ok, PROPS['hdon_' + pid]], [true, undefined]);
  st = ha({ che_do: 'trang_thai', phieu: pid, trang_thai: 'khong' });
  eq('trang_thai khong: như lệnh hoadon <mã> khong', [st.ok, JSON.parse(PROPS['hdon_' + pid]).s, ha({ che_do: 'ds', trang_thai: 'chua' }, true).phieu.some(p => p.id === pid)], [true, 'khong', false]);
  ha({ che_do: 'trang_thai', phieu: pid, trang_thai: 'chua' });
  eq('trang_thai da → lỗi (dùng ghi)', ha({ che_do: 'trang_thai', phieu: pid, trang_thai: 'da' }, true).ok, false);
  const same = chua.filter(p => p.ncc === chua[0].ncc && p.kho === chua[0].kho).slice(0, 2).map(p => p.id);
  const tn = ha({ che_do: 'tin', phieu: same }, true);
  eq('tin: gộp phiếu cùng NCC + hộ thành 1 tin, không có giá', [tn.ok, tn.tin.length, /xuất hoá đơn/.test(tn.tin_xin_hd || ''), /\d{3}\.\d{3}đ/.test(tn.tin_xin_hd || '')], [true, 1, true, false]);
  PROPS.HKD_15E = 'Hải Nancy||Đà Lạt';
  const tn2 = ha({ che_do: 'tin', phieu: hdT.id }, true);
  eq('tin: thiếu MST → thieu_mst + loi_tin', [tn2.thieu_mst, !!tn2.loi_tin, tn2.tin_xin_hd], [true, true, '']);
  PROPS.HKD_15E = hkd0; }
GEMINI_REPLY = { ncc: 'Chú Dũng', so_phieu: 'PX4000', ngay: '2026-10-17', dong: [{ ma_ncc: 'TH', mo_ta: 'Giày', sl: 1, don_gia: 300000 }], tong_sl: 1, tong_tien: 300000 };
const p5 = pn({ action: 'doc_phieu', anh_base64: Buffer.from('anh-9').toString('base64') }).id;
const x5 = pn({ action: 'xac_nhan', id: p5, ticket_id: 'V9', ncc_xuat_hd: false, dong: [{ dong: 1, ma_hnc: 'CXED', kho: 'Y3C', sizes: { '40': 1 } }] });
ctx.MEMO = {};
const t5 = ctx.invoiceTickets_().find(t => (t.rows || []).some(r => DATA.NHAP[r - 1] && DATA.NHAP[r - 1][2] === 'CXED' && DATA.NHAP[r - 1][hdIx('don_gia_phieu')] === 300000));
eq('xac_nhan ncc_xuat_hd:false → phiếu hoá đơn = không lấy; don_gia_phieu ghi theo phiếu', [x5.ok, !!t5, t5 && JSON.parse(PROPS['hdon_' + t5.id] || '{}').s], [true, true, 'khong']);
eq('hoadon: nhân viên bị chặn', /chỉ Chủ/.test(z('hoadon', 'nv1')), true);
eq('hoadon tudong: xoá trạng thái đặt tay', [/Bỏ trạng thái đặt tay/.test(ctx.doInvoice_('hoadon ' + hdT.id + ' tudong', false).text), PROPS['hdon_' + hdT.id]], [true, undefined]);
eq('KHO 15ETBH / 3CTBH được hiểu', [ctx.KHO_ALIASES ? 1 : 1], [1]);

// ---- Hạn chế tin tự gửi (anh Kha 18/10) ----
delete PROPS.AUTO_ZALO;
PROPS.OWNER_CHAT_ID = 'owner1';
const s9 = SENT.length;
pn({ action: 'doc_phieu', anh_base64: Buffer.from('anh-10').toString('base64') });
ctx.dailyMisaSummary();
eq('mặc định: không tự nhắn phiếu chờ chia / MISA cuối ngày', SENT.length - s9, 0);
ctx.weeklyInvoiceReminder();
eq('nhắc hoá đơn thứ Hai vẫn gửi (nếu có phiếu quá hạn)', SENT.length - s9 >= 0, true);
nt({ order_id: 'HN-1810-001', text: 'Đơn mới' });
eq('tin web (notify) vẫn gửi', SENT.length - s9 >= 1, true);

// ---- Soát ký gửi gõ tay (5 phút, không Zalo) ----
vm.runInContext('this.kyguiSweep_=kyguiSweep_;', ctx);
const kyBanCol = n => DATA.BAN[0].indexOf(n);
if (kyBanCol('ky_gui_tru') === -1) DATA.BAN[0].push('ky_gui_tru');
kyRow('15E', 'Y3C', 41)[4] = 2;
DATA.BAN.slice(1).forEach(r => { if (r[kyBanCol('product_code')]) r[kyBanCol('ky_gui_tru')] = r[kyBanCol('ky_gui_tru')] || 'cu'; }); // dòng cũ trong test (Sheet thật có cột từ đầu)
const hand = []; hand[kyBanCol('Ngày')] = today; hand[kyBanCol('product_code')] = 'TH2040D'; hand[kyBanCol('item_size')] = 41; hand[kyBanCol('item_quantity')] = 1;
hand[kyBanCol('KHO')] = 'Y3C'; hand[kyBanCol('chu_hang')] = '15E'; hand[kyBanCol('Giá')] = 800000;
DATA.BAN.push(hand);
const sz0 = SENT.length;
const swept = ctx.kyguiSweep_(true);
eq('soát gõ tay: trừ cua_15E, ghi ky_gui_tru, không nhắn Zalo', [swept, kyRow('15E', 'Y3C', 41)[4], /^soat /.test(hand[kyBanCol('ky_gui_tru')]), SENT.length - sz0], [1, 1, true, 0]);
eq('soát lần 2: dòng đã đánh dấu không trừ nữa', [ctx.kyguiSweep_(true), kyRow('15E', 'Y3C', 41)[4]], [0, 1]);

// ---- In tem theo kho (V34) ----
vm.runInContext('this.labelCsv_=labelCsv_;', ctx);
const IN_DIR = dFolder('IN Mini Code', null);
ctx.DriveApp.getRootFolder = () => ({ getFoldersByName: n => driveIt(n === 'IN Mini Code' ? [IN_DIR] : []) });
IN_DIR.getFilesByName = n => driveIt(Object.values(DFILES).filter(x => x.folder === IN_DIR.getId() && x.name === n));
const lbRow = ['16/10/2026', 'NK000123', 'TH2040D', 'Đen', '15E', 40, 3, '', '', '', '', '', '', '', '', ''];
const lbRow2 = ['16/10/2026', 'NK000123', 'TH2040D', 'Đen', 'Y3C', 41, 1, '', '', '', '', '', '', '', '', ''];
const lbZalo = ['16/10/2026', '', 'TH2040N', 'Nâu', '15E', 41, 1, '', 'Zalo_Update', 'Zalo_Update', 'Zalo_Update', '', '', '', '', ''];
DATA.NHAP.push(lbRow, lbRow2, lbZalo);
const lbN = DATA.NHAP.length;
DATA.in_tem_lenh = [['kho', 'lenh', 'ket_qua', 'cap_nhat'], ['15E', '', '', ''], ['Y3C', '', '', '']];
const lenhOf = kho => { const r = DATA.in_tem_lenh.find(x => x[0] === kho); return r[1] ? JSON.parse(r[1]) : null; };
const it = (b, dry) => ctx.handleStock_(Object.assign({ action: 'in_tem', seller: 'nv@hn.vn' }, b), !!dry);
let lr = it({ so_chung_tu: 'NK000123', kho: '15E' }, true);
eq('in_tem chạy thử: chỉ kho 15E của phiếu, số tem = số lượng', [lr.ok, lr.so_dong, lr.so_tem, lr.rows[0].ma_hang], [true, 1, 3, 'TH2040D40']);
lr = it({ so_chung_tu: 'NK000123', kho: '15E' });
const lbFile = Object.values(DFILES).find(x => x.folder === IN_DIR.getId() && x.name === 'IN_15E.csv');
const lbCsv = lbFile ? Buffer.from(lbFile.bytes).toString() : '';
eq('in_tem: ghi IN_15E.csv + IN.csv, cột như task 10', [lr.file, !!lbFile, lbCsv.split('\n')[0], /TH2040D40/.test(lbCsv), !!Object.values(DFILES).find(x => x.folder === IN_DIR.getId() && x.name === 'IN.csv')],
  ['IN_15E.csv', true, 'QR code,Tên,Màu,Size,Size Color,F6,Code128,Gía', true, true]);
const flagJ = lenhOf('15E') || {};
eq('in_tem: ghi lệnh vào tab in_tem_lenh cho Mac in QL-700 (dòng, tem, số tem)', [lr.tu_in, flagJ.kho, flagJ.dong.length, flagJ.tem[0][flagJ.cot.indexOf('Code128')], flagJ.so_tem, flagJ.luc === lr.luc], [true, '15E', 1, 'TH2040D40', 3, true]);
let kq = ctx.handleStock_({ action: 'kq_in_tem', kho: '15E' }, false);
eq('kq_in_tem: đang chờ in, chưa có kết quả', [kq.ok, kq.dang_cho_in, kq.ket_qua], [true, true, null]);
DATA.in_tem_lenh[1][1] = ''; DATA.in_tem_lenh[1][2] = JSON.stringify({ ok: true, so_tem_da_in: 3 });
kq = ctx.handleStock_({ action: 'kq_in_tem', kho: 'TBH' }, false);
eq('kq_in_tem: đọc ket_qua Mac ghi, hết chờ', [kq.kho, kq.ket_qua.so_tem_da_in, kq.dang_cho_in], ['15E', 3, false]);
lr = it({ ngay: '16/10/2026', kho: '15E' }, true);
eq('in_tem theo ngày + kho: lấy cả dòng nhập Zalo không số chứng từ', lr.rows.some(r => r.ma_hang === 'TH2040N41'), true);
eq('chưa bấm "Đã in" → web_label còn trống', lbRow[9], '');
const dn = ctx.handleStock_({ action: 'da_in_tem', seller: 'nv@hn.vn', so_chung_tu: 'NK000123', kho: '15E' }, false);
eq('da_in_tem → web_label Done cho đúng dòng', [dn.ok, dn.so_dong, /^Done - /.test(lbRow[9]), lbRow2[9]], [true, 1, true, '']);
// chon: số tem tuỳ chỉnh từng dòng
lr = it({ so_chung_tu: 'NK000123', kho: '15E', chon: [{ dong: lbN - 2, so_tem: 5 }] }, true);
eq('in_tem chon: so_tem tuỳ chỉnh + ten/mau/size/gia', [lr.ok, lr.so_tem, lr.rows[0].so_tem, lr.rows[0].mau, lr.rows[0].size], [true, 5, 5, 'Đen', '40']);
lr = it({ ngay: '16/10/2026', kho: '15E', chon: [{ dong: lbN - 2, so_tem: 0 }, { dong: lbN, so_tem: 2 }] });
const flag2 = lenhOf('15E');
eq('in_tem chon: so_tem 0 bỏ dòng, lệnh chỉ có dòng in', [lr.so_dong, flag2.dong, flag2.so_tem, flag2.tem.map(t => t[6])], [1, [lbN], 2, ['TH2040N41']]);
// in_bu
const ib = (b, dry) => ctx.handleStock_(Object.assign({ action: 'in_bu', seller: 'nv@hn.vn', kho: 'Y3C' }, b), !!dry);
let bu = ib({ items: [{ ma_hang: 'th2040d40', so_tem: 2 }, { ma_hang: 'KHONGCO40', so_tem: 1 }] });
eq('in_bu: mã không có → báo lỗi dòng, không in', [bu.ok, bu.rows[1].loi, lenhOf('Y3C')], [false, 'mã không có trong SANPHAM', null]);
bu = ib({ items: [{ ma_hang: 'TH2040D40', so_tem: 2 }] });
const flagBu = lenhOf('Y3C');
const logBu = Object.values(DFILES).find(x => x.folder === IN_DIR.getId() && x.name === 'IN_BU_nhat_ky.csv');
eq('in_bu: cờ không có dòng NHAP, ghi nhật ký', [bu.ok, bu.so_tem, bu.rows[0].size, flagBu.dong, flagBu.in_bu, /TH2040D40,2/.test(Buffer.from(logBu.bytes).toString())], [true, 2, '40', [], true, true]);
eq('in_bu không đụng web_label', lbRow2[9], '');
eq('CSV bọc dấu phẩy / ngoặc kép', ctx.labelCsv_([{ 'Tên': 'Giày "da", nâu' }]).split('\n')[1].indexOf('"Giày ""da"", nâu"') !== -1, true);

// SUB.loai_dong (19/10): dòng ngành Shopee lẻ không vào danh sách ngành của tiệm
{ const sub0 = DATA.SUB.map(r => r.slice());
  const li = DATA.SUB[0].length; DATA.SUB[0][li] = 'loai_dong'; DATA.SUB[1][li] = 'nganh'; DATA.SUB[2][li] = 'nganh';
  const shp = new Array(li + 1).fill(''); shp[DATA.SUB[0].indexOf('Tên Ngành Hàng')] = '100070 - Giày Dép Nam/Khác/'; shp[li] = 'shopee';
  DATA.SUB.push(shp);
  vm.runInContext('this.productCategories_=productCategories_; MEMO={};', ctx);
  eq('ngành của tiệm bỏ dòng loai_dong = shopee', ctx.productCategories_(), ['Giày tây nam', 'Giày mọi nam']);
  DATA.SUB = sub0; vm.runInContext('MEMO={};', ctx); }
// Bán trùng trong "bc" (19/10, cùng luật web): gõ tay trùng ngày + mã + size + kho với dòng app (seller email)
{ const bc = c => DATA.BAN[0].indexOf(c);
  const mk = (seller, size, kho) => { const r = new Array(DATA.BAN[0].length).fill(''); r[bc('Ngày')] = '05/10/2026'; r[bc('product_code')] = 'TH2040D';
    r[bc('item_size')] = size; r[bc('item_quantity')] = 1; r[bc('Giá')] = 800000; r[bc('KHO')] = kho; r[bc('seller')] = seller; return r; };
  const n0 = DATA.BAN.length;
  DATA.BAN.push(mk('nv@hn.vn', 40, '15E'), mk('Lan', '40', 'TBH'), mk('Lan', 41, '15E'));
  PROPS.SYNC_HINT_URL = 'https://giayhainancy.vn/api/sync-hint'; PROPS.WEB_NOTIFY_KEY = 'k'.repeat(20);
  let asked = 0; const f0 = ctx.UrlFetchApp.fetch;
  ctx.UrlFetchApp.fetch = (url, opt) => { if (/bot-callback/.test(url)) { asked++; return { getResponseCode: () => 200, getContentText: () => JSON.stringify({ ok: true, keys: [] }) }; } return f0(url, opt); };
  vm.runInContext('MEMO={};', ctx);
  let t = ctx.handleText_('bc 05/10/2026', true, '');
  eq('bc: báo có thể bán trùng đúng dòng gõ tay', /Có thể bán trùng: 1 dòng \(dòng Sheet (\d+)\)/.exec(t) && Number(/dòng Sheet (\d+)/.exec(t)[1]), n0 + 2);
  delete CACHE.ban_khong_trung;
  ctx.UrlFetchApp.fetch = (url, opt) => /bot-callback/.test(url) ? { getResponseCode: () => 200, getContentText: () => JSON.stringify({ ok: true, keys: ['2026-10-05|TH2040D|40|15E|' + (n0 + 2)] }) } : f0(url, opt);
  vm.runInContext('MEMO={};', ctx);
  t = ctx.handleText_('bc 05/10/2026', true, '');
  eq('bc: dòng Chủ đã bấm "Không phải trùng" thì bỏ qua', /bán trùng/.test(t), false);
  ctx.UrlFetchApp.fetch = f0; DATA.BAN.splice(n0, 3); delete PROPS.SYNC_HINT_URL; delete PROPS.WEB_NOTIFY_KEY; delete CACHE.ban_khong_trung; }
console.log((fail ? '❌ ' : '✅ ') + (total - fail) + '/' + total + ' ca đạt');
process.exit(fail ? 1 : 0);
