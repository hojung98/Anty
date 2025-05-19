import requests
import json
import sys
import re
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser, QFileDialog, QScrollArea, QCheckBox, QMessageBox, QHBoxLayout, QTextEdit, QTabWidget, QMenu
from PySide6.QtCore import QThread, Signal
from functools import partial
from PySide6.QtGui import QAction, QIcon

class ChatFetcherThread(QThread):
    chat_fetched = Signal(list, str, object)
    chat_progress = Signal(str)
    

    def __init__(self, video_id, nickname_filter, message_filter):
        super().__init__()
        self.video_id = video_id
        self.seen_messages = set()
        self.nickname_filter = nickname_filter
        self.message_filter = message_filter
        self.thread_queue = []
        self.current_thread_index = 0
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        API_URL = f"https://api.chzzk.naver.com/service/v1/videos/{self.video_id}/chats"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
            "Referer": f"https://chzzk.naver.com/video/{self.video_id}"
        }

        current_time = 0
        filtered_chats = []

        print("채팅 수집 시작!")

        while self._is_running:
            print(f"[요청] playerMessageTime={current_time}")
            params = {"playerMessageTime": str(current_time)}
            response = requests.get(API_URL, headers=headers, params=params)

            if response.status_code != 200:
                print(f"!!! HTTP 상태 코드: {response.status_code} !!!")
                self.chat_fetched.emit([], f"!!! 요청 실패! HTTP 상태 코드: {response.status_code} !!!", self.video_id)
                return

            chat_data = response.json()
            video_chats = chat_data.get("content", {}).get("videoChats", [])
            print(f"[응답] 채팅 수: {len(video_chats)}")

            if not video_chats:
                print("[완료] 더 이상 가져올 채팅이 없네요! 수집을 종료할께요!")
                break

            for chat in video_chats:
                if not self._is_running:
                    break

                profile_str = chat.get("profile")
                message_time = chat.get("playerMessageTime", 0)

                profile_data = {}
                if profile_str:
                    try:
                        loaded = json.loads(profile_str)
                        if isinstance(loaded, dict):
                            profile_data = loaded
                        else:
                            print(f"!!! [무시됨] profile_str가 dict가 아님: {profile_str} !!!")
                    except json.JSONDecodeError:
                        print(f"!!! [파싱 실패] profile_str: {profile_str} !!!")

                chat_nickname = profile_data.get("nickname", "Unknown")
                message = chat.get("content", "")

                nickname_match = not self.nickname_filter or chat_nickname == self.nickname_filter
                message_match = not self.message_filter or self.message_filter in message

                if nickname_match and message_match and message_time not in self.seen_messages:
                    formatted_chat = f'{self.format_time(message_time)} - {chat_nickname}: {message}'
                    filtered_chats.append(formatted_chat)
                    self.seen_messages.add(message_time)
                    print(f"[채팅] {formatted_chat}")
                    self.chat_progress.emit(formatted_chat)

            current_time = video_chats[-1]["playerMessageTime"] + 1

        print(f"[결과] 총 수집된 채팅 수는... {len(filtered_chats)}")
        self.chat_fetched.emit(filtered_chats, None, self.video_id)




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

        self.vod_checkboxes = []
        self.vod_data_list = []

        self.setWindowIcon(QIcon("Antys.ico"))
        self.setWindowTitle("Antys")
        self.setGeometry(100, 100, 1000, 600)

        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()


        self.id_label = QLabel("치지직 채널 홈 링크를 입력해주세요!")
        left_layout.addWidget(self.id_label)

        self.channel_url_input = QLineEdit()
        self.channel_url_input.setPlaceholderText("닉네임, 채팅 중 원하시는 하나만 채우면 되셔요! 둘 다 채우셔도 되시구요!")
        left_layout.addWidget(self.channel_url_input)

        self.load_vods_button = QPushButton("VOD 불러오기")
        self.load_vods_button.clicked.connect(self.load_vod_list)
        left_layout.addWidget(self.load_vods_button)

        self.select_all_button = QPushButton("전체 선택 / 해제")
        self.select_all_button.clicked.connect(self.toggle_all_checkboxes)
        left_layout.addWidget(self.select_all_button)

        self.vod_scroll_area = QScrollArea()
        self.vod_list_widget = QWidget()
        self.vod_list_layout = QVBoxLayout()
        self.vod_list_widget.setLayout(self.vod_list_layout)
        self.vod_scroll_area.setWidget(self.vod_list_widget)
        self.vod_scroll_area.setWidgetResizable(True)
        left_layout.addWidget(self.vod_scroll_area, stretch=1)

        self.nickname_label = QLabel("닉네임을 입력해주세요!")
        left_layout.addWidget(self.nickname_label)

        self.nickname_input = QLineEdit()
        self.nickname_input.setPlaceholderText("요기만 입력하시면 입력한 닉네임의 모든 채팅 내역이 불러와져요!")
        left_layout.addWidget(self.nickname_input)

        self.message_label = QLabel("검색하실 채팅 내용을 입력해주세요!")
        left_layout.addWidget(self.message_label)

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("요기만 입력하시면 누가 쳤든 상관 없이 입력한 내용이 포함된 모든 채팅이 불러와져요!")
        left_layout.addWidget(self.message_input)

        self.fetch_button = QPushButton("채팅 가져오기!")
        self.fetch_button.clicked.connect(self.start_fetching)
        left_layout.addWidget(self.fetch_button)

        self.save_button = QPushButton("모든 탭 파일로 저장하기!")
        self.save_button.clicked.connect(self.save_to_file)
        left_layout.addWidget(self.save_button)


        self.chat_tabs = QTabWidget()
        self.chat_tabs.setMinimumWidth(400)
        self.chat_tabs.setTabsClosable(False)

        self.chat_tabs.setTabsClosable(True)
        self.chat_tabs.tabCloseRequested.connect(self.chat_tabs.removeTab)


        self.chat_tabs.setStyleSheet("""
            QTabBar::tab {
                padding-right: 6px;
            }
        """)


        main_layout.addLayout(left_layout, 3)
        main_layout.addWidget(self.chat_tabs, 3)

        self.select_all_warned = False

        self.setLayout(main_layout)



    def start_fetching(self):
        selected_videos = [cb for cb in self.vod_checkboxes if cb.isChecked()]
        if not selected_videos:
            QMessageBox.warning(self, "다시보기 선택 안됨!", "채팅을 가져올 다시보기를 선택해주세요!")
            return

        nickname = self.nickname_input.text().strip()
        message = self.message_input.text().strip()

        if not nickname and not message:
            QMessageBox.warning(self, "하나도 입력 안댐!!", "아무리 그래두 닉네임 또는 채팅 내용 중 하나 이상은 입력해야 해요!")
            return

        QMessageBox.warning(self, "모든 준비 완료!!!", "선택한 영상들의 채팅을 가져올께요!!\n불러와지는 채팅 옆 시간을 누르시면 해당 다시보기로 연결되어요!!")
        self.fetch_button.setEnabled(False)

        self.filtered_chats = []
        self.thread_queue = [
            (cb.video_id, nickname, message)
            for cb in selected_videos
        ]
        self.current_thread_index = 0

        self.start_next_thread()


    def start_next_thread(self):
        if self.current_thread_index >= len(self.thread_queue):
            self.fetch_button.setEnabled(True)
            QMessageBox.information(self, "완료완료!!", "모든 영상의 채팅 수집이 완료되었습니다!")
            return

        video_id, nickname, message = self.thread_queue[self.current_thread_index]
        thread = ChatFetcherThread(video_id, nickname, message)
        thread.chat_fetched.connect(self.handle_thread_finished)
        thread.chat_progress.connect(self.append_chat)

        self.live_tab = QTextBrowser()
        self.live_tab.setOpenExternalLinks(True)

        matching_vod = next((vod for vod in self.vod_data_list if str(vod["videoNo"]) == video_id), None)
        if matching_vod:
            tab_title = f'{matching_vod["publishDate"]} - {matching_vod["videoTitle"]}'
        else:
            tab_title = f'영상 {video_id}'

        self.chat_tabs.addTab(self.live_tab, tab_title)

        self.current_thread = thread
        thread.start()


    def display_chats_per_video(self, chats, error_message, video_id):
        self.fetch_button.setEnabled(True)

        if error_message:
            QMessageBox.information(f"<b>🚨 [{video_id}] 오류:</b> {error_message}<br>")
            return

        if chats:
            count = len(chats)
            html_text = f"<b> [영상 {video_id}] 채팅 내역 ({count}개)</b><br>" + "<br>".join(chats) + "<br><br>"
            QMessageBox.information(html_text)
            self.filtered_chats.extend(chats)
        else:
            QMessageBox.information(f"<b>[영상 {video_id}] 해당 닉네임의 채팅을 찾을 수 없어요 ㅠ</b><br><br>")


    def handle_thread_finished(self, chats, error_message, video_id):
        if not hasattr(self, "live_tab"):
            return

        if error_message:
            self.live_tab.append(f"<b>🚨 [{video_id}] 오류:</b> {error_message}<br>")
        elif chats:
            count = len(chats)
            self.live_tab.append(f"<br><b>✅ [영상 {video_id}] 채팅 내역 ({count}개)</b><br><br>")
        else:
            self.live_tab.append(f"<b>🚨 [영상 {video_id}] 해당 닉네임의 채팅을 찾을 수 없어요 ㅠ</b><br><br>")

        matching_vod = next((vod for vod in self.vod_data_list if str(vod["videoNo"]) == video_id), None)
        if matching_vod:
            tab_title = f'{matching_vod["publishDate"]} - {matching_vod["videoTitle"]}'
        else:
            tab_title = f'영상 {video_id}'

        index = self.chat_tabs.indexOf(self.live_tab)
        if index != -1:
            self.chat_tabs.setTabText(index, tab_title)

        self.filtered_chats.extend(chats)
        self.current_thread_index += 1
        self.start_next_thread()





    def append_chat(self, chat_line):
        if hasattr(self, "live_tab"):
            self.live_tab.append(chat_line)


    def display_chats(self, chats, error_message):
        self.fetch_button.setEnabled(True)

        if error_message:
            QMessageBox.warning(error_message)
            return

        if chats:
            count = len(chats)
            html_text = f"<b>✅ 전체 채팅 내역!! ({count}개)</b><br>" + "<br>".join(chats)
            self.chat_display.setHtml(html_text)
        else:
            QMessageBox.warning(self, "알림", "해당 닉네임의 채팅을 찾을 수 없어요 ㅠ")

        self.filtered_chats = chats

    def save_to_file(self):
        if self.chat_tabs.count() == 0:
            QMessageBox.information(self, "저장 실패", "저장할 채팅 탭이 없어요...")
            return

        file_name, _ = QFileDialog.getSaveFileName(self, "파일 저장", "chat_log.txt", "Text Files (*.txt);;All Files (*)")
        if file_name:
            with open(file_name, "w", encoding="utf-8") as file:
                total_chat_count = 0

                for i in range(self.chat_tabs.count()):
                    tab = self.chat_tabs.widget(i)
                    title = self.chat_tabs.tabText(i)
                    plain_text = tab.toPlainText().strip()

                    lines = plain_text.splitlines()
                    chat_lines = [line.strip() for line in lines if line.strip() and not line.startswith("🚨")]

                    matching_vod = self.vod_data_list[i] if i < len(self.vod_data_list) else None
                    video_url = "https://chzzk.naver.com/"
                    if matching_vod:
                        video_id = matching_vod["videoId"]
                        video_url = f"https://chzzk.naver.com/video/{video_id}"

                    file.write(f"===== {title} =====\n")
                    file.write(f"{video_url}\n")
                    file.write(f"총 채팅 수: {len(chat_lines)}개\n\n")

                    for line in chat_lines:
                        file.write(line + "\n")

                    file.write("\n\n")
                    total_chat_count += len(chat_lines)

            selected_vod_count = self.chat_tabs.count()
            QMessageBox.information(self, "저장 완료", f"총 {selected_vod_count}개의 다시보기 속 {total_chat_count}개의 채팅이 저장되었어요! 짝짝짝")


    def closeEvent(self, event):
        try:
            if hasattr(self, "current_thread") and self.current_thread.isRunning():
                print("스레드 종료 시도 중...")
                self.current_thread.stop()
                self.current_thread.quit()
                self.current_thread.wait()
                print("스레드 정상 종료됨.")
        except Exception as e:
            print(f"스레드 종료 중 오류 발생: {e}")
        event.accept()



    def load_vod_list(self):
        url = self.channel_url_input.text().strip()
        match = re.search(r'/([a-z0-9]{32})$', url)
        if not match:
            QMessageBox.warning(self, "인식 불가!", "인식 가능한 링크가 아니에요!\n팔로우 목록에서 스트리머 분 누르면 나오는 그 페이지의 링크가 필요해요!")
            return

        channel_id = match.group(1)
        print(f"채널 ID 추출됨: {channel_id}")

        self.vod_checkboxes.clear()
        for i in reversed(range(self.vod_list_layout.count())):
            self.vod_list_layout.itemAt(i).widget().setParent(None)

        self.vod_data_list = []
        page = 0

        while True:
            api_url = (
                f"https://api.chzzk.naver.com/service/v1/channels/"
                f"{channel_id}/videos?sortType=LATEST&pagingType=PAGE&page={page}&size=18"
            )

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://chzzk.naver.com/"
            }

            response = requests.get(api_url, headers=headers, timeout=10)

            if response.status_code != 200:
                QMessageBox.critical(self, "에러에러", f"다시보기를 가져오는 데 실패했어요 ㅠㅠㅠ\n옆에 코드를 카페나 다른 방법을 통해 저에게 불러주시면 도와드릴께요 ㅠ \n코드: {response.status_code}")
                return

            data = response.json().get("content", {}).get("data", [])
            if not data:
                break

            self.vod_data_list.extend(data)
            for video in data:
                title = video["videoTitle"]
                date = video["publishDate"].split(" ")[0]
                video_id = video["videoId"]
                checkbox = QCheckBox(f"{date} - {title}")
                checkbox.video_id = str(video["videoNo"])
                self.vod_list_layout.addWidget(checkbox)
                self.vod_checkboxes.append(checkbox)

            page += 1

        QMessageBox.information(self, "있었어요!", f"총 {len(self.vod_checkboxes)}개의 다시보기를 불러왔어용 ㅎㅎ\n채팅을 불러올 다시보기를 선택해주세요!")

    def toggle_all_checkboxes(self):
        if not self.vod_checkboxes:
            return

        if not self.select_all_warned:
            QMessageBox.information(self, "경고!!", "너무 많은 데이터를 상습적으로 불러올 경우 서버에 부하가 가서 네이버가 화를 많이 낼 수 있어요!!")
            self.select_all_warned = True

        if any(not cb.isChecked() for cb in self.vod_checkboxes):
            for cb in self.vod_checkboxes:
                cb.setChecked(True)
        else:
            for cb in self.vod_checkboxes:
                cb.setChecked(False)


class ClosableTabWidget(QTabWidget):
    def __init__(self):
        super().__init__()
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setTabsClosable(False)

    def show_context_menu(self, pos):
        index = self.tabBar().tabAt(pos)
        if index == -1:
            return

        menu = QMenu(self)
        close_action = QAction("이 탭 닫기", self)
        close_action.triggered.connect(lambda: self.removeTab(index))
        menu.addAction(close_action)
        menu.exec(self.mapToGlobal(pos))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatFetcherApp()
    window.show()
    sys.exit(app.exec())