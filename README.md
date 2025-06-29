# Family Websites Repository Manager

A comprehensive Python application for managing GitHub repositories with image galleries, featuring advanced caching, error handling, and enhanced UI components.

## 🚀 Features

### Core Functionality
- **Repository Management**: Create, delete, and manage GitHub repositories
- **Image Upload**: Bulk upload images with automatic thumbnail generation
- **Gallery View**: Responsive web-based image gallery with mobile optimization
- **GitHub Pages Integration**: Automatic publishing to GitHub Pages
- **Build Tracking**: Real-time monitoring of GitHub Pages build status

### Enhanced Features (New)
- **Advanced Caching System**: Intelligent caching for improved performance
- **Comprehensive Error Handling**: Retry logic and user-friendly error messages
- **Service Layer Architecture**: Clean separation of concerns
- **Enhanced UI Components**: Modern styling with animations and hover effects
- **Input Validation**: Robust validation for all user inputs
- **Performance Optimizations**: Batch operations and concurrent processing

## 🏗️ Architecture

### Service Layer
- `GitHubService`: Handles all GitHub API operations
- `ImageService`: Manages image processing and optimization
- `CacheManager`: Provides intelligent caching for performance
- `ErrorHandler`: Centralized error handling with retry logic

### UI Components
- `EnhancedButton`: Buttons with hover effects and animations
- `StatusBar`: Multi-indicator status display
- `ImageCard`: Enhanced image display cards
- `LoadingSpinner`: Animated loading indicators
- `ToolbarWidget`: Organized toolbar with action grouping

### Configuration
- Centralized configuration management
- Environment variable support
- Configurable settings for all components

## 📦 Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd python-software-memory-uploader
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   Create a `.env` file in the project root:
   ```env
   GITHUB_TOKEN=your_github_personal_access_token
   ```

4. **Run the application**:
   ```bash
   python main.py
   ```

## 🔧 Configuration

The application uses a centralized configuration system. Key settings can be modified in `config.py`:

```python
class Config:
    # GitHub API Configuration
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    GITHUB_ORG = 'lifetime-memories'
    
    # Image Processing
    THUMBNAIL_SIZE = (200, 200)
    THUMBNAIL_QUALITY = 85
    
    # Caching
    CACHE_ENABLED = True
    CACHE_DURATION = 300  # 5 minutes
    
    # Rate Limiting
    RATE_LIMIT_WARNING_THRESHOLD = 100
    RATE_LIMIT_CRITICAL_THRESHOLD = 10
```

## 🎯 Usage

### Repository Management
1. **Create Repository**: Click "Create Repository" and enter a name
2. **Load Images**: Double-click a repository or use context menu
3. **Upload Images**: Right-click repository → "Upload Images"
4. **Delete Repository**: Right-click repository → "Delete"

### Gallery Features
- **Responsive Design**: Automatically adapts to screen size
- **Mobile Optimization**: Touch-friendly interface for mobile devices
- **Image Viewer**: Full-screen image viewing with zoom and pan
- **Download Support**: Download original images with native file dialog

### GitHub Pages
1. **Publish Gallery**: Click "Publish to GitHub Pages"
2. **Monitor Build**: Real-time build status tracking
3. **Access Site**: Automatic URL generation and browser opening

## 🔍 Error Handling

The application includes comprehensive error handling:

- **Retry Logic**: Automatic retry for transient failures
- **User-Friendly Messages**: Clear error descriptions
- **Rate Limit Management**: Automatic rate limit monitoring
- **Validation**: Input validation with helpful feedback

## 📊 Performance Features

### Caching System
- **Repository Data**: Cached repository lists and metadata
- **Image Metadata**: Cached image information for faster loading
- **Automatic Cleanup**: Expired cache items are automatically removed
- **Configurable TTL**: Time-to-live settings for different data types

### Batch Operations
- **Concurrent Uploads**: Multiple images uploaded simultaneously
- **Efficient API Usage**: Minimized API calls through batching
- **Memory Management**: Optimized memory usage for large galleries

## 🎨 UI Enhancements

### Modern Design
- **Dark Theme**: Consistent dark theme throughout
- **Smooth Animations**: Animated progress bars and transitions
- **Hover Effects**: Interactive hover states for better UX
- **Responsive Layout**: Adapts to different window sizes

### Enhanced Components
- **Status Indicators**: Real-time status and progress information
- **Loading Spinners**: Visual feedback during operations
- **Toolbar Organization**: Logical grouping of actions
- **Image Cards**: Enhanced image display with metadata

## 🔧 Development

### Project Structure
```
python-software-memory-uploader/
├── config.py                 # Configuration management
├── main.py                   # Main application entry point
├── services/                 # Service layer
│   ├── github_service.py    # GitHub API operations
│   └── image_service.py     # Image processing
├── utils/                    # Utility modules
│   ├── error_handler.py     # Error handling and validation
│   └── cache_manager.py     # Caching system
├── ui/                       # UI components
│   └── enhanced_widgets.py  # Enhanced UI widgets
├── layouts/                  # Layout implementations
├── requirements.txt          # Python dependencies
└── README.md                # This file
```

### Adding New Features
1. **Service Layer**: Add new services in the `services/` directory
2. **UI Components**: Create new widgets in `ui/enhanced_widgets.py`
3. **Configuration**: Add new settings to `config.py`
4. **Error Handling**: Use the centralized error handling system

## 🐛 Troubleshooting

### Common Issues
1. **GitHub Token**: Ensure your GitHub token has the necessary permissions
2. **Rate Limits**: Monitor the rate limit indicator in the status bar
3. **Image Upload**: Check file formats and sizes
4. **Cache Issues**: Clear cache if experiencing stale data

### Logging
The application uses comprehensive logging. Log files are stored in the `logs/` directory with timestamps.

## 📈 Performance Tips

1. **Enable Caching**: Keep caching enabled for better performance
2. **Batch Operations**: Upload multiple images at once
3. **Monitor Rate Limits**: Avoid hitting GitHub API limits
4. **Regular Cleanup**: Clear cache periodically for optimal performance

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- PyQt6 for the GUI framework
- GitHub API for repository management
- Pillow for image processing
- All contributors and users of this application
