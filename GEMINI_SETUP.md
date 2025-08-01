# 🚀 Gemini API Setup Guide

This guide will help you set up the Travel Agent System to use Google's Gemini API.

## Prerequisites

- Python 3.8 or higher
- A Google Cloud account (free tier available)

## Step 1: Get Your Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated API key

## Step 2: Configure Your Environment

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Open `.env` in your text editor and update:
   ```env
   GOOGLE_API_KEY=your_actual_gemini_api_key_here
   ```

3. (Optional) If you have other API keys:
   ```env
   ANTHROPIC_API_KEY=your_anthropic_key  # For Claude
   OPENAI_API_KEY=your_openai_key        # For GPT
   ```

## Step 3: Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 4: Verify Setup

Run the system check:
```bash
python check_system.py
```

Test Gemini integration:
```bash
python test_gemini.py
```

## Step 5: Launch the System

1. Start all agents:
   ```bash
   python src/launch_agents.py
   ```

2. In a new terminal, run the client:
   ```bash
   python src/travel_client.py
   ```

## Configuration Options

### Default LLM Provider

The system defaults to Gemini. To change the default provider:

```env
DEFAULT_LLM_PROVIDER=gemini  # or 'anthropic' or 'openai'
```

### Agent-Specific Providers

You can configure different LLM providers for specific agents:

```env
HOTEL_LLM_PROVIDER=gemini
ACTIVITY_LLM_PROVIDER=anthropic
BUDGET_LLM_PROVIDER=openai
```

### Model Selection

By default, the system uses:
- Gemini: `gemini-2.0-flash`
- Anthropic: `claude-3-5-sonnet-latest`
- OpenAI: `gpt-4o`

## Troubleshooting

### "API key not found" Error
- Make sure you've created the `.env` file (not just `.env.example`)
- Verify the API key is correctly copied without extra spaces
- Restart your terminal after updating `.env`

### "Invalid API key" Error
- Check that your API key is active in [Google AI Studio](https://makersuite.google.com/app/apikey)
- Ensure you're not using an old or revoked key
- Verify you have API access enabled

### Rate Limiting
- Gemini has rate limits on the free tier
- Consider upgrading if you hit limits frequently
- The system will automatically retry on rate limit errors

## Cost Considerations

- Gemini offers a generous free tier
- Monitor your usage in Google Cloud Console
- Consider using `gemini-2.0-flash` for lower costs
- Premium models like `gemini-1.5-pro` cost more but offer better quality

## Security Notes

- **Never commit your API keys to version control**
- Keep your `.env` file in `.gitignore`
- Use different keys for development and production
- Rotate keys regularly
- Consider using Google Cloud Secret Manager for production

## Advanced Configuration

### Temperature Settings

Agents are pre-configured with optimal temperatures:
- Orchestrator: 0.5 (more deterministic)
- Hotel/Transport: 0.7 (balanced)
- Activity: 0.8 (more creative)
- Budget: 0.3 (very deterministic)
- Itinerary: 0.6 (structured)

### Custom Models

To use different Gemini models, modify `src/shared/llm_config.py`:

```python
DEFAULT_MODELS = {
    "gemini": "gemini-1.5-pro",  # Premium model
    # or "gemini-2.0-flash" for faster/cheaper
}
```

## Next Steps

1. Review the [main README](README.md) for system overview
2. Check [PLANNING.md](PLANNING.md) for architecture details
3. See [QUICKSTART.md](docs/QUICKSTART.md) for usage examples
4. Run the example trip planning scenario

## Support

- [Google AI Documentation](https://ai.google.dev/docs)
- [LangChain Google Integration](https://python.langchain.com/docs/integrations/chat/google_generative_ai)
- Project Issues: Create an issue in this repository