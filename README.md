# w3-hyperlocal

A web application built with Python Flask and Supabase, featuring an interactive map component that consumes places from the Google Places API. The app helps users discover local places, create events, and connect with others through event participation.

## Features

- **Interactive Map** with Google Maps integration
- **Google Places API** search and autocomplete
- **Time-based Recommendations** - Smart suggestions based on time of day and weather
- **Event Management** - Create, join, and manage events at local places
- **Google OAuth Authentication** - Secure user authentication
- **Event Participation** - Join or mark interest in events
- **Organizer Tools** - View participants and manage events
- **Calendar & List Views** - Organize your events by date
- **Supabase Backend** - Reliable database and API
- **Modern, Responsive UI** - Works on desktop and mobile

## Prerequisites

- Python 3.9 or higher
- A Google Cloud Platform account with:
  - Maps JavaScript API enabled
  - Places API enabled
  - OAuth 2.0 credentials configured
- A Supabase account and project

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
# Install Python dependencies
python3 -m pip install -r requirements.txt
# or
pip3 install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
# Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key

# Google Maps API
GOOGLE_MAPS_API_KEY=your_google_maps_api_key

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
GOOGLE_REDIRECT_URI=http://localhost:5001/auth/google/callback

# Flask Session Secret
FLASK_SECRET_KEY=your_random_secret_key_here
```

**Note:** Generate a random `FLASK_SECRET_KEY` (e.g., using `python3 -c "import secrets; print(secrets.token_hex(32))"`)

### 3. Set Up Supabase

1. Create a new Supabase project at [supabase.com](https://supabase.com)
2. Get your project URL and anon key from the project settings
3. Run the migration SQL file in your Supabase SQL editor:
   - Open `db/supabase_migration.sql` and execute it in your Supabase SQL editor
   - Or copy the SQL from the file and run it manually
   - The migration includes test data (optional - comment out if you don't want test data)

### 4. Configure Google Maps API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the following APIs:
   - Maps JavaScript API
   - Places API
4. Create an API key and restrict it to your domain (recommended)
5. Add the API key to your `.env` file as `GOOGLE_MAPS_API_KEY`

### 5. Configure Google OAuth

1. In Google Cloud Console, go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. Select **Web application** as the application type
4. Add authorized redirect URI: `http://localhost:5001/auth/google/callback`
   - For production, add your production URL as well
5. Copy the **Client ID** and **Client Secret** to your `.env` file
6. Configure OAuth consent screen:
   - Go to **APIs & Services** > **OAuth consent screen**
   - Choose **External** (for testing) or **Internal** (for Google Workspace)
   - Fill in required fields (App name, User support email, Developer contact)
   - Add scopes: `email`, `profile`, `openid`
   - Add test users if in testing mode

**Verify OAuth Configuration:**
```bash
python3 test_oauth.py
```

This script will check:
- All required environment variables are set
- Client ID format is valid
- Redirect URI is configured correctly
- Google Cloud Console checklist items

### 6. Run the Application

```bash
python3 run.py
# or
python3 -m app.app
```

The application will be available at `http://localhost:5001`

**Note:** The app runs on port 5001 to avoid conflicts with macOS AirPlay Receiver on port 5000.

#### Background Scheduler

The application includes a **background job scheduler** that runs automatically when you start the Flask app. The scheduler handles periodic tasks without any additional setup:

**Automatic Features:**
- **Event Status Updates**: Automatically updates event statuses from "active" to "past" when events have passed
- **Runs every 1 minute**: Continuously monitors all events in the database
- **Immediate catch-up**: On startup, immediately processes all existing past events
- **No manual intervention**: Works automatically in the background

**What happens when you start the app:**
1. The scheduler starts automatically
2. It immediately runs an initial check to update any existing past events
3. Then it runs every minute to catch newly past events
4. You'll see console messages indicating when jobs run and how many events were updated

**Console Output Example:**
```
Running initial event status update to catch up on past events...
Initial update: Updated 5 event(s) to past status
Background jobs initialized: EventStatusUpdater scheduled to run every 1 minute
```

**Modular Jobs Framework:**
The background jobs system is designed to be modular and extensible. New jobs can be easily added by:
1. Creating a new job class in `app/jobs/` that extends `BaseJob`
2. Implementing the `execute()` method with your job logic
3. Registering the job in `init_jobs()` function in `app/app.py`

**Note:** The scheduler runs in the same process as the Flask app. For production deployments, consider running the scheduler as a separate service or using a process manager like Supervisor or systemd.

## Project Structure

```
w3-hyperlocal/
├── app/                   # Application code
│   ├── app.py            # Flask application and routes
│   ├── __init__.py       # Package initialization
│   ├── jobs/             # Background jobs module
│   │   ├── __init__.py   # Jobs package initialization
│   │   ├── base_job.py   # Base class for all background jobs
│   │   └── event_status_updater.py  # Job to update event statuses
│   └── templates/        # HTML templates
│       ├── index.html    # Main page with map component
│       └── event_details.html  # Event details page for URL access
├── db/                    # Database files
│   └── supabase_migration.sql  # Supabase migration script with test data
├── run.py                 # Application entry point
├── requirements.txt       # Python dependencies
├── test_oauth.py         # OAuth configuration test script
├── .env                   # Environment variables (not in git)
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

## Data Model

### Users Table
Stores Google OAuth user information:
- `id` (BIGSERIAL PRIMARY KEY)
- `google_id` (TEXT UNIQUE) - Google OAuth user ID
- `email` (TEXT) - User email
- `name` (TEXT) - User display name
- `picture_url` (TEXT) - Profile picture URL
- `created_at` (TIMESTAMP) - Account creation date

### Places Table
Stores place information (optional, for caching):
- `id` (BIGSERIAL PRIMARY KEY)
- `name` (TEXT) - Place name
- `address` (TEXT) - Full address
- `latitude` (DOUBLE PRECISION)
- `longitude` (DOUBLE PRECISION)
- `rating` (DOUBLE PRECISION) - Google Places rating
- `place_id` (TEXT UNIQUE) - Google Places ID
- `created_at` (TIMESTAMP)

### Destinations Table (Events)
Stores user-created events:
- `id` (BIGSERIAL PRIMARY KEY)
- `user_id` (BIGINT) - Foreign key to users (organizer)
- `place_name` (TEXT) - Name of the place
- `address` (TEXT) - Full address
- `latitude` (DOUBLE PRECISION)
- `longitude` (DOUBLE PRECISION)
- `place_id` (TEXT) - Google Places ID
- `place_type` (TEXT) - Type of place (e.g., "Restaurant", "Park")
- `rating` (DOUBLE PRECISION) - Place rating
- `scheduled_date` (DATE) - Event date
- `scheduled_time` (TIME) - Event time (optional, NULL for all-day)
- `status` (TEXT) - 'active', 'past', or 'cancelled'
- `created_at` (TIMESTAMP)

### Event Participants Table
Tracks user participation in events:
- `id` (BIGSERIAL PRIMARY KEY)
- `event_id` (BIGINT) - Foreign key to destinations
- `user_id` (BIGINT) - Foreign key to users
- `participation_type` (TEXT) - 'joined' or 'interested'
- `created_at` (TIMESTAMP)
- Unique constraint on (event_id, user_id) - prevents duplicate participation

## Request Flow

### Authentication Flow
1. User clicks "Sign in with Google"
2. Frontend redirects to `/auth/google`
3. Backend redirects to Google OAuth consent screen
4. User authorizes the application
5. Google redirects to `/auth/google/callback` with authorization code
6. Backend exchanges code for access token
7. Backend fetches user info from Google
8. Backend creates/updates user in database
9. Backend stores user info in Flask session
10. User is redirected back to the application (authenticated)

### Event Creation Flow
1. User searches for a place or clicks a recommendation marker
2. User clicks "Go here" button on a place marker
3. Side panel opens with place details
4. User fills in event date and optional time
5. System validates time against business hours (if available)
6. User submits form
7. Frontend sends POST to `/api/destinations` with event data
8. Backend validates and saves event to database
9. Event appears in "My Destinations" list and calendar

### Event Participation Flow
1. User receives event URL (e.g., `http://localhost:5001/event/123`)
2. If unauthenticated, user sees event details with sign-in prompt
3. If authenticated, user sees "Join" and "Interested" buttons
4. User clicks "Join" or "Interested"
5. Frontend sends POST to `/api/events/<id>/participate`
6. Backend creates/updates participation record
7. Event appears in user's "My Destinations" with participation badge
8. Organizer can see user in participants list

### Time-Based Recommendations Flow
1. User loads the home page
2. Browser requests geolocation
3. Frontend fetches current weather
4. System determines time of day and weather conditions
5. Frontend calls `loadTimeBasedRecommendations()`
6. System searches Google Places API for:
   - Relevant place types (cafe, restaurant, park, etc.)
   - Within 1 mile (walking distance)
   - Currently open places
7. System displays 3 unique places as green markers
8. Headline appears in search bar explaining recommendations
9. User can click markers to see details and create events

## API Endpoints

### Public Endpoints
- `GET /` - Renders the main page with the map
- `GET /event/<id>` - Event details page (for URL-based access)
- `GET /api/auth/status` - Get current authentication status
- `GET /api/destinations/<id>` - Get event details (public, includes organizer info)

### Authentication Endpoints
- `GET /auth/google` - Initiate Google OAuth login
- `GET /auth/google/callback` - OAuth callback handler
- `GET /auth/logout` - Logout user

### Protected Endpoints (require authentication)
- `GET /api/destinations` - Get user's destinations (created, joined, or interested)
- `POST /api/destinations` - Create a new event
- `DELETE /api/destinations/<id>` - Delete an event (organizer only)
- `PATCH /api/destinations/<id>/cancel` - Cancel an event (organizer only)
- `POST /api/events/<id>/participate` - Join or mark interest in an event
- `DELETE /api/events/<id>/participate` - Remove participation from an event
- `GET /api/users/<id>` - Get user profile information

## User Scenarios

### Scenario 1: Creating Your First Event

**As an unauthenticated user:**
1. You open the app and see the map with time-based recommendations
2. You see 3 green markers for places you can walk to now
3. You click on a coffee shop marker
4. You see place details but need to sign in to create an event
5. You click "Sign in with Google" and authenticate
6. You return to the map and click the coffee shop marker again
7. You click "Go here" and the side panel opens
8. You set the date for tomorrow at 2:00 PM
9. The system validates the time against business hours
10. You click "Create event"
11. The event is saved and appears in "My Destinations"

**As an authenticated user:**
1. You search for "pizza restaurant" in the search bar
2. You select a restaurant from the results
3. A marker appears on the map with place details
4. You click "Go here" and set event details
5. You optionally add invite emails
6. You create the event

### Scenario 2: Joining an Event

**Receiving an invitation:**
1. You receive an email with an event link: `http://localhost:5001/event/123`
2. You click the link and see event details
3. If not signed in, you see a sign-in prompt
4. After signing in, you see "Join" and "Interested" buttons
5. You click "Join" to confirm attendance
6. The event appears in your "My Destinations" with a "Joined" badge

**Discovering an event:**
1. You're browsing "My Destinations" and see an event you didn't create
2. The event shows the organizer's name
3. You click on the event to see details
4. You see you're marked as "Interested"
5. You click "Join" to confirm attendance
6. Your status changes from "Interested" to "Joined"

### Scenario 3: Managing Event Participants (Organizer)

**Viewing participants:**
1. You open "My Destinations" and click on an event you created
2. The Event View opens showing event details
3. You scroll down to see two sections:
   - "Confirmed Attendees" - People who clicked "Join"
   - "Interested" - People who marked interest but haven't joined
4. You see participant names and avatars

**Viewing participant profiles:**
1. In the Event View, you click on a participant's name
2. A User Profile side panel opens
3. You see the participant's name, email, profile picture, and member since date
4. You click the back arrow to return to the Event View

**Managing your event:**
1. As the organizer, you see additional options:
   - "Invite via email" - Share event link
   - "Cancel" - Cancel the event (if not past)
   - "Delete" - Permanently delete the event

### Scenario 4: Time-Based Recommendations

**Morning (8:00 AM):**
1. You open the app
2. The system detects it's morning
3. You see 3 green markers for breakfast/coffee places
4. The headline says: "☕ Three breakfast and coffee places you can walk to now"
5. All places are within 1 mile and currently open
6. You click a marker to see details and create an event

**Afternoon (3:00 PM, Sunny):**
1. You open the app
2. The system detects it's afternoon and sunny
3. You see 3 green markers for parks
4. The headline says: "🌳 Three parks you can walk to now"
5. You click a park marker and create an event for a weekend picnic

**Afternoon (3:00 PM, Cloudy):**
1. You open the app
2. The system detects it's afternoon but not sunny
3. You see 3 green markers for bookstores
4. The headline says: "📚 Three bookstores you can walk to now"
5. You explore bookstores and create a reading event

**Evening (8:00 PM):**
1. You open the app
2. The system detects it's evening
3. You see 3 green markers for bars
4. The headline says: "🍺 Three bars you can walk to now"
5. You click a bar marker and create an event for tonight

### Scenario 5: Calendar and List Views

**Using the Calendar View:**
1. You click "My Destinations" in the header
2. You switch to "Calendar" view
3. You see a monthly calendar with navigation arrows
4. Days with events are highlighted
5. The current day is highlighted in a different color
6. Past days are greyed out
7. You click on a day with events
8. The view scrolls to show a "Day View" below
9. You see all events for that day (active, past, cancelled)
10. Each event shows: name, type, organizer, time, and status
11. You click an event to see full details

**Using the List View:**
1. You're in "My Destinations" with "List" view active
2. Events are grouped by date with day separators
3. Events are sorted by what's happening next
4. Each event shows:
   - Place name with participation badge (if applicable)
   - Place type
   - Organizer name (or "You" if you're the organizer)
   - Time
   - Status badge (Active, Past, Cancelled)
5. You click an event to see full details

### Scenario 6: Event States and Status

**Active Event:**
1. You create an event for next week
2. It appears in "My Destinations" with "Active" status
3. You can cancel it, delete it, or invite more people
4. Participants can join or mark interest

**Past Event:**
1. An event date passes
2. The background scheduler automatically marks it as "Past" (runs every minute)
3. It appears in your list with "Past" status
4. You cannot cancel past events
5. You can still view details and delete if needed
6. The scheduler also catches up on all existing past events when the app starts

**Cancelled Event:**
1. As an organizer, you cancel an upcoming event
2. The status changes to "Cancelled"
3. It appears greyed out in lists
4. Participants can see it was cancelled
5. You can still delete it if needed

## Usage

### For Unauthenticated Users
1. Open the application in your browser
2. Use the search box to find places using Google Places Autocomplete
3. Click on a place in the search results to view it on the map
4. The map will show nearby places within a 4-mile radius
5. Click on markers to see place details
6. **Sign in required** to create events or view "My Destinations"
7. View time-based recommendations (3 places you can walk to now)

### For Authenticated Users
1. Click "Sign in with Google" to authenticate
2. Search for places and click "Go here" to create events
3. Set event date and time (filtered by business hours)
4. Invite people via email
5. View "My Destinations" to see:
   - Events you created
   - Events you joined
   - Events you're interested in
6. Click on events to see details and manage participation
7. Share event URLs to let others join or mark interest
8. As an organizer, view and manage participants

### Event Participation
- **Join**: Confirms you're attending (visible to organizer)
- **Interested**: Shows interest without confirming (visible to organizer)
- Organizers can see all participants and their status
- Participants can see organizer information

### Time-Based Recommendations
The app automatically shows 3 relevant places based on:
- **Time of day**: Morning (breakfast/coffee), Lunch (restaurants), Afternoon (parks or bookstores), Dinner (restaurants), Evening (bars)
- **Weather**: Sunny weather suggests parks, otherwise suggests bookstores
- **Distance**: Only places within 1 mile (walking distance)
- **Availability**: Only places that are currently open

Recommendations appear as green markers on the map with a headline explaining why they're suggested.

## Technologies Used

- **Flask 3.0.0** - Python web framework
- **Supabase** - Backend as a service (PostgreSQL database)
- **APScheduler 3.10.4** - Background job scheduling
- **Google Maps JavaScript API** - Map rendering
- **Google Places API** - Place search and details
- **Google OAuth 2.0** - User authentication
- **HTML/CSS/JavaScript** - Frontend
- **Python Requests** - HTTP client for OAuth flow

## Testing

### Test OAuth Configuration
```bash
python3 test_oauth.py
```

### Test Data
The migration script (`db/supabase_migration.sql`) includes optional test data:
- 3 test users
- 3 test places
- 4 test events (some future, one past)
- 2 test event participants

Comment out the test data section if you don't want it.

## License

TBD
