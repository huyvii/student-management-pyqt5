import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QMessageBox
from PyQt5 import uic


class SinhVien:
    def __init__(self, ma_sv, ho_ten, gpa):
        self.ma_sv = ma_sv
        self.ho_ten = ho_ten
        self.gpa = gpa


CSV_PATH = "sv.csv"


def doc_danh_sach_sv():
    list_students = []
    if not os.path.exists(CSV_PATH):
        return list_students
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                ma_sv, ho_ten, gpa = line.strip().split(",")
                student = SinhVien(ma_sv, ho_ten, float(gpa))
                list_students.append(student)
            except:
                pass
    return list_students


def ghi_danh_sach_sv(list_students):
    with open(CSV_PATH, "w", encoding="utf-8") as f:
        for sv in list_students:
            f.write(f"{sv.ma_sv},{sv.ho_ten},{sv.gpa}\n")


class StudentManagementApp(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("qlsv.ui", self)

        self.list_students = doc_danh_sach_sv()

        # ----- CACHE 1: dict tra cứu sinh viên theo mã SV -----
        # Giúp kiểm tra trùng mã và tra cứu sinh viên với độ phức tạp O(1)
        # thay vì phải duyệt tuần tự qua list (O(n)).
        self.cache_sv = {sv.ma_sv: sv for sv in self.list_students}

        # ----- CACHE 2: cache thống kê (tổng số SV, GPA trung bình) -----
        # Chỉ tính lại khi dữ liệu thực sự thay đổi (cache invalidation),
        # tránh việc duyệt lại toàn bộ danh sách mỗi khi vẽ lại giao diện.
        self._stats_cache = None

        # ----- CACHE 3: cache thời điểm sửa đổi file (session cache) -----
        # Dùng để chỉ đọc lại sv.csv khi file thật sự bị thay đổi từ bên ngoài,
        # tránh đọc lại toàn bộ file một cách không cần thiết.
        self._last_mtime = os.path.getmtime(CSV_PATH) if os.path.exists(CSV_PATH) else None

        self.update_table()
        self.update_stats()

        self.addButton.clicked.connect(self.add_student)
        self.updateButton.clicked.connect(self.update_student)
        self.deleteButton.clicked.connect(self.delete_student)
        self.clearButton.clicked.connect(self.clear_form)
        self.refreshButton.clicked.connect(self.refresh_from_disk)

        self.studentListView.itemClicked.connect(self.fill_info_to_form)
        self.searchEdit.textChanged.connect(self.filter_table)

        # Enter ở ô GPA cũng thêm sinh viên luôn, đỡ phải bấm chuột
        self.gpaEdit.returnPressed.connect(self.add_student)

        self.show()

    # ---------------------------------------------------------------
    # Các hàm liên quan đến cache
    # ---------------------------------------------------------------
    def _invalidate_stats_cache(self):
        """Đánh dấu cache thống kê là 'cũ', lần sau gọi update_stats() sẽ tính lại."""
        self._stats_cache = None

    def update_stats(self):
        """Cập nhật nhãn thống kê, có sử dụng cache để tránh tính lại nếu dữ liệu chưa đổi."""
        if self._stats_cache is None:
            total = len(self.list_students)
            avg_gpa = (sum(sv.gpa for sv in self.list_students) / total) if total > 0 else 0.0
            self._stats_cache = (total, avg_gpa)  # lưu kết quả vào cache

        total, avg_gpa = self._stats_cache
        self.statsLabel.setText(f"Tổng số sinh viên: {total} | GPA trung bình: {avg_gpa:.2f}")

    def refresh_from_disk(self):
        """Chỉ đọc lại sv.csv nếu file đã thay đổi kể từ lần đọc gần nhất
        (so sánh thời gian sửa đổi file - session cache), tránh đọc lại vô ích."""
        if not os.path.exists(CSV_PATH):
            self.statusbar.showMessage("Không tìm thấy file sv.csv", 3000)
            return

        mtime = os.path.getmtime(CSV_PATH)
        if self._last_mtime is not None and mtime == self._last_mtime:
            self.statusbar.showMessage("Dữ liệu không có gì thay đổi", 3000)
            return

        self.list_students = doc_danh_sach_sv()
        self.cache_sv = {sv.ma_sv: sv for sv in self.list_students}
        self._last_mtime = mtime
        self._invalidate_stats_cache()

        self.searchEdit.clear()
        self.update_table()
        self.update_stats()
        self.statusbar.showMessage("Đã tải lại dữ liệu từ sv.csv", 3000)

    # ---------------------------------------------------------------
    # Hiển thị bảng / tìm kiếm
    # ---------------------------------------------------------------
    def update_table(self, danh_sach=None):
        """Vẽ lại bảng. Nếu truyền vào danh_sach (kết quả lọc) thì hiển thị danh sách đó,
        ngược lại hiển thị toàn bộ self.list_students."""
        if danh_sach is None:
            danh_sach = self.list_students

        self.studentListView.setSortingEnabled(False)  # tắt tạm để tránh xáo trộn khi đang chèn dòng
        self.studentListView.setRowCount(0)
        for index, student in enumerate(danh_sach):
            self.studentListView.insertRow(index)
            self.studentListView.setItem(index, 0, QTableWidgetItem(student.ma_sv))
            self.studentListView.setItem(index, 1, QTableWidgetItem(student.ho_ten))
            self.studentListView.setItem(index, 2, QTableWidgetItem(str(student.gpa)))
        self.studentListView.setSortingEnabled(True)

    def filter_table(self):
        """Lọc danh sách hiển thị theo mã SV hoặc họ tên (không phân biệt hoa thường).
        Việc thêm/sửa/xóa vẫn hoạt động đúng vì luôn tra cứu qua cache_sv bằng mã SV
        lấy trực tiếp từ ô đang chọn, không phụ thuộc vào index của list gốc."""
        tu_khoa = self.searchEdit.text().strip().lower()
        if not tu_khoa:
            self.update_table()
            return

        ket_qua = [
            sv for sv in self.list_students
            if tu_khoa in sv.ma_sv.lower() or tu_khoa in sv.ho_ten.lower()
        ]
        self.update_table(ket_qua)

    # ---------------------------------------------------------------
    # Thêm / sửa / xóa
    # ---------------------------------------------------------------
    def add_student(self):
        ma_sv = self.idEdit.text().strip()
        ho_ten = self.nameEdit.text().strip()

        try:
            gpa = float(self.gpaEdit.text())
        except:
            QMessageBox.information(self, "Error", "Cannot convert GPA to float")
            return

        if not (ma_sv and ho_ten and 0.0 <= gpa <= 4.0):
            QMessageBox.information(self, "Error", "Please enter a valid value")
            return

        # ----- Dùng cache để kiểm tra trùng mã SV (O(1)) -----
        if ma_sv in self.cache_sv:
            QMessageBox.information(self, "Error", f"Mã sinh viên '{ma_sv}' đã tồn tại")
            return

        new_student = SinhVien(ma_sv, ho_ten, gpa)
        self.list_students.append(new_student)
        self.cache_sv[ma_sv] = new_student  # đồng bộ cache khi thêm mới
        self._invalidate_stats_cache()       # dữ liệu đổi -> cache thống kê phải tính lại

        ghi_danh_sach_sv(self.list_students)
        self._last_mtime = os.path.getmtime(CSV_PATH)

        self.searchEdit.clear()
        self.update_table()
        self.update_stats()
        self.clear_form()
        self.statusbar.showMessage(f"Đã thêm sinh viên {ma_sv}", 3000)

    def _lay_ma_sv_dang_chon(self):
        """Lấy mã SV của dòng đang chọn trực tiếp từ bảng (cột 0),
        thay vì chỉ dựa vào currentRow() để suy ra vị trí trong list_students.
        Nhờ vậy thao tác vẫn đúng dù bảng đang được sắp xếp hoặc đang lọc kết quả tìm kiếm."""
        selected_row = self.studentListView.currentRow()
        if selected_row < 0:
            return None
        item = self.studentListView.item(selected_row, 0)
        return item.text() if item else None

    def update_student(self):
        ma_sv_cu = self._lay_ma_sv_dang_chon()
        if ma_sv_cu is None or ma_sv_cu not in self.cache_sv:
            QMessageBox.information(self, "Error", "Vui lòng chọn một sinh viên trong bảng")
            return

        ma_sv_moi = self.idEdit.text().strip()
        ho_ten = self.nameEdit.text().strip()

        try:
            gpa = float(self.gpaEdit.text())
        except:
            QMessageBox.information(self, "Error", "Cannot convert GPA to float")
            return

        if not (ma_sv_moi and ho_ten and 0.0 <= gpa <= 4.0):
            QMessageBox.information(self, "Error", "Please enter a valid value")
            return

        if ma_sv_moi != ma_sv_cu and ma_sv_moi in self.cache_sv:
            QMessageBox.information(self, "Error", f"Mã sinh viên '{ma_sv_moi}' đã tồn tại")
            return

        # ----- Cập nhật trực tiếp qua cache (O(1)) thay vì dò index trong list -----
        sv = self.cache_sv[ma_sv_cu]
        sv.ma_sv = ma_sv_moi
        sv.ho_ten = ho_ten
        sv.gpa = gpa

        if ma_sv_moi != ma_sv_cu:
            del self.cache_sv[ma_sv_cu]
            self.cache_sv[ma_sv_moi] = sv

        self._invalidate_stats_cache()

        ghi_danh_sach_sv(self.list_students)
        self._last_mtime = os.path.getmtime(CSV_PATH)

        self.searchEdit.clear()
        self.update_table()
        self.update_stats()
        self.clear_form()
        self.statusbar.showMessage(f"Đã cập nhật sinh viên {ma_sv_moi}", 3000)

    def fill_info_to_form(self):
        ma_sv = self._lay_ma_sv_dang_chon()
        if ma_sv is None:
            return

        # ----- Tra cứu sinh viên qua cache (O(1)) thay vì lấy theo index -----
        selected_student = self.cache_sv.get(ma_sv)
        if selected_student is None:
            return

        self.idEdit.setText(selected_student.ma_sv)
        self.nameEdit.setText(selected_student.ho_ten)
        self.gpaEdit.setText(str(selected_student.gpa))

    def delete_student(self):
        ma_sv = self._lay_ma_sv_dang_chon()
        if ma_sv is None or ma_sv not in self.cache_sv:
            QMessageBox.information(self, "Error", "Vui lòng chọn một sinh viên trong bảng")
            return

        xac_nhan = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc muốn xóa sinh viên có mã '{ma_sv}' không?",
            QMessageBox.Yes | QMessageBox.No
        )
        if xac_nhan != QMessageBox.Yes:
            return

        sv = self.cache_sv[ma_sv]
        self.list_students.remove(sv)
        del self.cache_sv[ma_sv]
        self._invalidate_stats_cache()

        ghi_danh_sach_sv(self.list_students)
        self._last_mtime = os.path.getmtime(CSV_PATH)

        self.searchEdit.clear()
        self.update_table()
        self.update_stats()
        self.clear_form()
        self.statusbar.showMessage(f"Đã xóa sinh viên {ma_sv}", 3000)

    def clear_form(self):
        self.idEdit.clear()
        self.nameEdit.clear()
        self.gpaEdit.clear()
        self.studentListView.clearSelection()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = StudentManagementApp()
    sys.exit(app.exec_())