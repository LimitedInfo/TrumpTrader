import sys
import asyncio
import notifications
from repository import LLMRepository

# Default dollar amount for BUY orders
dollar_amount = 1000.0

# Assume schwab.py and chrome_scrapper.py exist and have needed functions
try:
    import schwab
    import chrome_scrapper # Import chrome_scrapper directly
    SCHWAB_AVAILABLE = True
except ImportError:
    # Update warning message
    print("WARNING: schwab.py or chrome_scrapper.py not found. Trading or tweet fetching may fail.", file=sys.stderr)
    SCHWAB_AVAILABLE = False
    # Set chrome_scrapper to None if it couldn't be imported, to prevent errors later
    chrome_scrapper = None

# Initialize the LLM Repository
llm_repo = LLMRepository()

def send_to_llm(text):
    """Sends text to the LLM Repository for analysis and returns the result."""
    print(f"Forwarding text to LLMRepository for analysis: {text[:50]}..." ) # Log snippet
    try:
        # Delegate the entire analysis process to the repository
        analysis_result = llm_repo.analyze_tweet_sentiment(text)
        if analysis_result:
             print(f"Analysis successful: {analysis_result}")
        else:
             print(f"Analysis returned None or failed.", file=sys.stderr)
        return analysis_result
    except Exception as e:
        # Catch potential exceptions from the repository call itself
        print(f"Error calling LLMRepository analyze_tweet_sentiment: {e}", file=sys.stderr)
        return None

def get_trade_suggestion(sentiment_result):
    """Gets a trade suggestion based on sentiment analysis result."""
    print(f"Attempting to get trade suggestion for sentiment: {sentiment_result}")
    try:
        suggestion = llm_repo.analyze_tweet_reasoning(sentiment_result)
        if suggestion:
            print(f"Received trade suggestion: {suggestion}")
        else:
            print(f"Failed to get trade suggestion.", file=sys.stderr)
        return suggestion
    except Exception as e:
        print(f"Error calling LLMRepository analyze_tweet_reasoning: {e}", file=sys.stderr)
        return None

async def main():
    print("Starting async main process (using direct chrome_scrapper call)...")
    schwab_client = None
    account_hash = None

    # Check if chrome_scrapper was imported successfully
    if not chrome_scrapper:
        print("chrome_scrapper module not found, cannot fetch tweet. Exiting.", file=sys.stderr)
        return

    # Initialize Schwab client and get account hash if available
    if SCHWAB_AVAILABLE:
        try:
            schwab_client = schwab.initialize_client()
            await asyncio.sleep(0.1) # Small yield
            account_hash = await schwab.get_primary_account_hash(schwab_client)
            await asyncio.sleep(0.1) # Small yield
            if not account_hash:
                 print("Failed to get Schwab account hash. Trading will be skipped.", file=sys.stderr)
        except Exception as e:
            print(f"Error initializing Schwab or getting account hash: {e}", file=sys.stderr)

    try:
        tweet_text = chrome_scrapper.main()

        if not tweet_text:
            print("chrome_scrapper.main() did not return tweet text. Exiting.", file=sys.stderr)
            return
        print(f"Fetched tweet via direct call: {tweet_text[:100]}...")

        tariff_firmness_result = llm_repo.analyze_tariff_firmness(tweet_text)
        print(f"Tariff firmness result: {tariff_firmness_result}")

        if tariff_firmness_result['firmness_direction'] == 'More Firm':
            action = 'SELL'
        elif tariff_firmness_result['firmness_direction'] == 'Less Firm':
            action = 'BUY'
        else:
            action = 'N/A'


        # sentiment_result = send_to_llm(tweet_text)
        # if not sentiment_result:
        #     print("Failed to analyze sentiment. Exiting.", file=sys.stderr)
        #     return
        # print(f"Sentiment analysis result: {sentiment_result}")

        

        # suggestion = get_trade_suggestion(sentiment_result)
        # if not suggestion:
        #     print("Failed to get trade suggestion. Exiting.", file=sys.stderr)
        #     return
        # print(f"Trade suggestion: {suggestion}")

        # print(f"Tariff sentiment change: {sentiment_result['tariff_sentiment_change']}")
        # # Increased/Decreased/Unchanged/Unclear
        # if sentiment_result['tariff_sentiment_change'] == 'Increased':
        #     action = suggestion.get('action')
        # elif sentiment_result['tariff_sentiment_change'] == 'Decreased':
        #     if suggestion.get('action') == 'SELL':
        #         action = 'BUY'
        #     elif suggestion.get('action') == 'BUY':
        #         action = 'SELL'
        # elif sentiment_result['tariff_sentiment_change'] == 'Unchanged':
        #     action = 'N/A'
        # elif sentiment_result['tariff_sentiment_change'] == 'Unclear':
        #     action = 'N/A'

        # 4. Execute trade if schwab is available and initialized
        if SCHWAB_AVAILABLE and schwab_client and account_hash:
            print("Schwab is available. Attempting to execute trade...")
            ticker = 'SPY'

            if action and ticker and action != 'N/A' and ticker != 'N/A':
                if action.upper() == 'BUY':
                    print(f"Executing BUY trade for {ticker} with ${dollar_amount}...")
                    try:
                        buy_order_id, calculated_quantity = await schwab.execute_schwab_trade(
                            schwab_client,
                            account_hash,
                            ticker,
                            dollar_amount,
                            "BUY"
                        )
                        if buy_order_id:
                             print(f"BUY trade for {ticker} submitted. Order ID: {buy_order_id}, Calc Quantity: {calculated_quantity}")
                        else:
                             print(f"BUY trade submission failed for {ticker}. Check logs.", file=sys.stderr)
                    except Exception as trade_err:
                        print(f"Error during BUY trade execution for {ticker}: {trade_err}", file=sys.stderr)

                elif action.upper() == 'SELL':
                    print(f"SELL action suggested for {ticker}. SELL execution is not implemented in this service as quantity is not provided by the LLM.", file=sys.stderr)
                    # Example: If quantity were available, the call would be:
                    sell_order_id = await schwab.execute_sell_trade(schwab_client, account_hash, ticker, dollar_amount)
                else:
                    print(f"Unknown action '{action}' in suggestion. No trade executed.", file=sys.stderr)
            else:
                print(f"Invalid or N/A suggestion (Action: {action}, Ticker: {ticker}). No trade executed.")
        else:
            print("Schwab is not available, not initialized, or account hash missing. Skipping trade execution.")

        # Send pushover notification
        success = notifications.send_pushover_notification(
            tweet_text, 
            title=f"{tariff_firmness_result['reasoning']}", 
            priority=1
        )
        

    # Add specific handling for potential errors from chrome_scrapper.main()
    except AttributeError as ae:
         if "'NoneType' object has no attribute 'main'" in str(ae):
             print("Error: chrome_scrapper could not be imported correctly.", file=sys.stderr)
         else:
             print(f"An unexpected AttributeError occurred: {ae}", file=sys.stderr)
    except Exception as e:
        # General error catching for the main logic block
        print(f"An error occurred in the main async process: {e}", file=sys.stderr)

    print("Async main process finished.")

if __name__ == "__main__":
    # Still run the async main function using asyncio.run
    asyncio.run(main())
