from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QLabel, QScrollArea, QFrame, QGridLayout,
                            QMessageBox, QFileDialog, QProgressBar, QSizePolicy)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QFont
import requests
import os
from PIL import Image
import io
import base64
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

class ImageUploadThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, repo_name, image_paths):
        super().__init__()
        self.repo_name = repo_name
        self.image_paths = image_paths

    def run(self):
        try:
            logger.info(f"Starting image upload for {len(self.image_paths)} images to {self.repo_name}")
            headers = {
                'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
                'Accept': 'application/vnd.github.v3+json'
            }

            for i, image_path in enumerate(self.image_paths):
                logger.info(f"Processing image {i+1}/{len(self.image_paths)}: {image_path}")
                # Process image
                with Image.open(image_path) as img:
                    # Create thumbnail
                    img.thumbnail((200, 200))
                    thumb_buffer = io.BytesIO()
                    img.save(thumb_buffer, format='JPEG', quality=85)
                    thumb_data = base64.b64encode(thumb_buffer.getvalue()).decode()

                    # Get original image data
                    with open(image_path, 'rb') as f:
                        orig_data = base64.b64encode(f.read()).decode()

                    # Upload both original and thumbnail
                    filename = os.path.basename(image_path)
                    files = [
                        {'path': filename, 'content': orig_data},
                        {'path': f'thumbnails/{filename}', 'content': thumb_data}
                    ]

                    for file in files:
                        logger.info(f"Uploading {file['path']}")
                        response = requests.put(
                            f'https://api.github.com/repos/lifetime-memories/{self.repo_name}/contents/{file["path"]}',
                            headers=headers,
                            json={
                                'message': f'Upload {file["path"]}',
                                'content': file['content']
                            }
                        )
                        if response.status_code not in [201, 200]:
                            error_msg = f"Failed to upload {file['path']}. Status code: {response.status_code}"
                            logger.error(error_msg)
                            raise Exception(error_msg)

                self.progress.emit(int((i + 1) / len(self.image_paths) * 100))

            logger.info("Image upload completed successfully")
            self.finished.emit()

        except Exception as e:
            logger.exception("Error during image upload")
            self.error.emit(str(e))

class RepositoryView(QMainWindow):
    def __init__(self, repo_name):
        super().__init__()
        logger.info(f"Initializing RepositoryView for {repo_name}")
        self.repo_name = repo_name
        self.setWindowTitle(f"Repository: {repo_name}")
        self.setMinimumSize(1200, 800)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create header
        header = QFrame()
        header.setFixedHeight(70)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        
        # Title
        title = QLabel(f"Repository: {repo_name}")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        # Add a stretch to push upload button to the right
        header_layout.addStretch()
        
        # Upload button
        upload_btn = QPushButton("Upload Images")
        upload_btn.setFixedSize(150, 40) # Adjusted size
        upload_btn.clicked.connect(self.upload_images)
        header_layout.addWidget(upload_btn)
        
        main_layout.addWidget(header)
        
        # Create scroll area for images
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("border: none;") # Remove border
        
        # Create container for image grid
        self.image_container = QWidget()
        self.image_grid = QGridLayout(self.image_container)
        self.image_grid.setContentsMargins(10, 10, 10, 10) # Added margins
        self.image_grid.setSpacing(15) # Reduced spacing
        
        scroll.setWidget(self.image_container)
        main_layout.addWidget(scroll)
        
        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Load images
        self.load_images()

    def create_image_card(self, thumb):
        card = QFrame()
        # Remove fixed size, let layout manage it
        # card.setMinimumSize(250, 250)
        card.setStyleSheet("border: 1px solid #cccccc; border-radius: 5px; background-color: #f9f9f9;") # Added border and background
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center content vertically and horizontally
        
        # Image
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Remove fixed minimum size, let scaled pixmap determine size hint
        # image_label.setMinimumSize(200, 200)
        image_label.setStyleSheet("background-color: #e0e0e0;")  # Slightly darker gray background
        
        try:
            # Load image from URL
            logger.info(f"Loading image: {thumb['name']} from {thumb['download_url']}")
            response = requests.get(thumb['download_url'])
            if response.status_code == 200:
                image = QImage.fromData(response.content)
                if not image.isNull():
                    pixmap = QPixmap.fromImage(image)
                    # Scale pixmap to fit within a reasonable size while maintaining aspect ratio
                    scaled_pixmap = pixmap.scaled(220, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    image_label.setPixmap(scaled_pixmap)
                    # Adjust the size of the QLabel to fit the scaled pixmap
                    image_label.setFixedSize(scaled_pixmap.size())
                    logger.info(f"Successfully loaded image: {thumb['name']}")
                else:
                    logger.error(f"Failed to create QImage from data for {thumb['name']}")
                    image_label.setText("Failed to load image")
                    # Set a fixed size for failed load case
                    image_label.setFixedSize(220, 220)
            else:
                logger.error(f"Failed to download image {thumb['name']}. Status code: {response.status_code}")
                image_label.setText("Failed to load image")
                # Set a fixed size for failed download case
                image_label.setFixedSize(220, 220)
        except Exception as e:
            logger.exception(f"Error loading image {thumb['name']}")
            image_label.setText("Error loading image")
            # Set a fixed size for error case
            image_label.setFixedSize(220, 220)
        
        layout.addWidget(image_label)
        
        # Image name
        name_label = QLabel(thumb['name'])
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Optional: style the name label
        # name_label.setStyleSheet("font-size: 10px; color: #555555;")
        layout.addWidget(name_label)
        
        # Adjust card size based on its content
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # Ensure the card's size hint reflects its content
        card.adjustSize()
        
        return card

    def load_images(self):
        try:
            logger.info(f"Loading images for repository: {self.repo_name}")
            headers = {
                'Authorization': f"token {os.getenv('GITHUB_TOKEN')}",
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Clear existing images
            for i in reversed(range(self.image_grid.count())): 
                self.image_grid.itemAt(i).widget().setParent(None)
            
            # Fetch thumbnails
            response = requests.get(
                f'https://api.github.com/repos/lifetime-memories/{self.repo_name}/contents/thumbnails',
                headers=headers
            )
            
            if response.status_code == 200:
                thumbnails = response.json()
                logger.info(f"Found {len(thumbnails)} images")
                self.display_images(thumbnails)
            elif response.status_code == 404:
                logger.info("No images found in repository")
                empty_label = QLabel("No images uploaded yet. Click 'Upload Images' to add some!")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.image_grid.addWidget(empty_label, 0, 0)
            else:
                error_msg = f"Failed to load images. Status code: {response.status_code}"
                logger.error(error_msg)
                QMessageBox.critical(self, "Error", error_msg)
                
        except Exception as e:
            logger.exception("Error while loading images")
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def display_images(self, thumbnails):
        logger.info("Displaying images in grid")
        row = 0
        col = 0
        max_cols = 4  # Maximum number of columns in the grid
        
        for thumb in thumbnails:
            if thumb['type'] == 'file':
                logger.info(f"Creating card for image: {thumb['name']}")
                image_card = self.create_image_card(thumb)
                self.image_grid.addWidget(image_card, row, col)
                
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

    def upload_images(self):
        logger.info("Opening file dialog for image upload")
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter("Images (*.png *.jpg *.jpeg)")
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            logger.info(f"Selected {len(selected_files)} files for upload")
            
            # Show progress bar
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Create and start upload thread
            self.upload_thread = ImageUploadThread(self.repo_name, selected_files)
            self.upload_thread.progress.connect(self.update_progress)
            self.upload_thread.finished.connect(self.upload_finished)
            self.upload_thread.error.connect(self.upload_error)
            self.upload_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def upload_finished(self):
        logger.info("Upload completed successfully")
        self.progress_bar.setVisible(False)
        self.load_images()
        QMessageBox.information(self, "Success", "Images uploaded successfully")

    def upload_error(self, error_msg):
        logger.error(f"Upload failed: {error_msg}")
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Error", f"Upload failed: {error_msg}") 