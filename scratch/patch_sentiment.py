import json
import re
import random

file_path = 'web/analyst_data.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract JSON from window.ANALYST_DATABASE = { ... };
match = re.search(r'window\.ANALYST_DATABASE\s*=\s*(\{.*?\});', content, re.DOTALL)
if match:
    json_str = match.group(1)
    data = json.loads(json_str)
    
    # Patch reports with sentiment scores based on rating
    for rep in data.get('reports', []):
        if 'sentiment_score' not in rep:
            if rep['rating'] == '매수 (Buy)':
                rep['sentiment_score'] = random.randint(70, 95)
            elif rep['rating'] == '홀딩 (Hold)':
                rep['sentiment_score'] = random.randint(40, 60)
            else:
                rep['sentiment_score'] = random.randint(10, 30)

    # Patch recommendations with sentiment scores
    for rec in data.get('recommendations', []):
        if 'sentiment_score' not in rec:
            if rec['current_rating'] == '매수 (Buy)':
                rec['sentiment_score'] = random.randint(70, 95)
            elif rec['current_rating'] == '홀딩 (Hold)':
                rec['sentiment_score'] = random.randint(40, 60)
            else:
                rec['sentiment_score'] = random.randint(10, 30)
                
    new_json_str = json.dumps(data, indent=2, ensure_ascii=False)
    new_content = f"window.ANALYST_DATABASE = {new_json_str};\n"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully patched analyst_data.js with sentiment scores.")
else:
    print("Failed to find ANALYST_DATABASE in analyst_data.js")
