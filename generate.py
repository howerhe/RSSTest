import json
import os

from rss_digest_tool import RSSDigestTool

# Configuration constants
CONFIG_PATH = 'config.json'
OUTPUT_DIR = 'output'


def main():
    # Check if config exists
    if not os.path.exists(CONFIG_PATH):
        print(f"Error: Configuration file {CONFIG_PATH} not found.")
        print("Please create a config.json file with your feed settings.")
        exit(1)

    # Load configuration
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {CONFIG_PATH}")
        exit(1)

    # Get API key from environment
    api_key = os.environ.get('ANTHROPIC_API_KEY')

    if not api_key:
        print("Warning: No API key provided. Summarization will be disabled.")
        print("Set the ANTHROPIC_API_KEY environment variable")

    # Create output directory
    output_dir = config.get('output_directory', OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)

    # Initialize the tool
    tool = RSSDigestTool(
        config=config,
        api_key=api_key
    )

    try:
        # Process feeds
        results = tool.process()

        if results:
            print("Successfully processed feeds!")
            create_index_html(config)
        else:
            print("No feeds were processed.")
    finally:
        tool.close()


# HTML template for index page - Note the double curly braces for CSS
INDEX_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>RSS Digest Feeds</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #333; }}
        ul {{ margin-top: 20px; }}
        li {{ margin-bottom: 10px; }}
        a {{ color: #0366d6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .updated {{ color: #666; font-size: 0.8em; }}
    </style>
</head>
<body>
    <h1>RSS Digest Feeds</h1>
    <p>Available digest feeds:</p>
    <ul>
{digest_links}
    </ul>
    <p class="updated">Last updated: {timestamp}</p>
</body>
</html>"""


def create_index_html(config):
    """Create a simple HTML index page that links to all digest feeds"""
    output_dir = config.get('output_directory', OUTPUT_DIR)

    # Find all digest files in the output directory
    digest_links = ""
    for digest in config.get('digests', []):
        digest_name = digest.get('name', 'Unknown')
        digest_id = digest.get('digest_id')

        if not digest_id:
            # Generate digest ID from name
            digest_id = digest_name.lower().replace(' ', '_').replace('-', '_')
            # Remove any non-alphanumeric characters except underscores
            digest_id = ''.join(
                c for c in digest_id if c.isalnum() or c == '_')

        # Check for different format files
        formats = []
        if os.path.exists(f"{output_dir}/{digest_id}.json"):
            formats.append(('JSON', f"{digest_id}.json"))
        if os.path.exists(f"{output_dir}/{digest_id}.xml"):
            formats.append(('RSS', f"{digest_id}.xml"))
        if os.path.exists(f"{output_dir}/{digest_id}.atom"):
            formats.append(('Atom', f"{digest_id}.atom"))

        if formats:
            digest_links += f'        <li>{digest_name}: '
            links = []
            for format_name, filename in formats:
                links.append(f'<a href="{filename}">{format_name}</a>')
            digest_links += ' | '.join(links) + '</li>\n'

    # Generate the HTML with the template
    timestamp = os.popen('date').read().strip()
    html = INDEX_HTML_TEMPLATE.format(
        digest_links=digest_links,
        timestamp=timestamp
    )

    # Write index.html to the output directory
    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, 'w') as f:
        f.write(html)
    print(f"Created index file at {index_path}")


if __name__ == "__main__":
    main()
