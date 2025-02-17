##################################################
# 1) Import Packages
##################################################

import requests
import pandas as pd
import openpyxl
import json
from bs4 import BeautifulSoup

##################################################
# 2) Define Functions
##################################################



##################################################
# 3) Accessing Web Data
##################################################

BASE_URL = "https://architecture.digital.gov.au"
EXPORT_ENDPOINT = BASE_URL + "/dynamic-data-export"

response = requests.get(EXPORT_ENDPOINT)

if response.status_code == 200:
    data = response.json()   # Parse JSON response
    print(data)
else:
    print(f"Request failed with status code {response.status_code}")

##################################################
# 3) Extracting Features/Data
##################################################

results = []

for item in data:
    domain_html = item["Domain"]  # e.g. "<a href=\"/ai\">Artificial Intelligence (AI)</a>"
    capability_html = item["Capability"]  # e.g. "<a href=\"/generative-artificial-intelligence\">Generative Artificial Intelligence (GenAI)</a>"
    # Parse out the actual link and text from each field
    domain_soup = BeautifulSoup(domain_html, "html.parser")
    domain_a = domain_soup.find("a")
    if not domain_a:
        continue  # No domain link found, skip
    domain_text = domain_a.text.strip()
    domain_href = domain_a["href"]
    full_domain_link = BASE_URL + domain_href  # combine to get absolute URL
    # Similarly for the capability:
    capability_soup = BeautifulSoup(capability_html, "html.parser")
    capability_a = capability_soup.find("a")
    capability_text = capability_a.text.strip()
    capability_href = capability_a["href"]
    full_capability_link = BASE_URL + capability_href
    # Now lets expand on that pattern to parse "Designs"
    designs_html = item.get("Designs", "")
    designs_soup = BeautifulSoup(designs_html, "html.parser")
    design_links = designs_soup.find_all("a")
    for dlink in design_links:
        print(" Design link text:", dlink.text, " | URL:", BASE_URL + dlink["href"])
    # If you specifically only want data from “Data and Analytics” or “AI” domain:
    if "/data-and-analytics" in domain_href or "/ai" in domain_href:
        # Here, gather the info you need
        # You might check if capability_text has "GenAI", "Deep Learning", etc.
        record = {
            "domain_text": domain_text,
            "domain_url": full_domain_link,
            "capability_text": capability_text,
            "capability_url": full_capability_link,
            # The item also has "Designs", "Policies", "Standards", "Strategies"
            # which themselves contain multiple <a href="..."> links separated by " | "
        }
        results.append(record)

# Now `results` is your filtered list of domains/capabilities
for row in results:
    print(row["domain_text"], "->", row["capability_text"])
    print("Link:", row["capability_url"])
    print("------")


# Create a DataFrame with every column
df = pd.DataFrame(results)

# Optionally, view a subset of the created DataFrame
print(df.head()) # Print top 10 rows

# Optionally, save to CSV or XLSX
df.to_csv("govt_digital_infrastructure_website.csv", index=False)
#df.to_excel("govt_digital_infrastructure_website.xlsx", index=False)