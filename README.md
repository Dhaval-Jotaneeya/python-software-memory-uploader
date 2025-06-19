# Family Websites Repository Manager

A modern desktop application built with Python and PyQt6 for managing image repositories on GitHub. This application provides a user-friendly interface for creating, viewing, and managing image repositories.

## Features

- Create new repositories
- View repository contents
- Upload images with automatic thumbnail generation
- Delete repositories
- Modern dark theme UI
- Responsive grid layout
- Progress tracking for uploads

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

4. Delete a repository:
   - Click the "Delete" button on any repository card
   - Confirm the deletion

## Development

The application is structured into two main components:

1. `main.py`: Contains the main window and repository management functionality
2. `repository_view.py`: Handles the repository view window and image upload functionality

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
