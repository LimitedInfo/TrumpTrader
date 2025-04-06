import json
import os
import sys
from dotenv import load_dotenv

# Ensure the script can find the repository module
# Add the project root to the Python path if repository.py is in the root
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from repository import LLMRepository
except ImportError:
    print("Error: Could not import LLMRepository. Make sure repository.py is in the project root or Python path.", file=sys.stderr)
    sys.exit(1)

# Load environment variables (like GEMINI_API_KEY)
load_dotenv()

def populate_ticker_mapping(json_file_path="ticker_effected_mapping.json"):
    """
    Reads a JSON mapping, uses LLMRepository to find relevant tickers for each key,
    and updates the JSON file.
    """
    try:
        print("Initializing LLM Repository...")
        llm_repo = LLMRepository()
        print("LLM Repository initialized.")
    except Exception as e:
        print(f"Fatal Error: Failed to initialize LLMRepository: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        print(f"Reading JSON data from {json_file_path}...")
        with open(json_file_path, 'r') as f:
            ticker_mapping = json.load(f)
        print("JSON data read successfully.")
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}", file=sys.stderr)
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_file_path}", file=sys.stderr)
        return

    updated_count = 0
    failed_count = 0

    print("Starting ticker population process...")
    for country, current_value in ticker_mapping.items():
        # Only update if the current value is the placeholder
        if current_value == "placeholder":
            print(f"Processing country: {country}")
            # Construct a dummy sentiment analysis input
            sentiment_analysis_input = {
                "country_reference": country,
                "tariff_sentiment_change": "Increased", # Assuming increased tariffs to get a relevant ticker
                "reasoning": f"Hypothetical scenario assuming increased US tariffs related to {country}."
            }

            try:
                print(f"  Calling LLM for ticker suggestion for {country}...")
                ticker_suggestion = llm_repo.analyze_tweet_reasoning(sentiment_analysis_input)

                if ticker_suggestion and isinstance(ticker_suggestion, dict):
                    ticker = ticker_suggestion.get("ticker", "N/A")
                    if ticker and ticker != "N/A":
                        ticker_mapping[country] = ticker
                        print(f"  Successfully updated ticker for {country} to: {ticker}")
                        updated_count += 1
                    else:
                        print(f"  LLM returned N/A or no ticker for {country}. Keeping placeholder.", file=sys.stderr)
                        failed_count += 1
                else:
                    print(f"  LLM call failed or returned invalid data for {country}. Keeping placeholder.", file=sys.stderr)
                    failed_count += 1

            except Exception as e:
                print(f"  Error processing {country}: {e}", file=sys.stderr)
                failed_count += 1
        else:
            print(f"Skipping {country}, already has value: {current_value}")

    print(f"Ticker population finished. Updated: {updated_count}, Failed/Skipped Placeholder: {failed_count}")

    # Write the updated mapping back to the JSON file
    try:
        print(f"Writing updated mapping back to {json_file_path}...")
        with open(json_file_path, 'w') as f:
            json.dump(ticker_mapping, f, indent=4) # Use indent for readability
        print("Successfully wrote updated JSON data.")
    except IOError as e:
        print(f"Error: Could not write updated JSON to {json_file_path}: {e}", file=sys.stderr)

if __name__ == "__main__":
    # Ensure environment variables are loaded if running directly
    if not os.getenv("GEMINI_API_KEY"):
         print("Warning: GEMINI_API_KEY environment variable not found. LLM calls might fail.", file=sys.stderr)
         # You might want to exit here if the key is absolutely required
         # sys.exit(1)
    populate_ticker_mapping() 