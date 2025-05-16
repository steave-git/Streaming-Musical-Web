from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from pytube import YouTube, Search
from io import BytesIO
import os
from dotenv import load_dotenv
import googleapiclient.discovery
from urllib.parse import quote
from datetime import timedelta
import re
import time
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Initialisation de l'application Flask
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv("SECRET_KEY") or "AIzaSyBspGGIFsSmQII7MrYCS9c1upgRqle8se4"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB limit

# Configuration YouTube
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
if not YOUTUBE_API_KEY:
    raise ValueError("La clé API YouTube est manquante dans les variables d'environnement")

# Décorateur pour les routes protégées
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter pour accéder à cette page', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Initialisation de la base de données
def init_db():
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Table utilisateurs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table playlists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Table pour les éléments de playlist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT NOT NULL,
                thumbnail TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES playlists (id)
            )
        ''')
        
        # Table pour les favoris
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                video_id TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, video_id)
            )
        ''')
        
        # Table cache pour les vidéos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                thumbnail TEXT NOT NULL,
                channel TEXT NOT NULL,
                duration TEXT NOT NULL,
                views TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
    except Exception as e:
        app.logger.error(f"Erreur initialisation DB: {str(e)}")
        raise e
    finally:
        conn.close()

# Initialisation au démarrage
init_db()

# Service YouTube
def get_youtube_service():
    return googleapiclient.discovery.build(
        'youtube',
        'v3',
        developerKey=YOUTUBE_API_KEY,
        static_discovery=False
    )

# Helper pour parser la durée
def parse_duration(duration):
    """Convertit la durée ISO 8601 en format MM:SS"""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return '00:00'
    
    hours, minutes, seconds = match.groups()
    hours = int(hours) if hours else 0
    minutes = int(minutes) if minutes else 0
    seconds = int(seconds) if seconds else 0
    
    total_minutes = hours * 60 + minutes
    return f"{total_minutes:02d}:{seconds:02d}"

# Helper pour formater la date
def format_date(published_at):
    """Formate la date en texte lisible"""
    from datetime import datetime
    if not published_at:
        return ""
    
    pub_date = datetime.strptime(published_at, '%Y-%m-%dT%H:%M:%SZ')
    now = datetime.utcnow()
    delta = now - pub_date
    
    if delta.days == 0:
        return "Aujourd'hui"
    elif delta.days < 7:
        return f"Il y a {delta.days} jour{'s' if delta.days > 1 else ''}"
    elif delta.days < 30:
        weeks = delta.days // 7
        return f"Il y a {weeks} semaine{'s' if weeks > 1 else ''}"
    elif delta.days < 365:
        months = delta.days // 30
        return f"Il y a {months} mois"
    else:
        years = delta.days // 365
        return f"Il y a {years} an{'s' if years > 1 else ''}"

# Routes d'authentification
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Veuillez remplir tous les champs', 'error')
            return redirect(url_for('login'))
        
        try:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, password FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session.permanent = True
                
                next_page = request.args.get('next')
                flash('Connexion réussie!', 'success')
                return redirect(next_page or url_for('home'))
            else:
                flash('Identifiants incorrects', 'error')
        except Exception as e:
            app.logger.error(f"Erreur connexion: {str(e)}")
            flash('Une erreur est survenue lors de la connexion', 'error')
        finally:
            conn.close()
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validation
        errors = []
        if not username or len(username) < 3:
            errors.append('Le nom d\'utilisateur doit contenir au moins 3 caractères')
        if not email or '@' not in email:
            errors.append('Veuillez entrer un email valide')
        if not password or len(password) < 6:
            errors.append('Le mot de passe doit contenir au moins 6 caractères')
        if password != confirm_password:
            errors.append('Les mots de passe ne correspondent pas')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('register'))
        
        try:
            hashed_password = generate_password_hash(password)
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, hashed_password)
            )
            conn.commit()
            
            flash('Inscription réussie! Vous pouvez maintenant vous connecter', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Ce nom d\'utilisateur ou email est déjà utilisé', 'error')
        except Exception as e:
            app.logger.error(f"Erreur inscription: {str(e)}")
            flash('Une erreur est survenue lors de l\'inscription', 'error')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Vous avez été déconnecté avec succès', 'info')
    return redirect(url_for('login'))

# Routes principales
@app.route('/')
@login_required
def home():
    return render_template('index.html', username=session.get('username'))

@app.route('/search')
@login_required
def search_videos():
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'error': 'Entrez une recherche valide'}), 400

        youtube = get_youtube_service()

        # Recherche de vidéos
        search_response = youtube.search().list(
            q=query,
            part='id,snippet',
            maxResults=15,
            type='video',
            videoDuration='medium',
            relevanceLanguage='fr',
            regionCode='FR'
        ).execute()

        videos = []
        video_ids = []

        # Extraction des résultats
        for item in search_response.get('items', []):
            if item['id']['kind'] == 'youtube#video':
                video_id = item['id']['videoId']
                video_ids.append(video_id)

                videos.append({
                    'id': video_id,
                    'title': item['snippet']['title'],
                    'thumbnail': item['snippet']['thumbnails']['high']['url'],
                    'channel': item['snippet']['channelTitle'],
                    'duration': '00:00',
                    'views': '0',
                    'publishedAt': item['snippet'].get('publishedAt', '')
                })

        # Détails des vidéos (durée, vues)
        if video_ids:
            videos_response = youtube.videos().list(
                id=','.join(video_ids),
                part='contentDetails,statistics'
            ).execute()

            for item in videos_response.get('items', []):
                for video in videos:
                    if video['id'] == item['id']:
                        video['duration'] = parse_duration(item['contentDetails']['duration'])
                        video['views'] = format(int(item['statistics'].get('viewCount', 0)), ',d').replace(',', ' ')

        return jsonify({'videos': videos})

    except Exception as e:
        app.logger.error(f"Erreur recherche YouTube: {str(e)}")
        return jsonify({'error': 'Erreur lors de la recherche. Veuillez réessayer.'}), 500

# API Routes
@app.route('/api/playlists', methods=['GET', 'POST'])
@login_required
def handle_playlists():
    if request.method == 'GET':
        try:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            
            # Récupérer les playlists de l'utilisateur
            cursor.execute('''
                SELECT id, name FROM playlists WHERE user_id = ?
            ''', (session['user_id'],))
            
            playlists = [{'id': row[0], 'name': row[1]} for row in cursor.fetchall()]
            return jsonify({'playlists': playlists})
            
        except Exception as e:
            app.logger.error(f"Erreur playlists: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            conn.close()
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            user_id = session['user_id']
            
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            
            # Créer une nouvelle playlist si demandé
            if data.get('createNew'):
                playlist_name = data.get('name', 'Ma Playlist')
                cursor.execute('''
                    INSERT INTO playlists (user_id, name) VALUES (?, ?)
                ''', (user_id, playlist_name))
                conn.commit()
                return jsonify({'success': True, 'playlistId': cursor.lastrowid})
            
            # Ajouter une vidéo à une playlist existante
            playlist_id = data.get('playlistId')
            video_id = data.get('videoId')
            title = data.get('title')
            thumbnail = data.get('thumbnail')
            
            if not all([playlist_id, video_id, title, thumbnail]):
                return jsonify({'error': 'Données manquantes'}), 400
            
            # Vérifier que la playlist appartient à l'utilisateur
            cursor.execute('SELECT 1 FROM playlists WHERE id = ? AND user_id = ?', (playlist_id, user_id))
            if not cursor.fetchone():
                return jsonify({'error': 'Playlist non trouvée'}), 404
            
            # Ajouter la vidéo à la playlist
            cursor.execute('''
                INSERT OR IGNORE INTO playlist_items 
                (playlist_id, video_id, title, thumbnail) 
                VALUES (?, ?, ?, ?)
            ''', (playlist_id, video_id, title, thumbnail))
            
            conn.commit()
            return jsonify({'success': True})
            
        except Exception as e:
            app.logger.error(f"Erreur playlist: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            conn.close()

@app.route('/api/favorites', methods=['GET', 'POST', 'DELETE'])
@login_required
def handle_favorites():
    if request.method == 'POST':
        try:
            data = request.get_json()
            video_id = data.get('videoId')
            title = data.get('title')
            thumbnail = data.get('thumbnail')
            channel = data.get('channel')
            
            if not all([video_id, title, thumbnail, channel]):
                return jsonify({'error': 'Données manquantes'}), 400
            
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            
            # Vérifier si la vidéo existe déjà dans la table videos
            cursor.execute('SELECT 1 FROM videos WHERE id = ?', (video_id,))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO videos (id, title, thumbnail, channel, duration, views)
                    VALUES (?, ?, ?, ?, '00:00', '0')
                ''', (video_id, title, thumbnail, channel))
            
            # Ajouter aux favoris
            cursor.execute('''
                INSERT OR IGNORE INTO favorites (user_id, video_id)
                VALUES (?, ?)
            ''', (session['user_id'], video_id))
            
            conn.commit()
            return jsonify({'success': True})
            
        except Exception as e:
            app.logger.error(f"Erreur favoris: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            conn.close()
    
    elif request.method == 'GET':
        try:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT v.id, v.title, v.thumbnail, v.channel
                FROM favorites f
                JOIN videos v ON f.video_id = v.id
                WHERE f.user_id = ?
            ''', (session['user_id'],))
            
            favorites = [{
                'videoId': row[0],
                'title': row[1],
                'thumbnail': row[2],
                'channel': row[3]
            } for row in cursor.fetchall()]
            
            return jsonify({'favorites': favorites})
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            conn.close()
    
    elif request.method == 'DELETE':
        try:
            video_id = request.args.get('videoId')
            if not video_id:
                return jsonify({'error': 'ID vidéo manquant'}), 400
            
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM favorites 
                WHERE user_id = ? AND video_id = ?
            ''', (session['user_id'], video_id))
            
            conn.commit()
            return jsonify({'success': True})
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            conn.close()

# Gestion des erreurs
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_code=404, error_message="Page non trouvée"), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error_code=500, error_message="Erreur interne du serveur"), 500

@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', error_code=403, error_message="Accès refusé"), 403

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)