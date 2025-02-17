##################################################
# 1) Import Packages
##################################################

import requests
import pandas as pd
import openpyxl
import json
from bs4 import BeautifulSoup
import itertools
from urllib.parse import urljoin

##################################################
# 2) Define Functions
##################################################

# Helper function to parse the “metadata card”
def parse_metadata_card(soup):
    """
    Find the 'metadata-card' block and extract pairs
    like ("Type" -> "Capability", "Reference" -> "DOM10.CAP72", etc.).
    Returns a dict.
    """
    metadata = {}
    metadata_card = soup.find("div", class_="metadata-card")
    if not metadata_card:
        return metadata  # No metadata card found
    title_elems = metadata_card.find_all("p", class_="title")
    for title_elem in title_elems:
        label = title_elem.get_text(strip=True)
        # Find the next significant sibling:
        # For 'Reference', we expect a <div class="codification-data">.
        # For others (like 'Type' or 'Mandate'), the next sibling is usually a <p>.
        possible_sibling = title_elem.find_next_sibling()
        if not possible_sibling:
            metadata[label] = ""
            continue
        # Special case for "Reference" if the next sibling is a <div class="codification-data">:
        if label == "Reference":
            # If the next sibling is that special div, grab its text:
            if possible_sibling.name == "div" and "codification-data" in possible_sibling.get("class", []):
                metadata[label] = possible_sibling.get_text(strip=True)
                continue
            else:
                # Fallback to a <p> if for some reason the HTML changed
                if possible_sibling.name == "p":
                    metadata[label] = possible_sibling.get_text(strip=True)
                else:
                    metadata[label] = ""
                continue
        else:
            # For non-"Reference" fields, we assume the value is the next <p>
            if possible_sibling.name == "p":
                metadata[label] = possible_sibling.get_text(strip=True)
            else:
                metadata[label] = ""
    return metadata

# Parsing a Domain page
def parse_domain_page(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, "html.parser")
    # 1) Parse the metadata card
    domain_metadata = parse_metadata_card(soup)
    # 2) Grab the main domain description. Typically the summary text
    #    is inside <div class="clearfix text-formatted field ...">
    #    (based on your screenshot).
    desc_div = soup.find("div", class_="clearfix text-formatted field field--name-body field--type-text-with-summary field--label-hidden field__item")
    domain_description = ""
    if desc_div:
        # get_text() merges all child paragraphs, etc.
        domain_description = desc_div.get_text(separator="\n", strip=True)
    return {
        "metadata": domain_metadata,
        "description": domain_description
    }

# Parsing a Capability page
def parse_capability_page(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, "html.parser")
    # 1) Parse metadata card
    cap_metadata = parse_metadata_card(soup)
    # 2) Collect <h2> headings and the paragraphs (or lists) underneath
    section_texts = {}  # e.g. {"Definition": "...", "Purpose": "...", ...}
    h2s = soup.find_all("h2")
    for h2 in h2s:
        heading = h2.get_text(strip=True)
        content_parts = []
        # Move through siblings until we see the next <h2> or no more siblings
        sibling = h2.next_sibling
        while sibling:
            # If we’ve reached another <h2>, break out
            if sibling.name == "h2":
                break
            # If it’s a paragraph, or an unordered list, etc., gather its text
            if sibling.name == "p":
                content_parts.append(sibling.get_text(strip=True))
            elif sibling.name == "ul":
                # Possibly gather bullet points
                content_parts.append(sibling.get_text(separator="\n", strip=True))
            sibling = sibling.next_sibling
        # Combine all that text
        section_text = "\n\n".join(content_parts)
        section_texts[heading] = section_text
    return {
        "metadata": cap_metadata,
        "sections": section_texts
    }

# Helper function to parse h2 sections
def parse_h2_sections(soup):
    """
    Returns a dict mapping each <h2> heading to a dict with:
      {
         "text": "All paragraph/bullet text under the h2 (until next h2)",
         "links": [ { "text": "...", "url": "..." }, ... ]
      }
    Preserves line breaks in text but also enumerates links separately.
    """
    sections = {}
    h2s = soup.find_all("h2")
    for h2 in h2s:
        heading_text = h2.get_text(strip=True)
        content_lines = []
        links_found = []
        # Move through siblings until we see the next <h2> or no more siblings
        sibling = h2.next_sibling
        while sibling:
            if sibling.name == "h2":
                break
            if sibling.name == "p":
                # Grab the paragraph text (with line breaks)
                paragraph_text = sibling.get_text("\n", strip=False)
                paragraph_text = paragraph_text.strip("\r\n ")
                if paragraph_text:
                    content_lines.append(paragraph_text)
                # Find all <a> tags for links
                for a in sibling.find_all("a"):
                    link_text = a.get_text(strip=True)
                    href = a.get("href", "")
                    # Make absolute URL if relative
                    full_url = urljoin(BASE_URL, href)
                    links_found.append({"text": link_text, "url": full_url})
            elif sibling.name == "ul":
                # Gather bullet points
                for li in sibling.find_all("li"):
                    li_text = li.get_text("\n", strip=False)
                    li_text = li_text.strip("\r\n ")
                    if li_text:
                        content_lines.append(li_text)
                    # Also find links in each <li>
                    for a in li.find_all("a"):
                        link_text = a.get_text(strip=True)
                        href = a.get("href", "")
                        full_url = urljoin(BASE_URL, href)
                        links_found.append({"text": link_text, "url": full_url})
            sibling = sibling.next_sibling
        # Combine text lines with double newlines between items
        combined_text = "\n\n".join(content_lines)
        sections[heading_text] = {
            "text": combined_text,
            "links": links_found
        }
    return sections


# Parse policy pages
def parse_policy_page(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, "html.parser")
    # 1) Extract metadata
    metadata = parse_metadata_card(soup)
    # 2) Grab the main body text
    body_div = soup.find("div", class_="clearfix text-formatted field field--name-body field--type-text-with-summary field--label-hidden field__item")
    # If that fails, you might also check for
    #   soup.find("div", class_="node__content") or some other container
    if not body_div:
        body_div = soup.find("div", class_="node__content")
    if body_div:
        # Extract text before first <h2> => "description" - i.e. We loop over body_div’s children until we hit an <h2>
        desc_lines = []
        for child in body_div.children:
            # If this is an <h2>, stop collecting
            if child.name == "h2":
                break
            # If it’s a tag we can get text from, or navigable string, gather it
            if hasattr(child, "get_text"):
                text = child.get_text("\n", strip=True)
            else:
                # Possibly a NavigableString
                text = str(child).strip()
            if text:
                desc_lines.append(text)
        # Now join all the description lines together
        policy_description = "\n".join(desc_lines)
        sections = parse_h2_sections(body_div)
        all_text = body_div.get_text("\n", strip=True)
    else:
        sections = {}
        all_text = ""
        policy_description = ""
    # 3) Locate the “Policy requirements” heading
    #    Typically stored in a small <div class="field--name-field-policy-requirements-title field__item">
    policy_req_title_div = soup.find(
        "div",
        class_="field field--name-field-policy-requirements-title field--type-string field--label-hidden field__item"
    )
    if policy_req_title_div:
        policy_req_title = policy_req_title_div.get_text(strip=True)
    else:
        policy_req_title = ""
    # 4) The descriptive text under “Policy requirements,” if present
    #    Usually in <div class="clearfix text-formatted field field--name-field-requirements-body field--type-text-long ...">
    policy_req_body_div = soup.find(
        "div",
        class_="clearfix text-formatted field field--name-field-requirements-body field--type-text-long field--label-hidden field__item"
    )
    if policy_req_body_div:
        policy_req_body = policy_req_body_div.get_text("\n", strip=True)
    else:
        policy_req_body = ""
    # 5) The “children of policies” block (each item with its own heading + text)
    #    <div class="field field--name-field-children-of-policies field--type-entity-reference field--label-hidden field__items">
    policy_children_div = soup.find(
        "div",
        class_="field field--name-field-children-of-policies field--type-entity-reference field--label-hidden field__items"
    )
    policy_children = []  # Will hold a list of dicts: [{heading: "...", content: "..."}...]
    if policy_children_div:
        # Each child item is typically <div class="field__item"> containing heading + text
        item_divs = policy_children_div.find_all("div", class_="field__item")
        for item_div in item_divs:
            # Example: The heading might be in <h3>, <strong>, or just a bold <p>
            heading_elem = item_div.find(["h2", "h3", "strong", "p"])
            heading_text = heading_elem.get_text(strip=True) if heading_elem else ""
            # Then gather paragraphs or lists beneath it
            paragraphs = item_div.find_all("p")
            paragraph_lines = []
            children_links = []
            for p in paragraphs:
                p_text = p.get_text("\n", strip=False).strip("\r\n ")
                if p_text:
                    paragraph_lines.append(p_text)
                # also find links
                for a in p.find_all("a"):
                    link_text = a.get_text(strip=True)
                    href = a.get("href", "")
                    full_url = urljoin(BASE_URL, href)
                    children_links.append({"text": link_text, "url": full_url})
                # Merge all paragraphs into one combined string
            combined_content = "\n\n".join(paragraph_lines)
            policy_children.append({
                "heading": heading_text,
                "content": combined_content,
                "links": children_links
            })
    return {
        "metadata": metadata,
        "description": policy_description,
        "sections": sections,  # <h2> sections from the main body
        #"raw_text": all_text,  # the entire body in one string
        "policy_requirements": {
            "title": policy_req_title,  # e.g. "Policy requirements"
            "body": policy_req_body,  # text below "Policy requirements"
            "children": policy_children  # list of sub-items
        }
    }


# Parse standard and design pages
def parse_standard_design_pages(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, "html.parser")
    metadata = parse_metadata_card(soup)
    # Some Design pages might store the main text in a slightly different container.
    # Start with the same guess:
    body_div = soup.find("div", class_="clearfix text-formatted field field--name-body field--type-text-with-summary field--label-hidden field__item")
    # If that fails, you might also check for
    #   soup.find("div", class_="node__content") or some other container
    if not body_div:
        body_div = soup.find("div", class_="node__content")
    if body_div:
        # Extract text before first <h2> => "description" - i.e. We loop over body_div’s children until we hit an <h2>
        desc_lines = []
        for child in body_div.children:
            # If this is an <h2>, stop collecting
            if child.name == "h2":
                break
            # If it’s a tag we can get text from, or navigable string, gather it
            if hasattr(child, "get_text"):
                text = child.get_text("\n", strip=True)
            else:
                # Possibly a NavigableString
                text = str(child).strip()
            if text:
                desc_lines.append(text)
        # Now join all the description lines together
        design_description = "\n".join(desc_lines)
        sections = parse_h2_sections(body_div)
        all_text = body_div.get_text("\n", strip=True)
    else:
        sections = {}
        all_text = ""
        design_description = ""
    return {
        "metadata": metadata,
        "description": design_description,
        "sections": sections,
        #"raw_text": all_text,
    }

# Example usage
#policy_url = "https://architecture.digital.gov.au/einvoicing-policy"
#policy_data = parse_policy_page(policy_url)
#print("Policy metadata:", policy_data["metadata"])
#print("Policy headings => text:", policy_data["sections"])
#standard_url = "https://architecture.digital.gov.au/einvoicing-standard"
#standard_data = parse_standard_design_pages(standard_url)
#design_url = "https://architecture.digital.gov.au/einvoicing-government-entities-govteams-site"
#design_data = parse_standard_design_pages(design_url)

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
    # --- 1) Parse domain/capability ---
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
    # --- 2) Helper function to parse a field of multiple <a> links ---
    def parse_links_field(html_string):
        """Returns a list of dicts: [{'text': 'Some Link', 'url': '...'}, ...]"""
        soup = BeautifulSoup(html_string, "html.parser")
        link_data = []
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            url = BASE_URL + link["href"]
            link_data.append({"text": text, "url": url})
        return link_data
        # --- 3) Parse designs/policies/standards/strategies ---
    designs_html = item.get("Designs", "")
    policies_html = item.get("Policies", "")
    standards_html = item.get("Standards", "")
    strategies_html = item.get("Strategies", "")
    # Now apply the helper function
    designs = parse_links_field(designs_html)
    policies = parse_links_field(policies_html)
    standards = parse_links_field(standards_html)
    strategies = parse_links_field(strategies_html)
    # --- 4) Filter to only the “Data and Analytics” or “AI” domain (if desired) ---
    # If you only want certain domains, you can do:
    if ("/data-and-analytics" not in domain_href) and ("/ai" not in domain_href):
        continue
    # --- 5) Extract information from the domain capability page ---
    domain_info = parse_domain_page(full_domain_link)
    capability_info = parse_capability_page(full_capability_link)
    capability_sections = capability_info.get("sections", {})
    definition_text = capability_sections.get("Definition")
    if not definition_text:
        # Fall back to first heading after the 'Header menu' and 'Explore the AGA' section - if any headings exist
        if capability_sections:
            first_heading = next(itertools.islice(capability_sections, 2, 3), None)
            definition_text = capability_sections[first_heading]
        else:
            definition_text = "Missing"
    # For headings that may be absent, just do .get(..., "Missing")
    objective_text = capability_sections.get("Objective", "Missing")
    purpose_text = capability_sections.get("Purpose", "Missing")
    wog_applicability_text = capability_sections.get("Whole of government applicability", "Missing")
    # --- 6) Build the record and append to results ---
    record = {
        "domain_name": domain_text,
        "domain_url": full_domain_link,
        "domain_reference": domain_info['metadata']['Reference'],
        "domain_mandate": domain_info['metadata']['Mandate'],
        "domain_description": domain_info['description'],
        "capability_name": capability_text,
        "capability_url": full_capability_link,
        "capability_reference": capability_info['metadata']['Reference'],
        "capability_mandate": capability_info['metadata']['Mandate'],
        "capability_definition": definition_text,
        "capability_objective": objective_text,
        "capability_purpose": purpose_text,
        "capability_WoG_applicability": wog_applicability_text,
        "designs": designs,
        "policies": policies,
        "standards": standards,
        "strategies": strategies
    }
    results.append(record)

# --- 7) Convert results to a single DataFrame ---
df = pd.DataFrame(results)

# For example, show the first few rows
print(df.head())

# Optionally, print `results` of your filtered list of domains/capabilities
for row in results:
    print(row["domain_text"], "->", row["capability_text"])
    print("Link:", row["capability_url"])
    print("------")

# Optionally, save to CSV or XLSX
df.to_csv("govt_digital_infrastructure_website.csv", index=False)
#df.to_excel("govt_digital_infrastructure_website.xlsx", index=False)