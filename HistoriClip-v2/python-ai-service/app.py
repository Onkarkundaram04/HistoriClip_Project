"""
HistoriClip - Python AI Service Entry Point

Flask-based microservice for AI processing:
- Vision: Landmark detection
- Information: Script generation
- Visual: Image generation
- Audio: Text-to-speech
- Editor: Video assembly
"""

import os
import shutil
import json
import uuid
from pathlib import Path
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from the single global .env at project root
ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ROOT_ENV)

# Import AI modules
from modules.vision import VisionAnalyzer
from modules.information import InformationGenerator
from modules.visual import ImageGenerator
from modules.audio import AudioGenerator
from modules.editor import VideoEditor

# Initialize Flask app
app = Flask(__name__)

# CORS Configuration - Only allow requests from backend (not direct browser access)
# In development: localhost:5000 (backend), In production: same origin via nginx
allowed_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5000,http://localhost:80')
CORS(app, origins=allowed_origins.split(','))

# Shared secret for Backend <-> AI Service authentication
AI_SERVICE_SECRET = os.getenv('AI_SERVICE_SECRET', '')


def require_service_auth(f):
    """
    Decorator to require AI_SERVICE_SECRET for protected endpoints.
    Only the Node.js backend should be able to call these endpoints.
    """
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get secret from header (preferred) or query param (fallback)
        provided_secret = request.headers.get('X-AI-Service-Secret') or request.args.get('secret')
        
        if not AI_SERVICE_SECRET:
            # If no secret configured (dev mode), allow through with warning
            print("[WARNING] AI_SERVICE_SECRET not configured - endpoints are OPEN!")
            return f(*args, **kwargs)
        
        if provided_secret != AI_SERVICE_SECRET:
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Valid AI service secret required'
            }), 401
        
        return f(*args, **kwargs)
    return decorated_function

# Initialize AI modules (lazy loading for performance)
vision_analyzer = None
info_generator = None
image_generator = None
audio_generator = None
video_editor = None


def get_vision_analyzer():
    """Lazy load Vision Analyzer."""
    global vision_analyzer
    if vision_analyzer is None:
        vision_analyzer = VisionAnalyzer()
    return vision_analyzer


def get_info_generator():
    """Lazy load Information Generator."""
    global info_generator
    if info_generator is None:
        info_generator = InformationGenerator()
    return info_generator


def get_image_generator():
    """Lazy load Image Generator."""
    global image_generator
    if image_generator is None:
        image_generator = ImageGenerator()
    return image_generator


def get_audio_generator():
    """Lazy load Audio Generator."""
    global audio_generator
    if audio_generator is None:
        audio_generator = AudioGenerator()
    return audio_generator


def get_video_editor():
    """Lazy load Video Editor."""
    global video_editor
    if video_editor is None:
        video_editor = VideoEditor()
    return video_editor


# ===========================================
# Health Check Endpoint
# ===========================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'HistoriClip AI Service',
        'version': '2.0.0'
    })


# ===========================================
# Vision Analysis Endpoint
# ===========================================

@app.route('/analyze/vision', methods=['POST'])
@require_service_auth
def analyze_vision():
    """
    Analyze uploaded image for landmark detection.
    
    Expected: multipart/form-data with 'image' file
    Returns: landmark info, GPS, location
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        image_file = request.files['image']
        analyzer = get_vision_analyzer()
        result = analyzer.analyze(image_file)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===========================================
# Full Pipeline Endpoint
# ===========================================

@app.route('/generate', methods=['POST'])
@require_service_auth
def generate_video():
    """
    Full video generation pipeline.
    
    Expected: multipart/form-data with 'image' file
    Returns: paths to generated video, audio, images
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        image_file = request.files['image']
        
        # Progress callback setup
        video_id = request.form.get('video_id')
        callback_url = request.form.get('callback_url')
        
        def report_progress(step_name):
            """Report current processing step back to Node.js backend."""
            if not video_id or not callback_url:
                return
            try:
                import requests as req_lib
                req_lib.post(callback_url, json={
                    'video_id': video_id,
                    'step': step_name
                }, timeout=3)
            except Exception:
                pass  # Non-critical, don't fail pipeline
        
        # Step 1: Vision Analysis
        report_progress('vision')
        print("📍 Step 1: Analyzing image...")
        analyzer = get_vision_analyzer()
        vision_result = analyzer.analyze(image_file)
        
        if not vision_result.get('success'):
            return jsonify({
                'error': 'No landmark detected',
                'message': 'All analysis tiers failed to geolocate the image.'
            }), 400

        if not vision_result.get('identified', False):
            return jsonify({
                'error': 'Location unidentified',
                'message': (
                    'The image was geolocated but no specific landmark could be identified. '
                    'Cannot generate a factual documentary without a verified landmark name.'
                ),
                'gps': vision_result.get('gps'),
                'location': vision_result.get('location'),
            }), 400
        
        landmark_name = vision_result['landmark_name']
        
        # Step 2: Information Generation
        report_progress('script')
        print("📝 Step 2: Generating script...")
        info_gen = get_info_generator()
        info_result = info_gen.generate(landmark_name)
        
        if info_result.get('error') or not info_result.get('script'):
            return jsonify({
                'error': 'Script Generation Failed',
                'message': info_result.get('error', 'Failed to generate factual script.')
            }), 500
        
        # Step 3: Image Generation
        report_progress('images')
        print("🖼️ Step 3: Generating images...")
        img_gen = get_image_generator()
        image_paths = img_gen.generate(info_result['prompts'])
        
        # Step 4: Audio Generation
        speed = request.form.get('speed', 'normal')
        report_progress('audio')
        print(f"🔊 Step 4: Generating narration (Speed: {speed})...")
        audio_gen = get_audio_generator()
        audio_path = audio_gen.generate(info_result['script'], speed=speed)
        
        # Step 5: Video Assembly
        report_progress('video')
        print("🎬 Step 5: Assembling video...")
        editor = get_video_editor()
        video_path = editor.create_video(image_paths, audio_path)
        
        print("✅ Video generation complete!")
        
        # Step 6: Process XAI data (copy visualizations to uploads)
        report_progress('xai')
        xai_matches_url = None
        xai_attention_url = None
        xai_top_matches = vision_result.get('xai_top_matches')
        xai_tier_used = vision_result.get('xai_tier_used') or vision_result.get('method')
        
        xai_dir = os.path.join(os.path.dirname(__file__), '..', 'backend', 'uploads', 'xai')
        os.makedirs(xai_dir, exist_ok=True)
        uid = uuid.uuid4().hex[:8]
        
        # Copy LightGlue match visualization
        src_matches = vision_result.get('xai_matches_path')
        if src_matches and os.path.exists(src_matches):
            dest_name = f"matches_{uid}.jpg"
            dest_path = os.path.join(xai_dir, dest_name)
            shutil.copy2(src_matches, dest_path)
            xai_matches_url = host_url(dest_path)
            print(f"[XAI] Copied matches viz: {xai_matches_url}")
        
        # Copy DINOv2 attention map visualization
        src_attention = vision_result.get('xai_attention_path')
        if src_attention and os.path.exists(src_attention):
            dest_name = f"attention_{uid}.jpg"
            dest_path = os.path.join(xai_dir, dest_name)
            shutil.copy2(src_attention, dest_path)
            xai_attention_url = host_url(dest_path)
            print(f"[XAI] Copied attention viz: {xai_attention_url}")
        
        # Build top-match image URLs (reference images from the FAISS index)
        if xai_top_matches:
            from modules.config import load_config_from_env
            loc_config = load_config_from_env()
            images_dir = str(loc_config.images_dir)
            for match in xai_top_matches:
                ref_filename = match.get('filename', '')
                if ref_filename:
                    ref_src = os.path.join(images_dir, ref_filename)
                    if os.path.exists(ref_src):
                        ref_dest_name = f"ref_{uid}_{match['rank']}_{ref_filename}"
                        ref_dest = os.path.join(xai_dir, ref_dest_name)
                        shutil.copy2(ref_src, ref_dest)
                        match['image_url'] = host_url(ref_dest)
        
        report_progress('complete')
        
        return jsonify({
            'success': True,
            'landmark': landmark_name,
            'location': vision_result.get('location'),
            'gps': vision_result.get('gps'),
            'script': info_result['script'],
            'is_unesco': info_result.get('is_unesco', False),
            'unesco_year': info_result.get('unesco_year'),
            'video_path': host_url(video_path),
            'audio_path': host_url(audio_path),
            'image_paths': [host_url(p) for p in image_paths],
            'prompts': info_result['prompts'],
            'xai_matches_url': xai_matches_url,
            'xai_attention_url': xai_attention_url,
            'xai_top_matches': xai_top_matches,
            'xai_tier_used': xai_tier_used
        })
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500



# ===========================================
# Individual Module Endpoints (for testing)
# ===========================================

@app.route('/generate/script', methods=['POST'])
@require_service_auth
def generate_script():
    """Generate script for a landmark."""
    try:
        data = request.get_json()
        landmark = data.get('landmark')
        
        if not landmark:
            return jsonify({'error': 'Landmark name required'}), 400
        
        info_gen = get_info_generator()
        result = info_gen.generate(landmark)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/generate/images', methods=['POST'])
@require_service_auth
def generate_images():
    """Generate images from prompts."""
    try:
        data = request.get_json()
        prompts = data.get('prompts', [])
        
        if not prompts:
            return jsonify({'error': 'Prompts required'}), 400
        
        img_gen = get_image_generator()
        image_paths = img_gen.generate(prompts)
        
        return jsonify({'image_paths': image_paths})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/generate/audio', methods=['POST'])
@require_service_auth
def generate_audio():
    """Generate audio from script."""
    try:
        data = request.get_json()
        script = data.get('script')
        
        if not script:
            return jsonify({'error': 'Script required'}), 400
        
        audio_gen = get_audio_generator()
        audio_path = audio_gen.generate(script)
        
        return jsonify({'audio_path': audio_path})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===========================================
# Static File Serving (for dev)
# ===========================================

@app.route('/data/<path:filename>')
def serve_data(filename):
    """Serve generated files (videos, images, audio)."""
    from flask import send_from_directory
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    return send_from_directory(data_dir, filename)

def host_url(path):
    """
    Convert local path to accessible URL.
    Files are now saved to backend/uploads folder, so use backend URL.
    """
    if not path:
        return None
    try:
        # Backend uploads directory
        backend_uploads = os.path.join(os.path.dirname(__file__), '..', 'backend', 'uploads')
        backend_uploads = os.path.abspath(backend_uploads)
        
        # Get absolute path of the file
        abs_path = os.path.abspath(path)
        
        # Extract relative path from 'uploads' directory
        rel_path = os.path.relpath(abs_path, backend_uploads)
        
        # Normalize slashes for URL
        rel_path = rel_path.replace('\\', '/')
        
        # Use backend URL since files are saved to backend/uploads
        url = f"http://localhost:5000/uploads/{rel_path}"
        print(f"[host_url] {path} -> {url}")
        return url
    except Exception as e:
        print(f"[host_url] Error converting path: {e}")
        # Fallback - just use the filename
        return f"http://localhost:5000/uploads/{os.path.basename(path)}"


# ===========================================
# Main Entry
# ===========================================

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    
    # Ensure backend upload dirs exist (where generated files are saved)
    backend_uploads = os.path.join(os.path.dirname(__file__), '..', 'backend', 'uploads')
    os.makedirs(os.path.join(backend_uploads, 'generated_videos'), exist_ok=True)
    os.makedirs(os.path.join(backend_uploads, 'generated_audio'), exist_ok=True)
    os.makedirs(os.path.join(backend_uploads, 'generated_images'), exist_ok=True)
    os.makedirs(os.path.join(backend_uploads, 'xai'), exist_ok=True)
    print(f"[Setup] Upload directories created at: {backend_uploads}")
    
    print(f"\n🤖 HistoriClip AI Service")
    print(f"📍 Running on: http://localhost:{port}")
    print(f"🔧 Debug mode: {debug}\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
