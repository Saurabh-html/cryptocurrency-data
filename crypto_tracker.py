import requests
import pandas as pd
import time
import schedule
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from datetime import datetime
import os

# Configure logging
logging.basicConfig(
    filename='crypto_tracker.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Constants
API_URL = 'https://api.coingecko.com/api/v3/coins/markets'
EXCEL_FILE = 'crypto_live_data.xlsx'
FIELDS = ['name', 'symbol', 'current_price', 'market_cap', 'total_volume', 'price_change_percentage_24h']

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_crypto_data():
    """Fetch top 50 cryptocurrencies with retries and rate limiting."""
    params = {
        'vs_currency': 'usd',
        'order': 'market_cap_desc',
        'per_page': 50,
        'page': 1,
        'sparkline': 'false',
        'price_change_percentage': '24h'
    }
    try:
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        logging.info("Data fetched successfully")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"API Error: {str(e)}")
        raise

def process_data(data):
    """Process and clean API data."""
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)[FIELDS]
    df['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df.rename(columns={
        'current_price': 'Price (USD)',
        'market_cap': 'Market Cap',
        'total_volume': '24h Volume',
        'price_change_percentage_24h': '24h Change (%)'
    }, inplace=True)
    return df.round(2)

def analyze_data(df):
    """Perform required analysis."""
    if df.empty:
        return {}
    
    analysis = {
        'top_5': df[['name', 'symbol', 'Market Cap']].head(5),
        'avg_price': df['Price (USD)'].mean(),
        'max_change': df.loc[df['24h Change (%)'].idxmax()],
        'min_change': df.loc[df['24h Change (%)'].idxmin()]
    }
    return analysis

def update_excel(df, analysis):
    """Update Excel with data and analysis."""
    try:
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            # Update live data sheet
            df.to_excel(writer, sheet_name='Live Data', index=False)
            
            # Update analysis sheet
            analysis_df = pd.DataFrame({
                'Metric': [
                    'Top 5 Cryptos (Market Cap)',
                    'Average Price (USD)',
                    'Highest 24h Gain (%)',
                    'Lowest 24h Loss (%)'
                ],
                'Value': [
                    ', '.join(analysis['top_5']['name'].tolist()),
                    round(analysis['avg_price'], 2),
                    f"{analysis['max_change']['24h Change (%)']}% ({analysis['max_change']['name']})",
                    f"{analysis['min_change']['24h Change (%)']}% ({analysis['min_change']['name']})"
                ]
            })
            analysis_df.to_excel(writer, sheet_name='Analysis', index=False)
            
        logging.info("Excel updated successfully")
    except Exception as e:
        logging.error(f"Excel Error: {str(e)}")

def job():
    """Main job sequence."""
    try:
        data = fetch_crypto_data()
        if not data:
            return
        df = process_data(data)
        analysis = analyze_data(df)
        update_excel(df, analysis)
        print(f"Updated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logging.critical(f"Job failed: {str(e)}")

if __name__ == "__main__":
    # Initialize Excel with headers if file doesn't exist
    if not os.path.exists(EXCEL_FILE):
        pd.DataFrame().to_excel(EXCEL_FILE, sheet_name='Live Data')
    
    # First run
    job()
    
    # Schedule every 5 minutes
    schedule.every(5).minutes.do(job)
    
    # Keep script running
    while True:
        schedule.run_pending()
        time.sleep(1)