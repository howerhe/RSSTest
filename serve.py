import argparse
import http.server
import json
import os
import socketserver
import webbrowser


# Terminal colors for output
class Colors:
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    HEADER = '\033[95m'
    STATUS = '\033[94m'
    FEED = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'


# Default server settings
DEFAULT_PORT = 8000
DEFAULT_DIRECTORY = 'output'


def find_digest_files(directory=DEFAULT_DIRECTORY):
    """Find all digest files in the specified directory"""
    digest_files = []
    for file in os.listdir(directory):
        if file.endswith('.json') or file.endswith('.xml') or file.endswith('.atom'):
            digest_files.append(os.path.join(directory, file))
    return digest_files


def get_feed_info(file_path):
    """Get basic info about a feed file"""
    if file_path.endswith('.json'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    'title': data.get('title', 'Unknown feed'),
                    'items': len(data.get('items', [])),
                    'type': 'JSON Feed'
                }
        except Exception:
            return {'title': os.path.basename(file_path), 'items': '?', 'type': 'JSON (Error)'}

    # For XML/Atom feeds, just return the filename
    return {
        'title': os.path.basename(file_path),
        'items': '?',
        'type': 'XML/Atom'
    }


def run_server(port=DEFAULT_PORT, directory=DEFAULT_DIRECTORY):
    """Run an HTTP server for the output directory"""

    # Check if the directory exists
    if not os.path.exists(directory):
        print(
            f"{Colors.FAIL}Error: Directory '{directory}' does not exist.{Colors.ENDC}")
        return

    # Find digest files
    digest_files = find_digest_files(directory)
    if not digest_files:
        print(
            f"{Colors.WARNING}Warning: No digest files found in '{directory}'.{Colors.ENDC}")

    # Set up the server
    handler = http.server.SimpleHTTPRequestHandler
    os.chdir(directory)  # Change to the output directory

    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            server_url = f"http://localhost:{port}"

            # Print server info
            print(
                f"\n{Colors.HEADER}{Colors.BOLD}RSS Digest Local Server{Colors.ENDC}")
            print(f"{Colors.STATUS}Server running at: {server_url}{Colors.ENDC}")

            # Print available feeds
            if digest_files:
                print(f"\n{Colors.BOLD}Available Feeds:{Colors.ENDC}")
                for file in digest_files:
                    feed_name = os.path.basename(file)
                    feed_url = f"{server_url}/{feed_name}"
                    feed_info = get_feed_info(file)

                    print(f"{Colors.FEED}• {feed_info['title']}{Colors.ENDC}")
                    print(f"  Type: {feed_info['type']}")
                    print(f"  URL: {feed_url}")
                    if isinstance(feed_info['items'], int):
                        print(f"  Items: {feed_info['items']}")
                    print()

            # Print instructions for RSS readers
            print(f"{Colors.BOLD}To use in an RSS reader:{Colors.ENDC}")
            print("1. Add a new feed in your RSS reader")
            print(f"2. Enter the URL: {server_url}/[filename]")
            print("   (Use one of the URLs listed above)")
            print("\nPress Ctrl+C to stop the server\n")

            # Open the browser with the index page if it exists
            if os.path.exists('index.html'):
                webbrowser.open(server_url)

            # Start the server
            httpd.serve_forever()

    except KeyboardInterrupt:
        print(f"\n{Colors.STATUS}Server stopped.{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}Error starting server: {e}{Colors.ENDC}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run a local HTTP server for testing RSS feeds")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="Port to run the server on")
    parser.add_argument("--dir", default=DEFAULT_DIRECTORY,
                        help="Directory containing the feed files")

    args = parser.parse_args()
    run_server(args.port, args.dir)
