from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from functools import wraps
from datetime import datetime
import requests
import json

load_dotenv()

# Initialize Flask app with templates folder in the same directory
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

if supabase_url and supabase_key:
    supabase: Client = create_client(supabase_url, supabase_key)
else:
    supabase = None
    print("Warning: Supabase credentials not found. Some features may not work.")

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


@app.route('/')
def index():
    """Render the main page with the map component."""
    google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY', '')
    return render_template('index.html', google_maps_api_key=google_maps_api_key)


@app.route('/event/<int:event_id>')
def event_details(event_id):
    """Render event details page for URL-based access."""
    google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY', '')
    return render_template('event_details.html', event_id=event_id, google_maps_api_key=google_maps_api_key)


@app.route('/auth/google')
def google_auth():
    """Initiate Google OAuth flow."""
    if not GOOGLE_CLIENT_ID:
        return jsonify({'error': 'Google OAuth not configured'}), 500
    
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
        token_response = requests.post(token_url, data=token_data)
        token_response.raise_for_status()
        tokens = token_response.json()
        access_token = tokens['access_token']
        
        # Get user info from Google
        user_info_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        headers = {'Authorization': f'Bearer {access_token}'}
        user_response = requests.get(user_info_url, headers=headers)
        user_response.raise_for_status()
        user_info = user_response.json()
        
        # Store or update user in database
        if supabase:
            # Check if user exists
            user_check = supabase.table('users').select('*').eq('google_id', user_info['id']).execute()
            
            if user_check.data:
                user = user_check.data[0]
                user_id = user['id']
            else:
                # Create new user
                new_user = supabase.table('users').insert({
                    'google_id': user_info['id'],
                    'email': user_info['email'],
                    'name': user_info.get('name'),
                    'picture_url': user_info.get('picture')
                }).execute()
                user_id = new_user.data[0]['id']
            
            # Store in session
            session['user_id'] = user_id
            session['user_email'] = user_info['email']
            session['user_name'] = user_info.get('name')
            session['user_picture'] = user_info.get('picture')
        
        # Redirect back to the page they came from or home
        redirect_url = request.args.get('redirect', '/')
        return redirect(redirect_url)
    except Exception as e:
        print(f"Error in Google OAuth callback: {e}")
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
        return jsonify({
            'authenticated': True,
            'user_id': session['user_id'],
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
        return jsonify([])
    
    try:
        user_id = session['user_id']
        
        # Get destinations where user is organizer
        created = supabase.table('destinations').select('*').eq('user_id', user_id).execute()
        
        # Get destinations where user is a participant
        participants = supabase.table('event_participants').select('event_id').eq('user_id', user_id).execute()
        event_ids = [p['event_id'] for p in participants.data] if participants.data else []
        
        # Get participant destinations
        participant_destinations = []
        if event_ids:
            participant_dest = supabase.table('destinations').select('*').in_('id', event_ids).execute()
            participant_destinations = participant_dest.data if participant_dest.data else []
        
        # Combine and deduplicate
        all_destinations = {}
        for dest in created.data:
            all_destinations[dest['id']] = {**dest, 'is_organizer': True}
        
        for dest in participant_destinations:
            if dest['id'] not in all_destinations:
                # Get participation type
                part = next((p for p in participants.data if p['event_id'] == dest['id']), None)
                all_destinations[dest['id']] = {
                    **dest,
                    'is_organizer': False,
                    'participation_type': part['participation_type'] if part else None
                }
        
        # Get organizer info for all destinations (both created and participant)
        for dest_id, dest in all_destinations.items():
            if dest.get('user_id'):
                organizer = supabase.table('users').select('name, email').eq('id', dest['user_id']).execute()
                if organizer.data:
                    dest['organizer_name'] = organizer.data[0].get('name') or organizer.data[0].get('email')
        
        # Convert to list and sort
        result = list(all_destinations.values())
        result.sort(key=lambda x: (x.get('scheduled_date', ''), x.get('scheduled_time', '')))
        
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching destinations: {e}")
        return jsonify([])


@app.route('/api/destinations/<int:destination_id>', methods=['GET'])
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
            organizer = supabase.table('users').select('name, email, picture_url').eq('id', destination['user_id']).execute()
            if organizer.data:
                destination['organizer'] = organizer.data[0]
        
        # Get all participants with user info
        participants_response = supabase.table('event_participants').select('*').eq('event_id', destination_id).execute()
        participants = participants_response.data if participants_response.data else []
        
        # Get user info for each participant
        for participant in participants:
            user_info = supabase.table('users').select('id, name, email, picture_url').eq('id', participant['user_id']).execute()
            if user_info.data:
                participant['user'] = user_info.data[0]
        
        destination['participants'] = participants
        
        # Separate joined and interested
        destination['joined'] = [p for p in participants if p['participation_type'] == 'joined']
        destination['interested'] = [p for p in participants if p['participation_type'] == 'interested']
        destination['joined_count'] = len(destination['joined'])
        destination['interested_count'] = len(destination['interested'])
        
        return jsonify(destination)
    except Exception as e:
        print(f"Error fetching destination: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/destinations', methods=['POST'])
@login_required
def save_destination():
    """Save a destination/event to Supabase."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        data = request.get_json()
        
        # Validate required fields (scheduled_time is optional)
        required_fields = ['place_name', 'latitude', 'longitude', 'scheduled_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Add user_id from session
        data['user_id'] = session['user_id']
        
        # If scheduled_time is not provided, set to None (all-day event)
        if 'scheduled_time' not in data or not data['scheduled_time']:
            data['scheduled_time'] = None
        
        # Set default status to 'active' if not provided
        if 'status' not in data:
            data['status'] = 'active'
        
        response = supabase.table('destinations').insert(data).execute()
        return jsonify(response.data)
    except Exception as e:
        print(f"Error saving destination: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/destinations/<int:destination_id>', methods=['DELETE'])
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


@app.route('/api/destinations/<int:destination_id>/cancel', methods=['PATCH'])
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


@app.route('/api/events/<int:event_id>/participate', methods=['POST'])
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
        
        return jsonify(response.data[0] if response.data else {})
    except Exception as e:
        print(f"Error participating in event: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<int:event_id>/participate', methods=['DELETE'])
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


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get user profile information."""
    if supabase is None:
        return jsonify({'error': 'Supabase not configured'}), 500
    
    try:
        user_response = supabase.table('users').select('id, google_id, email, name, picture_url, created_at').eq('id', user_id).execute()
        if not user_response.data:
            return jsonify({'error': 'User not found'}), 404
        
        user = user_response.data[0]
        # Don't expose google_id
        user.pop('google_id', None)
        
        return jsonify(user)
    except Exception as e:
        print(f"Error fetching user: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)
