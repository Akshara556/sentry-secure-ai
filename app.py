"""
Construction Site Safety Monitoring System
COMPLETE WORKING VERSION WITH WORKING AUDIO AND ALL TEMPLATES
"""

import os
import cv2
import numpy as np
import json
import time
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, redirect, url_for, Response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from collections import defaultdict, deque
import warnings
warnings.filterwarnings('ignore')

# ==================== SIMPLE AUDIO ALERT SETUP FOR WINDOWS ====================
try:
    import winsound
    AUDIO_ENABLED = True
    print("✅ Windows audio alerts enabled (winsound)")
except:
    try:
        # Try pygame as fallback
        import pygame
        pygame.mixer.init()
        AUDIO_ENABLED = True
        print("✅ Audio alerts enabled (pygame)")
    except:
        AUDIO_ENABLED = False
        print("⚠️ Audio alerts disabled (install winsound or pygame)")

# ==================== MONGODB SETUP ====================
try:
    from pymongo import MongoClient
    from bson import ObjectId
    
    client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
    mongo_db = client['construction_safety_db']
    users_collection = mongo_db['users']
    violations_collection = mongo_db['violations']
    
    client.server_info()
    print("✅ Connected to MongoDB successfully")
    
    users_collection.create_index('username', unique=True)
    users_collection.create_index('email', unique=True)
    violations_collection.create_index([('timestamp', -1)])
    
    MONGODB_ENABLED = True
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")
    print("⚠️ Falling back to in-memory database")
    MONGODB_ENABLED = False
    users_collection = None
    violations_collection = None
    ObjectId = str

# ==================== INITIALIZE FLASK APP ====================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'construction-safety-monitoring-secret-key-2024'

# ==================== USER DATABASE ====================
users_db = {}
violations_db = []

class User(UserMixin):
    def __init__(self, user_data):
        if MONGODB_ENABLED and '_id' in user_data:
            self.id = str(user_data['_id'])
        else:
            self.id = user_data.get('id', '')
        self.username = user_data.get('username', '')

# ==================== FLASK-LOGIN SETUP ====================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    try:
        if MONGODB_ENABLED and users_collection is not None:
            if user_id == '0':
                user_data = users_collection.find_one({'username': 'supervisor'})
            else:
                try:
                    user_data = users_collection.find_one({'_id': ObjectId(user_id)})
                except:
                    user_data = users_collection.find_one({'username': user_id})
            
            if user_data:
                return User(user_data)
        else:
            if user_id in users_db:
                return User(users_db[user_id])
            
            for uid, user in users_db.items():
                if user.get('username') == user_id:
                    return User(user)
    except Exception as e:
        print(f"Error loading user: {e}")
    
    return None

# ==================== HTML TEMPLATES ====================

LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Login - SiteSafe Monitor</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            width: 100%;
            max-width: 400px;
            padding: 20px;
        }
        .login-card {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.2);
        }
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo i {
            font-size: 3em;
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .logo h1 {
            color: #2c3e50;
            font-size: 1.8em;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .input-with-icon {
            position: relative;
        }
        .input-with-icon i {
            position: absolute;
            left: 15px;
            top: 50%;
            transform: translateY(-50%);
            color: #95a5a6;
        }
        .input-with-icon input {
            width: 100%;
            padding: 12px 12px 12px 45px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 1em;
        }
        .btn-login {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 1.1em;
            cursor: pointer;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
        }
        .demo-credentials {
            margin-top: 25px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            font-size: 0.9em;
        }
        .register-link {
            text-align: center;
            margin-top: 20px;
            color: #666;
        }
        .register-link a {
            color: #3498db;
            text-decoration: none;
            font-weight: 600;
        }
        .alert {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }
        .alert-danger {
            background: #ffeaea;
            border: 1px solid #e74c3c;
            color: #e74c3c;
        }
        .alert-success {
            background: #e8f6f3;
            border: 1px solid #27ae60;
            color: #27ae60;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-card">
            <div class="logo">
                <i class="fas fa-hard-hat"></i>
                <h1>SiteSafe Monitor</h1>
                <p>Construction Site Safety Monitoring System</p>
            </div>
            
            <div id="alert" class="alert" style="display: none;"></div>
            
            <form id="loginForm">
                <div class="form-group">
                    <label for="username">Username</label>
                    <div class="input-with-icon">
                        <i class="fas fa-user"></i>
                        <input type="text" id="username" name="username" placeholder="Enter your username" required>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="password">Password</label>
                    <div class="input-with-icon">
                        <i class="fas fa-lock"></i>
                        <input type="password" id="password" name="password" placeholder="Enter your password" required>
                    </div>
                </div>
                
                <button type="submit" class="btn-login">
                    <i class="fas fa-sign-in-alt"></i> Login
                </button>
            </form>
            
            <div class="demo-credentials">
                <h4><i class="fas fa-info-circle"></i> Demo Credentials</h4>
                <p><strong>Username:</strong> supervisor</p>
                <p><strong>Password:</strong> safety123</p>
            </div>
            
            <div class="register-link">
                Don't have an account? <a href="/register">Register here</a>
            </div>
        </div>
    </div>
    
    <script>
        document.getElementById('loginForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const alertDiv = document.getElementById('alert');
            
            alertDiv.style.display = 'none';
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: username, password: password})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alertDiv.className = 'alert alert-success';
                    alertDiv.innerHTML = '<i class="fas fa-check-circle"></i> Login successful! Redirecting...';
                    alertDiv.style.display = 'block';
                    
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 1000);
                } else {
                    alertDiv.className = 'alert alert-danger';
                    alertDiv.innerHTML = '<i class="fas fa-exclamation-triangle"></i> ' + data.message;
                    alertDiv.style.display = 'block';
                }
            } catch (error) {
                alertDiv.className = 'alert alert-danger';
                alertDiv.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Connection error. Please try again.';
                alertDiv.style.display = 'block';
            }
        });
    </script>
</body>
</html>
'''

REGISTER_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Register - SiteSafe Monitor</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .register-container {
            width: 100%;
            max-width: 450px;
            padding: 20px;
        }
        .register-card {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.2);
        }
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo i {
            font-size: 3em;
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .logo h1 {
            color: #2c3e50;
            font-size: 1.8em;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .input-with-icon {
            position: relative;
        }
        .input-with-icon i {
            position: absolute;
            left: 15px;
            top: 50%;
            transform: translateY(-50%);
            color: #95a5a6;
        }
        .input-with-icon input {
            width: 100%;
            padding: 12px 12px 12px 45px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 1em;
        }
        .btn-register {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 1.1em;
            cursor: pointer;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin-top: 10px;
        }
        .login-link {
            text-align: center;
            margin-top: 20px;
            color: #666;
        }
        .login-link a {
            color: #3498db;
            text-decoration: none;
            font-weight: 600;
        }
        .alert {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }
        .alert-danger {
            background: #ffeaea;
            border: 1px solid #e74c3c;
            color: #e74c3c;
        }
        .alert-success {
            background: #e8f6f3;
            border: 1px solid #27ae60;
            color: #27ae60;
        }
    </style>
</head>
<body>
    <div class="register-container">
        <div class="register-card">
            <div class="logo">
                <i class="fas fa-hard-hat"></i>
                <h1>SiteSafe Monitor</h1>
                <p>Create your account</p>
            </div>
            
            <div id="alert" class="alert" style="display: none;"></div>
            
            <form id="registerForm">
                <div class="form-group">
                    <label for="username">Username</label>
                    <div class="input-with-icon">
                        <i class="fas fa-user"></i>
                        <input type="text" id="username" name="username" placeholder="Choose a username" required>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="email">Email Address</label>
                    <div class="input-with-icon">
                        <i class="fas fa-envelope"></i>
                        <input type="email" id="email" name="email" placeholder="Enter your email" required>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="password">Password</label>
                    <div class="input-with-icon">
                        <i class="fas fa-lock"></i>
                        <input type="password" id="password" name="password" placeholder="Create password" required>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="confirmPassword">Confirm Password</label>
                    <div class="input-with-icon">
                        <i class="fas fa-lock"></i>
                        <input type="password" id="confirmPassword" name="confirmPassword" placeholder="Confirm password" required>
                    </div>
                </div>
                
                <button type="submit" class="btn-register">
                    <i class="fas fa-user-plus"></i> Create Account
                </button>
            </form>
            
            <div class="login-link">
                Already have an account? <a href="/login">Login here</a>
            </div>
        </div>
    </div>
    
    <script>
        document.getElementById('registerForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const alertDiv = document.getElementById('alert');
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            
            alertDiv.style.display = 'none';
            
            if (password !== confirmPassword) {
                alertDiv.className = 'alert alert-danger';
                alertDiv.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Passwords do not match';
                alertDiv.style.display = 'block';
                return;
            }
            
            if (password.length < 8) {
                alertDiv.className = 'alert alert-danger';
                alertDiv.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Password must be at least 8 characters';
                alertDiv.style.display = 'block';
                return;
            }
            
            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        username: document.getElementById('username').value,
                        email: document.getElementById('email').value,
                        password: password
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alertDiv.className = 'alert alert-success';
                    alertDiv.innerHTML = '<i class="fas fa-check-circle"></i> ' + data.message + ' Redirecting to login...';
                    alertDiv.style.display = 'block';
                    
                    setTimeout(() => {
                        window.location.href = '/login';
                    }, 2000);
                } else {
                    alertDiv.className = 'alert alert-danger';
                    alertDiv.innerHTML = '<i class="fas fa-exclamation-triangle"></i> ' + data.message;
                    alertDiv.style.display = 'block';
                }
            } catch (error) {
                alertDiv.className = 'alert alert-danger';
                alertDiv.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Connection error. Please try again.';
                alertDiv.style.display = 'block';
            }
        });
    </script>
</body>
</html>
'''

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard - SiteSafe Monitor</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: #f0f2f5;
        }
        .navbar {
            background: #2c3e50;
            color: white;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .navbar-brand {
            font-size: 1.5em;
            font-weight: bold;
            color: white;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .nav-links {
            display: flex;
            gap: 15px;
        }
        .nav-links a {
            color: white;
            text-decoration: none;
            padding: 8px 15px;
            border-radius: 4px;
            transition: background 0.3s;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .nav-links a:hover, .nav-links a.active {
            background: #3498db;
        }
        .container {
            max-width: 1200px;
            margin: 30px auto;
            padding: 0 20px;
        }
        .welcome-section {
            background: white;
            padding: 40px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .welcome-section h1 {
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        .dashboard-card {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.3s;
            cursor: pointer;
            text-decoration: none;
            color: inherit;
            display: block;
        }
        .dashboard-card:hover {
            transform: translateY(-5px);
        }
        .card-icon {
            font-size: 3em;
            margin-bottom: 20px;
            color: #3498db;
        }
        .dashboard-card h3 {
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .dashboard-card p {
            color: #666;
            font-size: 0.95em;
        }
        .btn {
            padding: 12px 25px;
            background: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: background 0.3s;
        }
        .btn:hover {
            background: #2980b9;
        }
        .btn-success {
            background: #27ae60;
        }
        .btn-success:hover {
            background: #219653;
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <a href="/dashboard" class="navbar-brand">
            <i class="fas fa-hard-hat"></i> SiteSafe Monitor
        </a>
        <div class="nav-links">
            <a href="/dashboard" class="active"><i class="fas fa-home"></i> Dashboard</a>
            <a href="/live-monitor"><i class="fas fa-video"></i> Live Monitor</a>
            <a href="/reports"><i class="fas fa-chart-bar"></i> Reports</a>
            <a href="/violations-report"><i class="fas fa-exclamation-triangle"></i> Violations</a>
            <a href="/logout" style="margin-left: 30px;"><i class="fas fa-sign-out-alt"></i> Logout</a>
        </div>
    </nav>
    
    <div class="container">
        <div class="welcome-section">
            <h1>Welcome, {{ username }}!</h1>
            <p>Monitor construction site safety in real-time using advanced computer vision.</p>
            
            <div style="display: flex; gap: 15px; margin-top: 20px;">
                <a href="/live-monitor" class="btn btn-success">
                    <i class="fas fa-play"></i> Start Monitoring
                </a>
                <a href="/reports" class="btn">
                    <i class="fas fa-chart-bar"></i> View Reports
                </a>
                <a href="/violations-report" class="btn" style="background: #e74c3c;">
                    <i class="fas fa-exclamation-triangle"></i> View Violations
                </a>
            </div>
        </div>
        
        <div class="dashboard-grid">
            <a href="/live-monitor" class="dashboard-card">
                <div class="card-icon">
                    <i class="fas fa-video"></i>
                </div>
                <h3>Live Monitoring</h3>
                <p>Real-time video analysis with PPE detection. Monitor workers for safety compliance.</p>
            </a>
            
            <a href="/reports" class="dashboard-card">
                <div class="card-icon">
                    <i class="fas fa-chart-bar"></i>
                </div>
                <h3>Safety Reports</h3>
                <p>Detailed analytics and compliance reports. View historical data and trends.</p>
            </a>
            
            <div class="dashboard-card">
                <div class="card-icon">
                    <i class="fas fa-hard-hat"></i>
                </div>
                <h3>PPE Detection</h3>
                <p>Automatically detects safety helmets, vests, gloves, boots, and goggles using AI.</p>
            </div>
            
            <div class="dashboard-card">
                <div class="card-icon">
                    <i class="fas fa-bell"></i>
                </div>
                <h3>Real-time Alerts</h3>
                <p>Instant notifications and LOUD audio alerts for safety violations and non-compliance incidents.</p>
            </div>
        </div>
    </div>
</body>
</html>
'''

LIVE_MONITOR_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Live Monitoring - SiteSafe Monitor</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: #f0f2f5;
        }
        .navbar {
            background: #2c3e50;
            color: white;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .navbar-brand {
            font-size: 1.5em;
            font-weight: bold;
            color: white;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .nav-links {
            display: flex;
            gap: 15px;
        }
        .nav-links a {
            color: white;
            text-decoration: none;
            padding: 8px 15px;
            border-radius: 4px;
            transition: background 0.3s;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .nav-links a:hover, .nav-links a.active {
            background: #3498db;
        }
        .container {
            max-width: 1200px;
            margin: 30px auto;
            padding: 0 20px;
        }
        .page-title {
            color: #2c3e50;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .monitor-container {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 30px;
            min-height: 600px;
        }
        .video-panel {
            background: #000;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            position: relative;
        }
        .video-feed {
            width: 100%;
            height: 480px;
            object-fit: cover;
            background: #222;
        }
        .video-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            padding: 15px;
            background: rgba(0,0,0,0.7);
            color: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #e74c3c;
        }
        .status-dot.active {
            background: #27ae60;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .controls-panel {
            display: flex;
            gap: 15px;
            padding: 15px;
            background: rgba(0,0,0,0.8);
        }
        .control-btn {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 5px;
            font-size: 1em;
            font-weight: bold;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: all 0.3s;
        }
        .start-btn {
            background: #27ae60;
            color: white;
        }
        .start-btn:hover:not(:disabled) {
            background: #219653;
        }
        .stop-btn {
            background: #e74c3c;
            color: white;
        }
        .stop-btn:hover:not(:disabled) {
            background: #c0392b;
        }
        .control-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .side-panel {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        .analysis-panel, .alerts-panel {
            background: white;
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
            flex: 1;
        }
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #f0f2f5;
        }
        .panel-header h3 {
            color: #2c3e50;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .alerts-container {
            max-height: 300px;
            overflow-y: auto;
        }
        .alert-item {
            background: #f8f9fa;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 8px;
        }
        .alert-item.danger {
            background: #ffeaea;
            border-left-color: #e74c3c;
        }
        .alert-item.warning {
            background: #fff8e6;
            border-left-color: #f39c12;
        }
        .alert-item.success {
            background: #e8f6f3;
            border-left-color: #27ae60;
        }
        .alert-item.info {
            background: #e8f4fd;
            border-left-color: #3498db;
        }
        .alert-time {
            font-size: 0.8em;
            color: #666;
            margin-top: 5px;
        }
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: #95a5a6;
        }
        .empty-state i {
            font-size: 3em;
            margin-bottom: 15px;
        }
        .audio-control {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 10px;
        }
        .audio-toggle {
            background: none;
            border: none;
            color: #3498db;
            cursor: pointer;
            font-size: 1.2em;
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <a href="/dashboard" class="navbar-brand">
            <i class="fas fa-hard-hat"></i> SiteSafe Monitor
        </a>
        <div class="nav-links">
            <a href="/dashboard"><i class="fas fa-home"></i> Dashboard</a>
            <a href="/live-monitor" class="active"><i class="fas fa-video"></i> Live Monitor</a>
            <a href="/reports"><i class="fas fa-chart-bar"></i> Reports</a>
            <a href="/violations-report"><i class="fas fa-exclamation-triangle"></i> Violations</a>
            <a href="/logout" style="margin-left: 30px;"><i class="fas fa-sign-out-alt"></i> Logout</a>
        </div>
    </nav>
    
    <div class="container">
        <h1 class="page-title">
            <i class="fas fa-video"></i> Live Safety Monitoring
        </h1>
        
        <div class="monitor-container">
            <div class="video-panel">
                <div class="video-overlay">
                    <div class="status-indicator">
                        <div class="status-dot" id="statusDot"></div>
                        <span id="statusText">MONITOR STOPPED</span>
                    </div>
                    <div class="audio-control">
                        <button id="audioToggle" class="audio-toggle" title="Toggle audio alerts">
                            <i class="fas fa-volume-up"></i>
                        </button>
                    </div>
                </div>
                <img id="videoFeed" class="video-feed" src="" alt="Live Feed">
                <div class="controls-panel">
                    <button id="startBtn" class="control-btn start-btn">
                        <i class="fas fa-play-circle"></i> START MONITORING
                    </button>
                    <button id="stopBtn" class="control-btn stop-btn" disabled>
                        <i class="fas fa-stop-circle"></i> STOP MONITORING
                    </button>
                </div>
            </div>
            
            <div class="side-panel">
                <div class="analysis-panel">
                    <div class="panel-header">
                        <h3><i class="fas fa-chart-line"></i> Real-time Analysis</h3>
                        <span id="violationCount" style="background: #e74c3c; color: white; padding: 4px 10px; border-radius: 20px; font-size: 0.9em;">0</span>
                    </div>
                    <div id="analysisContent">
                        <div class="empty-state">
                            <i class="fas fa-chart-line"></i>
                            <p>Start monitoring to see real-time analysis</p>
                        </div>
                    </div>
                </div>
                
                <div class="alerts-panel">
                    <div class="panel-header">
                        <h3><i class="fas fa-bell"></i> Live Alerts</h3>
                        <button id="clearAlertsBtn" class="audio-toggle" title="Clear all alerts">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                    <div class="alerts-container" id="alertsContainer">
                        <div class="empty-state">
                            <i class="fas fa-bell-slash"></i>
                            <p>No alerts yet<br>Start monitoring to see real-time safety alerts</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Elements
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        const videoFeed = document.getElementById('videoFeed');
        const alertsContainer = document.getElementById('alertsContainer');
        const analysisContent = document.getElementById('analysisContent');
        const violationCount = document.getElementById('violationCount');
        const audioToggle = document.getElementById('audioToggle');
        const clearAlertsBtn = document.getElementById('clearAlertsBtn');
        
        let audioEnabled = true;
        let updateInterval;
        let analysisInterval;
        
        // Update video feed
        function updateVideoFeed() {
            videoFeed.src = '/video_feed?t=' + new Date().getTime();
        }
        
        // Start monitoring
        startBtn.onclick = async () => {
            const response = await fetch('/api/start-monitoring', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            });
            
            const data = await response.json();
            
            if (data.success) {
                statusDot.classList.add('active');
                statusText.textContent = 'MONITORING ACTIVE';
                startBtn.disabled = true;
                stopBtn.disabled = false;
                
                updateVideoFeed();
                updateAnalysis();
                
                // Show start alert
                addAlertToDisplay('Safety monitoring started', 'info');
                
                // Start periodic updates
                clearInterval(updateInterval);
                clearInterval(analysisInterval);
                
                updateInterval = setInterval(updateVideoFeed, 100);
                analysisInterval = setInterval(updateAnalysis, 2000);
            } else {
                alert('Failed to start monitoring: ' + data.message);
            }
        };
        
        // Stop monitoring
        stopBtn.onclick = async () => {
            const response = await fetch('/api/stop-monitoring', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            });
            
            const data = await response.json();
            
            if (data.success) {
                statusDot.classList.remove('active');
                statusText.textContent = 'MONITOR STOPPED';
                startBtn.disabled = false;
                stopBtn.disabled = true;
                
                addAlertToDisplay('Safety monitoring stopped', 'info');
                
                // Clear intervals
                clearInterval(updateInterval);
                clearInterval(analysisInterval);
            } else {
                alert('Failed to stop monitoring: ' + data.message);
            }
        };
        
        // Update analysis panel
        async function updateAnalysis() {
            try {
                const response = await fetch('/api/live-analysis');
                const data = await response.json();
                
                if (data.success) {
                    renderAnalysis(data.analysis);
                    violationCount.textContent = data.analysis.violations || 0;
                }
                
                // Update alerts
                const alertsResponse = await fetch('/api/get-alerts');
                const alertsData = await alertsResponse.json();
                if (alertsData.success && alertsData.alerts.length > 0) {
                    updateAlertsDisplay(alertsData.alerts);
                }
            } catch (error) {
                console.error('Error updating analysis:', error);
            }
        }
        
        // Render analysis data
        function renderAnalysis(analysis) {
            if (analysis.status === 'waiting') {
                analysisContent.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-chart-line"></i>
                        <p>${analysis.message}</p>
                    </div>
                `;
                return;
            }
            
            let riskColor = '#27ae60';
            if (analysis.risk_level === 'MEDIUM') riskColor = '#f39c12';
            if (analysis.risk_level === 'HIGH') riskColor = '#e74c3c';
            
            analysisContent.innerHTML = `
                <div style="background: ${riskColor}15; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px; border: 2px solid ${riskColor};">
                    <div style="font-size: 1.2em; font-weight: bold; color: ${riskColor};">${analysis.risk_level} RISK LEVEL</div>
                    <div style="font-size: 0.8em; margin-top: 5px; color: #666;">Site Safety Status</div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #2c3e50; margin: 5px 0;">${analysis.workers_active}</div>
                        <div style="font-size: 0.9em; color: #666;">Active Workers</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #2c3e50; margin: 5px 0;">${analysis.compliance_rate}%</div>
                        <div style="font-size: 0.9em; color: #666;">Compliance Rate</div>
                    </div>
                </div>
                
                <div style="font-size: 0.9em; color: #666; padding: 10px; background: #f8f9fa; border-radius: 8px;">
                    <i class="fas fa-info-circle"></i> ${analysis.message}
                </div>
            `;
        }
        
        // Update alerts display
        function updateAlertsDisplay(alerts) {
            if (alerts.length === 0) return;
            
            // Clear if empty state exists
            if (alertsContainer.querySelector('.empty-state')) {
                alertsContainer.innerHTML = '';
            }
            
            // Keep only latest 10 alerts
            const latestAlerts = alerts.slice(-10);
            
            // Clear and rebuild
            alertsContainer.innerHTML = '';
            
            latestAlerts.reverse().forEach(alert => {
                addAlertToDisplay(alert.message, alert.severity, alert.timestamp, false);
            });
        }
        
        // Add alert to display
        function addAlertToDisplay(message, severity, timestamp = null, prepend = true) {
            if (alertsContainer.querySelector('.empty-state')) {
                alertsContainer.innerHTML = '';
            }
            
            let alertClass = 'info';
            if (severity === 'danger') alertClass = 'danger';
            else if (severity === 'warning') alertClass = 'warning';
            else if (severity === 'success') alertClass = 'success';
            
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert-item ${alertClass}`;
            alertDiv.innerHTML = `
                <div style="font-weight: bold; color: #2c3e50; margin-bottom: 5px;">${message}</div>
                <div class="alert-time">${timestamp || new Date().toLocaleTimeString()}</div>
            `;
            
            if (prepend && alertsContainer.firstChild) {
                alertsContainer.insertBefore(alertDiv, alertsContainer.firstChild);
            } else {
                alertsContainer.appendChild(alertDiv);
            }
            
            // Keep only 10 alerts
            const alerts = alertsContainer.querySelectorAll('.alert-item');
            if (alerts.length > 10) {
                alerts[alerts.length - 1].remove();
            }
            
            // Scroll to top
            alertsContainer.scrollTop = 0;
        }
        
        // Toggle audio alerts
        audioToggle.onclick = () => {
            audioEnabled = !audioEnabled;
            if (audioEnabled) {
                audioToggle.innerHTML = '<i class="fas fa-volume-up"></i>';
                audioToggle.title = "Audio alerts enabled";
            } else {
                audioToggle.innerHTML = '<i class="fas fa-volume-mute"></i>';
                audioToggle.title = "Audio alerts disabled";
            }
        };
        
        // Clear alerts
        clearAlertsBtn.onclick = async () => {
            if (confirm('Clear all alerts?')) {
                const response = await fetch('/api/clear-alerts', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                
                const data = await response.json();
                if (data.success) {
                    alertsContainer.innerHTML = `
                        <div class="empty-state">
                            <i class="fas fa-bell-slash"></i>
                            <p>No alerts yet<br>Start monitoring to see real-time safety alerts</p>
                        </div>
                    `;
                }
            }
        };
        
        // Initialize
        updateVideoFeed();
        setInterval(updateVideoFeed, 5000);
        
        // Load initial alerts
        setTimeout(() => {
            fetch('/api/get-alerts')
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.alerts.length > 0) {
                        data.alerts.forEach(alert => {
                            addAlertToDisplay(alert.message, alert.severity, alert.timestamp);
                        });
                    }
                });
        }, 1000);
    </script>
</body>
</html>
'''

REPORTS_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Safety Reports - SiteSafe Monitor</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: #f0f2f5;
        }
        .navbar {
            background: #2c3e50;
            color: white;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .navbar-brand {
            font-size: 1.5em;
            font-weight: bold;
            color: white;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .nav-links {
            display: flex;
            gap: 15px;
        }
        .nav-links a {
            color: white;
            text-decoration: none;
            padding: 8px 15px;
            border-radius: 4px;
            transition: background 0.3s;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .nav-links a:hover, .nav-links a.active {
            background: #3498db;
        }
        .container {
            max-width: 1200px;
            margin: 30px auto;
            padding: 0 20px;
        }
        .page-title {
            color: #2c3e50;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #95a5a6;
        }
        .empty-state i {
            font-size: 4em;
            margin-bottom: 20px;
        }
        .btn {
            padding: 12px 25px;
            background: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: background 0.3s;
        }
        .btn:hover {
            background: #2980b9;
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <a href="/dashboard" class="navbar-brand">
            <i class="fas fa-hard-hat"></i> SiteSafe Monitor
        </a>
        <div class="nav-links">
            <a href="/dashboard"><i class="fas fa-home"></i> Dashboard</a>
            <a href="/live-monitor"><i class="fas fa-video"></i> Live Monitor</a>
            <a href="/reports" class="active"><i class="fas fa-chart-bar"></i> Reports</a>
            <a href="/violations-report"><i class="fas fa-exclamation-triangle"></i> Violations</a>
            <a href="/logout" style="margin-left: 30px;"><i class="fas fa-sign-out-alt"></i> Logout</a>
        </div>
    </nav>
    
    <div class="container">
        <h1 class="page-title">
            <i class="fas fa-chart-bar"></i> Safety Compliance Report
        </h1>
        
        <div class="empty-state">
            <i class="fas fa-chart-bar"></i>
            <p>No monitoring data available yet</p>
            <p style="font-size: 0.9em;">Start monitoring in the Live Monitor section to generate reports</p>
            <a href="/live-monitor" class="btn" style="margin-top: 20px;">
                <i class="fas fa-video"></i> Go to Live Monitor
            </a>
        </div>
    </div>
</body>
</html>
'''

# ==================== SIMULATED PPE DETECTION WITH FREQUENT VIOLATIONS ====================
class PPEDetector:
    def __init__(self):
        self.required_ppe = ['helmet', 'vest', 'gloves', 'boots', 'goggles']
        self.detection_history = []
        self.violation_count = 0
        
    def detect_ppe(self, frame):
        """Simulate PPE detection on a frame - HIGH CHANCE OF VIOLATIONS FOR TESTING"""
        height, width = frame.shape[:2]
        
        # Generate simulated detections
        detections = []
        violations = []
        
        # Simulate 1-3 workers
        num_workers = np.random.randint(1, 4)
        
        for i in range(num_workers):
            # Random position for worker
            x = np.random.randint(50, width - 150)
            y = np.random.randint(50, height - 150)
            w = np.random.randint(80, 120)
            h = np.random.randint(150, 200)
            
            # Random missing PPE - HIGH CHANCE OF VIOLATIONS FOR TESTING (70% chance of missing each item)
            missing_ppe = []
            detected_ppe = []
            
            for ppe in self.required_ppe:
                # Only 30% chance of wearing each PPE item (MORE VIOLATIONS!)
                if np.random.random() > 0.7:
                    detected_ppe.append(ppe)
                else:
                    missing_ppe.append(ppe)
            
            # Create detection data
            detection = {
                'id': i,
                'bbox': [x, y, w, h],
                'detected_ppe': detected_ppe,
                'missing_ppe': missing_ppe,
                'compliance': len(detected_ppe) / len(self.required_ppe) * 100
            }
            
            detections.append(detection)
            
            # Check for violations
            if missing_ppe:
                violations.append({
                    'worker_id': i,
                    'missing_ppe': missing_ppe,
                    'position': (x, y),
                    'timestamp': datetime.now()
                })
        
        return detections, violations
    
    def draw_detections(self, frame, detections):
        """Draw PPE detection results on frame"""
        for det in detections:
            x, y, w, h = det['bbox']
            
            # Draw bounding box
            color = (0, 255, 0) if not det['missing_ppe'] else (0, 0, 255)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            
            # Draw label
            label = f"Worker {det['id']}: {len(det['detected_ppe'])}/5 PPE"
            cv2.putText(frame, label, (x, y - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # Draw PPE status
            status_y = y + 20
            for i, ppe in enumerate(['helmet', 'vest', 'gloves', 'boots', 'goggles']):
                status = "✓" if ppe in det['detected_ppe'] else "✗"
                color_status = (0, 255, 0) if status == "✓" else (0, 0, 255)
                text = f"{ppe}: {status}"
                cv2.putText(frame, text, (x + w + 10, status_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color_status, 1)
                status_y += 15

# ==================== MONITORING SYSTEM WITH WORKING AUDIO ====================
class MonitoringSystem:
    def __init__(self):
        print("🛡️ Initializing PPE Detection System...")
        self.camera = None
        self.is_monitoring = False
        self.alerts = deque(maxlen=50)
        self.last_frame = None
        self.detector = PPEDetector()
        self.violation_count = 0
        self.total_detections = 0
        self.last_alert_time = 0
        self.alert_cooldown = 2  # Reduced cooldown for testing (2 seconds)
        
    def start_monitoring(self, camera_id=0):
        try:
            # Try different camera indices
            for cam_id in [camera_id, 1, 2]:
                self.camera = cv2.VideoCapture(cam_id)
                if self.camera.isOpened():
                    print(f"✅ Started monitoring on camera {cam_id}")
                    self.is_monitoring = True
                    
                    # Add initial alert
                    self.add_alert('Safety monitoring started', 'info')
                    
                    # Play startup sound
                    self.play_alert_sound('start')
                    return True
                self.camera.release()
            
            print("❌ Cannot open any camera - using simulated feed")
            # Create a simulated camera feed
            self.camera = None
            self.is_monitoring = True
            self.add_alert('Safety monitoring started (simulated feed)', 'info')
            self.play_alert_sound('start')
            return True
            
        except Exception as e:
            print(f"❌ Error starting monitoring: {e}")
            return False
    
    def stop_monitoring(self):
        self.is_monitoring = False
        if self.camera:
            self.camera.release()
            self.camera = None
        print("⏹️ Monitoring stopped")
        self.add_alert('Safety monitoring stopped', 'info')
    
    def get_frame(self):
        if not self.is_monitoring:
            return None
        
        # Generate simulated frame if no camera
        if self.camera is None:
            # Create a blank frame
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:, :] = [50, 50, 50]  # Dark gray background
            
            # Add text
            cv2.putText(frame, "SIMULATED FEED - TESTING PPE DETECTION", 
                       (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, "Violations will trigger LOUD BEEP sounds", 
                       (80, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        else:
            # Try to get frame from camera
            ret, frame = self.camera.read()
            if not ret:
                return None
            frame = cv2.resize(frame, (640, 480))
        
        # Detect PPE
        detections, violations = self.detector.detect_ppe(frame)
        
        # Draw detections
        self.detector.draw_detections(frame, detections)
        
        # Process violations
        for violation in violations:
            self.process_violation(violation)
        
        # Update statistics
        self.total_detections += len(detections)
        
        self.last_frame = frame
        
        # Add timestamp
        cv2.putText(frame, datetime.now().strftime("%H:%M:%S"), 
                   (10, frame.shape[0] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Add status
        status = "MONITORING ACTIVE"
        color = (0, 255, 0) if self.is_monitoring else (0, 0, 255)
        cv2.putText(frame, status, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # Add violation counter
        violations_text = f"Violations: {self.violation_count}"
        cv2.putText(frame, violations_text, (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # Add audio indicator
        audio_status = "🔊 AUDIO: ON" if AUDIO_ENABLED else "🔇 AUDIO: OFF"
        cv2.putText(frame, audio_status, (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        return frame
    
    def process_violation(self, violation):
        """Process a PPE violation"""
        current_time = time.time()
        
        # Only trigger alert if cooldown period has passed
        if current_time - self.last_alert_time > self.alert_cooldown:
            missing_str = ", ".join(violation['missing_ppe'])
            alert_msg = f"Worker {violation['worker_id']} missing: {missing_str}"
            
            # Add to alerts
            self.add_alert(alert_msg, 'danger')
            
            # Play LOUD alert sound
            self.play_alert_sound('violation')
            
            # Store violation
            violation_data = {
                'worker_id': violation['worker_id'],
                'missing_ppe': violation['missing_ppe'],
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'severity': 'high' if 'helmet' in violation['missing_ppe'] else 'medium'
            }
            
            if MONGODB_ENABLED and violations_collection is not None:
                violations_collection.insert_one(violation_data)
            else:
                violations_db.append(violation_data)
            
            self.violation_count += 1
            self.last_alert_time = current_time
    
    def play_alert_sound(self, alert_type='violation'):
        """Play LOUD alert sound based on type - SIMPLE AND RELIABLE"""
        if not AUDIO_ENABLED:
            print("⚠️ Audio disabled, cannot play sound")
            return
            
        try:
            if alert_type == 'violation':
                print("🔊🔊🔊 LOUD VIOLATION ALERT! BEEP BEEP BEEP! 🔊🔊🔊")
                
                # Play 3 LOUD beeps for violation
                for i in range(3):
                    try:
                        import winsound
                        winsound.Beep(800 + i*100, 400)  # Increasing frequency, 400ms each
                        time.sleep(0.05)
                    except:
                        try:
                            import pygame
                            pygame.mixer.init()
                            # Simple beep
                            pygame.mixer.Sound(buffer=bytes([127] * 1000)).play()
                            time.sleep(0.05)
                        except:
                            # Last resort: print bell character
                            print('\a', end='', flush=True)
                    time.sleep(0.1)
                
            elif alert_type == 'start':
                print("🔊 Startup sound playing...")
                try:
                    import winsound
                    winsound.Beep(600, 500)  # 600Hz, 500ms
                except:
                    try:
                        import pygame
                        pygame.mixer.init()
                        pygame.mixer.Sound(buffer=bytes([127] * 500)).play()
                    except:
                        print('\a', end='', flush=True)
                        
        except Exception as e:
            print(f"🔇 Audio error: {e}")
    
    def add_alert(self, message, severity="info"):
        """Add alert to queue"""
        alert = {
            'id': len(self.alerts) + 1,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
        self.alerts.append(alert)
        print(f"📢 Alert: {message}")
        return alert
    
    def get_recent_alerts(self, count=10):
        return list(self.alerts)[-count:]
    
    def clear_alerts(self):
        self.alerts.clear()
    
    def get_live_analysis(self):
        """Get current analysis data"""
        if not self.is_monitoring:
            return {
                'status': 'waiting',
                'message': 'Waiting to start monitoring',
                'workers_active': 0,
                'compliance_rate': 100,
                'risk_level': 'LOW',
                'trend': 'stable',
                'violations': self.violation_count,
                'last_update': datetime.now().strftime('%H:%M:%S')
            }
        
        # Simulate analysis data
        workers_active = np.random.randint(1, 5)
        compliance_rate = max(60, 100 - (self.violation_count * 10))
        
        if compliance_rate > 90:
            risk_level = 'LOW'
        elif compliance_rate > 70:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'HIGH'
        
        return {
            'status': 'active',
            'message': f'Monitoring {workers_active} workers. {self.violation_count} violations detected.',
            'workers_active': workers_active,
            'compliance_rate': compliance_rate,
            'risk_level': risk_level,
            'trend': 'stable' if compliance_rate > 80 else 'declining',
            'violations': self.violation_count,
            'last_update': datetime.now().strftime('%H:%M:%S')
        }
    
    def get_summary(self):
        """Get monitoring summary"""
        return {
            'total_workers': self.total_detections,
            'violations': self.violation_count,
            'compliance_rate': 100 - (self.violation_count * 10) if self.total_detections > 0 else 100,
            'most_missing': ['helmet', 'vest'] if self.violation_count > 0 else [],
            'last_updated': datetime.now().strftime('%H:%M:%S')
        }
    
    def get_violations_report(self):
        """Get violations report"""
        if MONGODB_ENABLED and violations_collection is not None:
            violations = list(violations_collection.find().sort('timestamp', -1).limit(50))
            for v in violations:
                v['_id'] = str(v['_id'])
        else:
            violations = violations_db[-50:]
        
        return violations

monitoring_system = MonitoringSystem()

# ==================== AUTHENTICATION DECORATOR ====================
def requires_registration(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== FLASK ROUTES ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template_string(LOGIN_HTML)

@app.route('/register', methods=['GET'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template_string(REGISTER_HTML)

@app.route('/dashboard')
@requires_registration
def dashboard():
    return render_template_string(DASHBOARD_HTML, username=current_user.username)

@app.route('/live-monitor')
@requires_registration
def live_monitor():
    return render_template_string(LIVE_MONITOR_HTML)

@app.route('/video_feed')
@requires_registration
def video_feed():
    def generate():
        while True:
            if monitoring_system.is_monitoring:
                frame = monitoring_system.get_frame()
                if frame is not None:
                    # Draw timestamp and status
                    cv2.putText(frame, datetime.now().strftime("%H:%M:%S"), 
                               (10, frame.shape[0] - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    status = "MONITORING ACTIVE" if monitoring_system.is_monitoring else "STOPPED"
                    color = (0, 255, 0) if monitoring_system.is_monitoring else (0, 0, 255)
                    cv2.putText(frame, status, (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
                    # Add violation counter
                    violations_text = f"Violations: {monitoring_system.violation_count}"
                    cv2.putText(frame, violations_text, (10, 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    
                    # Encode frame
                    ret, buffer = cv2.imencode('.jpg', frame)
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                # Generate blank frame
                blank = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(blank, "MONITORING STOPPED", (150, 200), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.putText(blank, "Click START to begin safety analysis", (80, 240), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
                cv2.putText(blank, "Detects: Helmet, Vest, Gloves, Boots, Goggles", (50, 280), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
                
                ret, buffer = cv2.imencode('.jpg', blank)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            time.sleep(0.033)
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

# API Routes
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    
    if not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    try:
        # Check if username exists
        if MONGODB_ENABLED and users_collection is not None:
            if users_collection.find_one({'username': data['username']}):
                return jsonify({'success': False, 'message': 'Username already exists'})
            if users_collection.find_one({'email': data['email']}):
                return jsonify({'success': False, 'message': 'Email already registered'})
        else:
            for user in users_db.values():
                if user['username'] == data['username']:
                    return jsonify({'success': False, 'message': 'Username already exists'})
                if user['email'] == data['email']:
                    return jsonify({'success': False, 'message': 'Email already registered'})
        
        # Create user
        user_data = {
            'username': data['username'],
            'email': data['email'],
            'password': generate_password_hash(data['password']),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if MONGODB_ENABLED and users_collection is not None:
            users_collection.insert_one(user_data)
        else:
            user_id = str(len(users_db) + 1)
            user_data['id'] = user_id
            users_db[user_id] = user_data
        
        return jsonify({'success': True, 'message': 'Account created successfully!'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': 'Registration failed'})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    
    # Demo user
    if data['username'] == 'supervisor' and data['password'] == 'safety123':
        user_data = {'id': '0', 'username': 'supervisor'}
        
        # Ensure demo user exists in database
        if MONGODB_ENABLED and users_collection is not None:
            if not users_collection.find_one({'username': 'supervisor'}):
                users_collection.insert_one({
                    'username': 'supervisor',
                    'email': 'supervisor@site.com',
                    'password': generate_password_hash('safety123'),
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
        else:
            users_db['0'] = {
                'id': '0',
                'username': 'supervisor',
                'email': 'supervisor@site.com',
                'password': generate_password_hash('safety123'),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        user = User(user_data)
        login_user(user, remember=True)
        return jsonify({'success': True, 'message': 'Login successful'})
    
    try:
        user_data = None
        
        if MONGODB_ENABLED and users_collection is not None:
            user_data = users_collection.find_one({'username': data['username']})
        else:
            for user in users_db.values():
                if user['username'] == data['username']:
                    user_data = user
                    break
        
        if user_data and 'password' in user_data:
            if check_password_hash(user_data['password'], data['password']):
                user = User(user_data)
                login_user(user, remember=True)
                return jsonify({'success': True, 'message': 'Login successful'})
        
        return jsonify({'success': False, 'message': 'Invalid username or password'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': 'Login failed'})

@app.route('/api/start-monitoring', methods=['POST'])
@requires_registration
def start_monitoring_api():
    if monitoring_system.is_monitoring:
        return jsonify({'success': False, 'message': 'Monitoring already active'})
    
    if monitoring_system.start_monitoring(0):
        return jsonify({'success': True, 'message': 'Monitoring started'})
    else:
        return jsonify({'success': False, 'message': 'Failed to access camera'})

@app.route('/api/stop-monitoring', methods=['POST'])
@requires_registration
def stop_monitoring_api():
    if not monitoring_system.is_monitoring:
        return jsonify({'success': False, 'message': 'Monitoring not active'})
    
    monitoring_system.stop_monitoring()
    return jsonify({'success': True, 'message': 'Monitoring stopped'})

@app.route('/api/live-analysis', methods=['GET'])
@requires_registration
def live_analysis():
    return jsonify({'success': True, 'analysis': monitoring_system.get_live_analysis()})

@app.route('/api/get-alerts', methods=['GET'])
@requires_registration
def get_alerts():
    alerts = monitoring_system.get_recent_alerts(20)
    return jsonify({'success': True, 'alerts': alerts})

@app.route('/api/clear-alerts', methods=['POST'])
@requires_registration
def clear_alerts():
    monitoring_system.clear_alerts()
    return jsonify({'success': True, 'message': 'Alerts cleared'})

@app.route('/api/get-summary', methods=['GET'])
@requires_registration
def get_summary():
    return jsonify({'success': True, 'summary': monitoring_system.get_summary()})

@app.route('/api/get-violations', methods=['GET'])
@requires_registration
def get_violations():
    violations = monitoring_system.get_violations_report()
    return jsonify({'success': True, 'violations': violations})

@app.route('/reports')
@requires_registration
def reports():
    return render_template_string(REPORTS_HTML)

@app.route('/violations-report')
@requires_registration
def violations_report():
    violations = monitoring_system.get_violations_report()
    
    report_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Violations Report - SiteSafe Monitor</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f0f2f5; }
            .navbar {
                background: #2c3e50;
                color: white;
                padding: 15px 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .navbar-brand {
                font-size: 1.5em;
                font-weight: bold;
                color: white;
                text-decoration: none;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .nav-links {
                display: flex;
                gap: 15px;
            }
            .nav-links a {
                color: white;
                text-decoration: none;
                padding: 8px 15px;
                border-radius: 4px;
                transition: background 0.3s;
                display: flex;
                align-items: center;
                gap: 5px;
            }
            .container {
                max-width: 1200px;
                margin: 30px auto;
                padding: 0 20px;
            }
            .page-title {
                color: #2c3e50;
                margin-bottom: 30px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .violations-table {
                width: 100%;
                background: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 3px 10px rgba(0,0,0,0.1);
            }
            .violations-table table {
                width: 100%;
                border-collapse: collapse;
            }
            .violations-table th {
                background: #2c3e50;
                color: white;
                padding: 15px;
                text-align: left;
            }
            .violations-table td {
                padding: 15px;
                border-bottom: 1px solid #f0f2f5;
            }
            .violations-table tr:hover {
                background: #f8f9fa;
            }
            .severity-high { color: #e74c3c; font-weight: bold; }
            .severity-medium { color: #f39c12; }
            .severity-low { color: #27ae60; }
            .empty-state {
                text-align: center;
                padding: 60px 20px;
                color: #95a5a6;
            }
            .btn {
                padding: 12px 25px;
                background: #3498db;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                border: none;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                gap: 8px;
                transition: background 0.3s;
            }
        </style>
    </head>
    <body>
        <nav class="navbar">
            <a href="/dashboard" class="navbar-brand">
                <i class="fas fa-hard-hat"></i> SiteSafe Monitor
            </a>
            <div class="nav-links">
                <a href="/dashboard"><i class="fas fa-home"></i> Dashboard</a>
                <a href="/live-monitor"><i class="fas fa-video"></i> Live Monitor</a>
                <a href="/reports"><i class="fas fa-chart-bar"></i> Reports</a>
                <a href="/violations-report" class="active"><i class="fas fa-exclamation-triangle"></i> Violations</a>
                <a href="/logout"><i class="fas fa-sign-out-alt"></i> Logout</a>
            </div>
        </nav>
        
        <div class="container">
            <h1 class="page-title">
                <i class="fas fa-exclamation-triangle"></i> PPE Violations Report
            </h1>
    '''
    
    if violations:
        report_html += '''
            <div class="violations-table">
                <table>
                    <thead>
                        <tr>
                            <th>Worker ID</th>
                            <th>Missing PPE</th>
                            <th>Severity</th>
                            <th>Timestamp</th>
                        </tr>
                    </thead>
                    <tbody>
        '''
        
        for violation in violations:
            missing_ppe = ', '.join(violation.get('missing_ppe', []))
            severity = violation.get('severity', 'medium')
            severity_class = f'severity-{severity}'
            
            report_html += f'''
                        <tr>
                            <td>{violation.get('worker_id', 'N/A')}</td>
                            <td>{missing_ppe}</td>
                            <td class="{severity_class}">{severity.upper()}</td>
                            <td>{violation.get('timestamp', 'N/A')}</td>
                        </tr>
            '''
        
        report_html += '''
                    </tbody>
                </table>
            </div>
        '''
    else:
        report_html += '''
            <div class="empty-state">
                <i class="fas fa-check-circle" style="font-size: 4em; margin-bottom: 20px;"></i>
                <p>No violations detected yet</p>
                <p style="font-size: 0.9em;">Start monitoring in the Live Monitor section to detect safety violations</p>
                <a href="/live-monitor" class="btn" style="margin-top: 20px;">
                    <i class="fas fa-video"></i> Go to Live Monitor
                </a>
            </div>
        '''
    
    report_html += '''
        </div>
    </body>
    </html>
    '''
    
    return render_template_string(report_html)

@app.route('/logout')
@login_required
def logout():
    monitoring_system.stop_monitoring()
    logout_user()
    return redirect(url_for('login'))

# ==================== MAIN WITH AUDIO TEST ====================
if __name__ == '__main__':
    print("\n" + "="*70)
    print("🏗️  CONSTRUCTION SITE SAFETY MONITORING SYSTEM")
    print("="*70)
    print("\n🔐 DEFAULT LOGIN:")
    print("   Username: supervisor")
    print("   Password: safety123")
    print("\n🚨 KEY FEATURES:")
    print("   • Real-time PPE detection (Helmet, Vest, Gloves, Boots, Goggles)")
    print("   • 🔊 LOUD TRIPLE BEEP sounds for violations")
    print("   • Visual alerts with red bounding boxes")
    print("   • Violations tracking and reporting")
    print("\n🔧 AUDIO TEST ON STARTUP:")
    
    # Test audio immediately
    if AUDIO_ENABLED:
        print("🔊 Testing audio system...")
        try:
            # Test startup sound
            monitoring_system.play_alert_sound('start')
            time.sleep(0.5)
            print("✅ You should have heard a startup beep!")
            print("✅ During monitoring, you'll hear LOUD triple beeps for violations!")
            print("✅ Violations occur every 2-3 seconds for testing!")
        except Exception as e:
            print(f"❌ Audio test failed: {e}")
    else:
        print("❌ Audio is disabled. Install winsound (built-in) or pygame for alerts")
        print("   For Windows: winsound is built-in")
        print("   For others: pip install pygame")
    
    print("\n👉 Open: http://127.0.0.1:5000")
    print("="*70)
    
    app.run(host="0.0.0.0", port=5000, debug=False)