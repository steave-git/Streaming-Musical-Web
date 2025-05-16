import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    YOUTUBE_API_KEY = os.getenv('AIzaSyBspGGIFsSmQII7MrYCS9c1upgRqle8se4')
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key')