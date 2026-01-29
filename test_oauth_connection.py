#!/usr/bin/env python3
"""
Test script to diagnose Google OAuth connection issues.
This will help identify if the DNS error is related to network connectivity or configuration.
"""

import os
import sys
from dotenv import load_dotenv
import requests
from urllib.parse import urlparse

load_dotenv()

print("=" * 60)
print("Google OAuth Configuration Test")
print("=" * 60)

# Check environment variables
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5001/auth/google/callback')

print(f"\n1. Environment Variables:")
print(f"   GOOGLE_CLIENT_ID: {'✓ Set' if GOOGLE_CLIENT_ID else '✗ Missing'}")
print(f"   GOOGLE_CLIENT_SECRET: {'✓ Set' if GOOGLE_CLIENT_SECRET else '✗ Missing'}")
print(f"   GOOGLE_REDIRECT_URI: {GOOGLE_REDIRECT_URI}")

# Validate redirect URI format
print(f"\n2. Redirect URI Validation:")
parsed_uri = urlparse(GOOGLE_REDIRECT_URI)
if not parsed_uri.scheme:
    print(f"   ✗ ERROR: Missing scheme (http:// or https://)")
    sys.exit(1)
if not parsed_uri.netloc:
    print(f"   ✗ ERROR: Missing hostname")
    sys.exit(1)
print(f"   ✓ Scheme: {parsed_uri.scheme}")
print(f"   ✓ Hostname: {parsed_uri.netloc}")
print(f"   ✓ Path: {parsed_uri.path}")

# Test network connectivity to Google OAuth endpoints
print(f"\n3. Network Connectivity Tests:")

test_urls = [
    'https://accounts.google.com',
    'https://oauth2.googleapis.com',
    'https://www.googleapis.com'
]

for url in test_urls:
    try:
        print(f"   Testing {url}...", end=' ')
        response = requests.get(url, timeout=5)
        print(f"✓ OK (Status: {response.status_code})")
    except requests.exceptions.Timeout:
        print(f"✗ TIMEOUT")
    except requests.exceptions.ConnectionError as e:
        print(f"✗ CONNECTION ERROR: {e}")
    except Exception as e:
        print(f"✗ ERROR: {type(e).__name__}: {e}")

# Test DNS resolution
print(f"\n4. DNS Resolution Test:")
import socket
test_hosts = ['accounts.google.com', 'oauth2.googleapis.com', 'www.googleapis.com']
for host in test_hosts:
    try:
        print(f"   Resolving {host}...", end=' ')
        ip = socket.gethostbyname(host)
        print(f"✓ {ip}")
    except socket.gaierror as e:
        print(f"✗ DNS ERROR: {e}")
    except Exception as e:
        print(f"✗ ERROR: {type(e).__name__}: {e}")

# Check if redirect URI hostname can be resolved (if not localhost)
if parsed_uri.netloc and parsed_uri.netloc != 'localhost' and not parsed_uri.netloc.startswith('127.0.0.1'):
    print(f"\n5. Redirect URI Hostname Resolution:")
    try:
        print(f"   Resolving {parsed_uri.netloc}...", end=' ')
        ip = socket.gethostbyname(parsed_uri.netloc)
        print(f"✓ {ip}")
    except socket.gaierror as e:
        print(f"✗ DNS ERROR: Cannot resolve {parsed_uri.netloc}")
        print(f"   This might be the cause of your error!")
        print(f"   Make sure the hostname in GOOGLE_REDIRECT_URI is correct.")
    except Exception as e:
        print(f"✗ ERROR: {type(e).__name__}: {e}")

print(f"\n" + "=" * 60)
print("Test Complete")
print("=" * 60)

if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    print("\n⚠ WARNING: Missing OAuth credentials. Please check your .env file.")
    sys.exit(1)

print("\n✓ Configuration looks good. If you're still getting errors,")
print("  check the Flask console output for more details.")

