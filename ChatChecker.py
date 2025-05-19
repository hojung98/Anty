import requests
import json
import sys
import re
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser, QFileDialog
from PySide6.QtCore import QThread, Signal


class ChatFetcherThread(QThread):
    chat_fetched = Signal(list, str)

    def __init__(self, video_id, target_nickname):
        super().__init__()
        self.video_id = video_id
        self.target_nickname = target_nickname
        self.seen_messages = set()

    def run(self):
        API_URL = f"https://api.chzzk.naver.com/service/v1/videos/{self.video_id}/chats"

        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
            "Referer": f"https://chzzk.naver.com/video/{self.video_id}"
        }

        START_TIME = 0
        END_TIME = 400000
        STEP = 40000

        filtered_chats = []

        for playerMessageTime in range(START_TIME, END_TIME, STEP):
            params = {"playerMessageTime": str(playerMessageTime)}
            response = requests.get(API_URL, headers=headers, params=params)

            if response.status_code == 200:
                chat_data = response.json()
                video_chats = chat_data.get("content", {}).get("videoChats", [])

                if not video_chats:
                    continue

                for chat in video_chats:
                    profile_str = chat.get("profile")
                    message_time = chat.get("playerMessageTime", 0)

                    if profile_str:
                        profile_data = json.loads(profile_str)
                        chat_nickname = profile_data.get("nickname", "Unknown")
                    else:
                        chat_nickname = "Unknown"

                    message = chat.get("content", "")

                    if chat_nickname == self.target_nickname:
                        if message_time not in self.seen_messages:
                            formatted_chat = f'{self.format_time(message_time)} - {chat_nickname}: {message}'
                            filtered_chats.append(formatted_chat)
                            self.seen_messages.add(message_time)

            else:
                self.chat_fetched.emit([], f"🚨 요청 실패! HTTP 상태 코드: {response.status_code}")
                return

        self.chat_fetched.emit(filtered_chats, None)

    def format_time(self, milliseconds):
        """밀리초를 hh:mm:ss 형식으로 변환하고 링크로 감싸 반환"""
        total_seconds = milliseconds // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        time_str = f"{hours:02}:{minutes:02}:{seconds:02}"
        video_url = f"https://chzzk.naver.com/video/{self.video_id}?t={total_seconds}"
        return f'<a href="{video_url}">{time_str}</a>'


class ChatFetcherApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("치지직 채팅 수집기")
        self.setGeometry(100, 100, 500, 600)

        layout = QVBoxLayout()
        self.id_label = QLabel("영상 ID를 입력하세요:")
        layout.addWidget(self.id_label)

        self.video_id_input = QLineEdit()
        layout.addWidget(self.video_id_input)

        self.label = QLabel("채팅을 수집할 닉네임을 입력하세요:")
        layout.addWidget(self.label)

        self.nickname_input = QLineEdit()
        layout.addWidget(self.nickname_input)

        self.fetch_button = QPushButton("채팅 가져오기")
        self.fetch_button.clicked.connect(self.start_fetching)
        layout.addWidget(self.fetch_button)

        self.chat_display = QTextBrowser()
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        self.save_button = QPushButton("파일로 저장")
        self.save_button.clicked.connect(self.save_to_file)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

    def start_fetching(self):
        raw_video_id = self.video_id_input.text().strip()
        nickname = self.nickname_input.text().strip()

        # video_id가 URL이면 숫자만 추출
        match = re.search(r'/video/(\d+)', raw_video_id)
        video_id = match.group(1) if match else raw_video_id

        if not video_id.isdigit() or not nickname:
            self.chat_display.setText("❌ 영상 ID(또는 URL)와 닉네임을 모두 입력하세요.")
            return

        self.chat_display.setText(f"🔍 영상 ID: {video_id} / 닉네임: '{nickname}'의 채팅 검색 중...\n")
        self.fetch_button.setEnabled(False)

        self.thread = ChatFetcherThread(video_id, nickname)
        self.thread.chat_fetched.connect(self.display_chats)
        self.thread.start()

    def display_chats(self, chats, error_message):
        self.fetch_button.setEnabled(True)

        if error_message:
            self.chat_display.setText(error_message)
            return

        if chats:
            html_text = f"<b>✅ '{self.nickname_input.text()}'의 전체 채팅 내역:</b><br>" + "<br>".join(chats)
            self.chat_display.setHtml(html_text)
        else:
            self.chat_display.setText("\n🚨 해당 닉네임의 채팅 없음.")

        self.filtered_chats = chats

    def save_to_file(self):
        if not hasattr(self, 'filtered_chats') or not self.filtered_chats:
            self.chat_display.append("\n❌ 저장할 채팅 데이터가 없습니다.")
            return

        file_name, _ = QFileDialog.getSaveFileName(self, "파일 저장", "chat_log.txt", "Text Files (*.txt);;All Files (*)")
        if file_name:
            with open(file_name, "w", encoding="utf-8") as file:
                # HTML 태그 제거 후 저장
                for line in self.filtered_chats:
                    plain_text = line.replace('<a href="', '').replace('">', ' ').replace('</a>', '')
                    file.write(plain_text + "\n")
            self.chat_display.append("\n✅ 채팅 데이터가 저장되었습니다!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatFetcherApp()
    window.show()
    sys.exit(app.exec())
