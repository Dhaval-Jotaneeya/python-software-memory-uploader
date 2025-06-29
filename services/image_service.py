import io
import base64
import logging
from typing import Tuple, Optional
from PIL import Image, ImageOps
from config import Config

logger = logging.getLogger(__name__)

class ImageService:
    """Service class for image processing operations"""
    
    @staticmethod
    def load_image_from_bytes(image_bytes: bytes) -> Optional[Image.Image]:
        """Load an image from bytes"""
        try:
            return Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            logger.error(f"Failed to load image from bytes: {e}")
            return None
    
    @staticmethod
    def load_image_from_file(file_path: str) -> Optional[Image.Image]:
        """Load an image from file path"""
        try:
            return Image.open(file_path)
        except Exception as e:
            logger.error(f"Failed to load image from file {file_path}: {e}")
            return None
    
    @staticmethod
    def create_thumbnail(image: Image.Image, size: Tuple[int, int] = None, 
                        quality: int = None) -> Optional[Image.Image]:
        """Create a thumbnail from an image"""
        try:
            if size is None:
                size = Config.THUMBNAIL_SIZE
            if quality is None:
                quality = Config.THUMBNAIL_QUALITY
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Create thumbnail
            thumbnail = image.copy()
            thumbnail.thumbnail(size, Image.LANCZOS)
            
            return thumbnail
        except Exception as e:
            logger.error(f"Failed to create thumbnail: {e}")
            return None
    
    @staticmethod
    def crop_to_square(image: Image.Image) -> Optional[Image.Image]:
        """Crop image to square format"""
        try:
            width, height = image.size
            side = min(width, height)
            left = (width - side) // 2
            top = (height - side) // 2
            right = left + side
            bottom = top + side
            
            return image.crop((left, top, right, bottom))
        except Exception as e:
            logger.error(f"Failed to crop image to square: {e}")
            return None
    
    @staticmethod
    def compress_image(image: Image.Image, quality: int = None) -> Optional[bytes]:
        """Compress image to JPEG format"""
        try:
            if quality is None:
                quality = Config.THUMBNAIL_QUALITY
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save to bytes
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=quality, optimize=True)
            return buffer.getvalue()
        except Exception as e:
            logger.error(f"Failed to compress image: {e}")
            return None
    
    @staticmethod
    def image_to_base64(image_bytes: bytes) -> str:
        """Convert image bytes to base64 string"""
        return base64.b64encode(image_bytes).decode('utf-8')
    
    @staticmethod
    def base64_to_image(base64_string: str) -> Optional[bytes]:
        """Convert base64 string to image bytes"""
        try:
            return base64.b64decode(base64_string)
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            return None
    
    @staticmethod
    def get_image_info(image: Image.Image) -> dict:
        """Get image information"""
        try:
            return {
                'size': image.size,
                'mode': image.mode,
                'format': image.format,
                'width': image.width,
                'height': image.height
            }
        except Exception as e:
            logger.error(f"Failed to get image info: {e}")
            return {}
    
    @staticmethod
    def resize_image(image: Image.Image, size: Tuple[int, int], 
                    keep_aspect_ratio: bool = True) -> Optional[Image.Image]:
        """Resize image to specified size"""
        try:
            if keep_aspect_ratio:
                return image.resize(size, Image.LANCZOS)
            else:
                return image.resize(size, Image.LANCZOS)
        except Exception as e:
            logger.error(f"Failed to resize image: {e}")
            return None
    
    @staticmethod
    def validate_image_format(file_path: str) -> bool:
        """Validate if file is a supported image format"""
        try:
            with Image.open(file_path) as img:
                return img.format in ['JPEG', 'JPG', 'PNG']
        except Exception:
            return False
    
    @staticmethod
    def process_image_for_upload(file_path: str) -> Tuple[Optional[bytes], Optional[bytes]]:
        """Process image for upload - returns (original_bytes, thumbnail_bytes)"""
        try:
            # Load original image
            original_image = ImageService.load_image_from_file(file_path)
            if not original_image:
                return None, None
            
            # Convert original to bytes
            original_buffer = io.BytesIO()
            original_image.save(original_buffer, format='JPEG', quality=95)
            original_bytes = original_buffer.getvalue()
            
            # Create thumbnail
            thumbnail = ImageService.create_thumbnail(original_image)
            if not thumbnail:
                return original_bytes, None
            
            # Compress thumbnail
            thumbnail_bytes = ImageService.compress_image(thumbnail)
            
            return original_bytes, thumbnail_bytes
            
        except Exception as e:
            logger.error(f"Failed to process image {file_path}: {e}")
            return None, None
    
    @staticmethod
    def get_file_size_kb(bytes_data: bytes) -> float:
        """Get file size in KB"""
        return len(bytes_data) / 1024.0 