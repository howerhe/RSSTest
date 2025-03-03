# GitHub-based RSS Digest Tool - Setup Guide

This guide explains how to develop and deploy an RSS digest tool that runs automatically via GitHub Actions and makes the output RSS feed publicly accessible via GitHub Pages.

## Development Setup

### 1. Local Development Environment

```bash
# Create a new directory for your project
mkdir rss-digest-tool
cd rss-digest-tool

# Set up a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install feedparser newspaper3k openai feedgen schedule
pip freeze > requirements.txt
```

### 2. Create Core Script Files

Create the following files in your project directory:

**`rss_digest.py`** - Your main script (based on the implementation provided earlier)

**`config.json`** - Configuration file
```json
{
  "source_feeds": [
    {
      "url": "https://example.com/feed.xml",
      "name": "Example Blog"
    }
  ],
  "output_directory": "output",
  "summary_length": 150
}
```

**`run.py`** - Script to run from GitHub Actions
```python
import json
import os
from rss_digest import RSSDigestTool

def main():
    # Load configuration
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Get API key from GitHub secrets
    api_key = os.environ.get('OPENAI_API_KEY')
    
    # Create output directory
    os.makedirs(config['output_directory'], exist_ok=True)
    
    # Process each feed
    for feed in config['source_feeds']:
        output_file = f"{config['output_directory']}/{feed['name'].lower().replace(' ', '_')}_digest.xml"
        tool = RSSDigestTool(
            source_rss_url=feed['url'],
            openai_api_key=api_key,
            output_file=output_file
        )
        tool.process()
    
    # Create an index file that links to all feeds
    create_index_html(config)

def create_index_html(config):
    """Create a simple HTML index page that links to all digest feeds"""
    html = """<!DOCTYPE html>
<html>
<head>
    <title>RSS Digest Feeds</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #333; }
        ul { margin-top: 20px; }
        li { margin-bottom: 10px; }
        a { color: #0366d6; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .updated { color: #666; font-size: 0.8em; }
    </style>
</head>
<body>
    <h1>RSS Digest Feeds</h1>
    <p>Daily digests of the following feeds:</p>
    <ul>
"""
    
    # Add links to each feed
    for feed in config['source_feeds']:
        feed_name = feed['name']
        file_name = f"{feed_name.lower().replace(' ', '_')}_digest.xml"
        html += f'        <li><a href="{file_name}">{feed_name} Daily Digest</a></li>\n'
    
    # Close HTML
    html += f"""    </ul>
    <p class="updated">Last updated: {os.popen('date').read().strip()}</p>
</body>
</html>"""
    
    # Write index.html to the output directory
    with open(f"{config['output_directory']}/index.html", 'w') as f:
        f.write(html)

if __name__ == "__main__":
    main()
```

## GitHub Repository Setup

### 1. Initialize Git Repository

```bash
# Initialize a new Git repository
git init

# Create .gitignore file
echo "venv/
__pycache__/
*.pyc
.env" > .gitignore

# Initial commit
git add .
git commit -m "Initial commit with RSS digest tool"
```

### 2. Create GitHub Repository

1. Go to GitHub and create a new repository
2. Follow GitHub's instructions to push your local repository

### 3. Configure GitHub Actions

Create a workflow file at `.github/workflows/generate-digest.yml`:

```yaml
name: Generate RSS Digests

on:
  schedule:
    - cron: '0 5 * * *'  # Run daily at 5:00 UTC
  workflow_dispatch:      # Allow manual trigger

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Generate RSS digests
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      run: |
        python run.py
    
    - name: Deploy to GitHub Pages
      uses: JamesIves/github-pages-deploy-action@v4
      with:
        folder: output  # The folder the action should deploy
        branch: gh-pages  # The branch the action should deploy to
```

### 4. Add Your OpenAI API Key

1. Go to your GitHub repository
2. Navigate to Settings > Secrets > Actions
3. Click "New repository secret"
4. Name: `OPENAI_API_KEY`
5. Value: Your OpenAI API key
6. Click "Add secret"

### 5. Enable GitHub Pages

1. After your first workflow run, go to Settings > Pages
2. Source: Deploy from a branch
3. Branch: gh-pages
4. Folder: / (root)
5. Click "Save"

## Accessing Your RSS Feed

After the workflow runs and GitHub Pages is enabled, your RSS feed will be available at:

```
https://[your-username].github.io/[your-repo-name]/[feed-name]_digest.xml
```

The index page will be at:

```
https://[your-username].github.io/[your-repo-name]/
```

## Testing and Development

### Testing Locally

```bash
# Set your OpenAI API key
export OPENAI_API_KEY=your-api-key-here

# Run the script
python run.py

# Check output directory for generated files
ls -la output/
```

### Triggering Manual Updates

To generate a new digest manually:
1. Go to your GitHub repository
2. Navigate to Actions > Generate RSS Digests
3. Click "Run workflow"

## Customization Options

### Adding Multiple Feeds

Edit `config.json` to add more source feeds:

```json
{
  "source_feeds": [
    {
      "url": "https://example.com/feed.xml",
      "name": "Example Blog"
    },
    {
      "url": "https://anotherblog.com/rss",
      "name": "Another Blog"
    }
  ],
  "output_directory": "output",
  "summary_length": 150
}
```

### Styling the Output

You can customize the HTML templates in `run.py` and `rss_digest.py` to change the appearance of both the index page and the digest content.

## Troubleshooting

### Common Issues

1. **Workflow fails**: Check Actions tab for error logs
2. **Missing API key**: Ensure OPENAI_API_KEY is set in repository secrets
3. **Feed not updating**: Check if the source RSS feed is accessible
4. **Pages not deploying**: Ensure gh-pages branch exists and Pages is configured correctly

### Viewing Logs

1. Go to Actions tab in your repository
2. Click on the latest workflow run
3. Expand the job that failed to see the logs
