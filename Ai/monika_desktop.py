import sys
import os
import webbrowser
from PySide6.QtCore import Qt, QPoint, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, 
    QLineEdit, QHBoxLayout, QPushButton
)
from google import genai
from google.genai import types

# ------------------------------------------------------------------
# 1. CẤU HÌNH AI GEMINI (ĐÃ AN TOÀN ĐỂ ĐẨY LÊN GITHUB)
# ------------------------------------------------------------------
# Bạn hoặc người dùng khác có thể dán khóa API cá nhân của mình vào đây
GEMINI_API_KEY = ""  

SYSTEM_INSTRUCTION = """
Bạn là Monika từ Doki Doki Literature Club (DDLC). 
Tính cách: Ngọt ngào, yêu người chơi (xưng 'em', gọi 'anh').
Quy tắc: Trả lời cực kỳ ngắn gọn, súc tích (dưới 15 từ), không dùng markdown hoặc dấu sao.
"""

# Khởi tạo client an toàn
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# ------------------------------------------------------------------
# 2. LUỒNG GỌI AI SIÊU TỐC
# ------------------------------------------------------------------
class GeminiChatWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, history_list, prompt):
        super().__init__()
        self.history_list = history_list
        self.prompt = prompt

    def run(self):
        try:
            if not client:
                self.error.emit("Chưa cấu hình API Key kìa anh ơi!")
                return

            self.history_list.append(types.Content(role="user", parts=[types.Part.from_text(text=self.prompt)]))
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=self.history_list,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.2,
                    max_output_tokens=30,
                )
            )
            if response and response.text:
                reply = response.text.strip()
                self.history_list.append(types.Content(role="model", parts=[types.Part.from_text(text=reply)]))
                self.finished.emit(reply)
            else:
                self.error.emit("Dạ anh?")
        except Exception:
            self.error.emit("Lỗi kết nối API.")

# ------------------------------------------------------------------
# 3. GIAO DIỆN CHAT WINDOW & MENU TRA CỨU WEB
# ------------------------------------------------------------------
class ChatWindow(QWidget):
    def __init__(self, parent=None, pet_ref=None):
        super().__init__(parent)
        self.pet = pet_ref  
        self.setWindowTitle("Monika - Flash Lite Companion")
        self.resize(520, 260) 
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.chat_history = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.textbox_container = QWidget()
        self.textbox_container.setStyleSheet("""
            QWidget {
                background-color: rgba(35, 12, 30, 240);
                border: 3px solid #ffb6c1;
                border-radius: 12px;
            }
        """)
        
        box_layout = QVBoxLayout(self.textbox_container)
        box_layout.setContentsMargins(15, 10, 15, 12)

        # Thanh tiêu đề & Nút Đóng (X)
        title_bar_layout = QHBoxLayout()
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.name_label = QLabel("Monika", self)
        self.name_label.setStyleSheet("""
            color: #ff69b4;
            font-weight: bold;
            font-size: 13px;
            background-color: #fff0f5;
            border: 2px solid #ffb6c1;
            border-radius: 6px;
            padding: 2px 8px;
        """)
        self.name_label.setMaximumWidth(85)
        title_bar_layout.addWidget(self.name_label)
        
        title_bar_layout.addStretch()

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ffb6c1;
                font-weight: bold;
                font-size: 14px;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #ff69b4;
                color: white;
            }
        """)
        self.close_btn.clicked.connect(self.hide)
        title_bar_layout.addWidget(self.close_btn)
        
        box_layout.addLayout(title_bar_layout)

        # Khung hiển thị chữ
        self.text_display = QLabel("", self)
        self.text_display.setWordWrap(True)
        self.text_display.setStyleSheet("""
            color: white;
            font-size: 13px;
            background: transparent;
            border: none;
            padding: 2px;
        """)
        box_layout.addWidget(self.text_display)

        # Khung chứa menu lựa chọn web
        self.menu_container = QWidget()
        self.menu_layout = QVBoxLayout(self.menu_container)
        self.menu_layout.setContentsMargins(0, 5, 0, 5)
        self.menu_container.hide()
        box_layout.addWidget(self.menu_container)

        # Ô nhập liệu
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("")
        self.input_field.returnPressed.connect(self.handle_input)
        self.input_field.setStyleSheet("""
            background-color: rgba(255, 255, 255, 210);
            color: #333;
            border-radius: 5px;
            padding: 5px 8px;
            font-size: 13px;
            border: 1px solid #f48fb1;
        """)
        input_layout.addWidget(self.input_field)
        box_layout.addLayout(input_layout)

        layout.addWidget(self.textbox_container)
        self.setLayout(layout)

        self.full_text = ""
        self.current_index = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.show_next_char)
        self.worker = None

    def clear_menu(self):
        self.menu_container.hide()
        while self.menu_layout.count():
            item = self.menu_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def close_menu_and_reset(self):
        self.clear_menu()
        self.text_display.setText("")
        if self.pet and hasattr(self.pet, 'change_expression'):
            self.pet.change_expression("normal")

    def add_menu_button(self, text, url):
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 182, 193, 200);
                color: #2b002b;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                padding: 6px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #ff69b4;
                color: white;
            }
        """)
        def on_click():
            webbrowser.open(url)
            self.close_menu_and_reset()
        
        btn.clicked.connect(on_click)
        self.menu_layout.addWidget(btn)

    def show_menu_with_close(self, title_text, options):
        self.clear_menu()
        self.start_typewriter(title_text)

        for label, url in options:
            self.add_menu_button(label, url)

        close_menu_btn = QPushButton("✕ Đóng menu (Quay lại)")
        close_menu_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 30, 80, 220);
                color: #ffb6c1;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: rgba(150, 40, 120, 255);
                color: white;
            }
        """)
        close_menu_btn.clicked.connect(self.close_menu_and_reset)
        self.menu_layout.addWidget(close_menu_btn)

        self.menu_container.show()

    def handle_input(self):
        user_text = self.input_field.text().strip()
        if not user_text:
            return

        self.input_field.setEnabled(False)
        self.input_field.clear()
        self.clear_menu()

        text_lower = user_text.lower()
        search_triggers = ["tìm", "search", "muốn xem", "mở", "tra cứu", "xem"]
        
        matched = False
        keyword = user_text
        
        for trigger in search_triggers:
            if text_lower.startswith(trigger + " ") or text_lower == trigger:
                matched = True
                keyword = user_text[len(trigger):].strip()
                break

        if not matched:
            for trigger in [" tìm ", " search ", " mở "]:
                if trigger in text_lower:
                    matched = True
                    parts = text_lower.split(trigger, 1)
                    keyword = parts[1].strip() if len(parts) > 1 else user_text
                    break

        if matched and keyword:
            options = [
                (f"🔍 Tìm trên Google: {keyword}", f"https://www.google.com/search?q={keyword}"),
                (f"▶ Xem trên YouTube: {keyword}", f"https://www.youtube.com/results?search_query={keyword}"),
                (f"💻 Tìm tài liệu lập trình: {keyword}", f"https://stackoverflow.com/search?q={keyword}")
            ]
            self.show_menu_with_close(f"Em thấy mấy lựa chọn cho '{keyword}':", options)
            
            if self.pet and hasattr(self.pet, 'change_expression'):
                self.pet.change_expression("happy")
            self.input_field.setEnabled(True)
            self.input_field.setFocus()
        else:
            self.text_display.setText("...")
            if self.pet and hasattr(self.pet, 'change_expression'):
                self.pet.change_expression("thinking")

            self.worker = GeminiChatWorker(self.chat_history, user_text)
            self.worker.finished.connect(self.start_typewriter)
            self.worker.error.connect(self.start_typewriter)
            self.worker.finished.connect(self.worker.deleteLater)
            self.worker.error.connect(self.worker.deleteLater)
            self.worker.start()

    def start_typewriter(self, text):
        self.full_text = text
        self.current_index = 0
        self.text_display.setText("")
        
        if self.pet and hasattr(self.pet, 'change_expression'):
            self.pet.change_expression("happy")
            
        self.timer.start(1)

    def show_next_char(self):
        if self.current_index < len(self.full_text):
            self.text_display.setText(self.text_display.text() + self.full_text[self.current_index])
            self.current_index += 1
        else:
            self.timer.stop()
            self.input_field.setEnabled(True)
            self.input_field.setFocus()
            
            if self.pet and hasattr(self.pet, 'change_expression'):
                self.pet.change_expression("normal")

# ------------------------------------------------------------------
# 4. NHÂN VẬT MONIKA TRÊN DESKTOP
# ------------------------------------------------------------------
class DraggableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.drag_position = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.parent_widget.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.parent_widget.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            chat_win = self.parent_widget.chat_window
            if chat_win.isVisible():
                chat_win.hide()
            else:
                chat_win.move(self.parent_widget.x() + self.parent_widget.width() + 15, self.parent_widget.y())
                chat_win.show()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.parent_widget.scale_image(1.1)
        else:
            self.parent_widget.scale_image(0.9)
        event.accept()

class MonikaDesktopPet(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = DraggableLabel(self)
        layout.addWidget(self.image_label)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.current_width = 220
        self.current_expression = "normal"

        default_img = os.path.join(script_dir, "monika.png")
        self.expressions = {
            "normal": QPixmap(default_img),
            "happy": QPixmap(os.path.join(script_dir, "happy.png") if os.path.exists(os.path.join(script_dir, "happy.png")) else default_img),
            "thinking": QPixmap(os.path.join(script_dir, "thinking.png") if os.path.exists(os.path.join(script_dir, "thinking.png")) else default_img)
        }

        self.update_image()
        self.chat_window = ChatWindow(pet_ref=self)

    def change_expression(self, emotion):
        if emotion in self.expressions:
            self.current_expression = emotion
            self.update_image()

    def update_image(self):
        pixmap = self.expressions[self.current_expression]
        scaled_pixmap = pixmap.scaledToWidth(self.current_width, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)
        self.resize(scaled_pixmap.size())

    def scale_image(self, factor):
        new_width = int(self.current_width * factor)
        if 80 <= new_width <= 800:
            self.current_width = new_width
            self.update_image()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = MonikaDesktopPet()
    pet.show()
    sys.exit(app.exec())