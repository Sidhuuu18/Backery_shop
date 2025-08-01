from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
import pandas as pd
import os
import random
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import json
from flask_pymongo import PyMongo
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from pymongo.errors import ConnectionFailure
from functools import wraps
import io # Import io for BytesIO
import xlsxwriter # Import xlsxwriter for pd.ExcelWriter engine
import base64 # Import base64 for encoding image data
import qrcode # Import the qrcode library

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_very_secret_and_complex_key_for_auth_project_12345')

# --- Configuration Paths ---
USERS_EXCEL_PATH = 'data/users.xlsx' # Still kept for historical context, but not actively used for new users

# --- Admin Credentials (HARDCODED - NOT FOR PRODUCTION) ---
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD_HASH = generate_password_hash('adminpass') # !!! CHANGE 'adminpass' TO A STRONG PASSWORD !!!

# --- MongoDB Configuration ---
# IMPORTANT: Verify this MONGO_URI is EXACTLY correct from your MongoDB Atlas "Connect" section.
# It should include your actual cluster hostname, username, and password.
app.config["MONGO_URI"] = "mongodb+srv://projectuse222:iCKPUrfJpMdrP7SQ@cluster0.frpspvc.mongodb.net/bakerydb?retryWrites=true&w=majority&appName=Cluster0"

mongo = None # Initialize mongo as None
try:
    print("DEBUG: Attempting to initialize PyMongo and connect to MongoDB...")
    mongo = PyMongo(app)
    # Attempt a simple operation to force a connection check
    mongo.db.command('ping')
    print("DEBUG: Successfully connected to MongoDB.")
    users_collection = mongo.db.users
    bakery_items_collection = mongo.db.bakery_items
    subscriptions_collection = mongo.db.subscriptions

    # Ensure TTL index for bakery_items (for image/video expiry)
    # This index will automatically delete documents after 'createdAt' + 10 days
    # It's good for temporary media links, but for permanent images, you'd use cloud storage.
    bakery_items_collection.create_index(
        "createdAt",
        expireAfterSeconds=timedelta(days=10).total_seconds()
    )
    print("DEBUG: Ensured TTL index on bakery_items.createdAt for 10-day expiry.")

except ConnectionFailure as e:
    print(f"CRITICAL ERROR: MongoDB Connection Failed! Check your MONGO_URI, network access, and database credentials. Error: {e}")
    # In a production app, you might want to gracefully handle this, e.g., by exiting or showing a maintenance page.
except Exception as e:
    print(f"CRITICAL ERROR: An unexpected error occurred during MongoDB initialization: {e}")
    
# If mongo is still None, subsequent operations will fail.
if mongo is None:
    print("WARNING: MongoDB not initialized. Database operations will fail.")


# --- Google OAuth Configuration ---
GOOGLE_CLIENT_ID = '845165118488-62dmooghnnjskg35b5u1b223c7tjfu49.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = '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'
GOOGLE_AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'
GOOGLE_REDIRECT_URI = 'http://127.0.0.1:5000/oauth/google/callback'
GOOGLE_SCOPES = ['openid', 'email', 'profile']

# --- Facebook OAuth Configuration (Replace with your actual credentials) ---
FACEBOOK_CLIENT_ID = 'YOUR_FACEBOOK_CLIENT_ID'
FACEBOOK_CLIENT_SECRET = 'YOUR_FACEBOOK_CLIENT_SECRET'
FACEBOOK_AUTHORIZATION_URL = 'https://www.facebook.com/v19.0/dialog/oauth'
FACEBOOK_TOKEN_URL = 'https://graph.facebook.com/v19.0/oauth/access_token'
FACEBOOK_USERINFO_URL = 'https://graph.facebook.com/v19.0/me?fields=id,name,email'
FACEBOOK_REDIRECT_URI = 'http://127.0.0.1:5000/oauth/facebook/callback'
FACEBOOK_SCOPES = ['email', 'public_profile']

# --- GitHub OAuth Configuration (Replace with your actual credentials) ---
GITHUB_CLIENT_ID = 'YOUR_GITHUB_CLIENT_ID'
GITHUB_CLIENT_SECRET = 'YOUR_GITHUB_CLIENT_SECRET'
GITHUB_AUTHORIZATION_URL = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'
GITHUB_USERINFO_URL = 'https://api.github.com/user'
GITHUB_REDIRECT_URI = 'http://127.0.0.1:5000/oauth/github/callback'
GITHUB_SCOPES = ['user:email']

# --- Helper Functions for Excel User Data (Kept for compatibility, but not actively used for new users) ---
def load_users_from_excel():
    """Loads user data from users.xlsx. Creates an empty DataFrame if file doesn't exist."""
    if os.path.exists(USERS_EXCEL_PATH):
        try:
            print(f"DEBUG: Attempting to load existing users from {USERS_EXCEL_PATH}")
            return pd.read_excel(USERS_EXCEL_PATH)
        except Exception as e:
            print(f"ERROR: Failed to load users.xlsx: {e}")
            flash(f'Error loading user data: {e}', 'danger')
            return pd.DataFrame(columns=['Username', 'Email', 'Password Hash', 'Login Type', 'Social ID'])
    print(f"DEBUG: {USERS_EXCEL_PATH} does not exist. Initializing new DataFrame.")
    return pd.DataFrame(columns=['Username', 'Email', 'Password Hash', 'Login Type', 'Social ID'])

def save_users_to_excel(df):
    """Saves the entire DataFrame to users.xlsx."""
    print(f"DEBUG: Attempting to save DataFrame to {USERS_EXCEL_PATH}")
    try:
        df.to_excel(USERS_EXCEL_PATH, index=False)
        print(f"DEBUG: Successfully saved users to {USERS_EXCEL_PATH}")
    except Exception as e:
            print(f"ERROR: Failed to save users.xlsx: {e}")
            flash(f'Error saving user data: {e}', 'danger')

def create_data_dir_and_init_excel():
    """Ensures the data directory exists and initializes users.xlsx if it's new."""
    data_dir = os.path.dirname(USERS_EXCEL_PATH)
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir, exist_ok=True)
            print(f"DEBUG: Created data directory: {data_dir}")
        except OSError as e:
            print(f"CRITICAL ERROR: Could not create data directory {data_dir}: {e}")
            flash(f"Critical error: Could not create data directory at {data_dir}. Check permissions.", 'danger')

    if not os.path.exists(USERS_EXCEL_PATH):
        try:
            empty_df = pd.DataFrame(columns=['Username', 'Email', 'Password Hash', 'Login Type', 'Social ID'])
            empty_df.to_excel(USERS_EXCEL_PATH, index=False)
            print(f"DEBUG: Initialized empty users.xlsx at {USERS_EXCEL_PATH}")
        except Exception as e:
            print(f"CRITICAL ERROR: Could not initialize empty users.xlsx: {e}")
            flash(f"Critical error: Could not initialize users.xlsx at {USERS_EXCEL_PATH}. Check permissions.", 'danger')

# --- Admin Helper ---
def is_admin_logged_in():
    """Checks if an admin is logged into the session."""
    # Check if 'admin_logged_in' flag is explicitly set in session (for both hardcoded and DB admins)
    if session.get('admin_logged_in', False):
        return True
    # If not, and a general user is logged in, check if that user is marked as admin in MongoDB
    # This covers cases where a DB admin logs in via regular login (though they should use admin_login)
    if session.get('logged_in') and session.get('user_id') and mongo is not None:
        try:
            user_id_obj = ObjectId(session['user_id'])
            user = users_collection.find_one({"_id": user_id_obj})
            if user and user.get('is_admin'):
                session['is_admin'] = True # Ensure session reflects DB status
                session['admin_logged_in'] = True # Set admin_logged_in for consistency
                return True
        except Exception as e:
            print(f"ERROR: Failed to check admin status from DB: {e}")
            return False # Assume not admin on error
    return False

# --- Login Required Decorator (for general user access) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            flash('You need to be logged in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Admin Login Required Decorator (for admin-specific access) ---
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin_logged_in():
            flash('You must be logged in as an administrator to access this page.', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/')
def index():
    # If not logged in, show the home page with login/register links
    if 'logged_in' not in session or not session['logged_in']:
        return render_template('home.html')
    # If logged in, redirect to the items page
    return redirect(url_for('items_page'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    print("DEBUG: Entered /register route.")
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        print("ERROR: Register route: MongoDB not connected.")
        return render_template('register.html', errors={'general': 'Database not connected.'})

    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()

        print(f"DEBUG: Register POST request received for username: '{username}', email: '{email}'")

        errors = {}
        if not username:
            errors['username'] = 'Username is mandatory.'
        if not email:
            errors['email'] = 'Email is mandatory.'
        elif '@' not in email or '.' not in email:
            errors['email'] = 'Invalid email format.'
        if not password:
            errors['password'] = 'Password is mandatory.'
        elif len(password) < 6:
            errors['password'] = 'Password must be at least 6 characters long.'
        if password != confirm_password:
            errors['confirm_password'] = 'Passwords do not match.'
        if not full_name:
            errors['full_name'] = 'Full Name is mandatory.'

        # Check for existing username or email, case-insensitive
        existing_user = users_collection.find_one({
            "$or": [{"username": username.lower()}, {"email": email.lower()}]
        })
        if existing_user:
            errors['general'] = 'User with that username or email already exists.'
            print(f"DEBUG: Registration attempt failed: Username '{username}' or email '{email}' already exists in DB.")


        if errors:
            print(f"DEBUG: Registration failed due to validation errors: {errors}")
            return render_template('register.html', errors=errors, prev_username=username, prev_email=email, prev_full_name=full_name, prev_phone=phone)
        else:
            hashed_password = generate_password_hash(password)
            
            new_user = {
                'username': username.lower(), # Store username as lowercase for consistent lookup
                'email': email.lower(),       # Store email as lowercase for consistent lookup
                'password_hash': hashed_password,
                'full_name': full_name,
                'phone': phone,
                'login_type': 'Traditional',
                'social_id': None,
                'is_admin': False,
                'created_at': datetime.utcnow()
            }
            print(f"DEBUG: Attempting to insert new user into MongoDB: {new_user['username']}, {new_user['email']}")
            try:
                result = users_collection.insert_one(new_user)
                if result.inserted_id:
                    flash('Registration successful! Please log in.', 'success')
                    print(f"DEBUG: User '{username}' registered successfully with ID: {result.inserted_id}. Redirecting to login.")
                    return redirect(url_for('login'))
                else:
                    # This case should ideally not be hit with insert_one if no exception, but good for robustness
                    flash('An unexpected error occurred during registration. Please try again.', 'danger')
                    print(f"ERROR: MongoDB insertion failed for new user '{username}': No inserted_id returned from insert_one.")
                    return render_template('register.html', errors={'general': 'Database error during registration.'}, prev_username=username, prev_email=email, prev_full_name=full_name, prev_phone=phone)
            except Exception as e:
                flash(f'An error occurred during registration: {e}', 'danger')
                print(f"CRITICAL ERROR: MongoDB insertion exception for new user '{username}': {e}")
                return render_template('register.html', errors={'general': 'Database error during registration.'}, prev_username=username, prev_email=email, prev_full_name=full_name, prev_phone=phone)

    print("DEBUG: Rendering /register GET request.")
    return render_template('register.html', errors={}, prev_username='', prev_email='', prev_full_name='', prev_phone='')

@app.route('/login', methods=['GET', 'POST'])
def login():
    print("DEBUG: Entered /login route.")
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        print("ERROR: Login route: MongoDB not connected.")
        return render_template('login.html', errors={'general': 'Database not connected.'})

    if 'logged_in' in session and session['logged_in']:
        print(f"DEBUG: User '{session.get('user_name', 'N/A')}' already logged in. Redirecting to items page.")
        return redirect(url_for('items_page'))

    if request.method == 'POST':
        identifier = request.form['identifier'].strip()
        password = request.form['password']
        print(f"DEBUG: Login POST request received for identifier: '{identifier}'")

        user = users_collection.find_one({
            "$or": [{"username": identifier.lower()}, {"email": identifier.lower()}],
            "login_type": "Traditional"
        })

        if user:
            print(f"DEBUG: Found user in DB: {user['username']} (ID: {user['_id']}). Checking password.")
            if check_password_hash(user['password_hash'], password):
                session['logged_in'] = True
                session['user_id'] = str(user['_id'])
                session['user_name'] = user['username']
                session['user_email'] = user['email']
                session['login_type'] = user['login_type']
                session['is_admin'] = user.get('is_admin', False) # Ensure admin status is loaded
                flash(f'Welcome back, {session["user_name"]}! You are now logged in.', 'success')
                print(f"DEBUG: User '{identifier}' logged in successfully. Redirecting to items page.")
                return redirect(url_for('items_page')) # Redirect to items page after login
            else:
                flash('Invalid credentials. Please check your password.', 'danger')
                print(f"DEBUG: Login failed for '{identifier}': Invalid password.")
        else:
            flash('No traditional account found with that username or email, or invalid credentials.', 'danger')
            print(f"DEBUG: Login failed for '{identifier}': No traditional account found with traditional login type.")

    print("DEBUG: Rendering /login GET request.")
    return render_template('login.html', errors={})

@app.route('/logout')
@login_required # Logout also requires being logged in to execute
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    print("DEBUG: User logged out.")
    return redirect(url_for('login'))

# --- Social Login Routes ---
# OAuth callbacks do not need login_required as they handle initial login
@app.route('/oauth/google')
def oauth_google():
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return redirect(url_for('login'))

    auth_url = (
        f"{GOOGLE_AUTHORIZATION_URL}?"
        f"response_type=code&"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        f"scope={' '.join(GOOGLE_SCOPES)}&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    print(f"DEBUG: Redirecting to Google OAuth: {auth_url}")
    return redirect(auth_url)

@app.route('/oauth/google/callback')
def oauth_google_callback():
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return redirect(url_for('login'))

    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        flash(f"Google login failed: {error}", 'danger')
        print(f"ERROR: Google OAuth callback error: {error}")
        return redirect(url_for('login'))

    if not code:
        flash("Google login failed: No authorization code received.", 'danger')
        print("ERROR: Google OAuth callback: No authorization code.")
        return redirect(url_for('login'))

    token_payload = {
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    print("DEBUG: Exchanging Google authorization code for token...")
    try:
        token_response = requests.post(GOOGLE_TOKEN_URL, data=token_payload)
        token_response.raise_for_status()
        token_data = token_response.json()
        print("DEBUG: Google token exchange successful.")
    except requests.exceptions.RequestException as e:
        flash(f"Google token exchange failed: {e}", 'danger')
        print(f"ERROR: Google token exchange failed: {e}")
        return redirect(url_for('login'))

    access_token = token_data.get('access_token')
    if not access_token:
        flash("Google token exchange failed: No access token.", 'danger')
        print("ERROR: Google token exchange: No access token received.")
        return redirect(url_for('login'))

    print("DEBUG: Fetching Google user info...")
    try:
        userinfo_response = requests.get(GOOGLE_USERINFO_URL, headers={'Authorization': f'Bearer {access_token}'})
        userinfo_response.raise_for_status()
        user_info = userinfo_response.json()
        print(f"DEBUG: Google user info received: {user_info.get('email')}")
    except requests.exceptions.RequestException as e:
        flash(f"Failed to fetch Google user info: {e}", 'danger')
        print(f"ERROR: Failed to fetch Google user info: {e}")
        return redirect(url_for('login'))

    google_email = user_info.get('email')
    google_name = user_info.get('name')
    google_id = user_info.get('sub')

    if not google_email or not google_id:
        flash("Google login failed: Could not retrieve essential user info (email/ID).", 'danger')
        print("ERROR: Google login: Missing email or ID in user info.")
        return redirect(url_for('login'))

    user = users_collection.find_one({"social_id": google_id, "login_type": "Google"})

    if not user:
        print(f"DEBUG: Registering new Google social user: {google_email}")
        new_user = {
            'username': google_name.lower() if google_name else google_email.split('@')[0].lower(),
            'email': google_email.lower(),
            'password_hash': None, # No password for social logins
            'full_name': google_name,
            'phone': None,
            'login_type': 'Google',
            'social_id': google_id,
            'is_admin': False,
            'created_at': datetime.utcnow()
        }
        users_collection.insert_one(new_user)
        flash(f'Welcome, {google_name or google_email}! Your Google account has been linked.', 'success')
    else:
        print(f"DEBUG: Existing Google social user logged in: {google_email}")
        flash(f'Welcome back, {google_name or google_email}! Logged in with Google.', 'success')

    session['logged_in'] = True
    session['user_id'] = str(user['_id']) if user else str(new_user['_id'])
    session['user_name'] = google_name or google_email.split('@')[0]
    session['user_email'] = google_email
    session['login_type'] = 'Google'
    session['is_admin'] = user.get('is_admin', False) if user else False
    return redirect(url_for('items_page')) # Redirect to items page after social login

@app.route('/oauth/facebook')
def oauth_facebook():
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return redirect(url_for('login'))

    auth_url = (
        f"{FACEBOOK_AUTHORIZATION_URL}?"
        f"client_id={FACEBOOK_CLIENT_ID}&"
        f"redirect_uri={FACEBOOK_REDIRECT_URI}&"
        f"scope={','.join(FACEBOOK_SCOPES)}"
    )
    print(f"DEBUG: Redirecting to Facebook OAuth: {auth_url}")
    return redirect(auth_url)

@app.route('/oauth/facebook/callback')
def oauth_facebook_callback():
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return redirect(url_for('login'))

    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        flash(f"Facebook login failed: {error}", 'danger')
        print(f"ERROR: Facebook OAuth callback error: {error}")
        return redirect(url_for('login'))

    if not code:
        flash("Facebook login failed: No authorization code received.", 'danger')
        print("ERROR: Facebook OAuth callback: No authorization code.")
        return redirect(url_for('login'))

    token_payload = {
        'code': code,
        'client_id': FACEBOOK_CLIENT_ID,
        'client_secret': FACEBOOK_CLIENT_SECRET,
        'redirect_uri': FACEBOOK_REDIRECT_URI
    }
    print("DEBUG: Exchanging Facebook authorization code for token...")
    try:
        token_response = requests.get(FACEBOOK_TOKEN_URL, params=token_payload)
        token_response.raise_for_status()
        token_data = token_response.json()
        print("DEBUG: Facebook token exchange successful.")
    except requests.exceptions.RequestException as e:
        flash(f"Facebook token exchange failed: {e}", 'danger')
        print(f"ERROR: Facebook token exchange failed: {e}")
        return redirect(url_for('login'))

    access_token = token_data.get('access_token')
    if not access_token:
        flash("Facebook token exchange failed: No access token.", 'danger')
        print("ERROR: Facebook token exchange: No access token received.")
        return redirect(url_for('login'))

    print("DEBUG: Fetching Facebook user info...")
    try:
        userinfo_response = requests.get(FACEBOOK_USERINFO_URL, params={'access_token': access_token})
        userinfo_response.raise_for_status()
        user_info = userinfo_response.json()
        print(f"DEBUG: Facebook user info received: {user_info.get('email')}")
    except requests.exceptions.RequestException as e:
        flash(f"Failed to fetch Facebook user info: {e}", 'danger')
        print(f"ERROR: Failed to fetch Facebook user info: {e}")
        return redirect(url_for('login'))

    facebook_email = user_info.get('email')
    facebook_name = user_info.get('name')
    facebook_id = user_info.get('id')

    if not facebook_email or not facebook_id:
        flash("Facebook login failed: Could not retrieve essential user info (email/ID).", 'danger')
        print("ERROR: Facebook login: Missing email or ID in user info.")
        return redirect(url_for('login'))

    user = users_collection.find_one({"social_id": facebook_id, "login_type": "Facebook"})

    if not user:
        print(f"DEBUG: Registering new Facebook social user: {facebook_email}")
        new_user = {
            'username': facebook_name.lower() if facebook_name else facebook_email.split('@')[0].lower(),
            'email': facebook_email.lower(),
            'password_hash': None,
            'full_name': facebook_name,
            'phone': None,
            'login_type': 'Facebook',
            'social_id': facebook_id,
            'is_admin': False,
            'created_at': datetime.utcnow()
        }
        users_collection.insert_one(new_user)
        flash(f'Welcome, {facebook_name or facebook_email}! Your Facebook account has been linked.', 'success')
    else:
        print(f"DEBUG: Existing Facebook social user logged in: {facebook_email}")
        flash(f'Welcome back, {facebook_name or facebook_email}! Logged in with Facebook.', 'success')

    session['logged_in'] = True
    session['user_id'] = str(user['_id']) if user else str(new_user['_id'])
    session['user_name'] = facebook_name or facebook_email.split('@')[0]
    session['user_email'] = facebook_email
    session['login_type'] = 'Facebook'
    session['is_admin'] = user.get('is_admin', False) if user else False
    return redirect(url_for('items_page')) # Redirect to items page after social login

@app.route('/oauth/github')
def oauth_github():
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return redirect(url_for('login'))

    auth_url = (
        f"{GITHUB_AUTHORIZATION_URL}?"
        f"client_id={GITHUB_CLIENT_ID}&"
        f"redirect_uri={GITHUB_REDIRECT_URI}&"
        f"scope={','.join(GITHUB_SCOPES)}"
    )
    print(f"DEBUG: Redirecting to GitHub OAuth: {auth_url}")
    return redirect(auth_url)

@app.route('/oauth/github/callback')
def oauth_github_callback():
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return redirect(url_for('login'))

    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        flash(f"GitHub login failed: {error}", 'danger')
        print(f"ERROR: GitHub OAuth callback error: {error}")
        return redirect(url_for('login'))

    if not code:
        flash("GitHub login failed: No authorization code received.", 'danger')
        print("ERROR: GitHub OAuth callback: No authorization code.")
        return redirect(url_for('login'))

    token_payload = {
        'code': code,
        'client_id': GITHUB_CLIENT_ID,
        'client_secret': GITHUB_CLIENT_SECRET,
        'redirect_uri': GITHUB_REDIRECT_URI
    }
    print("DEBUG: Exchanging GitHub authorization code for token...")
    try:
        token_response = requests.post(GITHUB_TOKEN_URL, json=token_payload, headers={'Accept': 'application/json'})
        token_response.raise_for_status()
        token_data = token_response.json()
        print("DEBUG: GitHub token exchange successful.")
    except requests.exceptions.RequestException as e:
        flash(f"GitHub token exchange failed: {e}", 'danger')
        print(f"ERROR: GitHub token exchange failed: {e}")
        return redirect(url_for('login'))

    access_token = token_data.get('access_token')
    if not access_token:
        flash("GitHub token exchange failed: No access token.", 'danger')
        print("ERROR: GitHub token exchange: No access token received.")
        return redirect(url_for('login'))

    print("DEBUG: Fetching GitHub user info...")
    try:
        userinfo_response = requests.get(GITHUB_USERINFO_URL, headers={'Authorization': f'Bearer {access_token}'})
        userinfo_response.raise_for_status()
        user_info = userinfo_response.json()
        print(f"DEBUG: GitHub user info received: {user_info.get('email') or user_info.get('login')}")
    except requests.exceptions.RequestException as e:
        flash(f"Failed to fetch GitHub user info: {e}", 'danger')
        print(f"ERROR: Failed to fetch GitHub user info: {e}")
        return redirect(url_for('login'))

    github_email = user_info.get('email')
    github_name = user_info.get('name') or user_info.get('login')
    github_id = str(user_info.get('id'))

    if not github_email:
        print("DEBUG: GitHub email not directly available, trying public emails...")
        try:
            emails_response = requests.get(f"{GITHUB_USERINFO_URL}/emails", headers={'Authorization': f'Bearer {access_token}'})
            emails_response.raise_for_status()
            emails_data = emails_response.json()
            for email_entry in emails_data:
                if email_entry.get('primary') and email_entry.get('verified'):
                    github_email = email_entry.get('email')
                    print(f"DEBUG: Retrieved primary verified GitHub email: {github_email}")
                    break
        except requests.exceptions.RequestException as e:
            print(f"WARNING: Could not fetch GitHub emails: {e}")
            pass

    if not github_id:
        flash("GitHub login failed: Could not retrieve user ID.", 'danger')
        print("ERROR: GitHub login: Missing ID in user info.")
        return redirect(url_for('login'))

    user = users_collection.find_one({"social_id": github_id, "login_type": "GitHub"})

    if not user:
        print(f"DEBUG: Registering new GitHub social user: {github_email}")
        new_user = {
            'username': github_name.lower(),
            'email': github_email.lower() if github_email else f"{github_id}@github.com",
            'password_hash': None,
            'full_name': github_name,
            'phone': None,
            'login_type': 'GitHub',
            'social_id': github_id,
            'is_admin': False,
            'created_at': datetime.utcnow()
        }
        users_collection.insert_one(new_user)
        flash(f'Welcome, {github_name}! Your GitHub account has been linked.', 'success')
    else:
        print(f"DEBUG: Existing GitHub social user logged in: {github_email}")
        flash(f'Welcome back, {github_name}! Logged in with GitHub.', 'success')

    session['logged_in'] = True
    session['user_id'] = str(user['_id']) if user else str(new_user['_id'])
    session['user_name'] = github_name
    session['user_email'] = github_email or f"{github_id}@github.com"
    session['login_type'] = 'GitHub'
    session['is_admin'] = user.get('is_admin', False) if user else False
    return redirect(url_for('items_page')) # Redirect to items page after social login

# --- Admin Panel Routes ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # Admin login page should be accessible without prior general user login
    if is_admin_logged_in(): # Check if admin is already logged in
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check against hardcoded admin credentials first
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            session['is_admin'] = True # Explicitly mark as admin in session
            # Also set general login session for consistency for other parts of the app
            session['logged_in'] = True
            session['user_id'] = "admin_hardcoded_id" # Unique ID for hardcoded admin
            session['user_name'] = ADMIN_USERNAME
            session['user_email'] = f'{ADMIN_USERNAME}@bakery.com'
            session['login_type'] = 'Admin (Hardcoded)'
            flash('Admin login successful!', 'success')
            print("DEBUG: Admin logged in via hardcoded credentials.")
            return redirect(url_for('admin_dashboard'))
        else:
            # If hardcoded fails, check against MongoDB admin user
            if mongo is not None:
                user = users_collection.find_one({"username": username.lower(), "is_admin": True})
                if user and check_password_hash(user['password_hash'], password):
                    session['logged_in'] = True # Log them in as a regular user too
                    session['user_id'] = str(user['_id'])
                    session['user_name'] = user['username']
                    session['user_email'] = user['email']
                    session['login_type'] = user['login_type']
                    session['admin_logged_in'] = True # Set this flag for admin access
                    session['is_admin'] = True # Set this flag for admin access
                    flash('Admin login successful!', 'success')
                    print(f"DEBUG: Admin logged in via MongoDB user: {username}.")
                    return redirect(url_for('admin_dashboard'))
            
            flash('Invalid admin credentials.', 'danger')
            print("DEBUG: Admin login failed: Invalid credentials.")
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@admin_login_required # Only accessible by logged-in administrators
def admin_dashboard():
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return redirect(url_for('admin_login'))
    
    users_cursor = users_collection.find({})
    users_data = []
    for user in users_cursor:
        user['_id'] = str(user['_id'])
        user['password_hash'] = 'N/A (Social Login)' if user['login_type'] != 'Traditional' else 'HASHED (Not Decryptable)'
        users_data.append(user)
    
    bakery_items_cursor = bakery_items_collection.find({})
    bakery_items_data = []
    for item in bakery_items_cursor:
        item['_id'] = str(item['_id'])
        bakery_items_data.append(item)

    columns = ['_id', 'username', 'email', 'full_name', 'phone', 'login_type', 'social_id', 'is_admin', 'created_at', 'password_hash']

    print("DEBUG: Admin dashboard accessed. Displaying user and item data from MongoDB.")
    return render_template('admin_dashboard.html', users=users_data, user_columns=columns, bakery_items=bakery_items_data)

@app.route('/admin/download_users_data')
@admin_login_required # Only accessible by logged-in administrators
def download_users_data():
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return redirect(url_for('admin_login'))
    
    users_cursor = users_collection.find({})
    users_list = []
    for user in users_cursor:
        user['_id'] = str(user['_id'])
        user['password_hash'] = 'N/A (Social Login)' if user['login_type'] != 'Traditional' else 'HASHED'
        users_list.append(user)

    if users_list:
        df = pd.DataFrame(users_list)
        df = df[['_id', 'username', 'email', 'full_name', 'phone', 'login_type', 'social_id', 'is_admin', 'created_at', 'password_hash']]
        
        # Use a BytesIO buffer instead of a temporary file on disk
        # This keeps the file in memory, avoiding Windows permission issues
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Users')
        writer.close() # Important: Close the writer to save content to BytesIO
        output.seek(0) # Go to the beginning of the buffer

        print(f"DEBUG: Admin downloading users data from memory.")
        return send_file(output, as_attachment=True, download_name='users_data.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        flash("No user data found in MongoDB to download.", 'warning')
        print("WARNING: Admin tried to download, but no user data in MongoDB.")
        return redirect(url_for('admin_dashboard'))


@app.route('/admin/logout')
@admin_login_required # Only accessible by logged-in administrators
def admin_logout():
    # Clear admin-specific session flags
    session.pop('admin_logged_in', None)
    session.pop('is_admin', None)
    
    # If the general user session was set by the hardcoded admin login, clear it too
    if session.get('user_id') == "admin_hardcoded_id":
        session.clear() # Clear all session for hardcoded admin
    else: # If a MongoDB admin user was logged in, just clear admin flags, keep general user session
        # (This allows them to still be logged in as a regular user if they wish)
        session.pop('logged_in', None)
        session.pop('user_id', None)
        session.pop('user_name', None)
        session.pop('user_email', None)
        session.pop('login_type', None)
    
    flash('Admin logged out.', 'info')
    print("DEBUG: Admin logged out.")
    return redirect(url_for('admin_login'))

@app.route('/admin/add_item', methods=['GET', 'POST'])
@admin_login_required # Only accessible by logged-in administrators
def admin_add_item():
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        description = request.form['description'].strip()
        price = request.form['price'].strip()
        category = request.form['category'].strip()
        media_url = request.form.get('media_url', '').strip()
        rating = request.form.get('rating', '0').strip()

        errors = {}
        if not name:
            errors['name'] = 'Item name is mandatory.'
        if not description:
            errors['description'] = 'Description is mandatory.'
        if not price:
            errors['price'] = 'Price is mandatory.'
        else:
            try:
                price = float(price)
                if price <= 0:
                    errors['price'] = 'Price must be a positive number.'
            except ValueError:
                errors['price'] = 'Invalid price format.'
        if not category:
            errors['category'] = 'Category is mandatory.'
        
        try:
            rating = float(rating)
            if not (0 <= rating <= 5):
                errors['rating'] = 'Rating must be between 0 and 5.'
        except ValueError:
            errors['rating'] = 'Invalid rating format.'


        if errors:
            flash('Please correct the errors in the form.', 'danger')
            return render_template('admin_add_item.html', errors=errors, 
                                   prev_name=name, prev_description=description, 
                                   prev_price=request.form['price'], prev_category=category,
                                   prev_media_url=media_url, prev_rating=request.form['rating'])
        else:
            new_item = {
                'name': name,
                'description': description,
                'price': price,
                'category': category,
                'media_url': media_url,
                'rating': rating,
                'createdAt': datetime.utcnow()
            }
            bakery_items_collection.insert_one(new_item)
            flash(f'Bakery item "{name}" added successfully!', 'success')
            print(f"DEBUG: Bakery item '{name}' added to MongoDB.")
            return redirect(url_for('admin_dashboard'))

    # Ensure errors dictionary is always passed on GET request
    return render_template('admin_add_item.html', errors={}, 
                           prev_name='', prev_description='', prev_price='', 
                           prev_category='', prev_media_url='', prev_rating='0')

@app.route('/admin/edit_item/<item_id>', methods=['GET', 'POST'])
@admin_login_required # Only accessible by logged-in administrators
def admin_edit_item(item_id):
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return redirect(url_for('admin_login'))

    item = None
    try:
        item = bakery_items_collection.find_one({"_id": ObjectId(item_id)})
        if not item:
            flash('Item not found.', 'danger')
            return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f'Invalid item ID: {e}', 'danger')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        description = request.form['description'].strip()
        price = request.form['price'].strip()
        category = request.form['category'].strip()
        media_url = request.form.get('media_url', '').strip()
        rating = request.form.get('rating', '0').strip()

        errors = {}
        if not name:
            errors['name'] = 'Item name is mandatory.'
        if not description:
            errors['description'] = 'Description is mandatory.'
        if not price:
            errors['price'] = 'Price is mandatory.'
        else:
            try:
                price = float(price)
                if price <= 0:
                    errors['price'] = 'Price must be a positive number.'
            except ValueError:
                errors['price'] = 'Invalid price format.'
        if not category:
            errors['category'] = 'Category is mandatory.'
        
        try:
            rating = float(rating)
            if not (0 <= rating <= 5):
                errors['rating'] = 'Rating must be between 0 and 5.'
        except ValueError:
            errors['rating'] = 'Invalid rating format.'

        if errors:
            flash('Please correct the errors in the form.', 'danger')
            # Retain current form values for re-rendering
            item['name'] = name
            item['description'] = description
            item['price'] = request.form['price']
            item['category'] = category
            item['media_url'] = media_url
            item['rating'] = request.form['rating']
            return render_template('admin_edit_item.html', item=item, errors=errors)
        else:
            updated_item = {
                'name': name,
                'description': description,
                'price': price,
                'category': category,
                'media_url': media_url,
                'rating': rating,
            }
            bakery_items_collection.update_one({"_id": ObjectId(item_id)}, {"$set": updated_item})
            flash(f'Bakery item "{name}" updated successfully!', 'success')
            print(f"DEBUG: Bakery item '{name}' ({item_id}) updated in MongoDB.")
            return redirect(url_for('admin_dashboard'))

    # Ensure errors dictionary is always passed on GET request
    return render_template('admin_edit_item.html', item=item, errors={})

@app.route('/admin/delete_item/<item_id>', methods=['POST'])
@admin_login_required # Only accessible by logged-in administrators
def admin_delete_item(item_id):
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return redirect(url_for('admin_login'))

    try:
        result = bakery_items_collection.delete_one({"_id": ObjectId(item_id)})
        if result.deleted_count == 1:
            flash('Item deleted successfully!', 'success')
            print(f"DEBUG: Bakery item '{item_id}' deleted from MongoDB.")
        else:
            flash('Item not found.', 'danger')
            print(f"WARNING: Attempted to delete item '{item_id}' but not found.")
    except Exception as e:
        flash(f'Error deleting item: {e}', 'danger')
        print(f"ERROR: Error deleting item '{item_id}': {e}")
    
    return redirect(url_for('admin_dashboard'))


# --- Bakery Shop Routes (Search and Filter Added) ---
@app.route('/items')
@login_required # All user-facing routes now require login
def items_page():
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return render_template('items.html', items=[], all_categories=[], current_search='', current_category='')

    search_query = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()

    query = {}
    if search_query:
        query["$or"] = [
            {"name": {"$regex": search_query, "$options": "i"}},
            {"description": {"$regex": search_query, "$options": "i"}}
        ]
    if category_filter:
        query["category"] = {"$regex": category_filter, "$options": "i"}

    bakery_items = list(bakery_items_collection.find(query).sort("rating", -1))

    all_categories = sorted([
        cat for cat in bakery_items_collection.distinct("category") if cat
    ])

    for item in bakery_items:
        item['_id'] = str(item['_id'])
        if 'media_url' not in item or not item['media_url']:
            item['media_url'] = 'https://placehold.co/400x300/cccccc/000000?text=No+Image'

    print(f"DEBUG: Items page accessed. Search: '{search_query}', Category: '{category_filter}'. Displaying {len(bakery_items)} bakery items.")
    return render_template('items.html', 
                           items=bakery_items, 
                           all_categories=all_categories,
                           current_search=search_query,
                           current_category=category_filter)

@app.route('/contact')
@login_required # Requires login
def contact_page():
    return render_template('contact.html')

@app.route('/subscription')
@login_required # Requires login
def subscription_page():
    return render_template('subscription.html')

@app.route('/payment', methods=['GET', 'POST'])
@login_required # Requires login
def payment_page():
    if mongo is None:
        flash("Database connection error. Please try again later.", 'danger')
        return redirect(url_for('view_cart'))

    cart_items = session.get('cart', [])
    total_price = sum(item['price'] * item['quantity'] for item in cart_items)

    if not cart_items:
        flash("Your cart is empty. Please add items before proceeding to checkout.", 'warning')
        return redirect(url_for('items_page'))
    
    # Store cart details in session for QR code generation later
    # This is where the order_id is generated and stored for the current transaction
    session['order_details_for_qr'] = {
        'items': cart_items,
        'total': total_price,
        'order_id': f"ORDER-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000,9999)}"
    }
    session.modified = True # Important to save session changes

    print(f"DEBUG: Payment page accessed. Order ID: {session['order_details_for_qr']['order_id']}, Total: {total_price}")
    return render_template('payment.html', cart_items=cart_items, total_price=total_price)


@app.route('/confirm_order_and_qr', methods=['POST'])
@login_required
def confirm_order_and_qr():
    """
    Confirms the order (simulated payment) and then redirects to QR code generation.
    Clears the cart after "confirmation".
    """
    if 'order_details_for_qr' not in session:
        flash("No order details found to confirm. Please start a new order.", 'danger')
        return redirect(url_for('items_page'))

    # Simulate payment processing here (e.g., save order to DB, etc.)
    # For now, we'll just flash a message.
    flash("Payment confirmed! Your order is being processed.", 'success')
    print(f"DEBUG: Order {session['order_details_for_qr']['order_id']} confirmed.")

    # Clear the cart from the session after successful order confirmation
    session.pop('cart', None)
    session.modified = True

    # Redirect to the QR code generator page, which will now pull data from session['order_details_for_qr']
    return redirect(url_for('qrcode_generator_page'))


@app.route('/qrcode_generator')
@login_required # Requires login
def qrcode_generator_page():
    order_details = session.get('order_details_for_qr')
    
    qr_code_base64 = None
    order_summary_text = None
    order_id_for_template = None

    if order_details:
        # Format order summary for QR code
        order_summary_lines = [f"Order ID: {order_details['order_id']}"]
        for item in order_details['items']:
            order_summary_lines.append(f"{item['quantity']}x {item['name']} (${item['price']:.2f} each)")
        order_summary_lines.append(f"Total: ${order_details['total']:.2f}")
        order_summary_text = "\n".join(order_summary_lines)
        order_id_for_template = order_details['order_id']

        # Generate QR code using the Python qrcode library
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(order_summary_text)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save image to BytesIO buffer
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            
            # Encode to Base64
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            print(f"DEBUG: Server-side QR Code generated for Order ID: {order_details['order_id']}")

        except Exception as e:
            print(f"ERROR: Failed to generate server-side QR code: {e}")
            flash("Failed to generate QR code on the server. Please try manual input.", 'danger')
            qr_code_base64 = None # Ensure no partial QR code is sent
    else:
        flash("No order details found for QR code generation. Please place an order first.", 'warning')
        print("WARNING: QR Code Generator page accessed without order details in session.")
    
    # Pass the Base64 image data (or None) to the template
    return render_template('qrcode_generator.html', 
                           order_data=order_summary_text, # Still pass for manual form fallback
                           order_id=order_id_for_template, # Still pass for manual form fallback
                           qr_code_base64=qr_code_base64) # This is the new data for server-side QR

# --- Shopping Cart Routes ---

@app.route('/add_to_cart/<item_id>', methods=['POST'])
@login_required # Requires login
def add_to_cart(item_id):
    if mongo is None:
        flash("Database connection error. Cannot add to cart.", 'danger')
        return redirect(url_for('items_page'))

    try:
        item = bakery_items_collection.find_one({"_id": ObjectId(item_id)})
        if not item:
            flash('Item not found!', 'danger')
            return redirect(url_for('items_page'))

        # Initialize cart in session if it doesn't exist
        if 'cart' not in session:
            session['cart'] = []

        # Check if item is already in cart
        item_found = False
        for cart_item in session['cart']:
            if cart_item['_id'] == str(item['_id']): # Compare string IDs
                cart_item['quantity'] += 1
                item_found = True
                break
        
        if not item_found:
            # Add new item to cart
            session['cart'].append({
                '_id': str(item['_id']), # Store as string
                'name': item['name'],
                'price': item['price'],
                'media_url': item.get('media_url', 'https://placehold.co/400x300/cccccc/000000?text=No+Image'),
                'quantity': 1
            })
        
        session.modified = True # Important to tell Flask that session content has changed
        flash(f'"{item["name"]}" added to cart!', 'success')
        print(f"DEBUG: Item '{item['name']}' added to cart. Current cart: {session['cart']}")

    except Exception as e:
        flash(f'Error adding item to cart: {e}', 'danger')
        print(f"ERROR: Error adding item to cart: {e}")
    
    return redirect(url_for('items_page'))

@app.route('/cart')
@login_required # Requires login
def view_cart():
    cart_items = session.get('cart', [])
    total_price = sum(item['price'] * item['quantity'] for item in cart_items)
    print(f"DEBUG: Viewing cart. Items: {cart_items}, Total: {total_price}")
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

@app.route('/update_cart_item/<item_id>', methods=['POST'])
@login_required # Requires login
def update_cart_item(item_id):
    quantity_str = request.form.get('quantity', '1').strip()
    
    try:
        quantity = int(quantity_str)
        if quantity < 0:
            raise ValueError("Quantity cannot be negative.")
    except ValueError:
        flash('Invalid quantity.', 'danger')
        return redirect(url_for('view_cart'))

    cart_items = session.get('cart', [])
    updated = False
    for item in cart_items:
        if item['_id'] == item_id:
            if quantity == 0:
                cart_items.remove(item) # Remove item if quantity is 0
                flash(f'"{item["name"]}" removed from cart.', 'info')
                print(f"DEBUG: Item '{item['name']}' removed from cart.")
            else:
                item['quantity'] = quantity
                flash(f'Quantity for "{item["name"]}" updated to {quantity}.', 'success')
                print(f"DEBUG: Quantity for '{item['name']}' updated to {quantity}.")
            updated = True
            break
    
    if not updated:
        flash('Item not found in cart.', 'danger')
        print(f"WARNING: Attempted to update item '{item_id}' not found in cart.")

    session['cart'] = cart_items # Update session with modified list
    session.modified = True
    return redirect(url_for('view_cart'))

@app.route('/remove_from_cart/<item_id>', methods=['POST'])
@login_required # Requires login
def remove_from_cart(item_id):
    cart_items = session.get('cart', [])
    original_len = len(cart_items)
    
    # Filter out the item to be removed
    session['cart'] = [item for item in cart_items if item['_id'] != item_id]
    session.modified = True

    if len(session['cart']) < original_len:
        flash('Item removed from cart.', 'info')
        print(f"DEBUG: Item '{item_id}' removed from cart.")
    else:
        flash('Item not found in cart.', 'danger')
        print(f"WARNING: Attempted to remove item '{item_id}' but not found.")
    
    return redirect(url_for('view_cart'))

@app.route('/clear_cart', methods=['POST'])
@login_required # Requires login
def clear_cart():
    session['cart'] = []
    session.modified = True
    flash('Your cart has been cleared.', 'info')
    print("DEBUG: Cart cleared.")
    return redirect(url_for('view_cart'))


# --- Flask Application Initialization ---
if __name__ == '__main__':
    print("DEBUG: Starting Flask application initialization block.")
    create_data_dir_and_init_excel()
    print("DEBUG: Data directory and Excel initialization complete.")
    
    if mongo is not None:
        print("DEBUG: MongoDB connection is active. Proceeding with DB setup checks.")
        # Create initial admin user if not exists
        admin_user_exists = users_collection.find_one({"username": ADMIN_USERNAME.lower(), "is_admin": True})
        if not admin_user_exists:
            print("INFO: Creating initial admin user in MongoDB...")
            try:
                users_collection.insert_one({
                    'username': ADMIN_USERNAME.lower(),
                    'email': f'{ADMIN_USERNAME}@bakery.com',
                    'password_hash': ADMIN_PASSWORD_HASH,
                    'full_name': 'Bakery Admin',
                    'phone': None,
                    'login_type': 'Traditional',
                    'social_id': None,
                    'is_admin': True,
                    'created_at': datetime.utcnow()
                })
                print("INFO: Initial admin user created in MongoDB.")
            except Exception as e:
                print(f"CRITICAL ERROR: Failed to create initial admin user in MongoDB: {e}")
        else:
            print("INFO: Admin user already exists in MongoDB. Skipping creation.")

        # --- NEW: Seed Pastry Items if they don't exist ---
        if bakery_items_collection.count_documents({"category": "Pastry"}) == 0:
            print("INFO: Seeding initial pastry items into MongoDB...")
            pastry_items_to_add = [
                {
                    'name': 'Classic Croissant',
                    'description': 'Flaky, buttery, and golden-brown. A perfect breakfast treat.',
                    'price': 3.50,
                    'category': 'Pastry',
                    'media_url': 'https://placehold.co/400x300/FFD700/000000?text=Croissant',
                    'rating': 4.8,
                    'createdAt': datetime.utcnow()
                },
                {
                    'name': 'Chocolate Eclair',
                    'description': 'Light choux pastry filled with rich chocolate cream, topped with ganache.',
                    'price': 4.75,
                    'category': 'Pastry',
                    'media_url': 'https://placehold.co/400x300/A0522D/FFFFFF?text=Eclair',
                    'rating': 4.7,
                    'createdAt': datetime.utcnow()
                },
                {
                    'name': 'Blueberry Muffin',
                    'description': 'Moist and fluffy muffin bursting with fresh blueberries.',
                    'price': 3.00,
                    'category': 'Pastry',
                    'media_url': 'https://placehold.co/400x300/87CEEB/000000?text=Muffin',
                    'rating': 4.5,
                    'createdAt': datetime.utcnow()
                },
                {
                    'name': 'Cinnamon Roll',
                    'description': 'Soft, warm roll swirled with cinnamon and topped with sweet cream cheese frosting.',
                    'price': 4.25,
                    'category': 'Pastry',
                    'media_url': 'https://placehold.co/400x300/D2B48C/000000?text=Cinnamon+Roll',
                    'rating': 4.9,
                    'createdAt': datetime.utcnow()
                },
                {
                    'name': 'Apple Turnover',
                    'description': 'Puff pastry filled with spiced apple chunks, baked until golden.',
                    'price': 3.99,
                    'category': 'Pastry',
                    'media_url': 'https://placehold.co/400x300/F0E68C/000000?text=Apple+Turnover',
                    'rating': 4.6,
                    'createdAt': datetime.utcnow()
                }
            ]
            try:
                bakery_items_collection.insert_many(pastry_items_to_add)
                print(f"INFO: Added {len(pastry_items_to_add)} pastry items to MongoDB.")
            except Exception as e:
                print(f"CRITICAL ERROR: Failed to seed pastry items in MongoDB: {e}")
        else:
            print("INFO: Pastry items already exist in MongoDB. Skipping seeding.")

    else:
        print("WARNING: Skipping admin user and pastry item creation because MongoDB connection failed.")
    
    print("DEBUG: All pre-run checks and seeding complete. Attempting to run Flask app.")
    app.run(debug=True)
    print("DEBUG: Flask app.run() call finished (this line might not be reached in normal operation).")