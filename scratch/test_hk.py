import urllib.request
from bs4 import BeautifulSoup
import urllib.parse

url = "http://consensus.hankyung.com/apps.analysis/analysis.list"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('euc-kr', errors='ignore')
        soup = BeautifulSoup(html, 'html.parser')
        
        table = soup.find('table', {'class': 'table_style01'})
        if table:
            rows = table.find_all('tr')
            for row in rows[1:10]:
                cols = row.find_all('td')
                if len(cols) >= 6:
                    date = cols[0].text.strip()
                    title = cols[1].text.strip()
                    rating = cols[3].text.strip()
                    target = cols[4].text.strip()
                    firm = cols[5].text.strip()
                    print(f"Date: {date}, Title: {title}, Rating: {rating}, Target: {target}, Firm: {firm}")
except Exception as e:
    print("Error:", e)
