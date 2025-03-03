import argparse
import hashlib
import json
import logging
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import anthropic
import feedparser
from feedgen.feed import FeedGenerator
from newspaper import Article

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SummaryCache:
    """Cache system for storing article summaries to reduce API calls"""

    def __init__(self, cache_dir=None):
        """Initialize the cache with SQLite database"""
        # Create cache directory if it doesn't exist
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), '..', '.cache')
        os.makedirs(cache_dir, exist_ok=True)

        # Use the cache directory
        self.cache_file = os.path.join(cache_dir, "summary_cache.db")
        self.conn = sqlite3.connect(self.cache_file)
        self.create_table()

    def create_table(self):
        """Create the cache table if it doesn't exist"""
        cursor = self.conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            article_hash TEXT PRIMARY KEY,
            url TEXT,
            title TEXT,
            summary TEXT,
            timestamp TEXT
        )
        ''')
        self.conn.commit()

    def get(self, url, title, content):
        """Get a cached summary if it exists"""
        # Create a unique hash for the article based on URL and content
        article_hash = self._create_hash(url, content)

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT summary FROM summaries WHERE article_hash = ?",
            (article_hash,)
        )
        result = cursor.fetchone()

        if result:
            logger.info(f"Cache hit for article: {title}")
            return result[0]

        logger.info(f"Cache miss for article: {title}")
        return None

    def set(self, url, title, content, summary):
        """Save a summary to the cache"""
        article_hash = self._create_hash(url, content)
        timestamp = datetime.now(timezone.utc).isoformat()

        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO summaries VALUES (?, ?, ?, ?, ?)",
            (article_hash, url, title, summary, timestamp)
        )
        self.conn.commit()
        logger.info(f"Cached summary for article: {title}")

    def _create_hash(self, url, content):
        """Create a unique hash for an article"""
        # Use first 1000 chars of content to avoid excessive hashing
        content_sample = content[:1000] if content else ""
        hash_string = f"{url}:{content_sample}"
        return hashlib.md5(hash_string.encode('utf-8')).hexdigest()

    def cleanup(self, days=30):
        """Remove entries older than specified days"""
        cutoff = (datetime.now(timezone.utc) -
                  timedelta(days=days)).isoformat()

        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM summaries WHERE timestamp < ?",
            (cutoff,)
        )
        self.conn.commit()
        logger.info(f"Cleaned up cache entries older than {days} days")

    def close(self):
        """Close the database connection"""
        self.conn.close()


# Default values for configuration
DEFAULT_VALUES = {
    'summary_length': 150,
    'model': 'claude-3-haiku-20240307',
    'system_prompt': 'You are a helpful assistant that summarizes articles concisely.',
    'max_tokens': 150,
    'temperature': 0.3,
    'output_formats': ['json'],
    'do_summarize': True,
    'user_prompt': None
}

# List of settings that can be overridden at different levels
OVERRIDABLE_SETTINGS = list(DEFAULT_VALUES.keys())

# Global-only settings that cannot be overridden
GLOBAL_ONLY_SETTINGS = ['output_directory', 'cache_directory', 'cache_enabled']


class RSSDigestTool:
    def __init__(self, config, api_key=None, digest_filter=None):
        """
        Initialize the RSS Digest Tool with configuration

        Args:
            config (dict): Configuration for the digest tool
            api_key (str): API key for AI summarization, overrides config if provided
            digest_filter (str): Optional name of a specific digest to process
        """
        self.config = config
        self.digest_filter = digest_filter

        # Set up output directory (global setting only)
        self.output_dir = config.get('output_directory', 'output')
        os.makedirs(self.output_dir, exist_ok=True)

        # Set up cache (global settings only)
        self.cache_enabled = config.get('cache_enabled', True)
        cache_dir = config.get('cache_directory', '.cache')

        # Configure AI client if API key is provided
        api_key = api_key or os.environ.get(
            'ANTHROPIC_API_KEY') or config.get('api_key')
        if api_key:
            self.anthropic_client = anthropic.Anthropic(api_key=api_key)
        else:
            self.anthropic_client = None
            logger.warning(
                "No API key provided. Summarization will be disabled.")

        # Initialize cache if enabled
        if self.cache_enabled:
            self.cache = SummaryCache(cache_dir)
        else:
            self.cache = None

    def get_effective_config(self, source_config, digest_config=None):
        """
        Get effective configuration by cascading from global to digest to source

        Args:
            source_config (dict): Source feed configuration
            digest_config (dict): Digest configuration (optional)

        Returns:
            dict: Effective configuration with all necessary settings
        """
        # Define default values
        DEFAULT_VALUES = {
            'summary_length': 150,
            'model': 'claude-3-haiku-20240307',
            'system_prompt': 'You are a helpful assistant that summarizes articles concisely.',
            'max_tokens': 150,
            'temperature': 0.3,
            'output_formats': ['json'],
            'do_summarize': True,
            'user_prompt': None
        }

        # Start with global config (excluding digest-specific keys)
        global_keys = list(DEFAULT_VALUES.keys())

        effective_config = {
            k: v for k, v in self.config.items()
            if k in global_keys
        }

        # Add defaults for required fields
        for key, value in DEFAULT_VALUES.items():
            effective_config.setdefault(key, value)

        # Override with digest-level config if provided
        if digest_config:
            for key in global_keys:
                if key in digest_config:
                    effective_config[key] = digest_config[key]

        # Override with source-level config
        for key in global_keys:
            if key in source_config:
                effective_config[key] = source_config[key]

        return effective_config

    def fetch_rss(self, url):
        """Fetch and parse an RSS feed from the given URL"""
        try:
            logger.info(f"Fetching RSS from {url}")
            feed = feedparser.parse(url)
            return feed
        except Exception as e:
            logger.error(f"Error fetching RSS from {url}: {e}")
            return None

    def extract_full_text(self, url):
        """Extract full text and images from an article URL using newspaper3k"""
        try:
            article = Article(url)
            article.download()
            article.parse()

            # Get the top image if available
            top_image = None
            if article.top_image:
                top_image = article.top_image
            elif article.meta_img:
                top_image = article.meta_img
            elif len(article.images) > 0:
                # Get the first image from the article
                top_image = list(article.images)[0]

            return {
                'title': article.title,
                'text': article.text,
                'publish_date': article.publish_date,
                'image': top_image
            }
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return {
                'title': 'Unable to extract title',
                'text': 'Unable to extract content',
                'publish_date': None,
                'image': None
            }

    def summarize_content(self, title, content, effective_config):
        """
        Summarize article content, using cache if available

        Args:
            title (str): Article title
            content (str): Article content
            effective_config (dict): Effective configuration for this source
        """
        # Check if summarization is disabled
        if not effective_config.get('do_summarize', True):
            # Just return a truncated version of the content
            max_length = effective_config.get('summary_length', 150)
            return content[:max_length] + ("..." if len(content) > max_length else "")

        # Get summary length
        max_length = effective_config.get('summary_length', 150)

        # Check cache first if enabled
        if self.cache_enabled:
            feed_url = effective_config.get('url', '')
            cached_summary = self.cache.get(
                url=feed_url, title=title, content=content)
            if cached_summary:
                return cached_summary

        # If no cache hit, use AI to summarize
        try:
            if not self.anthropic_client:
                logger.warning("No API key provided, returning excerpt")
                return content[:max_length] + ("..." if len(content) > max_length else "")

            # Get AI settings from effective config
            model = effective_config.get('model', 'claude-3-haiku-20240307')
            max_tokens = effective_config.get('max_tokens', 150)
            temperature = effective_config.get('temperature', 0.3)
            system_prompt = effective_config.get(
                'system_prompt', 'You are a helpful assistant that summarizes articles concisely.')

            # User prompt content - ensure it's never null by using default if user_prompt is None
            user_prompt = effective_config.get('user_prompt')
            if user_prompt is None:
                user_text = f"Summarize this article in about 2-3 sentences. Title: {title}\n\nContent: {content}"
            else:
                user_text = user_prompt

            # Use Claude to summarize the content with effective settings
            message = self.anthropic_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_text
                            }
                        ]
                    }
                ]
            )
            summary = message.content[0].text

            # Store in cache if enabled
            if self.cache_enabled:
                feed_url = effective_config.get('url', '')
                self.cache.set(url=feed_url, title=title,
                               content=content, summary=summary)

            return summary
        except Exception as e:
            logger.error(f"Error during AI summarization: {e}")
            return content[:max_length] + ("..." if len(content) > max_length else "")

    def load_existing_feed(self, digest_id, format='json'):
        """Load existing feed to check for already processed articles"""
        base_filename = os.path.join(self.output_dir, digest_id)

        if format == 'json':
            try:
                with open(f"{base_filename}.json", 'r', encoding='utf-8') as f:
                    existing_feed = json.load(f)
                    # Create lookup dictionary of existing articles by URL
                    return {
                        item.get('url'): {
                            'title': item.get('title'),
                            'content_html': item.get('content_html'),
                            'content_text': item.get('content_text'),
                            'date_published': item.get('date_published')
                        }
                        for item in existing_feed.get('items', [])
                    }
            except (FileNotFoundError, json.JSONDecodeError):
                return {}

        elif format in ('rss', 'atom'):
            try:
                existing_feed = feedparser.parse(
                    f"{base_filename}.{'xml' if format == 'rss' else 'atom'}")
                return {
                    entry.link: {
                        'title': entry.title,
                        'content': entry.content[0].value if hasattr(entry, 'content') else entry.summary,
                        'pub_date': entry.published if hasattr(entry, 'published') else None
                    }
                    for entry in existing_feed.entries
                }
            except Exception:
                return {}

        return {}

    def process_feed_entries(self, feed_entries, source_config, effective_config, digest_id):
        """
        Process entries from a single feed

        Args:
            feed_entries (list): List of RSS entries
            source_config (dict): Source feed configuration
            effective_config (dict): Effective configuration for this source
            digest_id (str): ID of the digest

        Returns:
            dict: Articles grouped by date
        """
        articles_by_date = defaultdict(list)

        # Extract feed URL and extract domain to use as source label
        feed_url = source_config.get('url', '')

        # Extract domain from URL to use as source label
        from urllib.parse import urlparse
        parsed_url = urlparse(feed_url)
        source_label = parsed_url.netloc

        # Load existing articles from each output format
        existing_articles = {}
        output_formats = effective_config.get('output_formats', ['json'])
        for format in output_formats:
            existing_articles.update(
                self.load_existing_feed(digest_id, format))

        for entry in feed_entries:
            # Extract URL
            url = entry.link if hasattr(entry, 'link') else ""

            # Skip if article already exists in output feed
            if url in existing_articles:
                logger.info(f"Skipping already processed article: {url}")

                # Add to articles_by_date using existing content
                if 'published_parsed' in entry:
                    pub_date = datetime(*entry.published_parsed[:6])
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                else:
                    # Parse date from existing feed if available
                    pub_date = datetime.fromisoformat(existing_articles[url]['date_published']) \
                        if existing_articles[url].get('date_published') \
                        else datetime.now(timezone.utc)

                date_key = pub_date.strftime('%Y-%m-%d')

                articles_by_date[date_key].append({
                    'title': existing_articles[url]['title'],
                    'url': url,
                    'summary': existing_articles[url].get('content_text', existing_articles[url].get('content')),
                    'pub_date': pub_date,
                    'feed_url': feed_url,
                    'source_label': source_label,
                    'image': None
                })
                continue

            # Process new articles
            # Extract publication date
            if 'published_parsed' in entry:
                pub_date = datetime(*entry.published_parsed[:6])
                pub_date = pub_date.replace(tzinfo=timezone.utc)
            else:
                # If no date is available, use current date
                pub_date = datetime.now(timezone.utc)

            # Format as YYYY-MM-DD
            date_key = pub_date.strftime('%Y-%m-%d')

            # Get full article content if needed
            if not hasattr(entry, 'content') or not entry.content:
                article_data = self.extract_full_text(url)
                full_text = article_data['text']
                title = entry.title if hasattr(
                    entry, 'title') else article_data['title']
            else:
                # Some RSS feeds include full content
                full_text = entry.content[0].value if hasattr(
                    entry, 'content') else entry.summary
                title = entry.title if hasattr(entry, 'title') else 'No title'

            # Summarize the content (with cache check)
            summary = self.summarize_content(
                title, full_text, effective_config)

            # Get image if available
            image_url = None
            if hasattr(entry, 'media_content') and entry.media_content:
                # Try to get image from media content
                for media in entry.media_content:
                    if 'url' in media and media.get('medium', '') == 'image':
                        image_url = media['url']
                        break

            # If no image from media, try to get from enclosures
            if not image_url and hasattr(entry, 'enclosures') and entry.enclosures:
                for enclosure in entry.enclosures:
                    if 'type' in enclosure and enclosure['type'].startswith('image/'):
                        image_url = enclosure.get('href', enclosure.get('url'))
                        break

            # If we did full text extraction, check for image there
            if not image_url and not hasattr(entry, 'content'):
                article_data = self.extract_full_text(url)
                if article_data.get('image'):
                    image_url = article_data['image']

            # Add to the grouped dictionary
            articles_by_date[date_key].append({
                'title': title,
                'url': url,
                'summary': summary,
                'pub_date': pub_date,
                'feed_url': feed_url,
                'source_label': source_label,
                'image': image_url
            })

        return articles_by_date

    def get_feed_generator(self, feed_title="RSS Digest"):
        """Create and configure a FeedGenerator instance"""
        fg = FeedGenerator()

        # Set required fields
        fg.title(feed_title)

        # Set a link (required for RSS)
        fg.link(href="https://example.com/", rel='alternate')

        # Set ID (required for Atom)
        fg.id("https://example.com/" + feed_title.lower().replace(' ', '-'))

        fg.description('Daily digest of articles')
        fg.language('en')
        return fg

    def generate_json_feed(self, articles_by_date, output_file, feed_title="RSS Digest"):
        """Generate a JSON Feed format (https://jsonfeed.org/) with daily digest entries"""
        feed_items = []

        # Add entries for each day (most recent first)
        for date_key in sorted(articles_by_date.keys(), reverse=True):
            articles = articles_by_date[date_key]

            # Skip days with no articles
            if not articles:
                continue

            # Create content for this day's digest
            content_html = f"<h1>Daily Digest for {date_key}</h1>\n"
            content_text = f"Daily Digest for {date_key}\n\n"

            # Group articles by feed source
            articles_by_source = defaultdict(list)
            for article in articles:
                source_label = article.get('source_label', 'Unknown Source')
                articles_by_source[source_label].append(article)

            # Process each feed's articles
            for source_label, source_articles in articles_by_source.items():
                # Add source header if we have multiple sources
                if len(articles_by_source) > 1:
                    content_html += f"<h2>From {source_label}</h2>\n"
                    content_text += f"From {source_label}\n\n"

                # Process articles from this source
                for article in source_articles:
                    content_html += f"<h3><a href='{article['url']}'>{article['title']}</a></h3>\n"
                    content_text += f"{article['title']}\n"

                    if article.get('image'):
                        content_html += f"<img src='{article['image']}' style='max-width:100%; margin:10px 0;' alt='{article['title']}' />\n"

                    content_html += f"<p>{article['summary']}</p>\n"
                    content_text += f"{article['summary']}\n"
                    content_text += f"URL: {article['url']}\n\n"
                    content_html += "<hr>\n"

            # Create a feed item for this day's digest
            feed_item = {
                "id": f"digest-{date_key}",
                "url": articles[0].get('feed_url', ""),
                "title": f"Daily Digest for {date_key}",
                "content_html": content_html,
                "content_text": content_text,
                "date_published": articles[0]['pub_date'].isoformat(),
            }

            # Add to feed items
            feed_items.append(feed_item)

        # Create the full JSON Feed object
        json_feed = {
            "version": "https://jsonfeed.org/version/1.1",
            "title": feed_title,
            "home_page_url": "",
            "feed_url": output_file,
            "items": feed_items
        }

        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_feed, f, ensure_ascii=False, indent=2)

        logger.info(f"Generated JSON feed at {output_file}")
        return output_file

    def generate_feeds(self, articles_by_date, digest_config):
        """Generate feeds in all configured formats"""
        # Get digest ID (either specified or generated from name)
        digest_id = digest_config.get('digest_id')
        if not digest_id:
            # Generate digest ID from name
            digest_name = digest_config.get('name', 'RSS Digest')
            digest_id = digest_name.lower().replace(' ', '_').replace('-', '_')
            # Remove any non-alphanumeric characters except underscores
            digest_id = ''.join(
                c for c in digest_id if c.isalnum() or c == '_')

        base_filename = os.path.join(self.output_dir, digest_id)
        results = {}

        # Get output formats
        output_formats = digest_config.get(
            'output_formats', self.config.get('output_formats', ['json']))

        # Get digest name
        digest_name = digest_config.get('name', 'RSS Digest')

        # Prepare feed generator if needed for RSS/Atom
        if "rss" in output_formats or "atom" in output_formats:
            fg = self.get_feed_generator(digest_name)

            # Add entries to the feed
            for date_key in sorted(articles_by_date.keys(), reverse=True):
                articles = articles_by_date[date_key]

                # Skip days with no articles
                if not articles:
                    continue

                # Create an entry for this day's digest
                fe = fg.add_entry()
                fe.title(f'Daily Digest for {date_key}')

                # Ensure a valid link for the entry (required field)
                entry_link = articles[0].get(
                    'feed_url', "https://example.com/")
                if not entry_link or entry_link == "":
                    entry_link = "https://example.com/"
                fe.link(href=entry_link)

                # Set ID for the entry (required for Atom)
                fe.id(f"https://example.com/digest/{digest_id}/{date_key}")

                # Ensure the pub_date has timezone info
                pub_date = articles[0]['pub_date']
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                fe.pubDate(pub_date)

                # Compile the content with all articles for the day
                content = f"<h1>Daily Digest for {date_key}</h1>\n"

                # Group articles by feed source
                articles_by_source = defaultdict(list)
                for article in articles:
                    source_label = article.get(
                        'source_label', 'Unknown Source')
                    articles_by_source[source_label].append(article)

                # Process each feed's articles
                for source_label, source_articles in articles_by_source.items():
                    # Add source header if we have multiple sources
                    if len(articles_by_source) > 1:
                        content += f"<h2>From {source_label}</h2>\n"

                    # Process articles from this source
                    for article in source_articles:
                        content += f"<h3><a href='{article['url']}'>{article['title']}</a></h3>\n"

                        if article.get('image'):
                            content += f"<img src='{article['image']}' style='max-width:100%; margin:10px 0;' alt='{article['title']}' />\n"

                        content += f"<p>{article['summary']}</p>\n"
                        content += "<hr>\n"

                fe.content(content, type='html')

        # Generate outputs in requested formats
        if "rss" in output_formats:
            rss_file = f"{base_filename}.xml"
            fg.rss_file(rss_file)
            logger.info(f"Generated RSS feed at {rss_file}")
            results["rss"] = rss_file

        if "atom" in output_formats:
            atom_file = f"{base_filename}.atom"
            fg.atom_file(atom_file)
            logger.info(f"Generated Atom feed at {atom_file}")
            results["atom"] = atom_file

        if "json" in output_formats:
            json_file = f"{base_filename}.json"
            self.generate_json_feed(articles_by_date, json_file, digest_name)
            results["json"] = json_file

        return results

    def should_process_digest(self, digest_config):
        """
        Determine if a digest should be processed based on filter

        Args:
            digest_config (dict): Digest configuration

        Returns:
            bool: True if the digest should be processed, False otherwise
        """
        # If a digest filter is specified, only process matching digests
        if self.digest_filter and digest_config.get('name') != self.digest_filter:
            return False

        # Always process the digest (frequency feature removed)
        return True

    def process(self):
        """Process digests based on configuration"""
        results = {}

        # Process each digest defined in the configuration
        for digest_config in self.config.get('digests', []):
            # Skip if this digest shouldn't be processed now
            if not self.should_process_digest(digest_config):
                logger.info(
                    f"Skipping digest: {digest_config.get('name')} (not scheduled for current time)")
                continue

            # Get digest name
            digest_name = digest_config.get('name', 'RSS Digest')
            logger.info(f"Processing digest: {digest_name}")

            # Track all articles for this digest
            all_articles_by_date = defaultdict(list)

            # Process each source defined for this digest
            for source_config in digest_config.get('sources', []):
                # Check if this is a group with multiple sources
                if 'sources' in source_config:
                    # Process each source in the group
                    for nested_source in source_config.get('sources', []):
                        # Get effective configuration by cascading settings
                        nested_effective_config = self.get_effective_config(
                            nested_source,
                            # Combine digest and parent source config
                            {**digest_config, **source_config}
                        )

                        # Process this nested source
                        self._process_single_source(
                            nested_source,
                            nested_effective_config,
                            digest_config,
                            all_articles_by_date
                        )
                else:
                    # Get effective configuration by cascading settings
                    effective_config = self.get_effective_config(
                        source_config, digest_config)

                    # Process this source
                    self._process_single_source(
                        source_config,
                        effective_config,
                        digest_config,
                        all_articles_by_date
                    )

            # Generate digest output if we have articles
            if all_articles_by_date:
                digest_results = self.generate_feeds(
                    all_articles_by_date, digest_config)
                results[digest_name] = digest_results
            else:
                logger.info(f"No articles found for digest: {digest_name}")

        # Cleanup old cache entries if cache is enabled
        if self.cache_enabled and self.cache:
            self.cache.cleanup(days=30)

        return results

    def _process_single_source(self, source_config, effective_config, digest_config, all_articles_by_date):
        """
        Process a single source feed and add articles to the digest

        Args:
            source_config (dict): Source configuration
            effective_config (dict): Effective configuration for this source
            digest_config (dict): Parent digest configuration
            all_articles_by_date (dict): Dictionary to collect articles
        """
        # Skip if no URL
        if 'url' not in source_config:
            logger.error("Source config missing URL, skipping")
            return

        # Fetch the source RSS feed
        feed = self.fetch_rss(source_config['url'])
        if not feed:
            logger.error(f"Failed to fetch feed: {source_config['url']}")
            return

        # Get digest ID
        digest_id = digest_config.get('digest_id')
        if not digest_id:
            # Generate digest ID from name
            digest_name = digest_config.get('name', 'RSS Digest')
            digest_id = digest_name.lower().replace(' ', '_').replace('-', '_')
            # Remove any non-alphanumeric characters except underscores
            digest_id = ''.join(
                c for c in digest_id if c.isalnum() or c == '_')

        # Process entries from this feed
        articles_by_date = self.process_feed_entries(
            feed.entries,
            source_config,
            effective_config,
            digest_id
        )

        # Add to the combined collection for this digest
        for date, articles in articles_by_date.items():
            all_articles_by_date[date].extend(articles)

    def close(self):
        """Close any open resources"""
        if self.cache_enabled and self.cache:
            self.cache.close()


def run_digest_tool():
    """Run the RSS Digest Tool with configuration from environment or file"""

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Generate RSS digests with AI summaries')
    parser.add_argument('--api-key', help='API key for AI summarization')
    parser.add_argument(
        '--digest', help='Name of a specific digest to process')
    parser.add_argument('--config', required=True, help='Path to config file')

    args = parser.parse_args()

    # Load config file
    try:
        with open(args.config, 'r') as f:
            config = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error loading config file: {e}")
        return False

    # Initialize and run the tool
    tool = RSSDigestTool(
        config=config,
        api_key=args.api_key,
        digest_filter=args.digest
    )

    try:
        results = tool.process()
        return results
    finally:
        tool.close()


if __name__ == "__main__":
    run_digest_tool()
