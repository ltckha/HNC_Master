// Ca mẫu luật kho (P0, 20/10): chạy shared/ca_mau_luat_kho.json trên shared/luat_kho.js (mới) và trên hàm cũ của zalo_bot/Code.gs
// (qua vm, thay phần đọc / ghi Sheet bằng dữ liệu của ca). Mới, cũ và "ra" của ca phải y hệt.
// Chạy: node tests/test_luat_kho.js
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const L = require(path.join(ROOT, 'shared', 'luat_kho.js'));
const CASES = JSON.parse(fs.readFileSync(path.join(ROOT, 'shared', 'ca_mau_luat_kho.json'), 'utf8')).ca;

// ---- Nạp Code.gs cũ (chỉ cần hàm, không chạy doPost) ----
const ctx = { console, Date, JSON, Math, Number, String, Object, Array, RegExp, isNaN, parseInt, parseFloat, Set };
ctx.Utilities = { formatDate: (d, tz, fmt) => (ctx.__today && fmt === 'yyyy-MM-dd' ? ctx.__today : '2026-10-20'), newBlob: () => ({}) };
ctx.PropertiesService = { getScriptProperties: () => ({ getProperty: () => null, getProperties: () => ({}), setProperty() {}, deleteProperty() {} }) };
ctx.CacheService = { getScriptCache: () => ({ get: () => null, put() {}, remove() {} }) };
ctx.LockService = { getScriptLock: () => ({ waitLock() {}, tryLock: () => true, releaseLock() {} }), getDocumentLock: () => null };
ctx.SpreadsheetApp = { getActiveSpreadsheet: () => ({ getSheetByName: () => null }) };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(ROOT, 'zalo_bot', 'Code.gs'), 'utf8') + `
;this.__old = { parseMessage_, kyguiSale_, kyguiTransfer_, kyguiReturn_, kyguiCheck_, receiptNkPlan_, saleDupRows_, rowSrcStart_, rowSrcFields_, receiptUndoGuard_, parsePercent_, normSize_, moneyValue_, dateKey_, KHO_ALIASES, KYGUI_COL };
this.__set = (name, fn) => { eval(name + ' = fn'); };
this.__memo = () => { MEMO = {}; CTX = { pending: {} }; };`, ctx);
const O = ctx.__old;
const stub = (name, fn) => ctx.__set(name, fn);

function adjCapture() {
  const doi = [];
  stub('kyguiAdjust_', (chu, at, code, size, delta) => { doi.push({ kho: at, cot: O.KYGUI_COL[at], delta }); return null; });
  return doi;
}

// Bộ chuyển: gọi hàm cũ với dữ liệu của ca, trả kết quả theo dạng của luat_kho.js
const OLD = {
  tachMaSize(tok, ma, goc) {
    ctx.__memo();
    const p = O.parseMessage_('ban ' + tok + ' TBH', { codes: new Set(ma), bases: new Set(goc) });
    // Cũ: tách được khi ra đúng 1 mã đã biết và 1 size từ chính token đó
    const whole = String(tok).replace(/[^a-z0-9]/gi, '').toUpperCase();
    if (!p.code || p.code === whole || p.sizes.length !== 1 || ma.indexOf(p.code) === -1) return null;
    return { ma: p.code, size: p.sizes[0].size };
  },
  banTachChuHang(kho, qty, ky) {
    ctx.__memo();
    stub('kyguiQty_', () => Math.max(0, Number(ky) || 0));
    const doi = adjCapture();
    const r = O.kyguiSale_('X1', '', 0, '40', qty, kho, '', '', true);
    return { phan: r.phan, doi_cot: doi };
  },
  huyBanKhoiPhuc(doiLucBan) {
    // Cũ: op ký gửi lưu {before, after}; huỷ = ghi lại before → thay đổi = before − after
    return doiLucBan.map(d => { const op = { before: 10, after: 10 + d.delta }; return { kho: d.kho, cot: d.cot, delta: op.before - op.after }; });
  },
  chuyenKhoKyGui(tu, den, qty, ky) {
    ctx.__memo();
    stub('kyguiOn_', () => true);
    stub('kyguiQty_', (chu, at) => (chu === den && at === tu ? Math.max(0, Number(ky) || 0) : 0));
    const doi = adjCapture();
    const r = O.kyguiTransfer_('X1', '40', qty, tu, den, true);
    return { ghi_chu: r.notes.map(n => ({ loai: n.loai, chu_hang: n.chu_hang, qty: n.qty })), doi_cot: doi };
  },
  traHangChuHang(kho, code, size, qty, chu, ban) {
    ctx.__memo();
    stub('kyguiOn_', () => true);
    stub('sheetValues_', () => [['product_code', 'item_size', 'KHO', 'chu_hang']].concat(ban.map(b => [b.code, b.size, b.kho, b.chu_hang])));
    const doi = adjCapture();
    const r = O.kyguiReturn_(code, size, qty, kho, chu, true);
    return { chu_hang: r.chu_hang, doi_cot: doi };
  },
  canhBaoKyGui(ky, ton, traVe) {
    ctx.__memo();
    stub('kyguiOn_', () => true);
    stub('kyguiQty_', () => ky);
    stub('findKhoRows_', () => [{ current_quantity: ton }]);
    return !!O.kyguiCheck_('X1', '40', '15E', traVe);
  },
  soNhapKho(dong, khos, ncc, homNay, _chuan, nkCuoi) {
    ctx.__memo();
    ctx.__today = homNay;
    const sup = {};
    const meta = [['key', 'value', 'updated_at']].concat(Object.keys(nkCuoi || {}).map(k => ['nk_cuoi_' + k, String(nkCuoi[k]), '']));
    stub('sheetValues_', name => name === 'META' ? meta : [['Ngày chứng từ (*)', 'Số chứng từ (*)', 'product_code', 'KHO']].concat(dong.map((r, i) => {
      sup['M' + i] = r.ncc;
      const [y, m, d] = r.ngay_key.split('-');
      return [d + '/' + m + '/' + y, r.so, 'M' + i, r.kho];
    })));
    stub('productSuppliers_', () => sup);
    stub('receiptByNhap_', () => null);
    const out = O.receiptNkPlan_(khos, ncc);
    ctx.__today = null;
    return out;
  },
  giaMisa(d) {
    // Cũ (misaStockExport_ / main.py task 8): giaHd || giaPhieu || (inv > 0 ? inv : pur); tags 'giá tạm' / 'giá cũ theo mã'
    const giaHd = O.moneyValue_(d.don_gia_hd), giaPhieu = O.moneyValue_(d.don_gia_phieu), inv = O.moneyValue_(d.invoice_price), pur = O.moneyValue_(d.purchase_price);
    const lot = giaHd || giaPhieu;
    const gia = lot || (inv > 0 ? inv : pur);
    return { gia, nguon: giaHd ? 'hd' : giaPhieu ? 'phieu' : inv > 0 ? 'invoice' : pur ? 'purchase' : '', gia_tam: !String(d.so_hd || '').trim(), gia_cu: !lot };
  },
  donGiaPhieuMoi(gia, pur) {
    // Cũ (appendNhap_): (CTX.receiptId && CTX.donGiaPhieu) || spPurchasePrice_(code); 0 → không ghi ô
    return O.moneyValue_(gia) || O.moneyValue_(pur) || 0;
  },
  tonKho(f, dau, nhap, xuat, ban) {
    // Cũ = công thức Sheet: =E + SUMIF(NHAP!FSKU; A; SL) − SUMIF(XUAT…) − SUMIF(BAN…)
    const sumif = list => list.filter(r => r.fsku === f).reduce((t, r) => t + Number(r.qty), 0);
    return Number(dau) + sumif(nhap) - sumif(xuat) - sumif(ban);
  },
  fsku(kho, code, size) {
    // Cũ: =CONCATENATE(KHO; product_code; item_size) — mã IN HOA, size dạng Sheet
    return kho + String(code).trim().toUpperCase() + O.normSize_(size);
  },
  banTrung(dongs, boQua) {
    ctx.__memo();
    const days = Array.from(new Set(dongs.map(r => r.ngay_key)));
    stub('sheetValues_', () => {
      const rows = [['Ngày', 'product_code', 'item_size', 'KHO', 'seller']];
      dongs.forEach(r => { const [y, m, d] = r.ngay_key.split('-'); rows[r.dong - 1] = [d + '/' + m + '/' + y, r.code, r.size, r.kho, r.seller]; });
      for (let i = 0; i < rows.length; i++) if (!rows[i]) rows[i] = ['', '', '', '', ''];
      return rows;
    });
    const keys = {}; (boQua || []).forEach(k => { keys[k] = true; });
    stub('saleDupIgnore_', () => ({ ok: true, keys }));
    return [].concat(...days.map(d => O.saleDupRows_(d).rows)).sort((a, b) => a - b);
  },
  maDong(nguon, d, n) {
    // Cũ (bot rowSrcStart_ / rowSrcFields_): gốc theo thao tác, đếm thứ tự trong 1 thao tác. 'tay' do web cấp (bot không có) → theo quy ước hợp đồng
    if (nguon === 'tay') return 'TAY-' + d.ngay.replace(/-/g, '') + '-' + d.dong;
    const goc = nguon === 'phieu' ? d.phieu_id : nguon === 'zalo' ? 'Z-' + d.msg_id : nguon === 'mac' ? 'MAC-' + d.lan_chay : d.ticket;
    O.rowSrcStart_(nguon, goc);
    let f = {};
    for (let i = 0; i < n; i++) f = O.rowSrcFields_('NHAP');
    return f.ma_dong || '';
  },
  soNhapKe(so) {
    // Cũ: receiptNkPlan_ = số lớn nhất của kho + 1
    const m = String(so).match(/(\d+)$/);
    return OLD.soNhapKho(m ? [{ so: 'NK' + m[1], kho: '15E', ngay_key: '2000-01-01', ncc: '' }] : [], ['15E'], '', '2026-10-20')['15E'];
  },
  soTraHang(k) {
    // Cũ (appendNhap_): 'TRA-' + formatDate(hôm nay, 'ddMMyy')
    const [y, m, d] = k.split('-'); return 'TRA-' + d + m + y.slice(2);
  },
  huyNhapKiem(maMoi, gd, cua) {
    const tabCache = {};
    ['NHAP', 'BAN', 'XUAT'].forEach(t => {
      const rows = [['product_code', 'item_size', 'KHO']];
      gd.filter(x => x.tab === t).forEach(x => { rows[x.dong - 1] = [x.code, x.size, x.kho]; });
      for (let i = 0; i < rows.length; i++) if (!rows[i]) rows[i] = ['', '', ''];
      tabCache[t] = rows;
    });
    const own = {}; Object.keys(cua).forEach(t => { own[t] = {}; cua[t].forEach(d => { own[t][d] = true; }); });
    return [].concat(...maMoi.map(g => O.receiptUndoGuard_(g, own, tabCache)));
  },
  misaNhapDong(d) {
    // Cũ: misaStockExport_ (đoạn tạo dòng o[1..22], dùng parsePercent_ của bot)
    const reasons = [];
    if (!d.so_ct) reasons.push('Thiếu số chứng từ'); if (!d.dvt) reasons.push('Thiếu ĐVT'); if (!d.ngay) reasons.push('Thiếu ngày');
    if (!(d.sl > 0)) reasons.push('Thiếu số lượng'); if (!(d.don_gia > 0)) reasons.push('Thiếu đơn giá');
    if (!d.ncc_ma && !d.ncc_ten) reasons.push('Thiếu NCC'); if (!d.kho_misa) reasons.push('Thiếu kho');
    if (reasons.length) return { cot: {}, loi: reasons };
    const tags = [d.so_hd ? '' : 'giá tạm', d.gia_cu ? 'giá cũ theo mã' : ''].filter(Boolean);
    const amount = d.sl * d.don_gia, ckRate = O.parsePercent_(d.ck), ck = Math.round(amount * ckRate * 100) / 100;
    const vatRate = O.parsePercent_(d.vat), tax = Math.round((amount - ck) * vatRate * 100) / 100;
    const o = {};
    o[1] = 'Nhập kho mua hàng'; o[2] = d.ngay; o[3] = d.so_ct; o[4] = d.ncc_ma; o[5] = d.ncc_ten;
    o[6] = (d.ncc_ten ? 'Nhập kho mua hàng từ ' + d.ncc_ten : 'Nhập kho mua hàng') + (d.so_hd ? ' · HĐ ' + d.so_hd + (d.ngay_hd ? ' ngày ' + d.ngay_hd : '') : '') + (tags.length ? ' (' + tags.join(', ') + ')' : '');
    o[7] = 'Chưa thanh toán'; o[8] = d.sku; o[12] = d.kho_misa; o[14] = d.dvt; o[15] = d.sl; o[16] = d.don_gia; o[17] = amount; o[18] = ckRate; o[19] = ck; o[20] = vatRate; o[21] = tax; o[22] = amount - ck + tax;
    return { cot: o, loi: [] };
  },
  khoChuan: v => O.KHO_ALIASES[String(v).trim().toUpperCase()] || '',
  ngayKey: v => O.dateKey_(v),
  soTien: v => O.moneyValue_(v),
};

let fail = 0;
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
CASES.forEach(c => {
  const moi = L[c.ham].apply(null, JSON.parse(JSON.stringify(c.vao)));
  const cu = OLD[c.ham].apply(null, JSON.parse(JSON.stringify(c.vao)));
  if (!same(moi, c.ra) || !same(cu, c.ra)) {
    fail++;
    console.log('❌ ' + c.ten + '\n   ra:  ' + JSON.stringify(c.ra) + '\n   mới: ' + JSON.stringify(moi) + '\n   cũ:  ' + JSON.stringify(cu));
  }
});
console.log((fail ? '❌ ' : '✅ ') + (CASES.length - fail) + '/' + CASES.length + ' ca mẫu: luat_kho.js = code cũ');
process.exit(fail ? 1 : 0);
