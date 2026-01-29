from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from functools import wraps
from datetime import datetime, date, timedelta
import requests
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

load_dotenv()

# Initialize Flask app with templates folder in the same directory
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

if supabase_url and supabase_key:
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        # Test connection with a simple query
        try:
            supabase.table('users').select('id').limit(1).execute()
            print("✓ Supabase connection successful")
        except Exception as e:
            print(f"⚠ Warning: Supabase client created but connection test failed: {e}")
            print("  This may indicate the project is paused or unreachable.")
            supabase = None
    except Exception as e:
        print(f"✗ Error initializing Supabase client: {e}")
        supabase = None
else:
    supabase = None
    print("Warning: Supabase credentials not found. Some features may not work.")

# Initialize background job scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5001/auth/google/callback')


def login_required(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def check_supabase_connection():
    """
    Check if Supabase is available and return status.
    
    Returns:
        tuple: (is_available: bool, error_message: str or None)
    """
    if supabase is None:
        return False, "Supabase is not configured"
    
    try:
        # Try a simple query to test connectivity
        supabase.table('users').select('id').limit(1).execute()
        return True, None
    except Exception as e:
        error_msg = str(e).lower()
        if 'nodename' in error_msg or 'servname' in error_msg or 'dns' in error_msg:
            return False, "Supabase project appears to be paused or unreachable. Please check your Supabase project status."
        elif 'connection' in error_msg or 'timeout' in error_msg:
            return False, "Cannot connect to Supabase. Please check your internet connection and Supabase project status."
        else:
            return False, f"Supabase error: {str(e)}"


def handle_supabase_error(e, default_message="Database error"):
    """
    Handle Supabase errors and return user-friendly messages.
    
    Args:
        e: Exception object
        default_message: Default error message if error type is unknown
        
    Returns:
        str: User-friendly error message
    """
    error_msg = str(e).lower()
    
    if 'nodename' in error_msg or 'servname' in error_msg or 'dns' in error_msg:
        return "Supabase project appears to be paused or unreachable. Please check your Supabase project status."
    elif 'connection' in error_msg or 'timeout' in error_msg:
        return "Cannot connect to Supabase. Please check your internet connection and Supabase project status."
    elif 'authentication' in error_msg or 'unauthorized' in error_msg:
        return "Supabase authentication failed. Please check your API keys."
    else:
        return default_message


@app.route('/')
def index():
    """Render the main page with the map component."""
    google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY', '')
    return render_template('index.html', google_maps_api_key=google_maps_api_key)


@app.route('/api/health')
def health_check():
    """Health check endpoint to verify Supabase connectivity."""
    supabase_status, error_message = check_supabase_connection()
    return jsonify({
        'status': 'healthy' if supabase_status else 'degraded',
        'supabase': {
            'available': supabase_status,
            'error': error_message
        },
        'timestamp': datetime.now().isoformat()
    }), 200 if supabase_status else 503


@app.route('/event/<event_id>')
def event_details(event_id):
    """Render event details page for URL-based access."""
    google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY', '')
    return render_template('event_details.html', event_id=event_id, google_maps_api_key=google_maps_api_key)


@app.route('/auth/google')
def google_auth():
    """Initiate Google OAuth flow."""
    if not GOOGLE_CLIENT_ID:
        return jsonify({'error': 'Google OAuth not configured'}), 500
    
    # Validate redirect URI format
    from urllib.parse import urlparse
    parsed_uri = urlparse(GOOGLE_REDIRECT_URI)
    if not parsed_uri.scheme or not parsed_uri.netloc:
        print(f"ERROR: Invalid redirect URI format: {GOOGLE_REDIRECT_URI}")
        return jsonify({'error': f'Invalid redirect URI format: {GOOGLE_REDIRECT_URI}'}), 500
    
    print(f"Starting OAuth flow with redirect_uri: {GOOGLE_REDIRECT_URI}")
    
    from urllib.parse import urlencode
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'offline',
        'prompt': 'consent'
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return redirect(auth_url)


@app.route('/auth/google/callback')
def google_callback():
    """Handle Google OAuth callback."""
    code = request.args.get('code')
    if not code:
        return redirect('/?error=auth_failed')
    
    # Exchange code for tokens
    token_url = 'https://oauth2.googleapis.com/token'
    token_data = {
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    
    try:
        # Validate redirect URI before making requests
        if not GOOGLE_REDIRECT_URI or not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            print(f"OAuth configuration error: redirect_uri={GOOGLE_REDIRECT_URI}, client_id={'set' if GOOGLE_CLIENT_ID else 'missing'}, client_secret={'set' if GOOGLE_CLIENT_SECRET else 'missing'}")
            return redirect('/?error=oauth_not_configured')
        
        # Validate redirect URI format
        from urllib.parse import urlparse
        parsed_uri = urlparse(GOOGLE_REDIRECT_URI)
        if not parsed_uri.scheme or not parsed_uri.netloc:
            print(f"Invalid redirect URI format: {GOOGLE_REDIRECT_URI}")
            return redirect('/?error=invalid_redirect_uri')
        
        # Ensure redirect URI is properly formatted (no port in hostname for validation)
        # The redirect URI should be the full URL including port, but we need to validate it correctly
        redirect_uri_for_request = GOOGLE_REDIRECT_URI
        
        print(f"Exchanging code for token with redirect_uri: {redirect_uri_for_request}")
        print(f"Token URL: {token_url}")
        print(f"Client ID: {GOOGLE_CLIENT_ID[:10]}... (truncated)")
        
        # Make the token exchange request with explicit timeout and error handling
        try:
            token_response = requests.post(
                token_url, 
                data=token_data, 
                timeout=10,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
        except requests.exceptions.Timeout:
            print("ERROR: Timeout while exchanging code for token")
            return redirect('/?error=timeout')
        except requests.exceptions.ConnectionError as e:
            print(f"ERROR: Connection error while exchanging code for token: {e}")
            print(f"Error details: {type(e).__name__}")
            if hasattr(e, 'args') and e.args:
                print(f"Error args: {e.args}")
            return redirect('/?error=connection_error')
        
        token_response.raise_for_status()
        tokens = token_response.json()
        access_token = tokens['access_token']
        
        # Get user info from Google
        print("Fetching user info from Google")
        user_info_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            user_response = requests.get(user_info_url, headers=headers, timeout=10)
        except requests.exceptions.Timeout:
            print("ERROR: Timeout while fetching user info")
            return redirect('/?error=timeout')
        except requests.exceptions.ConnectionError as e:
            print(f"ERROR: Connection error while fetching user info: {e}")
            print(f"Error details: {type(e).__name__}")
            return redirect('/?error=connection_error')
        
        user_response.raise_for_status()
        user_info = user_response.json()
        
        # Store or update user in database
        if supabase:
            try:
                # Check if user exists
                user_check = supabase.table('users').select('*').eq('google_id', user_info['id']).execute()
                
                if user_check.data:
                    user = user_check.data[0]
                    user_id = user['id']
                    # Update user info in case it changed (name, email, picture)
                    # This ensures the database always has the latest info from Google
                    update_response = supabase.table('users').update({
                        'email': user_info['email'],
                        'name': user_info.get('name'),
                        'picture_url': user_info.get('picture')
                    }).eq('id', user_id).execute()
                    print(f"Updated user {user_id}: name={user_info.get('name')}, email={user_info['email']}")
                else:
                    # Create new user
                    new_user = supabase.table('users').insert({
                        'google_id': user_info['id'],
                        'email': user_info['email'],
                        'name': user_info.get('name'),
                        'picture_url': user_info.get('picture')
                    }).execute()
                    user_id = new_user.data[0]['id']
                    print(f"Created new user {user_id}: name={user_info.get('name')}, email={user_info['email']}, google_id={user_info['id']}")
                
                # Store in session
                session['user_id'] = user_id
                session['user_email'] = user_info['email']
            except Exception as e:
                error_message = handle_supabase_error(e, "Failed to save user information")
                print(f"ERROR: {error_message}")
                print(f"Exception details: {type(e).__name__}: {e}")
                return redirect(f'/?error=supabase_error&message={error_message.replace(" ", "%20")}')
        else:
            return redirect('/?error=supabase_not_configured')
            session['user_name'] = user_info.get('name')
            session['user_picture'] = user_info.get('picture')
            
            # Debug: Log the user info
            print(f"User authenticated: user_id={user_id}, email={user_info['email']}, name={user_info.get('name')}")
        
        # Redirect back to the page they came from or home
        redirect_url = request.args.get('redirect', '/')
        return redirect(redirect_url)
    except requests.exceptions.RequestException as e:
        print(f"Network error in Google OAuth callback: {e}")
        print(f"Error type: {type(e).__name__}")
        if hasattr(e, 'request'):
            print(f"Request URL: {e.request.url if e.request else 'N/A'}")
        return redirect('/?error=network_error')
    except Exception as e:
        print(f"Error in Google OAuth callback: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return redirect('/?error=auth_failed')


@app.route('/auth/logout')
def logout():
    """Logout user."""
    session.clear()
    return redirect('/')


@app.route('/api/auth/status')
def auth_status():
    """Get current authentication status."""
    if 'user_id' in session:
        # Verify user still exists in database and get fresh info
        user_id = session['user_id']
        if supabase:
            try:
                user_check = supabase.table('users').select('id, email, name, picture_url').eq('id', user_id).execute()
                if user_check.data and len(user_check.data) > 0:
                    user_data = user_check.data[0]
                    # Update session with fresh data
                    session['user_email'] = user_data.get('email')
                    session['user_name'] = user_data.get('name')
                    session['user_picture'] = user_data.get('picture_url')
                    return jsonify({
                        'authenticated': True,
                        'user_id': user_id,
                        'email': user_data.get('email'),
                        'name': user_data.get('name'),
                        'picture': user_data.get('picture_url')
                    })
                else:
                    # User not found in database, clear session
                    session.clear()
                    return jsonify({'authenticated': False})
            except Exception as e:
                error_message = handle_supabase_error(e, "Error verifying user")
                print(f"Error verifying user in auth_status: {error_message}")
                # Fall back to session data if available
                if 'user_id' in session:
                    return jsonify({
                        'authenticated': True,
                        'user_id': user_id,
                        'email': session.get('user_email'),
                        'name': session.get('user_name'),
                        'picture': session.get('user_picture'),
                        'warning': 'Database connection issue - using cached session data'
                    })
                else:
                    return jsonify({
                        'authenticated': False,
                        'error': error_message
                    }), 503
        else:
            # Supabase not configured, use session data
            return jsonify({
                'authenticated': True,
                'user_id': user_id,
                'email': session.get('user_email'),
                'name': session.get('user_name'),
                'picture': session.get('user_picture')
            })
    return jsonify({'authenticated': False})


@app.route('/api/places', methods=['GET'])
def get_places():
    """Get places from Supabase (if stored) or return empty list."""
    if supabase is None:
        return jsonify([])
    
    try:
        response = supabase.table('places').select('*').execute()
        return jsonify(response.data)
    except Exception as e:
        print(f"Error fetching places: {e}")
        return jsonify([])


@app.route('/api/places', methods=['POST'])
def save_place():
    """Save a place to Supabase."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        data = request.get_json()
        response = supabase.table('places').insert(data).execute()
        return jsonify(response.data)
    except Exception as e:
        print(f"Error saving place: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/destinations', methods=['GET'])
@login_required
def get_destinations():
    """Get destinations for the authenticated user (created, joined, or interested)."""
    if supabase is None:
        return jsonify({'error': 'Database not configured'}), 503
    
    # Check Supabase connection first
    supabase_available, error_message = check_supabase_connection()
    if not supabase_available:
        return jsonify({'error': error_message}), 503
    
    try:
        user_id = session['user_id']
        
        # Get destinations where user is organizer
        created = supabase.table('destinations').select('*').eq('user_id', user_id).execute()
        
        # Get destinations where user is a participant
        participants_response = supabase.table('event_participants').select('event_id, participation_type').eq('user_id', user_id).execute()
        participants_data = participants_response.data if participants_response.data else []
        event_ids = [p['event_id'] for p in participants_data]
        
        # Get participant destinations
        participant_destinations = []
        if event_ids:
            participant_dest = supabase.table('destinations').select('*').in_('id', event_ids).execute()
            participant_destinations = participant_dest.data if participant_dest.data else []
        
        # Combine and deduplicate
        all_destinations = {}
        for dest in created.data:
            all_destinations[dest['id']] = {**dest, 'is_organizer': True}
            # Explicitly set organizer_name to None for events you organize (will show "You" in frontend)
            all_destinations[dest['id']]['organizer_name'] = None
        
        for dest in participant_destinations:
            if dest['id'] not in all_destinations:
                # Get participation type
                part = next((p for p in participants_data if p['event_id'] == dest['id']), None)
                all_destinations[dest['id']] = {
                    **dest,
                    'is_organizer': False,
                    'participation_type': part['participation_type'] if part else None
                }
        
        # Get organizer info for all destinations (both created and participant)
        # Only get organizer info for events where user is NOT the organizer
        for dest_id, dest in all_destinations.items():
            if dest.get('user_id') and not dest.get('is_organizer'):
                try:
                    organizer = supabase.table('users').select('name, email').eq('id', dest['user_id']).execute()
                    if organizer.data and len(organizer.data) > 0:
                        organizer_info = organizer.data[0]
                        dest['organizer_name'] = organizer_info.get('name') or organizer_info.get('email') or 'Unknown'
                        # Debug: Log organizer lookup
                        print(f"Event {dest_id} organizer: user_id={dest['user_id']}, name={dest['organizer_name']}")
                    else:
                        dest['organizer_name'] = 'Unknown'
                        print(f"Warning: No organizer found for event {dest_id} with user_id={dest['user_id']}")
                except Exception as e:
                    print(f"Error fetching organizer for event {dest_id}: {e}")
                    dest['organizer_name'] = 'Unknown'
        
        # Convert to list for further processing
        result = list(all_destinations.values())
        
        # Fetch participant counts for all relevant events to determine friend labels
        event_ids = list(all_destinations.keys())
        friends_counts = {}
        if event_ids:
            participants_response = supabase.table('event_participants')\
                .select('event_id, user_id, participation_type')\
                .in_('event_id', event_ids)\
                .execute()
            if participants_response.data:
                for participant in participants_response.data:
                    event_id = participant.get('event_id')
                    participant_user_id = participant.get('user_id')
                    if participant_user_id == user_id:
                        continue  # Skip the current user
                    if event_id not in friends_counts:
                        friends_counts[event_id] = {'joined': 0, 'interested': 0}
                    if participant.get('participation_type') == 'joined':
                        friends_counts[event_id]['joined'] += 1
                    elif participant.get('participation_type') == 'interested':
                        friends_counts[event_id]['interested'] += 1
        
        # Attach friend counts to destinations
        for dest in result:
            counts = friends_counts.get(dest['id'], {'joined': 0, 'interested': 0})
            dest['friends_joining_count'] = counts['joined']
            dest['friends_interested_count'] = counts['interested']
        
        # Sort final result
        result.sort(key=lambda x: (x.get('scheduled_date', ''), x.get('scheduled_time', '')))
        
        return jsonify(result)
    except Exception as e:
        error_message = handle_supabase_error(e, "Failed to fetch destinations")
        print(f"Error fetching destinations: {error_message}")
        return jsonify({'error': error_message}), 503


@app.route('/api/destinations/<destination_id>', methods=['GET'])
def get_destination(destination_id):
    """Get a single destination with organizer info and participants."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        dest_response = supabase.table('destinations').select('*').eq('id', destination_id).execute()
        if not dest_response.data:
            return jsonify({'error': 'Destination not found'}), 404
        
        destination = dest_response.data[0]
        
        # Get organizer info
        if destination.get('user_id'):
            try:
                organizer = supabase.table('users').select('id, name, email, picture_url').eq('id', destination['user_id']).execute()
                if organizer.data and len(organizer.data) > 0:
                    destination['organizer'] = organizer.data[0]
                    print(f"Event {destination_id} organizer: user_id={destination['user_id']}, name={organizer.data[0].get('name')}")
                    
                    # Check if current user is following the organizer (if authenticated)
                    if 'user_id' in session:
                        current_user_id = session['user_id']
                        organizer_id = destination['organizer']['id']
                        if organizer_id != current_user_id:
                            follow_check = supabase.table('user_follows').select('id').eq('follower_id', current_user_id).eq('following_id', organizer_id).execute()
                            if follow_check.data:
                                destination['is_friend_event'] = True
                else:
                    print(f"Warning: No organizer found for event {destination_id} with user_id={destination['user_id']}")
            except Exception as e:
                print(f"Error fetching organizer for event {destination_id}: {e}")
        
        # Get all participants with user info
        participants_response = supabase.table('event_participants').select('*').eq('event_id', destination_id).execute()
        participants = participants_response.data if participants_response.data else []
        
        # Get user info for each participant and check if we're following them
        if 'user_id' in session:
            current_user_id = session['user_id']
            for participant in participants:
                participant_user_id = participant.get('user_id')
                if participant_user_id and participant_user_id != current_user_id:
                    # Check if we're following this participant
                    follow_check = supabase.table('user_follows').select('id').eq('follower_id', current_user_id).eq('following_id', participant_user_id).execute()
                    if follow_check.data:
                        # This is a friend event because we're following a participant
                        destination['is_friend_event'] = True
        
        # Get user info for each participant
        for participant in participants:
            try:
                user_info = supabase.table('users').select('id, name, email, picture_url').eq('id', participant['user_id']).execute()
                if user_info.data and len(user_info.data) > 0:
                    participant['user'] = user_info.data[0]
                    print(f"Participant: user_id={participant['user_id']}, name={user_info.data[0].get('name')}")
                else:
                    print(f"Warning: No user found for participant user_id={participant['user_id']}")
            except Exception as e:
                print(f"Error fetching user info for participant user_id={participant['user_id']}: {e}")
        
        destination['participants'] = participants
        
        # Separate joined and interested
        destination['joined'] = [p for p in participants if p['participation_type'] == 'joined']
        destination['interested'] = [p for p in participants if p['participation_type'] == 'interested']
        destination['joined_count'] = len(destination['joined'])
        destination['interested_count'] = len(destination['interested'])
        
        return jsonify(destination)
    except Exception as e:
        error_message = handle_supabase_error(e, "Failed to fetch destination")
        print(f"Error fetching destination: {error_message}")
        return jsonify({'error': error_message}), 503


@app.route('/api/destinations', methods=['POST'])
@login_required
def save_destination():
    """Save a destination/event to Supabase."""
    if supabase is None:
        return jsonify({'error': 'Database not configured'}), 503
    
    # Check Supabase connection first
    supabase_available, error_message = check_supabase_connection()
    if not supabase_available:
        return jsonify({'error': error_message}), 503
    
    try:
        data = request.get_json()
        
        # Validate required fields (scheduled_time is optional)
        required_fields = ['place_name', 'latitude', 'longitude', 'scheduled_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Add user_id from session (ensure it's the logged-in user)
        user_id = session['user_id']
        data['user_id'] = user_id
        
        # Debug: Log the user_id being used
        print(f"Creating event with user_id: {user_id}")
        
        # If scheduled_time is not provided, set to None (all-day event)
        if 'scheduled_time' not in data or not data['scheduled_time']:
            data['scheduled_time'] = None
        
        # Set default status to 'active' if not provided
        if 'status' not in data:
            data['status'] = 'active'
        
        try:
            response = supabase.table('destinations').insert(data).execute()
            
            # Verify the created event has the correct user_id
            if response.data:
                created_event = response.data[0] if isinstance(response.data, list) else response.data
                print(f"Event created with user_id: {created_event.get('user_id')}")
            
            return jsonify(response.data[0] if isinstance(response.data, list) and len(response.data) > 0 else response.data)
        except Exception as e:
            error_message = handle_supabase_error(e, "Failed to save destination")
            print(f"Error saving destination: {error_message}")
            return jsonify({'error': error_message}), 503
    except Exception as e:
        error_message = handle_supabase_error(e, "Failed to save destination")
        print(f"Error saving destination: {error_message}")
        return jsonify({'error': error_message}), 503


@app.route('/api/destinations/<destination_id>', methods=['DELETE'])
@login_required
def delete_destination(destination_id):
    """Delete a destination (only if user is the organizer)."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        # Check if user is the organizer
        dest_response = supabase.table('destinations').select('user_id').eq('id', destination_id).execute()
        if not dest_response.data:
            return jsonify({'error': 'Destination not found'}), 404
        
        if dest_response.data[0]['user_id'] != session['user_id']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        response = supabase.table('destinations').delete().eq('id', destination_id).execute()
        return jsonify({'success': True, 'deleted': response.data})
    except Exception as e:
        print(f"Error deleting destination: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/destinations/<destination_id>/cancel', methods=['PATCH'])
@login_required
def cancel_destination(destination_id):
    """Cancel a destination (only if user is the organizer)."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        # Check if user is the organizer
        dest_response = supabase.table('destinations').select('*').eq('id', destination_id).execute()
        
        if not dest_response.data:
            return jsonify({'error': 'Destination not found'}), 404
        
        destination = dest_response.data[0]
        
        if destination['user_id'] != session['user_id']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Check if destination is already cancelled
        if destination.get('status') == 'cancelled':
            return jsonify({'error': 'Destination is already cancelled'}), 400
        
        # Check if destination is in the past (cannot cancel past events)
        scheduled_date = datetime.strptime(destination['scheduled_date'], '%Y-%m-%d').date()
        
        # Handle optional scheduled_time
        if destination.get('scheduled_time'):
            scheduled_time = datetime.strptime(destination['scheduled_time'], '%H:%M:%S').time()
            scheduled_datetime = datetime.combine(scheduled_date, scheduled_time)
        else:
            # For all-day events, check if date is in the past
            scheduled_datetime = datetime.combine(scheduled_date, datetime.min.time())
        
        if scheduled_datetime < datetime.now():
            return jsonify({'error': 'Cannot cancel past events'}), 400
        
        # Update status to cancelled
        response = supabase.table('destinations').update({'status': 'cancelled'}).eq('id', destination_id).execute()
        return jsonify(response.data)
    except Exception as e:
        print(f"Error cancelling destination: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<event_id>/participate', methods=['POST'])
@login_required
def participate_event(event_id):
    """Join or mark interest in an event."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        data = request.get_json()
        participation_type = data.get('type')  # 'joined' or 'interested'
        
        if participation_type not in ['joined', 'interested']:
            return jsonify({'error': 'Invalid participation type'}), 400
        
        # Check if event exists
        event_check = supabase.table('destinations').select('id').eq('id', event_id).execute()
        if not event_check.data:
            return jsonify({'error': 'Event not found'}), 404
        
        user_id = session['user_id']
        
        # Debug: Log the user_id being used
        print(f"Participating in event {event_id} with user_id: {user_id}")
        
        # Check if already participating
        existing = supabase.table('event_participants').select('*').eq('event_id', event_id).eq('user_id', user_id).execute()
        
        if existing.data:
            # Update participation type
            response = supabase.table('event_participants').update({
                'participation_type': participation_type
            }).eq('event_id', event_id).eq('user_id', user_id).execute()
        else:
            # Create new participation
            response = supabase.table('event_participants').insert({
                'event_id': event_id,
                'user_id': user_id,
                'participation_type': participation_type
            }).execute()
        
        # Verify the participation record
        if response.data:
            participation = response.data[0] if isinstance(response.data, list) else response.data
            print(f"Participation created/updated with user_id: {participation.get('user_id')}")
        
        return jsonify(response.data[0] if response.data else {})
    except Exception as e:
        print(f"Error participating in event: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<event_id>/participate', methods=['DELETE'])
@login_required
def unparticipate_event(event_id):
    """Remove participation from an event."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        user_id = session['user_id']
        response = supabase.table('event_participants').delete().eq('event_id', event_id).eq('user_id', user_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error removing participation: {e}")
        return jsonify({'error': str(e)}), 500


# Initialize background jobs
def init_jobs():
    """Initialize and schedule all background jobs."""
    if supabase is None:
        print("Warning: Background jobs not started - Supabase not configured")
        return
    
    from app.jobs import EventStatusUpdater
    
    # Create job instance
    event_status_updater = EventStatusUpdater(supabase)
    
    # Run immediately on startup to catch up on any past events
    print("Running initial event status update to catch up on past events...")
    initial_result = event_status_updater.run()
    print(f"Initial update: {initial_result.get('message', 'Completed')}")
    
    # Schedule job to run every 1 minute
    scheduler.add_job(
        func=event_status_updater.run,
        trigger=IntervalTrigger(minutes=1),
        id='event_status_updater',
        name='Update Event Statuses',
        replace_existing=True
    )
    
    print("Background jobs initialized: EventStatusUpdater scheduled to run every 1 minute")


# Initialize jobs when app starts
init_jobs()


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get user profile information with follow status and upcoming events."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        user_response = supabase.table('users').select('id, google_id, email, name, picture_url, created_at').eq('id', user_id).execute()
        if not user_response.data:
            return jsonify({'error': 'User not found'}), 404
        
        user = user_response.data[0]
        # Don't expose google_id
        user.pop('google_id', None)
        
        # Check if current user is following this user
        is_following = False
        if 'user_id' in session:
            current_user_id = session['user_id']
            follow_check = supabase.table('user_follows').select('id').eq('follower_id', current_user_id).eq('following_id', user_id).execute()
            is_following = len(follow_check.data) > 0 if follow_check.data else False
        
        user['is_following'] = is_following
        
        # Upcoming events (next 7 days including today/weekend)
        start_date = date.today()
        end_date = start_date + timedelta(days=7)
        start_iso = start_date.isoformat()
        end_iso = end_date.isoformat()
        
        upcoming_events = []
        
        # Events user organized within range
        organized_events = supabase.table('destinations').select('*')\
            .eq('user_id', user_id)\
            .eq('status', 'active')\
            .gte('scheduled_date', start_iso)\
            .lte('scheduled_date', end_iso)\
            .execute()
        if organized_events.data:
            for event in organized_events.data:
                event['is_organizer'] = True
                upcoming_events.append(event)
        
        # Events user is participating in within range
        participant_events = supabase.table('event_participants').select('event_id, participation_type')\
            .eq('user_id', user_id).execute()
        if participant_events.data:
            event_ids = [p['event_id'] for p in participant_events.data]
            if event_ids:
                participant_destinations = supabase.table('destinations').select('*')\
                    .in_('id', event_ids)\
                    .eq('status', 'active')\
                    .gte('scheduled_date', start_iso)\
                    .lte('scheduled_date', end_iso)\
                    .execute()
                if participant_destinations.data:
                    for event in participant_destinations.data:
                        part = next((p for p in participant_events.data if p['event_id'] == event['id']), None)
                        event['is_organizer'] = False
                        event['participation_type'] = part['participation_type'] if part else None
                        upcoming_events.append(event)
        
        # Sort by date then time
        upcoming_events.sort(key=lambda x: (
            x.get('scheduled_date', ''),
            x.get('scheduled_time') or '23:59:59'
        ))
        user['upcoming_events'] = upcoming_events
        
        return jsonify(user)
    except Exception as e:
        print(f"Error fetching user: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/users/<int:user_id>/follow', methods=['POST'])
@login_required
def follow_user(user_id):
    """Follow a user."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        follower_id = session['user_id']
        
        # Can't follow yourself
        if follower_id == user_id:
            return jsonify({'error': 'Cannot follow yourself'}), 400
        
        # Check if already following
        existing = supabase.table('user_follows').select('id').eq('follower_id', follower_id).eq('following_id', user_id).execute()
        if existing.data:
            return jsonify({'error': 'Already following this user'}), 400
        
        # Create follow relationship
        response = supabase.table('user_follows').insert({
            'follower_id': follower_id,
            'following_id': user_id
        }).execute()
        
        return jsonify({'success': True, 'message': 'User followed successfully'})
    except Exception as e:
        print(f"Error following user: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/users/<int:user_id>/follow', methods=['DELETE'])
@login_required
def unfollow_user(user_id):
    """Unfollow a user."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        follower_id = session['user_id']
        
        response = supabase.table('user_follows').delete().eq('follower_id', follower_id).eq('following_id', user_id).execute()
        
        return jsonify({'success': True, 'message': 'User unfollowed successfully'})
    except Exception as e:
        print(f"Error unfollowing user: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/friends', methods=['GET'])
@login_required
def get_friends():
    """Get list of users that the current user follows."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        user_id = session['user_id']
        
        # Get all users that current user follows
        follows_response = supabase.table('user_follows').select('following_id').eq('follower_id', user_id).execute()
        
        if not follows_response.data:
            return jsonify([])
        
        following_ids = [f['following_id'] for f in follows_response.data]
        
        # Get user details for followed users
        users_response = supabase.table('users').select('id, email, name, picture_url, created_at').in_('id', following_ids).execute()
        
        return jsonify(users_response.data if users_response.data else [])
    except Exception as e:
        print(f"Error fetching friends: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/friends/events', methods=['GET'])
@login_required
def get_friend_events():
    """Get active events from users that the current user follows."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        user_id = session['user_id']
        
        # Get all users that current user follows
        follows_response = supabase.table('user_follows').select('following_id').eq('follower_id', user_id).execute()
        
        if not follows_response.data:
            return jsonify([])
        
        following_ids = [f['following_id'] for f in follows_response.data]
        
        # Get active events from followed users (not past, not cancelled)
        # Events where followed user is organizer
        events_response = supabase.table('destinations').select('*').in_('user_id', following_ids).eq('status', 'active').gte('scheduled_date', date.today().isoformat()).execute()
        
        # Also get events where followed users are participants (joined or interested)
        participant_events_response = supabase.table('event_participants').select('event_id, user_id, participation_type').in_('user_id', following_ids).execute()
        
        friend_events = []
        if events_response.data:
            for event in events_response.data:
                # Get organizer info
                organizer = supabase.table('users').select('id, name, email, picture_url').eq('id', event['user_id']).execute()
                if organizer.data:
                    event['organizer'] = organizer.data[0]
                    event['is_organizer'] = False  # Not organized by current user
                friend_events.append(event)
        
        # Get events where followed users are participants
        if participant_events_response.data:
            event_ids = [p['event_id'] for p in participant_events_response.data]
            if event_ids:
                part_events = supabase.table('destinations').select('*').in_('id', event_ids).eq('status', 'active').gte('scheduled_date', date.today().isoformat()).execute()
                if part_events.data:
                    for event in part_events.data:
                        # Get the followed user's participation info
                        part = next((p for p in participant_events_response.data if p['event_id'] == event['id']), None)
                        if part:
                            # Get the followed user's info
                            followed_user = supabase.table('users').select('id, name, email, picture_url').eq('id', part['user_id']).execute()
                            if followed_user.data:
                                event['friend_participant'] = followed_user.data[0]
                                event['friend_participation_type'] = part['participation_type']
                                # Get organizer info
                                if event.get('user_id'):
                                    organizer = supabase.table('users').select('id, name, email, picture_url').eq('id', event['user_id']).execute()
                                    if organizer.data:
                                        event['organizer'] = organizer.data[0]
                                friend_events.append(event)
        
        # Remove duplicates (same event might appear if user is both organizer and participant)
        seen_event_ids = set()
        unique_events = []
        for event in friend_events:
            if event['id'] not in seen_event_ids:
                seen_event_ids.add(event['id'])
                unique_events.append(event)
        
        return jsonify(unique_events)
    except Exception as e:
        print(f"Error fetching friend events: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)
