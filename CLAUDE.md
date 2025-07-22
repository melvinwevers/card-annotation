# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Streamlit-based web application for validating and correcting JSON data extracted from Dutch historical population registry cards. The application provides:

1. **Image-JSON Pair Validation**: Side-by-side display of historical card images with their corresponding JSON data
2. **Interactive Correction Interface**: Form-based editing with field validation, autocomplete, and error checking
3. **Multi-user Lock Management**: File locking system to prevent conflicts during simultaneous editing
4. **Real-time Dashboard**: Progress tracking, throughput metrics, and activity monitoring
5. **Google Cloud Storage Integration**: Handles file storage and retrieval from GCS buckets

## Architecture

### Core Components

- **main.py**: Primary Streamlit application entry point with session management and file locking
- **dashboard.py**: Analytics dashboard with metrics, progress charts, and activity monitoring  
- **ui_components.py**: Reusable UI components for forms, navigation, and image display
- **schemas.py**: Field validation schemas with patterns, enums, and autocomplete data
- **file_ops.py**: File operations for JSON loading, saving, and validation
- **gcs_utils.py**: Google Cloud Storage client operations and bucket management
- **config.py**: Application configuration and CSS styling

### Data Flow

1. Images stored in `data/images/` with corresponding JSON files in `data/jsons/`
2. Corrected files saved to `data/corrected/` and uploaded to GCS `corrected/` prefix
3. Lock files in `data/locks/` prevent concurrent editing with user/session tracking
4. JSON results cached in `json_results/` for performance

### Key Features

- **Field Validation**: Pattern matching for house numbers, postal codes, dates
- **Autocomplete Support**: Predefined lists for streets, occupations, birth places
- **Multi-level Data Structure**: Header info + main entries + follow-up entries
- **Concurrent User Management**: Lock-based system with stale lock detection and cleanup
- **Progress Tracking**: Real-time metrics on completion rates and throughput

## Development Commands

### Running the Application

```bash
# Main annotation interface
streamlit run main.py

# Analytics dashboard  
streamlit run dashboard.py
```

### Installing Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies: streamlit, google-cloud-storage, pandas, plotly, portalocker

### Testing GCS Access

```bash
python test_gcs_access.py
```

## Data Schema Structure

JSON records follow a three-level hierarchy:

1. **Header**: Street address, house number, district codes
2. **Main Entries**: Primary residents with registration/departure dates, demographics  
3. **Follow-up Entries**: Additional family members or updates

See `schemas.py` for complete field definitions, validation patterns, and autocomplete options.

## File Management

- Images: `data/images/{filename}.jpg`
- Raw JSON: `data/jsons/{filename}.json` 
- Corrected: `data/corrected/{filename}.json`
- Locks: `data/locks/{filename}.json.lock`
- Results Cache: `json_results/{filename}.json`

## Multi-user Coordination

The application uses file-based locking with user tracking:
- Lock files contain user info and session IDs
- Automatic stale lock detection (>2 hours)  
- Dashboard provides lock cleanup tools
- Session state manages lock lifecycle

## GCS Integration

- Bucket configuration in `config.py` or environment variables
- Raw files read from GCS, corrected files uploaded back
- Caching layer for performance optimization
- Error handling for network issues and permissions