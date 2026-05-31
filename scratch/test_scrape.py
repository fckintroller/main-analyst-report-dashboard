import urllib.request
from bs4 import BeautifulSoup
import re

url = "https://finance.naver.com/research/company_list.naver"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('euc-kr', errors='ignore')
        soup = BeautifulSoup(html, 'html.parser')
        
        table = soup.find('table', {'class': 'type_1'})
        if table:
            rows = table.find_all('tr')
            for row in rows[2:10]: # Skip header
                cols = row.find_all('td')
                if len(cols) >= 5:
                    stock = cols[0].text.strip()
                    title = cols[1].text.strip()
                    firm = cols[2].text.strip()
                    date = cols[4].text.strip()
                    print(f"Stock: {stock}, Title: {title}, Firm: {firm}, Date: {date}")
except Exception as e:
    print("Error:", e)
