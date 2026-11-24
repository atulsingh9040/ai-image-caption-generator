"""
Flask Backend Application for AI Image Caption Generator using AWS API.
"""
import os
import io
import base64
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from backend.aws_service import AWSCaptionService
from backend.caption_engine import CaptionEngine

# Load environment variables
load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

# Initialize AWS Service
aws_service = AWSCaptionService(
    aws_access_key=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
)

@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    has_creds = bool(aws_service.aws_access_key and aws_service.aws_secret_key)
    return jsonify({
        "status": "online",
        "aws_configured": has_creds,
        "region": aws_service.region_name,
        "service": "AWS Rekognition & Bedrock AI Caption Generator"
    })

@app.route('/api/config', methods=['POST'])
def update_config():
    data = request.json or {}
    access_key = data.get('aws_access_key_id')
    secret_key = data.get('aws_secret_access_key')
    region = data.get('aws_region', 'us-east-1')

    if not access_key or not secret_key:
        return jsonify({"success": False, "error": "Both Access Key ID and Secret Key are required"}), 400

    aws_service.update_credentials(access_key, secret_key, region)
    return jsonify({
        "success": True,
        "message": f"AWS credentials updated successfully for region {region}."
    })

@app.route('/api/analyze', methods=['POST'])
def analyze_image():
    try:
        image_bytes = None
        use_demo = False

        # Support both multipart file upload and base64 JSON payload
        if 'image' in request.files:
            file = request.files['image']
            image_bytes = file.read()
        elif request.is_json:
            data = request.get_json()
            if 'image_base64' in data:
                b64_str = data['image_base64']
                if ',' in b64_str:
                    b64_str = b64_str.split(',', 1)[1]
                image_bytes = base64.b64decode(b64_str)
            if data.get('demo_mode'):
                use_demo = True

        if not image_bytes:
            return jsonify({"error": "No image data provided"}), 400

        # Check if AWS credentials are valid or user requested demo
        has_creds = bool(aws_service.aws_access_key and aws_service.aws_secret_key)
        
        if not has_creds or use_demo:
            # Return smart simulated analysis with clear notice
            result = CaptionEngine.get_mock_caption()
            result['source'] = 'demo'
            return jsonify(result)

        # Call AWS Rekognition
        try:
            raw_analysis = aws_service.analyze_image_rekognition(image_bytes)
            caption_result = CaptionEngine.generate_captions_from_rekognition(raw_analysis)
            caption_result['source'] = 'aws_rekognition'
            caption_result['raw_labels_count'] = len(raw_analysis.get('labels', []))
            return jsonify(caption_result)

        except Exception as aws_err:
            # If AWS error occurred (e.g. invalid keys or unauthorized), return error with option to use demo
            error_message = str(aws_err)
            return jsonify({
                "error": f"AWS API Error: {error_message}",
                "suggestion": "Check your AWS Access Key, Secret Key, and Region permissions in Settings."
            }), 502

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 AI Image Caption Generator starting on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
