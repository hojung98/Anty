import requests
import json
import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog
from PySide6.QtCore import QThread, Signal


class ChatFetcherThread(QThread):
    chat_fetched = Signal(list, str)  # 채팅 데이터를 메인 스레드로 전달

    def __init__(self, video_id, target_nickname):
        super().__init__()
        self.video_id = video_id
        self.target_nickname = target_nickname
        self.seen_messages = set()  # 여기를 추가하세요

    def run(self):
        API_URL = f"https://api.chzzk.naver.com/service/v1/videos/{self.video_id}/chats"

        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
            "Referer": f"https://chzzk.naver.com/video/{self.video_id}"
        }

        START_TIME = 0
        END_TIME = 55000000
        STEP = 40000

        filtered_chats = []
        seen_messages = set()  # 중복 제거용 집합

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
                            formatted_chat = f"{self.format_time(message_time)} - {chat_nickname}: {message}"
                            filtered_chats.append(formatted_chat)
                            self.seen_messages.add(message_time)


            else:
                self.chat_fetched.emit([], f"🚨 요청 실패! HTTP 상태 코드: {response.status_code}")
                return

        self.chat_fetched.emit(filtered_chats, None)  # 성공적으로 가져오면 메인 스레드에 전달

    def format_time(self, milliseconds):
        """밀리초 단위의 시간을 hh:mm:ss 형식으로 변환"""
        total_seconds = milliseconds // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"


class ChatFetcherApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("치지직 채팅 수집기")
        self.setGeometry(100, 100, 500, 600)

        layout = QVBoxLayout()

        self.label = QLabel("채팅을 수집할 닉네임을 입력하세요:")
        layout.addWidget(self.label)

        self.nickname_input = QLineEdit()
        layout.addWidget(self.nickname_input)

        self.fetch_button = QPushButton("채팅 가져오기")
        self.fetch_button.clicked.connect(self.start_fetching)
        layout.addWidget(self.fetch_button)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        self.save_button = QPushButton("파일로 저장")
        self.save_button.clicked.connect(self.save_to_file)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

    def start_fetching(self):
        nickname = self.nickname_input.text().strip()
        if not nickname:
            self.chat_display.setText("❌ 닉네임을 입력하세요.")
            return

        self.chat_display.setText(f"🔍 '{nickname}'의 채팅을 검색 중...\n")
        self.fetch_button.setEnabled(False)  # 버튼 비활성화

        self.thread = ChatFetcherThread("6200690", nickname)
        self.thread.chat_fetched.connect(self.display_chats)
        self.thread.start()

    def display_chats(self, chats, error_message):
        self.fetch_button.setEnabled(True)  # 버튼 다시 활성화

        if error_message:
            self.chat_display.setText(error_message)
            return

        if chats:
            result_text = f"\n✅ '{self.nickname_input.text()}'의 전체 채팅 내역:\n" + "\n".join(chats)
            self.chat_display.setText(result_text)
        else:
            self.chat_display.setText("\n🚨 해당 닉네임의 채팅 없음.")

        self.filtered_chats = chats  # 저장을 위해 결과 저장

    def save_to_file(self):
        if not hasattr(self, 'filtered_chats') or not self.filtered_chats:
            self.chat_display.append("\n❌ 저장할 채팅 데이터가 없습니다.")
            return

        file_name, _ = QFileDialog.getSaveFileName(self, "파일 저장", "chat_log.txt", "Text Files (*.txt);;All Files (*)")
        if file_name:
            with open(file_name, "w", encoding="utf-8") as file:
                file.write("\n".join(self.filtered_chats))
            self.chat_display.append("\n✅ 채팅 데이터가 저장되었습니다!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatFetcherApp()
    window.show()
    sys.exit(app.exec())
