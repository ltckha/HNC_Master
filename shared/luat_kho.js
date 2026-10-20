/**
 * LUẬT KHO HNC — bản chung (P0 phương án 3, anh Kha "Chốt làm luôn P0" 20/10/2026).
 * JS thuần, KHÔNG đọc / ghi Sheet, không gọi mạng: chạy được trong Apps Script (bot), Node (main.py gọi qua node, test)
 * và Cloudflare Worker (web). Hàm nhận dữ liệu đã đọc sẵn, trả kết quả / thay đổi cần ghi; phía gọi tự ghi.
 *
 * Nguồn luật: zalo_bot/Code.gs (bản @35). Ca mẫu: shared/ca_mau_luat_kho.json — chạy: node tests/test_luat_kho.js
 * (so cả code cũ trong Code.gs lẫn file này, kết quả phải y hệt).
 * Chưa nối vào bot / main.py / web đang chạy: đổi thật sau 26/10, anh xác nhận tại phiên Thực thi – HNC_Master.
 *
 * Quy ước: kho = '15E' | 'Y3C'. "Ký gửi" = hàng của hộ kia đang nằm trong kho này (cột KHO15E.cua_Y3C / KHOY3C.cua_15E).
 */
var LuatKho = (function () {
  var PHIEN_BAN = '2026-10-20';

  var KHO_ALIASES = { 'YEN': 'Y3C', 'Y3C': 'Y3C', '3C': 'Y3C', '3CTBH': 'Y3C', 'TBH': '15E', '15E': '15E', '15ETBH': '15E' };
  var COT_KY_GUI = { '15E': 'cua_Y3C', 'Y3C': 'cua_15E' }; // kho đang ở → cột "hàng của hộ kia"

  /** Tên kho chuẩn từ chữ người gõ / ô Sheet ('yen', '3c', 'TBH'…) → '15E' | 'Y3C' | ''. */
  function khoChuan(v) {
    return KHO_ALIASES[String(v === null || v === undefined ? '' : v).trim().toUpperCase()] || '';
  }

  function hoKia(kho) {
    return kho === 'Y3C' ? '15E' : 'Y3C';
  }

  /** Size như Sheet: 40, "40", "40.0" → "40"; trống → "". */
  function chuanSize(v) {
    var s = String(v === null || v === undefined ? '' : v).trim();
    return s.slice(-2) === '.0' ? s.slice(0, -2) : s;
  }

  /** Số tiền từ ô Sheet: 800000 | "800.000 đ" → 800000; trống → 0. */
  function soTien(v) {
    if (typeof v === 'number') return v;
    var d = String(v || '').replace(/[^\d]/g, '');
    return d ? Number(d) : 0;
  }

  /** "dd/mm/yyyy…" → "yyyy-mm-dd"; sai → "". (Ô Date của Sheet: phía gọi tự đổi trước.) */
  function ngayKey(v) {
    var m = String(v || '').trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    return m ? m[3] + '-' + ('0' + m[2]).slice(-2) + '-' + ('0' + m[1]).slice(-2) : '';
  }

  function coMa(tap, k) {
    if (!tap) return false;
    return typeof tap.has === 'function' ? tap.has(k) : tap.indexOf(k) !== -1;
  }

  /**
   * Mã dính size (tem quét "AP048N-40", gõ "AP048N40" / "ap048n_40" / "ap048n/40") → { ma, size } hoặc null.
   * Chỉ tách khi cả token không phải mã / mã gốc đã biết, phần đầu đúng 1 mã đã biết, phần đuôi là size 20–49 (có thể ,5 / .5).
   * maBiet / maGoc: Set hoặc mảng mã IN HOA. Token đã bỏ dấu, chữ thường hay hoa đều được.
   */
  function tachMaSize(token, maBiet, maGoc) {
    var t = String(token || '').toLowerCase();
    var ca = t.replace(/[^a-z0-9]/g, '').toUpperCase();
    if (!ca || coMa(maBiet, ca) || coMa(maGoc, ca)) return null;
    var m = t.match(/^([a-z0-9]+?)[-_\/.]?([2-4]\d(?:[.,]5)?)$/);
    if (!m || !coMa(maBiet, m[1].toUpperCase())) return null;
    return { ma: m[1].toUpperCase(), size: m[2] };
  }

  /**
   * Bán ở kho `kho` n đôi: hàng ký gửi của hộ kia bán trước.
   * kyGuiHoKia = số đôi của hộ kia đang ở kho này (ô cua_… của dòng KHO).
   * → { phan: [{ chu_hang, qty }], doi_cot: [{ kho, cot, delta }] } (doi_cot = thay đổi ô ký gửi cần ghi).
   */
  function banTachChuHang(kho, qty, kyGuiHoKia) {
    var other = hoKia(kho);
    var cons = Math.min(qty, Math.max(0, Number(kyGuiHoKia) || 0));
    var phan = [], doi = [];
    if (cons > 0) { phan.push({ chu_hang: other, qty: cons }); doi.push({ kho: kho, cot: COT_KY_GUI[kho], delta: -cons }); }
    if (qty - cons > 0) phan.push({ chu_hang: kho, qty: qty - cons });
    return { phan: phan, doi_cot: doi };
  }

  /** Huỷ bán: trả lại ô ký gửi đã trừ (đảo dấu doi_cot của lần bán). Dòng BAN xoá do phía gọi. */
  function huyBanKhoiPhuc(doiCotLucBan) {
    return (doiCotLucBan || []).map(function (d) { return { kho: d.kho, cot: d.cot, delta: -d.delta }; });
  }

  /**
   * Chuyển kho tu → den n đôi: trả hàng của hộ `den` đang ký gửi ở `tu` trước, phần còn lại thành ký gửi của hộ `tu` ở `den`.
   * kyGuiCuaDenTaiTu = ô cua_<den> của dòng KHO ở kho `tu`.
   * → { ghi_chu: [{ loai: 'tra_ve_chu' | 'thanh_ky_gui', chu_hang, qty }], doi_cot: [{ kho, cot, delta }] }
   */
  function chuyenKhoKyGui(tu, den, qty, kyGuiCuaDenTaiTu) {
    var back = Math.min(qty, Math.max(0, Number(kyGuiCuaDenTaiTu) || 0));
    var out = { ghi_chu: [], doi_cot: [] };
    if (back > 0) {
      out.ghi_chu.push({ loai: 'tra_ve_chu', chu_hang: den, qty: back });
      out.doi_cot.push({ kho: tu, cot: COT_KY_GUI[tu], delta: -back });
    }
    if (qty - back > 0) {
      out.ghi_chu.push({ loai: 'thanh_ky_gui', chu_hang: tu, qty: qty - back });
      out.doi_cot.push({ kho: den, cot: COT_KY_GUI[den], delta: qty - back });
    }
    return out;
  }

  /**
   * Khách trả hàng về kho `kho`: chủ hàng = chủ gửi kèm, không có thì theo dòng BAN gần nhất cùng mã / size / kho có chu_hang.
   * banDongs: [{ code, size, kho, chu_hang }] theo thứ tự dòng Sheet (cũ → mới). Chủ là hộ kia → cộng lại ô ký gửi.
   * → { chu_hang, doi_cot }
   */
  function traHangChuHang(kho, code, size, qty, chuGui, banDongs) {
    var chu = khoChuan(chuGui);
    if (!chu) {
      var list = banDongs || [];
      for (var i = list.length - 1; i >= 0; i--) {
        var b = list[i];
        if (String(b.code || '').trim().toUpperCase() !== code || chuanSize(b.size) !== size || khoChuan(b.kho) !== kho) continue;
        chu = khoChuan(b.chu_hang);
        if (chu) break;
      }
    }
    chu = chu || kho;
    return { chu_hang: chu, doi_cot: chu !== kho ? [{ kho: kho, cot: COT_KY_GUI[kho], delta: qty }] : [] };
  }

  /**
   * Cảnh báo (không chặn) sau khi xuất / bán / chuyển: số ký gửi còn lại > tồn kho đó.
   * traVe = số đôi chuyển về đúng kho của hộ chủ trong lần này (trả ký gửi trước, bản @32).
   */
  function canhBaoKyGui(kyGui, tonSauKhiTru, traVe) {
    var ky = Math.max(0, (Number(kyGui) || 0) - (Number(traVe) || 0));
    return ky > 0 && ky > (Number(tonSauKhiTru) || 0);
  }

  /**
   * Số chứng từ nhập kho cho lần xác nhận phiếu, theo từng kho: NK + 6 số.
   * Cùng kho + cùng NCC + cùng ngày (hôm nay) đã có số → dùng chung; khác → số lớn nhất của kho đó + 1.
   * dongNhap: [{ so, kho, ngay_key, ncc }] (ncc của dòng do phía gọi tra: phiếu NCC, không thì SANPHAM.supplier).
   */
  function soNhapKho(dongNhap, khos, ncc, homNayKey, chuanTen) {
    var cmp = chuanTen || function (s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd'); };
    var max = {}, same = {};
    (dongNhap || []).forEach(function (r) {
      var m = String(r.so || '').trim().toUpperCase().match(/^NK(\d+)$/);
      var kho = khoChuan(r.kho);
      if (!m || !kho) return;
      max[kho] = Math.max(max[kho] || 0, Number(m[1]));
      if (!ncc || same[kho] || r.ngay_key !== homNayKey) return;
      if (cmp(r.ncc || '') === cmp(ncc)) same[kho] = 'NK' + m[1];
    });
    var out = {};
    khos.forEach(function (k) { out[k] = same[k] || 'NK' + ('000000' + ((max[k] || 0) + 1)).slice(-6); });
    return out;
  }

  /**
   * Giá nhập kho MISA theo lô (anh Kha 17/10): don_gia_hd → don_gia_phieu → invoice_price → purchase_price.
   * → { gia, nguon: 'hd' | 'phieu' | 'invoice' | 'purchase' | '', gia_tam: chưa có số HĐ, gia_cu: không có giá lô }
   */
  function giaMisa(d) {
    var hd = soTien(d.don_gia_hd), ph = soTien(d.don_gia_phieu), inv = soTien(d.invoice_price), pur = soTien(d.purchase_price);
    var gia = hd || ph || (inv > 0 ? inv : pur);
    var nguon = hd ? 'hd' : ph ? 'phieu' : inv > 0 ? 'invoice' : pur ? 'purchase' : '';
    return { gia: gia, nguon: nguon, gia_tam: !String(d.so_hd || '').trim(), gia_cu: !(hd || ph) };
  }

  /** Đơn giá phiếu ghi vào dòng NHAP mới (19/10): giá trên phiếu NCC, không có thì giá nhập SANPHAM; 0 = để trống. */
  function donGiaPhieuMoi(giaTrenPhieu, purchasePrice) {
    return soTien(giaTrenPhieu) || soTien(purchasePrice) || 0;
  }

  /**
   * Tồn hiện tại của 1 dòng KHO = tồn đầu + SUMIF(NHAP) − SUMIF(XUAT) − SUMIF(BAN) theo FSKU (= KHO + mã + size), như công thức Sheet.
   * nhap / xuat / ban: [{ fsku, qty }].
   */
  function tonKho(fsku, tonDau, nhap, xuat, ban) {
    var sum = function (list) { return (list || []).reduce(function (t, r) { return t + (r.fsku === fsku ? (Number(r.qty) || 0) : 0); }, 0); };
    return (Number(tonDau) || 0) + sum(nhap) - sum(xuat) - sum(ban);
  }

  function fsku(kho, code, size) {
    return kho + String(code || '').trim().toUpperCase() + chuanSize(size);
  }

  /**
   * Có thể bán trùng (19/10, cùng luật web allsales.ts): dòng BAN gõ tay (seller không có "@") trùng ngày + mã + size + kho
   * với dòng bot ghi từ app / đơn web (seller là email). Chỉ báo, vẫn cộng tổng.
   * dongs: [{ dong, ngay_key, code, size, kho, seller }]; boQua: khoá "ngày|mã|size|kho|dòng" Chủ đã bấm "Không phải trùng".
   * → [số dòng Sheet]
   */
  function banTrung(dongs, boQua) {
    var key = function (r) { return r.ngay_key + '|' + String(r.code || '').trim().toUpperCase() + '|' + (chuanSize(r.size) || '-') + '|' + (khoChuan(r.kho) || String(r.kho || '').trim()); };
    var app = {};
    (dongs || []).forEach(function (r) { if (/@/.test(String(r.seller || ''))) app[key(r)] = true; });
    return (dongs || []).filter(function (r) {
      return !/@/.test(String(r.seller || '')) && app[key(r)] && !coMa(boQua, key(r) + '|' + r.dong);
    }).map(function (r) { return r.dong; });
  }

  /**
   * Mã dòng duy nhất (ma_dong) của dòng BAN / NHAP / XUAT mới (Bán hàng chốt 20/10): <mã thao tác duy nhất>#<thứ tự trong thao tác>.
   * Không dùng số NK (2 phiếu cùng NCC cùng ngày chung số NK vẫn ra mã khác). nguon: 'phieu' | 'app' | 'web' | 'zalo' | 'mac' | 'tay'.
   * d: { phieu_id?, ticket?, msg_id?, lan_chay?, ngay? (yyyy-mm-dd), dong? (số hàng Sheet) }; thuTu bắt đầu từ 1 (tay: không dùng).
   */
  function maDong(nguon, d, thuTu) {
    d = d || {};
    // Dòng gõ tay lúc dự phòng: web cấp khi nhập bù (Bán hàng 20/10) → TAY-<yyyyMMdd>-<số hàng Sheet>, không có #
    if (nguon === 'tay') return d.ngay && d.dong ? 'TAY-' + String(d.ngay).replace(/-/g, '') + '-' + d.dong : '';
    // Bot / main.py không bao giờ cấp gốc TAY- (tránh trùng mã web cấp)
    if (/^TAY-/i.test(String(d.ticket || ''))) return '';
    var goc = nguon === 'phieu' ? d.phieu_id : nguon === 'zalo' ? 'Z-' + d.msg_id : nguon === 'mac' ? 'MAC-' + d.lan_chay : d.ticket;
    return goc && String(goc).indexOf('undefined') === -1 ? String(goc).trim() + '#' + thuTu : '';
  }

  return {
    PHIEN_BAN: PHIEN_BAN, KHO_ALIASES: KHO_ALIASES, COT_KY_GUI: COT_KY_GUI,
    khoChuan: khoChuan, hoKia: hoKia, chuanSize: chuanSize, soTien: soTien, ngayKey: ngayKey, fsku: fsku,
    tachMaSize: tachMaSize, banTachChuHang: banTachChuHang, huyBanKhoiPhuc: huyBanKhoiPhuc, chuyenKhoKyGui: chuyenKhoKyGui,
    traHangChuHang: traHangChuHang, canhBaoKyGui: canhBaoKyGui, soNhapKho: soNhapKho, giaMisa: giaMisa,
    donGiaPhieuMoi: donGiaPhieuMoi, tonKho: tonKho, banTrung: banTrung, maDong: maDong
  };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = LuatKho;
