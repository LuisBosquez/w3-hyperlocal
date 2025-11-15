#!/usr/bin/env python3
"""
OAuth Configuration Test Script
Run this to verify your Google OAuth setup is correct.
"""

import os
import sys
from dotenv import load_dotenv
import requests
from urllib.parse import urlencode

load_dotenv()

def test_oauth_config():
    """Test OAuth configuration."""
    print("=" * 60)
    print("Google OAuth Configuration Test")
    print("=" * 60)
    print()
    
    # Check required environment variables
    google_client_id = os.getenv('GOOGLE_CLIENT_ID')
    google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    google_redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5001/auth/google/callback')
    flask_secret_key = os.getenv('FLASK_SECRET_KEY')
    
    print("1. Checking Environment Variables:")
    print("-" * 40)
    
    checks = {
        'GOOGLE_CLIENT_ID': google_client_id,
        'GOOGLE_CLIENT_SECRET': google_client_secret,
        'GOOGLE_REDIRECT_URI': google_redirect_uri,
        'FLASK_SECRET_KEY': flask_secret_key
    }
    
    all_present = True
    for key, value in checks.items():
        if value:
            # Mask secret values
            if 'SECRET' in key or 'KEY' in key:
                display_value = value[:8] + "..." if len(value) > 8 else "***"
            else:
                display_value = value
            print(f"   ✓ {key}: {display_value}")
        else:
            print(f"   ✗ {key}: NOT SET")
            all_present = False
    
    print()
    
    if not all_present:
        print("❌ ERROR: Some required environment variables are missing!")
        print("   Please add them to your .env file.")
        return False
    
    # Validate Google Client ID format
    print("2. Validating Google Client ID Format:")
    print("-" * 40)
    if google_client_id and '.' in google_client_id:
        client_id_parts = google_client_id.split('.')
        if len(client_id_parts) >= 2:
            print(f"   ✓ Client ID format looks valid (contains domain: {client_id_parts[0]})")
        else:
            print(f"   ⚠ Client ID format may be incorrect")
    else:
        print(f"   ⚠ Client ID format may be incorrect")
    
    print()
    
    # Test OAuth URL generation
    print("3. Testing OAuth URL Generation:")
    print("-" * 40)
    try:
        params = {
            'client_id': google_client_id,
            'redirect_uri': google_redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'offline',
            'prompt': 'consent'
        }
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        print(f"   ✓ OAuth URL generated successfully")
        print(f"   URL length: {len(auth_url)} characters")
        print()
        print("   You can test the OAuth flow by:")
        print(f"   1. Starting your Flask app: python3 run.py")
        print(f"   2. Opening: http://localhost:5001")
        print(f"   3. Clicking 'Sign in with Google'")
        print()
    except Exception as e:
        print(f"   ✗ Error generating OAuth URL: {e}")
        return False
    
    # Validate redirect URI
    print("4. Validating Redirect URI:")
    print("-" * 40)
    if 'localhost' in google_redirect_uri or '127.0.0.1' in google_redirect_uri:
        print(f"   ✓ Redirect URI is for local development")
        print(f"   ⚠ Make sure this exact URI is added in Google Cloud Console:")
        print(f"      {google_redirect_uri}")
    elif 'http://' in google_redirect_uri:
        print(f"   ⚠ Using HTTP (not HTTPS) - OK for local development")
        print(f"   ⚠ Make sure this exact URI is added in Google Cloud Console:")
        print(f"      {google_redirect_uri}")
    else:
        print(f"   ✓ Redirect URI looks valid")
        print(f"   ⚠ Make sure this exact URI is added in Google Cloud Console:")
        print(f"      {google_redirect_uri}")
    
    print()
    
    # Check Google Cloud Console requirements
    print("5. Google Cloud Console Checklist:")
    print("-" * 40)
    print("   Please verify in Google Cloud Console:")
    print("   [ ] OAuth 2.0 Client ID is created")
    print("   [ ] Application type is 'Web application'")
    print(f"   [ ] Authorized redirect URIs includes: {google_redirect_uri}")
    print("   [ ] OAuth consent screen is configured")
    print("   [ ] Test users are added (if in testing mode)")
    print()
    
    # Test Flask app connectivity
    print("6. Testing Flask App (if running):")
    print("-" * 40)
    try:
        response = requests.get('http://localhost:5001/api/auth/status', timeout=2)
        if response.status_code == 200:
            print("   ✓ Flask app is running and responding")
            data = response.json()
            if data.get('authenticated'):
                print(f"   ✓ User is currently authenticated: {data.get('email')}")
            else:
                print("   ℹ No user is currently authenticated (this is normal)")
        else:
            print(f"   ⚠ Flask app responded with status: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ℹ Flask app is not running (start it with: python3 run.py)")
    except Exception as e:
        print(f"   ℹ Could not connect to Flask app: {e}")
    
    print()
    print("=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print()
    print("Next Steps:")
    print("1. Make sure all environment variables are set in .env")
    print("2. Verify redirect URI in Google Cloud Console")
    print("3. Start Flask app: python3 run.py")
    print("4. Try signing in with Google")
    print()
    
    return True

if __name__ == '__main__':
    success = test_oauth_config()
    sys.exit(0 if success else 1)

