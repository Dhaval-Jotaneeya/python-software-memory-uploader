import logging
import time
import functools
from typing import Callable, Any, Optional, Type, Union
from PyQt6.QtWidgets import QMessageBox
from config import Config

logger = logging.getLogger(__name__)

class RetryableError(Exception):
    """Exception that can be retried"""
    pass

class NonRetryableError(Exception):
    """Exception that should not be retried"""
    pass

class ErrorHandler:
    """Centralized error handling with retry logic"""
    
    @staticmethod
    def retry(max_attempts: int = 3, delay: float = 1.0, 
              backoff_factor: float = 2.0, 
              exceptions: tuple = (Exception,)):
        """Decorator for retrying functions with exponential backoff"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                last_exception = None
                current_delay = delay
                
                for attempt in range(max_attempts):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < max_attempts - 1:
                            logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                            time.sleep(current_delay)
                            current_delay *= backoff_factor
                        else:
                            logger.error(f"All {max_attempts} attempts failed for {func.__name__}: {e}")
                
                raise last_exception
            return wrapper
        return decorator
    
    @staticmethod
    def handle_github_error(error: Exception, operation: str) -> str:
        """Handle GitHub API errors and return user-friendly message"""
        error_str = str(error)
        
        if "401" in error_str or "Unauthorized" in error_str:
            return f"Authentication failed. Please check your GitHub token.\nOperation: {operation}"
        elif "403" in error_str or "Forbidden" in error_str:
            if "rate limit" in error_str.lower():
                return f"GitHub API rate limit exceeded. Please try again later.\nOperation: {operation}"
            else:
                return f"Access denied. You may not have permission for this operation.\nOperation: {operation}"
        elif "404" in error_str or "Not Found" in error_str:
            return f"Resource not found. The repository or file may not exist.\nOperation: {operation}"
        elif "422" in error_str or "Unprocessable Entity" in error_str:
            return f"Invalid request. Please check your input and try again.\nOperation: {operation}"
        elif "500" in error_str or "Internal Server Error" in error_str:
            return f"GitHub server error. Please try again later.\nOperation: {operation}"
        elif "timeout" in error_str.lower():
            return f"Request timed out. Please check your internet connection.\nOperation: {operation}"
        elif "connection" in error_str.lower():
            return f"Network connection error. Please check your internet connection.\nOperation: {operation}"
        else:
            return f"An unexpected error occurred: {error_str}\nOperation: {operation}"
    
    @staticmethod
    def handle_image_error(error: Exception, operation: str, file_path: str = None) -> str:
        """Handle image processing errors and return user-friendly message"""
        error_str = str(error)
        
        if "cannot identify image file" in error_str.lower():
            return f"Invalid image file. Please ensure the file is a valid image format.\nFile: {file_path or 'Unknown'}\nOperation: {operation}"
        elif "permission denied" in error_str.lower():
            return f"Permission denied. Please check file permissions.\nFile: {file_path or 'Unknown'}\nOperation: {operation}"
        elif "no such file" in error_str.lower():
            return f"File not found. Please check the file path.\nFile: {file_path or 'Unknown'}\nOperation: {operation}"
        elif "out of memory" in error_str.lower():
            return f"Image too large to process. Please try a smaller image.\nFile: {file_path or 'Unknown'}\nOperation: {operation}"
        else:
            return f"Image processing error: {error_str}\nFile: {file_path or 'Unknown'}\nOperation: {operation}"
    
    @staticmethod
    def show_error_dialog(parent, title: str, message: str, 
                         error_type: str = "Error", 
                         show_details: bool = False, 
                         details: str = None):
        """Show error dialog with optional details"""
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        if show_details and details:
            msg_box.setDetailedText(details)
        
        msg_box.exec()
    
    @staticmethod
    def show_warning_dialog(parent, title: str, message: str):
        """Show warning dialog"""
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec()
    
    @staticmethod
    def show_info_dialog(parent, title: str, message: str):
        """Show information dialog"""
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec()
    
    @staticmethod
    def log_and_show_error(parent, error: Exception, operation: str, 
                          error_type: str = "Error", show_dialog: bool = True):
        """Log error and optionally show dialog"""
        error_message = ErrorHandler.handle_github_error(error, operation)
        logger.exception(f"Error in {operation}: {error}")
        
        if show_dialog:
            ErrorHandler.show_error_dialog(parent, error_type, error_message)
        
        return error_message
    
    @staticmethod
    def safe_execute(func: Callable, *args, default_return: Any = None, 
                    error_message: str = "Operation failed", **kwargs) -> Any:
        """Safely execute a function and return default value on error"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"{error_message}: {e}")
            return default_return

class ValidationError(Exception):
    """Exception for validation errors"""
    pass

class ValidationHandler:
    """Handle input validation"""
    
    @staticmethod
    def validate_repo_name(name: str) -> bool:
        """Validate repository name"""
        if not name or not name.strip():
            raise ValidationError("Repository name cannot be empty")
        
        name = name.strip()
        
        # GitHub repository name rules
        if len(name) > 100:
            raise ValidationError("Repository name must be less than 100 characters")
        
        if not name[0].isalnum():
            raise ValidationError("Repository name must start with a letter or number")
        
        # Check for invalid characters
        invalid_chars = ['..', '~', '^', ':', '\\', '/', '?', '*', '[', ']']
        for char in invalid_chars:
            if char in name:
                raise ValidationError(f"Repository name cannot contain '{char}'")
        
        # Check for reserved names
        reserved_names = ['con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3', 
                         'com4', 'com5', 'com6', 'com7', 'com8', 'com9', 
                         'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 
                         'lpt7', 'lpt8', 'lpt9']
        if name.lower() in reserved_names:
            raise ValidationError(f"'{name}' is a reserved name")
        
        return True
    
    @staticmethod
    def validate_file_path(file_path: str) -> bool:
        """Validate file path"""
        import os
        
        if not file_path or not file_path.strip():
            raise ValidationError("File path cannot be empty")
        
        if not os.path.exists(file_path):
            raise ValidationError("File does not exist")
        
        if not os.path.isfile(file_path):
            raise ValidationError("Path is not a file")
        
        return True
    
    @staticmethod
    def validate_image_file(file_path: str) -> bool:
        """Validate image file"""
        from services.image_service import ImageService
        
        ValidationHandler.validate_file_path(file_path)
        
        if not ImageService.validate_image_format(file_path):
            raise ValidationError("File is not a supported image format (JPEG, PNG)")
        
        return True 