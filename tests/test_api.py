"""
Automated unit tests for the AI Caption Generator Backend.
"""
import unittest
import json
import io
from backend.app import app

class TestCaptionGeneratorAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_status_endpoint(self):
        response = self.app.get('/api/status')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get('status'), 'online')
        self.assertIn('aws_configured', data)

    def test_analyze_demo_mode(self):
        # Create a small dummy 1x1 image
        dummy_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        
        data = {
            'image': (io.BytesIO(dummy_png), 'test.png')
        }
        response = self.app.post('/api/analyze', data=data, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        res_data = json.loads(response.data)
        self.assertIn('primary_caption', res_data)
        self.assertIn('labels_summary', res_data)
        self.assertIn('hashtags', res_data)

    def test_config_endpoint_validation(self):
        # Missing keys
        response = self.app.post('/api/config', json={})
        self.assertEqual(response.status_code, 400)

        # Valid payload
        response = self.app.post('/api/config', json={
            'aws_access_key_id': 'TEST_KEY',
            'aws_secret_access_key': 'TEST_SECRET',
            'aws_region': 'us-east-1'
        })
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get('success'))

if __name__ == '__main__':
    unittest.main()
