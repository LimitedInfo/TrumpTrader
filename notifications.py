import requests
import os
from dotenv import load_dotenv
import sys

load_dotenv()

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"

def send_pushover_notification(message, title=None, priority=0, sound=None, device=None, url=None, url_title=None, html=0):
    """Sends a notification via the Pushover API.

    Args:
        message (str): The main notification message (required).
        title (str, optional): The title of the notification. Defaults to None (uses app name).
        priority (int, optional): Notification priority (-2 to 2). Defaults to 0.
        sound (str, optional): Name of the notification sound. Defaults to None (uses user default).
        device (str, optional): Specific device name to target. Defaults to None (all devices).
        url (str, optional): Supplementary URL. Defaults to None.
        url_title (str, optional): Title for the supplementary URL. Defaults to None.
        html (int, optional): Set to 1 to enable HTML parsing. Defaults to 0.

    Returns:
        bool: True if the notification was sent successfully, False otherwise.
    """
    api_token = os.getenv("PUSHOVER_API_TOKEN")
    user_key = os.getenv("PUSHOVER_USER_KEY")

    if not api_token:
        print("Error: PUSHOVER_API_TOKEN not found in .env file.", file=sys.stderr)
        return False
    if not user_key:
        print("Error: PUSHOVER_USER_KEY not found in .env file. Please add it.", file=sys.stderr)
        return False
    if not message:
        print("Error: Message content cannot be empty.", file=sys.stderr)
        return False

    payload = {
        "token": api_token,
        "user": user_key,
        "message": message,
        "priority": priority,
        "html": html
    }

    # Add optional parameters if they are provided
    if title:
        payload["title"] = title
    if sound:
        payload["sound"] = sound
    if device:
        payload["device"] = device
    if url:
        payload["url"] = url
    if url_title:
        payload["url_title"] = url_title
    # Note: Attachments require different handling (files) and are not included here.

    try:
        print(f"Sending Pushover notification: Title='{title}', Message='{message[:50]}...'")
        response = requests.post(PUSHOVER_API_URL, data=payload, timeout=10)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        response_data = response.json()
        if response_data.get("status") == 1:
            print(f"Pushover notification sent successfully! Request ID: {response_data.get('request')}")
            return True
        else:
            errors = response_data.get("errors", ["Unknown error"])
            print(f"Pushover API error: {', '.join(errors)}", file=sys.stderr)
            return False

    except requests.exceptions.RequestException as e:
        print(f"Error sending Pushover notification: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return False

# Example usage (for testing the module directly)
if __name__ == "__main__":
    print("Testing Pushover notification module...")
    # Make sure PUSHOVER_USER_KEY is set in your .env file before running this
    if os.getenv("PUSHOVER_USER_KEY"):
        test_message = "This is a test notification from notifications.py!"
        test_title = "Test Notification"
        if send_pushover_notification(test_message, title=test_title, priority=1):
            print("Test notification sent successfully.")
        else:
            print("Test notification failed.")
    else:
        print("Skipping test: PUSHOVER_USER_KEY not found in .env file.") 