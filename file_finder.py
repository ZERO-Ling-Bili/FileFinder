import sys
import os
import subprocess
import platform
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QFileDialog, QListWidget, QLabel,
                             QMessageBox, QColorDialog, QMenu, QAction, QDialog,
                             QFormLayout, QDialogButtonBox, QListWidgetItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPoint, QSize
from PyQt5.QtGui import QPixmap, QFont, QPalette, QBrush, QColor


class SearchWorker(QThread):
    """后台搜索线程，避免UI卡顿"""
    found_file = pyqtSignal(str, str)  # 信号：文件路径, 扩展名
    search_finished = pyqtSignal()

    def __init__(self, root_path, extensions, keyword):
        super().__init__()
        self.root_path = root_path
        self.extensions = [ext.lower().strip('.') for ext in extensions if ext]
        self.keyword = keyword.lower()
        self.is_running = True

    def run(self):
        try:
            for dirpath, dirnames, filenames in os.walk(self.root_path):
                if not self.is_running:
                    break
                # 简单优化：跳过隐藏文件夹
                dirnames[:] = [d for d in dirnames if not d.startswith('.')]

                for filename in filenames:
                    if not self.is_running:
                        break

                    # 1. 关键字匹配 (文件名)
                    if self.keyword and self.keyword not in filename.lower():
                        continue

                    # 2. 扩展名匹配
                    ext = ''
                    if '.' in filename:
                        ext = filename.rsplit('.', 1)[-1].lower()

                    if self.extensions:
                        if ext not in self.extensions:
                            continue

                    full_path = os.path.join(dirpath, filename)
                    self.found_file.emit(full_path, ext)
        except Exception as e:
            print(f"Search error: {e}")
        finally:
            self.search_finished.emit()

    def stop(self):
        self.is_running = False


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, parent=None, current_path="", current_keyword="", current_ext=""):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(450)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QFormLayout(self)

        # 路径选择
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit(current_path)
        self.path_input.setPlaceholderText("选择搜索根目录...")
        btn_browse = QPushButton("浏览")
        btn_browse.clicked.connect(self.browse_directory)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(btn_browse)
        layout.addRow("搜索路径:", path_layout)

        # 关键字
        self.keyword_input = QLineEdit(current_keyword)
        self.keyword_input.setPlaceholderText("输入文件名关键字（可选）")
        layout.addRow("关键字:", self.keyword_input)

        # 文件类型筛选
        self.ext_input = QLineEdit(current_ext)
        self.ext_input.setPlaceholderText("例如: jpg; png; txt (留空则不限)")
        layout.addRow("文件类型:", self.ext_input)

        # 分隔线
        layout.addRow(QLabel("—————— 外观设置 ——————"))

        # 背景设置按钮
        bg_layout = QHBoxLayout()
        btn_bg_color = QPushButton("更改背景色")
        btn_bg_color.clicked.connect(parent.change_background_color)
        btn_bg_img = QPushButton("设置背景图")
        btn_bg_img.clicked.connect(parent.change_background_image)
        btn_reset_bg = QPushButton("重置背景")
        btn_reset_bg.clicked.connect(parent.reset_background)
        bg_layout.addWidget(btn_bg_color)
        bg_layout.addWidget(btn_bg_img)
        bg_layout.addWidget(btn_reset_bg)
        layout.addRow("背景设置:", bg_layout)

        # 确定取消按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "选择搜索目录")
        if directory:
            self.path_input.setText(directory)

    def get_values(self):
        return {
            "path": self.path_input.text(),
            "keyword": self.keyword_input.text(),
            "ext": self.ext_input.text()
        }


class FileFinderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("文件搜索")

        # 配置文件路径
        self.config_path = os.path.join(os.path.expanduser("~"), ".file_finder_config.json")

        # 初始化变量
        self.current_bg_color = "#39C5BB"  # 默认颜色 #39C5BB
        self.current_bg_image = None
        self.search_worker = None
        self.drag_position = None

        # 加载配置
        self.load_config()

        # 无边框窗口
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self.init_ui()
        self.apply_style()

        # 如果有背景图，调整窗口大小匹配图片比例
        if self.current_bg_image and os.path.exists(self.current_bg_image):
            self.adjust_window_to_bg_image()

    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.current_bg_color = config.get("bg_color", "#39C5BB")
                    self.current_bg_image = config.get("bg_image", None)
            except Exception as e:
                print(f"加载配置失败: {e}")

    def save_config(self):
        """保存配置到文件"""
        config = {
            "bg_color": self.current_bg_color,
            "bg_image": self.current_bg_image
        }
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- 自定义标题栏 ---
        title_bar = QWidget()
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("🔍 文件搜索")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")

        btn_settings = QPushButton("⚙ 设置")
        btn_settings.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.3);
            }
        """)
        btn_settings.clicked.connect(self.open_settings)

        btn_min = QPushButton("─")
        btn_min.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                padding: 6px 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.2);
            }
        """)
        btn_min.clicked.connect(self.showMinimized)

        btn_close = QPushButton("✕")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                padding: 6px 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e81123;
            }
        """)
        btn_close.clicked.connect(self.close)

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(btn_settings)
        title_layout.addWidget(btn_min)
        title_layout.addWidget(btn_close)

        main_layout.addWidget(title_bar)

        # --- 搜索栏 ---
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入文件名关键字搜索...")
        self.search_input.returnPressed.connect(self.start_search)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 15px;
                border: none;
                border-radius: 20px;
                background-color: rgba(255, 255, 255, 0.9);
                font-size: 14px;
            }
        """)

        self.btn_search = QPushButton("搜索")
        self.btn_search.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.3);
            }
            QPushButton:disabled {
                background-color: rgba(255,255,255,0.1);
            }
        """)
        self.btn_search.clicked.connect(self.start_search)

        self.btn_stop = QPushButton("停止")
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 20px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.3);
            }
            QPushButton:disabled {
                background-color: rgba(255,255,255,0.1);
            }
        """)
        self.btn_stop.clicked.connect(self.stop_search)
        self.btn_stop.setEnabled(False)

        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.btn_search)
        search_layout.addWidget(self.btn_stop)

        main_layout.addLayout(search_layout)

        # --- 文件列表 ---
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self.open_file)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_context_menu)
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(255, 255, 255, 0.9);
                border: none;
                border-radius: 10px;
                padding: 5px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                background-color: rgba(57, 197, 187, 0.3);
                color: #333;
            }
            QListWidget::item:hover {
                background-color: rgba(57, 197, 187, 0.1);
            }
        """)

        main_layout.addWidget(self.file_list, 1)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 12px;")
        main_layout.addWidget(self.status_label)

        # 初始默认搜索路径
        self.search_path = os.path.expanduser("~")
        self.search_ext = ""
        self.search_keyword = ""

        # 设置初始窗口大小
        self.resize(800, 600)

    def adjust_window_to_bg_image(self):
        """调整窗口大小匹配背景图比例"""
        if self.current_bg_image and os.path.exists(self.current_bg_image):
            pixmap = QPixmap(self.current_bg_image)
            if not pixmap.isNull():
                img_width = pixmap.width()
                img_height = pixmap.height()

                # 限制最大窗口大小不超过屏幕的80%
                screen = QApplication.primaryScreen().availableGeometry()
                max_w = int(screen.width() * 0.8)
                max_h = int(screen.height() * 0.8)

                # 计算缩放比例
                scale = min(max_w / img_width, max_h / img_height, 1.0)
                win_w = int(img_width * scale)
                win_h = int(img_height * scale)

                # 最小尺寸
                win_w = max(win_w, 600)
                win_h = max(win_h, 400)

                self.resize(win_w, win_h)

    def apply_style(self):
        """应用自定义背景和基础样式"""
        # 设置窗口圆角
        self.setStyleSheet("""
            QMainWindow {
                border-radius: 15px;
                overflow: hidden;
            }
        """)

        # 设置背景图片或颜色
        palette = self.palette()
        if self.current_bg_image and os.path.exists(self.current_bg_image):
            pixmap = QPixmap(self.current_bg_image)
            if not pixmap.isNull():
                # 缩放图片以填充窗口，保持比例裁剪
                scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                brush = QBrush(scaled_pixmap)
                palette.setBrush(QPalette.Window, brush)
        else:
            palette.setColor(QPalette.Window, QColor(self.current_bg_color))

        self.setPalette(palette)
        self.setAutoFillBackground(True)

    def open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self, self.search_path, self.search_keyword, self.search_ext)
        if dialog.exec_() == QDialog.Accepted:
            values = dialog.get_values()
            self.search_path = values["path"]
            self.search_keyword = values["keyword"]
            self.search_ext = values["ext"]

    def change_background_color(self):
        color = QColorDialog.getColor(QColor(self.current_bg_color))
        if color.isValid():
            self.current_bg_image = None  # 清除图片背景
            self.current_bg_color = color.name()
            self.apply_style()
            self.save_config()

    def change_background_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择背景图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if file_path:
            self.current_bg_image = file_path
            self.adjust_window_to_bg_image()
            self.apply_style()
            self.save_config()

    def reset_background(self):
        self.current_bg_image = None
        self.current_bg_color = "#39C5BB"
        self.apply_style()
        self.resize(800, 600)
        self.save_config()

    def show_context_menu(self, position):
        """显示右键菜单"""
        item = self.file_list.itemAt(position)
        if not item:
            return

        file_path = item.data(Qt.UserRole)

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 25px;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background-color: rgba(57, 197, 187, 0.2);
            }
        """)

        # 在资源管理器中打开
        open_explorer_action = QAction("📂 在文件资源管理器中打开", self)
        open_explorer_action.triggered.connect(lambda: self.open_in_explorer(file_path))
        menu.addAction(open_explorer_action)

        # 复制文件路径
        copy_path_action = QAction("📋 复制文件路径", self)
        copy_path_action.triggered.connect(lambda: self.copy_file_path(file_path))
        menu.addAction(copy_path_action)

        # 选择打开方式
        open_with_action = QAction("🔄 选择打开方式", self)
        open_with_action.triggered.connect(lambda: self.open_with(file_path))
        menu.addAction(open_with_action)

        menu.exec_(self.file_list.viewport().mapToGlobal(position))

    def open_in_explorer(self, file_path):
        """在文件资源管理器中打开并选中文件"""
        try:
            if platform.system() == 'Windows':
                subprocess.run(['explorer', '/select,', os.path.normpath(file_path)])
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', '-R', file_path])
            else:  # Linux
                subprocess.run(['xdg-open', os.path.dirname(file_path)])
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开资源管理器: {str(e)}")

    def copy_file_path(self, file_path):
        """复制文件路径到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(file_path)
        self.status_label.setText("已复制文件路径到剪贴板")

    def open_with(self, file_path):
        """选择程序打开文件"""
        program, _ = QFileDialog.getOpenFileName(self, "选择打开方式", "", "可执行文件 (*.exe *.app);;所有文件 (*.*)")
        if program:
            try:
                subprocess.Popen([program, file_path])
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法打开文件: {str(e)}")

    def start_search(self):
        # 如果搜索路径是默认的，或者没设置，先弹出设置
        if not self.search_path or not os.path.exists(self.search_path):
            QMessageBox.information(self, "提示", "请先在设置中选择搜索目录")
            self.open_settings()
            if not self.search_path or not os.path.exists(self.search_path):
                return

        # 从搜索框获取关键字
        self.search_keyword = self.search_input.text()

        # 清空旧结果
        self.file_list.clear()

        # 解析扩展名
        extensions = [e.strip() for e in self.search_ext.split(';') if e.strip()]

        self.btn_search.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_label.setText("正在搜索...")

        self.search_worker = SearchWorker(self.search_path, extensions, self.search_keyword)
        self.search_worker.found_file.connect(self.add_file_to_list)
        self.search_worker.search_finished.connect(self.on_search_finished)
        self.search_worker.start()

    def stop_search(self):
        if self.search_worker:
            self.search_worker.stop()
            self.btn_stop.setEnabled(False)
            self.status_label.setText("搜索已停止")

    def add_file_to_list(self, file_path, ext):
        item = QListWidgetItem(f"{os.path.basename(file_path)}  [.{ext}]")
        item.setData(Qt.UserRole, file_path)  # 存储完整路径
        self.file_list.addItem(item)

    def on_search_finished(self):
        self.btn_search.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_label.setText(f"搜索完成，共找到 {self.file_list.count()} 个文件")

    def open_file(self, item):
        file_path = item.data(Qt.UserRole)
        if file_path and os.path.exists(file_path):
            try:
                if platform.system() == 'Darwin':  # macOS
                    subprocess.call(('open', file_path))
                elif platform.system() == 'Windows':  # Windows
                    os.startfile(file_path)
                else:  # Linux
                    subprocess.call(('xdg-open', file_path))
            except Exception as e:
                QMessageBox.critical(self, "打开失败", f"无法打开文件: {str(e)}")
        else:
            QMessageBox.warning(self, "错误", "文件不存在或路径无效")

    def resizeEvent(self, event):
        # 窗口大小改变时，如果使用的是背景图片，需要重新应用样式以缩放图片
        if self.current_bg_image:
            self.apply_style()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        """实现窗口拖动"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """实现窗口拖动"""
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        """实现窗口拖动"""
        self.drag_position = None


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # 设置全局字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    window = FileFinderApp()
    window.show()
    sys.exit(app.exec_())