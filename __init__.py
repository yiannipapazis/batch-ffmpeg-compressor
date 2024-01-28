import os
import subprocess

from PySide6.QtWidgets import QApplication, QWidget, QFileDialog, QSizePolicy
from PySide6 import QtWidgets, QtCore
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
        self.widget.appendPlainText(msg)
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

        select_folder = QtWidgets.QPushButton("Select Folder")
        select_folder.clicked.connect(self.select_folder)
        self.list_widget = QtWidgets.QListWidget()

        compress_layout = QtWidgets.QHBoxLayout()

        bitrate_layout = QtWidgets.QHBoxLayout()
        bitrate_label = QtWidgets.QLabel("Bitrate:")
        bitrate_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.bitrate_widget = QtWidgets.QSpinBox()
        self.bitrate_widget.setMaximum(9999)
        self.bitrate_widget.setValue(3000)
        self.bitrate_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        bitrate_layout.addWidget(bitrate_label)
        bitrate_layout.addWidget(self.bitrate_widget)

        self.skip_existing = QtWidgets.QCheckBox("Skip Existing")
        self.skip_existing.setChecked(False)
        self.skip_existing.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        compress_btn = QtWidgets.QPushButton("Compress")
        compress_btn.clicked.connect(self.compress_videos)
        compress_layout.addLayout(bitrate_layout)
        compress_layout.addWidget(self.skip_existing)

        self.layout.addWidget(select_folder)
        self.layout.addWidget(self.list_widget)
        self.layout.addLayout(compress_layout)
        self.layout.addWidget(compress_btn)
        self.layout.addWidget(self.log_widget.widget)

    def handle_readyReadStandardOutput(self):
        text = self._process.readAllStandardOutput().data().decode()
        logging.debug(text.strip())

    
    def select_folder(self):
        self.files=[]
        # Remove items
        for i in range(self.list_widget.count()):
            self.list_widget.takeItem(0)
            
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        if dialog.exec() == QFileDialog.Accepted:
            selected_folder = dialog.selectedFiles()[0]

            self.files = [f for f in os.listdir(selected_folder) if f.endswith(".mp4")]
        
            logging.info("Founds %s files." % len(self.files))

            logger = logging.getLogger()
            for file in self.files:
                item = self.FileItem(file,selected_folder)
                item.setText(file)
                self.list_widget.addItem(item)
    
    def compress_videos(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.compress(self.bitrate_widget.value(), self.skip_existing.isChecked())
            
            logging.info("Completed!")

        self.message_box("Complete!",f"Finished converting {self.list_widget.count()} items.")

    def message_box(self, title, content):
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(content)
        dialog.exec()
    
    class FileItem(QtWidgets.QListWidgetItem):
        def __init__(self, file, path):
            super().__init__()
            self.file = file
            self.path = path
        
        class ProcessThread(QtCore.QThread):
            # Define a signal to emit the output of the QProcess
            output = QtCore.Signal(str)

            def __init__(self, command):
                super().__init__()
                self.command = command

            def run(self):
                # Create a QProcess object and connect its output to the signal
                self.process = QtCore.QProcess()
                self.process.readyReadStandardOutput.connect(self.handleOutput)
                self.process.readyReadStandardError.connect(self.handleOutput)
                logging.debug("Running command " + self.command)
                self.process.startCommand(self.command)
                self.process.waitForFinished()
                logging.debug(self.process.readAll())

            def handleOutput(self):
                # Read the output and emit the signal
                data = self.process.readAllStandardOutput().data().decode()
                self.output.emit(data)
                logging.debug("Yahoo")
                logging.debug(data)
                logging.debug(self.process.readAll().fromStdString())
        
        def compress(self, bitrate, skip_existing=False):
            video_path = os.path.join(self.path,self.file)
            compressed_path = os.path.join(self.path,"compressed",self.file)
            bitrate = str(bitrate) + "k"

            logging.info(f"Compressing video {video_path}")
            if skip_existing and os.path.exists(compressed_path):
                logging.info(f"{self.file} already exists in target folder. Skipping")
            else:
                # Get the creation time of the input file
                creation_time = subprocess.check_output(['powershell', '-command', f'(Get-Item "{video_path}").CreationTime']).decode().strip()
                logging.info(f"Creation time is {creation_time}")
                
                os.makedirs(os.path.dirname(compressed_path), exist_ok=True)
                
                command = f'ffmpeg -i {video_path} -y -c:v libx264 -crf 23 -preset medium -c:a copy {compressed_path}'
                #self.thread = self.ProcessThread(command)
                #self.thread = self.ProcessThread("ipconfig")
                #self.thread.output.connect(lambda: self.handle_output(self.thread.output))
                #self.thread.start()

                ffmpeg= (
                    FFmpeg()
                        .option('y')
                        .input(video_path)
                        .output(compressed_path)

                )

                @ffmpeg.on("progress")
                def on_progress(progress: Progress):
                    logging.info(progress)
                
                ffmpeg.execute()

                # Set the creation time
                subprocess.run(f"powershell -command (Get-Item '{compressed_path}').CreationTime='{creation_time}'")







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