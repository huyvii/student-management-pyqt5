import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QMessageBox
from PyQt5 import uic

class SinhVien:
    def __init__(self, ma_sv, ho_ten, gpa):
        self.ma_sv = ma_sv
        self.ho_ten = ho_ten
        self.gpa = gpa

def doc_danh_sach_sv():
    list_students = []
    with open("sv.csv", "r", encoding="utf-8") as f:   # ← thêm dòng này
        for line in f:
            try:
                ma_sv, ho_ten, gpa = line.strip().split(",")
                student = SinhVien(ma_sv, ho_ten, float(gpa))
                list_students.append(student)
            except:
                pass
    return list_students

def ghi_danh_sach_sv(list_students):
    with open("sv.csv", "w", encoding="utf-8") as f:   # ← thêm dòng này
        for sv in list_students:
            f.write(f"{sv.ma_sv},{sv.ho_ten},{sv.gpa}\n")

class StudentManagementApp(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("qlsv.ui", self)

        self.list_students = doc_danh_sach_sv()
        self.update_table()

        self.addButton.clicked.connect(self.add_student)
        self.updateButton.clicked.connect(self.update_student)
        self.deleteButton.clicked.connect(self.delete_student)

        self.studentListView.itemClicked.connect(self.fill_info_to_form)

        self.show()

    def add_student(self):
        ma_sv = self.idEdit.text()
        ho_ten = self.nameEdit.text()

        try:
            gpa = float(self.gpaEdit.text())
        except:
            QMessageBox.information(self, "Error", "Cannot convert GPA to float")
            return

        if ma_sv and ho_ten and 0.0 <= gpa <= 4.0:
            new_student = SinhVien(ma_sv, ho_ten, gpa)
            self.list_students.append(new_student)
            ghi_danh_sach_sv(self.list_students)
            self.update_table()

            self.idEdit.clear()
            self.nameEdit.clear()
            self.gpaEdit.clear()
        else:
            QMessageBox.information(self, "Error", "Please enter a valid value")

    def update_table(self):
        self.studentListView.setRowCount(0)
        for index, student in enumerate(self.list_students):
            self.studentListView.insertRow(index)
            self.studentListView.setItem(index, 0, QTableWidgetItem(student.ma_sv))
            self.studentListView.setItem(index, 1, QTableWidgetItem(student.ho_ten))
            self.studentListView.setItem(index, 2, QTableWidgetItem(str(student.gpa)))

    def update_student(self):
        selected_rows = self.studentListView.currentRow()

        ma_sv = self.idEdit.text()
        ho_ten = self.nameEdit.text()

        try:
            gpa = float(self.gpaEdit.text())
        except:
            QMessageBox.information(self, "Error", "Cannot convert GPA to float")
            return

        if ma_sv and ho_ten and 0.0 <= gpa <= 4.0:
            new_student = SinhVien(ma_sv, ho_ten, gpa)
            self.list_students[selected_rows] = new_student
            ghi_danh_sach_sv(self.list_students)
            self.update_table()

            self.idEdit.clear()
            self.nameEdit.clear()
            self.gpaEdit.clear()


    def fill_info_to_form(self):
        selected_rows = self.studentListView.currentRow()
        selected_student = self.list_students[selected_rows]

        self.idEdit.setText(selected_student.ma_sv)
        self.nameEdit.setText(selected_student.ho_ten)
        self.gpaEdit.setText(str(selected_student.gpa))

    def delete_student(self):
        selected_rows = self.studentListView.currentRow()
        del self.list_students[selected_rows]

        ghi_danh_sach_sv(self.list_students)
        self.update_table()

        self.idEdit.clear()
        self.nameEdit.clear()
        self.gpaEdit.clear()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = StudentManagementApp()
    sys.exit(app.exec_())
