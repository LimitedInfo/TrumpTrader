# Truth Social Selenium Bot

A Selenium bot that navigates to truthsocial.com and attempts to log in.

## Setup

1. Create a `.env` file in the project root with your credentials:
```env
TRUTH_SOCIAL_USERNAME=your_username_here
TRUTH_SOCIAL_PASSWORD=your_password_here
```

2. Install Python dependencies:
```
pip install -r requirements.txt --user
```

3. Make sure you have Microsoft Edge installed on your machine.

## Usage

Run the Edge version with:
```
python edge_scrapper.py
```

## Features

- Navigates to truthsocial.com
- Attempts to log in using credentials from the `.env` file
- Maximizes the browser window
- Includes basic page scraping functionality (currently commented out after login)

## Customization

- Uncomment the headless option in `setup_driver()` to run without a visible browser
- Modify the `login_to_truth_social` function for different login flows
- Uncomment or add scraping logic after successful login in the `main` function

## Troubleshooting

- Ensure your credentials in the `.env` file are correct.
- Make sure your browser is up to date.
- Check that you have the latest Python dependencies installed.
- Try running in non-headless mode first.
- Login flows on websites can change; the XPaths used might need updating if the site structure changes. 