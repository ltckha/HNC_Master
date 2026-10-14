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
const ctx = {
  console,
  Utilities: { formatDate: (d, tz, f) => { const p = n => ('0' + n).slice(-2); return f.replace('yyyy', d.getFullYear()).replace('MM', p(d.getMonth() + 1)).replace('dd', p(d.getDate())); } },
  SpreadsheetApp: { getActiveSpreadsheet: () => ({ getSheetByName: n => DATA[n] ? { getDataRange: () => ({ getValues: () => DATA[n] }) } : null }) },
  PropertiesService: { getScriptProperties: () => ({ getProperty: k => PROPS[k] || null, setProperty: (k, v) => { PROPS[k] = v; }, getProperties: () => PROPS, deleteProperty: k => { delete PROPS[k]; } }) },
  LockService: { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) },
  CacheService: { getScriptCache: () => ({ get: () => null, put() {}, remove() {} }) },
};
vm.createContext(ctx);
const SENT = [];
ctx.UrlFetchApp = { fetch: (url, opt) => { SENT.push(JSON.parse(opt.payload)); return { getResponseCode: () => 200, getContentText: () => '{"ok":true}' }; } };
ctx.ContentService = { createTextOutput: t => { const o = { t, setMimeType: () => o }; return o; }, MimeType: { JSON: 'json' } };
PROPS.BOT_TOKEN = 'x';
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'Code.gs'), 'utf8') + '\n;this.parseMessage_=parseMessage_;this.handleSale_=handleSale_;this.knownCodes_=knownCodes_;this.handleText_=handleText_;this.handleNotify_=handleNotify_;this.doPost=doPost;', ctx);

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
eq('channel sai', sale({ ticket_id: 'T5', channel: 'facebook', lines: [{ code: 'TH2040D', size: 40, warehouse: 'Y3C' }] }).ok, false);
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

console.log((fail ? '❌ ' : '✅ ') + (total - fail) + '/' + total + ' ca đạt');
process.exit(fail ? 1 : 0);
