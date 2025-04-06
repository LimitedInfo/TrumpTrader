import os
import google.generativeai as genai
from dotenv import load_dotenv
import json # Import json
import sys  # Import sys for stderr

load_dotenv()

# Define the path to the mapping file
TICKER_MAPPING_FILE = 'ticker_effected_mapping.json'

class LLMRepository:
    def __init__(self):
        self.GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
        self.GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
        self.REDIRECT_URI = os.getenv("REDIRECT_URI")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        # Load the ticker mapping
        self.ticker_mapping = self._load_ticker_mapping()
        self.valid_countries = set(self.ticker_mapping.keys())

        # Authenticate and store both models
        self.gemini_flash_client, self.gemini_pro_client = self._authenticate_gemini_models()

        # Define the desired JSON structure for the analysis response
        self._analysis_json_structure = '''
        {
            "country_reference": "[Country Name or 'N/A']",
            "tariff_sentiment_change": "[Increased/Decreased/Unchanged/Unclear]",
            "reasoning": "[Brief explanation for the sentiment change assessment]"
        }
        '''
        # Define the desired JSON structure for the reasoning/ticker response
        self._reasoning_json_structure = '''
        {
            "ticker": "[RELEVANT_TICKER_SYMBOL or 'N/A']",
            "action": "[BUY/SELL or 'N/A']",
            "confidence": "[High/Medium/Low or 'N/A']",
            "explanation": "[Concise reasoning connecting sentiment analysis to ticker/action choice]"
        }
        '''
        # Define the desired JSON structure for the tariff firmness assessment
        self._firmness_json_structure = '''
        {
            "firmness_direction": "[More Firm/Less Firm/Unchanged/Unclear]",
            "confidence": "[High/Medium/Low]",
            "reasoning": "[Brief explanation for the firmness assessment]"
        }
        '''

    def _load_ticker_mapping(self):
        """Loads the ticker mapping from the JSON file."""
        try:
            with open(TICKER_MAPPING_FILE, 'r') as f:
                mapping = json.load(f)
                print(f"Successfully loaded ticker mapping from {TICKER_MAPPING_FILE}")
                return mapping
        except FileNotFoundError:
            print(f"Error: Ticker mapping file not found at {TICKER_MAPPING_FILE}", file=sys.stderr)
            return {}
        except json.JSONDecodeError:
            print(f"Error: Failed to decode JSON from {TICKER_MAPPING_FILE}", file=sys.stderr)
            return {}
        except Exception as e:
            print(f"An unexpected error occurred while loading {TICKER_MAPPING_FILE}: {e}", file=sys.stderr)
            return {}

    def _authenticate_gemini_models(self):
        """Authenticates and initializes both Gemini models."""
        if not self.gemini_api_key:
            raise ValueError("Gemini API key is required")
        genai.configure(api_key=self.gemini_api_key)
        
        try:
            # Initialize Flash model (Quick reasoning) - Using latest flash as 2.0 isn't standard
            # Using gemini-1.5-flash-latest as gemini-2.0-flash is not a standard identifier
            flash_model_name = 'gemini-2.0-flash' 
            print(f"Initializing Gemini Flash model: {flash_model_name}")
            flash_client = genai.GenerativeModel(flash_model_name)

            # Initialize Pro model (Smart reasoning) - Keeping the existing one
            pro_model_name = 'gemini-2.5-pro-preview-03-25' 
            print(f"Initializing Gemini Pro model: {pro_model_name}")
            pro_client = genai.GenerativeModel(pro_model_name)

            # Basic check to ensure models initialized (optional, but good practice)
            flash_client.generate_content("test", generation_config=genai.types.GenerationConfig(max_output_tokens=5)) 
            pro_client.generate_content("test", generation_config=genai.types.GenerationConfig(max_output_tokens=5))
            print("Both Gemini models initialized successfully.")
            
            return flash_client, pro_client
        except Exception as e:
            print(f"Error initializing Gemini models: {e}", file=sys.stderr)
            raise # Reraise the exception to prevent proceeding with invalid models

    def _generate_raw_response(self, prompt, model_type='pro'):
        """Internal method to call the LLM API."""
        
        # Select the client based on model_type
        if model_type == 'flash':
            client = self.gemini_flash_client
            model_name = 'Flash'
        elif model_type == 'pro':
            client = self.gemini_pro_client
            model_name = 'Pro'
        else:
             print(f"Error: Invalid model_type specified: {model_type}. Defaulting to Pro.", file=sys.stderr)
             client = self.gemini_pro_client
             model_name = 'Pro (Defaulted)'
 
        print(f"Sending prompt to LLM ({model_name})")
        try:
            response = client.generate_content(prompt)
            # Add basic error handling for the API response itself
            if not response.candidates:
                 print("Error: LLM response missing candidates.", file=sys.stderr)
                 return None
            # Assuming the first candidate has the content
            # Check if 'text' attribute exists
            if hasattr(response.candidates[0].content, 'parts') and response.candidates[0].content.parts:
                 # Check parts for text
                 if hasattr(response.candidates[0].content.parts[0], 'text'):
                      return response.candidates[0].content.parts[0].text
                 else:
                      print("Error: LLM response part missing 'text' attribute.", file=sys.stderr)
                      return None
            # Fallback or alternative structure check if needed
            elif hasattr(response, 'text'): 
                 return response.text
            else:
                 print("Error: Could not extract text from LLM response structure.", file=sys.stderr)
                 print(f"Response structure: {response}", file=sys.stderr)
                 return None
        except Exception as e:
            print(f"Error during LLM API call: {e}", file=sys.stderr)
            return None

    def _parse_llm_json_response(self, response_text):
        """Attempts to parse JSON from LLM response, stripping markdown if needed."""
        if response_text is None:
            print("Error: Cannot parse None response text.", file=sys.stderr)
            return None

        try:
            # First attempt: parse directly
            parsed_response = json.loads(response_text)
            print(f"Parsed LLM Response (direct): {parsed_response}")
            return parsed_response
        except json.JSONDecodeError:
            # Second attempt: strip markdown and parse
            print(f"Info: Direct JSON parse failed. Raw: '{response_text[:100]}...'. Attempting markdown stripping.", file=sys.stderr)
            response_stripped = response_text.strip()
            # Handle ```json ... ```
            if response_stripped.startswith("```json"):
                response_stripped = response_stripped[7:]
                if response_stripped.endswith("```"):
                    response_stripped = response_stripped[:-3]
            # Handle ``` ... ```
            elif response_stripped.startswith("```"):
                 response_stripped = response_stripped[3:]
                 if response_stripped.endswith("```"):
                     response_stripped = response_stripped[:-3]
            # Handle potential leading/trailing whitespace after stripping fences
            response_stripped = response_stripped.strip()

            if response_stripped:
                try:
                    parsed_response = json.loads(response_stripped)
                    print(f"Parsed LLM Response (after stripping): {parsed_response}")
                    return parsed_response
                except json.JSONDecodeError as e2:
                    print(f"Error: Still not valid JSON after stripping: {e2}", file=sys.stderr)
                    print(f"Stripped Response Content:\n{response_stripped}", file=sys.stderr)
                    return None # Failed even after stripping
            else:
                print("Error: Response was empty after stripping markdown.", file=sys.stderr)
                return None # Failed, empty after stripping

    def analyze_tweet_sentiment(self, tweet_text):
        """Analyzes tweet sentiment regarding tariffs and returns a parsed JSON dictionary."""
        cleaned_text = tweet_text.strip()
        if not cleaned_text:
            print("Warning: Empty tweet text received for analysis.", file=sys.stderr)
            return None

        # Get the list of valid countries/regions for the prompt
        valid_country_list = ", ".join(f"'{c}'" for c in self.valid_countries)

        # Construct the detailed prompt using the class attribute structure
        full_prompt = f'''
        Analyze the following tweet from Donald Trump regarding its potential impact on United States tariffs. Your goal is to determine if the tweet suggests a change in the likelihood that current US tariffs will remain in place.

        Tweet Text: "{cleaned_text}"

        Valid Countries/Regions: [{valid_country_list}]

        Pick the most specific item you can, if a country is mentioned, that is the country you should choose, or about a region then return that region. If however it's just a general statement about tariffs, choose 'Whole World'.

        Instructions:
        1. Identify the primary country or region mentioned or strongly implied in the tweet that relates to trade or tariffs. **Your answer MUST be one of the 'Valid Countries/Regions' listed above, or 'N/A' if no valid country/region is clearly identified.**
        2. Assess whether the tweet's content or tone suggests an INCREASED likelihood, DECREased likelihood, or UNCHANGED likelihood that US tariffs relevant to the identified country/region (or in general, if N/A) will remain in place. If the tweet is irrelevant or provides no clear signal, use "Unclear".
        3. Provide a brief reasoning for your assessment based *only* on the provided tweet text.

        Output your analysis ONLY in the following JSON format. Do not include any text before or after the JSON block:
        {self._analysis_json_structure}
        '''

        print(f"Constructed prompt for LLM analysis.")
        # print(f"Full prompt:\n{full_prompt}") # Optional: Debug prompt

        # Call the internal method to get the raw response string
        response_text = self._generate_raw_response(full_prompt, model_type='flash')
        parsed_response = self._parse_llm_json_response(response_text)

        # Add validation for country reference
        if parsed_response and 'country_reference' in parsed_response:
            country = parsed_response['country_reference']
            if country != 'N/A' and country not in self.valid_countries:
                print(f"Warning: LLM returned country '{country}' which is not in the valid list. Treating as N/A.", file=sys.stderr)
                parsed_response['country_reference'] = 'N/A' # Overwrite if invalid

        return parsed_response

    def analyze_tweet_reasoning(self, sentiment_analysis):
        """Takes sentiment analysis results and suggests a ticker/action from the mapping."""
        # Input validation
        if not isinstance(sentiment_analysis, dict):
            print("Error: Input sentiment_analysis must be a dictionary.", file=sys.stderr)
            return None
        required_keys = ["country_reference", "tariff_sentiment_change", "reasoning"]
        if not all(key in sentiment_analysis for key in required_keys):
            print(f"Error: Input sentiment_analysis missing required keys ({required_keys}).", file=sys.stderr)
            return None

        country = sentiment_analysis.get("country_reference", "N/A")
        sentiment = sentiment_analysis.get("tariff_sentiment_change", "Unclear")
        initial_reasoning = sentiment_analysis.get("reasoning", "") # Keep for potential explanation

        # Handle non-actionable sentiment or invalid country
        if sentiment in ["Unclear", "Unchanged"] or country == "N/A" or country not in self.ticker_mapping:
            explanation = "Sentiment analysis was unclear, unchanged, or country was N/A/invalid."
            if country != "N/A" and country not in self.ticker_mapping:
                explanation = f"Country '{country}' not found in ticker mapping."
                print(f"Info: Country '{country}' from sentiment analysis not found in ticker_effected_mapping.json.", file=sys.stderr)
            else:
                print(f"Info: Sentiment ({sentiment}) or country ({country}) is non-actionable. Returning N/A.", file=sys.stderr)

            return {
                "ticker": "N/A",
                "action": "N/A",
                "confidence": "N/A", # Confidence is not applicable here
                "explanation": explanation
            }

        # Lookup ticker and action from the mapping
        mapping_entry = self.ticker_mapping.get(country)

        if not mapping_entry or 'ticker' not in mapping_entry or 'action' not in mapping_entry:
             print(f"Error: Invalid mapping entry for country '{country}' in {TICKER_MAPPING_FILE}.", file=sys.stderr)
             return {
                 "ticker": "N/A",
                 "action": "N/A",
                 "confidence": "N/A",
                 "explanation": f"Invalid or incomplete mapping found for country '{country}'."
             }

        ticker = mapping_entry['ticker']
        action = mapping_entry['action']

        # Construct a simple explanation based on the lookup
        explanation = f"Based on tariff sentiment '{sentiment}' for '{country}', mapped ticker is '{ticker}' with action '{action}'. Initial LLM reasoning: {initial_reasoning}"

        print(f"Determined trade suggestion from mapping for '{country}': Ticker={ticker}, Action={action}")

        # Return the result in the expected JSON structure
        return {
            "ticker": ticker,
            "action": action,
            "confidence": "Medium", # Set a default confidence level for mapping-based suggestions
            "explanation": explanation
        }

    def analyze_tariff_firmness(self, tweet_text):
        """Analyzes whether a tweet suggests Trump is becoming more or less firm on tariffs in general."""
        cleaned_text = tweet_text.strip()
        if not cleaned_text:
            print("Warning: Empty tweet text received for firmness analysis.", file=sys.stderr)
            return None

        # Construct the prompt specifically for tariff firmness assessment
        full_prompt = f'''
        Analyze the following tweet from Donald Trump regarding his stance on tariffs in general. Your goal is to determine if the tweet suggests he is becoming MORE FIRM or LESS FIRM in his general position on tariffs.

        Tweet Text: "{cleaned_text}"

        Instructions:
        1. Determine if Trump's language and tone suggest he is becoming MORE FIRM (stronger, more committed) or LESS FIRM (softer, more flexible) on tariffs generally.
        2. If the tweet doesn't clearly indicate a change in firmness, use "Unchanged".
        3. If the tweet is unrelated to tariffs or provides no signal about tariff firmness, use "Unclear".
        4. Provide your confidence level in this assessment.
        5. Give a brief explanation of your reasoning based strictly on the tweet content.

        Output your analysis ONLY in the following JSON format. Do not include any text before or after the JSON block:
        {self._firmness_json_structure}
        '''

        print("Constructed prompt for tariff firmness analysis.")
        
        # Call the flash model for faster response on this relatively straightforward task
        response_text = self._generate_raw_response(full_prompt, model_type='flash')
        parsed_response = self._parse_llm_json_response(response_text)
        
        return parsed_response

