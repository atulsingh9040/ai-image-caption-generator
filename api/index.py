"""
Unified Serverless & Local Flask Application for AI Caption Studio.
Supports OpenRouter Multimodal Vision AI + AWS Rekognition.
Fully self-contained for zero-configuration Vercel deployment.
"""
import os
import sys
import json
import base64
import time
import urllib.request
import urllib.error
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# Determine base directory for static assets
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if not os.path.exists(os.path.join(BASE_DIR, 'index.html')):
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
CORS(app)

# ── API Configurations ───────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_BASE = 'https://openrouter.ai/api/v1'
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'meta-llama/llama-3.2-11b-vision-instruct:free')

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

# ── AWS Rekognition Helper ───────────────────────────────────────────────────
def call_aws_rekognition(image_bytes, access_key, secret_key, region):
    """Analyze image using boto3 Rekognition client."""
    try:
        import boto3
        kwargs = {'region_name': region or 'us-east-1'}
        if access_key and secret_key:
            kwargs['aws_access_key_id'] = access_key
            kwargs['aws_secret_access_key'] = secret_key
        
        client = boto3.client('rekognition', **kwargs)
        
        labels_resp = client.detect_labels(
            Image={'Bytes': image_bytes},
            MaxLabels=20,
            MinConfidence=55.0,
            Features=['GENERAL_LABELS', 'IMAGE_PROPERTIES']
        )
        
        text_resp = {}
        try:
            text_resp = client.detect_text(Image={'Bytes': image_bytes})
        except Exception:
            pass

        return {
            'labels': labels_resp.get('Labels', []),
            'image_properties': labels_resp.get('ImageProperties', {}),
            'text_detections': text_resp.get('TextDetections', [])
        }
    except Exception as e:
        raise RuntimeError(f"AWS Rekognition Error: {str(e)}")

# ── Caption Synthesizer (from Rekognition data) ──────────────────────────────
def synthesize_rekognition_captions(raw_data):
    labels = raw_data.get('labels', [])
    texts = raw_data.get('text_detections', [])
    props = raw_data.get('image_properties', {})

    sorted_labels = sorted(labels, key=lambda x: x.get('Confidence', 0), reverse=True)
    top_names = [l['Name'] for l in sorted_labels[:10]]

    people, animals, objects, scenes, actions = [], [], [], [], []
    for l in sorted_labels:
        n = l['Name']
        tags = set([c.get('Name', '').lower() for c in l.get('Categories', [])] + 
                   [p.get('Name', '').lower() for p in l.get('Parents', [])] + [n.lower()])
        if any(k in tags for k in ['person', 'human', 'face', 'portrait']):
            people.append(n)
        elif any(k in tags for k in ['animal', 'pet', 'wildlife', 'bird', 'dog', 'cat']):
            animals.append(n)
        elif any(k in tags for k in ['sport', 'action', 'running', 'walking', 'jumping']):
            actions.append(n)
        elif any(k in tags for k in ['outdoors', 'nature', 'landscape', 'architecture', 'city', 'indoor']):
            scenes.append(n)
        else:
            objects.append(n)

    subject = (people[0] if people else 
               (f"a {animals[0]}" if animals else 
               (objects[0] if objects else (top_names[0] if top_names else "subject"))))
    setting = f" in a {scenes[0].lower()} setting" if scenes else ""
    action = f", engaging in {actions[0].lower()}" if actions else ""

    primary = f"A focused photograph capturing {subject}{setting}{action}."
    short = " • ".join(filter(None, [subject, scenes[0] if scenes else None]))[:35]
    desc = f"The composition highlights {subject}{setting}. Identified elements include {', '.join(top_names[:6])}."

    detected_text = [t['DetectedText'] for t in texts if t.get('Type') == 'LINE' and t.get('Confidence', 0) > 75][:4]
    hashtags = [f"#{tag.replace(' ', '')}" for tag in top_names[:8]]

    labels_summary = [
        {"name": l['Name'], "confidence": round(l.get('Confidence', 0), 1)}
        for l in sorted_labels[:12]
    ]

    return {
        "primary_caption": primary,
        "short_caption": short or "Scene Analysis",
        "detailed_description": desc,
        "labels_summary": labels_summary,
        "hashtags": hashtags,
        "detected_text": detected_text
    }

# ── OpenRouter Multimodal Vision Helper ──────────────────────────────────────
def call_openrouter_vision(image_bytes, api_key=None, model=None):
    key = api_key or OPENROUTER_API_KEY
    if not key:
        raise ValueError("OpenRouter API key is required.")

    target_model = model or OPENROUTER_MODEL
    b64_image = base64.b64encode(image_bytes).decode('utf-8')

    prompt = (
        "You are an expert computer vision model. Analyze this image thoroughly and return a valid JSON object "
        "with these exact keys:\n"
        "{\n"
        '  "primary_caption": "One polished, articulate editorial sentence describing the key subject, action, and lighting.",\n'
        '  "short_caption": "3-5 word concise headline.",\n'
        '  "detailed_description": "2-3 comprehensive sentences highlighting composition, scene elements, colors, and emotional tone.",\n'
        '  "labels_summary": [{"name": "Subject/Object", "confidence": 98.5}, ... (provide 8-12 detected objects/concepts with realistic 0-100 float confidence)],\n'
        '  "hashtags": ["#tag1", "#tag2", ... (8 relevant hashtags)],\n'
        '  "detected_text": ["any legible words seen in image", ... (empty array if none)]\n'
        "}\n"
        "Respond ONLY with raw JSON. Do not wrap in markdown code blocks."
    )

    payload = json.dumps({
        "model": target_model,
        "max_tokens": 700,
        "temperature": 0.2,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    }).encode('utf-8')

    req = urllib.request.Request(
        f"{OPENROUTER_BASE}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/atulsingh9040/ai-image-caption-generator",
            "X-Title": "Lumina Vision Studio"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=35) as resp:
        res_data = json.loads(resp.read().decode('utf-8'))

    raw_text = res_data['choices'][0]['message']['content'].strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(raw_text)

# ── Demo / Fallback Data ─────────────────────────────────────────────────────
def get_demo_analysis():
    return {
        "primary_caption": "A breathtaking panoramic landscape featuring rugged mountain peaks kissed by golden morning light across an alpine wilderness.",
        "short_caption": "Alpine Mountain Vista",
        "detailed_description": "The composition captures an expansive mountain range under clear atmospheric skies. Natural sunlight illuminates alpine ridges, contrasting lush evergreen valley textures with glacial terrain.",
        "labels_summary": [
            {"name": "Mountain Range", "confidence": 99.4},
            {"name": "Alpine Wilderness", "confidence": 98.2},
            {"name": "Morning Sunlight", "confidence": 96.5},
            {"name": "Evergreen Forest", "confidence": 93.8},
            {"name": "Atmospheric Sky", "confidence": 91.0},
            {"name": "Glacial Peak", "confidence": 88.6},
            {"name": "Topography", "confidence": 85.3},
            {"name": "High Altitude", "confidence": 82.7}
        ],
        "hashtags": ["#MountainVista", "#AlpineNature", "#Wilderness", "#LandscapePhotography", "#GoldenHour", "#Peaks", "#ExploreNature", "#OutdoorLife"],
        "detected_text": [],
        "is_demo": True
    }

# ── Endpoints ────────────────────────────────────────────────────────────────
@app.route('/')
def serve_home():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/api/status', methods=['GET'])
def get_system_status():
    has_openrouter = bool(OPENROUTER_API_KEY)
    has_aws = bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)
    return jsonify({
        "status": "online",
        "openrouter_active": has_openrouter,
        "openrouter_model": OPENROUTER_MODEL,
        "aws_active": has_aws,
        "aws_region": AWS_DEFAULT_REGION,
        "version": "2.4.0",
        "runtime": "Vercel Serverless / WSGI"
    })

@app.route('/api/test-key', methods=['POST'])
def test_key_connectivity():
    data = request.get_json() or {}
    key = data.get('api_key') or OPENROUTER_API_KEY
    if not key:
        return jsonify({"success": False, "message": "No API key provided."}), 400

    start_time = time.time()
    try:
        payload = json.dumps({
            "model": OPENROUTER_MODEL,
            "max_tokens": 15,
            "messages": [{"role": "user", "content": "Respond with: Ready."}]
        }).encode('utf-8')

        req = urllib.request.Request(
            f"{OPENROUTER_BASE}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/atulsingh9040/ai-image-caption-generator",
                "X-Title": "Lumina Vision Studio"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_body = json.loads(resp.read().decode('utf-8'))
            reply = resp_body['choices'][0]['message']['content'].strip()

        latency_ms = int((time.time() - start_time) * 1000)
        return jsonify({
            "success": True,
            "message": f"Verified successfully in {latency_ms}ms ({reply})",
            "latency_ms": latency_ms,
            "model": OPENROUTER_MODEL
        })
    except urllib.error.HTTPError as err:
        err_body = err.read().decode('utf-8', errors='ignore')
        return jsonify({"success": False, "message": f"HTTP {err.code}: {err_body}"}), 400
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)}), 500

@app.route('/api/config', methods=['POST'])
def save_configuration():
    global OPENROUTER_API_KEY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
    data = request.json or {}

    if 'openrouter_api_key' in data:
        OPENROUTER_API_KEY = data['openrouter_api_key'].strip()
    if 'aws_access_key_id' in data:
        AWS_ACCESS_KEY_ID = data['aws_access_key_id'].strip()
    if 'aws_secret_access_key' in data:
        AWS_SECRET_ACCESS_KEY = data['aws_secret_access_key'].strip()
    if 'aws_region' in data:
        AWS_DEFAULT_REGION = data['aws_region'].strip()

    return jsonify({
        "success": True,
        "message": "Configuration updated successfully."
    })

@app.route('/api/analyze', methods=['POST'])
def analyze_image_route():
    start_time = time.time()
    try:
        image_bytes = None
        custom_key = request.headers.get('X-OpenRouter-Key') or None
        target_engine = request.form.get('engine') or 'auto'

        if 'image' in request.files:
            image_bytes = request.files['image'].read()
        elif request.is_json:
            data = request.get_json()
            b64_str = data.get('image_base64', '')
            if ',' in b64_str:
                b64_str = b64_str.split(',', 1)[1]
            if b64_str:
                image_bytes = base64.b64decode(b64_str)
            custom_key = data.get('openrouter_key') or custom_key
            target_engine = data.get('engine') or target_engine

        if not image_bytes:
            return jsonify({"error": "No image payload provided."}), 400

        # 1. Attempt OpenRouter Vision
        effective_key = custom_key or OPENROUTER_API_KEY
        if target_engine in ('auto', 'openrouter') and effective_key:
            try:
                result = call_openrouter_vision(image_bytes, api_key=effective_key)
                result['source'] = 'openrouter'
                result['engine_name'] = 'OpenRouter Multimodal Vision'
                result['model'] = OPENROUTER_MODEL
                result['latency_ms'] = int((time.time() - start_time) * 1000)
                return jsonify(result)
            except Exception as e:
                # If OpenRouter failed and user explicitly requested openrouter, report error
                if target_engine == 'openrouter':
                    return jsonify({"error": f"OpenRouter Vision Error: {str(e)}"}), 502

        # 2. Attempt AWS Rekognition
        has_aws = bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)
        if target_engine in ('auto', 'aws') and has_aws:
            try:
                raw_aws = call_aws_rekognition(image_bytes, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION)
                result = synthesize_rekognition_captions(raw_aws)
                result['source'] = 'aws_rekognition'
                result['engine_name'] = f'AWS Rekognition ({AWS_DEFAULT_REGION})'
                result['latency_ms'] = int((time.time() - start_time) * 1000)
                return jsonify(result)
            except Exception as e:
                if target_engine == 'aws':
                    return jsonify({"error": f"AWS Rekognition Error: {str(e)}"}), 502

        # 3. Fallback Demo Simulation
        result = get_demo_analysis()
        result['source'] = 'demo'
        result['engine_name'] = 'Simulation Engine (Add API Key in Settings)'
        result['latency_ms'] = int((time.time() - start_time) * 1000)
        return jsonify(result)

    except Exception as exc:
        return jsonify({"error": f"Processing failed: {str(exc)}"}), 500

# Export application for Vercel WSGI
application = app

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
