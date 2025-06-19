import sys
import os
import logging
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QScrollArea, 
                            QFrame, QGridLayout, QMessageBox, QFileDialog,
                            QLineEdit, QDialog, QListWidget, QListWidgetItem, 
                            QSplitter, QSizePolicy, QMenu, QProgressBar, QTableWidget, QTableWidgetItem)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QFont, QColor, QPalette, QPixmap, QImage
import requests
import json
import io
import base64
from PIL import Image
from dotenv import load_dotenv
# Removed RepositoryView import
# from repository_view import RepositoryView

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
    image_loaded = pyqtSignal(int, QPixmap, str)  # index, pixmap, name
    finished = pyqtSignal()

    def __init__(self, thumbnails):
        super().__init__()
        self.thumbnails = thumbnails

    def run(self):
        for idx, thumb in enumerate(self.thumbnails):
            if thumb['type'] == 'file':
                try:
                    response = requests.get(thumb['download_url'])
                    if response.status_code == 200:
                        image = QImage.fromData(response.content)
                        if not image.isNull():
                            w, h = image.width(), image.height()
                            side = min(w, h)
                            x = (w - side) // 2
                            y = (h - side) // 2
                            cropped = image.copy(x, y, side, side)
                            pixmap = QPixmap.fromImage(cropped)
                            scaled_pixmap = pixmap.scaled(220, 220, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                            self.image_loaded.emit(idx, scaled_pixmap, thumb['name'])
                        else:
                            self.image_loaded.emit(idx, None, thumb['name'])
                    else:
                        self.image_loaded.emit(idx, None, thumb['name'])
                except Exception:
                    self.image_loaded.emit(idx, None, thumb['name'])
        self.finished.emit()

# Placeholder for the image viewer widget
class ImageViewerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo_name = None
        self._thumbnails = []  # Store thumbnails for responsive layout
        self._image_cards = []

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
        self.image_grid = QGridLayout(self.image_container)
        self.scroll_area.setWidget(self.image_container)

        # Placeholder label
        self.placeholder_label = QLabel("Select a repository and right-click to load images.")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.placeholder_label)
        self.placeholder_label.raise_()

        # Ensure the widget expands to fill the splitter panel
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._thumbnails:
            self._relayout_images()

    def load_images(self, repo_name):
        logger.info(f"ImageViewerWidget received request to load images for: {repo_name}")
        
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
        for i in reversed(range(self.image_grid.count())): 
            widget = self.image_grid.itemAt(i).widget()
            if widget:
                widget.deleteLater()
                
        self.repo_name = repo_name
        self._thumbnails = []

        if not repo_name:
            # If repo_name is None or empty, show placeholder and hide scroll area
            self.placeholder_label.setText("Select a repository and right-click to load images.")
            self.placeholder_label.setVisible(True)
            self.scroll_area.setVisible(False)
            self.layout.addWidget(self.placeholder_label) # Add back to layout
            self.placeholder_label.raise_() # Bring to front
            logger.info("ImageViewerWidget cleared and showing placeholder.")
            return

        # Add a temporary loading message to the grid
        loading_label = QLabel(f"Loading images for {repo_name}...")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_grid.addWidget(loading_label, 0, 0)
        self.image_container.update() # Update to show loading message

        try:
            logger.info(f"Loading images for repository: {self.repo_name}")
            headers = {
                'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Fetch thumbnails
            response = requests.get(
                f'https://api.github.com/repos/lifetime-memories/{self.repo_name}/contents/thumbnails',
                headers=headers
            )
            
            # Clear the temporary loading message
            for i in reversed(range(self.image_grid.count())): 
                 widget = self.image_grid.itemAt(i).widget()
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
                    self.image_grid.addWidget(empty_label, 0, 0)
                    self._thumbnails = []

            elif response.status_code == 404:
                logger.info("Thumbnails directory not found, no images to display.")
                empty_label = QLabel("No images uploaded yet. Right-click and select 'Upload Images' to add some!")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.image_grid.addWidget(empty_label, 0, 0)
                self._thumbnails = []

            else:
                error_msg = f"Failed to load images. Status code: {response.status_code}"
                logger.error(error_msg)
                error_label = QLabel(f"Error loading images: {response.status_code}")
                error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.image_grid.addWidget(error_label, 0, 0)
                QMessageBox.critical(self.parentWidget(), "Error", error_msg)
                
        except Exception as e:
            # Clear the temporary loading message in case of exception
            for i in reversed(range(self.image_grid.count())): 
                 widget = self.image_grid.itemAt(i).widget()
                 if widget and isinstance(widget, QLabel) and "Loading images for" in widget.text():
                     widget.deleteLater()
                     break

            logger.exception("Error while loading images")
            error_label = QLabel(f"An error occurred: {str(e)}")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.image_grid.addWidget(error_label, 0, 0)
            QMessageBox.critical(self.parentWidget(), "Error", f"An error occurred: {str(e)}")
            self._thumbnails = []

        self.image_container.update() # Force update after loading/error

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
        # Responsive: calculate columns based on available width
        card_width = 140  # Card width (image + padding + label)
        spacing = self.image_grid.horizontalSpacing() or 10
        available_width = self.scroll_area.viewport().width()
        max_cols = max(1, available_width // (card_width + spacing))
        row = 0
        col = 0
        for idx, thumb in enumerate(thumbnails):
            if thumb['type'] == 'file':
                card = QFrame()
                layout = QVBoxLayout(card)
                layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                image_container = QFrame()
                image_container.setFixedSize(120, 120)
                image_layout = QVBoxLayout(image_container)
                image_label = QLabel()
                image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                image_layout.addWidget(image_label)
                layout.addWidget(image_container)
                name_label = QLabel(thumb['name'])
                name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_label.setWordWrap(True)
                name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                layout.addWidget(name_label)
                card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                card.adjustSize()
                self.image_grid.addWidget(card, row, col)
                self._image_cards.append((image_label, name_label))
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
        # Stretch columns to fill
        for col_idx in range(max_cols):
            self.image_grid.setColumnStretch(col_idx, 1)
        # Start worker thread
        self._loader_thread = QThread()
        self._loader_worker = ImageLoaderWorker(thumbnails)
        self._loader_worker.moveToThread(self._loader_thread)
        self._loader_thread.started.connect(self._loader_worker.run)
        self._loader_worker.image_loaded.connect(self._on_image_loaded)
        self._loader_worker.finished.connect(self._loader_thread.quit)
        self._loader_worker.finished.connect(self._loader_worker.deleteLater)
        self._loader_thread.finished.connect(self._loader_thread.deleteLater)
        self._loader_thread.start()

    def _on_image_loaded(self, idx, pixmap, name):
        if 0 <= idx < len(self._image_cards):
            image_label, name_label = self._image_cards[idx]
            if pixmap:
                image_label.setPixmap(pixmap)
            else:
                image_label.setText("Failed to load image")

    def _clear_image_grid(self):
        for i in reversed(range(self.image_grid.count())):
            widget = self.image_grid.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self._image_cards = []


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
        
        # add button layout to main layout
        main_layout.addLayout(button_layout)
        
        # Create splitter for left and right panes and make it 20:80 ratio
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left pane: Repository list
        self.repo_list = QListWidget()
        self.repo_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.repo_list.customContextMenuRequested.connect(self.show_repo_context_menu)
        splitter.addWidget(self.repo_list)
        
        # Right pane: Image list (replaces image viewer)
        self.image_table = QTableWidget()
        self.image_table.setColumnCount(5)
        self.image_table.setHorizontalHeaderLabels(["Name", "Size (KB)", "Orig Size (KB)", "SHA", "Date"])
        self.image_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.image_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.image_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        # Make table compact
        compact_font = QFont()
        compact_font.setPointSize(9)
        self.image_table.setFont(compact_font)
        self.image_table.verticalHeader().setDefaultSectionSize(22)
        #self.image_table.setShowGrid(False)
        self.image_table.setWordWrap(False)
        header_font = QFont()
        header_font.setPointSize(9)
        self.image_table.horizontalHeader().setFont(header_font)
        self.image_table.horizontalHeader().setMinimumHeight(22)
        # Add a progress bar below the image list
        self.upload_progress = QProgressBar()
        self.upload_progress.setVisible(True)
        self.upload_progress.setMinimum(0)
        self.upload_progress.setMaximum(100)
        self.upload_progress.setValue(0)
        self.upload_progress.setFormat('Idle')
        # Right pane layout
        right_pane = QVBoxLayout()
        right_pane.addWidget(self.image_table)
        right_pane.addWidget(self.upload_progress)
        right_widget = QWidget()
        right_widget.setLayout(right_pane)
        splitter.addWidget(right_widget)
        
        # Set stretch factors to maintain 20:80 ratio
        splitter.setStretchFactor(0, 2)  # Left pane gets 20%
        splitter.setStretchFactor(1, 8)  # Right pane gets 80%
        
        # add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Initialize repositories
        self.repositories = []
        self.refresh_repositories()

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

    def show_repo_context_menu(self, position):
        item = self.repo_list.itemAt(position)
        if item:
            repo = item.data(Qt.ItemDataRole.UserRole)
            if repo:
                menu = QMenu()
                load_action = menu.addAction("Load Images")
                upload_action = menu.addAction("Upload Images")
                delete_action = menu.addAction("Delete")
                load_action.triggered.connect(lambda: self.load_and_display_images(repo['name']))
                upload_action.triggered.connect(lambda: self.upload_images_to_repo(repo['name']))
                delete_action.triggered.connect(lambda: self.delete_repository(repo['name']))
                menu.exec(self.repo_list.mapToGlobal(position))

    def set_interactive(self, enabled):
        self.repo_list.setEnabled(enabled)
        self.image_table.setEnabled(enabled)
        self.create_repo_btn.setEnabled(enabled)
        # If you have other header buttons, disable them here as well
        # Optionally, disable the main window itself: self.setEnabled(enabled)

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
                            self.image_table.setItem(row, 3, sha_item)
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
                                # If this is the last thread, re-enable UI
                                if row_idx == len(thumbnails) - 1:
                                    self.set_interactive(True)
                            t = threading.Thread(target=fetch_and_set_orig_size_and_date, args=(row, thumb['name']), daemon=True)
                            t.start()
                            threads.append(t)
                            row += 1
                    self.image_table.setRowCount(row)  # In case some are not files
                    self.image_table.resizeColumnsToContents()
                    # If there are no threads (no files), re-enable UI
                    if not threads:
                        self.set_interactive(True)
                else:
                    self.image_table.setRowCount(1)
                    self.image_table.setItem(0, 0, QTableWidgetItem("No images uploaded yet."))
                    self.image_table.setItem(0, 1, QTableWidgetItem(""))
                    self.image_table.setItem(0, 2, QTableWidgetItem(""))
                    self.image_table.setItem(0, 3, QTableWidgetItem(""))
                    self.image_table.setItem(0, 4, QTableWidgetItem(""))
                    self.image_table.resizeColumnsToContents()
                    self.set_interactive(True)
            elif response.status_code == 404:
                self.image_table.setRowCount(1)
                self.image_table.setItem(0, 0, QTableWidgetItem("No images uploaded yet."))
                self.image_table.setItem(0, 1, QTableWidgetItem(""))
                self.image_table.setItem(0, 2, QTableWidgetItem(""))
                self.image_table.setItem(0, 3, QTableWidgetItem(""))
                self.image_table.setItem(0, 4, QTableWidgetItem(""))
                self.image_table.resizeColumnsToContents()
                self.set_interactive(True)
            else:
                error_msg = f"Failed to load images. Status code: {response.status_code}"
                logger.error(error_msg)
                QMessageBox.critical(self, "Error", error_msg)
                self.set_interactive(True)
        except Exception as e:
            logger.exception("Error while loading images")
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
            self.set_interactive(True)

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