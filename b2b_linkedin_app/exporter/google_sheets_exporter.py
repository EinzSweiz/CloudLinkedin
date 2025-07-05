# IMPROVED exporter/google_sheets_exporter.py

import gspread
import logging
import time
from oauth2client.service_account import ServiceAccountCredentials
from django.conf import settings
from gspread.exceptions import APIError, SpreadsheetNotFound
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GoogleSheetsExporter:
    def __init__(self):
        self.client = None
        self.sheet = None
        self.spreadsheet = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Sheets client with error handling"""
        try:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"  # ✅ Added explicit sheets scope
            ]
            
            # Check if credentials file exists
            if not hasattr(settings, 'GSHEET_CREDENTIALS_PATH') or not settings.GSHEET_CREDENTIALS_PATH:
                raise ValueError("GSHEET_CREDENTIALS_PATH not configured in settings")
                
            if not hasattr(settings, 'GSHEET_SPREADSHEET_ID') or not settings.GSHEET_SPREADSHEET_ID:
                raise ValueError("GSHEET_SPREADSHEET_ID not configured in settings")
            
            # Initialize credentials
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                settings.GSHEET_CREDENTIALS_PATH, scope
            )
            self.client = gspread.authorize(creds)
            
            # Try to open the spreadsheet
            try:
                self.spreadsheet = self.client.open_by_key(settings.GSHEET_SPREADSHEET_ID)
                self.sheet = self.spreadsheet.sheet1
            except SpreadsheetNotFound:
                logger.error(f"❌ Spreadsheet not found: {settings.GSHEET_SPREADSHEET_ID}")
                raise ValueError(f"Spreadsheet {settings.GSHEET_SPREADSHEET_ID} not found or not accessible")
            
            # Ensure headers exist
            self._ensure_headers()
            
            logger.info("✅ Google Sheets client initialized successfully")
            logger.info(f"📊 Connected to spreadsheet: {self.spreadsheet.title}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Sheets client: {e}")
            raise
    
    def _ensure_headers(self):
        """Ensure the sheet has proper headers"""
        try:
            # Check if first row has headers
            try:
                existing_headers = self.sheet.row_values(1)
            except Exception:
                existing_headers = []
            
            expected_headers = ["Full Name", "Position", "Company", "Email", "Profile URL", "Exported At"]
            
            if not existing_headers or len(existing_headers) < len(expected_headers):
                logger.info("📋 Setting up Google Sheets headers...")
                
                # Clear first row and add headers
                if existing_headers:
                    self.sheet.delete_rows(1)
                
                self.sheet.insert_row(expected_headers, 1)
                
                # Format headers (bold, background color)
                try:
                    self.sheet.format('A1:F1', {
                        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                        "textFormat": {"bold": True}
                    })
                except Exception as format_error:
                    logger.warning(f"⚠️ Could not format headers: {format_error}")
                
                logger.info("✅ Headers set up successfully")
                
        except Exception as e:
            logger.warning(f"⚠️ Could not set up headers: {e}")
    
    def write_profile(self, profile_data: dict, max_retries=3):
        """Write a single profile to Google Sheets with retry logic"""
        for attempt in range(max_retries):
            try:
                # Validate required data
                if not profile_data.get("full_name"):
                    logger.warning("⚠️ Skipping profile without name")
                    return True  # Consider this a success to avoid retries
                
                # Prepare the row data
                row = [
                    profile_data.get("full_name", ""),
                    profile_data.get("position", ""),
                    profile_data.get("company_name", ""),
                    profile_data.get("email", ""),
                    profile_data.get("profile_url", ""),
                    time.strftime("%Y-%m-%d %H:%M:%S")  # Timestamp
                ]
                
                # Append the row to the sheet
                self.sheet.append_row(row, value_input_option="RAW")
                
                logger.info(f"✅ Successfully exported to Google Sheets: {profile_data.get('full_name', 'Unknown')}")
                return True
                
            except APIError as api_error:
                if "RATE_LIMIT_EXCEEDED" in str(api_error):
                    # Handle rate limiting specifically
                    wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                    logger.warning(f"⚠️ Rate limit exceeded (attempt {attempt + 1}), waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
                elif "PERMISSION_DENIED" in str(api_error):
                    logger.error(f"❌ Permission denied - check service account permissions")
                    raise  # Don't retry permission errors
                else:
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 1  # Exponential backoff: 1s, 2s, 4s
                        logger.warning(f"⚠️ Google Sheets API error (attempt {attempt + 1}), retrying in {wait_time}s: {api_error}")
                        time.sleep(wait_time)
                        
                        # Reinitialize client on API errors
                        try:
                            self._initialize_client()
                        except Exception as reinit_error:
                            logger.error(f"❌ Failed to reinitialize client: {reinit_error}")
                            
                        continue
                    else:
                        logger.error(f"❌ Google Sheets API error after {max_retries} attempts: {api_error}")
                        raise
                        
            except HttpError as http_error:
                # Handle HTTP errors from Google API
                if http_error.resp.status == 429:  # Rate limit
                    wait_time = (2 ** attempt) * 2
                    logger.warning(f"⚠️ HTTP 429 Rate limit (attempt {attempt + 1}), waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
                elif http_error.resp.status == 403:  # Forbidden
                    logger.error(f"❌ HTTP 403 Forbidden - check permissions")
                    raise
                else:
                    logger.error(f"❌ HTTP Error {http_error.resp.status}: {http_error}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        raise
                        
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 1
                    logger.warning(f"⚠️ Error exporting to Google Sheets (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ Failed to export to Google Sheets after {max_retries} attempts: {e}")
                    raise
        
        return False
    
    def write_batch(self, profiles_data: list, batch_size=10):
        """Write multiple profiles in batches for better performance"""
        try:
            if not profiles_data:
                return {"success": True, "count": 0}
            
            # Process in batches to avoid rate limits
            total_exported = 0
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            
            for i in range(0, len(profiles_data), batch_size):
                batch = profiles_data[i:i + batch_size]
                
                # Prepare batch rows
                rows = []
                for profile_data in batch:
                    if profile_data.get("full_name"):  # Only add profiles with names
                        row = [
                            profile_data.get("full_name", ""),
                            profile_data.get("position", ""),
                            profile_data.get("company_name", ""),
                            profile_data.get("email", ""),
                            profile_data.get("profile_url", ""),
                            timestamp
                        ]
                        rows.append(row)
                
                if rows:
                    # Batch insert with retry
                    for attempt in range(3):
                        try:
                            self.sheet.append_rows(rows, value_input_option="RAW")
                            total_exported += len(rows)
                            logger.info(f"✅ Batch exported {len(rows)} profiles to Google Sheets")
                            break
                        except Exception as e:
                            if attempt < 2:
                                logger.warning(f"⚠️ Batch export attempt {attempt + 1} failed, retrying: {e}")
                                time.sleep(2 ** attempt)
                            else:
                                raise
                
                # Small delay between batches
                if i + batch_size < len(profiles_data):
                    time.sleep(1)
            
            return {
                "success": True,
                "count": total_exported,
                "exported_at": timestamp
            }
            
        except Exception as e:
            logger.error(f"❌ Batch export to Google Sheets failed: {e}")
            raise
    
    def get_sheet_info(self):
        """Get information about the current sheet"""
        try:
            sheet_info = {
                "title": self.spreadsheet.title,
                "sheet_name": self.sheet.title,
                "url": f"https://docs.google.com/spreadsheets/d/{settings.GSHEET_SPREADSHEET_ID}",
                "row_count": self.sheet.row_count,
                "col_count": self.sheet.col_count,
            }
            
            # Get actual data count (excluding header)
            try:
                all_values = self.sheet.get_all_values()
                data_rows = len([row for row in all_values if any(cell.strip() for cell in row)]) - 1  # Exclude header
                sheet_info["data_rows"] = max(0, data_rows)
            except Exception as e:
                logger.warning(f"⚠️ Could not get row count: {e}")
                sheet_info["data_rows"] = "Unknown"
            
            return sheet_info
            
        except Exception as e:
            logger.error(f"❌ Failed to get sheet info: {e}")
            return {"error": str(e)}
    
    def test_connection(self):
        """Test the Google Sheets connection"""
        try:
            info = self.get_sheet_info()
            if info and "error" not in info:
                logger.info(f"✅ Google Sheets connection test successful")
                logger.info(f"📊 Spreadsheet: {info['title']} ({info['data_rows']} data rows)")
                return True
            else:
                logger.error(f"❌ Google Sheets connection test failed: {info}")
                return False
        except Exception as e:
            logger.error(f"❌ Google Sheets connection test error: {e}")
            return False