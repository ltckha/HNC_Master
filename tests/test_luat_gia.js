// Luật gợi ý giá chung shared/luat_gia.js (Agent đăng SP GĐ3b) — node tests/test_luat_gia.js
const L = require('../shared/luat_gia.js');
let fail = 0, total = 0;
const eq = (n, got, want) => { total++; const ok = JSON.stringify(got) === JSON.stringify(want); if (!ok) { fail++; console.log('❌ ' + n + '\n   được ' + JSON.stringify(got) + '\n   cần  ' + JSON.stringify(want)); } };
eq('giá nhập: lô hoá đơn → lô phiếu → purchase → invoice', [L.giaNhap({ don_gia_hd: '530.000', don_gia_phieu: 500000 }, { purchase_price: 1 }), L.giaNhap({ don_gia_phieu: '500.000 đ' }, { purchase_price: 1 }),
  L.giaNhap({}, { invoice_price: '450,000', purchase_price: 400000 }), L.giaNhap(null, { invoice_price: '450000', purchase_price: '' }), L.giaNhap({}, {})], [530000, 500000, 400000, 450000, 0]);
eq('trung vị chẵn / lẻ', [L.trungVi([3, 1, 2]), L.trungVi([1, 2, 3, 4])], [2, 2.5]);
const mk = (n, ncc, nhom, ban, nhap) => Array.from({ length: n }, (_, i) => ({ code: ncc + nhom + i, ncc, nhom, gia_ban: ban, gia_nhap: nhap }));
const mau = mk(5, 'A', 'Giày tây', 900000, 300000).concat(mk(4, 'B', 'Giày tây', 500000, 250000), mk(3, 'C', 'Dép', 300000, 100000));
let r = L.goiYGia({ code: 'x1', ncc: 'a', nhom: 'giày tây', gia_nhap: 333000 }, mau);
eq('cùng NCC + nhóm ≥ 5 mã: tỷ lệ 3, làm tròn 10.000', [r.gia, r.theo, r.so_ma], [1000000, 'ncc_nhom', 5]);
eq('lý do không có số tiền, không tên NCC', [/\d{3}|\d+k|triệu/i.test(r.ly_do.replace(/\d+ mã/, '')), /\bA\b/.test(r.ly_do)], [false, false]);
r = L.goiYGia({ code: 'x2', ncc: 'B', nhom: 'Giày tây', gia_nhap: 250000 }, mau);
eq('NCC < 5 mã → cả nhóm (9 mã, trung vị 3)', [r.gia, r.theo, r.so_ma], [750000, 'nhom', 9]);
eq('nhóm < 5 mã → không gợi ý', L.goiYGia({ code: 'x3', ncc: 'C', nhom: 'Dép', gia_nhap: 100000 }, mau).loi, 'ít hơn 5 mã cùng nhóm Dép để so');
eq('thiếu giá nhập / nhóm', [L.goiYGia({ code: 'x4', nhom: 'Dép' }, mau).loi, L.goiYGia({ code: 'x5', gia_nhap: 1 }, mau).loi], ['chưa có giá nhập', 'chưa có nhóm hàng']);
eq('không tự so với chính mã đó', L.goiYGia({ code: 'AGiày tây0', ncc: 'A', nhom: 'Giày tây', gia_nhap: 300000 }, mau).theo, 'nhom');
r = L.goiYGiaLo([{ code: 'y', ncc: 'A', nhom: 'Giày tây', lo: { don_gia_phieu: '200.000' }, purchase_price: '999999' }],
  mau.map(x => ({ code: x.code, ncc: x.ncc, nhom: x.nhom, gia_ban: x.gia_ban, purchase_price: x.gia_nhap })));
eq('lô: giá nhập tính từ lô / purchase_price', [r[0].gia, r[0].theo], [600000, 'ncc_nhom']);
console.log((fail ? '❌ ' : '✅ ') + (total - fail) + '/' + total + ' ca đạt (luat_gia)');
process.exit(fail ? 1 : 0);
