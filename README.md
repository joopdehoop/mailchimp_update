# Mailchimp List Management Tool

A Python-based application for managing Mailchimp mailing lists by processing Excel files containing contact information. Designed specifically for educational institutions to manage student and employee contacts with proper categorization and language preferences.

## Features

- **Excel File Processing**: Import contact data from Excel files
- **GUI Interface**: User-friendly Tkinter-based single-window interface
- **Contact Categorization**: Separate handling for Students and Employees
- **Language Preferences**: Support for Nederlands and English
- **Batch Operations**: Efficient bulk processing using Mailchimp API
- **Real-time Progress**: Live progress tracking and status updates
- **Debug Mode**: Safe testing with read-only operations
- **Error Handling**: Comprehensive error tracking and reporting

## Requirements

- Python 3.x
- pandas
- python-dotenv
- tkinter (standard library)
- mailchimp3

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install pandas python-dotenv mailchimp3
   ```
3. Create a `.env` file with your configuration (see Configuration section)

## Configuration

Create a `.env` file in the project root with the following variables:

```env
# Required
MAILCHIMP_API_KEY=your_mailchimp_api_key
MAILCHIMP_LIST_ID=your_list_id

# Optional
CONFIG_UPDATE=true
CONFIG_PAGINATE=1000
DEBUG_MODE=false
DEFAULT_CONTACT_TYPE=Student

# Category IDs for member segmentation
CATEGORY_*_ID=category_id
CATEGORY_*_STUDENT=student_value
CATEGORY_*_EMPLOYEE=employee_value
CATEGORY_TAAL_NEDERLANDS=nederlands_value
CATEGORY_TAAL_ENGLISH=english_value
```

## Usage

1. Run the application:
   ```bash
   python mailchimp_update.py
   ```

2. Use the GUI to:
   - Select an Excel file containing contact data
   - Choose contact type (Student/Employee)
   - Enable debug mode for testing (optional)
   - Process contacts and monitor progress
   - Check batch operation status

## How It Works

1. **Data Import**: Reads contact information from Excel files
2. **Data Validation**: Cleans and validates contact data
3. **Member Lookup**: Uses MD5-hashed email addresses to identify existing members
4. **Batch Creation**: Creates efficient batch operations for API calls
5. **Processing**: Submits batches to Mailchimp API with real-time progress updates
6. **Status Monitoring**: Tracks batch operation completion and results

## Debug Mode

Enable debug mode to:
- Perform read-only operations (no data changes)
- View detailed logging of all processing steps
- Test configurations safely without affecting your Mailchimp list

## Project Structure

```
mailchimp_update/
├── mailchimp_update.py     # Main application
├── mailchimp3/             # Custom Mailchimp API client
├── .env                    # Configuration file
├── CLAUDE.md              # Development guidance
└── README.md              # This file
```

## License

This project is designed for educational institution use. Please ensure compliance with Mailchimp's terms of service and data protection regulations.
