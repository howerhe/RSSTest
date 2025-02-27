import feedparser
from feedgen.feed import FeedGenerator
from datetime import datetime, timedelta, timezone
import argparse
import logging
import html
import os
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
RSS_URL = "https://www.solidot.org/index.rss"
TIME_WINDOW = 24  # hours
OUTPUT_PATH = "merged_feed.xml"
FEED_TITLE = "Solidot 聚合长文章"
FEED_DESCRIPTION = "每日Solidot文章聚合"
DEFAULT_FEED_LINK = "https://example.com/merged_feed.xml"
# Timezone for Solidot (China)
TIMEZONE_OFFSET = 8  # GMT+8

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Merge RSS entries into a single feed.')
    parser.add_argument('--feed-link', default=DEFAULT_FEED_LINK,
                        help=f'Link for the generated feed (default: {DEFAULT_FEED_LINK})')
    return parser.parse_args()

def safe_html(text):
    """Sanitize HTML content."""
    return html.escape(text)

def merge_entries(feed_link):
    """
    Fetch and merge RSS entries within a specified time window.
    
    Args:
        feed_link (str): Link for the generated feed
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Fetch the original RSS feed
        logger.info(f"Fetching RSS feed from {RSS_URL}")
        feed = feedparser.parse(RSS_URL)
        
        if hasattr(feed, 'bozo') and feed.bozo:
            logger.warning(f"Feed parsing error: {feed.bozo_exception}")
        
        entries = feed.entries
        logger.info(f"Found {len(entries)} entries in the feed")
        
        # Filter entries by publication time
        # Create datetime in Solidot's timezone (GMT+8)
        china_tz = timezone(timedelta(hours=TIMEZONE_OFFSET))
        now = datetime.now(tz=china_tz)
        filtered_entries = []
        
        for entry in entries:
            try:
                # feedparser returns times in UTC
                published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                # Convert to China timezone for comparison
                china_time = published_time.astimezone(china_tz)
                if now - china_time < timedelta(hours=TIME_WINDOW):
                    filtered_entries.append(entry)
            except (AttributeError, TypeError) as e:
                logger.warning(f"Could not parse publication time for entry: {e}")
        
        logger.info(f"Found {len(filtered_entries)} entries within the last {TIME_WINDOW} hours")
        
        if not filtered_entries:
            logger.warning("No entries found within the specified time window")
            return False
        
        # Generate merged content
        merged_content = []
        for entry in filtered_entries:
            title = entry.get('title', 'No Title')
            description = entry.get('description', 'No Description')
            link = entry.get('link', '#')
            
            merged_content.append(
                f"<h3>{safe_html(title)}</h3>"
                f"<p>{description}</p>"  # Description might already be HTML
                f"<a href='{safe_html(link)}'>原文链接</a>"
                f"<hr>"
            )
        
        # Generate the new feed
        logger.info("Generating new RSS feed")
        fg = FeedGenerator()
        fg.title(FEED_TITLE)
        fg.link(href=feed_link)
        fg.description(FEED_DESCRIPTION)
        
        # Add metadata from original feed if available
        if hasattr(feed, 'feed'):
            if hasattr(feed.feed, 'language'):
                fg.language(feed.feed.language)
        
        # Add the merged entry
        fe = fg.add_entry()
        entry_date = now.strftime('%Y%m%d')
        fe.id(f"solidot-merge-{entry_date}")
        # Format title with requested format
        fe.title(f"奇客Solidot {now.strftime('%Y%m%d')}")
        fe.content("".join(merged_content), type='CDATA')
        fe.published(now)
        
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(OUTPUT_PATH)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Write the feed to a file
        fg.rss_file(OUTPUT_PATH)
        logger.info(f"RSS feed successfully written to {OUTPUT_PATH}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error merging entries: {e}", exc_info=True)
        return False

def main():
    """Main function to run the script."""
    args = parse_arguments()
    success = merge_entries(args.feed_link)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
