import json
import time
import requests
import feedparser
import configparser
import os
import logging
from datetime import datetime, timedelta
from pprint import pprint

def load_config():
    """Load configuration from config.ini file."""
    config = configparser.ConfigParser()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")
    
    config.read(config_path)
    return config

def fetch_rss_feed(url):
    """Fetch and parse the RSS feed."""
    print("Fetching RSS feed from:", url)
    response = requests.get(url)
    response.raise_for_status()
    feed = feedparser.parse(response.text)
    
    # Debug printing
    print("\nFeed structure:")
    print("Feed type:", type(feed))
    print("Entries type:", type(feed.entries))
    if feed.entries:
        print("\nFirst entry structure:")
        try:
            pprint(vars(feed.entries[0]))
        except:
            print("Could not print first entry details")
    return feed

def check_disruptions(feed, area):
    """Check if the specified area is affected by a water disruption."""
    print(f"\nChecking for area: {area}")
    
    for entry in feed.entries:
        print("\nProcessing entry:")
        try:
            pprint(vars(entry))
        except:
            print("Could not print entry details")
        
        # Try to get description using different methods
        try:
            if hasattr(entry, 'summary'):
                description = entry.summary
            elif hasattr(entry, 'description'):
                description = entry.description
            else:
                description = str(entry)
            
            print(f"Description found: {description}")
            
            if area.lower() in description.lower():
                return {
                    'id': getattr(entry, 'id', ''),
                    'title': getattr(entry, 'title', ''),
                    'description': description
                }
        except Exception as e:
            print(f"Error processing entry: {e}")
            continue
    
    return None

def send_pushover_notification(api_key, user_key, title, message):
    """Send a notification through Pushover using a direct HTTPS request."""
    url = "https://api.pushover.net/1/messages.json"
    data = {
        "token": api_key,
        "user": user_key,
        "title": title,
        "message": message
    }
    response = requests.post(url, data=data)
    response.raise_for_status()

def load_last_notification():
    """Load information about the last sent notification."""
    try:
        with open('last_notification.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_last_notification(disruption):
    """Save details about the notification just sent."""
    notification_data = {
        'timestamp': time.time(),
        'disruption_id': disruption.get('id', ''),
        'description': disruption.get('description', '')
    }
    
    with open('last_notification.json', 'w') as f:
        json.dump(notification_data, f)

def should_send_notification(disruption, min_interval_minutes=30):
    """Determine if a new notification should be sent."""
    last_notification = load_last_notification()
    
    if not last_notification:
        return True
    
    current_time = time.time()
    time_since_last = current_time - last_notification.get('timestamp', 0)
    
    if time_since_last < (min_interval_minutes * 60):
        return False
    
    current_id = disruption.get('id', '')
    last_id = last_notification.get('disruption_id')
    
    if current_id != last_id:
        return True
    
    if disruption.get('description', '') != last_notification.get('description'):
        return True
    
    return False

def main():
    """Main program flow with duplicate notification prevention."""
    try:
        print("Starting water disruption check...")
        
        config = load_config()
        
        rss_url = config['RSS']['url']
        area = config['RSS']['area']
        pushover_api = config['PUSHOVER']['api_key']
        pushover_user = config['PUSHOVER']['user_key']
        
        # Fix for the config.get() error
        min_interval = 30  # default value
        if 'NOTIFICATIONS' in config:
            min_interval = config['NOTIFICATIONS'].getint('min_interval_minutes', 30)
        
        print(f"\nConfiguration loaded:")
        print(f"RSS URL: {rss_url}")
        print(f"Area to check: {area}")
        print(f"Minimum notification interval: {min_interval} minutes")
        
        feed = fetch_rss_feed(rss_url)
        disruption = check_disruptions(feed, area)
        
        if disruption:
            print(f"\nDisruption found for area: {area}")
            if should_send_notification(disruption, min_interval):
                title = "Water Outage"
                message = f"Disruption in {area}: {disruption.get('description', '')}"
                send_pushover_notification(pushover_api, pushover_user, title, message)
                save_last_notification(disruption)
                print("Notification sent!")
            else:
                print("Disruption found but notification skipped (too soon or duplicate)")
        else:
            print("No disruptions found in your area.")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
