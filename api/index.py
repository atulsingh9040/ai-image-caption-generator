"""
Unified Serverless Flask Application for Lumina Vision Studio.
Single WSGI entrypoint — Vercel deploys ONLY this file as the backend.
Supports OpenRouter Multimodal Vision AI + AWS Rekognition fallback.
"""
import os
import json
import base64
import time
import urllib.request
import urllib.error
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if not os.path.exists(os.path.join(ROOT_DIR, 'index.html')):
    ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ── API Configurations ────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_BASE    = 'https://openrouter.ai/api/v1'
OPENROUTER_MODEL   = os.getenv('OPENROUTER_MODEL', 'particle-ai/particle-1:free')
OPENROUTER_FALLBACK_MODELS = [
    'particle-ai/particle-1:free',
    'google/gemma-4-26b-a4b-it:free',
    'google/gemma-4-31b-it:free',
    'inclusionai/ling-3.2-flash:free',
]

AWS_ACCESS_KEY_ID     = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
AWS_DEFAULT_REGION    = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

# ── AWS Rekognition Helper ────────────────────────────────────────────────────
def call_aws_rekognition(image_bytes, access_key, secret_key, region):
    try:
        import boto3
        kwargs = {'region_name': region or 'us-east-1'}
        if access_key and secret_key:
            kwargs['aws_access_key_id'] = access_key
            kwargs['aws_secret_access_key'] = secret_key
        client = boto3.client('rekognition', **kwargs)
        labels_resp = client.detect_labels(
            Image={'Bytes': image_bytes},
            MaxLabels=20, MinConfidence=55.0,
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


# ── Caption Synthesizer (Rekognition → structured output) ─────────────────────
def synthesize_rekognition_captions(raw_data):
    labels  = raw_data.get('labels', [])
    texts   = raw_data.get('text_detections', [])
    sorted_labels = sorted(labels, key=lambda x: x.get('Confidence', 0), reverse=True)
    top_names = [l['Name'] for l in sorted_labels[:10]]

    people, animals, objects, scenes, actions = [], [], [], [], []
    for l in sorted_labels:
        n    = l['Name']
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
    action  = f", engaging in {actions[0].lower()}" if actions else ""

    primary     = f"A focused photograph capturing {subject}{setting}{action}."
    short       = " \u2022 ".join(filter(None, [subject, scenes[0] if scenes else None]))[:35]
    description = f"The composition highlights {subject}{setting}. Identified elements include {', '.join(top_names[:6])}."

    detected_text = [t['DetectedText'] for t in texts
                     if t.get('Type') == 'LINE' and t.get('Confidence', 0) > 75][:4]
    hashtags = [f"#{tag.replace(' ', '')}" for tag in top_names[:8]]
    labels_summary = [
        {"name": l['Name'], "confidence": round(l.get('Confidence', 0), 1)}
        for l in sorted_labels[:12]
    ]

    return {
        "primary_caption": primary,
        "short_caption": short or "Scene Analysis",
        "detailed_description": description,
        "labels_summary": labels_summary,
        "hashtags": hashtags,
        "detected_text": detected_text
    }


# ── OpenRouter Vision Helper ──────────────────────────────────────────────────
def _detect_mime_type(image_bytes):
    if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:16]:
        return 'image/webp'
    if image_bytes.startswith(b'GIF8'):
        return 'image/gif'
    return 'image/jpeg'


def _normalize_vision_result(parsed):
    """Ensure labels_summary, hashtags, and detected_text match the UI schema."""
    raw_labels = parsed.get('labels_summary') or []
    norm_labels = []
    for idx, item in enumerate(raw_labels):
        if isinstance(item, dict) and 'name' in item:
            norm_labels.append({
                'name': str(item['name']),
                'confidence': round(float(item.get('confidence', 90.0)), 1)
            })
        elif isinstance(item, str) and item.strip():
            norm_labels.append({
                'name': item.strip().title(),
                'confidence': round(max(70.0, 96.0 - idx * 3.2), 1)
            })
    parsed['labels_summary'] = norm_labels

    raw_tags = parsed.get('hashtags') or []
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split() if t.strip()]
    parsed['hashtags'] = [t if t.startswith('#') else f"#{t}" for t in raw_tags]

    raw_ocr = parsed.get('detected_text') or []
    if isinstance(raw_ocr, str):
        raw_ocr = [raw_ocr.strip()] if raw_ocr.strip() else []
    parsed['detected_text'] = [str(x) for x in raw_ocr if str(x).strip()]
    return parsed


def call_openrouter_vision(image_bytes, api_key=None, model=None):
    key = api_key or OPENROUTER_API_KEY
    if not key:
        raise ValueError("OpenRouter API key is required.")

    mime_type = _detect_mime_type(image_bytes)
    b64_image = base64.b64encode(image_bytes).decode('utf-8')

    prompt = (
        "You are an expert computer vision model. Analyze this image thoroughly and return a valid JSON object "
        "with these exact keys:\n"
        "{\n"
        '  "primary_caption": "One polished, articulate editorial sentence describing the key subject, action, and lighting.",\n'
        '  "short_caption": "3-5 word concise headline.",\n'
        '  "detailed_description": "2-3 comprehensive sentences highlighting composition, scene elements, colors, and emotional tone.",\n'
        '  "labels_summary": [{"name": "Subject/Object", "confidence": 98.5}],\n'
        '  "hashtags": ["#tag1", "#tag2"],\n'
        '  "detected_text": ["any legible words seen in image"]\n'
        "}\n"
        "Respond ONLY with raw JSON. Do not wrap in markdown code blocks."
    )

    models_to_try = [model] if model else [OPENROUTER_MODEL] + [m for m in OPENROUTER_FALLBACK_MODELS if m != OPENROUTER_MODEL]
    last_error = None

    for target_model in models_to_try:
        try:
            payload = json.dumps({
                "model": target_model,
                "max_tokens": 1500,
                "temperature": 0.2,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}},
                        {"type": "text", "text": prompt}
                    ]
                }]
            }).encode('utf-8')

            req = urllib.request.Request(
                f"{OPENROUTER_BASE}/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://ai-image-caption-generator.vercel.app",
                    "X-Title": "Lumina Vision Studio"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                res_data = json.loads(resp.read().decode('utf-8'))

            msg = res_data['choices'][0]['message']
            raw_text = (msg.get('content') or msg.get('reasoning') or '').strip()
            if not raw_text:
                raise ValueError(f"Empty response from {target_model}")

            if raw_text.startswith("```"):
                lines = raw_text.split("\n")
                raw_text = "\n".join(lines[1:])
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3].strip()

            start_idx = raw_text.find('{')
            end_idx = raw_text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                raw_text = raw_text[start_idx:end_idx + 1]

            parsed = _normalize_vision_result(json.loads(raw_text))
            parsed['_used_model'] = target_model
            return parsed
        except Exception as err:
            last_error = err
            continue

    raise RuntimeError(f"All OpenRouter vision models failed: {last_error}")


# ── Demo / Fallback Data ──────────────────────────────────────────────────────
def get_demo_analysis():
    return {
        "primary_caption": "A breathtaking panoramic landscape featuring rugged mountain peaks kissed by golden morning light across an alpine wilderness.",
        "short_caption": "Alpine Mountain Vista",
        "detailed_description": "The composition captures an expansive mountain range under clear atmospheric skies. Natural sunlight illuminates alpine ridges, contrasting lush evergreen valley textures with glacial terrain.",
        "labels_summary": [
            {"name": "Mountain Range",    "confidence": 99.4},
            {"name": "Alpine Wilderness", "confidence": 98.2},
            {"name": "Morning Sunlight",  "confidence": 96.5},
            {"name": "Evergreen Forest",  "confidence": 93.8},
            {"name": "Atmospheric Sky",   "confidence": 91.0},
            {"name": "Glacial Peak",      "confidence": 88.6},
            {"name": "Topography",        "confidence": 85.3},
            {"name": "High Altitude",     "confidence": 82.7}
        ],
        "hashtags": ["#MountainVista", "#AlpineNature", "#Wilderness", "#LandscapePhotography",
                     "#GoldenHour", "#Peaks", "#ExploreNature", "#OutdoorLife"],
        "detected_text": [],
        "is_demo": True
    }


# ── Static & API Routes ───────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def serve_index():
    return send_from_directory(ROOT_DIR, 'index.html')


@app.route('/<path:filename>', methods=['GET'])
def serve_static_file(filename):
    if filename in ('index.html', 'style.css', 'app.js'):
        return send_from_directory(ROOT_DIR, filename)
    return jsonify({"error": "Not found"}), 404


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
        "version": "2.5.0",
        "runtime": "Vercel Serverless"
    })


@app.route('/api/test-key', methods=['POST'])
def test_key_connectivity():
    data = request.get_json() or {}
    key  = data.get('api_key') or OPENROUTER_API_KEY
    if not key:
        return jsonify({"success": False, "message": "No API key provided."}), 400

    start_time = time.time()
    try:
        # First validate the key directly against OpenRouter's auth endpoint (never rate-limited by model providers)
        auth_req = urllib.request.Request(
            f"{OPENROUTER_BASE}/auth/key",
            headers={
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": "https://ai-image-caption-generator.vercel.app",
                "X-Title": "Lumina Vision Studio"
            },
            method="GET"
        )
        with urllib.request.urlopen(auth_req, timeout=10) as resp:
            auth_body = json.loads(resp.read().decode('utf-8'))

        latency_ms = int((time.time() - start_time) * 1000)
        label = auth_body.get('data', {}).get('label') or 'OpenRouter Key'
        return jsonify({
            "success": True,
            "message": f"Key verified ({label}) in {latency_ms}ms",
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
    data = request.get_json() or {}
    if 'openrouter_api_key' in data:
        OPENROUTER_API_KEY = data['openrouter_api_key'].strip()
    if 'aws_access_key_id' in data:
        AWS_ACCESS_KEY_ID = data['aws_access_key_id'].strip()
    if 'aws_secret_access_key' in data:
        AWS_SECRET_ACCESS_KEY = data['aws_secret_access_key'].strip()
    if 'aws_region' in data:
        AWS_DEFAULT_REGION = data['aws_region'].strip()
    return jsonify({"success": True, "message": "Configuration updated."})


@app.route('/api/analyze', methods=['POST'])
def analyze_image_route():
    start_time  = time.time()
    image_bytes = None
    custom_key  = request.headers.get('X-OpenRouter-Key') or None
    target_engine = 'auto'

    try:
        if 'image' in request.files:
            image_bytes   = request.files['image'].read()
            target_engine = request.form.get('engine', 'auto')
        elif request.is_json:
            body          = request.get_json()
            b64_str       = body.get('image_base64', '')
            if ',' in b64_str:
                b64_str   = b64_str.split(',', 1)[1]
            if b64_str:
                image_bytes = base64.b64decode(b64_str)
            custom_key    = body.get('openrouter_key') or custom_key
            target_engine = body.get('engine', 'auto')

        if not image_bytes:
            return jsonify({"error": "No image payload provided."}), 400

        # 1. Try OpenRouter Vision
        effective_key = custom_key or OPENROUTER_API_KEY
        if target_engine in ('auto', 'openrouter') and effective_key:
            try:
                result = call_openrouter_vision(image_bytes, api_key=effective_key)
                used_model = result.pop('_used_model', OPENROUTER_MODEL)
                result['source']      = 'openrouter'
                result['engine_name'] = f'OpenRouter ({used_model.split("/")[-1]})'
                result['model']       = used_model
                result['latency_ms']  = int((time.time() - start_time) * 1000)
                return jsonify(result)
            except Exception as e:
                if target_engine == 'openrouter':
                    return jsonify({"error": f"OpenRouter Error: {str(e)}"}), 502

        # 2. Try AWS Rekognition
        has_aws = bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)
        if target_engine in ('auto', 'aws') and has_aws:
            try:
                raw_aws = call_aws_rekognition(image_bytes, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION)
                result  = synthesize_rekognition_captions(raw_aws)
                result['source']      = 'aws_rekognition'
                result['engine_name'] = f'AWS Rekognition ({AWS_DEFAULT_REGION})'
                result['latency_ms']  = int((time.time() - start_time) * 1000)
                return jsonify(result)
            except Exception as e:
                if target_engine == 'aws':
                    return jsonify({"error": f"AWS Error: {str(e)}"}), 502

        # 3. Demo fallback
        result = get_demo_analysis()
        result['source']      = 'demo'
        result['engine_name'] = 'Simulation Engine (Add API Key in Settings)'
        result['latency_ms']  = int((time.time() - start_time) * 1000)
        return jsonify(result)

    except Exception as exc:
        return jsonify({"error": f"Processing failed: {str(exc)}"}), 500


# Export for Vercel WSGI handler
application = app

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
