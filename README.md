# 🖼️ AI Image Caption Generator (AWS Rekognition & Bedrock)

A full-stack AI Image Caption Generator web application that analyzes images and generates rich captions, scene summaries, detected entities, tags, and OCR text using **AWS Rekognition** and **AWS Bedrock**.

---

## 🌟 Key Features

- **AWS Rekognition Integration**: Leverages AWS Deep Learning models via `DetectLabels`, `DetectText`, and image properties.
- **Smart Caption Synthesis**: Automatically constructs natural language captions, short badges, hashtags, and descriptive summaries from AWS image analysis.
- **Modern Responsive UI**: Sleek dark-mode interface with glassmorphism, drag-and-drop file upload, clipboard paste (`Ctrl+V`), and sample image presets.
- **Speech Synthesis (TTS)**: Built-in text-to-speech button to listen to generated image captions out loud.
- **AWS Key Configuration via UI & `.env`**: Configure `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_DEFAULT_REGION` directly inside the web UI modal or via `.env`.
- **Demo / Offline Fallback**: Works immediately even before AWS keys are added, allowing you to preview and test the complete workflow without interruption.

---

## 📁 Project Structure (Single-Folder Layout)

```
ai-image-caption-generator/
├── index.html          # Web UI layout (served at /)
├── style.css           # Glassmorphism dark-mode styles
├── app.js              # Frontend logic & API interaction
├── app.py              # Flask server & REST API
├── aws_service.py      # AWS Rekognition & Bedrock client
├── caption_engine.py   # Caption synthesis & heuristics
├── api/
│   └── index.py        # Vercel Serverless Function entrypoint
├── tests/
│   └── test_api.py     # Automated tests
├── vercel.json         # Vercel routing configuration
├── .env.example        # Environment variables template
├── requirements.txt    # Python dependencies
├── run.py              # Local server launcher
└── README.md
```

---

## 🚀 Quick Start Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure AWS Credentials (Optional)
You can configure credentials either via `.env` file:
```bash
cp .env.example .env
```
Edit `.env`:
```ini
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
```
*Note: Your IAM user needs the `AmazonRekognitionReadOnlyAccess` policy.*
Alternatively, you can click **"⚙️ AWS Settings"** directly in the Web UI to enter your credentials securely.

### 3. Run the Application
```bash
python run.py
```
Open your browser at:
👉 **`http://localhost:5000`**

---

## ⚡ Deploy to Vercel

This repository includes built-in Vercel configuration (`vercel.json` and `api/index.py`), allowing seamless deployment on Vercel:

### Method 1: Deploy via Vercel Dashboard
1. Go to [vercel.com](https://vercel.com) and click **"Add New..."** > **"Project"**.
2. Import this repository: `atulsingh9040/ai-image-caption-generator`.
3. Under **Environment Variables**, add:
   - `AWS_ACCESS_KEY_ID`: *(Your AWS Access Key)*
   - `AWS_SECRET_ACCESS_KEY`: *(Your AWS Secret Key)*
   - `AWS_DEFAULT_REGION`: `us-east-1`
4. Click **Deploy**!
   - Vercel automatically deploys the frontend static assets and routes `/api/*` to the Python serverless function.

### Method 2: Deploy via Vercel CLI
```bash
npm i -g vercel
vercel
```

---

## 🧪 Testing the Application

Run the automated test suite:
```bash
python -m unittest tests/test_api.py
```
