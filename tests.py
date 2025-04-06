import unittest
from unittest.mock import patch, MagicMock
import io
import sys
import os # Import os to check environment variables
import json # Import json for loading test data if needed
import contextlib # Import contextlib for redirecting stdout/stderr

# Import the service module
import service
from repository import LLMRepository # Import repo directly if needed for type checks

# Decorator to skip tests unless RUN_INTEGRATION_TESTS is set
skip_integration_tests = unittest.skipUnless(
    os.environ.get('RUN_INTEGRATION_TESTS') == 'true',
    "Skipping integration test: Set RUN_INTEGRATION_TESTS=true to run."
)

class TestService(unittest.TestCase):

    # Patch the specific method within the llm_repo instance used by send_to_llm
    @patch('service.llm_repo.analyze_tweet_sentiment')
    def test_run_scrapper_and_forward_with_mock_process(self, mock_analyze_tweet):
        # Configure the mock to return a valid dictionary structure
        mock_analyze_tweet.return_value = {
            "country_reference": "Mocked Country",
            "tariff_sentiment_change": "Unchanged",
            "reasoning": "Mocked analysis result for test."
        }

        # 1. Prepare simulated output
        simulated_tweet_lines = [
            "Tweet Line 1", "---END_OF_TWEET_DELIMITER---",
            "Tweet Line 2", "---END_OF_TWEET_DELIMITER---"
        ]
        simulated_stdout_content = "\n".join(simulated_tweet_lines) + "\n"
        simulated_stdout = io.StringIO(simulated_stdout_content)

        # 2. Create a mock process object
        mock_process = MagicMock()
        mock_process.stdout = simulated_stdout
        mock_process.stderr = io.StringIO("")

        # 3. Call the function with the injected mock process
        service.run_scrapper_and_forward(process=mock_process)

        # 4. Assertions
        # Check that the mocked analyze_tweet_sentiment method was called twice
        self.assertEqual(mock_analyze_tweet.call_count, 2,
                         "analyze_tweet_sentiment should be called twice")
        # Verify the arguments passed to the mock
        calls = mock_analyze_tweet.call_args_list
        self.assertEqual(calls[0][0][0], "Tweet Line 1", "First call arg mismatch")
        self.assertEqual(calls[1][0][0], "Tweet Line 2", "Second call arg mismatch")

    # Patch the specific method within the llm_repo instance used by send_to_llm
    @patch('service.llm_repo.analyze_tweet_sentiment')
    def test_send_to_llm_interaction_wrapper(self, mock_analyze_tweet):
        # Test the wrapper function send_to_llm

        # Scenario 1: Repository method returns a valid result
        sample_tweet_text = "Test tweet for wrapper."
        expected_result_dict = {"country_reference": "Test", "tariff_sentiment_change": "Unclear", "reasoning": "Testing wrapper"}
        mock_analyze_tweet.return_value = expected_result_dict

        actual_result = service.send_to_llm(sample_tweet_text)

        mock_analyze_tweet.assert_called_once_with(sample_tweet_text)
        self.assertEqual(actual_result, expected_result_dict, "Wrapper did not return repo result correctly")

        # Scenario 2: Repository method returns None
        mock_analyze_tweet.reset_mock()
        mock_analyze_tweet.return_value = None
        sample_tweet_text_2 = "Another test tweet."

        actual_result_none = service.send_to_llm(sample_tweet_text_2)

        mock_analyze_tweet.assert_called_once_with(sample_tweet_text_2)
        self.assertIsNone(actual_result_none, "Wrapper should return None if repo method returns None")

        # Scenario 3: Repository method raises an exception
        mock_analyze_tweet.reset_mock()
        mock_analyze_tweet.side_effect = ValueError("Repo Error")
        sample_tweet_text_3 = "Tweet causing error."

        # Capture stderr to check for error message
        original_stderr = sys.stderr
        captured_stderr = io.StringIO()
        sys.stderr = captured_stderr

        actual_result_exception = service.send_to_llm(sample_tweet_text_3)

        # Restore stderr
        sys.stderr = original_stderr

        mock_analyze_tweet.assert_called_once_with(sample_tweet_text_3)
        self.assertIsNone(actual_result_exception, "Wrapper should return None if repo method raises exception")
        # Check if the error from the repo call was logged
        self.assertIn("Error calling LLMRepository analyze_tweet_sentiment: Repo Error", captured_stderr.getvalue(),
                      "Error message from repo exception not logged by wrapper")

    # --- Tests for analyze_tweet_reasoning --- 

    @patch('repository.LLMRepository._generate_raw_response') # Patch the raw generator
    def test_analyze_tweet_reasoning_unit(self, mock_generate_raw_response):
        """Unit test for analyze_tweet_reasoning logic, mocking the LLM call."""
        repo_instance = service.llm_repo # Use the instance from service

        # Scenario 1: Actionable sentiment (Increased)
        sentiment_input_increased = {
            "country_reference": "China",
            "tariff_sentiment_change": "Increased",
            "reasoning": "Tweet sounds aggressive towards China trade."
        }
        expected_output_json_str = json.dumps({
            "ticker": "F",
            "action": "BUY",
            "confidence": "Medium",
            "explanation": "Increased tariffs on China might benefit domestic auto makers like Ford."
        })
        mock_generate_raw_response.return_value = expected_output_json_str

        result_increased = repo_instance.analyze_tweet_reasoning(sentiment_input_increased)

        mock_generate_raw_response.assert_called_once() # Check LLM was called
        prompt_sent = mock_generate_raw_response.call_args[0][0]
        self.assertIn("China", prompt_sent)
        self.assertIn("Increased", prompt_sent)
        self.assertIsNotNone(result_increased, "Expected a result dict, got None")
        self.assertEqual(result_increased.get("ticker"), "F")
        self.assertEqual(result_increased.get("action"), "BUY")

        # Scenario 2: Actionable sentiment (Decreased)
        mock_generate_raw_response.reset_mock()
        sentiment_input_decreased = {
            "country_reference": "Mexico",
            "tariff_sentiment_change": "Decreased",
            "reasoning": "Tweet suggests easing of trade tensions."
        }
        expected_output_json_str_2 = json.dumps({
            "ticker": "AAPL",
            "action": "BUY", # Decreased tariffs could lower costs for AAPL
            "confidence": "Low",
            "explanation": "Easing Mexico tariffs might slightly lower supply chain costs."
        })
        mock_generate_raw_response.return_value = expected_output_json_str_2

        result_decreased = repo_instance.analyze_tweet_reasoning(sentiment_input_decreased)
        self.assertIsNotNone(result_decreased)
        self.assertEqual(result_decreased.get("ticker"), "AAPL")
        self.assertEqual(mock_generate_raw_response.call_count, 1)

        # Scenario 3: Non-actionable sentiment (Unclear)
        mock_generate_raw_response.reset_mock()
        sentiment_input_unclear = {
            "country_reference": "Canada",
            "tariff_sentiment_change": "Unclear",
            "reasoning": "Tweet is vague."
        }
        result_unclear = repo_instance.analyze_tweet_reasoning(sentiment_input_unclear)
        self.assertIsNotNone(result_unclear) # Should return the default N/A dict
        self.assertEqual(result_unclear.get("ticker"), "N/A")
        self.assertEqual(result_unclear.get("action"), "N/A")
        mock_generate_raw_response.assert_not_called() # LLM should not be called for non-actionable

        # Scenario 4: Non-actionable sentiment (N/A Country)
        mock_generate_raw_response.reset_mock()
        sentiment_input_na_country = {
            "country_reference": "N/A",
            "tariff_sentiment_change": "Increased",
            "reasoning": "General tariff increase mentioned."
        }
        result_na_country = repo_instance.analyze_tweet_reasoning(sentiment_input_na_country)
        self.assertIsNotNone(result_na_country)
        self.assertEqual(result_na_country.get("ticker"), "N/A")
        mock_generate_raw_response.assert_not_called()

        # Scenario 5: Invalid Input (missing key)
        mock_generate_raw_response.reset_mock()
        sentiment_invalid = {"country_reference": "France"} # Missing keys
        result_invalid = repo_instance.analyze_tweet_reasoning(sentiment_invalid)
        self.assertIsNone(result_invalid) # Should return None on validation error
        mock_generate_raw_response.assert_not_called()
        
    @skip_integration_tests
    def test_analyze_tweet_reasoning_integration(self):
        """Integration test for analyze_tweet_reasoning with real LLM."""
        repo_instance = service.llm_repo
        
        # Use a plausible sentiment input that should be actionable
        sentiment_input = {
            "country_reference": "Germany",
            "tariff_sentiment_change": "Increased",
            "reasoning": "Tweet strongly suggests upcoming tariffs targeting German automakers."
        }
        
        expected_keys = {"ticker", "action", "confidence", "explanation"}
        possible_actions = {"BUY", "SELL", "N/A"}
        possible_confidences = {"High", "Medium", "Low", "N/A"}
        
        try:
            result = repo_instance.analyze_tweet_reasoning(sentiment_input)
            
            self.assertIsNotNone(result, "analyze_tweet_reasoning returned None unexpectedly.")
            self.assertIsInstance(result, dict, f"Expected dict, got {type(result)}")
            self.assertEqual(result.keys(), expected_keys, f"Result keys {result.keys()} != {expected_keys}")
            
            # Check types and values
            self.assertIsInstance(result.get("ticker"), str)
            self.assertIn(result.get("action"), possible_actions)
            self.assertIn(result.get("confidence"), possible_confidences)
            self.assertIsInstance(result.get("explanation"), str)
            
            # Handle the N/A case - if ticker is N/A, others should be too
            if result.get("ticker") == "N/A":
                self.assertEqual(result.get("action"), "N/A")
                self.assertEqual(result.get("confidence"), "N/A")
            
            print(f"\n--- Reasoning Integration Test Result ---\nInput Sentiment: {sentiment_input}\nLLM Reasoning Result: {result}\n-------------------------------------")
            
        except Exception as e:
            self.fail(f"analyze_tweet_reasoning integration test failed unexpectedly: {e}")

    # --- End tests for analyze_tweet_reasoning ---

    # Integration test - requires API Key and network access
    @skip_integration_tests
    def test_send_to_llm_with_real_repo(self):
        # This tests the original sentiment analysis end-to-end
        sample_tweet_text = "Just had a great meeting with the leaders of France. Discussing fair trade."
        expected_keys = {"country_reference", "tariff_sentiment_change", "reasoning"}
        possible_sentiments = {"Increased", "Decreased", "Unchanged", "Unclear"}
        try:
            result = service.send_to_llm(sample_tweet_text)
            self.assertIsNotNone(result, "send_to_llm returned None...")
            self.assertIsInstance(result, dict, f"Expected a dict... got {type(result)}")
            self.assertEqual(result.keys(), expected_keys, f"Result keys {result.keys()} != {expected_keys}")
            self.assertIsInstance(result.get("country_reference"), str)
            self.assertIn(result.get("tariff_sentiment_change"), possible_sentiments)
            self.assertIsInstance(result.get("reasoning"), str)
            print(f"\n--- Sentiment Integration Test Result ---\nTweet: {sample_tweet_text}\nLLM Result: {result}\n-----------------------------")
        except Exception as e:
            self.fail(f"send_to_llm with real repo failed unexpectedly: {e}")

    # --- New E2E Test --- 
    @skip_integration_tests
    def test_run_scrapper_and_forward_e2e_with_mock_scraper(self):
        """End-to-end test for the service loop using real LLM and Schwab calls but a mock scraper."""
        
        # 1. Prepare simulated tweet output (using actionable examples)
        simulated_tweet1 = "Massive tariffs on Chinese imports are coming next week! Prepare!"
        simulated_tweet2 = "Just finished a very productive call with leadership in Mexico. Great things are happening for trade!"
        delimiter = "---END_OF_TWEET_DELIMITER---"
        # Ensure trailing newline for loop termination
        simulated_stdout_content = f"{simulated_tweet1}\n{delimiter}\n{simulated_tweet2}\n{delimiter}\n"
        simulated_stdout = io.StringIO(simulated_stdout_content)
        simulated_stderr = io.StringIO("") # Assume no scraper errors for this test

        # 2. Create mock process object
        mock_process = MagicMock()
        mock_process.stdout = simulated_stdout
        mock_process.stderr = simulated_stderr
        # No need to mock poll(), wait(), terminate() etc. as the service 
        # only manages processes it creates itself (should_manage_process=False)

        # 3. Capture stdout/stderr produced by the service and repository
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        print("\n--- Starting E2E Service Test --- ")
        with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
            # 4. Run the function with the mock scraper process injected
            # This will use REAL LLMRepository calls via send_to_llm and get_trade_suggestion
            service.run_scrapper_and_forward(process=mock_process)
        print("--- Finished E2E Service Test --- ")

        # 5. Assertions on captured output
        stdout_val = captured_stdout.getvalue()
        stderr_val = captured_stderr.getvalue()

        # Print captures for debugging if needed
        # print("\n--- E2E Test Captured STDOUT ---")
        # print(stdout_val)
        # print("--- E2E Test Captured STDERR ---")
        # print(stderr_val)
        # print("--- End E2E Test Captures ---")

        # Check for key log messages indicating the flow for the FIRST tweet
        self.assertIn("--- Processing Tweet ---", stdout_val)
        self.assertIn(f"Tweet Text: {simulated_tweet1[:200]}...", stdout_val)
        self.assertIn("Sentiment Analysis: {", stdout_val) # Check sentiment dict logged
        self.assertIn("Attempting to get trade suggestion for sentiment:", stdout_val)
        # Check that *some* trade suggestion dict was logged (could be N/A if LLM decides)
        self.assertRegex(stdout_val, r"Trade Suggestion: \{.*\}|Could not derive trade suggestion", 
                         "Expected a trade suggestion log or derivation failure log")
        self.assertIn("--- End Processing Tweet ---", stdout_val)
        
        # Check for key log messages indicating the flow for the SECOND tweet
        self.assertIn(f"Tweet Text: {simulated_tweet2[:200]}...", stdout_val)
        self.assertIn("Sentiment Analysis: {", stdout_val) # Check sentiment logged again
        self.assertIn("Attempting to get trade suggestion for sentiment:", stdout_val) # Check suggestion attempted again
        self.assertRegex(stdout_val, r"Trade Suggestion: \{.*\}|Could not derive trade suggestion", 
                         "Expected a trade suggestion log or derivation failure log for second tweet")
        
        # Check that no major unexpected *errors* were logged to stderr
        # Allow for specific "Error:" lines from parsing attempts if they happen
        lines_in_stderr = stderr_val.strip().split('\n')
        unexpected_errors = [line for line in lines_in_stderr if line.startswith("Error:") and "LLM response was not valid JSON" not in line and "Still not valid JSON after stripping" not in line and "Cannot parse None response text" not in line and "Input sentiment_analysis missing required keys" not in line]
        self.assertEqual(len(unexpected_errors), 0, f"Found unexpected errors in stderr: {unexpected_errors}")

if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + sys.argv[1:], exit=False)
