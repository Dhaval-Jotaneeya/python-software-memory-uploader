import sys
import os
import logging
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QScrollArea, 
                            QFrame, QGridLayout, QMessageBox, QFileDialog,
                            QLineEdit, QDialog, QListWidget, QListWidgetItem, 
                            QSplitter, QSizePolicy, QMenu, QProgressBar, QTableWidget, QTableWidgetItem, QLayout, QStyle)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QObject, QRect, QPoint, QEvent, QTimer
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
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import pyqtSlot
import time

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
        
        # Add cache for GitHub data
        self._commit_cache = {}
        self._content_cache = {}
        self._rate_limit_remaining = None
        self._rate_limit_reset = None
        
        # Store current gallery HTML
        self._current_gallery_html = None
        self._current_repo_name = None
        
        # GitHub Pages build tracker
        self._build_tracker_thread = None
        self._build_tracker_worker = None
        self._build_tracking = False
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create main splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # First Column (Left)
        left_widget = QWidget()
        left_column = QVBoxLayout(left_widget)
        left_column.setContentsMargins(6, 6, 6, 6)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        self.create_repo_btn = QPushButton("Create Repository")
        self.create_repo_btn.clicked.connect(self.create_repository)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_repositories)
        button_layout.addWidget(self.create_repo_btn)
        button_layout.addWidget(refresh_btn)
        left_column.addLayout(button_layout)
        
        # Repository list
        self.repo_list = QListWidget()
        self.repo_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.repo_list.customContextMenuRequested.connect(self.show_repo_context_menu)
        self.repo_list.itemDoubleClicked.connect(self.handle_repo_double_click)
        left_column.addWidget(self.repo_list)
        
        # Rate limit section
        rate_limit_layout = QVBoxLayout()
        self.rate_limit_label = QLabel()
        self.rate_limit_label.setStyleSheet("padding: 5px;")
        self.refresh_rate_limit_btn = QPushButton("Check Rate Limit")
        self.refresh_rate_limit_btn.setStyleSheet("padding: 2px 10px; margin: 2px;")
        self.refresh_rate_limit_btn.clicked.connect(self.refresh_rate_limit)
        rate_limit_layout.addWidget(self.rate_limit_label)
        rate_limit_layout.addWidget(self.refresh_rate_limit_btn)
        left_column.addLayout(rate_limit_layout)
        
        # Second Column (Center)
        center_widget = QWidget()
        center_column = QVBoxLayout(center_widget)
        center_column.setContentsMargins(6, 6, 6, 6)
        
        # Table view
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
        self.image_table.setColumnHidden(3, True)
        self.image_table.setStyleSheet("QTableWidget { border: none; padding: 0; margin: 0; } QHeaderView::section { padding: 0; margin: 0; }")
        center_column.addWidget(self.image_table)
        
        # Progress bar and upload button layout
        progress_layout = QHBoxLayout()
        self.upload_progress = QProgressBar()
        self.upload_progress.setVisible(True)
        self.upload_progress.setMinimum(0)
        self.upload_progress.setMaximum(100)
        self.upload_progress.setValue(0)
        self.upload_progress.setFormat('Idle')
        progress_layout.addWidget(self.upload_progress)
        
        # Upload button
        upload_btn = QPushButton("Upload Images")
        upload_btn.clicked.connect(lambda: self.upload_images_to_repo(self._current_repo_name) if self._current_repo_name else None)
        progress_layout.addWidget(upload_btn)
        center_column.addLayout(progress_layout)
        
        # Third Column (Right)
        right_widget = QWidget()
        right_column = QVBoxLayout(right_widget)
        right_column.setContentsMargins(6, 6, 6, 6)
        
        # Web gallery view
        self.web_gallery = QWebEngineView()
        right_column.addWidget(self.web_gallery)
        
        # HTML-related buttons
        html_buttons_layout = QHBoxLayout()
        save_gallery_btn = QPushButton("Save Gallery Locally")
        save_gallery_btn.clicked.connect(self.save_gallery_as_html)
        publish_btn = QPushButton("Publish to GitHub Pages")
        publish_btn.clicked.connect(lambda: self.publish_to_github_pages(self._current_repo_name) if self._current_repo_name else None)
        
        # Build status indicator
        self.build_status_label = QLabel("Build Status: Not started")
        self.build_status_label.setStyleSheet("padding: 5px; color: gray; font-size: 11px;")
        
        # Manual check button
        self.check_build_btn = QPushButton("Check Build Status")
        self.check_build_btn.clicked.connect(self.manual_check_build_status)
        self.check_build_btn.setEnabled(False)
        
        html_buttons_layout.addWidget(save_gallery_btn)
        html_buttons_layout.addWidget(publish_btn)
        html_buttons_layout.addWidget(self.build_status_label)
        html_buttons_layout.addWidget(self.check_build_btn)
        right_column.addLayout(html_buttons_layout)
        
        # Add widgets to splitter
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(center_widget)
        self.splitter.addWidget(right_widget)
        
        # Set stretch factors (20:30:50)
        self.splitter.setStretchFactor(0, 1)  # 10% for left pane
        self.splitter.setStretchFactor(1, 2)  # 20% for center pane
        self.splitter.setStretchFactor(2, 7)  # 70% for right pane
        
        # Set minimum widths
        left_widget.setMinimumWidth(250)
        center_widget.setMinimumWidth(400)
        right_widget.setMinimumWidth(400)
        
        # Add splitter to main layout
        main_layout.addWidget(self.splitter)
        
        # Initialize rate limit display
        self.update_rate_limit_display()
        # Set default black background for gallery
        self.set_gallery_black_background()
        # Initialize repositories
        self.repositories = []
        self.refresh_repositories()

        # Add web channel for JavaScript communication
        self.web_channel = QWebChannel()
        self.web_channel.registerObject("backend", self)

    def __del__(self):
        self.cancel_build_tracking()
        super().__del__()

    def cancel_build_tracking(self):
        """Cancel any ongoing build tracking"""
        if self._build_tracker_worker is not None:
            self._build_tracker_worker.cancel()
        if self._build_tracker_thread is not None:
            try:
                if self._build_tracker_thread.isRunning():
                    self._build_tracker_thread.quit()
                    self._build_tracker_thread.wait()
            except RuntimeError:
                # Thread already deleted
                pass
        self._build_tracker_thread = None
        self._build_tracker_worker = None
        self._build_tracking = False

    def start_build_tracking(self, repo_name):
        """Start tracking GitHub Pages build status"""
        self.cancel_build_tracking()
        
        # Initialize UI for build tracking
        self.build_status_label.setText("Build Status: Starting build tracking...")
        self.build_status_label.setStyleSheet("padding: 5px; color: blue; font-size: 11px;")
        self.check_build_btn.setEnabled(True)
        
        self._build_tracker_thread = QThread()
        self._build_tracker_worker = GitHubPagesBuildTracker(repo_name)
        self._build_tracker_worker.moveToThread(self._build_tracker_thread)
        
        # Connect signals
        self._build_tracker_thread.started.connect(self._build_tracker_worker.run)
        self._build_tracker_worker.build_status_updated.connect(self._on_build_status_updated)
        self._build_tracker_worker.build_completed.connect(self._on_build_completed)
        self._build_tracker_worker.finished.connect(self._build_tracker_thread.quit)
        self._build_tracker_worker.finished.connect(self._build_tracker_worker.deleteLater)
        self._build_tracker_thread.finished.connect(self._build_tracker_thread.deleteLater)
        
        self._build_tracking = True
        self._build_tracker_thread.start()

    def _on_build_status_updated(self, status, message):
        """Handle build status updates"""
        logger.info(f"GitHub Pages build status: {status} - {message}")
        
        # Update build status label
        status_colors = {
            'building': 'orange',
            'waiting': 'blue', 
            'success': 'green',
            'error': 'red',
            'timeout': 'red',
            'unknown': 'gray'
        }
        color = status_colors.get(status, 'gray')
        self.build_status_label.setText(f"Build Status: {message}")
        self.build_status_label.setStyleSheet(f"padding: 5px; color: {color}; font-size: 11px;")
        
        # Enable manual check button
        self.check_build_btn.setEnabled(True)
        
        # Update progress bar with status
        if status == 'building':
            self.upload_progress.setFormat(f'Building GitHub Pages...')
            self.upload_progress.setValue(50)  # Show progress
        elif status == 'waiting':
            self.upload_progress.setFormat(f'Waiting for build...')
            self.upload_progress.setValue(25)
        elif status == 'success':
            self.upload_progress.setFormat(f'✅ {message}')
            self.upload_progress.setValue(100)
        elif status == 'error':
            self.upload_progress.setFormat(f'❌ {message}')
            self.upload_progress.setValue(0)
        elif status == 'timeout':
            self.upload_progress.setFormat(f'⏰ {message}')
            self.upload_progress.setValue(0)
        else:
            self.upload_progress.setFormat(f'Status: {message}')
        
        QApplication.processEvents()

    def _on_build_completed(self, success, url):
        """Handle build completion"""
        self._build_tracking = False
        
        if success:
            # Show success message with the URL
            QMessageBox.information(
                self,
                "GitHub Pages Published!",
                f"Your gallery is now live at:\n{url}\n\nYou can share this link with others!"
            )
            
            # Ask if user wants to open the published page
            reply = QMessageBox.question(
                self,
                "Open Page",
                "Would you like to open the published gallery in your default browser?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                import webbrowser
                webbrowser.open(url)
        else:
            # Show error message
            QMessageBox.warning(
                self,
                "Build Failed",
                "GitHub Pages build failed. Please check the repository settings and try again."
            )
        
        # Reset progress bar
        self.upload_progress.setValue(0)
        self.upload_progress.setFormat('Ready')
        QApplication.processEvents()

    def manual_check_build_status(self):
        """Manually check the current build status"""
        if not self._current_repo_name:
            QMessageBox.warning(self, "Warning", "No repository selected.")
            return
            
        try:
            self.upload_progress.setFormat('Checking build status...')
            QApplication.processEvents()
            
            headers = {
                'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
                'Accept': 'application/vnd.github.v3+json'
            }
            
            pages_url = f'https://api.github.com/repos/lifetime-memories/{self._current_repo_name}/pages'
            response = requests.get(pages_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                pages_data = response.json()
                status = pages_data.get('status', 'unknown')
                site_url = pages_data.get('html_url', f'https://lifetime-memories.github.io/{self._current_repo_name}')
                
                status_messages = {
                    'built': f'✅ Build completed! Site available at: {site_url}',
                    'building': '🔄 Site is currently building...',
                    'errored': f'❌ Build failed: {pages_data.get("error", {}).get("message", "Unknown error")}',
                    'not_built': '⏳ Build not started yet',
                    'unknown': f'❓ Unknown status: {status}'
                }
                
                message = status_messages.get(status, f'Status: {status}')
                self.build_status_label.setText(f"Build Status: {message}")
                
                # Set color based on status
                if status == 'built':
                    self.build_status_label.setStyleSheet("padding: 5px; color: green; font-size: 11px;")
                    # Ask if user wants to open the site
                    reply = QMessageBox.question(
                        self,
                        "Site Ready",
                        f"Your site is ready!\n\n{site_url}\n\nWould you like to open it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        import webbrowser
                        webbrowser.open(site_url)
                elif status == 'building':
                    self.build_status_label.setStyleSheet("padding: 5px; color: orange; font-size: 11px;")
                elif status == 'errored':
                    self.build_status_label.setStyleSheet("padding: 5px; color: red; font-size: 11px;")
                else:
                    self.build_status_label.setStyleSheet("padding: 5px; color: gray; font-size: 11px;")
                    
            elif response.status_code == 404:
                self.build_status_label.setText("Build Status: GitHub Pages not enabled")
                self.build_status_label.setStyleSheet("padding: 5px; color: red; font-size: 11px;")
            else:
                self.build_status_label.setText(f"Build Status: API Error ({response.status_code})")
                self.build_status_label.setStyleSheet("padding: 5px; color: red; font-size: 11px;")
                
        except Exception as e:
            logger.exception("Error checking build status")
            self.build_status_label.setText(f"Build Status: Error - {str(e)}")
            self.build_status_label.setStyleSheet("padding: 5px; color: red; font-size: 11px;")
        finally:
            self.upload_progress.setFormat('Ready')
            QApplication.processEvents()

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
        menu = QMenu()
        
        if item:
            repo = item.data(Qt.ItemDataRole.UserRole)
            if repo:
                load_action = menu.addAction("Load Images")
                upload_action = menu.addAction("Upload Images")
                save_gallery_action = menu.addAction("Save Gallery as HTML")
                publish_action = menu.addAction("Publish to GitHub Pages")
                delete_action = menu.addAction("Delete")
                
                load_action.triggered.connect(lambda: self._load_images_for_repo(repo['name']))
                upload_action.triggered.connect(lambda: self.upload_images_to_repo(repo['name']))
                save_gallery_action.triggered.connect(self.save_gallery_as_html)
                publish_action.triggered.connect(lambda: self.publish_to_github_pages(repo['name']))
                delete_action.triggered.connect(lambda: self.delete_repository(repo['name']))
        else:
            # Context menu for empty area
            refresh_action = menu.addAction("Refresh")
            create_action = menu.addAction("Create Repository")
            
            refresh_action.triggered.connect(self.refresh_repositories)
            create_action.triggered.connect(self.create_repository)
                
            menu.exec(self.repo_list.mapToGlobal(position))

    def publish_to_github_pages(self, repo_name):
        """Publish the gallery to GitHub Pages"""
        if not self._current_gallery_html:
            QMessageBox.warning(self, "Warning", "Please load the repository images first.")
            return

        try:
            self.upload_progress.setValue(0)
            self.upload_progress.setFormat('Publishing to GitHub Pages...')
            QApplication.processEvents()

            # First, enable GitHub Pages if not already enabled
            headers = {
                'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
                'Accept': 'application/vnd.github.v3+json'
            }

            # Enable GitHub Pages
            pages_settings = {
                'source': {
                    'branch': 'gh-pages',
                    'path': '/'
                }
            }
            
            pages_url = f'https://api.github.com/repos/lifetime-memories/{repo_name}/pages'
            pages_response = requests.post(pages_url, headers=headers, json=pages_settings)
            
            # Get the current commit SHA of the default branch
            repo_response = requests.get(f'https://api.github.com/repos/lifetime-memories/{repo_name}', headers=headers)
            if repo_response.status_code != 200:
                raise Exception(f"Failed to get repository info: {repo_response.status_code}")
            
            repo_data = repo_response.json()
            default_branch = repo_data['default_branch']
            
            # Get the latest commit SHA
            branch_response = requests.get(
                f'https://api.github.com/repos/lifetime-memories/{repo_name}/git/refs/heads/{default_branch}',
                headers=headers
            )
            if branch_response.status_code != 200:
                raise Exception(f"Failed to get branch info: {branch_response.status_code}")
            
            base_sha = branch_response.json()['object']['sha']

            # Create or update gh-pages branch
            try:
                # Try to get gh-pages ref
                gh_pages_response = requests.get(
                    f'https://api.github.com/repos/lifetime-memories/{repo_name}/git/refs/heads/gh-pages',
                    headers=headers
                )
                gh_pages_exists = gh_pages_response.status_code == 200
            except:
                gh_pages_exists = False

            # Create a blob with the HTML content
            blob_data = {
                'content': self._current_gallery_html,
                'encoding': 'utf-8'
            }
            blob_response = requests.post(
                f'https://api.github.com/repos/lifetime-memories/{repo_name}/git/blobs',
                headers=headers,
                json=blob_data
            )
            if blob_response.status_code != 201:
                raise Exception(f"Failed to create blob: {blob_response.status_code}")
            
            blob_sha = blob_response.json()['sha']

            # Create a tree
            tree_data = {
                'base_tree': base_sha,
                'tree': [{
                    'path': 'index.html',
                    'mode': '100644',
                    'type': 'blob',
                    'sha': blob_sha
                }]
            }
            tree_response = requests.post(
                f'https://api.github.com/repos/lifetime-memories/{repo_name}/git/trees',
                headers=headers,
                json=tree_data
            )
            if tree_response.status_code != 201:
                raise Exception(f"Failed to create tree: {tree_response.status_code}")
            
            tree_sha = tree_response.json()['sha']

            # Create a commit
            commit_data = {
                'message': 'Update GitHub Pages',
                'tree': tree_sha,
                'parents': [base_sha]
            }
            commit_response = requests.post(
                f'https://api.github.com/repos/lifetime-memories/{repo_name}/git/commits',
                headers=headers,
                json=commit_data
            )
            if commit_response.status_code != 201:
                raise Exception(f"Failed to create commit: {commit_response.status_code}")
            
            new_commit_sha = commit_response.json()['sha']

            # Create or update the gh-pages branch reference
            if gh_pages_exists:
                # Update existing branch
                ref_data = {
                    'sha': new_commit_sha,
                    'force': True
                }
                ref_response = requests.patch(
                    f'https://api.github.com/repos/lifetime-memories/{repo_name}/git/refs/heads/gh-pages',
                    headers=headers,
                    json=ref_data
                )
            else:
                # Create new branch
                ref_data = {
                    'ref': 'refs/heads/gh-pages',
                    'sha': new_commit_sha
                }
                ref_response = requests.post(
                    f'https://api.github.com/repos/lifetime-memories/{repo_name}/git/refs',
                    headers=headers,
                    json=ref_data
                )

            if ref_response.status_code not in [200, 201]:
                raise Exception(f"Failed to update gh-pages branch: {ref_response.status_code}")

            # Content published successfully, now start tracking the build
            self.upload_progress.setFormat('Content published! Starting build tracking...')
            self.upload_progress.setValue(25)
            QApplication.processEvents()
            
            # Start the build tracker
            self.start_build_tracking(repo_name)

        except Exception as e:
            logger.exception("Error publishing to GitHub Pages")
            QMessageBox.critical(self, "Error", f"Failed to publish to GitHub Pages: {str(e)}")
            self.upload_progress.setValue(0)
            self.upload_progress.setFormat('Ready')
            QApplication.processEvents()

    def reset_build_status(self):
        """Reset build status display"""
        self.build_status_label.setText("Build Status: Not started")
        self.build_status_label.setStyleSheet("padding: 5px; color: gray; font-size: 11px;")
        self.check_build_btn.setEnabled(False)
        self.cancel_build_tracking()

    def _load_images_for_repo(self, repo_name):
        """Load images for a repository and update the gallery view"""
        # Reset build status for new repository
        self.reset_build_status()
        
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
                image_pairs = []
                for thumb in thumbnails:
                    if thumb['type'] == 'file':
                        thumb_url = thumb['download_url']
                        orig_url = thumb_url.replace('/thumbnails/', '/')
                        image_pairs.append((thumb_url, orig_url))
                html = self._generate_gallery_html(image_pairs)
                
                # Set up web channel before loading HTML
                self.web_gallery.page().setWebChannel(self.web_channel)
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
            # Add tooltip to show that double-click loads the repository
            item.setToolTip("Double-click to load repository")
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

    def _check_rate_limit(self, response):
        """Check and update rate limit info from response headers"""
        try:
            self._rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            self._rate_limit_reset = datetime.fromtimestamp(reset_time)
            
            # Update the GUI display
            self.update_rate_limit_display()
            
            if self._rate_limit_remaining < 100:  # Warning threshold
                reset_time_str = self._rate_limit_reset.strftime('%Y-%m-%d %H:%M:%S')
                logger.warning(f"GitHub API rate limit low: {self._rate_limit_remaining} remaining, resets at {reset_time_str}")
                if self._rate_limit_remaining < 10:  # Critical threshold
                    QMessageBox.warning(self, "Rate Limit Warning", 
                        f"GitHub API rate limit is very low ({self._rate_limit_remaining} remaining).\n"
                        f"Limit will reset at {reset_time_str}")
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            self.rate_limit_label.setText("Rate limit: Unknown")
            self.rate_limit_label.setStyleSheet("padding: 5px; color: gray;")

    def update_rate_limit_display(self):
        """Update the rate limit display in the status bar"""
        try:
            if self._rate_limit_remaining is not None and self._rate_limit_reset is not None:
                # Calculate time until reset
                now = datetime.now()
                time_until_reset = self._rate_limit_reset - now
                hours = int(time_until_reset.total_seconds() // 3600)
                minutes = int((time_until_reset.total_seconds() % 3600) // 60)
                
                # Format the display text
                reset_time = self._rate_limit_reset.strftime('%H:%M:%S')
                display_text = f"API Calls Remaining: {self._rate_limit_remaining} | Resets in: {hours}h {minutes}m (at {reset_time})"
                
                # Set color based on remaining limit
                if self._rate_limit_remaining < 10:
                    color = "red"
                elif self._rate_limit_remaining < 100:
                    color = "orange"
                else:
                    color = "green"
                
                self.rate_limit_label.setText(display_text)
                self.rate_limit_label.setStyleSheet(f"padding: 5px; color: {color};")
            else:
                self.rate_limit_label.setText("Rate limit: Not yet fetched")
                self.rate_limit_label.setStyleSheet("padding: 5px; color: gray;")
        except Exception as e:
            logger.error(f"Error updating rate limit display: {e}")
            self.rate_limit_label.setText("Rate limit: Error")
            self.rate_limit_label.setStyleSheet("padding: 5px; color: red;")

    @pyqtSlot(str, str)
    def downloadImage(self, url, filename):
        """Handle image download with native file dialog"""
        try:
            # Show save file dialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Image As",
                filename,
                "JPEG Images (*.jpg *.jpeg);;All Files (*.*)"
            )
            
            if file_path:
                # Download the image
                headers = {
                    'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
                    'Accept': 'application/vnd.github.v3+json'
                }
                response = requests.get(url, headers=headers, stream=True)
                
                if response.status_code == 200:
                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    QMessageBox.information(self, "Success", "Image downloaded successfully!")
                else:
                    QMessageBox.critical(self, "Error", f"Failed to download image: {response.status_code}")
        except Exception as e:
            logger.exception("Error downloading image")
            QMessageBox.critical(self, "Error", f"Failed to download image: {str(e)}")

    def refresh_rate_limit(self):
        """Manually refresh the rate limit information"""
        try:
            self.upload_progress.setFormat('Checking rate limit...')
            QApplication.processEvents()
            
            response = self._make_github_request('https://api.github.com/rate_limit')
            if response.status_code == 200:
                rate_data = response.json()
                self._rate_limit_remaining = rate_data['rate']['remaining']
                self._rate_limit_reset = datetime.fromtimestamp(rate_data['rate']['reset'])
                self.update_rate_limit_display()
                self.upload_progress.setFormat('Rate limit updated')
            else:
                logger.error(f"Failed to fetch rate limit. Status code: {response.status_code}")
                self.upload_progress.setFormat('Failed to update rate limit')
        except Exception as e:
            logger.error(f"Error refreshing rate limit: {e}")
            self.upload_progress.setFormat('Error checking rate limit')
        finally:
            QApplication.processEvents()
            # Reset progress bar after a short delay
            QTimer.singleShot(2000, lambda: self.upload_progress.setFormat('Idle'))

    def _make_github_request(self, url, headers=None):
        """Make a GitHub API request with rate limit checking"""
        if not headers:
            headers = {
                'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
                'Accept': 'application/vnd.github.v3+json'
            }
        
        try:
            response = requests.get(url, headers=headers)
            self._check_rate_limit(response)
            return response
        except Exception as e:
            logger.error(f"Error making GitHub request to {url}: {e}")
            raise

    def load_and_display_images(self, repo_name):
        self._current_repo_name = repo_name  # Store current repo name
        logger.info(f"Loading images for repository {repo_name} via context menu.")
        
        # Reset build status for new repository
        self.reset_build_status()
        
        self.set_interactive(False)
        self.image_table.setRowCount(0)
        if not repo_name:
            self.set_interactive(True)
            return
        
        # Reset and show progress bar
        self.upload_progress.setValue(0)
        self.upload_progress.setFormat('Fetching repository data...')
        QApplication.processEvents()
        
        try:
            # Get thumbnails list
            response = self._make_github_request(
                f'https://api.github.com/repos/lifetime-memories/{repo_name}/contents/thumbnails'
            )
            
            if response.status_code == 200:
                thumbnails = response.json()
                self._last_thumbnails = thumbnails
                if thumbnails:
                    total_images = len(thumbnails)
                    self.image_table.setRowCount(total_images)
                    self.upload_progress.setFormat(f'Loading metadata for {total_images} images... %p%')
                    QApplication.processEvents()
                    
                    # Batch fetch original file metadata
                    orig_files_url = f'https://api.github.com/repos/lifetime-memories/{repo_name}/contents'
                    orig_response = self._make_github_request(orig_files_url)
                    if orig_response.status_code == 200:
                        orig_files = {f['name']: f for f in orig_response.json()}
                    else:
                        orig_files = {}
                    
                    # Batch fetch commit history for all files
                    commits_url = f'https://api.github.com/repos/lifetime-memories/{repo_name}/commits'
                    commits_response = self._make_github_request(f"{commits_url}?per_page=100")
                    if commits_response.status_code == 200:
                        commits_data = commits_response.json()
                        # Create a map of filename to latest commit
                        file_commits = {}
                        for commit in commits_data:
                            if 'files' in commit:
                                for file in commit['files']:
                                    filename = file['filename'].split('/')[-1]
                                    if filename not in file_commits:
                                        file_commits[filename] = commit['commit']['committer']['date']
                    else:
                        file_commits = {}
                    
                    row = 0
                    completed_images = 0
                    
                    for thumb in thumbnails:
                        if thumb['type'] == 'file':
                            filename = thumb['name']
                            name_item = QTableWidgetItem(filename)
                            size_kb = thumb['size'] / 1024
                            size_item = QTableWidgetItem(f"{size_kb:.1f}")
                            
                            # Get original file size from batch request
                            orig_size_kb = "-"
                            if filename in orig_files:
                                orig_size_kb = f"{orig_files[filename]['size'] / 1024:.1f}"
                            orig_size_item = QTableWidgetItem(str(orig_size_kb))
                            
                            # Get commit date from batch request
                            date_str = "-"
                            if filename in file_commits:
                                dt = datetime.fromisoformat(file_commits[filename].replace('Z', '+00:00'))
                                date_str = dt.strftime('%Y-%m-%d %H:%M')
                            date_item = QTableWidgetItem(date_str)
                            
                            self.image_table.setItem(row, 0, name_item)
                            self.image_table.setItem(row, 1, size_item)
                            self.image_table.setItem(row, 2, orig_size_item)
                            self.image_table.setItem(row, 4, date_item)
                            
                            row += 1
                    
                    self.image_table.setRowCount(row)
                    self.image_table.resizeColumnsToContents()
                    
                    self.upload_progress.setFormat('Loading gallery view...')
                    QApplication.processEvents()
                    
                    self.set_interactive(True)
                    self.web_gallery.setVisible(True)
                    if row > 1 or (row == 1 and self.image_table.item(0, 0) and self.image_table.item(0, 0).text() != "No images uploaded yet."):
                        self.splitter.setStretchFactor(1, 3)
                        self.splitter.setStretchFactor(2, 5)
                    else:
                        self.splitter.setStretchFactor(1, 4)
                        self.splitter.setStretchFactor(2, 4)
                    
                    self.upload_progress.setValue(100)
                    self.upload_progress.setFormat('Ready')
                    QApplication.processEvents()
                else:
                    self._handle_empty_repository()
            elif response.status_code == 404:
                self._handle_empty_repository()
            else:
                self._handle_error(f"Failed to load images. Status code: {response.status_code}")
        except Exception as e:
            self._handle_error(f"An error occurred: {str(e)}")

    def _handle_empty_repository(self):
        """Handle case when repository is empty"""
        self.image_table.setRowCount(1)
        self.image_table.setItem(0, 0, QTableWidgetItem("No images uploaded yet."))
        self.image_table.setItem(0, 1, QTableWidgetItem(""))
        self.image_table.setItem(0, 2, QTableWidgetItem(""))
        self.image_table.setItem(0, 4, QTableWidgetItem(""))
        self.image_table.resizeColumnsToContents()
        self.set_interactive(True)
        self.web_gallery.setVisible(True)
        self.splitter.setStretchFactor(1, 4)
        self.splitter.setStretchFactor(2, 4)
        self.upload_progress.setValue(100)
        self.upload_progress.setFormat('Ready')
        QApplication.processEvents()

    def _handle_error(self, error_msg):
        """Handle error cases"""
        logger.error(error_msg)
        QMessageBox.critical(self, "Error", error_msg)
        self.set_interactive(True)
        self.web_gallery.setVisible(True)
        self.splitter.setStretchFactor(1, 4)
        self.splitter.setStretchFactor(2, 4)
        self.upload_progress.setValue(0)
        self.upload_progress.setFormat('Error loading images')
        QApplication.processEvents()

    def _generate_gallery_html(self, image_pairs):
        html = '''
        <!DOCTYPE html>
        <html><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Image Gallery</title>
        <style>
        html, body { 
            background: #222; 
            color: #eee; 
            margin: 0; 
            padding: 0;
            font-family: sans-serif;
            min-height: 100vh;
            width: 100%;
            overflow-x: hidden;
            box-sizing: border-box;
        }
        *, *:before, *:after {
            box-sizing: inherit;
        }
        .gallery-header {
            padding: 20px;
            text-align: center;
            background: rgba(0,0,0,0.4);
            backdrop-filter: blur(10px);
            position: sticky;
            top: 0;
            z-index: 100;
            width: 100%;
            box-sizing: border-box;
        }
        .gallery-title {
            margin: 0;
            font-size: 24px;
            color: #fff;
            word-wrap: break-word;
            max-width: 100%;
        }
        @media (max-width: 600px) {
            .gallery-header {
                padding: 20px 16px;
                min-height: 70px;
            }
            .gallery-title {
                font-size: 22px;
            }
        }
        .gallery-info {
            margin-top: 10px;
            font-size: 14px;
            color: #aaa;
        }
        .gallery-view {
            position: relative;
            min-height: 100vh;
            width: 100%;
            max-width: 100vw;
            overflow-x: hidden;
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
            margin: 0;
            padding: 0;
        }
        .image-view {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            width: 100%;
            height: 100%;
            display: none;
            background: #222;
            flex-direction: column;
            z-index: 1000;
            touch-action: manipulation;
            overflow: hidden;
        }
        .image-view.mobile {
            background: rgba(0, 0, 0, 0.95);
        }
        .image-view.mobile .controls-container {
            display: none !important;
        }
        .context-menu {
            display: none;
            position: fixed;
            background: rgba(40, 40, 40, 0.98);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 8px 0;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            z-index: 2000;
        }
        .context-menu-item {
            padding: 12px 24px;
            color: white;
            font-size: 16px;
            cursor: pointer;
            white-space: nowrap;
        }
        .context-menu-item:active {
            background: rgba(255,255,255,0.1);
        }
        .gallery-container {
            width: 100%;
            max-width: 100vw;
            margin: 0 auto;
            padding: 0 24px;
            box-sizing: border-box;
            overflow: hidden;
        }
        .masonry { 
            column-count: 10; 
            column-gap: 8px; 
            padding: 24px 0;
            width: 100%;
            margin: 0 auto;
            box-sizing: border-box;
        }
        .masonry img { 
            width: 100%; 
            margin-bottom: 8px; 
            border-radius: 4px;
            box-shadow: none;
            display: block; 
            break-inside: avoid; 
            background: #222; 
            cursor: pointer;
            transition: transform 0.15s ease-out;
            height: auto;
            vertical-align: middle;
            max-width: 100%;
        }
        .masonry img:hover {
            transform: scale(1.02);
        }
        /* Default desktop layout */
        .masonry { 
            column-count: 10;
            column-gap: 8px;
            padding: 24px 0;
        }

        /* Mobile-specific detection */
        @media only screen 
        and (max-device-width: 812px)
        and (-webkit-min-device-pixel-ratio: 2),
        only screen and (max-device-width: 812px)
        and (min-resolution: 192dpi) { 
            .gallery-header {
                padding: 48px 24px;
                background: rgba(0,0,0,0.85);
                backdrop-filter: blur(15px);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: auto;
                width: 100vw;
                margin: 0;
                box-sizing: border-box;
                box-shadow: 0 2px 20px rgba(0,0,0,0.4);
            }
            .gallery-title {
                font-size: 24px;
                line-height: 1.3;
                padding: 0;
                margin: 0;
                width: 100%;
                text-align: center;
                font-weight: 600;
                text-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            .gallery-info {
                font-size: 20px;
                margin-top: 24px;
                opacity: 0.95;
                width: 100%;
                text-align: center;
            }
            .gallery-container {
                padding: 15px;
                width: 100vw;
                max-width: 100%;
                margin: 0 auto;
                box-sizing: border-box;
                background: #222;
                display: flex;
                justify-content: center;
            }
            .masonry { 
                column-count: 2 !important;
                column-gap: 15px;
                padding: 0;
                margin: 0;
                width: 100%;
                max-width: 800px;
            }
            .masonry img {
                border-radius: 12px;
                margin-bottom: 15px;
                box-shadow: none;
                transition: none;
                position: relative;
                -webkit-tap-highlight-color: transparent;
            }
            /* Remove any hover/active effects on mobile */
            .masonry img:active,
            .masonry img:hover {
                transform: none;
                box-shadow: none;
            }
        }
            .masonry img:active {
                transform: scale(0.98);
            }
            /* Improve touch targets */
            button {
                padding: 16px 24px;
                border-radius: 14px;
                font-size: 17px;
                margin: 10px 0;
                min-height: 54px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            }
            /* Add more breathing room at the bottom */
            .gallery-view {
                padding-bottom: 32px;
            }
        }

        /* Tablet-specific detection */
        @media only screen 
        and (min-device-width: 813px) 
        and (max-device-width: 1366px)
        and (-webkit-min-device-pixel-ratio: 1.5) {
            .masonry { 
                column-count: 3 !important;
                column-gap: 8px;
            }
            .gallery-container {
                padding: 0 12px;
            }
        }

        /* Desktop and general responsive breakpoints */
        @media screen and (max-width: 576px) {
            .masonry { 
                column-count: 2;
                column-gap: 6px;
                padding: 12px 0;
            }
            .gallery-container {
                padding: 0 8px;
            }
        }
        @media screen and (min-width: 577px) and (max-width: 768px) {
            .masonry { 
                column-count: 3;
                column-gap: 6px;
            }
            .gallery-container {
                padding: 0 12px;
            }
        }
        @media screen and (min-width: 769px) and (max-width: 992px) {
            .masonry { column-count: 4; }
            .gallery-container { padding: 0 16px; }
        }
        @media screen and (min-width: 993px) and (max-width: 1200px) {
            .masonry { column-count: 5; }
            .gallery-container { padding: 0 20px; }
        }
        @media screen and (min-width: 1201px) and (max-width: 1600px) {
            .masonry { column-count: 6; }
        }
        @media screen and (min-width: 1601px) and (max-width: 1920px) {
            .masonry { column-count: 8; }
        }
        @media screen and (min-width: 1921px) {
            .masonry { column-count: 10; }
        }

        /* Touch device optimizations */
        @media (hover: none) and (pointer: coarse) {
            .gallery-header {
                padding: 48px 24px;
                font-size: 42px;
            }
            .gallery-container {
                padding: 15px;
                margin: 0 auto;
                display: flex;
                justify-content: center;
            }
            .masonry {
                column-count: 2 !important;
                column-gap: 15px;
                max-width: 800px;
            }
            .masonry img {
                margin-bottom: 15px;
                border-radius: 12px;
                -webkit-tap-highlight-color: transparent;
            }
            /* Hide desktop controls on mobile */
            .controls-container {
                display: none !important;
            }
            /* Only force 2 columns if it's also a small screen */
            @media (max-width: 576px) {
                .masonry {
                    column-count: 2 !important;
                }
            }
        }

        /* Custom scrollbar styles */
        ::-webkit-scrollbar {
            width: 12px;
            background: #333;
        }
        ::-webkit-scrollbar-thumb {
            background: #666;
            border-radius: 6px;
            border: 2px solid #333;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #888;
        }

        /* Image viewer styles */
        .viewer-header {
            padding: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(0,0,0,0.4);
            backdrop-filter: blur(10px);
            flex-wrap: wrap;
            gap: 8px;
        }
        .viewer-title {
            font-size: 1.2rem;
            margin: 0;
            word-break: break-all;
        }
        .viewer-buttons {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        .viewer-buttons button {
            padding: 8px 16px;
            font-size: 1rem;
            border-radius: 4px;
            border: none;
            background: #444;
            color: #fff;
            cursor: pointer;
            text-decoration: none;
            white-space: nowrap;
            min-width: 44px;
            min-height: 44px;
            touch-action: manipulation;
        }
        .viewer-buttons button:hover {
            background: #666;
        }
        @media (max-width: 600px) {
            .viewer-header {
                padding: 12px;
            }
            .viewer-title {
                font-size: 1rem;
                width: 100%;
            }
            .viewer-buttons {
                width: 100%;
                justify-content: center;
            }
            .viewer-buttons button {
                padding: 8px 12px;
                font-size: 0.9rem;
            }
        }
        .viewer-content {
            flex: 1;
            overflow: auto;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            -webkit-overflow-scrolling: touch;
            background: rgba(0, 0, 0, 0.9);
        }
        .viewer-img {
            max-width: 100%;
            max-height: calc(100vh - 120px);
            border-radius: 4px;
            box-shadow: none;
            transition: transform 0.2s ease-out;
            touch-action: manipulation;
            background: #222;
            object-fit: contain;
        }
        /* Mobile image viewer styles */
        @media (hover: none) and (pointer: coarse) {
            .viewer-content {
                padding: 0;
                overflow: hidden;
                position: relative;
                width: 100%;
                height: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .viewer-img {
                max-height: 100vh;
                border-radius: 0;
                object-fit: contain;
                transform-origin: center center;
                position: relative;
                flex-shrink: 0;
                transition: none;
            }
            .image-view.mobile {
                background: black;
            }
            .image-view.mobile .viewer-content {
                background: black;
            }
        }
        @media (max-width: 600px) {
            .viewer-content {
                padding: 12px 24px;  /* Added horizontal padding */
            }
            .viewer-img {
                max-height: calc(100vh - 150px);
            }
        }
        @media (max-width: 400px) {
            .viewer-content {
                padding: 8px 16px;  /* Reduced padding for very small screens */
            }
        }
        </style>
        </head>
        <body>
        <div class="gallery-header">
            <h1 class="gallery-title">''' + (self._current_repo_name or 'Image Gallery') + '''</h1>
        </div>
        <div class="gallery-view">
            <div class="gallery-container">
            <div class="masonry">
        '''
        for thumb_url, orig_url in image_pairs:
            filename = orig_url.split('/')[-1]
            html += f'<img src="{thumb_url}" data-orig-url="{orig_url}" data-filename="{filename}" loading="lazy" onclick="showImage(\'{orig_url}\', \'{filename}\')">\n'
        html += '''
            </div>
        </div>
        </div>
        
        <div class="image-view" onclick="if(event.target === this) hideImage()">
            <div class="viewer-header controls-container">
                <h2 class="viewer-title"></h2>
                <div class="viewer-buttons">
                    <button onclick="event.stopPropagation(); downloadImage()">Download</button>
                    <button onclick="event.stopPropagation(); zoomIn()">Zoom In</button>
                    <button onclick="event.stopPropagation(); zoomOut()">Zoom Out</button>
                    <button onclick="event.stopPropagation(); hideImage()">Close</button>
                    <button onclick="openInNewTab()">Open in New Tab</button>
                    <button onclick="backToGallery()">Back to Gallery</button>
                </div>
            </div>
            <div class="viewer-content">
                <img id="viewerImg" class="viewer-img" src="" />
            </div>
        </div>
        
        <script>
            const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
            let longPressTimer = null;
            let currentOrigUrl = null;
            let currentFilename = null;
            let currentScale = 1;
            let currentTranslateX = 0;
            let currentTranslateY = 0;
            let galleryView = document.querySelector('.gallery-view');
            let imageView = document.querySelector('.image-view');
            let viewerImg = document.getElementById('viewerImg');
            let viewerTitle = document.querySelector('.viewer-title');
            
            // Touch gesture variables for pinch-to-zoom
            let initialDistance = 0;
            let initialScale = 1;
            let initialTranslateX = 0;
            let initialTranslateY = 0;
            let isPinching = false;
            let lastTouchTime = 0;
            let touchStartX = 0;
            let touchStartY = 0;
            let lastTouchX = 0;
            let lastTouchY = 0;
            let isPanning = false;
            
            function updateImageTransform() {
                viewerImg.style.transform = `translate(${currentTranslateX}px, ${currentTranslateY}px) scale(${currentScale})`;
            }
            
            function constrainPan() {
                const rect = viewerImg.getBoundingClientRect();
                const containerRect = document.querySelector('.viewer-content').getBoundingClientRect();
                
                // Calculate the scaled dimensions
                const scaledWidth = rect.width * currentScale;
                const scaledHeight = rect.height * currentScale;
                
                // Calculate maximum pan limits
                const maxPanX = Math.max(0, (scaledWidth - containerRect.width) / 2);
                const maxPanY = Math.max(0, (scaledHeight - containerRect.height) / 2);
                
                // Constrain panning
                currentTranslateX = Math.max(-maxPanX, Math.min(maxPanX, currentTranslateX));
                currentTranslateY = Math.max(-maxPanY, Math.min(maxPanY, currentTranslateY));
            }
            
            function showImage(origUrl, filename) {
                currentOrigUrl = origUrl;
                currentFilename = filename;
                currentScale = 1;
                currentTranslateX = 0;
                currentTranslateY = 0;
                
                viewerImg.src = origUrl;
                viewerTitle.textContent = filename;
                imageView.style.display = 'flex';
                
                // Add to browser history for both mobile and desktop
                history.pushState({view: 'image', origUrl: origUrl, filename: filename}, filename, '#image');
                
                if (isMobile) {
                    imageView.classList.add('mobile');
                    document.querySelector('.controls-container').style.display = 'none';
                    // Reset transform for mobile
                    updateImageTransform();
                } else {
                    imageView.classList.remove('mobile');
                    document.querySelector('.controls-container').style.display = 'flex';
                    galleryView.style.display = 'none';
                }
            }
            
            function hideImage() {
                imageView.style.display = 'none';
                currentOrigUrl = null;
                currentFilename = null;
                currentScale = 1;
                currentTranslateX = 0;
                currentTranslateY = 0;
                updateImageTransform();
            }
            
            function zoomIn() {
                const oldScale = currentScale;
                currentScale = Math.min(currentScale * 1.2, 3);
                
                // Adjust translation to zoom towards center
                const scaleRatio = currentScale / oldScale;
                currentTranslateX *= scaleRatio;
                currentTranslateY *= scaleRatio;
                
                constrainPan();
                updateImageTransform();
            }
            
            function zoomOut() {
                const oldScale = currentScale;
                currentScale = Math.max(currentScale / 1.2, 0.5);
                
                // Adjust translation to zoom towards center
                const scaleRatio = currentScale / oldScale;
                currentTranslateX *= scaleRatio;
                currentTranslateY *= scaleRatio;
                
                constrainPan();
                updateImageTransform();
            }

            function downloadImage() {
                if (currentOrigUrl && currentFilename) {
                    // Call the Python backend to handle download
                    if (window.backend) {
                        window.backend.downloadImage(currentOrigUrl, currentFilename);
                    }
                }
            }

            function backToGallery() {
                imageView.style.display = 'none';
                galleryView.style.display = 'block';
                viewerImg.src = '';
                currentOrigUrl = null;
                currentFilename = null;
                currentScale = 1;
                currentTranslateX = 0;
                currentTranslateY = 0;
                updateImageTransform();
                
                // Update browser history to go back to gallery
                if (history.state && history.state.view === 'image') {
                    history.back();
                }
            }

            function openInNewTab() {
                if (currentOrigUrl) {
                    window.open(currentOrigUrl, '_blank');
                }
            }

            // Calculate distance between two touch points
            function getDistance(touch1, touch2) {
                const dx = touch1.clientX - touch2.clientX;
                const dy = touch1.clientY - touch2.clientY;
                return Math.sqrt(dx * dx + dy * dy);
            }

            // Calculate center point between two touches
            function getTouchCenter(touch1, touch2) {
                return {
                    x: (touch1.clientX + touch2.clientX) / 2,
                    y: (touch1.clientY + touch2.clientY) / 2
                };
            }

            // Touch event handlers for pinch-to-zoom and pan
            function handleTouchStart(e) {
                if (e.touches.length === 2) {
                    // Two finger touch - start pinch gesture
                    isPinching = true;
                    isPanning = false;
                    initialDistance = getDistance(e.touches[0], e.touches[1]);
                    initialScale = currentScale;
                    initialTranslateX = currentTranslateX;
                    initialTranslateY = currentTranslateY;
                    
                    const center = getTouchCenter(e.touches[0], e.touches[1]);
                    const rect = viewerImg.getBoundingClientRect();
                    const containerRect = document.querySelector('.viewer-content').getBoundingClientRect();
                    
                    // Calculate touch point relative to image center
                    touchStartX = center.x - (rect.left + rect.width / 2);
                    touchStartY = center.y - (rect.top + rect.height / 2);
                    
                    e.preventDefault();
                } else if (e.touches.length === 1) {
                    // Single touch - start panning or double tap
                    isPanning = true;
                    isPinching = false;
                    lastTouchX = e.touches[0].clientX;
                    lastTouchY = e.touches[0].clientY;
                    
                    const now = Date.now();
                    if (now - lastTouchTime < 300) {
                        // Double tap detected
                        if (currentScale > 1) {
                            // Reset zoom
                            currentScale = 1;
                            currentTranslateX = 0;
                            currentTranslateY = 0;
                        } else {
                            // Zoom in to double tap point
                            const rect = viewerImg.getBoundingClientRect();
                            const containerRect = document.querySelector('.viewer-content').getBoundingClientRect();
                            
                            // Calculate zoom center relative to image
                            const zoomCenterX = e.touches[0].clientX - (rect.left + rect.width / 2);
                            const zoomCenterY = e.touches[0].clientY - (rect.top + rect.height / 2);
                            
                            // Zoom in
                            currentScale = 2;
                            
                            // Adjust translation to zoom towards touch point
                            currentTranslateX = -zoomCenterX * (currentScale - 1);
                            currentTranslateY = -zoomCenterY * (currentScale - 1);
                            
                            constrainPan();
                        }
                        updateImageTransform();
                        e.preventDefault();
                    }
                    lastTouchTime = now;
                }
            }

            function handleTouchMove(e) {
                if (isPinching && e.touches.length === 2) {
                    // Continue pinch gesture
                    const currentDistance = getDistance(e.touches[0], e.touches[1]);
                    const scale = currentDistance / initialDistance;
                    const newScale = Math.max(0.5, Math.min(3, initialScale * scale));
                    
                    // Calculate zoom center
                    const center = getTouchCenter(e.touches[0], e.touches[1]);
                    const rect = viewerImg.getBoundingClientRect();
                    const containerRect = document.querySelector('.viewer-content').getBoundingClientRect();
                    
                    // Calculate touch point relative to image center
                    const touchX = center.x - (rect.left + rect.width / 2);
                    const touchY = center.y - (rect.top + rect.height / 2);
                    
                    // Calculate scale change
                    const scaleChange = newScale / currentScale;
                    
                    // Adjust translation to zoom towards touch point
                    currentTranslateX = touchX - (touchX - currentTranslateX) * scaleChange;
                    currentTranslateY = touchY - (touchY - currentTranslateY) * scaleChange;
                    
                    currentScale = newScale;
                    constrainPan();
                    updateImageTransform();
                    
                    e.preventDefault();
                } else if (isPanning && e.touches.length === 1 && currentScale > 1) {
                    // Pan the image
                    const deltaX = e.touches[0].clientX - lastTouchX;
                    const deltaY = e.touches[0].clientY - lastTouchY;
                    
                    currentTranslateX += deltaX;
                    currentTranslateY += deltaY;
                    
                    constrainPan();
                    updateImageTransform();
                    
                    lastTouchX = e.touches[0].clientX;
                    lastTouchY = e.touches[0].clientY;
                    
                    e.preventDefault();
                }
            }

            function handleTouchEnd(e) {
                if (isPinching) {
                    // End pinch gesture
                    isPinching = false;
                    initialDistance = 0;
                    initialScale = 1;
                }
                if (isPanning) {
                    // End panning
                    isPanning = false;
                }
            }

            // Handle browser back button for both mobile and desktop
            window.addEventListener('popstate', function(e) {
                if (imageView.style.display === 'flex') {
                    hideImage();
                    // Show gallery view on desktop
                    if (!isMobile) {
                        galleryView.style.display = 'block';
                    }
                }
            });

            // Set up mobile-specific handlers
            if (isMobile) {
                document.addEventListener('DOMContentLoaded', function() {
                    const images = document.querySelectorAll('.masonry img');
                    
                    images.forEach(img => {
                        // Handle long press for download
                        img.addEventListener('touchstart', function(e) {
                            const origUrl = this.getAttribute('data-orig-url');
                            const filename = this.getAttribute('data-filename');
                            
                            longPressTimer = setTimeout(() => {
                                e.preventDefault();
                                if (window.backend) {
                                    window.backend.downloadImage(origUrl, filename);
                                }
                            }, 800);
                        });

                        img.addEventListener('touchend', function() {
                            if (longPressTimer) {
                                clearTimeout(longPressTimer);
                            }
                        });

                        img.addEventListener('touchmove', function() {
                            if (longPressTimer) {
                                clearTimeout(longPressTimer);
                            }
                        });
                    });

                    // Add touch event listeners to the image viewer for pinch-to-zoom and pan
                    viewerImg.addEventListener('touchstart', handleTouchStart, { passive: false });
                    viewerImg.addEventListener('touchmove', handleTouchMove, { passive: false });
                    viewerImg.addEventListener('touchend', handleTouchEnd, { passive: false });
                });
            }

            document.addEventListener('keydown', function(e) {
                if (imageView.style.display === 'flex') {
                    if (e.key === 'Escape') hideImage();
                    if (e.key === '+') zoomIn();
                    if (e.key === '-') zoomOut();
                }
            });
        </script>
        </body></html>
        '''
        # Store the generated HTML
        self._current_gallery_html = html
        return html

    def save_gallery_as_html(self):
        """Save the current gallery view as a standalone HTML file"""
        if not self._current_gallery_html or not self._current_repo_name:
            QMessageBox.warning(self, "Warning", "No gallery is currently loaded.")
            return
            
        try:
            # Create a default filename with timestamp
            default_filename = f"gallery_{self._current_repo_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
            # Show save file dialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Gallery as HTML",
                default_filename,
                "HTML Files (*.html);;All Files (*.*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self._current_gallery_html)
                QMessageBox.information(self, "Success", "Gallery saved successfully!")
                
                # Ask if user wants to open the saved file
                reply = QMessageBox.question(
                    self,
                    "Open File",
                    "Would you like to open the saved gallery in your default browser?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    import webbrowser
                    webbrowser.open(file_path)
                    
        except Exception as e:
            logger.exception("Error saving gallery HTML")
            QMessageBox.critical(self, "Error", f"Failed to save gallery: {str(e)}")

    def handle_repo_double_click(self, item):
        """Handle double-click on repository list item"""
        if item:
            repo = item.data(Qt.ItemDataRole.UserRole)
            if repo:
                # Update cursor to show loading state
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    # Load the repository
                    self._load_images_for_repo(repo['name'])
                finally:
                    # Restore cursor
                    QApplication.restoreOverrideCursor()

class GitHubPagesBuildTracker(QObject):
    build_status_updated = pyqtSignal(str, str)  # status, message
    build_completed = pyqtSignal(bool, str)  # success, url
    finished = pyqtSignal()

    def __init__(self, repo_name):
        super().__init__()
        self.repo_name = repo_name
        self._is_cancelled = False
        self.max_attempts = 60  # 5 minutes with 5-second intervals
        self.attempt_count = 0

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        """Monitor GitHub Pages build status"""
        try:
            headers = {
                'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Wait a bit for the build to start
            import time
            time.sleep(3)
            
            while not self._is_cancelled and self.attempt_count < self.max_attempts:
                try:
                    # Check GitHub Pages status
                    pages_url = f'https://api.github.com/repos/lifetime-memories/{self.repo_name}/pages'
                    response = requests.get(pages_url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        pages_data = response.json()
                        status = pages_data.get('status', 'unknown')
                        build_type = pages_data.get('build_type', 'unknown')
                        
                        if status == 'built':
                            # Build completed successfully
                            site_url = pages_data.get('html_url', f'https://lifetime-memories.github.io/{self.repo_name}')
                            self.build_status_updated.emit('success', f'Build completed successfully!')
                            self.build_completed.emit(True, site_url)
                            break
                        elif status == 'building':
                            # Still building
                            self.build_status_updated.emit('building', f'Building site... (attempt {self.attempt_count + 1}/{self.max_attempts})')
                        elif status == 'errored':
                            # Build failed
                            error_msg = pages_data.get('error', {}).get('message', 'Unknown build error')
                            self.build_status_updated.emit('error', f'Build failed: {error_msg}')
                            self.build_completed.emit(False, '')
                            break
                        elif status == 'not_built':
                            # Not built yet
                            self.build_status_updated.emit('waiting', f'Waiting for build to start... (attempt {self.attempt_count + 1}/{self.max_attempts})')
                        else:
                            # Unknown status
                            self.build_status_updated.emit('unknown', f'Unknown build status: {status}')
                    
                    elif response.status_code == 404:
                        # GitHub Pages not enabled or not found
                        self.build_status_updated.emit('error', 'GitHub Pages not found or not enabled')
                        self.build_completed.emit(False, '')
                        break
                    else:
                        # API error
                        self.build_status_updated.emit('error', f'API error: {response.status_code}')
                        self.build_completed.emit(False, '')
                        break
                        
                except requests.exceptions.RequestException as e:
                    self.build_status_updated.emit('error', f'Network error: {str(e)}')
                    self.build_completed.emit(False, '')
                    break
                
                self.attempt_count += 1
                time.sleep(5)  # Wait 5 seconds before next check
            
            # If we've exhausted all attempts
            if self.attempt_count >= self.max_attempts and not self._is_cancelled:
                self.build_status_updated.emit('timeout', 'Build status check timed out. Please check manually.')
                self.build_completed.emit(False, '')
                
        except Exception as e:
            logger.exception(f"Error in GitHub Pages build tracker: {e}")
            self.build_status_updated.emit('error', f'Tracker error: {str(e)}')
            self.build_completed.emit(False, '')
        finally:
            self.finished.emit()

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