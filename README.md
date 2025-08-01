A sophisticated and user-friendly online bakery shop built with Flask, MongoDB, and Razorpay, featuring a luxurious gold and brown theme and an interactive 3D background animation.
Table of Contents
 * Features
 * Technologies Used
 * Setup Instructions
   * Prerequisites
   * Database Setup (MongoDB Atlas)
   * Razorpay Setup
   * Google OAuth Setup
   * Installation
   * Running the Application
 * Usage
   * User Flow
   * Admin Flow
 * Important Notes
 * Screenshots (Placeholder - you can add your own!)
Features
 * User Authentication:
   * Traditional registration and login with secure password hashing (passwords are one-way encrypted).
   * Social login options: Google, Facebook, and GitHub integration (requires API setup).
   * Session management for logged-in users.
   * User data (excluding raw passwords) is securely stored in MongoDB.
 * Admin Panel:
   * Secure admin login (both hardcoded and MongoDB-based admin user).
   * Dashboard to manage bakery items (add, edit, delete).
   * View all registered users.
   * View all customer orders.
   * Export all user data to an Excel file (for reporting purposes, not primary data storage).
 * Bakery Item Catalog:
   * Browse a wide range of bakery items.
   * Search items by name or description.
   * Filter items by category.
   * Display item details including name, description, price, media (image URL), and rating.
 * Shopping Cart Functionality:
   * Add items to a dynamic shopping cart.
   * Update quantities of items in the cart.
   * Remove individual items or clear the entire cart.
 * Secure Payment Gateway (Razorpay):
   * Seamless checkout process integrated with Razorpay for Indian Rupee (INR) payments.
   * Payment verification for security.
 * Order QR Code Generation:
   * Generate a unique QR code for each successful order, containing order details (already implemented).
   * Option to "Pay Now (QR)" for a single item directly from the items page (already implemented).
 * Elegant User Interface:
   * Luxurious "gold and brown luxe aura" theme with modern typography.
   * Glassmorphism effects and subtle shadows for a premium feel.
 * Interactive 3D Background:
   * Dynamic 3D animation on the home page featuring floating bakery-themed objects (buns, loaves, donuts) rendered with Three.js.
   * Subtle camera movement controlled by mouse/touch for an immersive experience.
 * Responsive Design:
   * Optimized for viewing across various devices (desktops, tablets, mobile phones).
Technologies Used
 * Backend:
   * Flask (Python Web Framework)
   * Flask-PyMongo (MongoDB integration for Flask)
   * Werkzeug Security (for password hashing)
   * Requests (for OAuth API calls)
   * Pandas & XlsxWriter (for Excel data export)
   * Razorpay Python SDK (for payment processing)
   * QR Code (Python library for QR generation)
 * Frontend:
   * HTML5
   * CSS3 (Custom styling for the luxe theme)
   * JavaScript
   * Three.js (for 3D background animation)
   * QRCode.js (for client-side QR generation fallback)
 * Database:
   * MongoDB Atlas (Cloud-hosted NoSQL database)
Setup Instructions
Prerequisites
Before you begin, ensure you have the following installed:
 * Python 3.8+
 * pip (Python package installer)
 * Git (optional, for cloning the repository)
Database Setup (MongoDB Atlas)
 * Create a MongoDB Atlas Account: If you don't have one, sign up at MongoDB Atlas.
 * Create a New Cluster: Follow the instructions to create a free tier (M0) cluster.
 * Create a Database User:
   * Navigate to "Database Access" in the Security section.
   * Click "Add New Database User".
   * Choose "Password" as the Authentication Method.
   * Set a strong username and password (e.g., projectuse222 and iCKPUrfJpMdrP7SQ as in your code - highly recommend changing this for production!).
   * Grant "Read and write to any database" privileges.
 * Configure Network Access:
   * Navigate to "Network Access" in the Security section.
   * Click "Add IP Address".
   * For development, you can "Allow Access from Anywhere" (for testing purposes, not recommended for production). For production, add specific IP addresses.
 * Get Connection String:
   * Go to "Databases" and click "Connect" on your cluster.
   * Choose "Connect your application".
   * Select "Python" and your Python version.
   * Copy the connection string. It will look something like:
     mongodb+srv://<username>:<password>@cluster0.frpspvc.mongodb.net/bakerydb?retryWrites=true&w=majority&appName=Cluster0
   * Replace <username> and <password> with the database user credentials you created.
 * Update app.py: Ensure the app.config["MONGO_URI"] variable in app.py is updated with your correct MongoDB Atlas connection string.
Razorpay Setup
 * Create a Razorpay Account: Sign up at Razorpay.
 * Get API Keys:
   * Log in to your Razorpay Dashboard.
   * Navigate to Settings -> API Keys.
   * Generate new Key ID and Key Secret.
 * Update app.py:
   * Replace 'rzp_test_YOUR_KEY_ID' with your actual Key ID.
   * Replace 'YOUR_RAZORPAY_SECRET_KEY' with your actual Key Secret.
   * Important: For production, store these securely as environment variables, not directly in the code.
Google OAuth Setup (Optional, but recommended for full functionality)
 * Go to Google Cloud Console: Visit https://console.developers.google.com/.
 * Create a New Project: If you don't have one, create a new project.
 * Enable Google People API: In the left sidebar, go to "APIs & Services" -> "Library", search for "Google People API" and enable it.
 * Create OAuth Consent Screen:
   * Go to "APIs & Services" -> "OAuth consent screen".
   * Choose "External" user type and fill in the required details (App name, user support email, developer contact information).
   * Add "email", "profile", and "openid" as scopes.
   * Add test users if your app is still in "Testing" status.
 * Create OAuth Client ID:
   * Go to "APIs & Services" -> "Credentials".
   * Click "Create Credentials" -> "OAuth client ID".
   * Select "Web application".
   * Set the "Authorized JavaScript origins" to http://127.0.0.1:5000.
   * Set the "Authorized redirect URIs" to http://127.0.0.1:5000/oauth/google/callback.
   * Click "Create".
   * Copy your Client ID and Client Secret.
 * Update app.py: Replace the placeholder GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in app.py with your actual credentials.
Note: Similar steps apply for Facebook and GitHub OAuth if you wish to enable them. You'll need to create developer accounts and applications on their respective platforms to get client IDs and secrets.
Installation
 * Clone the repository (if applicable) or navigate to your project directory:
   cd C:\Users\STUDENT4_10\Desktop\backery_shop

 * Create a Python Virtual Environment (recommended):
   python -m venv venv

 * Activate the Virtual Environment:
   * Windows:
     .\venv\Scripts\activate

   * macOS/Linux:
     source venv/bin/activate

 * Install Dependencies:
   pip install Flask Flask-PyMongo pandas openpyxl xlsxwriter qrcode[pil] razorpay requests werkzeug

   (Note: openpyxl is needed by pandas for Excel operations, qrcode[pil] installs Pillow for image generation, and werkzeug for security utilities.)
Running the Application
 * Ensure your virtual environment is activated.
 * Run the Flask application:
   python app.py

 * Access the application: Open your web browser and go to http://127.0.0.1:5000/.
Usage
User Flow
 * Home Page:
   * Upon visiting http://127.0.0.1:5000/, you'll see the home page with the interactive 3D bakery animation in the background.
   * You can register a new account or log in.
 * Registration:
   * Click "Join Us Now" or navigate to /register.
   * Fill in your details to create a traditional account, or use the social login options.
 * Login:
   * Navigate to /login.
   * Log in with your traditional account or via Google, Facebook, or GitHub.
 * Bakery Items Page:
   * After logging in, you'll be redirected to /items.
   * Browse items, use the search bar to find specific products, or filter by category.
   * Click "Add to Cart" to add items to your shopping cart.
   * Use the "Pay Now (QR)" button with a quantity to directly proceed to checkout for a single item.
 * Shopping Cart:
   * Click the "Cart" link in the navigation bar to view /cart.
   * Adjust item quantities, remove items, or clear the entire cart.
 * Checkout:
   * From the cart page, click "Proceed to Checkout" to go to /checkout.
   * Confirm your order details and proceed with payment via Razorpay.
 * QR Code Generation:
   * Upon successful payment, you'll be redirected to /qrcode_generator where a QR code containing your order details will be displayed. You can download this QR code.
   * A manual QR code generator is also available as a fallback.
 * Contact Page:
   * Access the contact information at /contact.
 * Subscription Page:
   * View placeholder subscription plans at /subscription. (Note: This feature is currently a placeholder and does not have active Razorpay subscription integration).
Admin Flow
 * Admin Login:
   * Navigate to http://127.0.0.1:5000/admin/login.
   * Default Hardcoded Admin:
     * Username: admin
     * Password: adminpass (Highly recommended to change this in app.py for security!)
   * MongoDB Admin User: If you've created a user in MongoDB and set is_admin: true, you can log in with those credentials.
 * Admin Dashboard:
   * After logging in, you'll be redirected to /admin/dashboard.
   * Manage Bakery Items:
     * Click "Add New Bakery Item" to add new products to your shop.
     * Use "Edit" and "Delete" buttons next to existing items to manage them.
   * Registered Users: View a table of all registered users.
   * Recent Orders: View a list of all customer orders.
   * Download User Data: Click "Download All Users Data (Excel)" to export user information.
   * Admin Logout: Click "Admin Logout" to end your admin session.
Important Notes
 * Security & Data Storage:
   * The application primarily uses MongoDB Atlas for storing user accounts, bakery items, and orders, which is a robust and scalable database solution.
   * Passwords for traditional accounts are stored using secure hashing (one-way encryption) via werkzeug.security. This means passwords cannot be decrypted back to their original form, protecting user credentials.
   * The hardcoded admin credentials (admin/adminpass) are for development purposes only. CHANGE THEM IMMEDIATELY in app.py before any deployment.
   * The Excel file (users.xlsx) is used only for admin data export and reporting. It is not the primary database for user authentication or application data. User details in this export are not encrypted, as it's intended for internal administrative use.
   * NEVER expose your Razorpay Key Secret directly in client-side code or public repositories. For production, use environment variables for all sensitive keys.
   * The current social OAuth client IDs/secrets are placeholders. You must replace them with your own from Google, Facebook, and GitHub developer consoles.
 * Razorpay Integration: The current Razorpay integration handles one-time payments. Subscriptions are noted as a future feature and are not fully implemented.
 * 3D Animation Performance: While Three.js is optimized, complex scenes or very old browsers might experience performance issues. The current scene is kept simple to balance aesthetics and performance.
 * Error Handling: Basic error handling is in place, but for a production application, more robust error logging and user feedback mechanisms would be required.
Screenshots
(Placeholder for screenshots. You can add images of your application's home page, items page, cart, admin dashboard, and QR code.)
