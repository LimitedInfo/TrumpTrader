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
        # Get the directory path where the driver is installed
        driver_install_path = ChromeDriverManager().install()
        print(f"Driver manager install path result: {driver_install_path}")

        # Construct the expected path to the executable
        # The install path might point to the directory or a file within it.
        if os.path.isdir(driver_install_path):
            driver_dir = driver_install_path
        else:
            driver_dir = os.path.dirname(driver_install_path)
        
        expected_driver_path = os.path.join(driver_dir, "chromedriver.exe")
        print(f"Expecting driver executable at: {expected_driver_path}")
        
        if not os.path.isfile(expected_driver_path):
            print(f"Error: chromedriver.exe not found at the expected path: {expected_driver_path}", file=sys.stderr)
            # Attempt to use the path directly from install() as a fallback, though it might fail
            print("Falling back to using the direct path from ChromeDriverManager...")
            service = ChromeService(driver_install_path) 
        else:
            # Use the explicitly constructed path to chromedriver.exe
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
    """Scrapes the text content of the first tweet using a specific XPath."""
    tweet_text = None # Initialize tweet_text
    try:
        # Wait for the specific tweet text element to be present
        wait = WebDriverWait(driver, 20) 
        first_tweet_text_xpath = "//*[@id=\"timeline\"]/div/div[2]/div[1]/div[1]/div" # Using the specific XPath provided
        print(f"Waiting for the first tweet text element with XPath: {first_tweet_text_xpath}")
        
        # Find the element containing the tweet text directly
        tweet_text_element = wait.until(EC.presence_of_element_located((By.XPATH, first_tweet_text_xpath)))
        print("Tweet text element found.")

        tweet_text = tweet_text_element.text.strip()
        
        if tweet_text:
            print("\n--- First Tweet Text ---")
            print(tweet_text)
        else:
            print("\nFound the element, but it contains no text.")
            tweet_text = None # Ensure it's None if empty

    except TimeoutException:
        print(f"Error: Timed out waiting for the tweet text element with XPath: {first_tweet_text_xpath}")
    except NoSuchElementException:
        print(f"Error: Could not find the tweet text element using the specific XPath: {first_tweet_text_xpath}")
    except Exception as e:
        print(f"An error occurred while scraping the first tweet: {e}")
        tweet_text = None # Ensure it's None on error
    
    return tweet_text # Return the scraped text (or None)

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
    
    try:
        # Navigate to Truth Social
        print("Navigating to Truth Social...")
        driver.get("https://truthsocial.com")
        
        # Wait for the page to load with random delay
        print("Waiting for the page to load...")
        random_delay(3, 6) # Initial random wait for page load
        
        # Attempt Login
        if login_to_truth_social(driver):
            print("Login successful or process completed.")
            # Scrape the first tweet after login
            print("Attempting to scrape the first tweet...")
            scraped_tweet_text = scrape_first_tweet(driver)
            
            # Send notification if text was scraped
            if scraped_tweet_text:
                print("Sending Pushover notification for the scraped tweet...")
                notification_title = "New Truth Social Tweet Scraped"
                notifications.send_pushover_notification(scraped_tweet_text, title=notification_title, priority=1)
            else:
                print("No tweet text scraped, skipping notification.")
            
            # Optionally scrape general page info after login
            # print("Scraping info after login...")
            # scrape_page_info(driver)
        else:
            print("Login failed or encountered an error.")
            # Scrape info anyway if login failed?
            # scrape_page_info(driver)
        
        # Pause to see the result
        input("\nPress Enter to close the browser...")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the browser
        if 'driver' in locals():
            print("Closing the browser...")
            driver.quit()

if __name__ == "__main__":
    main() 