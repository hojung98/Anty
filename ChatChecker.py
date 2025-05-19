import requests
import json
import sys
import re
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser, QFileDialog
from PySide6.QtCore import QThread, Signal


class ChatFetcherThread(QThread):
    chat_fetched = Signal(list, str)  # 기존 전체 전송용
    chat_progress = Signal(str)       # 🔥 실시간 채팅 전송용 추가

    def __init__(self, video_id, nickname_filter, message_filter):
        super().__init__()
        self.video_id = video_id
        self.seen_messages = set()
        self.nickname_filter = nickname_filter
        self.message_filter = message_filter

    def run(self):
        API_URL = f"https://api.chzzk.naver.com/service/v1/videos/{self.video_id}/chats"

        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
            "Referer": f"https://chzzk.naver.com/video/{self.video_id}"
        }

        current_time = 0
        filtered_chats = []

        print("🚀 [시작] 채팅 수집 시작됨")

        while True:
            print(f"📡 [요청] playerMessageTime={current_time}")
            params = {"playerMessageTime": str(current_time)}
            response = requests.get(API_URL, headers=headers, params=params)

            if response.status_code != 200:
                print(f"❌ [에러] HTTP 상태 코드: {response.status_code}")
                self.chat_fetched.emit([], f"🚨 요청 실패! HTTP 상태 코드: {response.status_code}")
                return

            chat_data = response.json()
            video_chats = chat_data.get("content", {}).get("videoChats", [])
            print(f"📥 [응답] 채팅 수: {len(video_chats)}")

            if not video_chats:
                print("✅ [완료] 더 이상 가져올 채팅이 없습니다. 수집 종료.")
                break

            for chat in video_chats:
                profile_str = chat.get("profile")
                message_time = chat.get("playerMessageTime", 0)

                profile_data = {}
                if profile_str:
                    try:
                        loaded = json.loads(profile_str)
                        if isinstance(loaded, dict):  # ✅ 이게 중요
                            profile_data = loaded
                        else:
                            print(f"⚠️ [무시됨] profile_str가 dict가 아님: {profile_str}")
                    except json.JSONDecodeError:
                        print(f"⚠️ [파싱 실패] profile_str: {profile_str}")

                chat_nickname = profile_data.get("nickname", "Unknown")
                message = chat.get("content", "")

                nickname_match = not self.nickname_filter or chat_nickname == self.nickname_filter
                message_match = not self.message_filter or self.message_filter in message

                if nickname_match and message_match and message_time not in self.seen_messages:
                    formatted_chat = f'{self.format_time(message_time)} - {chat_nickname}: {message}'
                    filtered_chats.append(formatted_chat)
                    self.seen_messages.add(message_time)
                    print(f"💬 [채팅] {formatted_chat}")
                    self.chat_progress.emit(formatted_chat)   # ✅ 실시간 전송

            current_time = video_chats[-1]["playerMessageTime"] + 1

        print(f"📦 [결과] 총 수집된 채팅 수: {len(filtered_chats)}")
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
        self.id_label = QLabel("치지직 다시보기 URL을 입력해주세요!")
        layout.addWidget(self.id_label)

        self.video_id_input = QLineEdit()
        layout.addWidget(self.video_id_input)

        self.nickname_label = QLabel("닉네임 필터 (선택 사항)")
        layout.addWidget(self.nickname_label)
        self.nickname_input = QLineEdit()
        layout.addWidget(self.nickname_input)

        self.message_label = QLabel("채팅 내용 필터 (선택 사항)")
        layout.addWidget(self.message_label)
        self.message_input = QLineEdit()
        layout.addWidget(self.message_input)

        self.fetch_button = QPushButton("채팅 가져오기")
        self.fetch_button.clicked.connect(self.start_fetching)
        layout.addWidget(self.fetch_button)

        self.chat_display = QTextBrowser()
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        self.save_button = QPushButton("파일로 저장하기")
        self.save_button.clicked.connect(self.save_to_file)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

    def toggle_mode(self):
        if self.search_mode == "nickname":
            self.search_mode = "message"
            self.mode_button.setText("💬 채팅내용으로 검색 중 (클릭하여 전환)")
            self.label.setText("검색할 채팅 내용을 입력해주세요!")
        else:
            self.search_mode = "nickname"
            self.mode_button.setText("🔍 닉네임으로 검색 중 (클릭하여 전환)")
            self.label.setText("채팅을 수집할 닉네임을 입력해주세요!")

    def start_fetching(self):
        raw_video_id = self.video_id_input.text().strip()
        nickname = self.nickname_input.text().strip()
        message = self.message_input.text().strip()

        # video_id가 URL이면 숫자만 추출
        match = re.search(r'/video/(\d+)', raw_video_id)
        video_id = match.group(1) if match else raw_video_id

        if not video_id.isdigit():
            self.chat_display.setText("❌ 영상 URL을 입력해주셔야해요!")
            return

        if not nickname and not message:
            self.chat_display.setText("❌ 닉네임 또는 채팅 내용을 하나 이상 입력해야 해요!")
            return

        self.chat_display.setText(f"🔍 영상 ID: {video_id} / 닉네임: '{nickname}'의 채팅 검색 중...\n")
        self.fetch_button.setEnabled(False)

        self.thread = ChatFetcherThread(video_id, nickname, message)
        self.thread.chat_fetched.connect(self.display_chats)
        self.thread.chat_progress.connect(self.append_chat)  # ✅ 실시간 업데이트 연결

        self.thread.start()

    def append_chat(self, chat_line):
        self.chat_display.append(chat_line)   # ✅ 실시간으로 한 줄씩 추가

    def display_chats(self, chats, error_message):
        self.fetch_button.setEnabled(True)

        if error_message:
            self.chat_display.setText(error_message)
            return

        if chats:
            html_text = f"<b>✅ 전체 채팅 내역!!" + "<br>".join(chats)
            self.chat_display.setHtml(html_text)
        else:
            self.chat_display.setText("\n🚨 해당 닉네임의 채팅을 찾을 수 없어요 ㅠ")

        self.filtered_chats = chats

    def save_to_file(self):
        if not hasattr(self, 'filtered_chats') or not self.filtered_chats:
            self.chat_display.append("\n❌ 저장할 채팅 데이터가 없네용")
            return

        file_name, _ = QFileDialog.getSaveFileName(self, "파일 저장", "chat_log.txt", "Text Files (*.txt);;All Files (*)")
        if file_name:
            with open(file_name, "w", encoding="utf-8") as file:
                # HTML 태그 제거 후 저장
                for line in self.filtered_chats:
                    plain_text = line.replace('<a href="', '').replace('">', ' ').replace('</a>', '')
                    file.write(plain_text + "\n")
            self.chat_display.append("\n✅ 채팅 데이터가 저장되었어요!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatFetcherApp()
    window.show()
    sys.exit(app.exec())
