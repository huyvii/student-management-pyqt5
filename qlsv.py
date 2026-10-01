"""Ứng dụng quản lý sinh viên (PyQt5).

Cấu trúc project:
- models.py  : dữ liệu (SinhVien) và quy tắc nghiệp vụ (xếp loại, chuẩn hóa, bỏ dấu)
- storage.py : đọc/ghi CSV an toàn (utf-8-sig, ghi nguyên tử, đường dẫn ghim theo thư mục app)
- qlsv.py    : giao diện và thao tác của người dùng (file này)

Phím tắt: Ctrl+N thêm, Ctrl+U sửa, Delete xóa, Ctrl+L làm trống form,
F5 làm mới dữ liệu, Ctrl+I nhập CSV, Ctrl+E xuất CSV, Ctrl+Q thoát.
"""

import os
import sys

from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QHeaderView,
    QMainWindow,
    QMessageBox,
    QShortcut,
    QStyle,
    QTableWidgetItem,
)
from PyQt5 import uic

import storage
from models import SinhVien, bo_dau, chuan_hoa_ten, email_hop_le, xep_loai

# Các cột của bảng hiển thị
COT_MA, COT_TEN, COT_NGAY, COT_LOP, COT_EMAIL, COT_GPA, COT_XEP_LOAI = range(7)

XEP_LOAI_COLORS = {
    "Giỏi": "#1a7f37",
    "Khá": "#0969da",
    "Trung bình": "#9a6700",
    "Yếu": "#cf222e",
}


class SortItem(QTableWidgetItem):
    """Ô dữ liệu sắp xếp theo khóa riêng (số / chuỗi đã chuẩn hóa) thay vì theo
    chữ hiển thị — để GPA sort đúng theo số, ngày sinh sort đúng theo thời gian,
    họ tên sort không phân biệt hoa thường và dấu."""

    def __init__(self, text, sort_key, alignment=None):
        super().__init__(text)
        self._sort_key = sort_key
        if alignment is not None:
            self.setTextAlignment(alignment)

    def __lt__(self, other):
        try:
            return self._sort_key < other._sort_key
        except (AttributeError, TypeError):
            return super().__lt__(other)


class QuanLySinhVienApp(QMainWindow):
    def __init__(self):
        super().__init__()
        try:
            uic.loadUi(storage.UI_PATH, self)
        except Exception as e:
            QMessageBox.critical(None, "Lỗi giao diện", f"Không tải được file qlsv.ui:\n{e}")
            raise

        self.list_students = []
        self.cache_sv = {}          # tra cứu sinh viên theo mã SV (O(1))
        self._stats_cache = None    # thống kê chỉ tính lại khi dữ liệu đổi

        self._cau_hinh_giao_dien()
        self._ket_noi_tin_hieu()

        self.tai_du_lieu_tu_dia()
        self.filter_table()  # vẽ bảng lần đầu (đồng thời xử lý trạng thái rỗng)
        self.update_stats()
        self.show()

    # ---------------------------------------------------------------
    # Khởi tạo giao diện
    # ---------------------------------------------------------------
    def _cau_hinh_giao_dien(self):
        style = self.style()
        self.addButton.setIcon(style.standardIcon(QStyle.SP_DialogApplyButton))
        self.updateButton.setIcon(style.standardIcon(QStyle.SP_DialogSaveButton))
        self.deleteButton.setIcon(style.standardIcon(QStyle.SP_TrashIcon))
        self.clearButton.setIcon(style.standardIcon(QStyle.SP_DialogResetButton))
        self.refreshButton.setIcon(style.standardIcon(QStyle.SP_BrowserReload))

        # Ngày sinh không được ở tương lai
        self.dobEdit.setMaximumDate(QDate.currentDate())

        # Giới hạn chiều rộng ô nhập cho cân đối (mặc định chúng giãn hết hàng)
        self.idEdit.setMaximumWidth(220)
        self.nameEdit.setMaximumWidth(320)
        self.dobEdit.setMaximumWidth(160)
        self.classEdit.setMaximumWidth(180)
        self.emailEdit.setMaximumWidth(320)
        self.gpaSpin.setMaximumWidth(130)

        # Độ rộng cột: cột họ tên và email chiếm phần dư, các cột khác vừa nội dung
        header = self.studentTable.horizontalHeader()
        self.studentTable.setColumnWidth(COT_MA, 100)
        header.setSectionResizeMode(COT_TEN, QHeaderView.Stretch)
        self.studentTable.setColumnWidth(COT_NGAY, 110)
        self.studentTable.setColumnWidth(COT_LOP, 120)
        header.setSectionResizeMode(COT_EMAIL, QHeaderView.Stretch)
        self.studentTable.setColumnWidth(COT_GPA, 80)
        self.studentTable.setColumnWidth(COT_XEP_LOAI, 110)

        # Phím tắt. Delete gắn vào bảng (WidgetShortcut) để không dính khi đang gõ chữ
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.add_student)
        QShortcut(QKeySequence("Ctrl+U"), self, activated=self.update_student)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.clear_form)
        QShortcut(QKeySequence("F5"), self, activated=self.refresh_from_disk)
        QShortcut(QKeySequence(Qt.Key_Delete), self.studentTable,
                  activated=self.delete_student, context=Qt.WidgetShortcut)

        # Menu "Tệp": nhập / xuất / mở thư mục dữ liệu
        menu_tep = self.menubar.addMenu("&Tệp")
        act_nhap = QAction("Nhập CSV…", self)
        act_nhap.setShortcut("Ctrl+I")
        act_nhap.triggered.connect(self.import_csv)
        act_xuat = QAction("Xuất CSV…", self)
        act_xuat.setShortcut("Ctrl+E")
        act_xuat.triggered.connect(self.export_csv)
        act_mo_thu_muc = QAction("Mở thư mục chứa dữ liệu", self)
        act_mo_thu_muc.triggered.connect(self.mo_thu_muc_du_lieu)
        act_thoat = QAction("Thoát", self)
        act_thoat.setShortcut("Ctrl+Q")
        act_thoat.triggered.connect(self.close)
        menu_tep.addAction(act_nhap)
        menu_tep.addAction(act_xuat)
        menu_tep.addSeparator()
        menu_tep.addAction(act_mo_thu_muc)
        menu_tep.addSeparator()
        menu_tep.addAction(act_thoat)

    def _ket_noi_tin_hieu(self):
        self.addButton.clicked.connect(self.add_student)
        self.updateButton.clicked.connect(self.update_student)
        self.deleteButton.clicked.connect(self.delete_student)
        self.clearButton.clicked.connect(self.clear_form)
        self.refreshButton.clicked.connect(self.refresh_from_disk)

        # Chọn dòng bằng chuột lẫn bàn phím (mũi tên) đều điền thông tin vào form
        self.studentTable.itemSelectionChanged.connect(self.fill_info_to_form)

        # Lọc ngay khi gõ
        self.searchEdit.textChanged.connect(self.filter_table)

        # Enter đi tiếp sang trường kế; Enter ở ô GPA gửi form
        # (sửa nếu đang chọn sinh viên có sẵn, thêm nếu là mã mới)
        for widget in (self.idEdit, self.nameEdit, self.dobEdit.lineEdit(),
                       self.classEdit, self.emailEdit):
            widget.returnPressed.connect(self.focusNextChild)
        self.gpaSpin.lineEdit().returnPressed.connect(self._submit_form)

    # ---------------------------------------------------------------
    # Nạp dữ liệu / thống kê
    # ---------------------------------------------------------------
    def tai_du_lieu_tu_dia(self):
        """Đọc sv.csv. Dòng lỗi / trùng mã được báo rõ, không bỏ qua âm thầm."""
        students, loi, canh_bao = storage.doc_danh_sach_sv()
        self.list_students = students
        self.cache_sv = {sv.ma_sv: sv for sv in students}
        self._stats_cache = None

        van_de = loi + canh_bao
        if van_de:
            noi_dung = "\n".join(van_de[:5])
            if len(van_de) > 5:
                noi_dung += f"\n… và {len(van_de) - 5} dòng nữa"
            QMessageBox.warning(self, "Dữ liệu có vấn đề trong sv.csv", noi_dung)

    def refresh_from_disk(self):
        self.tai_du_lieu_tu_dia()
        self.filter_table()
        self.update_stats()
        self.statusbar.showMessage("Đã tải lại dữ liệu từ sv.csv", 5000)

    def update_stats(self):
        if self._stats_cache is None:
            total = len(self.list_students)
            avg = sum(sv.gpa for sv in self.list_students) / total if total else 0.0
            dem = {"Giỏi": 0, "Khá": 0, "Trung bình": 0, "Yếu": 0}
            for sv in self.list_students:
                dem[xep_loai(sv.gpa)] += 1
            self._stats_cache = (total, avg, dem)

        total, avg, dem = self._stats_cache
        self.statsLabel.setText(
            f"Tổng số: {total} sinh viên   |   GPA trung bình: {avg:.2f}   |   "
            f"Giỏi: {dem['Giỏi']} · Khá: {dem['Khá']} · Trung bình: {dem['Trung bình']} · Yếu: {dem['Yếu']}"
        )

    # ---------------------------------------------------------------
    # Hiển thị bảng / tìm kiếm
    # ---------------------------------------------------------------
    def update_table(self, danh_sach=None):
        """Vẽ lại bảng. Giữ nguyên dòng đang chọn (tra theo mã SV) và bộ lọc."""
        if danh_sach is None:
            danh_sach = self.list_students
        ma_dang_chon = self._ma_sv_dang_chon()

        self.studentTable.setSortingEnabled(False)  # tránh xáo trộn khi đang chèn dòng
        self.studentTable.setRowCount(0)
        for row, sv in enumerate(danh_sach):
            self.studentTable.insertRow(row)
            self.studentTable.setItem(row, COT_MA, SortItem(sv.ma_sv, sv.ma_sv.lower()))
            self.studentTable.setItem(row, COT_TEN, SortItem(sv.ho_ten, bo_dau(sv.ho_ten)))

            ngay_hien_thi = ""
            if sv.ngay_sinh:
                ngay_hien_thi = QDate.fromString(sv.ngay_sinh, "yyyy-MM-dd").toString("dd/MM/yyyy")
            self.studentTable.setItem(row, COT_NGAY,
                                      SortItem(ngay_hien_thi, sv.ngay_sinh, Qt.AlignCenter))

            self.studentTable.setItem(row, COT_LOP, SortItem(sv.lop, bo_dau(sv.lop)))
            self.studentTable.setItem(row, COT_EMAIL, SortItem(sv.email, sv.email.lower()))
            self.studentTable.setItem(row, COT_GPA,
                                      SortItem(f"{sv.gpa:.2f}", sv.gpa, Qt.AlignRight | Qt.AlignVCenter))

            loai = xep_loai(sv.gpa)
            item_loai = SortItem(loai, sv.gpa, Qt.AlignCenter)
            item_loai.setForeground(QColor(XEP_LOAI_COLORS.get(loai, "#000000")))
            self.studentTable.setItem(row, COT_XEP_LOAI, item_loai)
        self.studentTable.setSortingEnabled(True)

        # Phục hồi dòng đang chọn trước khi vẽ lại
        if ma_dang_chon:
            row = self._tim_row_theo_ma(ma_dang_chon)
            if row >= 0:
                self.studentTable.selectRow(row)

        # Trạng thái bảng rỗng (chưa có dữ liệu hoặc không khớp từ khóa)
        if self.studentTable.rowCount() == 0:
            tu_khoa = self.searchEdit.text().strip()
            if tu_khoa:
                self.emptyLabel.setText(f"Không có sinh viên nào khớp “{tu_khoa}”.")
            else:
                self.emptyLabel.setText("Chưa có sinh viên nào.\nNhập thông tin phía trên rồi bấm “Thêm” (Ctrl+N).")
            self.stack.setCurrentIndex(0)
        else:
            self.stack.setCurrentIndex(1)

    def filter_table(self):
        """Lọc không phân biệt hoa thường và dấu tiếng Việt."""
        tu_khoa = bo_dau(self.searchEdit.text().strip())
        if not tu_khoa:
            self.update_table()
            return
        ket_qua = [
            sv for sv in self.list_students
            if tu_khoa in bo_dau(sv.ma_sv)
            or tu_khoa in bo_dau(sv.ho_ten)
            or tu_khoa in bo_dau(sv.lop)
            or tu_khoa in bo_dau(sv.email)
        ]
        self.update_table(ket_qua)

    def _tim_row_theo_ma(self, ma_sv):
        for row in range(self.studentTable.rowCount()):
            item = self.studentTable.item(row, COT_MA)
            if item and item.text() == ma_sv:
                return row
        return -1

    def _ma_sv_dang_chon(self):
        """Lấy mã SV của dòng đang chọn trực tiếp từ bảng, nên thao tác vẫn đúng
        dù bảng đang được sắp xếp hay đang lọc kết quả tìm kiếm."""
        row = self.studentTable.currentRow()
        if row < 0:
            return None
        item = self.studentTable.item(row, COT_MA)
        return item.text() if item else None

    # ---------------------------------------------------------------
    # Form
    # ---------------------------------------------------------------
    def fill_info_to_form(self):
        ma_sv = self._ma_sv_dang_chon()
        sv = self.cache_sv.get(ma_sv) if ma_sv else None
        if sv is None:
            return
        self.idEdit.setText(sv.ma_sv)
        self.nameEdit.setText(sv.ho_ten)
        if sv.ngay_sinh:
            ngay = QDate.fromString(sv.ngay_sinh, "yyyy-MM-dd")
            if ngay.isValid():
                self.dobEdit.setDate(ngay)
        self.classEdit.setText(sv.lop)
        self.emailEdit.setText(sv.email)
        self.gpaSpin.setValue(sv.gpa)

    def _doc_form(self):
        """Đọc và kiểm tra form. Trả về (SinhVien, thông_báo_lỗi) — lỗi là None nếu hợp lệ."""
        ma_sv = self.idEdit.text().strip().upper()
        ho_ten = chuan_hoa_ten(self.nameEdit.text())
        lop = " ".join(self.classEdit.text().split())
        email = self.emailEdit.text().strip().lower()
        ngay_sinh = self.dobEdit.date().toString("yyyy-MM-dd")
        gpa = self.gpaSpin.value()

        if not ma_sv:
            return None, "Vui lòng nhập mã sinh viên."
        if not ho_ten:
            return None, "Vui lòng nhập họ và tên."
        if email and not email_hop_le(email):
            return None, f"Email không đúng định dạng: “{email}”."

        return SinhVien(ma_sv, ho_ten, ngay_sinh, lop, email, gpa), None

    def _submit_form(self):
        """Enter ở ô GPA: sửa nếu đang chọn sinh viên có sẵn, thêm nếu là mã mới."""
        ma_sv = self.idEdit.text().strip().upper()
        if ma_sv and ma_sv in self.cache_sv:
            self.update_student()
        else:
            self.add_student()

    def clear_form(self):
        self.idEdit.clear()
        self.nameEdit.clear()
        self.dobEdit.setDate(QDate(2000, 1, 1))
        self.classEdit.clear()
        self.emailEdit.clear()
        self.gpaSpin.setValue(0.0)
        self.studentTable.clearSelection()
        self.idEdit.setFocus()

    # ---------------------------------------------------------------
    # Thêm / sửa / xóa
    # ---------------------------------------------------------------
    def add_student(self):
        sv, loi = self._doc_form()
        if loi:
            QMessageBox.warning(self, "Thông tin chưa hợp lệ", loi)
            return

        if sv.ma_sv in self.cache_sv:
            QMessageBox.warning(
                self, "Trùng mã sinh viên",
                f"Mã sinh viên “{sv.ma_sv}” đã tồn tại.\nBấm “Sửa” nếu bạn muốn cập nhật sinh viên này."
            )
            return

        self.list_students.append(sv)
        self.cache_sv[sv.ma_sv] = sv
        self._luu_va_ve_lai(f"Đã thêm sinh viên {sv.ma_sv}")
        self.clear_form()

    def update_student(self):
        ma_cu = self._ma_sv_dang_chon()
        if ma_cu is None or ma_cu not in self.cache_sv:
            QMessageBox.warning(self, "Chưa chọn sinh viên", "Vui lòng chọn một sinh viên trong bảng.")
            return

        sv_moi, loi = self._doc_form()
        if loi:
            QMessageBox.warning(self, "Thông tin chưa hợp lệ", loi)
            return

        if sv_moi.ma_sv != ma_cu and sv_moi.ma_sv in self.cache_sv:
            QMessageBox.warning(self, "Trùng mã sinh viên",
                                f"Mã sinh viên “{sv_moi.ma_sv}” đã được dùng cho sinh viên khác.")
            return

        sv = self.cache_sv[ma_cu]
        sv.ma_sv = sv_moi.ma_sv
        sv.ho_ten = sv_moi.ho_ten
        sv.ngay_sinh = sv_moi.ngay_sinh
        sv.lop = sv_moi.lop
        sv.email = sv_moi.email
        sv.gpa = sv_moi.gpa
        if sv_moi.ma_sv != ma_cu:
            del self.cache_sv[ma_cu]
            self.cache_sv[sv_moi.ma_sv] = sv

        self._luu_va_ve_lai(f"Đã cập nhật sinh viên {sv_moi.ma_sv}")
        self.clear_form()

    def delete_student(self):
        ma_sv = self._ma_sv_dang_chon()
        if ma_sv is None or ma_sv not in self.cache_sv:
            QMessageBox.warning(self, "Chưa chọn sinh viên", "Vui lòng chọn một sinh viên trong bảng.")
            return

        sv = self.cache_sv[ma_sv]
        # Nút mặc định là "No" để bấm nhầm Enter cũng không xóa mất dữ liệu
        xac_nhan = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Xóa sinh viên “{sv.ho_ten}” (mã {ma_sv})?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if xac_nhan != QMessageBox.Yes:
            return

        self.list_students.remove(sv)
        del self.cache_sv[ma_sv]
        self._luu_va_ve_lai(f"Đã xóa sinh viên {ma_sv}")
        self.clear_form()

    def _luu_va_ve_lai(self, thong_diep):
        """Ghi danh sách xuống sv.csv rồi vẽ lại bảng + thống kê, giữ nguyên bộ lọc."""
        try:
            storage.ghi_danh_sach_sv(self.list_students)
        except OSError as e:
            QMessageBox.critical(self, "Không lưu được dữ liệu", f"Không ghi được sv.csv:\n{e}")
            return
        self._stats_cache = None
        self.filter_table()  # vẽ lại theo đúng bộ lọc đang có, không xóa ô tìm kiếm
        self.update_stats()
        self.statusbar.showMessage(thong_diep, 5000)

    # ---------------------------------------------------------------
    # Nhập / xuất CSV
    # ---------------------------------------------------------------
    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file CSV để nhập", "",
                                              "CSV (*.csv);;Tất cả file (*)")
        if not path:
            return
        try:
            ds, loi, canh_bao = storage.doc_danh_sach_sv(path)
        except UnicodeDecodeError:
            QMessageBox.warning(self, "Nhập CSV",
                                "Không đọc được file này theo bảng mã UTF-8.\n"
                                "Hãy mở file bằng Notepad/Excel rồi lưu lại dưới mã UTF-8.")
            return
        except OSError as e:
            QMessageBox.critical(self, "Nhập CSV", f"Không mở được file:\n{e}")
            return

        moi, bo_qua = [], 0
        for sv in ds:
            if sv.ma_sv in self.cache_sv:
                bo_qua += 1
            else:
                moi.append(sv)

        if not moi and not loi and not canh_bao:
            self.statusbar.showMessage("File không chứa sinh viên mới.", 5000)
            return

        self.list_students.extend(moi)
        for sv in moi:
            self.cache_sv[sv.ma_sv] = sv
        self._luu_va_ve_lai(f"Đã nhập {len(moi)} sinh viên mới từ {os.path.basename(path)}")

        thong_diep = f"Đã nhập {len(moi)} sinh viên mới, bỏ qua {bo_qua} sinh viên trùng mã."
        van_de = loi + canh_bao
        if van_de:
            noi_dung = "\n".join(van_de[:5])
            if len(van_de) > 5:
                noi_dung += f"\n… và {len(van_de) - 5} dòng nữa"
            QMessageBox.warning(self, "Nhập CSV", thong_diep + "\n\nMột số dòng bị bỏ qua:\n" + noi_dung)

    def export_csv(self):
        if not self.list_students:
            QMessageBox.information(self, "Xuất CSV", "Danh sách đang trống, không có gì để xuất.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Xuất danh sách ra CSV", "danh_sach_sv.csv",
                                              "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            storage.ghi_danh_sach_sv(self.list_students, path)
        except OSError as e:
            QMessageBox.critical(self, "Xuất CSV", f"Không ghi được file:\n{e}")
            return
        self.statusbar.showMessage(f"Đã xuất {len(self.list_students)} sinh viên ra {path}", 5000)

    def mo_thu_muc_du_lieu(self):
        thu_muc = os.path.dirname(storage.CSV_PATH)
        if sys.platform == "win32":
            os.startfile(thu_muc)
        elif sys.platform == "darwin":
            os.system(f'open "{thu_muc}"')
        else:
            os.system(f'xdg-open "{thu_muc}"')


def main():
    # Hiển thị nét trên màn hình DPI cao (Windows 125%/150%, màn Retina)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    window = QuanLySinhVienApp()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
