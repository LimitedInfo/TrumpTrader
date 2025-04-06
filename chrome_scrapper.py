from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import sys
import os
from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException, NoSuchElementException
# Import the notifications module
import notifications
# Import selenium-stealth
from selenium_stealth import stealth
import random # For random delays
import stat # Import stat for permission constants
import json # Added import
import threading # Added for timeout handling
import signal # Added for timeout handling

load_dotenv()

SEEN_TWEETS_FILE = 'seen_tweets.json' # Define storage file path

def print_status(message):
    """Prints a status message to stderr."""
    print(message, file=sys.stderr)

def random_delay(min_seconds=1, max_seconds=4):
    """Introduce a random delay to mimic human behavior."""
    delay = random.uniform(min_seconds, max_seconds)
    # Use print_status for non-essential output
    print_status(f"Waiting for {delay:.2f} seconds...")
    time.sleep(delay)

def setup_driver():
    chrome_options = ChromeOptions()
    # Uncomment the line below if you want to run in headless mode
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--start-maximized")
    
    # Add relevant Chrome options (some might overlap with Edge)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Standard stealth arguments
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    try:
        # Use ChromeDriverManager and ChromeService
        # Use print_status
        print_status("Installing/Locating Chrome driver...")
        # Get the path (which might be to the notice file or directory)
        driver_install_path = ChromeDriverManager().install()
        # Use print_status
        print_status(f"Driver manager install path result: {driver_install_path}")

        # Determine the directory containing the driver executable
        if os.path.isdir(driver_install_path):
            driver_dir = driver_install_path
        else:
            # Assume install() gave a path *within* the correct directory
            driver_dir = os.path.dirname(driver_install_path)
        # Use print_status
        print_status(f"Inferred driver directory: {driver_dir}")

        # Determine the correct executable name based on OS
        if sys.platform == "win32":
            driver_executable_name = "chromedriver.exe"
        else:
            # Assume Linux/macOS
            driver_executable_name = "chromedriver"
        
        # Construct the full path to the expected executable
        expected_driver_path = os.path.join(driver_dir, driver_executable_name)
        # Use print_status
        print_status(f"Expecting driver executable at: {expected_driver_path}")
        
        # Check if the constructed path is valid
        if not os.path.isfile(expected_driver_path):
            # Use print_status for error
            print_status(f"Error: {driver_executable_name} not found at the expected path: {expected_driver_path}")
            # Use print_status for fallback message
            print_status("Falling back to using the direct path from ChromeDriverManager (might fail)...")
            # Fallback: Use the potentially incorrect path from install() directly
            service = ChromeService(executable_path=driver_install_path) 
        else:
            # Success: Use the explicitly constructed and verified path
            # Use print_status
            print_status(f"Using verified executable path: {expected_driver_path}")

            # --- Set Execute Permissions (Linux/macOS fix) ---
            if sys.platform != "win32": # Only necessary on non-Windows
                try:
                    # Use print_status
                    print_status(f"Ensuring execute permissions for: {expected_driver_path}")
                    st = os.stat(expected_driver_path)
                    # Add execute permissions for user, group, and others (like chmod +x)
                    os.chmod(expected_driver_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    # Use print_status
                    print_status("Execute permissions set.")
                except Exception as chmod_err:
                    # Use print_status for warning
                    print_status(f"Warning: Failed to set execute permissions: {chmod_err}")
            # -----------------------------------------------

            service = ChromeService(executable_path=expected_driver_path)

        # Use print_status
        print_status("Initializing Chrome WebDriver with stealth...")
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Apply selenium-stealth patches
        stealth(driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
        )

        # Use print_status
        print_status("WebDriver initialized and stealth applied.")
        return driver
    except Exception as e:
        # Use print_status for error
        print_status(f"Error setting up WebDriver: {e}")
        sys.exit(1)

def login_to_truth_social(driver):
    """Handles the login process"""
    username = os.getenv("TRUTH_SOCIAL_USERNAME")
    password = os.getenv("TRUTH_SOCIAL_PASSWORD")

    if not username or not password:
        # Use print_status for error
        print_status("Error: TRUTH_SOCIAL_USERNAME or TRUTH_SOCIAL_PASSWORD not found in .env file.")
        return False

    try:
        wait = WebDriverWait(driver, 10)

        # Click the login button on the homepage
        # Use print_status
        print_status("Clicking the main login button...")
        login_button_main = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div/div[1]/div/div[2]/div/div[1]/div[2]/button")))
        login_button_main.click()
        # Use print_status
        print_status("Main login button clicked.")
        random_delay(1, 2) # Random delay after click

        # Wait for the login modal to appear and elements to be ready
        # Use print_status
        print_status("Waiting for login modal elements...")
        username_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='username']")))
        password_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='password']")))
        login_button_modal = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div/div[1]/div[2]/div/div/div/div[2]/form/div[2]/button[1]")))
        # Use print_status
        print_status("Login modal elements located.")

        # Enter credentials
        # Use print_status
        print_status("Entering username...")
        username_field.send_keys(username)
        random_delay(0.5, 1.5) # Small delay after typing username
        # Use print_status
        print_status("Entering password...")
        password_field.send_keys(password)
        random_delay(0.5, 1.5) # Small delay after typing password
        
        # Click the login button in the modal
        # Use print_status
        print_status("Clicking the modal login button...")
        login_button_modal.click()
        # Use print_status
        print_status("Login attempted.")

        # Wait a bit to see if login is successful (e.g., check for a specific element or URL change)
        random_delay(4, 7) # Longer random delay after login attempt
        # Use print_status
        print_status("Login process complete.")
        return True

    except Exception as e:
        # Use print_status for error
        print_status(f"Error during login: {e}")
        return False

def scrape_first_tweet(driver):
    """Scrapes the core text content of the first tweet using a specific XPath relative to the first item in the timeline."""
    tweet_text = None
    try:
        wait = WebDriverWait(driver, 20) # Increased wait time slightly just in case

        # 1. Find the main timeline container
        timeline_container_xpath = "//*[@id='timeline']/div/div[2]" # Corrected quotes
        print_status(f"Waiting for the timeline container element with XPath: {timeline_container_xpath}")
        timeline_container = wait.until(EC.presence_of_element_located((By.XPATH, timeline_container_xpath)))
        print_status("Timeline container element found.")
        random_delay(0.5, 1.5) # Small delay after finding container

        # 2. Find the first tweet item within the container
        first_tweet_item = None
        possible_first_item_selectors = ["./div[1]", "./*[1]"]
        for selector in possible_first_item_selectors:
             try:
                 print_status(f"Attempting to find first tweet item using relative XPath: {selector}")
                 # Use the timeline_container as the context for finding the element
                 first_tweet_item = timeline_container.find_element(By.XPATH, selector)
                 print_status("First tweet item found.")
                 break
             except NoSuchElementException:
                 print_status(f"Could not find first item using {selector}. Trying next selector...")
                 continue

        if not first_tweet_item:
            print_status("Error: Could not locate the first tweet item within the timeline container.")
            return None

        # 3. Wait for and find the core text within the first tweet item
        specific_text_xpath_relative = ".//div/div[2]/div[1]/div/div/p/p"
        print_status(f"Waiting for core text within the first item using relative XPath: {specific_text_xpath_relative}")

        try:
            # **** ADDED EXPLICIT WAIT for the text element relative to the first_tweet_item ****
            text_element = WebDriverWait(first_tweet_item, 10).until(
                EC.presence_of_element_located((By.XPATH, specific_text_xpath_relative))
            )
            # **********************************************************************************
            
            tweet_text = text_element.text.strip()
            if tweet_text:
                print_status("Core tweet text found using specific XPath.")
            else:
                print_status("Found specific text element, but it contained no text.")
                tweet_text = None
        except TimeoutException:
            print_status(f"Error: Timed out waiting for specific text element within the first tweet item using relative XPath: {specific_text_xpath_relative}")
            tweet_text = None
        except NoSuchElementException: # Should be less likely now with the wait, but kept for safety
            print_status(f"Error: Specific text element not found within the first tweet item using relative XPath: {specific_text_xpath_relative}")
            tweet_text = None

    except TimeoutException:
        print_status(f"Error: Timed out waiting for the timeline container element: {timeline_container_xpath}")
    except NoSuchElementException:
        print_status(f"Error: Could not find the timeline container element: {timeline_container_xpath}")
    except Exception as e:
        print_status(f"An error occurred while scraping the first tweet: {e}")

    return tweet_text

def load_seen_tweets(filepath):
    """Loads seen tweets from a JSON file."""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                # Use print_status
                print_status(f"Loading seen tweets from {filepath}...")
                data = json.load(f)
                # Use print_status
                print_status(f"Loaded {len(data)} tweets.")
                return set(data) # Convert list back to set
        else:
            # Use print_status
            print_status(f"Seen tweets file ({filepath}) not found. Starting with an empty set.")
            return set()
    except (IOError, json.JSONDecodeError) as e:
        # Use print_status for error
        print_status(f"Error loading seen tweets from {filepath}: {e}. Starting with an empty set.")
        return set()

def save_seen_tweets(tweets_set, filepath):
    """Saves seen tweets to a JSON file."""
    try:
        with open(filepath, 'w') as f:
            # Use print_status
            print_status(f"Saving {len(tweets_set)} seen tweets to {filepath}...")
            json.dump(list(tweets_set), f, indent=4) # Convert set to list for JSON
            # Use print_status
            print_status("Seen tweets saved.")
    except IOError as e:
        # Use print_status for error
        print_status(f"Error saving seen tweets to {filepath}: {e}")

def scrape_page_info(driver):
    """Get basic information from the page"""
    try:
        # Wait for page to load completely
        wait = WebDriverWait(driver, 10)
        
        # Try to get page title and metadata
        print("\n--- Page Information ---")
        print(f"Title: {driver.title}")
        print(f"Current URL: {driver.current_url}")
        
        # Get meta description if available
        try:
            meta_desc = driver.find_element(By.CSS_SELECTOR, 'meta[name="description"]')
            print(f"Meta Description: {meta_desc.get_attribute('content')}")
        except:
            print("Meta Description: Not found")
        
        # Get all links on the page
        print("\n--- Links on Page ---")
        links = driver.find_elements(By.TAG_NAME, 'a')
        for i, link in enumerate(links[:10], 1):  # Display only first 10 links to avoid clutter
            href = link.get_attribute('href')
            text = link.text.strip() or "[No text]"
            print(f"{i}. {text} -> {href}")
        
        if len(links) > 10:
            print(f"... and {len(links) - 10} more links")
        
        # Get all images
        print("\n--- Images on Page ---")
        images = driver.find_elements(By.TAG_NAME, 'img')
        for i, img in enumerate(images[:5], 1):  # Display only first 5 images
            src = img.get_attribute('src')
            alt = img.get_attribute('alt') or "[No alt text]"
            print(f"{i}. {alt} -> {src}")
        
        if len(images) > 5:
            print(f"... and {len(images) - 5} more images")
            
    except Exception as e:
        print(f"Error while scraping page: {e}")

def quit_driver_without_waiting(driver):
    """Quit the driver in a separate thread without waiting at all."""
    def quit_func():
        try:
            driver.quit()
            print_status("Browser closed successfully.")
        except Exception as e:
            print_status(f"Error closing browser: {e}")
    
    # Create and start a thread for quitting
    quit_thread = threading.Thread(target=quit_func)
    quit_thread.daemon = True  # Set as daemon so it doesn't block program exit
    quit_thread.start()
    # Immediately return without waiting
    print_status("Continuing program execution without waiting for browser to close...")

def main():
    # Initialize the WebDriver
    # Use print_status
    print_status("Setting up the WebDriver...")
    driver = setup_driver()
    
    # Load previously seen tweets from file
    seen_tweets = load_seen_tweets(SEEN_TWEETS_FILE)
    
    try:
        # Navigate to Truth Social
        # Use print_status
        print_status("Navigating to Truth Social...")
        driver.get("https://truthsocial.com")
        
        # Wait for the page to load
        # Use print_status
        print_status("Waiting for the initial page to load...")
        random_delay(3, 6)
        
        # Attempt Login
        if not login_to_truth_social(driver):
            # Use print_status for error
            print_status("Login failed. Exiting.")
            return # Exit if login fails
        
        # Use print_status
        print_status("\n--- Starting Tweet Monitoring Loop (Press Ctrl+C to stop) ---")
        
        while True:
            try:
                # Use print_status
                print_status("\nChecking for new tweet...")
                # Scrape the latest tweet
                current_tweet_text = scrape_first_tweet(driver)
                
                # --- Keep DEBUG PRINTS to stderr if needed --- 
                print_status(f"DEBUG: Scraped Text (raw): '{repr(current_tweet_text)}'")
                print_status(f"DEBUG: Seen Tweets Set: {seen_tweets}") 
                # --- END DEBUG PRINTS ---
                
                # Check if it's a new tweet
                is_new = current_tweet_text and current_tweet_text not in seen_tweets
                print_status(f"DEBUG: Is considered new? {is_new}") # Debug check result
                
                if is_new:
                    print_status(f"*** New tweet found! ***") # Prints to stderr

                    # --- PRINT THE TWEET TEXT TO STDOUT FOR THE SERVICE ---
                    print_status("DEBUG: About to print tweet to stdout...") # ADDED
                    print(current_tweet_text, flush=True) # Should print to stdout
                    print_status("DEBUG: Finished printing tweet to stdout.") # ADDED
                    # --- ADD A UNIQUE DELIMITER AFTER THE TWEET TEXT ---
                    print_status("DEBUG: About to print delimiter to stdout...") # ADDED
                    print("---END_OF_TWEET_DELIMITER---", flush=True) # Should print to stdout
                    print_status("DEBUG: Finished printing delimiter to stdout.") # ADDED
                    # --- END PRINT TO STDOUT ---

                    print_status("Sending Pushover notification...") # Prints to stderr
                    notification_title = "New Truth Social Tweet Scraped"
                    
                    # Add to seen tweets only if notification was successful
                    seen_tweets.add(current_tweet_text)
                    # Save the updated set to the file
                    save_seen_tweets(seen_tweets, SEEN_TWEETS_FILE)
                    return current_tweet_text

                elif current_tweet_text:
                    # Use print_status
                    print_status("Tweet is not new.")
                else:
                    # Use print_status
                    print_status("Could not scrape tweet text in this cycle.")

                # --- Active Wait and Element Check --- 
                refresh_interval_min = 15 # 15 seconds
                refresh_interval_max = 30 # 30 seconds
                wait_duration = random.uniform(refresh_interval_min, refresh_interval_max)
                start_time = time.time()
                found_indicator = False
                # Corrected XPath: Use * instead of // at the start if id is the first condition
                new_tweet_indicator_xpath = "//*[@id='soapbox']/div[1]/div/div[2]/div[1]/div/div[2]/main/div/div/div[2]/div/div[4]/div[2]/div[1]/a"

                print_status(f"\nActively waiting up to {wait_duration:.2f}s for new tweet indicator ({new_tweet_indicator_xpath}) or scheduled refresh...")

                while time.time() - start_time < wait_duration:
                    try:
                        # Check if the indicator element exists
                        indicator_elements = driver.find_elements(By.XPATH, new_tweet_indicator_xpath)
                        if indicator_elements: # If list is not empty, element found
                            print_status(f"*** New tweet indicator element found! Refreshing immediately. ***")
                            found_indicator = True
                            break # Exit the waiting loop to refresh now
                    except Exception as check_err:
                        # Log potential errors during check but continue waiting
                        print_status(f"Warning: Error checking for indicator element: {check_err}")
                    
                    # Wait for a short interval before checking again
                    time.sleep(1) # Check every 1 second
                
                if not found_indicator:
                     print_status(f"Wait duration elapsed without finding indicator. Proceeding with scheduled refresh.")
                # --- End Active Wait --- 

                print_status("Refreshing the page...")
                driver.refresh()
                # **** ADDED DELAY AFTER REFRESH ****
                print_status("Waiting after refresh for page to load...")
                random_delay(1, 2) # Give it a few seconds to reload content post-refresh
                # ***********************************

            except KeyboardInterrupt:
                # Use print_status
                print_status("\nCtrl+C detected. Exiting loop.")
                break # Exit the while loop
            except Exception as loop_error:
                # Use print_status for error
                print_status(f"\nAn error occurred within the monitoring loop: {loop_error}")
                print_status("Attempting to continue after a delay...")
                random_delay(30, 60) # Wait longer after an error before retrying
                # Consider adding logic here to try refreshing or re-logging in if errors persist

    except Exception as e:
        # Use print_status for critical error
        print_status(f"An critical error occurred: {e}")
    finally:
        # Close the browser
        if 'driver' in locals():
            # Use print_status
            print_status("Closing the browser...")
            # Replace driver.quit() with non-blocking version
            quit_driver_without_waiting(driver)

if __name__ == "__main__":
    main() 