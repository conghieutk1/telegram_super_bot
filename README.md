# telegram_super_bot

# Telegram Super Bot

This project is a Telegram bot that aggregates news, provides weather updates, and fetches financial data such as gold prices and currency exchange rates.

## Project Structure

```
telegram_super_bot
├── src
│   ├── main.py               # Entry point of the application
│   ├── util.py               # Utility functions for JSON handling and HTTP requests
│   ├── telegram_client.py     # Functions for interacting with the Telegram API
│   ├── gold_fx_service.py     # Fetches current prices of gold, gasoline, and USD
│   ├── weather_service.py      # Provides weather information and alerts
│   └── news_service.py        # Aggregates news from various sources
├── config.json                # General configuration settings
├── secrets.example.json       # Template for API keys
├── state.json                 # Stores runtime state information
├── .gitignore                 # Specifies files to ignore in Git
├── README.md                  # Documentation for the project
└── requirements.txt           # Lists Python dependencies
```

## Python version 3.10

## Setup Instructions

1. Clone the repository:

    ```
    git clone <repository-url>
    cd telegram_super_bot
    ```

2. Create a `secrets.json` file based on `secrets.example.json` and fill in your API keys.

3. Install the required dependencies:

    ```
    pip install -r requirements.txt
    ```

4. Run the bot:
    ```
    python src/main.py
    ```

## Usage Guidelines

-   The bot will listen for updates from Telegram and respond based on the configured services.
-   You can customize the default city and news sources in the `config.json` file.
-   Ensure that the `state.json` file is writable, as it stores the bot's runtime state.

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.
