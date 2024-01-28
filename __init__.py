import os
import subprocess

from PySide6.QtWidgets import QApplication, QWidget, QFileDialog, QSizePolicy
from PySide6 import QtWidgets, QtCore, QtGui
import qdarkstyle
import logging
from ffmpeg import FFmpeg, Progress

# Only needed for access to command line arguments
import sys

class QTextEditLogger(logging.StreamHandler):
    def __init__(self, parent):
        super().__init__()
        self.widget = QtWidgets.QPlainTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.setPlainText(msg)
        QApplication.processEvents()

# Create a Qt widget, which will be our window.
class VideoCompressor(QWidget):
    def __init__(self):
        super().__init__()

        self.log_widget = QTextEditLogger(self)
        self.log_widget.setFormatter(logging.Formatter('%(message)s'))
        self.log_widget.widget.setMaximumHeight(100)
        logging.getLogger().addHandler(self.log_widget)
        logging.getLogger().setLevel(logging.DEBUG)

        self.setWindowTitle("Video Compressor")
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        self.files=[]

        self.select_folder_btn = QtWidgets.QPushButton("Select Folder")
        self.select_folder_btn.clicked.connect(self.select_folder)
        self.list_widget = QtWidgets.QListWidget()

        compress_layout = QtWidgets.QHBoxLayout()

        self.skip_existing = QtWidgets.QCheckBox("Skip Existing")
        self.skip_existing.setChecked(True)
        self.skip_existing.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        self.compress_btn = QtWidgets.QPushButton("Compress")
        self.compress_btn.clicked.connect(self.compress_videos)
        compress_layout.addWidget(self.compress_btn)
        compress_layout.addWidget(self.skip_existing)

        self.layout.addWidget(self.select_folder_btn)
        self.layout.addWidget(self.list_widget)
        self.layout.addLayout(compress_layout)
        self.layout.addWidget(self.log_widget.widget)

    def select_folder(self):
        self.files=[]
        # Remove items
        for i in range(self.list_widget.count()):
            self.list_widget.takeItem(0)
            
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        if dialog.exec() == QFileDialog.Accepted:
            selected_folder = dialog.selectedFiles()[0]

            self.files = [f for f in os.listdir(selected_folder) if f.endswith((".mp4",".wmv"))]
        
            logging.info("Founds %s files." % len(self.files))

            logger = logging.getLogger()
            for file in self.files:
                item = self.FileItem(file,selected_folder)
                item.setText(file)
                self.list_widget.addItem(item)
    
    def compress_videos(self):
        
        items = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            items.append(item.get_paths())
        
        self.thread = self.ProcessVideos(self)
        self.thread.output.connect(self.log_widget.widget.setPlainText)
        self.thread.start()

    def message_box(self, title, content):
        dialog = QtWidgets.QMessageBox(self)        
        dialog.setWindowTitle(title)
        dialog.setText(content)
        dialog.exec()
    
    class ProcessVideos(QtCore.QThread):
        
        output = QtCore.Signal(str)

        def __init__(self, app):
            super().__init__()
            self.app = app

        def run(self):            
            self.app.compress_btn.setEnabled(False)
            self.app.select_folder_btn.setEnabled(False)

            total = self.app.list_widget.count()
            for i in range(total):
                item = self.app.list_widget.item(i)
                video_path, compressed_path, file = item.get_paths()
                item.setBackground(QtGui.QColor("yellow"))

                if self.app.skip_existing.isChecked() and os.path.exists(compressed_path):
                    pass
                else:
                    # Get the creation time of the input file
                    creation_time = subprocess.check_output(['powershell', '-command', f'(Get-Item "{video_path}").CreationTime']).decode().strip()
                    self.output.emit(f"Creation time is {creation_time}")
                    
                    os.makedirs(os.path.dirname(compressed_path), exist_ok=True)

                    ffmpeg= (
                        FFmpeg()
                            .option('y')
                            .input(video_path)
                            .output(compressed_path)

                    )

                    @ffmpeg.on("progress")
                    def on_progress(progress: Progress):
                            self.output.emit(f"File {i+1}/{total}\n{str(progress)}")

                    ffmpeg.execute()

                    # Set the creation time
                    subprocess.run(f"powershell -command (Get-Item '{compressed_path}').CreationTime='{creation_time}'")
                item.setBackground(QtGui.QColor("green"))

            self.output.emit("Complete!")

            self.app.select_folder_btn.setEnabled(True)
            self.app.compress_btn.setEnabled(True)

    class FileItem(QtWidgets.QListWidgetItem):
        def __init__(self, file, path):
            super().__init__()
            self.file = file
            self.path = path
        
        def get_paths(self):
            video_path = os.path.join(self.path,self.file)
            compressed_path = os.path.join(self.path,"compressed",self.file)
            file = self.file
            return (video_path, compressed_path, file)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet())
    window = VideoCompressor()
    window.show()
    # Start the event loop.
    sys.exit(app.exec())


    # Your application won't reach here until you exit and the event
    # loop has stopped.

#Convert string to