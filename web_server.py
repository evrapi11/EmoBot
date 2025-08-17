import os
import secrets
from typing import Optional
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from dotenv import load_dotenv
from database import UserProfile, init_db

load_dotenv()

app = FastAPI(title="EmoBot OAuth", description="OAuth authentication for EmoBot")

app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv('SESSION_SECRET_KEY', secrets.token_urlsafe(32))
)

templates = Jinja2Templates(directory="templates")

oauth = OAuth()

oauth.register(
    name='discord',
    client_id=os.getenv('DISCORD_CLIENT_ID'),
    client_secret=os.getenv('DISCORD_CLIENT_SECRET'),
    client_kwargs={'scope': 'identify email'},
    server_metadata_url='https://discord.com/.well-known/openid_configuration',
)

oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    client_kwargs={'scope': 'openid email profile'},
    server_metadata_url='https://accounts.google.com/.well-known/openid_configuration',
)

oauth.register(
    name='github',
    client_id=os.getenv('GITHUB_CLIENT_ID'),
    client_secret=os.getenv('GITHUB_CLIENT_SECRET'),
    client_kwargs={'scope': 'user:email'},
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize',
    api_base_url='https://api.github.com/',
)

async def get_current_user(request: Request) -> Optional[dict]:
    return request.session.get('user')

async def require_auth(current_user: Optional[dict] = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return current_user

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, current_user: Optional[dict] = Depends(get_current_user)):
    if current_user:
        return RedirectResponse(url="/profile")
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request, current_user: dict = Depends(require_auth)):
    user_profile = None
    if current_user.get('discord_id'):
        user_profile = await UserProfile.find_by_discord_id(current_user['discord_id'])
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user,
        "profile": user_profile
    })

@app.get("/login/{provider}")
async def login(request: Request, provider: str):
    if provider not in ['discord', 'google', 'github']:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    client = oauth.create_client(provider)
    redirect_uri = request.url_for('auth_callback', provider=provider)
    return await client.authorize_redirect(request, redirect_uri)

@app.get("/auth/{provider}")
async def auth_callback(request: Request, provider: str):
    if provider not in ['discord', 'google', 'github']:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    client = oauth.create_client(provider)
    token = await client.authorize_access_token(request)
    
    user_info = {}
    
    if provider == 'discord':
        user_data = token.get('userinfo') or await client.get('users/@me', token=token)
        if hasattr(user_data, 'json'):
            user_data = user_data.json()
        user_info = {
            'id': user_data['id'],
            'discord_id': user_data['id'],
            'username': user_data['username'],
            'email': user_data.get('email'),
            'avatar': user_data.get('avatar'),
            'provider': 'discord'
        }
    
    elif provider == 'google':
        user_data = token.get('userinfo')
        user_info = {
            'id': user_data['sub'],
            'username': user_data['name'],
            'email': user_data['email'],
            'avatar': user_data.get('picture'),
            'provider': 'google'
        }
    
    elif provider == 'github':
        user_data = await client.get('user', token=token)
        user_data = user_data.json()
        user_info = {
            'id': str(user_data['id']),
            'username': user_data['login'],
            'email': user_data.get('email'),
            'avatar': user_data.get('avatar_url'),
            'provider': 'github'
        }
    
    request.session['user'] = user_info
    return RedirectResponse(url="/profile")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@app.get("/api/user")
async def get_user_api(current_user: dict = Depends(require_auth)):
    return current_user

@app.get("/api/profile")
async def get_profile_api(current_user: dict = Depends(require_auth)):
    if not current_user.get('discord_id'):
        raise HTTPException(status_code=400, detail="Discord account required for profile access")
    
    user_profile = await UserProfile.find_by_discord_id(current_user['discord_id'])
    if not user_profile:
        return {"message": "No profile found"}
    
    return {
        "discord_id": user_profile.discord_id,
        "username": user_profile.username,
        "games": user_profile.games,
        "artists": user_profile.artists,
        "interests": user_profile.interests,
        "scanning_enabled": user_profile.scanning_enabled
    }

@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"}
        )
    return RedirectResponse(url="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "web_server:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True
    )