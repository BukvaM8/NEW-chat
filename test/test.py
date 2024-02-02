import requests
import time

api_url = "https://www.virustotal.com/api/v3/files"
headers = {"x-apikey": "fdd6dfc0214034eb4d84a2a5659435804e8b85057a95e818a8ff8f4c7accfb6d"}
file_path = "processed_all_reviews_1.json"

start_time = time.perf_counter()
with open(file_path, "rb") as file:
    files = {"file": (file_path, file)}
    response = requests.post(api_url, headers=headers, files=files)
    print(response)
    if response.status_code == 200:
        result = response.json()
        file_id = result.get("data").get("id")

        print(file_id)

        analysis_url = "https://www.virustotal.com/api/v3/" + "analyses/" + file_id
        res = requests.get(analysis_url, headers=headers)
        print(res)
        if res.status_code == 200:
            result = res.json()
            print(result)
            if result.get("data").get("attributes").get("last_analysis_results"):
                stats = result.get("data").get("attributes").get("last_analysis_stats")
                results = result.get("data").get("attributes").get("last_analysis_results")
                print(stats)
                print(results)

print(time.perf_counter() - start_time)