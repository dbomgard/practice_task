import threading

from PyQt6 import QtGui
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QGridLayout, QPushButton, \
    QCheckBox, QMessageBox, QWIDGETSIZE_MAX, QLineEdit, QHBoxLayout, QFileDialog
import cv2 as cv

PROG_NAME = "Program"

MIN_SIZE = QSize()


def img_select_channels(img0: cv.Mat, r: bool, g: bool, b: bool):
    """Возвращает изображение, в котором видны только заданные каналы"""
    img = img0.copy()
    if not r:
        img[:, :, 0] = 0
    if not g:
        img[:, :, 1] = 0
    if not b:
        img[:, :, 2] = 0
    return img


def img_crop(img0: cv.Mat, x1, y1, x2, y2):
    """Обрезает изображение по заданным координатам"""
    h, w, _ = img0.shape
    if x1 < 0 or x2 <= x1 or y1 < 0 or y2 <= y1 or x2 > w or x1 >= x2 or y2 > h or y1 >= y2:
        raise BaseException('Неверные координаты')
    return img0[y1:y2, x1:x2]


def img_brighter(img0: cv.Mat, br):
    """Увеличивает интенсивность каждого канала на заданную величину"""
    return cv.convertScaleAbs(img0, alpha=1.0, beta=br)


def img_draw_line(img0: cv.Mat, x1, y1, x2, y2, thickness):
    """Рисует зеленую линию на изображении с заданными координатами и толщиной"""
    return cv.line(img0, (x1, y1), (x2, y2), (0, 255, 0), thickness=thickness)


class MainWindow(QMainWindow):
    """ Главное окно приложения """

    def __init__(self):
        super().__init__()
        self.setWindowTitle(PROG_NAME)

        self.camera = None
        self.capturing = False


        # Настройка виджетов

        load_button = QPushButton("Загрузить")
        camera_button = QPushButton("Камера")
        save_button = QPushButton("Сохранить")
        crop_button = QPushButton("Обрезать")
        bright_button = QPushButton("Сделать ярче")
        line_button = QPushButton("Нарисовать линию")

        load_button.clicked.connect(self.load_image_action)
        camera_button.clicked.connect(self.init_camera_action)
        save_button.clicked.connect(self.save_image_action)
        crop_button.clicked.connect(self.crop_image_action)
        bright_button.clicked.connect(self.make_image_brighter_action)
        line_button.clicked.connect(self.draw_green_line_action)

        self.red_box = QCheckBox("Красный")
        self.green_box = QCheckBox("Зеленый")
        self.blue_box = QCheckBox("Синий")
        self.red_box.setChecked(True)
        self.green_box.setChecked(True)
        self.blue_box.setChecked(True)
        self.red_box.checkStateChanged.connect(self.show_image)
        self.green_box.checkStateChanged.connect(self.show_image)
        self.blue_box.checkStateChanged.connect(self.show_image)

        self.control_widget = QWidget()
        self.control_widget.setLayout(QGridLayout())
        self.control_widget.layout().addWidget(load_button, 0, 0, 1, 1)
        self.control_widget.layout().addWidget(camera_button, 0, 1, 1, 1)
        self.control_widget.layout().addWidget(save_button, 0, 2, 1, 1)
        self.control_widget.layout().addWidget(crop_button, 0, 3, 1, 1)
        self.control_widget.layout().addWidget(bright_button, 0, 4, 1, 1)
        self.control_widget.layout().addWidget(line_button, 0, 5, 1, 1)
        self.control_widget.layout().addWidget(self.red_box, 1, 0, 1, 2)
        self.control_widget.layout().addWidget(self.green_box, 1, 2, 1, 2)
        self.control_widget.layout().addWidget(self.blue_box, 1, 4, 1, 2)

        self.aux_panel = QWidget()
        self.aux_panel.setLayout(QVBoxLayout())

        self.canvas = QLabel()

        self.main_widget = QWidget()
        self.main_widget.setLayout(QVBoxLayout())
        self.main_widget.layout().addWidget(self.canvas)

        self.setCentralWidget(QWidget())
        self.centralWidget().setLayout(QVBoxLayout())
        self.centralWidget().layout().addWidget(self.control_widget)
        self.centralWidget().layout().addWidget(self.aux_panel)
        self.centralWidget().layout().addWidget(self.main_widget)

        self.timer = None
        self.cv_image = None
        self.aux_widget = None

    def enable_controls(self, enable):
        self.control_widget.setEnabled(enable)

    def show_capture_panel(self):
        self.aux_widget = CapturePanel(self)
        self.aux_panel.layout().addWidget(self.aux_widget)

    def show_crop_panel(self):
        self.aux_widget = CropPanel(self)
        self.aux_panel.layout().addWidget(self.aux_widget)

    def show_brighter_panel(self):
        self.aux_widget = BrightnessPanel(self)
        self.aux_panel.layout().addWidget(self.aux_widget)

    def show_line_panel(self):
        self.aux_widget = LinePanel(self)
        self.aux_panel.layout().addWidget(self.aux_widget)

    def hide_aux_controls(self):
        self.aux_widget.close()
        self.aux_panel.layout().removeWidget(self.aux_widget)

    def restore_size(self):
        self.main_widget.layout().removeWidget(self.canvas)
        self.canvas = QLabel()
        self.main_widget.layout().addWidget(self.canvas)
        self.setFixedSize(MIN_SIZE)
        self.setFixedSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
        self.show_image()

    def load_image_action(self):
        filename = QFileDialog.getOpenFileName(self, "Открыть", ".", "Изображения (*.png *.jpg *.jpeg *.bmp)")[0]
        if filename is None:
            return
        self.cv_image = cv.imread(filename, cv.IMREAD_COLOR)
        if self.cv_image is None:
            QMessageBox.critical(self, PROG_NAME, 'Невозможно открыть файл!')
            return

        self.cv_image = cv.cvtColor(self.cv_image, cv.COLOR_BGR2RGB)
        self.restore_size()

    def save_image_action(self):
        if self.cv_image is None:
            QMessageBox.critical(self, PROG_NAME, 'Сначала выберите изображение!')
            return
        filename = QFileDialog.getSaveFileName(self, "Сохранить", "Безымянный.png",
                                               "Изображения (*.png *.jpg *.jpeg *.bmp)")[0]
        if filename is None:
            return

        cv_image = cv.cvtColor(self.cv_image, cv.COLOR_RGB2BGR)
        cv.imwrite(filename, cv_image)

    def init_camera_action(self):
        self.cv_image = None
        self.restore_size()
        self.camera = cv.VideoCapture(0)
        if self.camera is None:
            QMessageBox.critical(self, PROG_NAME, 'Камера не найдена!')
            return
        self.enable_controls(False)
        self.show_capture_panel()
        self.capturing = True
        self.timer = threading.Timer(0.1, self.timer_event)
        self.timer.start()

    def crop_image_action(self):
        if self.cv_image is None:
            QMessageBox.critical(self, PROG_NAME, 'Сначала выберите изображение!')
            return
        self.enable_controls(False)
        self.show_crop_panel()

    def make_image_brighter_action(self):
        if self.cv_image is None:
            QMessageBox.critical(self, PROG_NAME, 'Сначала выберите изображение!')
            return
        self.enable_controls(False)
        self.show_brighter_panel()

    def draw_green_line_action(self):
        if self.cv_image is None:
            QMessageBox.critical(self, PROG_NAME, 'Сначала выберите изображение!')
            return
        self.enable_controls(False)
        self.show_line_panel()

    def cancel_capturing_event(self):
        self.capturing = False
        self.timer.cancel()
        self.camera.release()
        self.camera = None
        self.enable_controls(True)
        self.hide_aux_controls()
        self.cv_image = None
        self.canvas.setPixmap(QtGui.QPixmap())
        self.restore_size()

    def cancel_event(self):
        self.enable_controls(True)
        self.hide_aux_controls()
        self.restore_size()

    def capture_event(self):
        self.capturing = False
        self.timer.cancel()
        self.camera.release()
        self.camera = None
        self.enable_controls(True)
        self.hide_aux_controls()
        self.restore_size()

    def crop_event(self, x1, y1, x2, y2):
        try:
            self.cv_image = img_crop(self.cv_image, x1, y1, x2, y2)
        except:
            QMessageBox.critical(self, PROG_NAME, 'Неверные координаты!')
        self.enable_controls(True)
        self.hide_aux_controls()
        self.restore_size()

    def brighter_event(self, br):
        try:
            self.cv_image = img_brighter(self.cv_image, br)
        except:
            QMessageBox.critical(self, PROG_NAME, 'Неверное значение!')
        self.enable_controls(True)
        self.hide_aux_controls()
        self.restore_size()

    def draw_line_event(self, x1, y1, x2, y2, t):
        try:
            self.cv_image = img_draw_line(self.cv_image, x1, y1, x2, y2, t)
        except:
            QMessageBox.critical(self, PROG_NAME, 'Неверные координаты!')
        self.enable_controls(True)
        self.hide_aux_controls()
        self.restore_size()

    def timer_event(self):
        self.take_snapshot()
        if self.capturing:
            self.timer = threading.Timer(0.1, self.timer_event)
            self.timer.start()

    def take_snapshot(self):
        ret, frame = self.camera.read()
        if not ret:
            return
        self.cv_image = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
        self.show_image()

    def show_image(self):
        if self.cv_image is not None:
            r = self.red_box.isChecked()
            g = self.green_box.isChecked()
            b = self.blue_box.isChecked()
            cv_image = img_select_channels(self.cv_image, r, g, b)
            h, w, ch = cv_image.shape
            q_img = QImage(cv_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self.canvas.setPixmap(QtGui.QPixmap(q_img))

    def closeEvent(self, a0):
        if self.timer:
            self.timer.cancel()


class CapturePanel(QWidget):
    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.setLayout(QHBoxLayout())
        capture_button = QPushButton("Снимок")
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(main_window.cancel_capturing_event)
        capture_button.clicked.connect(main_window.capture_event)
        self.layout().addWidget(capture_button)
        self.layout().addWidget(cancel_button)


class CropPanel(QWidget):
    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window

        x1 = 0
        y1 = 0
        x2 = main_window.cv_image.shape[1]
        y2 = main_window.cv_image.shape[0]

        self.setLayout(QVBoxLayout())
        x1_label = QLabel("x1:")
        self.x1_edit = QLineEdit(str(x1))
        y1_label = QLabel("y1:")
        self.y1_edit = QLineEdit(str(y1))
        x2_label = QLabel("x2:")
        self.x2_edit = QLineEdit(str(x2))
        y2_label = QLabel("y2:")
        self.y2_edit = QLineEdit(str(y2))

        crop_button = QPushButton("Обрезать")
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(main_window.cancel_event)
        crop_button.clicked.connect(self.crop_event)

        top_panel = QWidget()
        top_panel.setLayout(QHBoxLayout())
        bottom_panel = QWidget()
        bottom_panel.setLayout(QHBoxLayout())

        top_panel.layout().addWidget(x1_label)
        top_panel.layout().addWidget(self.x1_edit)
        top_panel.layout().addWidget(y1_label)
        top_panel.layout().addWidget(self.y1_edit)
        top_panel.layout().addWidget(x2_label)
        top_panel.layout().addWidget(self.x2_edit)
        top_panel.layout().addWidget(y2_label)
        top_panel.layout().addWidget(self.y2_edit)

        bottom_panel.layout().addWidget(crop_button)
        bottom_panel.layout().addWidget(cancel_button)

        self.layout().addWidget(top_panel)
        self.layout().addWidget(bottom_panel)

    def crop_event(self):
        try:
            x1 = int(self.x1_edit.text())
            y1 = int(self.y1_edit.text())
            x2 = int(self.x2_edit.text())
            y2 = int(self.y2_edit.text())
            self.main_window.crop_event(x1, y1, x2, y2)
        except:
            QMessageBox.critical(self, PROG_NAME, 'Неверные координаты!')


class BrightnessPanel(QWidget):
    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window

        self.setLayout(QVBoxLayout())
        value_label = QLabel("Увеличить яркость на:")
        self.value_edit = QLineEdit(str(10))

        brighter_button = QPushButton("Сделать ярче")
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(main_window.cancel_event)
        brighter_button.clicked.connect(self.brighter_event)

        top_panel = QWidget()
        top_panel.setLayout(QHBoxLayout())
        bottom_panel = QWidget()
        bottom_panel.setLayout(QHBoxLayout())

        top_panel.layout().addWidget(value_label)
        top_panel.layout().addWidget(self.value_edit)

        bottom_panel.layout().addWidget(brighter_button)
        bottom_panel.layout().addWidget(cancel_button)

        self.layout().addWidget(top_panel)
        self.layout().addWidget(bottom_panel)

    def brighter_event(self):
        try:
            br = int(self.value_edit.text())
            self.main_window.brighter_event(br)
        except:
            QMessageBox.critical(self, PROG_NAME, 'Неверное значение!')


class LinePanel(QWidget):
    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window

        x1 = 0
        y1 = 0
        x2 = main_window.cv_image.shape[1]
        y2 = main_window.cv_image.shape[0]

        self.setLayout(QVBoxLayout())
        x1_label = QLabel("x1:")
        self.x1_edit = QLineEdit(str(x1))
        y1_label = QLabel("y1:")
        self.y1_edit = QLineEdit(str(y1))
        x2_label = QLabel("x2:")
        self.x2_edit = QLineEdit(str(x2))
        y2_label = QLabel("y2:")
        self.y2_edit = QLineEdit(str(y2))
        t_label = QLabel("thickness:")
        self.t_edit = QLineEdit(str(3))

        draw_button = QPushButton("Нарисовать")
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(main_window.cancel_event)
        draw_button.clicked.connect(self.draw_event)

        top_panel = QWidget()
        top_panel.setLayout(QHBoxLayout())
        bottom_panel = QWidget()
        bottom_panel.setLayout(QHBoxLayout())

        top_panel.layout().addWidget(x1_label)
        top_panel.layout().addWidget(self.x1_edit)
        top_panel.layout().addWidget(y1_label)
        top_panel.layout().addWidget(self.y1_edit)
        top_panel.layout().addWidget(x2_label)
        top_panel.layout().addWidget(self.x2_edit)
        top_panel.layout().addWidget(y2_label)
        top_panel.layout().addWidget(self.y2_edit)
        top_panel.layout().addWidget(t_label)
        top_panel.layout().addWidget(self.t_edit)

        bottom_panel.layout().addWidget(draw_button)
        bottom_panel.layout().addWidget(cancel_button)

        self.layout().addWidget(top_panel)
        self.layout().addWidget(bottom_panel)

    def draw_event(self):
        try:
            x1 = int(self.x1_edit.text())
            y1 = int(self.y1_edit.text())
            x2 = int(self.x2_edit.text())
            y2 = int(self.y2_edit.text())
            t = int(self.t_edit.text())
            self.main_window.draw_line_event(x1, y1, x2, y2, t)
        except:
            QMessageBox.critical(self, PROG_NAME, 'Неверные координаты!')


def main():
    """ Функция запуска приложения """
    global MIN_SIZE
    app = QApplication([])  # Создаем экземпляр QApplication
    window = MainWindow()  # Создаём объект класса MainWindow
    window.show()  # Показываем окно
    MIN_SIZE = window.size()
    app.exec()  # Запускаем цикл событий приложения


if __name__ == '__main__':
    main()
