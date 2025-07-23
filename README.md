# Card Annotation Tool

A Streamlit-based web application for collaborative annotation and validation of card data. The application supports multiple users working simultaneously on different records, with built-in file locking mechanisms to prevent concurrent edits of the same record.

## Features

- 🔄 Multi-user support with file locking
- 🖼️ Image and JSON data visualization
- ✏️ Interactive form-based editing
- 🔒 Concurrent access protection
- 🗄️ Google Cloud Storage integration
- ✅ Validation system
- 🔄 Automatic progression to next record
- 📊 Progress tracking

## Prerequisites

- Python 3.7+
- Google Cloud Storage account and credentials
- Streamlit account (for cloud deployment)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/card-annotation.git
cd card-annotation
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Google Cloud Storage credentials:
   - Place your GCS credentials JSON file in the project root as `key.json`
   - Or set up appropriate environment variables for GCS authentication

## Configuration

The application uses several configuration files:

- `.streamlit/config.toml`: Streamlit configuration
- `.streamlit/secrets.toml`: Sensitive configuration (GCS credentials, etc.)
- `config.py`: Application-specific configuration

## Usage

### Local Development

Run the application locally:

```bash
streamlit run main.py
```

### Streamlit Cloud Deployment

1. Push your code to GitHub
2. Connect your repository to Streamlit Cloud
3. Set the main file path to `main.py`
4. Configure secrets in Streamlit Cloud dashboard

## File Structure

- `main.py`: Main application entry point
- `ui_components.py`: UI component definitions
- `file_ops.py`: File operations and GCS interactions
- `gcs_utils.py`: Google Cloud Storage utilities
- `config.py`: Application configuration
- `schemas.py`: Data validation schemas
- `utils.py`: Utility functions

## Workflow

1. Users access the application and see available records
2. When a user opens a record:
   - The record is locked for exclusive access
   - The image and JSON data are displayed
   - An editing form is presented
3. After editing:
   - Changes can be saved
   - The record moves to the corrected folder
   - The user automatically progresses to the next record
4. Locks are automatically released when:
   - Moving to a different record
   - Finalizing a record
   - Closing the session
   - Application shutdown

## Multi-user Support

The application supports multiple users working simultaneously:
- Each user can work on different records
- File locking prevents concurrent editing of the same record
- Users see warnings if attempting to access locked records
- Central storage ensures data consistency

## Data Storage

- Images and JSON files are stored in Google Cloud Storage
- Records are organized in two folders:
  - `jsons/`: Original records pending review
  - `corrected/`: Finalized and validated records
- Local lock files manage concurrent access

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license information here]