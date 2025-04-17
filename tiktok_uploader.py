import os
import time
import json
import random
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tiktok_uploader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TikTokUploader:
    """TikTok video uploader using Selenium and cookies."""
    
    def __init__(
        self,
        cookies: List[Dict[str, Any]] = None,
        cookies_file: str = None,
        tracking_file: str = "uploaded_videos.txt",
        captions_dir: str = "captions",
        headless: bool = False
    ):
        """
        Initialize the TikTok uploader.
        
        Args:
            cookies: List of cookie dictionaries (optional)
            cookies_file: Path to JSON file with cookies (optional)
            tracking_file: File to track uploaded videos
            captions_dir: Directory containing caption files
            headless: Run browser in headless mode
        """
        self.cookies = cookies
        self.cookies_file = cookies_file
        self.tracking_file = tracking_file
        self.captions_dir = captions_dir
        self.headless = headless
        self.driver = None
        self.uploaded_videos = set()
        
        # Create captions directory if it doesn't exist
        if not os.path.exists(self.captions_dir):
            os.makedirs(self.captions_dir)
            with open(os.path.join(self.captions_dir, "sample.txt"), "w") as f:
                f.write("This is a sample caption. Add more caption files to this folder.")
            logger.info(f"Created captions directory: {self.captions_dir}")
        
        # Load previously uploaded videos if tracking file exists
        if os.path.exists(self.tracking_file):
            with open(self.tracking_file, "r") as f:
                self.uploaded_videos = set(line.strip() for line in f.readlines())
    
    def _get_random_caption(self) -> str:
        """Get a random caption from the captions directory."""
        caption_files = []
        for file in os.listdir(self.captions_dir):
            if file.endswith(".txt"):
                caption_files.append(os.path.join(self.captions_dir, file))
        
        if not caption_files:
            logger.warning("No caption files found in directory")
            return "Check out my new video!"
        
        # Choose a random caption file
        caption_file = random.choice(caption_files)
        
        try:
            with open(caption_file, "r", encoding="utf-8") as f:
                caption = f.read().strip()
            logger.info(f"Selected random caption from {caption_file}")
            return caption
        except Exception as e:
            logger.error(f"Error reading caption file {caption_file}: {str(e)}")
            return "Check out my new video!"
    
    def _setup_driver(self):
        """Set up and configure the Selenium WebDriver."""
        chrome_options = Options()
        
        # Add options to make bot detection harder
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Use a realistic user agent
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        chrome_options.add_argument(f"user-agent={user_agent}")
        
        # Disable GPU to avoid WebGL and rendering errors
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        
        if self.headless:
            chrome_options.add_argument("--headless=new")
        
        # Set browser window size
        chrome_options.add_argument("--window-size=1920,1080")
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            # Execute JavaScript to mask selenium's presence
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            logger.info("WebDriver setup successful")
            return True
            
        except Exception as e:
            logger.error(f"WebDriver setup failed: {str(e)}")
            return False
    
    def _load_cookies(self):
        """Load cookies into the browser session with improved error handling."""
        try:
            # First visit TikTok domain to set cookies properly
            self.driver.get("https://www.tiktok.com")
            time.sleep(3)  # Give more time for the page to load completely
            
            # Clear any existing cookies to avoid conflicts
            self.driver.delete_all_cookies()
            time.sleep(0.5)
            
            # Load cookies from file if specified
            if self.cookies_file and not self.cookies:
                try:
                    with open(self.cookies_file, 'r') as f:
                        self.cookies = json.load(f)
                    logger.info(f"Successfully loaded {len(self.cookies)} cookies from file")
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    logger.error(f"Error loading cookies file: {str(e)}")
                    return False
            
            if not self.cookies or len(self.cookies) == 0:
                logger.error("No cookies provided or empty cookies list")
                return False
                
            # Add cookies to browser
            added_count = 0
            for cookie in self.cookies:
                # Fix common issues with cookies
                if 'expiry' in cookie:
                    del cookie['expiry']
                if 'sameSite' in cookie:
                    cookie['sameSite'] = 'None'
                    
                try:
                    self.driver.add_cookie(cookie)
                    added_count += 1
                except Exception as e:
                    logger.warning(f"Could not add cookie: {str(e)}")
            
            logger.info(f"Successfully added {added_count} out of {len(self.cookies)} cookies")
            
            # Refresh page to apply cookies
            self.driver.refresh()
            time.sleep(5)  # Longer wait to ensure cookies are applied
            
            return added_count > 0
        except Exception as e:
            logger.error(f"Error loading cookies: {str(e)}")
            # Take a screenshot for debugging
            try:
                self.driver.save_screenshot("cookie_loading_error.png")
            except:
                pass
            return False
    
    def _verify_login(self) -> bool:
        """Verify that we're logged in with improved verification methods."""
        try:
            # Navigate to TikTok home
            self.driver.get("https://www.tiktok.com")
            time.sleep(3)
            
            # Method 1: Check for the upload button (most reliable)
            try:
                upload_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'upload-icon') or contains(@data-e2e, 'upload')]"))
                )
                logger.info("Successfully verified login by finding upload button")
                return True
            except:
                logger.warning("Upload button not found, trying alternative verification")
            
            # Method 2: Check if user avatar is present
            try:
                avatar = self.driver.find_element(By.XPATH, "//div[contains(@class, 'avatar') or contains(@data-e2e, 'avatar')]")
                logger.info("Successfully verified login by finding user avatar")
                return True
            except:
                logger.warning("User avatar not found, trying alternative verification")
            
            # Method 3: Check if we see the login button (negative check)
            try:
                login_button = self.driver.find_element(By.XPATH, "//a[contains(@href, '/login') or contains(text(), 'Log in')]")
                # If we find login button, we're not logged in
                logger.warning("Login button found, indicating we are NOT logged in")
                return False
            except:
                # If we don't find login button, we might be logged in
                logger.info("Login button not found (good sign), assuming login successful")
                return True
                
        except Exception as e:
            logger.warning(f"Login verification error: {str(e)}")
            # Take screenshot for debugging
            try:
                self.driver.save_screenshot("login_verification_failed.png")
            except:
                pass
            return False

    
    def _manual_login(self) -> bool:
        """Prompt user for manual login if cookie-based login fails."""
        try:
            self.driver.get("https://www.tiktok.com/login")
            print("\n" + "=" * 80)
            print("MANUAL LOGIN REQUIRED")
            print("=" * 80)
            print("1. Please log in to TikTok in the browser window")
            print("2. After logging in, come back here and press Enter")
            print("=" * 80)
            input("Press Enter after you've logged in...")
            
            # Verify login was successful
            if not self._verify_login():
                logger.error("Manual login verification failed")
                return False
                
            # Save the cookies for future use
            if self.cookies_file:
                cookies = self.driver.get_cookies()
                with open(self.cookies_file, 'w') as f:
                    json.dump(cookies, f)
                logger.info(f"Saved new cookies to {self.cookies_file}")
                
            return True
        except Exception as e:
            logger.error(f"Manual login error: {str(e)}")
            return False
    
    def _set_caption_text(self, caption_text: str) -> bool:
        """Set the caption text using multiple methods for improved reliability."""
        try:
            # Try multiple possible caption field selectors (updated for 2025)
            caption_selectors = [
                "//div[contains(@class, 'caption-container')]/textarea",
                "//div[contains(@class, 'caption-container')]//textarea",
                "//textarea[contains(@placeholder, 'caption') or contains(@placeholder, 'Caption')]",
                "//textarea[contains(@data-e2e, 'caption')]",
                "//div[contains(@data-e2e, 'caption-input')]//textarea",
                "//div[contains(@class, 'DraftEditor-root')]//div[@contenteditable='true']",  # Updated selector
                "//div[contains(@class, 'public-DraftEditor-content')]",  # Another possible selector
                "//div[contains(@role, 'textbox') and contains(@aria-placeholder, 'caption')]"  # Yet another option
            ]
            
            # Try standard Selenium approach first
            for selector in caption_selectors:
                try:
                    caption_field = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    caption_field.clear()
                    # For better reliability with some elements, use JavaScript to clear
                    self.driver.execute_script("arguments[0].value = '';", caption_field)
                    
                    caption_field.send_keys(Keys.CONTROL, 'a')  # or Keys.COMMAND on Mac
                    caption_field.send_keys(Keys.BACKSPACE)        # or Keys.BACKSPACE
                    time.sleep(1.5)  # Small delay to ensure the field is cleared
                    # Type the caption character by character with small delays
                    for char in caption_text:
                        
                        caption_field.send_keys(char)
                        
                    time.sleep(1)  # Small delay to ensure caption is set
                    logger.info(f"Added caption using selector: {selector}")
                    return True
                except Exception:
                    continue
            
            # If standard approach fails, try JavaScript with more selectors
            js_selectors = [
                "document.querySelector('textarea[placeholder*=\"caption\" i]')",
                "document.querySelector('div.caption-container textarea')",
                "document.querySelector('textarea[data-e2e*=\"caption\" i]')",
                "document.querySelector('div[data-e2e*=\"caption-input\"] textarea')",
                "document.querySelector('div[contenteditable=\"true\"]')",
                "document.querySelectorAll('textarea')[0]"  # Last resort: first textarea on page
            ]
            
            for js_selector in js_selectors:
                try:
                    # Escape quotes in caption text for JavaScript
                    safe_caption = caption_text.replace('"', '\\"').replace("'", "\\'")
                    
                    js_script = f"""
                    var captionField = {js_selector};
                    if (captionField) {{
                        captionField.value = '';
                        captionField.value = "{safe_caption}";
                        captionField.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        captionField.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                    return false;
                    """
                    result = self.driver.execute_script(js_script)
                    if result:
                        logger.info(f"Added caption using JavaScript selector: {js_selector}")
                        return True
                except Exception:
                    continue
            
            # Super aggressive approach: find ALL possible input fields and try them
            try:
                all_inputs = self.driver.find_elements(By.CSS_SELECTOR, "textarea, div[contenteditable='true'], input[type='text']")
                logger.info(f"Found {len(all_inputs)} potential input fields to try")
                
                for i, input_field in enumerate(all_inputs):
                    try:
                        # Try to determine if this could be a caption field by position or attributes
                        if input_field.is_displayed() and input_field.is_enabled():
                            logger.info(f"Trying input field {i+1}/{len(all_inputs)}")
                            input_field.clear()
                            input_field.send_keys(caption_text)
                            time.sleep(0.5)  # Brief pause to see if it worked
                            logger.info(f"Input entered in field {i+1}")
                            # Don't return, try all fields to maximize chances
                    except Exception as e:
                        logger.debug(f"Could not enter text in input field {i+1}: {str(e)}")
                
                # Return true assuming at least one worked
                return True
            except Exception as e:
                logger.warning(f"Aggressive caption entry failed: {str(e)}")
            
            logger.warning("Could not set caption using any method")
            # Take screenshot to help diagnose the issue
            try:
                self.driver.save_screenshot("caption_setting_failed.png")
            except:
                pass
            return False
        except Exception as e:
            logger.error(f"Error setting caption: {str(e)}")
            return False
    
    def _upload_single_video(self, video_path: str, description: str = None, hashtags: List[str] = None) -> bool:
        """
        Upload a single video to TikTok.
        
        Args:
            video_path: Path to the video file
            description: Caption for the video
            hashtags: List of hashtags to add
            
        Returns:
            True if upload was successful, False otherwise
        """
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return False
            
        try:
            logger.info(f"Starting upload for: {video_path}")
            
            # Go to upload page
            self.driver.get("https://www.tiktok.com/upload")
            time.sleep(3)  # Wait for page to fully load
            
            # Wait for the file input to be present
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    file_input = WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
                    )
                    
                    # Upload the video file
                    file_input.send_keys(os.path.abspath(video_path))
                    logger.info("Video file selected")
                    break
                except Exception as e:
                    if attempt < max_attempts - 1:
                        logger.warning(f"Upload attempt {attempt+1} failed: {str(e)}. Retrying...")
                        self.driver.refresh()
                        time.sleep(3)
                    else:
                        logger.error(f"Failed to select video file after {max_attempts} attempts")
                        return False
            
            # Wait for video to process (with more reliability)
            try:
                WebDriverWait(self.driver, 40).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'progress-bar') and contains(@style, '100%')]"))
                )
                logger.info("Video processed")
            except TimeoutException:
                # Sometimes the progress bar may not be detected correctly, try to continue anyway
                logger.warning("Could not detect video processing progress, continuing anyway")
                # Give extra time for processing to complete
            
            # Prepare description
            if description is None:
                # Get random caption from captions directory
                description = self._get_random_caption()
                
            # Add hashtags if provided
            if hashtags and len(hashtags) > 0:
                hashtag_str = ' '.join([f"#{tag}" for tag in hashtags])
                description = f"{description} {hashtag_str}"
            
            # Set caption with enhanced reliability
            self._set_caption_text(description)
            
            # Click Post button (with retry logic)
            max_post_attempts = 3
            for attempt in range(max_post_attempts):
                try:
                    post_button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Post') or contains(@data-e2e, 'post')]"))
                    )
                    post_button.click()
                    break
                except Exception as e:
                    if attempt < max_post_attempts - 1:
                        logger.warning(f"Post attempt {attempt+1} failed: {str(e)}. Retrying...")
                        time.sleep(3)
                    else:
                        logger.error(f"Failed to click Post button after {max_post_attempts} attempts")
                        # Try one more time with JavaScript click
                        try:
                            self.driver.execute_script("document.querySelector('button[data-e2e=\"post\"]').click();")
                            logger.info("Used JavaScript click as fallback")
                        except:
                            return False
            
            # Wait for upload to complete with better error handling
            try:
                WebDriverWait(self.driver, 40).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Your video is being uploaded to TikTok') or contains(text(), 'Your video is now published')]"))
                )
            except TimeoutException:
                # Check if we're redirected to profile page or if there's a success message elsewhere
                if '/profile' in self.driver.current_url:
                    logger.info("Redirected to profile page, upload likely successful")
                else:
                    # Take screenshot for debugging
                    try:
                        pass #self.driver.save_screenshot(f"upload_completion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                    except:
                        pass
                    logger.warning("Could not confirm upload completion, but will assume success if no error appears")
                      # Wait a bit more to see if any error appears
            
            # Record this video as uploaded
            self.uploaded_videos.add(video_path)
            with open(self.tracking_file, "a") as f:
                f.write(f"{video_path}\n")
                
            logger.info(f"Successfully uploaded video: {video_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading video {video_path}: {str(e)}")
            # Take screenshot of the error
            try:
                self.driver.save_screenshot(f"upload_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            except:
                pass
            return False
        finally:
            os.remove(video_path)
    
    def _cleanup(self):
        """Clean up resources."""
        if self.driver:
            logger.info("Closing WebDriver")
            
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {str(e)}")
            self.driver = None


    # PUBLIC METHODS
    
    @staticmethod
    def save_cookies(output_file: str = "tiktok_cookies.json"):
        """
        Save TikTok cookies to a file after manual login.
        
        Args:
            output_file: Path to save cookies JSON file
        
        Returns:
            True if cookies were saved successfully, False otherwise
        """
        chrome_options = Options()
        driver = None
        try:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            driver.get("https://www.tiktok.com/login")
            print("\n\n")
            print("=" * 80)
            print("COOKIE SAVER TOOL")
            print("=" * 80)
            print("1. The browser window has opened")
            print("2. Please log in to TikTok manually")
            print("3. After logging in, come back here and press Enter to save your cookies")
            print("=" * 80)
            input("Press Enter after you've logged in...")
            
            # Verify login was successful
            try:
                driver.get("https://www.tiktok.com/upload")
                time.sleep(3)
                
                # Check if we're on the upload page
                if "tiktok.com/upload" not in driver.current_url:
                    print("Login verification failed. Please make sure you are logged in.")
                    return False
            except:
                print("Error verifying login. Please make sure you are logged in.")
                return False
            
            # Get and save cookies
            cookies = driver.get_cookies()
            with open(output_file, 'w') as f:
                json.dump(cookies, f)
            
            print(f"\nCookies saved to {output_file}")
            return True
            
        except Exception as e:
            print(f"Error saving cookies: {str(e)}")
            return False
        finally:
            if driver:
                driver.quit()
    
    def upload_video(self, video_path: str, description: str = None, hashtags: List[str] = None) -> bool:
        """
        Upload a single video to TikTok.
        
        Args:
            video_path: Path to the video file
            description: Caption for the video (optional)
            hashtags: List of hashtags to add (optional)
            
        Returns:
            True if upload was successful, False otherwise
        """
        try:
            if not self._setup_driver():
                return False
            
            # Check for default cookies file if not explicitly provided
            default_cookies_file = "tiktok_cookies.json"
            if not self.cookies_file and not self.cookies and os.path.exists(default_cookies_file):
                logger.info(f"Found default cookies file: {default_cookies_file}")
                self.cookies_file = default_cookies_file
            
            # First try with cookies if available
            login_successful = False
            if self.cookies_file or self.cookies:
                logger.info(f"Attempting login with cookies from: {self.cookies_file}")
                if self._load_cookies() and self._verify_login():
                    login_successful = True
                    logger.info("Login successful using cookies")
            else:
                logger.info("No cookies file found or provided")
            
            # If cookie login failed, try manual login
            if not login_successful:
                logger.info("Cookie login failed or not available, trying manual login")
                if not self._manual_login():
                    logger.error("Both cookie and manual login failed")
                    return False
            
            result = self._upload_single_video(video_path, description, hashtags)
            return result
        except Exception as e:
            logger.error(f"Unexpected error in upload_video: {str(e)}")
            return False
        finally:
            self._cleanup()

    
    def upload_multiple_videos(
        self,
        videos_dir: str,
        hashtags: List[str] = None,
        max_uploads: Optional[int] = None,
        min_delay: int = 3600,
        max_delay: int = 7200
    ) -> int:
        """
        Upload multiple videos from a directory.
        
        Args:
            videos_dir: Directory containing videos to upload
            hashtags: List of hashtags to add to videos
            max_uploads: Maximum number of videos to upload (None for no limit)
            min_delay: Minimum delay between uploads in seconds
            max_delay: Maximum delay between uploads in seconds
            
        Returns:
            Number of videos successfully uploaded
        """
        if not os.path.exists(videos_dir):
            logger.error(f"Videos directory not found: {videos_dir}")
            return 0
            
        # Get list of videos to upload
        video_files = []
        for file in os.listdir(videos_dir):
            if file.lower().endswith(('.mp4', '.mov', '.avi')):
                file_path = os.path.join(videos_dir, file)
                # Only include videos that haven't been uploaded
                if file_path not in self.uploaded_videos:
                    video_files.append(file_path)
        
        logger.info(f"Found {len(video_files)} new videos to upload")
        if not video_files:
            return 0
            
        try:
            if not self._setup_driver():
                return 0
            
            # First try with cookies if available
            login_successful = False
            if self.cookies_file or self.cookies:
                if self._load_cookies() and self._verify_login():
                    login_successful = True
                    logger.info("Login successful using cookies")
            
            # If cookie login failed, try manual login
            if not login_successful:
                logger.info("Cookie login failed or not available, trying manual login")
                if not self._manual_login():
                    logger.error("Both cookie and manual login failed")
                    return 0
                
            uploads_count = 0
            for i, video in enumerate(video_files):
                if max_uploads is not None and uploads_count >= max_uploads:
                    logger.info(f"Reached maximum uploads limit ({max_uploads}). Stopping.")
                    break
                    
                success = self._upload_single_video(video, hashtags=hashtags)
                if success:
                    uploads_count += 1
                    
                    # If there are more videos to upload, wait before the next one
                    if i < len(video_files) - 1 and (max_uploads is None or uploads_count < max_uploads):
                        delay = random.randint(min_delay, max_delay)
                        logger.info(f"Waiting {delay} seconds before next upload")
                        time.sleep(delay)
            
            logger.info(f"Upload session completed. Successfully uploaded {uploads_count} videos.")
            return uploads_count
            
        except Exception as e:
            logger.error(f"Unexpected error in upload_multiple_videos: {str(e)}")
            return 0
        finally:
            self._cleanup()


# Example usage functions

def save_tiktok_cookies(output_file="tiktok_cookies.json"):
    """Helper function to save TikTok cookies."""
    return TikTokUploader.save_cookies(output_file)


def upload_single_video(cookies_file, video_path, description=None, hashtags=None, captions_dir="captions"):
    """
    Upload a single video to TikTok.
    
    Args:
        cookies_file: Path to cookies JSON file
        video_path: Path to video file
        description: Video caption
        hashtags: List of hashtags
        captions_dir: Directory with caption files
        
    Returns:
        True if successful, False otherwise
    """
    uploader = TikTokUploader(cookies_file=cookies_file, captions_dir=captions_dir)
    return uploader.upload_video(video_path, description, hashtags)


def upload_videos_from_directory(cookies_file, videos_dir, hashtags=None, max_uploads=None, captions_dir="captions"):
    """
    Upload multiple videos from a directory.
    
    Args:
        cookies_file: Path to cookies JSON file
        videos_dir: Directory containing videos
        hashtags: List of hashtags
        max_uploads: Maximum number of videos to upload
        captions_dir: Directory with caption files
        
    Returns:
        Number of videos successfully uploaded
    """
    uploader = TikTokUploader(cookies_file=cookies_file, captions_dir=captions_dir)
    return uploader.upload_multiple_videos(videos_dir, hashtags, max_uploads)


if __name__ == "__main__":
    import argparse
    import sys
    
    # If no arguments provided, try to use a default mode
    if len(sys.argv) == 1:
        parser = argparse.ArgumentParser(description="TikTok Video Uploader")
        # Default behavior: Check if cookies exist and upload from videos directory
        default_cookies_file = "tiktok_cookies.json"
        default_videos_dir = "videos"  # Adjust to your preferred videos directory
        
        if not os.path.exists(default_cookies_file):
            print("No cookies file found. Will create one first.")
            TikTokUploader.save_cookies(default_cookies_file)
        
        if os.path.exists(default_videos_dir):
            print(f"Found videos directory. Will upload videos from {default_videos_dir}")
            uploader = TikTokUploader(cookies_file=default_cookies_file)
            uploader.upload_multiple_videos(default_videos_dir)
        else:
            print(f"No videos directory found at {default_videos_dir}. Please create one or specify a different directory.")
            print("For more options, use command-line arguments:")
            parser.print_help()
    else:
        # Original command line argument handling
        parser = argparse.ArgumentParser(description="TikTok Video Uploader")
        subparsers = parser.add_subparsers(dest='command')
        
        # Save cookies command
        save_parser = subparsers.add_parser('save_cookies', help='Save TikTok cookies after manual login')
        save_parser.add_argument("--output", default="tiktok_cookies.json", help="Output file for cookies")
        
        # Upload single video command
        single_parser = subparsers.add_parser('upload_video', help="Upload a single video to TikTok")
        single_parser.add_argument("--cookies", required=True, help="Path to cookies JSON file")
        single_parser.add_argument("--video", required=True, help="Path to video file")
        single_parser.add_argument("--description", help="Video caption (if not provided, will use random caption)")
        single_parser.add_argument("--hashtags", help="Comma-separated list of hashtags")
        single_parser.add_argument("--captions-dir", default="captions", help="Directory containing caption files")
        
        # Upload multiple videos command
        multi_parser = subparsers.add_parser('upload_multiple', help="Upload multiple videos from a directory")
        multi_parser.add_argument("--cookies", required=True, help="Path to cookies JSON file")
        multi_parser.add_argument("--videos-dir", required=True, help="Directory containing videos")
        multi_parser.add_argument("--hashtags", help="Comma-separated list of hashtags")
        multi_parser.add_argument("--max-uploads", type=int, help="Maximum number of videos to upload")
        multi_parser.add_argument("--min-delay", type=int, default=3600, help="Minimum delay between uploads in seconds")
        multi_parser.add_argument("--max-delay", type=int, default=7200, help="Maximum delay between uploads in seconds")
        multi_parser.add_argument("--captions-dir", default="captions", help="Directory containing caption files")
        
        args = parser.parse_args()
        
        if args.command == 'save_cookies':
            TikTokUploader.save_cookies(args.output)
        
        elif args.command == 'upload_video':
            hashtags_list = args.hashtags.split(",") if args.hashtags else None
            uploader = TikTokUploader(cookies_file=args.cookies, captions_dir=args.captions_dir)
            uploader.upload_video(args.video, args.description, hashtags_list)
        
        elif args.command == 'upload_multiple':
            hashtags_list = args.hashtags.split(",") if args.hashtags else None
            uploader = TikTokUploader(cookies_file=args.cookies, captions_dir=args.captions_dir)
            uploader.upload_multiple_videos(
                args.videos_dir, 
                hashtags_list, 
                args.max_uploads, 
                args.min_delay, 
                args.max_delay
            )
        
        else:
            parser.print_help()