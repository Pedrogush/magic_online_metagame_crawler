#!/usr/bin/env python
"""Test MTGO.com page fetching to analyze performance characteristics."""

import re
from curl_cffi import requests as curl_requests

def analyze_mtgo_page():
    """Fetch and analyze an MTGO decklist page structure."""
    # First try to get a real URL from the index
    index_url = 'https://www.mtgo.com/decklists/2025/10'
    print(f'Fetching index: {index_url}')

    index_response = curl_requests.get(index_url, impersonate='chrome', timeout=30)
    print(f'Index status: {index_response.status_code}')

    if index_response.status_code != 200:
        print('Failed to fetch index, trying sample URL directly')
        url = 'https://www.mtgo.com/decklist/modern-league-2025-10-229742'
    else:
        # Parse index to get first decklist URL
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(index_response.text, 'lxml')
        link = soup.select_one('li.decklists-item a.decklists-link')
        if link and link.get('href'):
            from urllib.parse import urljoin
            url = urljoin('https://www.mtgo.com', link['href'])
            print(f'Found first decklist: {url}')
        else:
            url = 'https://www.mtgo.com/decklist/modern-league-2025-10-229742'

    print()
    print(f'Fetching decklist: {url}')
    print()

    response = curl_requests.get(url, impersonate='chrome', timeout=30)
    print(f'Status: {response.status_code}')
    print(f'Content-Length: {response.headers.get("content-length", "Not specified")}')
    print(f'Content-Encoding: {response.headers.get("content-encoding", "None")}')
    print(f'Content-Type: {response.headers.get("content-type")}')
    print()

    html = response.text
    print(f'Response size (bytes): {len(html)}')
    print(f'Response size (KB): {round(len(html) / 1024, 2)}')
    print()

    # Find where the JSON data appears in the HTML
    pattern = r'window\.MTGO\.decklists\.data\s*=\s*(\{.*?\});'
    match = re.search(pattern, html, re.DOTALL)
    if match:
        json_start = html.find(match.group(0))
        print(f'JSON data found at position: {json_start}')
        print(f'Percentage into HTML: {round(json_start / len(html) * 100, 2)}%')
        print()

        json_payload = match.group(1)
        print(f'JSON payload size (bytes): {len(json_payload)}')
        print(f'JSON payload size (KB): {round(len(json_payload) / 1024, 2)}')
        print(f'Ratio of payload to total HTML: {round(len(json_payload) / len(html) * 100, 2)}%')
        print()

        # Check if the data appears in the first part of the HTML
        html_head_end = html.find('</head>')
        html_body_start = html.find('<body')

        if html_head_end > 0:
            print(f'<head> ends at position: {html_head_end}')
            if json_start < html_head_end:
                print('✓ JSON is in <head> (server-side rendered)')
            else:
                print('✗ JSON is after <head> (likely in <body>)')

        if html_body_start > 0:
            print(f'<body> starts at position: {html_body_start}')
            if json_start > html_body_start:
                print('JSON is in <body>')

        # Look for script tags
        script_pattern = r'<script[^>]*>(.*?)window\.MTGO\.decklists\.data'
        script_match = re.search(script_pattern, html, re.DOTALL)
        if script_match:
            script_content_before = script_match.group(1)
            print(f'\nContent before JSON in <script>: {len(script_content_before)} chars')

        print()
        print('=' * 60)
        print('OPTIMIZATION ANALYSIS:')
        print('=' * 60)

        # Calculate potential savings
        overhead_before = json_start
        overhead_after = len(html) - (json_start + len(match.group(0)))

        print(f'Data before JSON: {overhead_before} bytes ({round(overhead_before/1024, 2)} KB)')
        print(f'Data after JSON: {overhead_after} bytes ({round(overhead_after/1024, 2)} KB)')
        print(f'Total overhead: {overhead_before + overhead_after} bytes ({round((overhead_before + overhead_after)/1024, 2)} KB)')
        print()

        if json_start / len(html) < 0.5:
            print('✓ JSON appears in first half of HTML - streaming could help')
        else:
            print('✗ JSON appears in second half of HTML - streaming less effective')

    else:
        print('✗ JSON data not found in page')
        print('Checking for alternative patterns...')

        # Look for any window.MTGO assignments
        mtgo_pattern = r'window\.MTGO[^=]+=\s*'
        matches = re.findall(mtgo_pattern, html)
        if matches:
            print(f'Found {len(matches)} window.MTGO assignments:')
            for m in matches[:5]:
                print(f'  {m}')

if __name__ == '__main__':
    analyze_mtgo_page()
