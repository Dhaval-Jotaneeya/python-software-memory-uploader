import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Centralized configuration for the application"""
    
    # GitHub API Configuration
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    GITHUB_ORG = 'lifetime-memories'
    GITHUB_API_BASE = 'https://api.github.com'
    
    # Application Settings
    APP_NAME = "Family Websites Repository Manager"
    APP_VERSION = "1.0.0"
    
    # UI Settings
    WINDOW_MIN_WIDTH = 1200
    WINDOW_MIN_HEIGHT = 800
    SPLITTER_RATIOS = {
        'left': 1,      # Repository list
        'center': 2,    # Image table
        'right': 7      # Gallery view
    }
    
    # Image Processing
    THUMBNAIL_SIZE = (200, 200)
    THUMBNAIL_QUALITY = 85
    MAX_WORKERS = 8
    IMAGE_TIMEOUT = 10
    
    # Gallery Settings
    GALLERY_ROW_HEIGHT = 120
    GALLERY_MARGIN = 0
    GALLERY_SPACING = 6
    
    # Rate Limiting
    RATE_LIMIT_WARNING_THRESHOLD = 100
    RATE_LIMIT_CRITICAL_THRESHOLD = 10
    
    # Build Tracking
    BUILD_CHECK_INTERVAL = 5  # seconds
    MAX_BUILD_ATTEMPTS = 60   # 5 minutes total
    
    # File Upload
    SUPPORTED_IMAGE_FORMATS = ['*.jpg', '*.jpeg', '*.png']
    CHUNK_SIZE = 8192
    
    # Logging
    LOG_DIR = "logs"
    LOG_LEVEL = "DEBUG"
    
    # Cache Settings
    CACHE_ENABLED = True
    CACHE_DURATION = 300  # 5 minutes
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.GITHUB_TOKEN:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        return True 