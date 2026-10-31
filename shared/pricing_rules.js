/**
 * LUẬT GỢI Ý GIÁ BÁN — bản chung (Agent đăng SP GĐ3b, anh Kha "LÀM" 28/10/2026).
 * JS thuần như luat_kho.js: KHÔNG đọc / ghi Sheet, không gọi mạng — chạy được trong Apps Script, Node (Mac gọi qua node) và Worker.
 *
 * Giá nhập 1 mã: giá lô mới nhất (don_gia_hd → don_gia_phieu), không có thì giá theo mã purchase_price (giá mua trên phiếu) → invoice_price
 *   (anh Kha 28/10: giá mua trước — khớp giá phiếu của mã mới; thử 2240 mã: 76% trong ±10% so với 62% khi invoice trước).
 * Tỷ lệ = trung vị (giá bán / giá nhập) các mã cùng NCC + nhóm hàng (≥ MIN_MA mã); thiếu thì chỉ cùng nhóm hàng; thiếu nữa → không gợi ý.
 * Giá gợi ý = giá nhập × tỷ lệ, làm tròn theo bước giá tem (LAM_TRON) như giá tem hiện nay.
 * Lý do KHÔNG chứa số tiền, KHÔNG chứa tên NCC (hợp đồng web goi_y_gia).
 */
var LuatGia = (function () {
  var PHIEN_BAN = '2026-10-28';
  var MIN_MA = 5;
  var LAM_TRON = 10000; // giá tem trên Sheet: 2237 / 2240 mã chia hết 10.000 (28/10)
  var GIA_MIN = 10000, GIA_MAX = 50000000;

  function so(v) {
    if (typeof v === 'number') return isFinite(v) && v > 0 ? Math.round(v) : 0;
    var d = String(v === null || v === undefined ? '' : v).replace(/[^\d]/g, '');
    return d ? Number(d) : 0;
  }

  function chu(v) {
    return String(v === null || v === undefined ? '' : v).trim();
  }

  /** Giá nhập: lo = {don_gia_hd, don_gia_phieu} (lô mới nhất, có thể trống), ma = {purchase_price, invoice_price}. */
  function giaNhap(lo, ma) {
    lo = lo || {}; ma = ma || {};
    return so(lo.don_gia_hd) || so(lo.don_gia_phieu) || so(ma.purchase_price) || so(ma.invoice_price); // giá mua trước (anh Kha 28/10)
  }

  function trungVi(ds) {
    var a = ds.slice().sort(function (x, y) { return x - y; });
    var n = a.length;
    return n % 2 ? a[(n - 1) / 2] : (a[n / 2 - 1] + a[n / 2]) / 2;
  }

  function lamTron(v) {
    return Math.round(v / LAM_TRON) * LAM_TRON;
  }

  /**
   * ma = {code, ncc, nhom, gia_nhap}; mau = [{code, ncc, nhom, gia_ban, gia_nhap}] (mã đã có giá bán, đã bỏ mã đang chờ duyệt).
   * → {code, gia, ly_do, so_ma, theo: 'ncc_nhom' | 'nhom'} hoặc {code, loi}.
   */
  function goiYGia(ma, mau) {
    var code = chu(ma.code).toUpperCase(), ncc = chu(ma.ncc).toLowerCase(), nhom = chu(ma.nhom), gn = so(ma.gia_nhap);
    if (!gn) return { code: code, loi: 'chưa có giá nhập' };
    if (!nhom) return { code: code, loi: 'chưa có nhóm hàng' };
    var cungNhom = (mau || []).filter(function (x) {
      return chu(x.code).toUpperCase() !== code && chu(x.nhom).toLowerCase() === nhom.toLowerCase() && so(x.gia_ban) && so(x.gia_nhap);
    });
    var cungNcc = ncc ? cungNhom.filter(function (x) { return chu(x.ncc).toLowerCase() === ncc; }) : [];
    var dung = cungNcc.length >= MIN_MA ? cungNcc : cungNhom.length >= MIN_MA ? cungNhom : null;
    if (!dung) return { code: code, loi: 'ít hơn ' + MIN_MA + ' mã cùng nhóm ' + nhom + ' để so' };
    var tyLe = trungVi(dung.map(function (x) { return so(x.gia_ban) / so(x.gia_nhap); }));
    var gia = lamTron(gn * tyLe);
    if (gia < GIA_MIN || gia > GIA_MAX) return { code: code, loi: 'giá gợi ý ngoài khoảng cho phép' };
    var theo = dung === cungNcc ? 'ncc_nhom' : 'nhom';
    return { code: code, gia: gia, so_ma: dung.length, theo: theo,
      ly_do: 'tỷ lệ trung vị ' + dung.length + ' mã cùng nhóm ' + nhom + (theo === 'ncc_nhom' ? ', cùng nhà cung cấp' : '') +
        ', làm tròn theo giá tem' };
  }

  /** Cả lô (1 lần gọi node từ Mac). Mỗi mã / mẫu chưa có gia_nhap thì tính bằng giaNhap(x.lo, x) — x mang invoice_price / purchase_price. */
  function goiYGiaLo(ds, mau) {
    var co = function (x) { return x.gia_nhap !== undefined ? x : Object.assign({}, x, { gia_nhap: giaNhap(x.lo, x) }); };
    var m = (mau || []).map(co);
    return (ds || []).map(function (x) { return goiYGia(co(x), m); });
  }

  return { PHIEN_BAN: PHIEN_BAN, MIN_MA: MIN_MA, LAM_TRON: LAM_TRON, giaNhap: giaNhap, trungVi: trungVi, lamTron: lamTron, goiYGia: goiYGia,
    goiYGiaLo: goiYGiaLo };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = LuatGia;
