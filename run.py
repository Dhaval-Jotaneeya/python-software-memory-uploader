#!/usr/bin/env python3
"""
Launcher script for Family Websites Repository Manager
"""

import sys
import os
import logging
from datetime import datetime

def setup_logging():
    """Setup logging configuration"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import PyQt6
        import requests
        import PIL
        import dotenv
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Please install dependencies with: pip install -r requirements.txt")
        return False

def check_environment():
    """Check if environment is properly configured"""
    from dotenv import load_dotenv
    load_dotenv()
    
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        print("Warning: GITHUB_TOKEN not found in environment variables.")
        print("Please create a .env file with your GitHub token:")
        print("GITHUB_TOKEN=your_github_personal_access_token")
        return False
    
    return True

def main():
    """Main launcher function"""
    print("Starting Family Websites Repository Manager...")
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check environment
    if not check_environment():
        print("Environment check failed. Please configure your GitHub token.")
        print("You can still run the application, but some features may not work.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    try:
        # Import and run the main application
        from main import main as app_main
        logger.info("Application starting...")
        app_main()
    except Exception as e:
        logger.exception("Failed to start application")
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 