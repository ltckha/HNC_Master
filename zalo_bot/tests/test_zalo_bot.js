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
        setValue: v => { WRITES.push({ sheet: n, cell: [r, c], v }); if (n !== 'SANPHAM' && n !== 'META') put(v); },
        setFormula: v => { WRITES.push({ sheet: n, cell: [r, c], v }); put(v); },
        clearContent: () => put(''),
      };
    },
    getRangeList: list => ({ setValue: v => WRITES.push({ sheet: n, cells: list, v }) }),
  };
}
const CACHE = {};
const ctx = {
  console,
  Utilities: { DigestAlgorithm: { MD5: 'md5' }, Charset: { UTF_8: 'utf8' }, computeDigest: (a, t) => Array.from(require('crypto').createHash('md5').update(t).digest()).map(b => (b > 127 ? b - 256 : b)), formatDate: (d, tz, f) => {
    const parts = {};
    new Intl.DateTimeFormat('en-GB', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
      .formatToParts(d).forEach(x => { parts[x.type] = x.value; });
    return f.replace('yyyy', parts.year).replace('yy', parts.year.slice(-2)).replace('MM', parts.month).replace('dd', parts.day).replace('HH', parts.hour).replace('mm', parts.minute);
  } },
  SpreadsheetApp: { getActiveSpreadsheet: () => ({ getSheetByName: n => DATA[n] ? mockSheet(n) : null }) },
  PropertiesService: { getScriptProperties: () => ({ getProperty: k => PROPS[k] || null, setProperty: (k, v) => { PROPS[k] = v; }, getProperties: () => PROPS, deleteProperty: k => { delete PROPS[k]; } }) },
  LockService: { getScriptLock: () => ({ waitLock() {}, tryLock: () => true, releaseLock() {} }), getDocumentLock: () => ({ tryLock: () => true, releaseLock() {} }) },
  DriveApp: { getFolderById: () => driveFolder('root', Object.keys(DRIVE).map(h => driveFolder(h, Object.keys(DRIVE[h]).map(sp => driveFolder(sp, DRIVE[h][sp].map(d => driveFolder(d, [], true))))))) },
  CacheService: { getScriptCache: () => ({ get: k => (k in CACHE ? CACHE[k] : null), put: (k, v) => { CACHE[k] = v; }, remove: k => { delete CACHE[k]; } }) },
};
vm.createContext(ctx);
const SENT = [];
const HINTS = [];
ctx.UrlFetchApp = { fetch: (url, opt) => {
  if (url.indexOf('sync-hint') !== -1) { HINTS.push({ url, body: JSON.parse(opt.payload) }); return { getResponseCode: () => 202, getContentText: () => '' }; }
  SENT.push(JSON.parse(opt.payload)); return { getResponseCode: () => 200, getContentText: () => '{"ok":true}' }; } };
ctx.ContentService = { createTextOutput: t => { const o = { t, setMimeType: () => o }; return o; }, MimeType: { JSON: 'json' } };
PROPS.BOT_TOKEN = 'x';
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'Code.gs'), 'utf8') + '\n;this.parseMessage_=parseMessage_;this.handleSale_=handleSale_;this.knownCodes_=knownCodes_;this.handleText_=handleText_;this.handleNotify_=handleNotify_;this.doPost=doPost;this.queueSyncHint_=queueSyncHint_;this.appendNhap_=appendNhap_;this.handleStock_=handleStock_;this.invoiceTickets_=invoiceTickets_;this.invoiceStatus_=invoiceStatus_;this.doInvoice_=doInvoice_;this.invoiceMessage_=invoiceMessage_;this.handleExport_=handleExport_;this.flushSyncHints=flushSyncHints;', ctx);

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
eq('trả lời trả hàng', [/↩️ TRẢ HÀNG: nhập lại TH2040D/.test(txt), /không xuất phiếu nhập MISA/.test(txt)], [true, true]);
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
eq('danh sách chỉ phiếu từ 01/09 chưa có', [/PHIẾU CHƯA CÓ HOÁ ĐƠN: 2/.test(txt), /260920-TP-15E/.test(txt), /260910-TP-Y3C/.test(txt), /260805/.test(txt)], [true, true, true, false]);
PROPS.HKD_15E = 'HKD A | 0312345678 | 15E Tăng Bạt Hổ';
txt = ctx.doInvoice_('hoadon 260920-tp-15e', true).text;
eq('câu nhắn soạn sẵn ghi rõ hộ + MST + hàng gọn theo mã cha', [/Đơn vị mua: HKD A/.test(txt), /MST: 0312345678/.test(txt), /\nTH2040 x 3\n/.test(txt), /Tổng: 3 sản phẩm\n/.test(txt), /×|\d\.000đ/.test(txt.split('Hàng hoá:')[1]), /kho 15E/.test(txt)], [true, true, true, true, false, true]);
txt = ctx.invoiceMessage_(ctx.invoiceTickets_().find(t => t.id === '260910-TP-15E'));
eq('gom 2 màu cùng mã cha (TH2040D 2 + TH2040N 1)', /\nTH2040 x 3\nTổng: 3 sản phẩm/.test(txt), true);
txt = ctx.doInvoice_('hoadon 260920-TP-15E da', false).text;
eq('ghi đã nhận tay', [/Đã ghi ✅ đã có hoá đơn: 260920-TP-15E/.test(txt), JSON.parse(PROPS['hdon_260920-TP-15E']).s], [true, 'da']);
ctx.doInvoice_('hoadon 260910-TP-Y3C khong', false);
eq('hết phiếu chưa có', /Không còn phiếu nào/.test(ctx.doInvoice_('hoadon', true).text), true);
eq('mã phiếu sai', /Không có phiếu nào/.test(ctx.doInvoice_('hoadon 999999', true).text), true);
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

// ---- Báo web chép Sheet ----
ctx.queueSyncHint_(['BAN']);
eq('chưa cấu hình URL → không gửi', HINTS.length, 0);
delete CACHE.sync_q;
PROPS.SYNC_HINT_URL = 'https://web.example/api/sync-hint'; PROPS.SYNC_HINT_KEY = 'synckey_1234567890';
ctx.queueSyncHint_(['BAN']);
eq('BAN đổi → gửi kèm KHO15E, KHOY3C', [HINTS.length, HINTS[0] && HINTS[0].body.tabs, /key=synckey_1234567890/.test(HINTS[0] && HINTS[0].url)], [1, ['KHO15E', 'KHOY3C', 'BAN'], true]);
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

console.log((fail ? '❌ ' : '✅ ') + (total - fail) + '/' + total + ' ca đạt');
process.exit(fail ? 1 : 0);
