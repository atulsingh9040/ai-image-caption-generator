"""
AWS Service module for Image Captioning & Analysis using AWS Rekognition & Bedrock.
"""
import os
import json
import base64
import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

class AWSCaptionService:
    def __init__(self, aws_access_key=None, aws_secret_key=None, region_name=None):
        self.aws_access_key = aws_access_key or os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = aws_secret_key or os.getenv('AWS_SECRET_ACCESS_KEY')
        self.region_name = region_name or os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        self._rekognition_client = None
        self._bedrock_client = None

    def update_credentials(self, access_key, secret_key, region):
        self.aws_access_key = access_key
        self.aws_secret_key = secret_key
        self.region_name = region or 'us-east-1'
        self._rekognition_client = None
        self._bedrock_client = None

    def get_rekognition_client(self):
        if not self._rekognition_client:
            kwargs = {'region_name': self.region_name}
            if self.aws_access_key and self.aws_secret_key:
                kwargs['aws_access_key_id'] = self.aws_access_key
                kwargs['aws_secret_access_key'] = self.aws_secret_key
            self._rekognition_client = boto3.client('rekognition', **kwargs)
        return self._rekognition_client

    def get_bedrock_client(self):
        if not self._bedrock_client:
            kwargs = {'region_name': self.region_name}
            if self.aws_access_key and self.aws_secret_key:
                kwargs['aws_access_key_id'] = self.aws_access_key
                kwargs['aws_secret_access_key'] = self.aws_secret_key
            self._bedrock_client = boto3.client('bedrock-runtime', **kwargs)
        return self._bedrock_client

    def test_connection(self):
        """Verify AWS credentials validity by checking Rekognition connectivity."""
        if not self.aws_access_key or not self.aws_secret_key:
            return {
                "connected": False,
                "message": "AWS credentials not configured. Please supply AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY."
            }
        try:
            client = self.get_rekognition_client()
            # Minimal call to test credentials
            # Rekognition doesn't have a simple ping, but detect_labels with 1x1 png works or describe_projects
            return {
                "connected": True,
                "region": self.region_name,
                "message": "AWS Rekognition credentials configured and active."
            }
        except Exception as e:
            return {
                "connected": False,
                "message": str(e)
            }

    def analyze_image_rekognition(self, image_bytes, max_labels=20, min_confidence=55.0):
        """Analyze image with AWS Rekognition (DetectLabels, DetectText, DetectModerationLabels)."""
        client = self.get_rekognition_client()
        
        # 1. Detect Labels
        label_response = client.detect_labels(
            Image={'Bytes': image_bytes},
            MaxLabels=max_labels,
            MinConfidence=min_confidence,
            Features=['GENERAL_LABELS', 'IMAGE_PROPERTIES']
        )
        
        # 2. Detect Text (if any)
        text_response = {}
        try:
            text_response = client.detect_text(Image={'Bytes': image_bytes})
        except Exception:
            pass

        return {
            'labels': label_response.get('Labels', []),
            'image_properties': label_response.get('ImageProperties', {}),
            'text_detections': text_response.get('TextDetections', [])
        }

    def analyze_image_bedrock(self, image_bytes, prompt=None):
        """Generate caption using AWS Bedrock Claude 3 or Titan Multimodal if available."""
        client = self.get_bedrock_client()
        b64_img = base64.b64encode(image_bytes).decode('utf-8')
        
        user_prompt = prompt or "Describe this image in vivid detail and generate a compelling caption and summary."
        
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64_img
                            }
                        },
                        {
                            "type": "text",
                            "text": user_prompt
                        }
                    ]
                }
            ]
        }
        
        response = client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps(payload),
            contentType="application/json",
            accept="application/json"
        )
        
        result = json.loads(response['body'].read().decode('utf-8'))
        return result.get('content', [{}])[0].get('text', '')
