import requests

BASE_URL = 'https://sppims-dams.dsdiqlgp.qld.gov.au/api/v1/spp'

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0"
}


def fetch_suburb_names():
    """Fetch suburb names from the API."""
    url = f"{BASE_URL}/suburb_name/"
    response = requests.post(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()  # Returns a list of suburb names
    else:
        return f"Error: {response.status_code}, {response.text}"


def fetch_layer_categories():
    """Fetch available layer categories from the API."""
    url = f"{BASE_URL}/layer_categories/"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()  # Returns layer categories
    else:
        return f"Error: {response.status_code}, {response.text}"


if __name__ == "__main__":
    suburb_data = fetch_suburb_names()

    print("Suburb Names:", suburb_data)

    layer_data = fetch_layer_categories()

    print("Layer Categories:", layer_data)