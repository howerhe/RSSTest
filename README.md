# RSS Digest Tool

Generate AI-summarized digests from RSS feeds. This tool fetches articles from RSS feeds, summarizes them using AI, combines multiple sources into one feed if needed, and produces digests in various formats (JSON, RSS, Atom).

## Features

- 📰 Fetch articles from any RSS feed
- 🤖 Automatically summarize articles using AI (Claude; more coming soon...)
- 📋 Group articles into daily digests
- 🔗 Combine multiple feeds into a single digest output
- 📑 Generate outputs in multiple formats (JSON Feed, RSS, Atom)
- 💾 Cache summaries to reduce API usage
- 🌐 Built-in server for local preview
- 🔄 Automated generation via GitHub Actions

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/rss-digest-tool.git
cd rss-digest-tool

# Install the package
# Option 1: Install the package (recommended)
pip install -e .

# Option 2: Install dependencies only
# pip install -r requirements.txt
```

## Configuration

The tool uses a straightforward configuration system that allows you to define multiple digests from various sources.

### Configuration Structure

The configuration file uses a clean, flat structure with:

1. **Global settings** at the top level
2. **Digest definitions** in the `digests` array
3. **Source configurations** within each digest

### Example Configuration

```json
{
  "output_directory": "output",
  "cache_directory": ".cache",
  "cache_enabled": true,
  "summary_length": 150,
  "model": "claude-3-haiku-20240307",
  "system_prompt": "You are a helpful assistant that summarizes articles concisely.",
  "output_formats": ["json"],
  
  "digests": [
    {
      "name": "Solidot Updates",
      "sources": [
        {
          "url": "https://www.solidot.org/index.rss",
          "do_summarize": false
        }
      ]
    },
    {
      "name": "Tech News Roundup",
      "output_formats": ["json", "rss", "atom"],
      "sources": [
        {
          "group": "Apple News",
          "sources": [
            {
              "url": "https://9to5mac.com/feed/",
              "do_summarize": true,
              "model": "claude-3-sonnet-20240229"
            },
            {
              "url": "https://www.theverge.com/rss/index.xml",
              "do_summarize": false
            }
          ]
        },
        {
          "url": "https://arstechnica.com/feed/",
          "do_summarize": true,
          "summary_length": 180
        }
      ]
    }
  ]
}
```

### Configuration Options

#### Global-Only Settings

These settings can only be specified at the top level:

| Setting | Description | Default |
|---------|-------------|---------|
| `output_directory` | Directory for output files | `"output"` |
| `cache_directory` | Directory for cache database | `".cache"` |
| `cache_enabled` | Enable caching of summaries | `true` |

#### Global Settings (can be overridden)

These settings apply to all digests and sources but can be overridden at digest or source level:

| Setting | Description | Default |
|---------|-------------|---------|
| `summary_length` | Default length for excerpts | `150` |
| `model` | Claude model to use | `"claude-3-haiku-20240307"` |
| `system_prompt` | System prompt for Claude | `"You are a helpful assistant..."` |
| `max_tokens` | Maximum tokens for Claude response | `150` |
| `temperature` | Temperature for Claude | `0.3` |
| `output_formats` | Output formats to generate | `["json"]` |
| `do_summarize` | Whether to summarize articles | `true` |
| `api_key` | Anthropic API key | `null` (use environment variable) |

> ⚠️ **Security Note**: API keys should be set using environment variables (`ANTHROPIC_API_KEY`) rather than storing them in the config file.

#### Digest-Specific Settings

These settings apply only to digests:

| Setting | Description | Default |
|---------|-------------|---------|
| `name` | Name of the digest (required) | None |
| `digest_id` | ID for output filenames | Generated from name |

#### Source-Specific Settings

Each source represents an RSS feed to include in a digest:

| Setting | Description | Default |
|---------|-------------|---------|
| `url` | URL of the RSS feed (required) | None |

#### Source Grouping (Optional)

You can optionally group multiple sources together:

```json
{
  "group": "Tech News Group",
  "sources": [
    { "url": "https://example.com/feed1" },
    { "url": "https://example.com/feed2" }
  ]
}
```

Source groups are purely organizational and help to apply common settings to multiple sources.

### Setting Inheritance

Settings cascade down from global → digest → source group → source. More specific settings override more general ones.

## Usage

### Environment Setup

Set your Claude API key as an environment variable:

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

### Generate Digests

Run the generator to fetch feeds and create digests:

```bash
python scripts/generate.py --config config.json
```

To process only a specific digest:

```bash
python scripts/generate.py --config config.json --digest "Tech News Daily"
```

### Preview Digests

Start a local server to preview the generated digests:

```bash
python scripts/serve.py
```

This will:
1. Start a server at http://localhost:8000
2. Display available feeds
3. Open your browser with an index page linking to all feeds

You can use custom port and directory:

```bash
python scripts/serve.py --port 8080 --dir custom_output
```

## Automated Deployment with GitHub Actions

This project includes GitHub Actions automation to generate digests on a schedule.

### Setup

1. **Fork or clone this repository**

2. **Add your Anthropic API key as a repository secret:**
   - Go to your repository on GitHub
   - Click on Settings > Secrets and variables > Actions > New repository secret
   - Name: `ANTHROPIC_API_KEY`
   - Value: Your Anthropic API key

3. **Enable GitHub Actions:**
   - Go to the Actions tab in your repository
   - Click "I understand my workflows, go ahead and enable them"

### How It Works

- **Schedule:** Digests are generated according to a predefined schedule in the workflow
- **Process:** The workflow:
  - Sets up Python
  - Installs the package
  - Runs the generator script
  - Commits updated digest files to the repository

### Manual Trigger

You can manually trigger digest generation:
1. Go to Actions tab in your GitHub repository
2. Select "Generate RSS Digests" workflow
3. Click "Run workflow" button

## Future Enhancements

Here are some planned features for future releases:

- **Advanced scheduling options**:
  - Support for cron expressions (`"cron": "0 8 * * *"`)
  - Timezone-aware scheduling
  - Per-digest frequency controls
  
- **Additional AI provider support**:
  - OpenAI (GPT-3.5, GPT-4)
  - DeepSeek (R1)
  - Open source models
  
- **Enhanced configuration**:
  - Different API keys for different sources
  - Better error handling for failed feeds
  - Configuration validation

- **UI improvements**:
  - Web-based configuration editor
  - Live preview of digests
  - Statistics dashboard

## Development Note

This project is developed with massive assistance of AI. But I have reviewed and understand each line of code. And the high level design is by human mind.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.