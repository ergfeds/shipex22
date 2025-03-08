import requests
import time
import os
import logging
from datetime import datetime
import random

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('keep_alive')

def get_render_url():
    # This will automatically detect the current domain
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # Try to get the domain from environment
        if 'RENDER_EXTERNAL_URL' in os.environ:
            url = os.environ['RENDER_EXTERNAL_URL']
            logger.info(f"Using RENDER_EXTERNAL_URL: {url}")
            return url
        
        # Fallback to APP_URL environment variable
        if 'APP_URL' in os.environ:
            url = os.environ['APP_URL']
            logger.info(f"Using APP_URL: {url}")
            return url
        
        # Fallback to getting it from the request
        logger.info("Attempting to get URL from Render API")
        response = requests.get('https://api.render.com/deploy/url', headers=headers, timeout=5)
        if response.status_code == 200:
            url = response.text.strip()
            logger.info(f"Got URL from Render API: {url}")
            return url
    except Exception as e:
        logger.error(f"Error getting Render URL: {e}")
    
    # Hardcoded fallback (update this with your actual Render URL)
    fallback_url = "https://your-render-app-url.onrender.com"
    logger.warning(f"Using fallback URL: {fallback_url}")
    return fallback_url

def ping_server():
    try:
        url = get_render_url()
        if not url:
            logger.error("Could not determine server URL")
            return False
        
        # Add random parameter to avoid caching
        random_param = random.randint(1, 1000000)
        endpoints = [
            f"{url}/health?nocache={random_param}",
            f"{url}/?nocache={random_param}"
        ]
        
        for endpoint in endpoints:
            try:
                logger.info(f"Pinging {endpoint}")
                response = requests.get(endpoint, timeout=10)
                logger.info(f"Ping status: {response.status_code}")
                if response.status_code < 400:  # Any successful or redirect response
                    logger.info("Ping successful")
                    return True
            except Exception as e:
                logger.error(f"Ping to {endpoint} failed: {e}")
        
        logger.error("All ping attempts failed")
        return False
    except Exception as e:
        logger.error(f"Ping failed with exception: {e}")
        return False

def main():
    logger.info("[KEEP-ALIVE] Service starting...")
    
    # Initial wait to ensure the app is fully started
    time.sleep(30)
    
    failures = 0
    while True:
        success = ping_server()
        
        if success:
            failures = 0
            # Ping every 5 minutes (300 seconds) to be well within the 15-minute timeout
            # Add some randomness to avoid predictable patterns
            sleep_time = 300 + random.randint(-30, 30)
        else:
            failures += 1
            logger.warning(f"Ping failure count: {failures}")
            # If we've failed multiple times, try more frequently
            sleep_time = max(60, 300 - (failures * 30))
        
        logger.info(f"Sleeping for {sleep_time} seconds")
        time.sleep(sleep_time)

if __name__ == "__main__":
    main() 