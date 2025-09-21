import os
import logging
from flask import Flask, request, redirect, session, url_for, send_from_directory, jsonify
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration - Using your original variable names
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_ID_SECRET")  # Your original variable name
REDIRECT_URI = os.getenv("URI")                # Your original variable name
SCOPE = "playlist-modify-public playlist-modify-private user-top-read user-read-private"

# Validate required environment variables
if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI]):
    raise ValueError("Missing required environment variables: CLIENT_ID, CLIENT_SECRET, REDIRECT_URI")

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", CLIENT_SECRET)  # Use separate secret key
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Spotify OAuth setup
sp_oauth = SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    cache_path=None  # Don't cache to file for web apps
)

def get_spotify_client():
    """Get authenticated Spotify client from session token."""
    token_info = session.get('token_info')
    if not token_info:
        return None
    
    # Check if token needs refresh
    if sp_oauth.is_token_expired(token_info):
        try:
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
            session['token_info'] = token_info
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            session.pop('token_info', None)
            return None
    
    return Spotify(auth=token_info['access_token'])

# Routes for static files - Fixed the route conflict from your original code
@app.route("/static", defaults={"path": ""})
@app.route("/static/<path:path>")
def serve_frontend(path):
    """Serve React frontend files."""
    try:
        if path and os.path.exists(os.path.join("dist", path)):
            return send_from_directory("dist", path)
        return send_from_directory("dist", "index.html")
    except Exception as e:
        logger.error(f"Error serving frontend: {e}")
        return "Frontend not found", 404

# Main route - equivalent to your original index() function
@app.route('/')
def index():
    """Main page with login link or user info if authenticated."""
    sp = get_spotify_client()
    if sp:
        try:
            user = sp.current_user()
            return f'''
            <h1>Welcome {user.get('display_name', user['id'])}!</h1>
            <p><a href="/create_playlist">Create Playlist</a></p>
            <p><a href="/auth/logout">Logout</a></p>
            '''
        except:
            pass
    
    auth_url = sp_oauth.get_authorize_url()
    return f'<a href="{auth_url}">Login with Spotify</a>'

# Authentication routes
@app.route('/callback')  # Your original callback route, improved
def callback():
    """Handle Spotify OAuth callback."""
    try:
        code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            logger.error(f"OAuth error: {error}")
            return redirect('/?error=access_denied')
        
        if not code:
            logger.error("No authorization code received")
            return redirect('/?error=no_code')
        
        token_info = sp_oauth.get_access_token(code)
        session['token_info'] = token_info
        session.permanent = True
        
        # Redirect to create_playlist like your original code
        return redirect(url_for('create_playlist'))
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return redirect('/?error=callback_failed')

@app.route('/auth/logout')
def logout():
    """Clear session and logout user."""
    session.clear()
    return redirect('/')

@app.route('/auth/status')
def auth_status():
    """Check if user is authenticated."""
    sp = get_spotify_client()
    if sp:
        try:
            user = sp.current_user()
            return jsonify({
                "authenticated": True,
                "user": {
                    "id": user['id'],
                    "display_name": user.get('display_name'),
                    "email": user.get('email')
                }
            })
        except SpotifyException as e:
            logger.error(f"Spotify API error: {e}")
            session.pop('token_info', None)
    
    return jsonify({"authenticated": False})

# Playlist routes - Your original create_playlist route, improved
@app.route('/create_playlist')
def create_playlist():
    """Create a new playlist - matches your original function."""
    sp = get_spotify_client()
    if not sp:
        return redirect('/')
    
    try:
        # Get current user ID (same as your original)
        user_id = sp.current_user()['id']
        
        # Create playlist (same as your original)
        playlist = sp.user_playlist_create(
            user=user_id,
            name="My Personalized Playlist 🎶",
            public=False,
            description="Generated by Flask + Spotipy"
        )
        
        # Get recommendations (same as your original)
        recs = sp.recommendations(seed_genres=['pop'], limit=10)
        
        # Add tracks to playlist (same as your original)
        track_uris = [track['uri'] for track in recs['tracks']]
        sp.playlist_add_items(playlist['id'], track_uris)
        
        # Return success message with playlist link
        return f'''
        <h1>Playlist created! 🎉</h1>
        <p>Check your Spotify account: <a href="{playlist['external_urls']['spotify']}" target="_blank">{playlist['name']}</a></p>
        <p>Added {len(track_uris)} tracks</p>
        <p><a href="/">Back to Home</a></p>
        '''
        
    except SpotifyException as e:
        logger.error(f"Spotify API error in create_playlist: {e}")
        return f"<h1>Error creating playlist</h1><p>{str(e)}</p><p><a href='/'>Try Again</a></p>"
    except Exception as e:
        logger.error(f"Unexpected error in create_playlist: {e}")
        return f"<h1>Unexpected error</h1><p><a href='/'>Try Again</a></p>"

# Fixed your modify_playlist route to handle URL encoding issues
@app.route('/modify_playlist/<playlist_id>/<action>/<path:track_uri>')
def modify_playlist(playlist_id, action, track_uri):
    """Modify playlist - improved version of your original function."""
    sp = get_spotify_client()
    if not sp:
        return redirect('/')
    
    try:
        if action == "add":
            sp.playlist_add_items(playlist_id, [track_uri])
            return f"<h1>Success!</h1><p>Added {track_uri}</p><p><a href='/'>Back to Home</a></p>"
        elif action == "remove":
            sp.playlist_remove_all_occurrences_of_items(playlist_id, [track_uri])
            return f"<h1>Success!</h1><p>Removed {track_uri}</p><p><a href='/'>Back to Home</a></p>"
        else:
            return "<h1>Invalid action</h1><p>Use 'add' or 'remove'</p><p><a href='/'>Back to Home</a></p>"
            
    except SpotifyException as e:
        logger.error(f"Spotify API error in modify_playlist: {e}")
        return f"<h1>Error modifying playlist</h1><p>{str(e)}</p><p><a href='/'>Back to Home</a></p>"
    except Exception as e:
        logger.error(f"Unexpected error in modify_playlist: {e}")
        return f"<h1>Unexpected error</h1><p><a href='/'>Back to Home</a></p>"

@app.route('/api/user/playlists')
def get_user_playlists():
    """Get user's playlists."""
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        playlists = sp.current_user_playlists(limit=50)
        return jsonify({
            "playlists": [{
                "id": playlist['id'],
                "name": playlist['name'],
                "tracks": playlist['tracks']['total'],
                "public": playlist['public'],
                "url": playlist['external_urls']['spotify']
            } for playlist in playlists['items']]
        })
    except SpotifyException as e:
        logger.error(f"Spotify API error in get_user_playlists: {e}")
        return jsonify({"error": f"Spotify API error: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Unexpected error in get_user_playlists: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/search')
def search_tracks():
    """Search for tracks."""
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({"error": "No search query provided"}), 400
        
        results = sp.search(q=query, type='track', limit=20)
        tracks = [{
            "uri": track['uri'],
            "name": track['name'],
            "artists": [artist['name'] for artist in track['artists']],
            "album": track['album']['name'],
            "duration_ms": track['duration_ms'],
            "preview_url": track['preview_url']
        } for track in results['tracks']['items']]
        
        return jsonify({"tracks": tracks})
        
    except SpotifyException as e:
        logger.error(f"Spotify API error in search_tracks: {e}")
        return jsonify({"error": f"Spotify API error: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Unexpected error in search_tracks: {e}")
        return jsonify({"error": "Internal server error"}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':  # Fixed the syntax error from your original
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
