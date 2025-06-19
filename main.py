import sys
import os
import logging
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QScrollArea, 
                            QFrame, QGridLayout, QMessageBox, QFileDialog,
                            QLineEdit, QDialog, QListWidget, QListWidgetItem, 
                            QSplitter, QSizePolicy, QMenu, QProgressBar, QTableWidget, QTableWidgetItem, QLayout, QStyle)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QObject, QRect, QPoint, QEvent
from PyQt6.QtGui import QIcon, QFont, QColor, QPalette, QPixmap, QImage
import requests
import json
import io
import base64
from PIL import Image
from dotenv import load_dotenv
from masonry_layout import MasonryLayout  # or from main import MasonryLayout if in same file
from justified_gallery_layout import JustifiedGalleryLayout
# Removed RepositoryView import
# from repository_view import RepositoryView
import concurrent.futures
import traceback
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl

# Configure logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class CreateRepoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("Initializing CreateRepoDialog")
        self.setWindowTitle("Create New Repository")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Repository name input
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter repository name")
        layout.addWidget(self.name_input)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        create_btn = QPushButton("Create")
        create_btn.clicked.connect(self.accept)
        
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(create_btn)
        layout.addLayout(buttons_layout)

    def get_repo_name(self):
        return self.name_input.text().strip()

class ImageLoaderWorker(QObject):
    image_loaded = pyqtSignal(int, QImage, str)  # index, qimage, name
    finished = pyqtSignal()

    def __init__(self, thumbnails):
        super().__init__()
        self.thumbnails = thumbnails
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def _download_and_process(self, idx_thumb):
        idx, thumb = idx_thumb
        if self._is_cancelled:
            return (idx, None, thumb.get('name', ''))
        if thumb.get('type') == 'file':
            try:
                response = requests.get(thumb.get('download_url', ''), timeout=10)
                if response.status_code == 200:
                    image = QImage.fromData(response.content)
                    if not image.isNull():
                        w, h = image.width(), image.height()
                        side = min(w, h)
                        x = (w - side) // 2
                        y = (h - side) // 2
                        cropped = image.copy(x, y, side, side)
                        # Only emit QImage, not QPixmap
                        return (idx, cropped, thumb.get('name', ''))
                    else:
                        logger.warning(f"Image is null for {thumb.get('name', '')}")
                        return (idx, None, thumb.get('name', ''))
                else:
                    logger.error(f"Failed to download image {thumb.get('name', '')}: {response.status_code}")
                    return (idx, None, thumb.get('name', ''))
            except Exception as e:
                logger.exception(f"Exception in _download_and_process for {thumb.get('name', '')}: {e}")
                return (idx, None, thumb.get('name', ''))
        return (idx, None, thumb.get('name', ''))

    def run(self):
        try:
            max_workers = min(8, len(self.thumbnails)) if self.thumbnails else 1
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for idx, thumb in enumerate(self.thumbnails):
                    if self._is_cancelled:
                        break
                    futures.append(executor.submit(self._download_and_process, (idx, thumb)))
                for future in concurrent.futures.as_completed(futures):
                    if self._is_cancelled:
                        break
                    try:
                        idx, qimage, name = future.result()
                        self.image_loaded.emit(idx, qimage, name)
                    except Exception as e:
                        logger.exception(f"Exception in worker future: {e}")
            self.finished.emit()
        except Exception as e:
            logger.exception(f"Exception in ImageLoaderWorker.run: {e}")
            self.finished.emit()

# Placeholder for the image viewer widget
class ImageViewerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo_name = None
        self._thumbnails = []  # Store thumbnails for responsive layout
        self._image_cards = []
        self._loader_thread = None
        self._loader_worker = None
        self._thread_running = False

        self.layout = QVBoxLayout(self)
        # Use default margins and spacing
        # self.layout.setContentsMargins(6, 6, 6, 6)
        # self.layout.setSpacing(6)
        
        # Scroll area for the image grid
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.layout.addWidget(self.scroll_area)

        # Container and grid for images
        self.image_container = QWidget()
        self.image_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_justified = JustifiedGalleryLayout(self.image_container, margin=0, spacing=6, row_height=120)
        self.scroll_area.setWidget(self.image_container)

        # Install event filter on scroll area viewport for resize responsiveness
        self.scroll_area.viewport().installEventFilter(self)

        # Placeholder label
        self.placeholder_label = QLabel("Select a repository and right-click to load images.")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.placeholder_label)
        self.placeholder_label.raise_()

        # Ensure the widget expands to fill the splitter panel
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def __del__(self):
        self.cancel_loading()
        super().__del__()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._thumbnails:
            self._relayout_images()
            self.image_justified.invalidate()
            self.image_container.updateGeometry()
            self.image_container.update()
        # Force image_container to fill the scroll area
        self.image_container.resize(self.scroll_area.viewport().size())

    def cancel_loading(self):
        if self._loader_worker is not None:
            self._loader_worker.cancel()
        if self._loader_thread is not None:
            try:
                if self._loader_thread.isRunning():
                    self._loader_thread.quit()
                    self._loader_thread.wait()
            except RuntimeError:
                # Thread already deleted
                pass
        self._loader_thread = None
        self._loader_worker = None
        self._thread_running = False

    def load_images(self, repo_name):
        logger.info(f"ImageViewerWidget received request to load images for: {repo_name}")
        self.cancel_loading()
        try:
            # Clear previous content (including placeholder or loading label)
            while self.layout.count():
                item = self.layout.takeAt(0)
                widget = item.widget()
                if widget and widget != self.scroll_area and widget != self.placeholder_label:
                    widget.deleteLater()
            # Hide placeholder and show scroll area
            self.placeholder_label.setVisible(False)
            self.scroll_area.setVisible(True)
            # Clear existing images in the grid
            for i in reversed(range(self.image_justified.count())): 
                widget = self.image_justified.itemAt(i).widget()
                if widget:
                    widget.deleteLater()
            self.repo_name = repo_name
            self._thumbnails = []
            if not repo_name:
                self.placeholder_label.setText("Select a repository and right-click to load images.")
                self.placeholder_label.setVisible(True)
                self.scroll_area.setVisible(False)
                self.layout.addWidget(self.placeholder_label)
                self.placeholder_label.raise_()
                logger.info("ImageViewerWidget cleared and showing placeholder.")
                return
            loading_label = QLabel(f"Loading images for {repo_name}...")
            loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.image_justified.addWidget(loading_label)
            self.image_container.update()
            try:
                headers = {
                    'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
                    'Accept': 'application/vnd.github.v3+json'
                }
                response = requests.get(
                    f'https://api.github.com/repos/lifetime-memories/{repo_name}/contents/thumbnails',
                    headers=headers, timeout=10
                )
                # Clear the temporary loading message
                for i in reversed(range(self.image_justified.count())): 
                    widget = self.image_justified.itemAt(i).widget()
                    if widget and isinstance(widget, QLabel) and "Loading images for" in widget.text():
                        widget.deleteLater()
                        break
                if response.status_code == 200:
                    thumbnails = response.json()
                    logger.info(f"Found {len(thumbnails)} images")
                    self._thumbnails = thumbnails if thumbnails else []
                    if thumbnails:
                        self.display_images(thumbnails)
                    else:
                        logger.info("Repository is empty, no images to display.")
                        empty_label = QLabel("No images uploaded yet. Right-click and select 'Upload Images' to add some!")
                        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        self.image_justified.addWidget(empty_label)
                        self._thumbnails = []
                elif response.status_code == 404:
                    logger.info("Thumbnails directory not found, no images to display.")
                    empty_label = QLabel("No images uploaded yet. Right-click and select 'Upload Images' to add some!")
                    empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.image_justified.addWidget(empty_label)
                    self._thumbnails = []
                elif response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers and response.headers['X-RateLimit-Remaining'] == '0':
                    logger.error("GitHub API rate limit exceeded.")
                    error_label = QLabel("GitHub API rate limit exceeded. Please try again later.")
                    error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.image_justified.addWidget(error_label)
                    QMessageBox.critical(self.parentWidget(), "Error", "GitHub API rate limit exceeded. Please try again later.")
                else:
                    error_msg = f"Failed to load images. Status code: {response.status_code}"
                    logger.error(error_msg)
                    error_label = QLabel(f"Error loading images: {response.status_code}")
                    error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.image_justified.addWidget(error_label)
                    QMessageBox.critical(self.parentWidget(), "Error", error_msg)
            except Exception as e:
                for i in reversed(range(self.image_justified.count())): 
                    widget = self.image_justified.itemAt(i).widget()
                    if widget and isinstance(widget, QLabel) and "Loading images for" in widget.text():
                        widget.deleteLater()
                        break
                logger.exception("Error while loading images")
                error_label = QLabel(f"An error occurred: {str(e)}")
                error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.image_justified.addWidget(error_label)
                QMessageBox.critical(self.parentWidget(), "Error", f"An error occurred: {str(e)}")
                self._thumbnails = []
            self.image_container.update()
        except Exception as e:
            logger.exception(f"Exception in load_images: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self.parentWidget(), "Error", f"An error occurred: {str(e)}")

    def display_images(self, thumbnails):
        logger.info("Displaying images in grid (responsive)")
        self._thumbnails = thumbnails
        self._relayout_images()

    def _relayout_images(self):
        self._clear_image_grid()
        self._image_cards = []
        thumbnails = self._thumbnails
        if not thumbnails:
            return
        self.cancel_loading()
        for idx, thumb in enumerate(thumbnails):
            if thumb['type'] == 'file':
                card = QFrame()
                layout = QVBoxLayout(card)
                layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                image_label = QLabel()
                image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                layout.addWidget(image_label)
                card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
                self.image_justified.addWidget(card)
                self._image_cards.append((image_label, None))
        # Start worker thread
        self._loader_thread = QThread()
        self._loader_worker = ImageLoaderWorker(thumbnails)
        self._loader_worker.moveToThread(self._loader_thread)
        self._loader_thread.started.connect(self._loader_worker.run)
        self._loader_worker.image_loaded.connect(self._on_image_loaded)
        self._loader_worker.finished.connect(self._loader_thread.quit)
        self._loader_worker.finished.connect(self._loader_worker.deleteLater)
        self._loader_thread.finished.connect(self._loader_thread.deleteLater)
        self._thread_running = True
        self._loader_thread.start()

    def _on_image_loaded(self, idx, qimage, name):
        try:
            if 0 <= idx < len(self._image_cards):
                image_label, _ = self._image_cards[idx]
                if qimage and not qimage.isNull():
                    pixmap = QPixmap.fromImage(qimage)
                    scaled_pixmap = pixmap.scaled(220, 220, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    image_label.setPixmap(scaled_pixmap)
                else:
                    image_label.setText("Failed to load image")
        except Exception as e:
            logger.exception(f"Exception in _on_image_loaded: {e}")

    def _clear_image_grid(self):
        try:
            while self.image_justified.count():
                item = self.image_justified.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            self._image_cards = []
        except Exception as e:
            logger.exception(f"Exception in _clear_image_grid: {e}")

    def eventFilter(self, obj, event):
        if obj == self.scroll_area.viewport() and event.type() == QEvent.Type.Resize:
            if self._thumbnails:
                self._relayout_images()
                self.image_justified.invalidate()
                self.image_container.updateGeometry()
                self.image_container.update()
        return super().eventFilter(obj, event)

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self.itemList = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing if spacing >= 0 else 6)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        spaceX = self.spacing()
        spaceY = self.spacing()
        for item in self.itemList:
            wid = item.widget()
            if not wid.isVisible():
                continue
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
        return y + lineHeight - rect.y()

class GalleryPopup(QDialog):
    def __init__(self, repo_name, thumbnails, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Gallery View - {repo_name}")
        self.setMinimumSize(900, 700)
        layout = QVBoxLayout(self)
        self.gallery_widget = ImageViewerWidget()
        layout.addWidget(self.gallery_widget)
        self.gallery_widget.load_images(repo_name)
        # Optionally, pass thumbnails if already loaded
        if thumbnails:
            self.gallery_widget.display_images(thumbnails)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Initializing MainWindow")
        self.setWindowTitle("Family Websites Repository Manager")
        self.setMinimumSize(1200, 800)
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        # Header buttons
        button_layout = QHBoxLayout()
        # Create repository button
        self.create_repo_btn = QPushButton("Create Repository")
        self.create_repo_btn.clicked.connect(self.create_repository)
        button_layout.addWidget(self.create_repo_btn)
        # Header buttons
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_repositories)
        button_layout.addWidget(refresh_btn)
        button_layout.addStretch(1)
        main_layout.addLayout(button_layout)
        # Create splitter for left and right panes and make it 20:80 ratio
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        # Left pane: Repository list
        self.repo_list = QListWidget()
        self.repo_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.repo_list.customContextMenuRequested.connect(self.show_repo_context_menu)
        self.splitter.addWidget(self.repo_list)
        # Center pane: Table view
        self.image_table = QTableWidget()
        self.image_table.setColumnCount(5)
        self.image_table.setHorizontalHeaderLabels(["Name", "Size (KB)", "Orig Size (KB)", "SHA", "Date"])
        self.image_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.image_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.image_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        compact_font = QFont()
        compact_font.setPointSize(9)
        self.image_table.setFont(compact_font)
        self.image_table.verticalHeader().setDefaultSectionSize(22)
        self.image_table.setWordWrap(False)
        header_font = QFont()
        header_font.setPointSize(9)
        self.image_table.horizontalHeader().setFont(header_font)
        self.image_table.horizontalHeader().setMinimumHeight(22)
        # Hide SHA column
        self.image_table.setColumnHidden(3, True)
        # Add a progress bar below the image list
        self.upload_progress = QProgressBar()
        self.upload_progress.setVisible(True)
        self.upload_progress.setMinimum(0)
        self.upload_progress.setMaximum(100)
        self.upload_progress.setValue(0)
        self.upload_progress.setFormat('Idle')
        # Table and progress bar in a vertical layout
        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(4, 0, 4, 0)
        table_layout.setSpacing(0)
        self.image_table.setStyleSheet("QTableWidget { border: none; padding: 0; margin: 0; } QHeaderView::section { padding: 0; margin: 0; }")
        table_layout.addWidget(self.image_table)
        table_layout.addWidget(self.upload_progress)
        table_widget = QWidget()
        table_widget.setLayout(table_layout)
        self.splitter.addWidget(table_widget)
        # Right pane: HTML Gallery view using QWebEngineView
        self.web_gallery = QWebEngineView()
        self.splitter.addWidget(self.web_gallery)
        # Set stretch factors to maintain 20:40:40 ratio
        self.splitter.setStretchFactor(0, 2)  # Left pane gets 20%
        self.splitter.setStretchFactor(1, 4)  # Table gets 40%
        self.splitter.setStretchFactor(2, 4)  # Gallery gets 40%
        main_layout.addWidget(self.splitter)
        # Set minimum widths
        self.image_table.setMinimumWidth(400)
        self.web_gallery.setMinimumWidth(400)
        # Set default black background for gallery
        self.set_gallery_black_background()
        # Initialize repositories
        self.repositories = []
        self.refresh_repositories()

    def set_gallery_black_background(self):
        self.web_gallery.setHtml('<html><body style="background:#222;"></body></html>', QUrl("about:blank"))

    def create_repository(self):
        logger.info("Opening create repository dialog")
        dialog = CreateRepoDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            repo_name = dialog.get_repo_name()
            if repo_name:
                try:
                    logger.info(f"Creating new repository: {repo_name}")
                    headers = {
                        'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
                        'Accept': 'application/vnd.github.v3+json'
                    }
                    response = requests.post(
                        'https://api.github.com/orgs/lifetime-memories/repos',
                        headers=headers,
                        json={
                            'name': repo_name,
                            'private': False,
                            'description': 'Image repository created by Repository Manager',
                            'has_issues': False,
                            'has_projects': False,
                            'has_wiki': False,
                            'auto_init': True
                        }
                    )
                    
                    if response.status_code == 201:
                        logger.info(f"Successfully created repository: {repo_name}")
                        self.refresh_repositories()
                        QMessageBox.information(self, "Success", "Repository created successfully")
                    else:
                        error_msg = f"Failed to create repository. Status code: {response.status_code}"
                        logger.error(error_msg)
                        QMessageBox.critical(self, "Error", error_msg)
                        
                except Exception as e:
                    logger.exception(f"Error while creating repository: {repo_name}")
                    QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def delete_repository(self, repo_name):
        logger.info(f"Attempting to delete repository: {repo_name}")
        reply = QMessageBox.question(
            self, 
            "Confirm Delete",
            f"Are you sure you want to delete {repo_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                headers = {
                    'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
                    'Accept': 'application/vnd.github.v3+json'
                }
                response = requests.delete(
                    f'https://api.github.com/repos/lifetime-memories/{repo_name}',
                    headers=headers
                )
                
                if response.status_code == 204:
                    logger.info(f"Successfully deleted repository: {repo_name}")
                    self.refresh_repositories()
                    QMessageBox.information(self, "Success", "Repository deleted successfully")
                else:
                    error_msg = f"Failed to delete repository. Status code: {response.status_code}"
                    logger.error(error_msg)
                    QMessageBox.critical(self, "Error", error_msg)
                    
            except Exception as e:
                logger.exception(f"Error while deleting repository: {repo_name}")
                QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def upload_images_to_repo(self, repo_name):
        self.set_interactive(False)
        files, _ = QFileDialog.getOpenFileNames(self, "Select JPG Images to Upload", "", "JPEG Images (*.jpg *.jpeg)")
        if not files:
            self.set_interactive(True)
            return
        headers = {
            'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
            'Accept': 'application/vnd.github.v3+json'
        }
        errors = []
        total = len(files)
        self.upload_progress.setValue(0)
        self.upload_progress.setFormat('Uploading... %p%')
        for idx, file_path in enumerate(files):
            try:
                # Read original image
                with open(file_path, 'rb') as f:
                    orig_bytes = f.read()
                orig_b64 = base64.b64encode(orig_bytes).decode('utf-8')
                filename = os.path.basename(file_path)
                # Compress image (max 200x200, JPEG, quality 85)
                image = Image.open(io.BytesIO(orig_bytes))
                image = image.convert('RGB')
                image.thumbnail((200, 200), Image.LANCZOS)
                buf = io.BytesIO()
                image.save(buf, format='JPEG', quality=85)
                thumb_bytes = buf.getvalue()
                thumb_b64 = base64.b64encode(thumb_bytes).decode('utf-8')
                # Upload original image to repo root
                put_url = f'https://api.github.com/repos/lifetime-memories/{repo_name}/contents/{filename}'
                put_data = {
                    'message': f'Upload {filename}',
                    'content': orig_b64
                }
                put_resp = requests.put(put_url, headers=headers, json=put_data)
                if put_resp.status_code not in (201, 200):
                    errors.append(f"Failed to upload {filename}: {put_resp.status_code}")
                    continue
                # Upload compressed image to thumbnails/
                thumb_url = f'https://api.github.com/repos/lifetime-memories/{repo_name}/contents/thumbnails/{filename}'
                thumb_data = {
                    'message': f'Upload thumbnail {filename}',
                    'content': thumb_b64
                }
                thumb_resp = requests.put(thumb_url, headers=headers, json=thumb_data)
                if thumb_resp.status_code not in (201, 200):
                    errors.append(f"Failed to upload thumbnail for {filename}: {thumb_resp.status_code}")
                    continue
            except Exception as e:
                errors.append(f"Error with {file_path}: {str(e)}")
            # Update progress bar
            self.upload_progress.setValue(int((idx + 1) / total * 100))
            QApplication.processEvents()
        self.upload_progress.setValue(0)
        self.upload_progress.setFormat('Idle')
        if errors:
            QMessageBox.critical(self, "Upload Errors", "\n".join(errors))
        else:
            QMessageBox.information(self, "Success", "Images uploaded successfully!")
        self.set_interactive(True)
        self.load_and_display_images(repo_name)

    def show_repo_context_menu(self, position):
        item = self.repo_list.itemAt(position)
        if item:
            repo = item.data(Qt.ItemDataRole.UserRole)
            if repo:
                menu = QMenu()
                load_action = menu.addAction("Load Images")
                upload_action = menu.addAction("Upload Images")
                delete_action = menu.addAction("Delete")
                load_action.triggered.connect(lambda: self._load_images_for_repo(repo['name']))
                upload_action.triggered.connect(lambda: self.upload_images_to_repo(repo['name']))
                delete_action.triggered.connect(lambda: self.delete_repository(repo['name']))
                menu.exec(self.repo_list.mapToGlobal(position))

    def _load_images_for_repo(self, repo_name):
        self.load_and_display_images(repo_name)
        # Fetch thumbnails and update HTML gallery
        headers = {
            'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
            'Accept': 'application/vnd.github.v3+json'
        }
        try:
            response = requests.get(
                f'https://api.github.com/repos/lifetime-memories/{repo_name}/contents/thumbnails',
                headers=headers
            )
            if response.status_code == 200:
                thumbnails = response.json()
                image_urls = [thumb['download_url'] for thumb in thumbnails if thumb['type'] == 'file']
                html = self._generate_gallery_html(image_urls)
                self.web_gallery.setHtml(html, QUrl("about:blank"))
            else:
                self.set_gallery_black_background()
        except Exception as e:
            self.set_gallery_black_background()

    def set_interactive(self, enabled):
        self.repo_list.setEnabled(enabled)
        self.image_table.setEnabled(enabled)
        self.create_repo_btn.setEnabled(enabled)
        # If you have other header buttons, disable them here as well
        # Optionally, disable the main window itself: self.setEnabled(enabled)

    def refresh_repositories(self):
        logger.info("Refreshing repositories")
        self.repo_list.clear()
        self.image_table.setRowCount(0)
        try:
            headers = {
                'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
                'Accept': 'application/vnd.github.v3+json'
            }
            response = requests.get(
                'https://api.github.com/orgs/lifetime-memories/repos',
                headers=headers
            )
            if response.status_code == 200:
                self.repositories = response.json()
                self.display_repositories()
                logger.info(f"Successfully fetched {len(self.repositories)} repositories")
            else:
                error_msg = f"Failed to fetch repositories. Status code: {response.status_code}"
                logger.error(error_msg)
                QMessageBox.critical(self, "Error", error_msg)
        except Exception as e:
            logger.exception("Error while refreshing repositories")
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def display_repositories(self):
        logger.info("Displaying repositories in list")
        for repo in self.repositories:
            item = QListWidgetItem(repo['name'])
            item.setData(Qt.ItemDataRole.UserRole, repo)
            self.repo_list.addItem(item)
        # Resize QListWidget to fit contents
        max_width = 0
        for i in range(self.repo_list.count()):
            item = self.repo_list.item(i)
            width = self.repo_list.fontMetrics().horizontalAdvance(item.text())
            if width > max_width:
                max_width = width
        self.repo_list.setMinimumWidth(max_width + 40)
        self.repo_list.updateGeometry()

    def load_and_display_images(self, repo_name):
        logger.info(f"Loading images for repository {repo_name} via context menu.")
        self.set_interactive(False)
        self.image_table.setRowCount(0)
        if not repo_name:
            self.set_interactive(True)
            return
        headers = {
            'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
            'Accept': 'application/vnd.github.v3+json'
        }
        try:
            response = requests.get(
                f'https://api.github.com/repos/lifetime-memories/{repo_name}/contents/thumbnails',
                headers=headers
            )
            if response.status_code == 200:
                thumbnails = response.json()
                self._last_thumbnails = thumbnails
                if thumbnails:
                    self.image_table.setRowCount(len(thumbnails))
                    row = 0
                    threads = []
                    for thumb in thumbnails:
                        if thumb['type'] == 'file':
                            name_item = QTableWidgetItem(thumb['name'])
                            size_kb = thumb['size'] / 1024
                            size_item = QTableWidgetItem(f"{size_kb:.1f}")
                            orig_size_item = QTableWidgetItem("Loading...")
                            sha_item = QTableWidgetItem(thumb.get('sha', ''))
                            date_item = QTableWidgetItem("Loading...")
                            self.image_table.setItem(row, 0, name_item)
                            self.image_table.setItem(row, 1, size_item)
                            self.image_table.setItem(row, 2, orig_size_item)
                            self.image_table.setItem(row, 4, date_item)
                            # Fetch original image size and last commit date for this file
                            import threading
                            def fetch_and_set_orig_size_and_date(row_idx, file_name):
                                import requests
                                import datetime
                                # Fetch original image metadata
                                orig_url = f'https://api.github.com/repos/lifetime-memories/{repo_name}/contents/{file_name}'
                                try:
                                    orig_resp = requests.get(orig_url, headers=headers)
                                    if orig_resp.status_code == 200:
                                        orig_info = orig_resp.json()
                                        orig_size_kb = orig_info.get('size', 0) / 1024
                                        self.image_table.setItem(row_idx, 2, QTableWidgetItem(f"{orig_size_kb:.1f}"))
                                        self.image_table.resizeColumnToContents(2)
                                    else:
                                        self.image_table.setItem(row_idx, 2, QTableWidgetItem("-"))
                                        self.image_table.resizeColumnToContents(2)
                                except Exception:
                                    self.image_table.setItem(row_idx, 2, QTableWidgetItem("-"))
                                    self.image_table.resizeColumnToContents(2)
                                # Fetch last commit date for this file (thumbnail)
                                commits_url = f'https://api.github.com/repos/lifetime-memories/{repo_name}/commits?path=thumbnails/{file_name}&per_page=1'
                                try:
                                    resp = requests.get(commits_url, headers=headers)
                                    if resp.status_code == 200:
                                        commits = resp.json()
                                        if commits:
                                            date_str = commits[0]['commit']['committer']['date']
                                            dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                            formatted = dt.strftime('%Y-%m-%d %H:%M')
                                            self.image_table.setItem(row_idx, 4, QTableWidgetItem(formatted))
                                            self.image_table.resizeColumnToContents(4)
                                        else:
                                            self.image_table.setItem(row_idx, 4, QTableWidgetItem("-"))
                                            self.image_table.resizeColumnToContents(4)
                                    else:
                                        self.image_table.setItem(row_idx, 4, QTableWidgetItem("-"))
                                        self.image_table.resizeColumnToContents(4)
                                except Exception:
                                    self.image_table.setItem(row_idx, 4, QTableWidgetItem("-"))
                                    self.image_table.resizeColumnToContents(4)
                                # If this is the last thread, re-enable UI and adjust splitter
                                if row_idx == len(thumbnails) - 1:
                                    self.set_interactive(True)
                                    # --- Adjust splitter after table is fully filled ---
                                    self.web_gallery.setVisible(True)
                                    if self.image_table.rowCount() > 1 or (self.image_table.rowCount() == 1 and self.image_table.item(0, 0) and self.image_table.item(0, 0).text() != "No images uploaded yet."):
                                        self.splitter.setStretchFactor(1, 3)  # Table
                                        self.splitter.setStretchFactor(2, 5)  # Gallery
                                    else:
                                        self.splitter.setStretchFactor(1, 4)
                                        self.splitter.setStretchFactor(2, 4)
                            t = threading.Thread(target=fetch_and_set_orig_size_and_date, args=(row, thumb['name']), daemon=True)
                            t.start()
                            threads.append(t)
                            row += 1
                    self.image_table.setRowCount(row)  # In case some are not files
                    self.image_table.resizeColumnsToContents()
                    if not threads:
                        self.set_interactive(True)
                        # --- Adjust splitter after table is fully filled (no threads case) ---
                        self.web_gallery.setVisible(True)
                        if self.image_table.rowCount() > 1 or (self.image_table.rowCount() == 1 and self.image_table.item(0, 0) and self.image_table.item(0, 0).text() != "No images uploaded yet."):
                            self.splitter.setStretchFactor(1, 3)  # Table
                            self.splitter.setStretchFactor(2, 5)  # Gallery
                        else:
                            self.splitter.setStretchFactor(1, 4)
                            self.splitter.setStretchFactor(2, 4)
                else:
                    self.image_table.setRowCount(1)
                    self.image_table.setItem(0, 0, QTableWidgetItem("No images uploaded yet."))
                    self.image_table.setItem(0, 1, QTableWidgetItem(""))
                    self.image_table.setItem(0, 2, QTableWidgetItem(""))
                    self.image_table.setItem(0, 4, QTableWidgetItem(""))
                    self.image_table.resizeColumnsToContents()
                    self.set_interactive(True)
                    # --- Adjust splitter after table is fully filled (no images case) ---
                    self.web_gallery.setVisible(True)
                    self.splitter.setStretchFactor(1, 4)
                    self.splitter.setStretchFactor(2, 4)
            elif response.status_code == 404:
                self.image_table.setRowCount(1)
                self.image_table.setItem(0, 0, QTableWidgetItem("No images uploaded yet."))
                self.image_table.setItem(0, 1, QTableWidgetItem(""))
                self.image_table.setItem(0, 2, QTableWidgetItem(""))
                self.image_table.setItem(0, 4, QTableWidgetItem(""))
                self.image_table.resizeColumnsToContents()
                self.set_interactive(True)
                # --- Adjust splitter after table is fully filled (404 case) ---
                self.web_gallery.setVisible(True)
                self.splitter.setStretchFactor(1, 4)
                self.splitter.setStretchFactor(2, 4)
            else:
                error_msg = f"Failed to load images. Status code: {response.status_code}"
                logger.error(error_msg)
                QMessageBox.critical(self, "Error", error_msg)
                self.set_interactive(True)
                # --- Adjust splitter after table is fully filled (error case) ---
                self.web_gallery.setVisible(True)
                self.splitter.setStretchFactor(1, 4)
                self.splitter.setStretchFactor(2, 4)
        except Exception as e:
            logger.exception("Error while loading images")
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
            self.set_interactive(True)
            # --- Adjust splitter after table is fully filled (exception case) ---
            self.web_gallery.setVisible(True)
            self.splitter.setStretchFactor(1, 4)
            self.splitter.setStretchFactor(2, 4)

    def _generate_gallery_html(self, image_urls):
        # Simple CSS Masonry using columns
        html = '''
        <!DOCTYPE html>
        <html><head><meta charset="utf-8">
        <style>
        body { background: #222; color: #eee; margin: 0; font-family: sans-serif; }
        .masonry {
            column-count: 4;
            column-gap: 12px;
            padding: 16px;
        }
        .masonry img {
            width: 100%;
            margin-bottom: 12px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            display: block;
            break-inside: avoid;
            background: #222;
        }
        @media (max-width: 1200px) { .masonry { column-count: 7; } }
        @media (max-width: 900px) { .masonry { column-count: 5; } }
        @media (max-width: 600px) { .masonry { column-count: 3; } }
        </style></head><body>
        <div class="masonry">
        '''
        for url in image_urls:
            html += f'<img src="{url}" loading="lazy" />\n'
        html += '</div></body></html>'
        return html

def main():
    logger.info("Starting application")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set up dark palette
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(35, 35, 35))
    app.setPalette(dark_palette)

    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 