#!/usr/bin/env python3
"""
Startup script for EmoBot OAuth server
"""
import os
import sys
import asyncio
import subprocess
from pathlib import Path

def check_requirements():
    """Check if all required packages are installed"""
    required_packages = [
        'fastapi', 'uvicorn', 'authlib', 'itsdangerous', 
        'jinja2', 'python-multipart', 'asyncpg', 'python-dotenv'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for pkg in missing_packages:
            print(f"   - {pkg}")
        print("\n💡 Install missing packages with:")
        print("   pip install -r requirements.txt")
        return False
    
    print("✅ All required packages are installed")
    return True

def check_env_file():
    """Check if .env file exists and has required variables"""
    env_path = Path('.env')
    if not env_path.exists():
        print("❌ .env file not found")
        print("💡 Copy .env.example to .env and configure your OAuth credentials:")
        print("   cp .env.example .env")
        return False
    
    # Check for required environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = [
        'DATABASE_URL',
        'SESSION_SECRET_KEY',
        'DISCORD_CLIENT_ID',
        'DISCORD_CLIENT_SECRET'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 Update your .env file with the missing variables")
        return False
    
    print("✅ Environment configuration looks good")
    return True

async def test_database_connection():
    """Test database connection"""
    try:
        from database import init_db
        await init_db()
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("💡 Check your DATABASE_URL and ensure PostgreSQL is running")
        return False

def start_server():
    """Start the OAuth web server"""
    print("🚀 Starting EmoBot OAuth server...")
    print("📱 Web interface will be available at: http://localhost:8000")
    print("🛑 Press Ctrl+C to stop the server\n")
    
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "web_server:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n👋 OAuth server stopped")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")

async def main():
    """Main startup function"""
    print("🤖 EmoBot OAuth Setup")
    print("=" * 30)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check environment configuration
    if not check_env_file():
        sys.exit(1)
    
    # Test database connection
    if not await test_database_connection():
        sys.exit(1)
    
    print("\n" + "=" * 30)
    print("✅ All checks passed!")
    print("=" * 30 + "\n")
    
    # Start the server
    start_server()

if __name__ == "__main__":
    asyncio.run(main())