"""Dữ liệu và quy tắc nghiệp vụ của ứng dụng quản lý sinh viên."""

import re
import unicodedata
from dataclasses import dataclass

# Email "đủ dùng": có phần @, phần tên miền và phần đuôi, không chứa khoảng trắng
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# GPA là thang điểm 4 (chuẩn quốc tế, dùng phổ biến ở các trường Việt Nam)
GPA_MIN, GPA_MAX = 0.0, 4.0


@dataclass
class SinhVien:
    ma_sv: str
    ho_ten: str
    ngay_sinh: str = ""  # dạng ISO yyyy-mm-dd, có thể rỗng
    lop: str = ""
    email: str = ""
    gpa: float = 0.0


def xep_loai(gpa: float) -> str:
    """Xếp loại học lực theo GPA thang 4."""
    if gpa >= 3.6:
        return "Giỏi"
    if gpa >= 3.0:
        return "Khá"
    if gpa >= 2.0:
        return "Trung bình"
    return "Yếu"


def bo_dau(s: str) -> str:
    """Chuỗi so sánh cho tìm kiếm: bỏ dấu tiếng Việt + viết thường.

    'Nguyễn Thị Hoa' -> 'nguyen thi hoa' nên gõ 'nguyen hoa' vẫn tìm thấy.
    """
    khong_dau = unicodedata.normalize("NFD", s)
    khong_dau = "".join(c for c in khong_dau if unicodedata.category(c) != "Mn")
    return khong_dau.lower()


def chuan_hoa_ten(ho_ten: str) -> str:
    """Cắt khoảng trắng thừa ở hai đầu và giữa các từ, viết hoa đúng vị trí."""
    return " ".join(ho_ten.split()).title()


def email_hop_le(email: str) -> bool:
    return bool(EMAIL_RE.match(email))
