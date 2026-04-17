import sys
import cv2
import os
import uuid
import random
from datetime import datetime
from datetime import date
from PIL import Image

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from recognizer import predict
from database import init_db, insert_pet, get_pets_by_category, search_pets
from database import get_daily_reminders, update_daily_reminder
from database import get_health_events, upsert_health_event, add_recognition_record, get_recognition_records
from database import list_pet_profiles, get_pet_profile_by_id, create_pet_profile, update_pet_profile_by_id
from config import UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
init_db()


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class PetSystem(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Pet&Recognition")
        self.setWindowIcon(self.build_paw_icon())
        self.setGeometry(200,100,1200,700)

        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        self.frame_count = 0
        self.running = False
        self.current_upload_path = None
        self.paw_count = 0
        self.last_realtime_label = "???"
        self.last_realtime_conf = 0.0
        self.awaiting_camera_confirm = False
        self.pending_camera_main = ""
        self.pending_camera_conf = 0.0
        self.reminder_checkboxes = []
        self.current_profile_id = None
        self.low_conf_camera_tips = ["请对准目标", "请勿乱晃", "请更换目标", "请保持画面稳定", "请靠近一些"]

        self.init_ui()

    def build_paw_icon(self):
        size = 64
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#2E7D32"))
        p.drawEllipse(20, 26, 24, 22)
        p.drawEllipse(13, 15, 11, 13)
        p.drawEllipse(25, 9, 11, 13)
        p.drawEllipse(38, 15, 11, 13)
        p.drawEllipse(21, 40, 8, 8)
        p.drawEllipse(35, 40, 8, 8)
        p.end()
        return QIcon(pix)


    def init_ui(self):

        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # 左侧导航
        sidebar = QVBoxLayout()

        btn_book = QPushButton(QIcon("icons/book.png"),"宠 物 百 科")
        btn_add = QPushButton(QIcon("icons/add.png"),"添 加 宠 物")

        btn_book.clicked.connect(self.open_pet_book)
        btn_add.clicked.connect(self.open_pet_editor)

        sidebar.addWidget(btn_book)
        sidebar.addWidget(btn_add)
        profile_box = QGroupBox("我的宠物档案")
        profile_layout = QVBoxLayout(profile_box)
        self.profile_selector = QComboBox()
        self.profile_selector.currentIndexChanged.connect(self.on_profile_changed)
        self.profile_name_label = QLabel("当前宠物：")
        self.profile_type_label = QLabel("类型：")
        self.profile_note_label = QLabel("备注：")
        self.profile_note_label.setWordWrap(True)
        btn_add_profile = QPushButton("新增档案")
        btn_edit_profile = QPushButton("编辑档案")
        btn_add_profile.clicked.connect(self.open_profile_creator)
        btn_edit_profile.clicked.connect(self.open_profile_editor)
        profile_layout.addWidget(self.profile_selector)
        profile_layout.addWidget(self.profile_name_label)
        profile_layout.addWidget(self.profile_type_label)
        profile_layout.addWidget(self.profile_note_label)
        profile_layout.addWidget(btn_add_profile)
        profile_layout.addWidget(btn_edit_profile)
        sidebar.addWidget(profile_box)

        reminder_box = QGroupBox("今日提醒")
        self.reminder_layout = QVBoxLayout(reminder_box)
        sidebar.addWidget(reminder_box)

        calendar_box = QGroupBox("健康日历")
        calendar_layout = QVBoxLayout(calendar_box)
        self.health_line_1 = QLabel("疫苗复查：")
        self.health_line_2 = QLabel("体内驱虫：")
        self.health_today = QLabel("今日：")
        btn_edit_health = QPushButton("编辑日历")
        btn_edit_health.clicked.connect(self.open_health_editor)
        calendar_layout.addWidget(self.health_line_1)
        calendar_layout.addWidget(self.health_line_2)
        calendar_layout.addWidget(self.health_today)
        calendar_layout.addWidget(btn_edit_health)
        sidebar.addWidget(calendar_box)

        history_box = QGroupBox("识别记录")
        history_layout = QVBoxLayout(history_box)
        self.history_list = QListWidget()
        self.history_list.setMinimumWidth(240)
        self.history_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_list.setWordWrap(True)
        history_layout.addWidget(self.history_list)
        sidebar.addWidget(history_box)
        sidebar.addStretch()

        content_root = QVBoxLayout()
        content_root.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("🐾 Pet&Recognition")
        title.setObjectName("heroTitle")
        badges = QLabel("🐶  🐱  🐰  🐦   🌿")
        badges.setObjectName("heroBadges")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(badges)

        content = QGridLayout()
        content.setHorizontalSpacing(10)
        content.setVerticalSpacing(10)

        # 摄像头画面
        self.camera_label = ClickableLabel()
        self.camera_label.setObjectName("previewLabel")
        self.camera_label.setFixedSize(500,300)
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setCursor(Qt.PointingHandCursor)
        self.camera_label.clicked.connect(self.toggle_camera)

        self.upload_label = ClickableLabel()
        self.upload_label.setObjectName("previewLabel")
        self.upload_label.setFixedSize(500,300)
        self.upload_label.setAlignment(Qt.AlignCenter)
        self.upload_label.setCursor(Qt.PointingHandCursor)
        self.upload_label.clicked.connect(self.upload_image)

        self.camera_result = QTextEdit()
        self.camera_result.setObjectName("resultBox")
        self.camera_result.setReadOnly(True)
        self.camera_yes_btn = QPushButton("YES")
        self.camera_no_btn = QPushButton("NO")
        self.camera_yes_btn.setObjectName("confirmYesBtn")
        self.camera_no_btn.setObjectName("confirmNoBtn")
        self.camera_yes_btn.setToolTip("确认结果并写入识别记录")
        self.camera_no_btn.setToolTip("否定本次结果并重新识别")
        self.camera_yes_btn.clicked.connect(self.on_camera_confirm_yes)
        self.camera_no_btn.clicked.connect(self.on_camera_confirm_no)
        self.camera_yes_btn.setVisible(False)
        self.camera_no_btn.setVisible(False)
        camera_result_panel = QWidget()
        camera_result_layout = QVBoxLayout(camera_result_panel)
        camera_result_layout.setContentsMargins(0, 0, 0, 0)
        camera_result_layout.setSpacing(8)
        camera_result_layout.addWidget(self.camera_result)
        camera_btn_row = QHBoxLayout()
        camera_btn_row.addWidget(self.camera_yes_btn)
        camera_btn_row.addWidget(self.camera_no_btn)
        camera_result_layout.addLayout(camera_btn_row)

        # 图片识别结果
        self.upload_result = QTextEdit()
        self.upload_result.setObjectName("resultBox")
        self.upload_result.setReadOnly(True)

        content.addWidget(self.camera_label,0,0)
        content.addWidget(self.upload_label,0,1)

        content.addWidget(camera_result_panel,1,0)
        content.addWidget(self.upload_result,1,1)

        content_root.addLayout(title_row)
        content_root.addLayout(content)

        main_layout.addLayout(sidebar,1)
        main_layout.addLayout(content_root,4)

        main_widget.setLayout(main_layout)

        self.setStyleSheet("""
        QWidget{
            background:#f5f6f7;
            color:#2f343a;
            font-size:13px;
        }

        QPushButton{
            background:#ffffff;
            border:1px solid #c9cdd2;
            border-radius:12px;
            padding:10px 12px;
            color:#2f343a;
            font-weight:700;
        }

        QPushButton:hover{
            background:#eef1f4;
            border:1px solid #b7bdc5;
        }

        QPushButton:pressed{
            background:#e1e5ea;
        }

        QPushButton#confirmYesBtn{
            background:#2f855a;
            border:1px solid #38a169;
            color:#ffffff;
            font-size:15px;
            font-weight:700;
            min-height:36px;
        }
        QPushButton#confirmYesBtn:hover{
            background:#2b6f4d;
            border:1px solid #2f855a;
        }
        QPushButton#confirmYesBtn:pressed{
            background:#22543d;
        }

        QPushButton#confirmNoBtn{
            background:#9b2c2c;
            border:1px solid #c53030;
            color:#ffffff;
            font-size:15px;
            font-weight:700;
            min-height:36px;
        }
        QPushButton#confirmNoBtn:hover{
            background:#822727;
            border:1px solid #9b2c2c;
        }
        QPushButton#confirmNoBtn:pressed{
            background:#63171b;
        }

        QLabel#previewLabel{
            background:#ffffff;
            border:2px solid #c2c7cf;
            border-radius:14px;
        }

        QTextEdit#resultBox{
            background:#ffffff;
            border:1px solid #c9cdd2;
            border-radius:12px;
            padding:8px;
            color:#2f343a;
        }

        QLabel#heroTitle{
            font-size:22px;
            font-weight:700;
            color:#2f343a;
            padding:4px 2px;
        }

        QLabel#heroBadges{
            font-size:22px;
            color:#5d6670;
            padding:4px 10px;
            background:#eceff3;
            border:1px solid #c6ccd4;
            border-radius:12px;
        }

        QGroupBox{
            border:2px solid #c9cdd2;
            border-radius:12px;
            margin-top:8px;
            padding-top:12px;
            color:#2f343a;
            font-weight:700;
            background:#ffffff;
        }
        QGroupBox::title{
            subcontrol-origin: margin;
            left:10px;
            padding:0 6px;
            color:#2f343a;
            background:#f5f6f7;
        }

        QDialog{
            background:#f5f6f7;
            color:#2f343a;
        }

        QLineEdit, QComboBox, QTextEdit, QListWidget{
            background:#ffffff;
            border:1px solid #c9cdd2;
            border-radius:10px;
            padding:6px;
        }

        QListWidget::item{
            padding:6px;
            border-radius:8px;
        }

        QListWidget::item:selected{
            background:#e7ebf0;
            color:#2f343a;
        }

        QMessageBox{
            background:#f5f6f7;
        }

        QMessageBox QPushButton{
            min-width:86px;
        }
        """)
        self.set_icon_placeholder(self.camera_label, "icons/camera.png", "点击开启摄像头")
        self.set_icon_placeholder(self.upload_label, "icons/upload.png", "点击上传图片")
        self.camera_result.setText(self.format_camera_idle_text())
        self.upload_result.setText("识别结果将在这里显示")
        self.load_sidebar_data()
        self.refresh_history_view()

    def set_icon_placeholder(self, label, icon_path, text):
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path)
            if not pix.isNull():
                label.setPixmap(pix.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        label.setPixmap(QPixmap())
        label.setText(text)

    def set_label_pixmap_center_crop(self, label, pixmap):
        if pixmap.isNull():
            return
        target_w = label.width()
        target_h = label.height()
        scaled = pixmap.scaled(target_w, target_h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = max(0, (scaled.width() - target_w) // 2)
        y = max(0, (scaled.height() - target_h) // 2)
        cropped = scaled.copy(x, y, target_w, target_h)
        label.setText("")
        label.setPixmap(cropped)

    def apply_dialog_style(self, dialog):
        dialog.setStyleSheet("""
        QDialog{
            background:#f5f6f7;
            color:#2f343a;
        }
        QLabel{
            color:#2f343a;
        }
        QLineEdit, QComboBox, QTextEdit, QListWidget{
            background:#ffffff;
            border:1px solid #c9cdd2;
            border-radius:10px;
            padding:6px;
        }
        QPushButton{
            background:#ffffff;
            border:1px solid #c9cdd2;
            border-radius:12px;
            padding:8px 10px;
            color:#2f343a;
            font-weight:700;
        }
        QPushButton:hover{
            background:#eef1f4;
        }
        """)

    def format_result(self, main, conf):
        return f"""
识别结果: {main}
置信度: {conf:.2%}

饲养建议:
1 定期疫苗
2 保持清洁
3 合理饮食
"""

    def format_camera_processing_text(self):
        paws = "🐾" * self.paw_count
        return f"""
识别中 {paws}

温馨提示：请稳定拍摄设备，在画面中央对准识别目标
"""

    def format_camera_idle_text(self):
        return """
点击开启摄像头后开始识别
"""

    def format_camera_confirm_text(self, main, conf):
        return f"""
识别结果: {main}
置信度: {conf:.2%}

饲养建议:
1 定期疫苗
2 保持清洁
3 合理饮食

请确认是否记录该结果：
- Yes：写入识别记录
- Not：刷新实时识别并重新捕捉
"""

    def advance_paw_count(self):
        self.paw_count = (self.paw_count + 1) % 6

    def add_history_record(self, source, label, conf):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        add_recognition_record(source, label, conf, ts)
        self.refresh_history_view()

    def refresh_history_view(self):
        self.history_list.clear()
        rows = get_recognition_records(500)
        if not rows:
            self.history_list.addItem("暂无识别记录")
            return
        for row in rows:
            line1 = f"{row[0]}  [{row[1]}]"
            line2 = f"结果: {row[2]}    置信度: {row[3]:.2%}"
            item = QListWidgetItem(f"{line1}\n{line2}")
            item.setSizeHint(QSize(item.sizeHint().width(), 44))
            self.history_list.addItem(item)

    def load_sidebar_data(self):
        profiles = list_pet_profiles()
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        for p in profiles:
            self.profile_selector.addItem(p["pet_name"], p["id"])
        self.profile_selector.blockSignals(False)

        if profiles:
            valid_ids = {p["id"] for p in profiles}
            if self.current_profile_id not in valid_ids:
                self.current_profile_id = profiles[0]["id"]
            idx = next((i for i, p in enumerate(profiles) if p["id"] == self.current_profile_id), 0)
            self.profile_selector.setCurrentIndex(idx)
            selected = get_pet_profile_by_id(self.current_profile_id) or profiles[0]
            self.profile_name_label.setText(f"当前宠物：{selected['pet_name']}")
            self.profile_type_label.setText(f"类型：{selected['pet_type']} / {selected['pet_stage']}")
            self.profile_note_label.setText(f"备注：{selected['note']}")
        else:
            self.current_profile_id = None
            self.profile_name_label.setText("当前宠物：")
            self.profile_type_label.setText("类型：")
            self.profile_note_label.setText("备注：")

        for cb in self.reminder_checkboxes:
            self.reminder_layout.removeWidget(cb)
            cb.deleteLater()
        self.reminder_checkboxes = []
        reminders = get_daily_reminders()
        for rid, title, is_done in reminders:
            cb = QCheckBox(title)
            cb.setChecked(bool(is_done))
            cb.stateChanged.connect(lambda state, reminder_id=rid: self.on_reminder_toggled(reminder_id, state))
            self.reminder_layout.addWidget(cb)
            self.reminder_checkboxes.append(cb)

        events = get_health_events()
        today = date.today()
        if len(events) > 0:
            d1 = datetime.strptime(events[0][1], "%Y-%m-%d").date()
            self.health_line_1.setText(f"{events[0][0]}：{(d1 - today).days} 天后")
        else:
            self.health_line_1.setText("疫苗复查：未设置")
        if len(events) > 1:
            d2 = datetime.strptime(events[1][1], "%Y-%m-%d").date()
            self.health_line_2.setText(f"{events[1][0]}：{(d2 - today).days} 天后")
        else:
            self.health_line_2.setText("体内驱虫：未设置")
        self.health_today.setText(f"今日：{today.isoformat()}")

    def on_reminder_toggled(self, reminder_id, state):
        update_daily_reminder(reminder_id, state == Qt.Checked)

    def on_profile_changed(self, index):
        if index < 0:
            return
        profile_id = self.profile_selector.itemData(index)
        if profile_id is None:
            return
        self.current_profile_id = int(profile_id)
        profile = get_pet_profile_by_id(self.current_profile_id)
        if profile:
            self.profile_name_label.setText(f"当前宠物：{profile['pet_name']}")
            self.profile_type_label.setText(f"类型：{profile['pet_type']} / {profile['pet_stage']}")
            self.profile_note_label.setText(f"备注：{profile['note']}")

    def open_profile_creator(self):
        self.open_profile_editor_impl(create_new=True)

    def open_profile_editor(self):
        self.open_profile_editor_impl(False)

    def open_profile_editor_impl(self, create_new=False):
        data = {"pet_name": "", "pet_type": "", "pet_stage": "", "note": ""}
        if not create_new and self.current_profile_id is not None:
            db_data = get_pet_profile_by_id(self.current_profile_id)
            if db_data:
                data = db_data
        dialog = QDialog(self)
        dialog.setWindowTitle("新增宠物档案" if create_new else "编辑我的宠物档案")
        dialog.resize(460, 420)
        self.apply_dialog_style(dialog)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name = QLineEdit(data["pet_name"])
        pet_type = QLineEdit(data["pet_type"])
        stage = QLineEdit(data["pet_stage"])
        note = QTextEdit(data["note"])
        note.setFixedHeight(160)
        form.addRow("宠物名", name)
        form.addRow("类型", pet_type)
        form.addRow("阶段", stage)
        form.addRow("备注", note)
        save_btn = QPushButton("新增档案" if create_new else "保存档案")

        def save_profile():
            pet_name = name.text().strip()
            if not pet_name:
                QMessageBox.warning(dialog, "提示", "请填写宠物名")
                return
            if create_new:
                new_id = create_pet_profile(
                    pet_name,
                    pet_type.text().strip(),
                    stage.text().strip(),
                    note.toPlainText().strip()
                )
                self.current_profile_id = new_id
            elif self.current_profile_id is not None:
                update_pet_profile_by_id(
                    self.current_profile_id,
                    pet_name,
                    pet_type.text().strip(),
                    stage.text().strip(),
                    note.toPlainText().strip()
                )
            self.load_sidebar_data()
            dialog.accept()

        save_btn.clicked.connect(save_profile)
        layout.addLayout(form)
        layout.addWidget(save_btn)
        dialog.exec_()

    def open_health_editor(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑健康日历")
        dialog.resize(460, 260)
        self.apply_dialog_style(dialog)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        vaccine_date = QDateEdit()
        deworm_date = QDateEdit()
        vaccine_date.setCalendarPopup(True)
        deworm_date.setCalendarPopup(True)
        vaccine_date.setDate(QDate.currentDate().addDays(12))
        deworm_date.setDate(QDate.currentDate().addDays(5))
        for item_name, due_date in get_health_events():
            if item_name == "疫苗复查":
                vaccine_date.setDate(QDate.fromString(due_date, "yyyy-MM-dd"))
            if item_name == "体内驱虫":
                deworm_date.setDate(QDate.fromString(due_date, "yyyy-MM-dd"))
        form.addRow("疫苗复查日期", vaccine_date)
        form.addRow("体内驱虫日期", deworm_date)
        save_btn = QPushButton("保存日历")

        def save_health():
            upsert_health_event("疫苗复查", vaccine_date.date().toString("yyyy-MM-dd"))
            upsert_health_event("体内驱虫", deworm_date.date().toString("yyyy-MM-dd"))
            self.load_sidebar_data()
            dialog.accept()

        save_btn.clicked.connect(save_health)
        layout.addLayout(form)
        layout.addWidget(save_btn)
        dialog.exec_()

    def format_low_conf_camera_result(self, conf):
        tip = random.choice(self.low_conf_camera_tips)
        return f"""
识别结果: 未稳定识别
置信度: {conf:.2%}

提示: {tip}
"""

    def format_low_conf_upload_result(self, conf):
        return f"""
识别结果: 未检测到可靠目标
置信度: {conf:.2%}

提示: 请更换识别文件
"""

    def set_camera_pending_confirmation(self, main, conf):
        self.awaiting_camera_confirm = True
        self.pending_camera_main = main
        self.pending_camera_conf = conf
        self.camera_result.setText(self.format_camera_confirm_text(main, conf))
        self.camera_yes_btn.setVisible(True)
        self.camera_no_btn.setVisible(True)

    def on_camera_confirm_yes(self):
        if not self.awaiting_camera_confirm:
            return
        self.add_history_record("实时识别", self.pending_camera_main, self.pending_camera_conf)
        self.camera_result.setText(self.format_result(self.pending_camera_main, self.pending_camera_conf))
        self.awaiting_camera_confirm = False
        self.camera_yes_btn.setVisible(False)
        self.camera_no_btn.setVisible(False)

    def on_camera_confirm_no(self):
        self.awaiting_camera_confirm = False
        self.pending_camera_main = ""
        self.pending_camera_conf = 0.0
        self.last_realtime_label = "???"
        self.paw_count = 0
        self.camera_yes_btn.setVisible(False)
        self.camera_no_btn.setVisible(False)
        self.camera_result.setText(self.format_camera_processing_text())

    def english_label(self, label):
        text = str(label or "").strip()
        if "_" in text:
            return text.split("_")[-1]
        if "-" in text:
            return text.split("-")[-1]
        return text

    def toggle_camera(self):

        if not self.running:

            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                QMessageBox.warning(self, "提示", "摄像头无法打开")
                self.cap = None
                return
            self.paw_count = 0
            self.last_realtime_label = "???"
            self.last_realtime_conf = 0.0
            self.awaiting_camera_confirm = False
            self.camera_yes_btn.setVisible(False)
            self.camera_no_btn.setVisible(False)
            self.camera_result.setText("摄像头已开启，正在捕捉识别目标")
            self.timer.start(30)
            self.running = True

        else:

            self.timer.stop()
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            self.running = False
            self.awaiting_camera_confirm = False
            self.camera_yes_btn.setVisible(False)
            self.camera_no_btn.setVisible(False)
            self.set_icon_placeholder(self.camera_label, "icons/camera.png", "点击开启摄像头")


    def update_frame(self):
        if self.cap is None:
            return

        ret,frame = self.cap.read()

        if not ret:
            return

        self.frame_count += 1

        if self.frame_count % 5 == 0 and not self.awaiting_camera_confirm:

            img = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img)

            main,conf,breed,bconf = predict(pil_img)
            self.last_realtime_conf = conf
            if conf >= 0.7:
                self.last_realtime_label = self.english_label(main)
                self.set_camera_pending_confirmation(main, conf)
            else:
                self.last_realtime_label = "???"
                self.advance_paw_count()
                self.camera_result.setText(self.format_camera_processing_text())

        cv2.putText(
            frame,
            self.last_realtime_label,
            (20, 36),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0),
            2
        )

        rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

        h,w,ch = rgb.shape
        bytes_per_line = ch * w

        qt_img = QImage(rgb.data,w,h,bytes_per_line,QImage.Format_RGB888)

        pix = QPixmap.fromImage(qt_img)
        self.set_label_pixmap_center_crop(self.camera_label, pix)


    def upload_image(self):

        file,_ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "Images (*.jpg *.png)"
        )

        if not file:
            return

        self.current_upload_path = file
        pix = QPixmap(file)
        self.set_label_pixmap_center_crop(self.upload_label, pix)

        img = Image.open(file)

        main,conf,breed,bconf = predict(img)
        self.add_history_record("上传识别", main if conf >= 0.7 else "未识别", conf)
        if conf < 0.7:
            self.upload_result.setText(self.format_low_conf_upload_result(conf))
        else:
            self.upload_result.setText(self.format_result(main, conf))

    def reset_home(self):
        if self.running:
            self.toggle_camera()
        self.paw_count = 0
        self.awaiting_camera_confirm = False
        self.camera_yes_btn.setVisible(False)
        self.camera_no_btn.setVisible(False)
        self.set_icon_placeholder(self.camera_label, "icons/camera.png", "点击开启摄像头")
        self.set_icon_placeholder(self.upload_label, "icons/upload.png", "点击上传图片")
        self.camera_result.setText(self.format_camera_idle_text())
        self.upload_result.setText("识别结果将在这里显示")

    def open_pet_editor(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("宠物百科录入")
        dialog.resize(520, 620)
        self.apply_dialog_style(dialog)

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        category = QComboBox()
        category.addItems(["dogs", "cats", "other"])
        name = QLineEdit()
        scientific = QLineEdit()
        class_name = QLineEdit()
        order_name = QLineEdit()
        family = QLineEdit()
        species = QLineEdit()
        advice = QTextEdit()
        advice.setFixedHeight(120)
        image_path = QLineEdit()
        image_path.setReadOnly(True)
        choose_btn = QPushButton("选择图片")

        def choose_image():
            file, _ = QFileDialog.getOpenFileName(dialog, "选择宠物图片", "", "Images (*.jpg *.jpeg *.png *.webp)")
            if file:
                image_path.setText(file)

        choose_btn.clicked.connect(choose_image)

        form.addRow("类别", category)
        form.addRow("名称", name)
        form.addRow("学名", scientific)
        form.addRow("纲", class_name)
        form.addRow("目", order_name)
        form.addRow("科", family)
        form.addRow("种", species)
        form.addRow("饲养建议", advice)

        image_row = QHBoxLayout()
        image_row.addWidget(image_path)
        image_row.addWidget(choose_btn)

        save_btn = QPushButton("保存到宠物百科")

        def save_pet():
            if not name.text().strip() or not image_path.text().strip():
                QMessageBox.warning(dialog, "提示", "请至少填写名称并选择图片")
                return
            pet_id = str(uuid.uuid4())
            save_path = os.path.join(UPLOAD_FOLDER, f"{pet_id}.jpg")
            try:
                Image.open(image_path.text().strip()).convert("RGB").save(save_path)
                insert_pet((
                    pet_id,
                    category.currentText().strip(),
                    name.text().strip(),
                    scientific.text().strip(),
                    class_name.text().strip(),
                    order_name.text().strip(),
                    family.text().strip(),
                    species.text().strip(),
                    advice.toPlainText().strip(),
                    save_path
                ))
                QMessageBox.information(dialog, "成功", "已保存到宠物百科")
                dialog.accept()
            except Exception as e:
                QMessageBox.warning(dialog, "失败", f"保存失败: {e}")

        save_btn.clicked.connect(save_pet)

        layout.addLayout(form)
        layout.addLayout(image_row)
        layout.addWidget(save_btn)
        dialog.exec_()

    def open_pet_book(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("宠物百科")
        dialog.resize(980, 620)
        self.apply_dialog_style(dialog)

        root = QVBoxLayout(dialog)

        toolbar = QHBoxLayout()
        category = QComboBox()
        category.addItems(["all", "dogs", "cats", "other"])
        keyword = QLineEdit()
        keyword.setPlaceholderText("输入关键字搜索名称/学名/科/种")
        btn_search = QPushButton("查询")
        btn_refresh = QPushButton("刷新")
        btn_add = QPushButton("新增宠物")
        toolbar.addWidget(QLabel("类别"))
        toolbar.addWidget(category)
        toolbar.addWidget(keyword)
        toolbar.addWidget(btn_search)
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_add)

        body = QHBoxLayout()
        list_widget = QListWidget()
        list_widget.setMinimumWidth(360)

        detail_layout = QVBoxLayout()
        image_label = QLabel()
        image_label.setFixedSize(480, 280)
        image_label.setAlignment(Qt.AlignCenter)
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        detail_layout.addWidget(image_label)
        detail_layout.addWidget(info_text)

        body.addWidget(list_widget, 2)
        body.addLayout(detail_layout, 3)

        root.addLayout(toolbar)
        root.addLayout(body)

        def load_rows():
            cat = category.currentText().strip()
            kw = keyword.text().strip()
            if kw:
                rows = search_pets(kw)
            elif cat == "all":
                rows = get_pets_by_category("dogs") + get_pets_by_category("cats") + get_pets_by_category("other")
            else:
                rows = get_pets_by_category(cat)
            list_widget.clear()
            for row in rows:
                title = f"[{row[1]}] {row[2]}"
                item = QListWidgetItem(title)
                item.setData(Qt.UserRole, row)
                list_widget.addItem(item)
            if list_widget.count() == 0:
                image_label.setPixmap(QPixmap())
                image_label.setText("暂无数据")
                info_text.setText("当前没有匹配的宠物数据")
            else:
                list_widget.setCurrentRow(0)

        def show_item(item):
            if item is None:
                return
            row = item.data(Qt.UserRole)
            image_path = row[9]
            if isinstance(image_path, str) and os.path.exists(image_path):
                pix = QPixmap(image_path)
                self.set_label_pixmap_center_crop(image_label, pix)
            else:
                image_label.setPixmap(QPixmap())
                image_label.setText("图片缺失")
            info_text.setText(
                f"类别: {row[1]}\n"
                f"名称: {row[2]}\n"
                f"学名: {row[3]}\n"
                f"纲: {row[4]}\n"
                f"目: {row[5]}\n"
                f"科: {row[6]}\n"
                f"种: {row[7]}\n\n"
                f"饲养建议:\n{row[8]}"
            )

        btn_search.clicked.connect(load_rows)
        btn_refresh.clicked.connect(load_rows)
        category.currentIndexChanged.connect(load_rows)
        list_widget.currentItemChanged.connect(lambda cur, prev: show_item(cur))
        btn_add.clicked.connect(self.open_pet_editor)

        load_rows()
        dialog.exec_()


if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = PetSystem()
    window.show()

    sys.exit(app.exec_())
