from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QProgressBar, QFrame, QScrollArea,
                            QSizePolicy, QSpacerItem, QToolButton, QMenu)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon, QPixmap
import logging

logger = logging.getLogger(__name__)

class AnimatedProgressBar(QProgressBar):
    """Enhanced progress bar with animations"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._animation = QPropertyAnimation(self, b"value")
        self._animation.setDuration(300)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Enhanced styling
        self.setStyleSheet("""
            QProgressBar {
                border: 2px solid #444;
                border-radius: 8px;
                background: #2a2a2a;
                text-align: center;
                font-weight: bold;
                color: #fff;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:0.5 #8BC34A, stop:1 #4CAF50);
                border-radius: 6px;
                margin: 1px;
            }
        """)
    
    def setValue(self, value):
        """Animate to the new value"""
        self._animation.setStartValue(self.value())
        self._animation.setEndValue(value)
        self._animation.start()

class StatusBar(QFrame):
    """Enhanced status bar with multiple indicators"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(40)
        self.setStyleSheet("""
            StatusBar {
                background: #2a2a2a;
                border-top: 1px solid #444;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)
        
        # Status indicators
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #ccc; font-size: 11px;")
        
        self.progress_bar = AnimatedProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        
        # Rate limit indicator
        self.rate_limit_label = QLabel("Rate Limit: --")
        self.rate_limit_label.setStyleSheet("color: #888; font-size: 10px;")
        
        # Cache indicator
        self.cache_label = QLabel("Cache: --")
        self.cache_label.setStyleSheet("color: #888; font-size: 10px;")
        
        # Add widgets to layout
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addStretch()
        layout.addWidget(self.rate_limit_label)
        layout.addWidget(self.cache_label)
    
    def set_status(self, message: str, show_progress: bool = False):
        """Set status message and show/hide progress bar"""
        self.status_label.setText(message)
        self.progress_bar.setVisible(show_progress)
    
    def set_progress(self, value: int, format_str: str = None):
        """Set progress bar value and format"""
        self.progress_bar.setValue(value)
        if format_str:
            self.progress_bar.setFormat(format_str)
    
    def update_rate_limit(self, remaining: int, reset_time: str):
        """Update rate limit display"""
        color = "green" if remaining > 100 else "orange" if remaining > 10 else "red"
        self.rate_limit_label.setText(f"Rate Limit: {remaining}")
        self.rate_limit_label.setStyleSheet(f"color: {color}; font-size: 10px;")
    
    def update_cache_stats(self, stats: dict):
        """Update cache statistics display"""
        if stats.get('cache_enabled'):
            valid = stats.get('valid_items', 0)
            total = stats.get('total_items', 0)
            self.cache_label.setText(f"Cache: {valid}/{total}")
        else:
            self.cache_label.setText("Cache: Disabled")

class EnhancedButton(QPushButton):
    """Enhanced button with hover effects and animations"""
    
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setup_style()
    
    def setup_style(self):
        """Setup enhanced button styling"""
        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a4a4a, stop:1 #3a3a3a);
                border: 1px solid #555;
                border-radius: 6px;
                padding: 8px 16px;
                color: #fff;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5a5a5a, stop:1 #4a4a4a);
                border: 1px solid #666;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a3a3a, stop:1 #2a2a2a);
                border: 1px solid #444;
            }
            QPushButton:disabled {
                background: #2a2a2a;
                border: 1px solid #333;
                color: #666;
            }
        """)

class PrimaryButton(EnhancedButton):
    """Primary action button with blue styling"""
    
    def setup_style(self):
        """Setup primary button styling"""
        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2196F3, stop:1 #1976D2);
                border: 1px solid #1976D2;
                border-radius: 6px;
                padding: 8px 16px;
                color: #fff;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #42A5F5, stop:1 #2196F3);
                border: 1px solid #2196F3;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1976D2, stop:1 #1565C0);
                border: 1px solid #1565C0;
            }
            QPushButton:disabled {
                background: #2a2a2a;
                border: 1px solid #333;
                color: #666;
            }
        """)

class DangerButton(EnhancedButton):
    """Danger action button with red styling"""
    
    def setup_style(self):
        """Setup danger button styling"""
        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f44336, stop:1 #d32f2f);
                border: 1px solid #d32f2f;
                border-radius: 6px;
                padding: 8px 16px;
                color: #fff;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ef5350, stop:1 #f44336);
                border: 1px solid #f44336;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #d32f2f, stop:1 #c62828);
                border: 1px solid #c62828;
            }
            QPushButton:disabled {
                background: #2a2a2a;
                border: 1px solid #333;
                color: #666;
            }
        """)

class ImageCard(QFrame):
    """Enhanced image card with hover effects"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_style()
        self.setup_layout()
    
    def setup_style(self):
        """Setup image card styling"""
        self.setStyleSheet("""
            ImageCard {
                background: #2a2a2a;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 8px;
            }
            ImageCard:hover {
                background: #3a3a3a;
                border: 1px solid #666;
                transform: translateY(-2px);
            }
        """)
        self.setMaximumSize(250, 300)
    
    def setup_layout(self):
        """Setup image card layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Image placeholder
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(200, 200)
        self.image_label.setStyleSheet("""
            QLabel {
                background: #1a1a1a;
                border: 1px solid #333;
                border-radius: 4px;
                color: #666;
            }
        """)
        self.image_label.setText("Loading...")
        
        # Image info
        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #ccc; font-size: 11px;")
        self.info_label.setWordWrap(True)
        
        layout.addWidget(self.image_label)
        layout.addWidget(self.info_label)
    
    def set_image(self, pixmap: QPixmap):
        """Set the image for the card"""
        if pixmap and not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setStyleSheet("""
                QLabel {
                    background: transparent;
                    border: none;
                }
            """)
        else:
            self.image_label.setText("Failed to load")
            self.image_label.setStyleSheet("""
                QLabel {
                    background: #1a1a1a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    color: #f44336;
                }
            """)
    
    def set_info(self, text: str):
        """Set the info text for the card"""
        self.info_label.setText(text)

class LoadingSpinner(QWidget):
    """Animated loading spinner"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.rotate)
        self.setup_style()
    
    def setup_style(self):
        """Setup spinner styling"""
        self.setFixedSize(32, 32)
        self.setStyleSheet("""
            LoadingSpinner {
                background: transparent;
            }
        """)
    
    def start(self):
        """Start the spinner animation"""
        self.timer.start(50)  # 20 FPS
        self.show()
    
    def stop(self):
        """Stop the spinner animation"""
        self.timer.stop()
        self.hide()
    
    def rotate(self):
        """Rotate the spinner"""
        self.angle = (self.angle + 30) % 360
        self.update()
    
    def paintEvent(self, event):
        """Custom paint event for spinner"""
        from PyQt6.QtGui import QPainter, QPen
        from PyQt6.QtCore import QRect
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw spinner
        pen = QPen(QColor("#2196F3"), 3)
        painter.setPen(pen)
        
        rect = QRect(4, 4, 24, 24)
        painter.drawArc(rect, self.angle * 16, 120 * 16)

class ToolbarWidget(QFrame):
    """Enhanced toolbar with better organization"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_style()
        self.setup_layout()
    
    def setup_style(self):
        """Setup toolbar styling"""
        self.setStyleSheet("""
            ToolbarWidget {
                background: #2a2a2a;
                border-bottom: 1px solid #444;
                padding: 8px;
            }
        """)
        self.setMaximumHeight(60)
    
    def setup_layout(self):
        """Setup toolbar layout"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Left side - main actions
        self.left_widget = QWidget()
        self.left_layout = QHBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(8)
        
        # Right side - secondary actions
        self.right_widget = QWidget()
        self.right_layout = QHBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(8)
        
        layout.addWidget(self.left_widget)
        layout.addStretch()
        layout.addWidget(self.right_widget)
    
    def add_left_button(self, button: QPushButton):
        """Add button to left side of toolbar"""
        self.left_layout.addWidget(button)
    
    def add_right_button(self, button: QPushButton):
        """Add button to right side of toolbar"""
        self.right_layout.addWidget(button)
    
    def add_left_widget(self, widget: QWidget):
        """Add widget to left side of toolbar"""
        self.left_layout.addWidget(widget)
    
    def add_right_widget(self, widget: QWidget):
        """Add widget to right side of toolbar"""
        self.right_layout.addWidget(widget) 