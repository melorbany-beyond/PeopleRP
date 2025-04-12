from flask import Blueprint, render_template, request, redirect, url_for, flash
import json
import os
import requests
from datetime import datetime
from .token_helper import get_access_token
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

bp = Blueprint('calendar', __name__, template_folder='../templates')

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
EMPLOYEES_FILE = os.path.join(DATA_DIR, 'employees.json')
HOLIDAYS_FILE = os.path.join(DATA_DIR, 'holidays.json')
META_FILE = os.path.join(DATA_DIR, 'meta.json')

# Utility functions to load/save JSON
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

@bp.route('/calendar')
def calendar_view():
    # Load holiday data and employee mapping
    holidays = load_json(HOLIDAYS_FILE).get("data", [])
    employees = load_json(EMPLOYEES_FILE)
    
    # Create a dictionary mapping employee IDs to names
    employee_dict = {str(emp["id"]): emp["en"] for emp in employees}
    
    # Filter and process only approved transactions
    approved_holidays = []
    for entry in holidays:
        if entry.get("status") == "approved":
            emp_id = str(entry.get("employee", {}).get("id"))
            entry["employee_name"] = employee_dict.get(emp_id, f"Employee {emp_id}")
            approved_holidays.append(entry)
    
    last_meta = load_json(META_FILE)
    last_updated = last_meta.get("last_updated", "Never")
    
    return render_template("calendar.html", holidays=approved_holidays, last_updated=last_updated)

@bp.route('/update-holidays', methods=['POST'])
def update_holidays():
    logger.info("Update holidays endpoint called")
    try:
        # Get access token using token helper
        logger.debug("Attempting to get access token")
        access_token = get_access_token()
        logger.debug("Successfully obtained access token")
        
        # Load meta to get the last page fetched
        meta = load_json(META_FILE)
        logger.debug(f"Meta data loaded: {meta}")
        
        last_page = meta.get("last_page", 0)
        if last_page == -1:  # If we've reached the end before, start from beginning
            last_page = 0
            
        next_page = last_page + 1
        logger.debug(f"Starting from page: {next_page}")
        
        # Load existing holidays
        holidays_json = load_json(HOLIDAYS_FILE)
        if "data" not in holidays_json:
            holidays_json["data"] = []
        current_data = holidays_json["data"]
        existing_ids = {str(record.get("id")) for record in current_data}
        
        total_new_records = 0
        current_page = next_page
        has_more_pages = True
        
        while has_more_pages:
            # Fetch approved holiday transactions from ZenHR API for the current page
            api_url = f"https://api.zenhr.com/api/v3/branches/5737/timeoff_transactions"
            params = {
                "page": current_page,
                "limit": 100,
                "filter[status][]": "approved"
            }
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            logger.debug(f"Making API request to: {api_url}")
            logger.debug(f"With params: {params}")
            response = requests.get(api_url, params=params, headers=headers)
            logger.debug(f"API response status code: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                new_data = response_data.get("data", [])
                logger.debug(f"Page {current_page}: Received {len(new_data)} records")
                
                # Add new records if they don't already exist
                new_records = [record for record in new_data if str(record.get("id")) not in existing_ids]
                total_new_records += len(new_records)
                current_data.extend(new_records)
                
                # Update existing_ids with new records
                existing_ids.update(str(record.get("id")) for record in new_records)
                
                # Check if this is the last page
                if len(new_data) < 100:
                    logger.info(f"Received {len(new_data)} records (less than limit of 100), this is the last page")
                    meta["last_page"] = -1  # Set to -1 to indicate we've reached the end
                    has_more_pages = False
                else:
                    meta["last_page"] = current_page
                    current_page += 1
            else:
                error_msg = f"Failed to fetch page {current_page} from ZenHR API. Status code: {response.status_code}"
                logger.error(f"{error_msg}. Response: {response.text}")
                flash(error_msg, "error")
                break
        
        # Save all updates at once
        holidays_json["data"] = current_data
        save_json(HOLIDAYS_FILE, holidays_json)
        logger.debug(f"Saved updated holidays to file. Total records: {len(current_data)}")
        
        # Update meta info
        current_time = datetime.utcnow()
        meta["last_updated"] = current_time.isoformat() + "Z"
        save_json(META_FILE, meta)
        logger.debug(f"Updated meta data: {meta}")
        
        if total_new_records > 0:
            flash(f"Updated holidays with {total_new_records} new records across {current_page - next_page} pages.", "success")
        else:
            flash("No new holiday records found.", "info")
        logger.info("Successfully updated holidays")
    
    except Exception as e:
        error_msg = f"Error updating holidays: {str(e)}"
        logger.error(error_msg, exc_info=True)
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        flash(error_msg, "error")
    
    return redirect(url_for('calendar.calendar_view'))