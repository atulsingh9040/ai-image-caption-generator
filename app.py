"""
Flask Backend - AI Image Caption Generator
Uses OpenRouter AI (vision model) + AWS Rekognition fallback.
"""
import os
import base64
import json
import urllib.request
import urllib.error
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from aws_service import AWSCaptionService
from caption_engine import CaptionEngine

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
CORS(app)

# ── OpenRouter config ───────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_BASE = 'https://openrouter.ai/api/v1'
OPENROUTER_MODEL = 'meta-llama/llama-3.2-11b-vision-instruct:free'   # free vision model

# ── AWS config ───────────────────────────────────────────────────────────────
aws_service = AWSCaptionService(
    aws_access_key=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
)

# ── Helpers ──────────────────────────────────────────────────────────────────

def openrouter_chat(messages, api_key=None, max_tokens=400):
    """Call OpenRouter /chat/completions with given messages list."""
    key = api_key or OPENROUTER_API_KEY
    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "max_tokens": max_tokens,
        "messages": messages
    }).encode('utf-8')

    req = urllib.request.Request(
        f'{OPENROUTER_BASE}/chat/completions',
        data=payload,
        headers={
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/atulsingh9040/ai-image-caption-generator',
            'X-Title': 'AI Caption Generator'
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    return result['choices'][0]['message']['content'].strip()


def openrouter_caption_image(image_bytes, api_key=None):
    """Generate a rich caption from raw image bytes via OpenRouter vision model."""
    b64 = base64.b64encode(image_bytes).decode('utf-8')
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                },
                {
                    "type": "text",
                    "text": (
                        "Analyze this image thoroughly and respond with a JSON object "
                        "containing exactly these keys:\n"
                        "1. primary_caption  – one vivid, complete sentence describing the scene.\n"
                        "2. short_caption    – 3-5 word title.\n"
                        "3. detailed_description – 2-3 sentences with rich detail.\n"
                        "4. labels_summary   – array of {name, confidence} objects for top 8 detected items (use 0-100 scale).\n"
                        "5. hashtags         – array of 8 relevant hashtag strings.\n"
                        "6. detected_text    – array of any visible text in the image (empty array if none).\n"
                        "Return ONLY valid JSON, no markdown fences."
                    )
                }
            ]
        }
    ]
    raw = openrouter_chat(messages, api_key=api_key, max_tokens=600)
    # Strip possible markdown fences
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
    return json.loads(raw)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    has_aws = bool(aws_service.aws_access_key and aws_service.aws_secret_key)
    return jsonify({
        "status": "online",
        "openrouter_configured": bool(OPENROUTER_API_KEY),
        "aws_configured": has_aws,
        "region": aws_service.region_name,
        "service": "AI Caption Generator (OpenRouter + AWS)"
    })


@app.route('/api/test-key', methods=['POST'])
def test_api_key():
    """Quick 'Hi' test to verify an OpenRouter API key is valid."""
    data = request.get_json() or {}
    api_key = data.get('api_key') or OPENROUTER_API_KEY

    if not api_key:
        return jsonify({"success": False, "message": "No API key provided."}), 400

    try:
        reply = openrouter_chat(
            messages=[{"role": "user", "content": "Say exactly: Hi! I am working perfectly."}],
            api_key=api_key,
            max_tokens=30
        )
        return jsonify({"success": True, "message": reply, "model": OPENROUTER_MODEL})
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        return jsonify({"success": False, "message": f"HTTP {e.code}: {body}"}), 400
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route('/api/config', methods=['POST'])
def update_config():
    global OPENROUTER_API_KEY
    data = request.json or {}
    new_key = data.get('openrouter_api_key')
    if new_key:
        OPENROUTER_API_KEY = new_key

    # Optional AWS update
    access_key = data.get('aws_access_key_id')
    secret_key = data.get('aws_secret_access_key')
    region = data.get('aws_region', 'us-east-1')
    if access_key and secret_key:
        aws_service.update_credentials(access_key, secret_key, region)

    return jsonify({"success": True, "message": "Configuration updated."})


@app.route('/api/analyze', methods=['POST'])
def analyze_image():
    try:
        image_bytes = None

        if 'image' in request.files:
            image_bytes = request.files['image'].read()
        elif request.is_json:
            data = request.get_json()
            b64_str = data.get('image_base64', '')
            if ',' in b64_str:
                b64_str = b64_str.split(',', 1)[1]
            if b64_str:
                image_bytes = base64.b64decode(b64_str)

        if not image_bytes:
            return jsonify({"error": "No image data provided"}), 400

        # ── 1. Try OpenRouter vision first ───────────────────────────────────
        if OPENROUTER_API_KEY:
            try:
                result = openrouter_caption_image(image_bytes)
                result['source'] = 'openrouter'
                result['model'] = OPENROUTER_MODEL
                return jsonify(result)
            except Exception as or_err:
                # Fall through to AWS or demo
                pass

        # ── 2. Try AWS Rekognition ────────────────────────────────────────────
        has_aws = bool(aws_service.aws_access_key and aws_service.aws_secret_key)
        if has_aws:
            try:
                raw = aws_service.analyze_image_rekognition(image_bytes)
                caption_result = CaptionEngine.generate_captions_from_rekognition(raw)
                caption_result['source'] = 'aws_rekognition'
                return jsonify(caption_result)
            except Exception:
                pass

        # ── 3. Demo fallback ─────────────────────────────────────────────────
        result = CaptionEngine.get_mock_caption()
        result['source'] = 'demo'
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 AI Image Caption Generator → http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
