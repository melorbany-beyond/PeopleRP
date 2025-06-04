import logging
import os
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from flask import current_app
import atexit
import requests
from datetime import datetime
from routes.token_helper import get_access_token

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants - same as in calendar.py
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
HOLIDAYS_FILE = os.path.join(DATA_DIR, 'holidays.json')
META_FILE = os.path.join(DATA_DIR, 'meta.json')

# Utility functions - same as in calendar.py
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def fetch_holidays_from_zenhr():
    """
    Automated function to fetch holidays data from ZenHR API.
    This is the same logic as the /update-holidays endpoint but designed for background execution.
    """
    logger.info("Starting automated ZenHR holidays fetch...")
    
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
                break
        
        # Save all updates at once
        holidays_json["data"] = current_data
        save_json(HOLIDAYS_FILE, holidays_json)
        logger.debug(f"Saved updated holidays to file. Total records: {len(current_data)}")
        
        # Update meta info
        current_time = datetime.utcnow()
        meta["last_updated"] = current_time.isoformat() + "Z"
        meta["last_auto_fetch"] = current_time.isoformat() + "Z"  # Track when auto-fetch last ran
        save_json(META_FILE, meta)
        logger.debug(f"Updated meta data: {meta}")
        
        if total_new_records > 0:
            logger.info(f"Automated fetch completed: Added {total_new_records} new records across {current_page - next_page} pages.")
        else:
            logger.info("Automated fetch completed: No new holiday records found.")
            
    except Exception as e:
        logger.error(f"Error in automated holidays fetch: {str(e)}", exc_info=True)

def start_scheduler(app):
    """
    Initialize and start the background scheduler for automated tasks.
    """
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        # Prevent scheduler from starting twice in debug mode
        return
    
    scheduler = BackgroundScheduler()
    
    # Add job to fetch holidays every hour
    scheduler.add_job(
        func=fetch_holidays_from_zenhr,
        trigger=IntervalTrigger(hours=1),
        id='fetch_holidays_job',
        name='Fetch holidays from ZenHR every hour',
        replace_existing=True,
        max_instances=1  # Prevent overlapping executions
    )
    
    # Start the scheduler
    scheduler.start()
    logger.info("Background scheduler started - holidays will be fetched every hour")
    
    # Ensure scheduler shuts down cleanly when the app exits
    atexit.register(lambda: scheduler.shutdown())
    
    return scheduler

def stop_scheduler():
    """
    Stop the background scheduler.
    """
    try:
        # This is a global reference that would need to be managed
        # For now, we rely on atexit to handle cleanup
        logger.info("Scheduler shutdown requested")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {str(e)}") 