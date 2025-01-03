# Changelog

All notable changes to this project will be documented in this file.

## [0.0.5] - 2024-01-06

### Added
- Integrated Codestral Mamba model:
  - High-performance inference capabilities
  - Enhanced code completion and generation
  - Improved context understanding
  - State-of-the-art reasoning abilities

## [0.0.4] - 2024-01-05

### Added
- New modern UI design inspired by Cursor IDE:
  - Bubble-style panels for workspace, chat, and main content
  - Centered logo and title placement
  - Improved spacing and layout consistency
  - Enhanced visual hierarchy
- Improved chat interface:
  - Fixed height chat input area
  - Better message spacing
  - Cleaner bubble design
- Enhanced workspace panel:
  - Centralized workspace controls
  - Better organized file tree
  - Improved model selection dropdown
- Updated copyright notice with special thanks

### Changed
- Adjusted panel widths for better usability
- Improved spacing between elements
- Enhanced button styles and hover effects
- Refined color scheme and borders
- Reorganized layout structure for better visual flow

## [0.0.3] - 2024-01-04

### Added
- Comprehensive file attachment support:
  - PDF files with text extraction
  - Microsoft Word documents (.docx)
  - Excel spreadsheets with sheet parsing
  - Images with OCR capabilities
  - Enhanced Markdown with GFM support
  - All major programming languages
  - Configuration files
  - Text and documentation files
- File preview functionality:
  - Syntax highlighting for code files
  - Formatted view for PDFs
  - Spreadsheet formatting
  - Image text extraction preview
- File handling features:
  - Multiple file upload support
  - Progress indicators
  - File size display
  - Type-specific icons
  - Remove attachments
  - Preview button for each file
- Error handling and validation:
  - File type detection
  - Size limits for unknown files
  - Proper error messages
  - Loading indicators

### Removed
- Archive file support (ZIP, RAR, 7z)

## [0.0.2] - 2024-01-03

### Added
- WebSocket support using Flask-SocketIO and Eventlet
- Real-time notifications for code changes
- Automatic server restart when static files or templates change
- Cache busting for static assets
- Socket.IO client integration for real-time updates

### Changed
- Updated model lineup:
  - Added Qwen 2.5 Coder (32B model)
  - Removed Groq integration
- Improved workspace change notifications
- Enhanced real-time feedback for file modifications

### Fixed
- Static file reloading issues
- Template caching problems
- WebSocket connection stability
- Environment variable configuration for OpenRouter API

## [0.0.1] - Initial Release

### Added
- Multi-model AI support (DeepSeek, Grok, Claude)
- Workspace management system
- Code generation and modification
- Interactive chat interface
- SQLite-based history tracking
- File diff previews
- Basic static file serving 