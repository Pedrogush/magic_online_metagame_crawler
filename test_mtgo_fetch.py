#!/usr/bin/env python
"""Test MTGO.com page fetching to analyze performance characteristics."""

import re
import sys
from pathlib import Path

# Add parent directory to path to import navigators module
sys.path.insert(0, str(Path(__file__).parent))

from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time


DETAIL_RE = re.compile(r"window\.MTGO\.decklists\.data\s*=\s*(\{.*?\});", re.DOTALL)


def fetch_with_streaming(url: str) -> tuple[str, dict]:
    """Fetch URL with streaming, stopping when JSON is found."""
    print(f"\n{'='*60}")
    print(f"STREAMING FETCH (optimized)")
    print(f"{'='*60}")

    start_time = time.time()
    response = curl_requests.get(url, impersonate='chrome', timeout=30, stream=True)
    response.raise_for_status()

    accumulated = ""
    chunk_size = 8192
    total_bytes = 0
    chunks_read = 0

    for chunk in response.iter_content(chunk_size=chunk_size, decode_unicode=True):
        if chunk:
            accumulated += chunk
            total_bytes += len(chunk)
            chunks_read += 1

            if "window.MTGO.decklists.data" in accumulated:
                match = DETAIL_RE.search(accumulated)
                if match:
                    response.close()
                    elapsed = time.time() - start_time

                    stats = {
                        'bytes': total_bytes,
                        'chunks': chunks_read,
                        'time': elapsed,
                        'json_size': len(match.group(1))
                    }

                    if response.headers.get('content-length'):
                        stats['total_size'] = int(response.headers['content-length'])
                        stats['saved_pct'] = round((1 - total_bytes / stats['total_size']) * 100, 1)

                    return accumulated, stats

    elapsed = time.time() - start_time
    stats = {
        'bytes': total_bytes,
        'chunks': chunks_read,
        'time': elapsed,
        'json_size': 0
    }
    return accumulated, stats


def fetch_without_streaming(url: str) -> tuple[str, dict]:
    """Fetch entire page without streaming."""
    print(f"\n{'='*60}")
    print(f"NORMAL FETCH (baseline)")
    print(f"{'='*60}")

    start_time = time.time()
    response = curl_requests.get(url, impersonate='chrome', timeout=30)
    response.raise_for_status()
    html = response.text
    elapsed = time.time() - start_time

    stats = {
        'bytes': len(html),
        'time': elapsed,
        'json_size': 0
    }

    match = DETAIL_RE.search(html)
    if match:
        stats['json_size'] = len(match.group(1))

    return html, stats


def analyze_mtgo_page():
    """Fetch and analyze an MTGO decklist page structure."""
    # Get a real URL from the index
    index_url = 'https://www.mtgo.com/decklists/2025/10'
    print(f'Fetching index: {index_url}')

    index_response = curl_requests.get(index_url, impersonate='chrome', timeout=30)
    print(f'Index status: {index_response.status_code}')

    if index_response.status_code != 200:
        print('Failed to fetch index, exiting')
        return

    # Parse index to get first decklist URL
    soup = BeautifulSoup(index_response.text, 'lxml')
    link = soup.select_one('li.decklists-item a.decklists-link')
    if not link or not link.get('href'):
        print('No decklist links found')
        return

    url = urljoin('https://www.mtgo.com', link['href'])
    print(f'Found first decklist: {url}')

    # Test 1: Normal fetch (baseline)
    html_normal, stats_normal = fetch_without_streaming(url)
    print(f"Downloaded: {stats_normal['bytes']:,} bytes ({round(stats_normal['bytes']/1024, 2)} KB)")
    print(f"Time: {stats_normal['time']:.3f}s")
    print(f"JSON payload: {stats_normal['json_size']:,} bytes ({round(stats_normal['json_size']/1024, 2)} KB)")
    print()

    # Test 2: Streaming fetch (optimized)
    html_stream, stats_stream = fetch_with_streaming(url)
    print(f"Downloaded: {stats_stream['bytes']:,} bytes ({round(stats_stream['bytes']/1024, 2)} KB)")
    print(f"Time: {stats_stream['time']:.3f}s")
    print(f"JSON payload: {stats_stream['json_size']:,} bytes ({round(stats_stream['json_size']/1024, 2)} KB)")
    print(f"Chunks read: {stats_stream['chunks']}")

    if 'saved_pct' in stats_stream:
        print(f"Total page size: {stats_stream['total_size']:,} bytes ({round(stats_stream['total_size']/1024, 2)} KB)")
        print(f"Bandwidth saved: {stats_stream['saved_pct']}%")

    # Comparison
    print(f"\n{'='*60}")
    print(f"COMPARISON")
    print(f"{'='*60}")

    if stats_stream['bytes'] < stats_normal['bytes']:
        saved_bytes = stats_normal['bytes'] - stats_stream['bytes']
        saved_pct = round((saved_bytes / stats_normal['bytes']) * 100, 1)
        print(f"✓ Streaming saved {saved_bytes:,} bytes ({saved_pct}%)")
    else:
        print(f"✗ Streaming used same or more data")

    if stats_stream['time'] < stats_normal['time']:
        time_saved = stats_normal['time'] - stats_stream['time']
        time_pct = round((time_saved / stats_normal['time']) * 100, 1)
        print(f"✓ Streaming saved {time_saved:.3f}s ({time_pct}% faster)")
    else:
        time_diff = stats_stream['time'] - stats_normal['time']
        print(f"✗ Streaming took {time_diff:.3f}s longer")

    # Verify both methods got the same JSON
    if stats_stream['json_size'] == stats_normal['json_size'] and stats_stream['json_size'] > 0:
        print(f"✓ Both methods extracted identical JSON payload")
    else:
        print(f"⚠ JSON sizes differ or missing")

if __name__ == '__main__':
    analyze_mtgo_page()
