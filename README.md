# Family Websites Repository Manager

A modern desktop application built with Python and PyQt6 for managing image repositories on GitHub. This application provides a user-friendly interface for creating, viewing, and managing image repositories.

## Features

- Create new repositories
- View repository contents
- Upload images with automatic thumbnail generation
- Delete repositories
- **GitHub Pages publishing with real-time build status tracking**
- Modern dark theme UI
- Responsive grid layout
- Progress tracking for uploads

## GitHub Pages Features

The application includes advanced GitHub Pages functionality:

- **Automatic Publishing**: Publish your image galleries directly to GitHub Pages
- **Real-time Build Tracking**: Monitor the build process in real-time with status updates
- **Build Status Indicator**: Visual indicator showing current build status (building, completed, failed, etc.)
- **Manual Status Check**: Check build status manually at any time
- **Automatic Notifications**: Get notified when your site is ready to view
- **Direct Site Access**: Open your published site directly from the application

### Build Status Tracking

When you publish to GitHub Pages, the application will:

1. Upload your gallery content to the repository
2. Start monitoring the build process automatically
3. Show real-time status updates in the progress bar and status indicator
4. Notify you when the build completes successfully
5. Provide the live URL for your published gallery

The build tracker will monitor for up to 5 minutes and provide detailed status information including:
- ✅ Build completed successfully
- 🔄 Site is currently building
- ❌ Build failed with error details
- ⏳ Build not started yet
- ⏰ Build check timed out

## Requirements

- Python 3.8 or higher
- PyQt6
- requests
- python-dotenv
- Pillow

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/repository-manager.git
cd repository-manager
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with your GitHub token:
```
GITHUB_TOKEN=your_github_token_here
```

## Usage

1. Run the application:
```bash
python main.py
```

2. Create a new repository:
   - Click the "Create Repository" button
   - Enter a repository name
   - Click "Create"

3. View a repository:
   - Click the "View" button on any repository card
   - Use the "Upload Images" button to add new images
   - Images will be automatically resized and thumbnails will be generated

4. Publish to GitHub Pages:
   - Load a repository with images
   - Click "Publish to GitHub Pages"
   - Monitor the build status in real-time
   - Get notified when your site is ready

5. Check build status:
   - Use the "Check Build Status" button to manually check current status
   - View the build status indicator for real-time updates

6. Delete a repository:
   - Click the "Delete" button on any repository card
   - Confirm the deletion

## Development

The application is structured into two main components:

1. `main.py`: Contains the main window and repository management functionality
2. `repository_view.py`: Handles the repository view window and image upload functionality

### Key Components

- **GitHubPagesBuildTracker**: Monitors GitHub Pages build status in a separate thread
- **Build Status UI**: Real-time status indicators and manual check functionality
- **Progress Tracking**: Visual feedback during publishing and build processes

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
