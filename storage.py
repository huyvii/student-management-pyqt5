"""Đọc/ghi dữ liệu CSV cho danh sách sinh viên.

Thiết kế an toàn:
- Đường dẫn ghim theo thư mục chứa code, nên app chạy từ đâu cũng đọc/đúng
  một file dữ liệu (không tạo nhầm sv.csv ở thư mục khác).
- utf-8-sig: Excel mở đúng tiếng Việt, và vẫn đọc được file được Excel lưu lại (có BOM).
- Ghi nguyên tử: ghi file tạm rồi os.replace, app chết giữa lúc ghi cũng không mất file cũ.
- Dòng dữ liệu lỗi không bị nuốt âm thầm: trả về kèm số dòng và lý do để báo cho người dùng.
"""

import csv
import os
from datetime import datetime

from models import SinhVien, chuan_hoa_ten

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "sv.csv")
UI_PATH = os.path.join(BASE_DIR, "qlsv.ui")

HEADER = ["ma_sv", "ho_ten", "ngay_sinh", "lop", "email", "gpa"]

# Tiêu đề cột nhận diện được khi gặp ở cột đầu tiên của một dòng
HEADER_LABELS = {"ma_sv", "ma sinh vien", "mã sinh viên", "id"}


def parse_gpa(text) -> float:
    """Đổi chuỗi thành GPA hợp lệ. Chấp nhận cả dấu phẩy thập phân kiểu '3,5'."""
    gpa = float(str(text).strip().replace(",", "."))
    if not (0.0 <= gpa <= 4.0):
        raise ValueError(f"GPA phải trong khoảng 0.0 – 4.0, nhận '{text.strip()}'")
    return gpa


def parse_ngay_sinh(text) -> str:
    """Chuẩn hóa ngày sinh về dạng ISO yyyy-mm-dd. Chuỗi rỗng -> rỗng."""
    text = (text or "").strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"Ngày sinh không đọc được: '{text.strip()}'")


def doc_danh_sach_sv(path=CSV_PATH):
    """Đọc file CSV sinh viên.

    Trả về (list[SinhVien], loi:list[str], canh_bao:list[str]):
    - loi: dòng không đọc được (sai cột, sai số liệu) — kèm số dòng và lý do.
    - canh_bao: dòng đọc được nhưng có vấn đề (trùng mã SV) — kèm số dòng.
    """
    students, loi, canh_bao = [], [], []
    if not os.path.exists(path):
        return students, loi, canh_bao

    da_thay = set()
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for so_dong, row in enumerate(csv.reader(f), start=1):
            if not row or all(not c.strip() for c in row):
                continue
            if row[0].strip().lower() in HEADER_LABELS:
                continue  # dòng tiêu đề

            try:
                if len(row) == 3:
                    # Định dạng cũ (ma, ho_ten, gpa) — giữ tương thích
                    ma, ten, gpa_txt = row
                    ngay, lop, email = "", "", ""
                elif len(row) == 6:
                    ma, ten, ngay, lop, email, gpa_txt = row
                else:
                    raise ValueError(f"cần 3 hoặc 6 cột, nhận {len(row)} cột")

                ten = chuan_hoa_ten(ten)
                if not ma.strip() or not ten:
                    raise ValueError("thiếu mã SV hoặc họ tên")
                sv = SinhVien(
                    ma_sv=ma.strip().upper(),
                    ho_ten=ten,
                    ngay_sinh=parse_ngay_sinh(ngay),
                    lop=" ".join(lop.split()),
                    email=email.strip().lower(),
                    gpa=parse_gpa(gpa_txt),
                )
            except ValueError as e:
                loi.append(f"Dòng {so_dong}: {e}")
                continue

            if sv.ma_sv in da_thay:
                canh_bao.append(f"Dòng {so_dong}: mã '{sv.ma_sv}' trùng, giữ lại bản ghi đầu tiên")
                continue
            da_thay.add(sv.ma_sv)
            students.append(sv)

    return students, loi, canh_bao


def ghi_danh_sach_sv(students, path=CSV_PATH):
    """Ghi danh sách ra CSV (có dòng tiêu đề) theo cách nguyên tử."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for sv in students:
            writer.writerow([sv.ma_sv, sv.ho_ten, sv.ngay_sinh, sv.lop, sv.email, f"{sv.gpa:.2f}"])
    os.replace(tmp, path)  # thay file cũ trong một bước, không sợ ghi dở
