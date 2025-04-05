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

load_dotenv()

def random_delay(min_seconds=1, max_seconds=4):
    """Introduce a random delay to mimic human behavior."""
    delay = random.uniform(min_seconds, max_seconds)
    print(f"Waiting for {delay:.2f} seconds...")
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
        print("Installing/Locating Chrome driver...")
        # Get the path (which might be to the notice file or directory)
        driver_install_path = ChromeDriverManager().install()
        print(f"Driver manager install path result: {driver_install_path}")

        # Determine the directory containing the driver executable
        if os.path.isdir(driver_install_path):
            driver_dir = driver_install_path
        else:
            # Assume install() gave a path *within* the correct directory
            driver_dir = os.path.dirname(driver_install_path)
        print(f"Inferred driver directory: {driver_dir}")

        # Determine the correct executable name based on OS
        if sys.platform == "win32":
            driver_executable_name = "chromedriver.exe"
        else:
            # Assume Linux/macOS
            driver_executable_name = "chromedriver"
        
        # Construct the full path to the expected executable
        expected_driver_path = os.path.join(driver_dir, driver_executable_name)
        print(f"Expecting driver executable at: {expected_driver_path}")
        
        # Check if the constructed path is valid
        if not os.path.isfile(expected_driver_path):
            print(f"Error: {driver_executable_name} not found at the expected path: {expected_driver_path}", file=sys.stderr)
            print("Falling back to using the direct path from ChromeDriverManager (might fail)...")
            # Fallback: Use the potentially incorrect path from install() directly
            service = ChromeService(executable_path=driver_install_path) 
        else:
            # Success: Use the explicitly constructed and verified path
            print(f"Using verified executable path: {expected_driver_path}")
            service = ChromeService(executable_path=expected_driver_path)

        print("Initializing Chrome WebDriver with stealth...")
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

        print("WebDriver initialized and stealth applied.")
        return driver
    except Exception as e:
        print(f"Error setting up WebDriver: {e}")
        sys.exit(1)

def login_to_truth_social(driver):
    """Handles the login process"""
    username = os.getenv("TRUTH_SOCIAL_USERNAME")
    password = os.getenv("TRUTH_SOCIAL_PASSWORD")

    if not username or not password:
        print("Error: TRUTH_SOCIAL_USERNAME or TRUTH_SOCIAL_PASSWORD not found in .env file.")
        return False

    try:
        wait = WebDriverWait(driver, 10)

        # Click the login button on the homepage
        print("Clicking the main login button...")
        login_button_main = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div/div[1]/div/div[2]/div/div[1]/div[2]/button")))
        login_button_main.click()
        print("Main login button clicked.")
        random_delay(1, 2) # Random delay after click

        # Wait for the login modal to appear and elements to be ready
        print("Waiting for login modal elements...")
        username_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='username']")))
        password_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='password']")))
        login_button_modal = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div/div[1]/div[2]/div/div/div/div[2]/form/div[2]/button[1]")))
        print("Login modal elements located.")

        # Enter credentials
        print("Entering username...")
        username_field.send_keys(username)
        random_delay(0.5, 1.5) # Small delay after typing username
        print("Entering password...")
        password_field.send_keys(password)
        random_delay(0.5, 1.5) # Small delay after typing password
        
        # Click the login button in the modal
        print("Clicking the modal login button...")
        login_button_modal.click()
        print("Login attempted.")

        # Wait a bit to see if login is successful (e.g., check for a specific element or URL change)
        random_delay(4, 7) # Longer random delay after login attempt
        print("Login process complete.")
        return True

    except Exception as e:
        print(f"Error during login: {e}")
        return False

def scrape_first_tweet(driver):
    """Scrapes the core text content of the first tweet using a specific XPath."""
    tweet_text = None
    try:
        wait = WebDriverWait(driver, 20)
        # This XPath identifies the container of the first tweet
        first_tweet_container_xpath = "//*[@id=\"timeline\"]/div/div[2]/div[1]/div[1]/div"
        print(f"Waiting for the first tweet container element with XPath: {first_tweet_container_xpath}")
        
        tweet_container_element = wait.until(EC.presence_of_element_located((By.XPATH, first_tweet_container_xpath)))
        print("Tweet container element found.")

        # --- Use the SPECIFIC relative XPath provided by the user --- 
        specific_text_xpath_relative = ".//div/div[2]/div[1]/div/div/p/p" # Relative to the container
        print(f"Attempting to find core text using specific relative XPath: {specific_text_xpath_relative}")
        
        try:
            text_element = tweet_container_element.find_element(By.XPATH, specific_text_xpath_relative)
            tweet_text = text_element.text.strip()
            if tweet_text: 
                print("Core tweet text found using specific XPath.")
            else:
                print("Found specific element, but it contained no text.")
                tweet_text = None # Explicitly set to None
        except NoSuchElementException:
            print(f"Error: Element not found using specific relative XPath: {specific_text_xpath_relative}")
            tweet_text = None # Ensure None if element not found
        # -------------------------------------------------------------

        if tweet_text:
            print("\n--- First Tweet Core Text --- ")
            print(tweet_text)
        # No fallback needed now as we have a specific target

    except TimeoutException:
        print(f"Error: Timed out waiting for the tweet container element: {first_tweet_container_xpath}")
    except NoSuchElementException:
        print(f"Error: Could not find the tweet container element: {first_tweet_container_xpath}")
    except Exception as e:
        print(f"An error occurred while scraping the first tweet: {e}")
        tweet_text = None
    
    return tweet_text

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

def main():
    # Initialize the WebDriver
    print("Setting up the WebDriver...")
    driver = setup_driver()
    
    # Set to store the text of tweets already seen
    seen_tweets = set()
    
    try:
        # Navigate to Truth Social
        print("Navigating to Truth Social...")
        driver.get("https://truthsocial.com")
        
        # Wait for the page to load
        print("Waiting for the initial page to load...")
        random_delay(3, 6)
        
        # Attempt Login
        if not login_to_truth_social(driver):
            print("Login failed. Exiting.")
            return # Exit if login fails
        
        print("\n--- Starting Tweet Monitoring Loop (Press Ctrl+C to stop) ---")
        
        while True:
            try:
                print("\nChecking for new tweet...")
                # Scrape the latest tweet
                current_tweet_text = scrape_first_tweet(driver)
                
                # --- DEBUG PRINTS --- 
                print(f"DEBUG: Scraped Text (raw): '{repr(current_tweet_text)}'") # Show raw text with quotes/escapes
                print(f"DEBUG: Seen Tweets Set: {seen_tweets}") 
                # --- END DEBUG PRINTS ---
                
                # Check if it's a new tweet
                is_new = current_tweet_text and current_tweet_text not in seen_tweets
                print(f"DEBUG: Is considered new? {is_new}") # Debug check result
                
                if is_new:
                    print(f"*** New tweet found! ***")
                    print("Sending Pushover notification...")
                    notification_title = "New Truth Social Tweet Scraped"
                    
                    # Send notification
                    success = notifications.send_pushover_notification(
                        current_tweet_text, 
                        title=notification_title, 
                        priority=1
                    )
                    
                    print(f"DEBUG: Notification success? {success}") # Debug notification result
                    
                    if success:
                        # Add to seen tweets only if notification was successful
                        seen_tweets.add(current_tweet_text)
                        print("Notification sent and tweet marked as seen.")
                    else:
                        print("Failed to send notification for the new tweet.")
                        
                elif current_tweet_text:
                    print("Tweet is not new.")
                else:
                    print("Could not scrape tweet text in this cycle.")

                # Wait before refreshing
                # refresh_interval_min = 60 # 1 minute
                # refresh_interval_max = 120 # 2 minutes
                refresh_interval_min = 15 # 15 seconds
                refresh_interval_max = 30 # 30 seconds
                print(f"\nWaiting for {refresh_interval_min}-{refresh_interval_max} seconds before refresh...")
                random_delay(refresh_interval_min, refresh_interval_max)

                # Refresh the page
                print("Refreshing the page...")
                driver.refresh()
                print("Page refreshed. Waiting for content to load...")
                random_delay(5, 10) # Wait a bit after refresh for elements to potentially load
            
            except KeyboardInterrupt:
                print("\nCtrl+C detected. Exiting loop.")
                break # Exit the while loop
            except Exception as loop_error:
                print(f"\nAn error occurred within the monitoring loop: {loop_error}")
                print("Attempting to continue after a delay...")
                random_delay(30, 60) # Wait longer after an error before retrying
                # Consider adding logic here to try refreshing or re-logging in if errors persist

    except Exception as e:
        print(f"An critical error occurred: {e}")
    finally:
        # Close the browser
        if 'driver' in locals():
            print("Closing the browser...")
            driver.quit()

if __name__ == "__main__":
    main() 