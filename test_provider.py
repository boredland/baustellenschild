#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup

url = "https://www.bauaufsicht-frankfurt.de/service/bauschild"
resp = requests.get(url)

soup = BeautifulSoup(resp.text, "html.parser")
form = soup.find("form", class_="tx-vierwd-baf-infothek")
if not form:
    print("Form with class not found, trying any form...")
    form = soup.find("form")

print(f"Form found: {form is not None}")
if form:
    print(f"Form attributes: {form.attrs}")
    provider = form.get("data-ac-provider")
    print(f"data-ac-provider: {provider}")
